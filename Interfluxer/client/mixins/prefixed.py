import contextlib
from asyncio import TimeoutError
from collections import defaultdict
from typing import Optional, Callable, Any, Coroutine, Iterable, TYPE_CHECKING

from typing_extensions import Self

from Interfluxer.api.events.base import RawGatewayEvent
from Interfluxer.api.events.fluxer import MessageCreate
from Interfluxer.api.events.internal import (
    CommandError,
    CommandCompletion,
    ExtensionUnload,
)
from Interfluxer.client.utils.input_utils import get_args, get_first_word
from Interfluxer.models.external.enums import Intents
from Interfluxer.models.external.message import Message
from Interfluxer.models.internal.prefixed.command import PrefixedCommand
from Interfluxer.models.internal.prefixed.context import PrefixedContext
from Interfluxer.models.internal.prefixed.utils import when_mentioned

if TYPE_CHECKING:
    from Interfluxer.client.client import Client

__all__ = ("PrefixedCommandsMixin",)


class _PrefixedFacade:
    """Lightweight proxy that preserves ``client.prefixed.commands`` access."""

    __slots__ = ("_client",)

    def __init__(self, client: "Client") -> None:
        self._client = client

    @property
    def commands(self) -> dict[str, PrefixedCommand]:
        return self._client.prefixed_commands

    def add_command(self, command: PrefixedCommand) -> None:
        return self._client.add_prefixed_command(command)

    def get_command(self, name: str) -> Optional[PrefixedCommand]:
        return self._client.get_prefixed_command(name)

    def remove_command(self, name: str, delete_parent_if_empty: bool = False) -> Optional[PrefixedCommand]:
        return self._client.remove_prefixed_command(name, delete_parent_if_empty)


