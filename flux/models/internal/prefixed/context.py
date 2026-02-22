from typing import TYPE_CHECKING, Any, Iterable, Optional, Union

from typing_extensions import Self

from flux.client.const import ClientT
from flux.client.mixins.send import SendMixin
from flux.models.external.channel import TYPE_MESSAGEABLE_CHANNEL
from flux.models.external.embed import Embed
from flux.models.external.file import UPLOADABLE_TYPE
from flux.models.external.message import Message, MessageReference
from flux.models.internal.context import BaseContext
from flux.models.misc.context_manager import Typing

if TYPE_CHECKING:
    from .command import PrefixedCommand

__all__ = ("PrefixedContext",)


class PrefixedContext(BaseContext[ClientT], SendMixin):
    _message: Message

    prefix: str
    "The prefix used to invoke this command."
    content_parameters: str
    "The message content without the command and prefix."
    command: "PrefixedCommand"
    "The command this context invokes."

    args: list[str]
    "The arguments passed to the message."
    kwargs: dict
    "This is always empty, and is only here for compatibility with other types of commands."

    @classmethod
    def from_dict(cls, client: "ClientT", payload: dict) -> Self:
        # this doesn't mean anything, so just implement it to make abc happy
        raise NotImplementedError

    @classmethod
    def from_message(cls, client: "ClientT", message: Message) -> Self:
        instance = cls(client=client)

        # hack to work around BaseContext property
        # since the message is the most important part of the context,
        # we don't want to rely on the cache for it
        instance._message = message

        instance.message_id = message.id
        instance.author_id = message._author_id
        instance.channel_id = message._channel_id
        instance.guild_id = message._guild_id

        instance.prefix = ""
        instance.content_parameters = ""
        instance.command = None  # type: ignore
        instance.args = []
        instance.kwargs = {}
        return instance

    @property
    def message(self) -> Message:
        """The message that invoked this context."""
        return self._message

    @property
    def channel(self) -> TYPE_MESSAGEABLE_CHANNEL:
        """The channel this context was invoked in."""
        return self.message.channel

    @property
    def invoke_target(self) -> str:
        """The name of the command to be invoked."""
        return self.command.name

    @property
    def typing(self) -> Typing:
        """A context manager to send a typing state to the context's channel as long as the wrapped operation takes."""
        return self.channel.typing

    async def _send_http_request(self, message_payload: dict, files: Iterable["UPLOADABLE_TYPE"] | None = None) -> dict:
        return await self.client.http.create_message(message_payload, self.channel_id, files=files)

    async def reply(
        self,
        content: Optional[str] = None,
        embeds: Optional[Union[Iterable[Union[Embed, dict]], Union[Embed, dict]]] = None,
        embed: Optional[Union[Embed, dict]] = None,
        fail_if_not_exists: bool = True,
        **kwargs: Any,
    ) -> Message:
        """
        Reply to the context's message. Takes all the same attributes as `send`.

        Args:
            content: Message text content.
            embeds: Embedded rich content (up to 6000 characters).
            embed: Embedded rich content (up to 6000 characters).
            fail_if_not_exists: Whether to error if the command invocation doesn't exist instead of sending as a normal (non-reply) message.
            **kwargs: Additional options to pass to `send`.

        Returns:
            New message object.

        """
        ref = MessageReference.for_message(self.message, fail_if_not_exists=fail_if_not_exists)
        return await self.send(content=content, reply_to=ref, embeds=embeds or embed, **kwargs)