class PrefixedCommandsMixin:
    """Mixin that provides prefixed command support to the Client."""

    def _init_prefixed_commands(
        self,
        default_prefix: Optional[str | list[str]] = None,
        generate_prefixes: Optional[
            Callable[
                ["Client", Message],
                Coroutine[Any, Any, str | list[str]],
            ]
        ] = None,
        prefixed_context: type[PrefixedContext] = PrefixedContext,
        help_command: bool = True,
    ) -> None:
        self.prefixed_commands: dict[str, PrefixedCommand] = {}
        self._prefixed_default_prefix = default_prefix
        self._prefixed_context_cls = prefixed_context
        self._prefixed_ext_command_list: defaultdict[str, set[str]] = defaultdict(set)
        self._prefixed_facade = _PrefixedFacade(self)  # type: ignore[arg-type]

        if (
            default_prefix or (generate_prefixes and generate_prefixes != when_mentioned)
        ) and Intents.MESSAGE_CONTENT not in self.intents:  # type: ignore[attr-defined]
            self.logger.warning(  # type: ignore[attr-defined]
                "Prefixed commands will not work since the required intent is not set -> Requires:"
                f" {Intents.MESSAGE_CONTENT.__repr__()} or usage of the default mention prefix as the prefix"
            )

        if default_prefix is None and generate_prefixes is None:
            generate_prefixes = when_mentioned

        if generate_prefixes is not None:
            self._prefixed_generate_prefixes = generate_prefixes
        else:
            self._prefixed_generate_prefixes = self._prefixed_default_generate_prefixes

        if help_command:
            from Interfluxer.models.internal.prefixed.help import PrefixedHelpCommand

            PrefixedHelpCommand(self).register()  # type: ignore[arg-type]

        # Create and register listeners manually (not via decorators) to avoid
        # _gather_callbacks discovering them and registering duplicates.
        from Interfluxer.models.internal.listener import Listener

        dispatch_listener = Listener.create("raw_message_create", is_default_listener=True)(
            self._dispatch_prefixed_commands
        )
        unload_listener = Listener.create("extension_unload")(self._handle_prefixed_ext_unload)

        self.add_listener(dispatch_listener)  # type: ignore[attr-defined]
        self.add_listener(unload_listener)  # type: ignore[attr-defined]

        self._add_command_hook.append(self._register_prefixed_command)  # type: ignore[attr-defined]

    async def _prefixed_default_generate_prefixes(self, client: "Client", msg: Message) -> str | list[str]:
        return self._prefixed_default_prefix  # type: ignore

    @property
    def prefixed(self) -> _PrefixedFacade:
        """Backwards-compatible facade for ``client.prefixed.commands`` etc."""
        return self._prefixed_facade

    def add_prefixed_command(self, command: PrefixedCommand) -> None:
        """
        Add a prefixed command to the client.

        Args:
            command: The command to add.

        """
        if command.is_subcommand:
            raise ValueError("You cannot add subcommands to the client - add the base command instead.")

        command._parse_parameters()

        if self.prefixed_commands.get(command.name):
            raise ValueError(f"Duplicate command! Multiple commands share the name/alias: {command.name}.")
        self.prefixed_commands[command.name] = command

        for alias in command.aliases:
            if self.prefixed_commands.get(alias):
                raise ValueError(f"Duplicate command! Multiple commands share the name/alias: {alias}.")
            self.prefixed_commands[alias] = command

        if command.extension:
            self._prefixed_ext_command_list[command.extension.extension_name].add(command.name)
            command.extension._commands.append(command)

    def get_prefixed_command(self, name: str) -> Optional[PrefixedCommand]:
        """
        Gets a prefixed command by the name/alias specified.

        This function is able to resolve subcommands - fully qualified names can be used.

        Args:
            name: The name of the command to search for.

        Returns:
            The command object, if found.

        """
        if " " not in name:
            return self.prefixed_commands.get(name)

        names = name.split()
        if not names:
            return None

        cmd = self.prefixed_commands.get(names[0])
        if not cmd:
            return cmd

        for name in names[1:]:
            try:
                cmd = cmd.subcommands[name]
            except (AttributeError, KeyError):
                return None

        return cmd

    def _remove_prefixed_cmd_and_aliases(self, name: str) -> None:
        if cmd := self.prefixed_commands.pop(name, None):
            if cmd.extension:
                self._prefixed_ext_command_list[cmd.extension.extension_name].discard(cmd.name)
                with contextlib.suppress(ValueError):
                    cmd.extension._commands.remove(cmd)

            for alias in cmd.aliases:
                self.prefixed_commands.pop(alias, None)

    def remove_prefixed_command(self, name: str, delete_parent_if_empty: bool = False) -> Optional[PrefixedCommand]:
        """
        Removes a prefixed command if it exists.

        Args:
            name: The command to remove.
            delete_parent_if_empty: Should the parent command be deleted if it \
                ends up having no subcommands after deleting the command specified?

        Returns:
            The command that was removed, if one was.

        """
        command = self.get_prefixed_command(name)

        if command is None:
            return None

        if name in command.aliases:
            command.aliases.remove(name)
            return command

        if command.parent:
            command.parent.remove_command(command.name)
        else:
            self._remove_prefixed_cmd_and_aliases(command.name)

        if delete_parent_if_empty:
            while command.parent is not None and not command.parent.subcommands:
                if command.parent.parent:
                    _new_cmd = command.parent
                    command.parent.parent.remove_command(command.parent.name)
                    command = _new_cmd
                else:
                    self._remove_prefixed_cmd_and_aliases(command.parent.name)
                    break

        return command

    def _register_prefixed_command(self, callback: Callable) -> None:
        """Registers a prefixed command, if there is one given."""
        if not isinstance(callback, PrefixedCommand):
            return

        if not callback.is_subcommand:
            self.add_prefixed_command(callback)

    async def _handle_prefixed_ext_unload(self, event: ExtensionUnload) -> None:
        """Unregisters all prefixed commands in an extension as it is being unloaded."""
        for name in self._prefixed_ext_command_list[event.extension.extension_name].copy():
            self.remove_prefixed_command(name)

    async def _dispatch_prefixed_commands(self, event: RawGatewayEvent) -> None:  # noqa: C901
        """Determine if a prefixed command is being triggered, and dispatch it."""
        if not self.prefixed_commands:
            return

        data = event.data

        if not data.get("content"):
            return

        if data.get("webhook_id") or data["author"].get("bot", False):
            return

        message = self.cache.get_message(int(data["channel_id"]), int(data["id"]))  # type: ignore[attr-defined]

        if message and (
            (not message._guild_id and event.data.get("guild_id"))
            or (message._guild_id and not message.guild)
            or not message.channel
        ):
            message = None

        if not message:
            try:
                msg_event: MessageCreate = await self.wait_for(  # type: ignore[attr-defined]
                    MessageCreate, checks=lambda e: int(e.message.id) == int(data["id"]), timeout=2
                )
                message = msg_event.message
            except TimeoutError:
                return

        if not message.content:
            return

        prefixes: str | Iterable[str] = await self._prefixed_generate_prefixes(self, message)  # type: ignore[arg-type]

        if isinstance(prefixes, str):
            prefixes = (prefixes,)  # type: ignore

        prefix_used = next(
            (prefix for prefix in prefixes if message.content.startswith(prefix)),
            None,
        )
        if not prefix_used:
            return

        context = self._prefixed_context_cls.from_message(self, message)  # type: ignore[arg-type]
        context.prefix = prefix_used

        content_parameters = message.content.removeprefix(prefix_used).strip()
        command: "Self | PrefixedCommand" = self  # yes, this is a hack

        while True:
            first_word: str = get_first_word(content_parameters)  # type: ignore
            if isinstance(command, PrefixedCommand):
                new_command = command.subcommands.get(first_word)
            else:
                new_command = command.prefixed_commands.get(first_word)  # type: ignore[attr-defined]
            if not new_command or not new_command.enabled:
                break

            command = new_command
            content_parameters = content_parameters.removeprefix(first_word).strip()

        if not isinstance(command, PrefixedCommand) or not command.enabled:
            return

        context.command = command
        context.content_parameters = content_parameters.strip()
        context.args = get_args(context.content_parameters)
        try:
            if self.pre_run_callback:  # type: ignore[attr-defined]
                await self.pre_run_callback(context)  # type: ignore[attr-defined]
            await command(context)
            if self.post_run_callback:  # type: ignore[attr-defined]
                await self.post_run_callback(context)  # type: ignore[attr-defined]
        except Exception as e:
            self.dispatch(CommandError(ctx=context, error=e))  # type: ignore[attr-defined]
        finally:
            self.dispatch(CommandCompletion(ctx=context))  # type: ignore[attr-defined]
