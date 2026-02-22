import asyncio
import contextlib
import functools
import glob
import importlib.util
import inspect
import logging
import os
import re
import sys
import traceback
from collections.abc import Iterable
from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Union,
    Awaitable,
    TypeVar,
    overload,
)

from aiohttp import BasicAuth

import flux.api.events as events
import flux.client.const as constants
from flux.api.events import BaseEvent, processors, CallbackAdded
from flux.api.gateway.gateway import GatewayClient
from flux.api.gateway.state import ConnectionState
from flux.api.http.http_client import HTTPClient
from flux.client.const import (
    Missing,
    MISSING,
    Absent,
    get_logger,
    AsyncCallable,
)
from flux.client.errors import (
    BotException,
    ExtensionLoadException,
    ExtensionNotFound,
    HTTPException,
    NotFound,
)
from flux.client.smart_cache import GlobalCache
from flux.client.utils import NullCache
from flux.client.utils.misc_utils import get_event_name, wrap_partial
from flux.client.utils.serializer import to_image_data
from flux.models import (
    Activity,
    Application,
    CustomEmoji,
    Guild,
    GuildTemplate,
    Extension,
    ClientUser,
    User,
    Member,
    StickerPack,
    Sticker,
    ScheduledEvent,
    to_snowflake,
    VoiceRegion,
)
from flux.models import Wait
from flux.models.discord.entitlement import Entitlement
from flux.models.discord.enums import (
    Intents,
    Status,
)
from flux.models.discord.file import UPLOADABLE_TYPE
from flux.client.mixins.prefixed import PrefixedCommandsMixin
from flux.models.internal.active_voice_state import ActiveVoiceState
from flux.models.internal.callback import CallbackObject
from flux.models.internal.listener import Listener
from flux.models.internal.prefixed.context import PrefixedContext
from flux.models.internal.tasks import Task

if TYPE_CHECKING:
    from flux.models import Snowflake_Type, TYPE_ALL_CHANNEL
    from flux.models.discord.message import Message

EventT = TypeVar("EventT", bound=BaseEvent)

__all__ = ("Client",)

# see https://discord.com/developers/docs/topics/gateway#list-of-intents
_INTENT_EVENTS: dict[BaseEvent, list[Intents]] = {
    # Intents.GUILDS
    events.GuildJoin: [Intents.GUILDS],
    events.GuildLeft: [Intents.GUILDS],
    events.GuildUpdate: [Intents.GUILDS],
    events.RoleCreate: [Intents.GUILDS],
    events.RoleDelete: [Intents.GUILDS],
    events.RoleUpdate: [Intents.GUILDS],
    events.ChannelCreate: [Intents.GUILDS],
    events.ChannelDelete: [Intents.GUILDS],
    events.ChannelUpdate: [Intents.GUILDS],
    events.ThreadCreate: [Intents.GUILDS],
    events.ThreadDelete: [Intents.GUILDS],
    events.ThreadListSync: [Intents.GUILDS],
    events.ThreadMemberUpdate: [Intents.GUILDS],
    events.ThreadUpdate: [Intents.GUILDS],
    events.StageInstanceCreate: [Intents.GUILDS],
    events.StageInstanceDelete: [Intents.GUILDS],
    events.StageInstanceUpdate: [Intents.GUILDS],
    # Intents.GUILD_MEMBERS
    events.MemberAdd: [Intents.GUILD_MEMBERS],
    events.MemberRemove: [Intents.GUILD_MEMBERS],
    events.MemberUpdate: [Intents.GUILD_MEMBERS],
    # Intents.GUILD_MODERATION
    events.BanCreate: [Intents.GUILD_MODERATION],
    events.BanRemove: [Intents.GUILD_MODERATION],
    events.GuildAuditLogEntryCreate: [Intents.GUILD_MODERATION],
    # Intents.GUILD_EXPRESSIONS
    events.GuildEmojisUpdate: [Intents.GUILD_EXPRESSIONS],
    events.GuildStickersUpdate: [Intents.GUILD_EXPRESSIONS],
    # Intents.GUILD_INTEGRATIONS
    events.IntegrationCreate: [Intents.GUILD_INTEGRATIONS],
    events.IntegrationDelete: [Intents.GUILD_INTEGRATIONS],
    events.IntegrationUpdate: [Intents.GUILD_INTEGRATIONS],
    # Intents.GUILD_WEBHOOKS
    events.WebhooksUpdate: [Intents.GUILD_WEBHOOKS],
    # Intents.GUILD_INVITES
    events.InviteCreate: [Intents.GUILD_INVITES],
    events.InviteDelete: [Intents.GUILD_INVITES],
    # Intents.GUILD_VOICE_STATES
    events.VoiceStateUpdate: [Intents.GUILD_VOICE_STATES],
    # Intents.GUILD_PRESENCES
    events.PresenceUpdate: [Intents.GUILD_PRESENCES],
    # Intents.GUILD_MESSAGES
    events.MessageDeleteBulk: [Intents.GUILD_MESSAGES],
    # Intents.AUTO_MODERATION_CONFIGURATION
    events.AutoModExec: [Intents.AUTO_MODERATION_EXECUTION, Intents.AUTO_MOD],
    # Intents.AUTO_MODERATION_CONFIGURATION
    events.AutoModCreated: [Intents.AUTO_MODERATION_CONFIGURATION, Intents.AUTO_MOD],
    events.AutoModUpdated: [Intents.AUTO_MODERATION_CONFIGURATION, Intents.AUTO_MOD],
    events.AutoModDeleted: [Intents.AUTO_MODERATION_CONFIGURATION, Intents.AUTO_MOD],
    # Intents.GUILD_SCHEDULED_EVENTS
    events.GuildScheduledEventCreate: [Intents.GUILD_SCHEDULED_EVENTS],
    events.GuildScheduledEventUpdate: [Intents.GUILD_SCHEDULED_EVENTS],
    events.GuildScheduledEventDelete: [Intents.GUILD_SCHEDULED_EVENTS],
    events.GuildScheduledEventUserAdd: [Intents.GUILD_SCHEDULED_EVENTS],
    events.GuildScheduledEventUserRemove: [Intents.GUILD_SCHEDULED_EVENTS],
    # multiple intents
    events.ThreadMembersUpdate: [Intents.GUILDS, Intents.GUILD_MEMBERS],
    events.TypingStart: [
        Intents.GUILD_MESSAGE_TYPING,
        Intents.DIRECT_MESSAGE_TYPING,
        Intents.TYPING,
    ],
    events.MessageUpdate: [Intents.GUILD_MESSAGES, Intents.DIRECT_MESSAGES, Intents.MESSAGES],
    events.MessageCreate: [Intents.GUILD_MESSAGES, Intents.DIRECT_MESSAGES, Intents.MESSAGES],
    events.MessageDelete: [Intents.GUILD_MESSAGES, Intents.DIRECT_MESSAGES, Intents.MESSAGES],
    events.ChannelPinsUpdate: [Intents.GUILDS, Intents.DIRECT_MESSAGES],
    events.MessageReactionAdd: [
        Intents.GUILD_MESSAGE_REACTIONS,
        Intents.DIRECT_MESSAGE_REACTIONS,
        Intents.REACTIONS,
    ],
    events.MessageReactionRemove: [
        Intents.GUILD_MESSAGE_REACTIONS,
        Intents.DIRECT_MESSAGE_REACTIONS,
        Intents.REACTIONS,
    ],
    events.MessageReactionRemoveAll: [
        Intents.GUILD_MESSAGE_REACTIONS,
        Intents.DIRECT_MESSAGE_REACTIONS,
        Intents.REACTIONS,
    ],
    events.MessageReactionRemoveEmoji: [
        Intents.GUILD_MESSAGE_REACTIONS,
        Intents.DIRECT_MESSAGE_REACTIONS,
        Intents.REACTIONS,
    ],
}


class Client(
    processors.AutoModEvents,
    processors.ChannelEvents,
    processors.EntitlementEvents,
    processors.GuildEvents,
    processors.IntegrationEvents,
    processors.MemberEvents,
    processors.MessageEvents,
    processors.ReactionEvents,
    processors.RoleEvents,
    processors.ScheduledEvents,
    processors.StageEvents,
    processors.ThreadEvents,
    processors.UserEvents,
    processors.VoiceEvents,
    PrefixedCommandsMixin,
):
    """

    The bot client.

    Args:
        intents: The intents to use

        status: The status the bot should log in with (IE ONLINE, DND, IDLE)
        activity: The activity the bot should log in "playing"

        fetch_members: Should the client fetch members from guilds upon startup (this will delay the client being ready)
        send_command_tracebacks: Automatically send uncaught tracebacks if a command throws an exception

        total_shards: The total number of shards in use
        shard_id: The zero based int ID of this shard

        basic_logging: Utilise basic logging to output library data to console. Do not use in combination with `Client.logger`
        logging_level: The level of logging to use for basic_logging. Do not use in combination with `Client.logger`
        logger: The logger flux.py should use. Do not use in combination with `Client.basic_logging` and `Client.logging_level`. Note: Different loggers with multiple clients are not supported

        proxy: A http/https proxy to use for all requests
        proxy_auth: The auth to use for the proxy - must be either a tuple of (username, password) or aiohttp.BasicAuth

    Optionally, you can configure the caches here, by specifying the name of the cache, followed by a dict-style object to use.
    It is recommended to use `smart_cache.create_cache` to configure the cache here.
    as an example, this is a recommended attribute `message_cache=create_cache(250, 50)`,

    ???+ note "Intents Note"
        By default, all non-privileged intents will be enabled

    ???+ note "Caching Note"
        Setting a message cache hard limit to None is not recommended, as it could result in extremely high memory usage, we suggest a sane limit.


    """

    def __init__(
        self,
        *,
        activity: Union[Activity, str] = None,
        basic_logging: bool = False,
        default_prefix: Optional[str | list[str]] = None,
        fetch_members: bool = False,
        generate_prefixes: Optional[
            Callable[
                ["Client", "Message"],
                Coroutine[Any, Any, str | list[str]],
            ]
        ] = None,
        global_post_run_callback: Absent[Callable[..., Coroutine]] = MISSING,
        global_pre_run_callback: Absent[Callable[..., Coroutine]] = MISSING,
        intents: Union[int, Intents] = Intents.DEFAULT,
        logger: logging.Logger = MISSING,
        logging_level: int = logging.INFO,
        owner_ids: Iterable["Snowflake_Type"] = (),
        prefixed_context: type[PrefixedContext] = PrefixedContext,
        send_command_tracebacks: bool = True,
        shard_id: int = 0,
        show_ratelimit_tracebacks: bool = False,
        status: Status = Status.ONLINE,
        sync_ext: bool = True,
        proxy_url: str | None = None,
        proxy_auth: BasicAuth | tuple[str, str] | None = None,
        token: str | None = None,
        total_shards: int = 1,
        **kwargs,
    ) -> None:
        if logger is MISSING:
            logger = constants.get_logger()

        if basic_logging:
            logging.basicConfig()
            logger.setLevel(logging_level)

        # Set Up logger and overwrite the constant
        self.logger = logger
        """The logger flux.py should use. Do not use in combination with `Client.basic_logging` and `Client.logging_level`.
        !!! note
            Different loggers with multiple clients are not supported"""
        constants._logger = logger

        # Configuration
        self.send_command_tracebacks: bool = send_command_tracebacks
        """Should the traceback of command errors be sent in reply to the command invocation"""
        self.intents = intents if isinstance(intents, Intents) else Intents(intents)

        # resources
        if isinstance(proxy_auth, tuple):
            proxy_auth = BasicAuth(*proxy_auth)

        proxy = (proxy_url, proxy_auth) if proxy_url or proxy_auth else None
        self.http: HTTPClient = HTTPClient(
            logger=self.logger, show_ratelimit_tracebacks=show_ratelimit_tracebacks, proxy=proxy
        )
        """The HTTP client to use when interacting with discord endpoints"""

        self.token: str | None = token

        # flags
        self._ready = asyncio.Event()
        self._closed = False
        self._startup = False

        self._guild_event = asyncio.Event()
        self.guild_event_timeout = 3
        """How long to wait for guilds to be cached"""

        # Sharding
        self.total_shards = total_shards
        self._connection_state: ConnectionState = ConnectionState(self, intents, shard_id=shard_id)

        self.fetch_members = fetch_members
        """Fetch the full members list of all guilds on startup"""

        self._mention_reg = MISSING

        # caches
        self.cache: GlobalCache = GlobalCache(self, **{k: v for k, v in kwargs.items() if hasattr(GlobalCache, k)})
        # these store the last sent presence data for change_presence
        self._status: Status = status
        if isinstance(activity, str):
            self._activity = Activity.create(name=str(activity))
        else:
            self._activity: Activity = activity

        self._user: Absent[ClientUser] = MISSING
        self._app: Absent[Application] = MISSING

        # collections
        self.sync_ext = sync_ext
        self.processors: Dict[str, Callable[..., Coroutine]] = {}
        self.__modules = {}
        self.ext: Dict[str, Extension] = {}
        """A dictionary of mounted ext"""
        self.listeners: Dict[str, list[Listener]] = {}
        self.waits: Dict[str, List] = {}
        self.owner_ids: set[Snowflake_Type] = set(owner_ids)

        self.async_startup_tasks: list[tuple[Callable[..., Coroutine], Iterable[Any], dict[str, Any]]] = []
        """A list of coroutines to run during startup"""

        self._add_command_hook: list[Callable[[Callable], Any]] = []

        # callbacks
        if global_pre_run_callback:
            if asyncio.iscoroutinefunction(global_pre_run_callback):
                self.pre_run_callback: Callable[..., Coroutine] = global_pre_run_callback
            else:
                raise TypeError("Callback must be a coroutine")
        else:
            self.pre_run_callback = MISSING

        if global_post_run_callback:
            if asyncio.iscoroutinefunction(global_post_run_callback):
                self.post_run_callback: Callable[..., Coroutine] = global_post_run_callback
            else:
                raise TypeError("Callback must be a coroutine")
        else:
            self.post_run_callback = MISSING

        super().__init__()
        self._sanity_check()

        self._init_prefixed_commands(
            default_prefix=default_prefix,
            generate_prefixes=generate_prefixes,
            prefixed_context=prefixed_context,
        )

    async def __aenter__(self) -> "Client":
        if not self.token:
            raise ValueError(
                "Token not found - to use the bot in a context manager, you must pass the token in the Client"
                " constructor."
            )
        await self.login(self.token)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self.is_closed:
            await self.stop()

    @property
    def is_closed(self) -> bool:
        """Returns True if the bot has closed."""
        return self._closed

    @property
    def is_ready(self) -> bool:
        """Returns True if the bot is ready."""
        return self._ready.is_set()

    @property
    def latency(self) -> float:
        """Returns the latency of the websocket connection (seconds)."""
        return self._connection_state.latency

    @property
    def average_latency(self) -> float:
        """Returns the average latency of the websocket connection (seconds)."""
        return self._connection_state.average_latency

    @property
    def start_time(self) -> datetime:
        """The start time of the bot."""
        return self._connection_state.start_time

    @property
    def gateway_started(self) -> bool:
        """Returns if the gateway has been started."""
        return self._connection_state.gateway_started.is_set()

    @property
    def user(self) -> ClientUser:
        """Returns the bot's user."""
        return self._user

    @property
    def app(self) -> Application:
        """Returns the bots application."""
        return self._app

    @property
    def owner(self) -> Optional["User"]:
        """Returns the bot's owner'."""
        try:
            return self.app.owner
        except TypeError:
            return MISSING

    @property
    def owners(self) -> List["User"]:
        """Returns the bot's owners as declared via `client.owner_ids`."""
        return [self.get_user(u_id) for u_id in self.owner_ids]

    @property
    def guilds(self) -> List["Guild"]:
        """Returns a list of all guilds the bot is in."""
        return self.user.guilds

    @property
    def guild_count(self) -> int:
        """
        Returns the number of guilds the bot is in.

        This function is faster than using `len(client.guilds)` as it does not require using the cache.
        As such, this is preferred when you only need the count of guilds.
        """
        return self.user.guild_count

    @property
    def status(self) -> Status:
        """
        Get the status of the bot.

        IE online, afk, dnd

        """
        return self._status

    @property
    def activity(self) -> Activity:
        """Get the activity of the bot."""
        return self._activity

    @property
    def ws(self) -> GatewayClient:
        """Returns the websocket client."""
        return self._connection_state.gateway

    def get_guild_websocket(self, id: "Snowflake_Type") -> GatewayClient:
        return self.ws

    def _sanity_check(self) -> None:
        """Checks for possible and common errors in the bot's configuration."""
        self.logger.debug("Running client sanity checks...")

        if Intents.GUILDS not in self._connection_state.intents:
            self.logger.warning("GUILD intent has not been enabled; this is very likely to cause errors")

        if self.fetch_members and Intents.GUILD_MEMBERS not in self._connection_state.intents:
            raise BotException("Members Intent must be enabled in order to use fetch members")
        if self.fetch_members:
            self.logger.warning("fetch_members enabled; startup will be delayed")

        if len(self.processors) == 0:
            self.logger.warning("No Processors are loaded! This means no events will be processed!")

        caches = [
            c[0]
            for c in inspect.getmembers(self.cache, predicate=lambda x: isinstance(x, dict))
            if not c[0].startswith("__")
        ]
        for cache in caches:
            _cache_obj = getattr(self.cache, cache)
            if isinstance(_cache_obj, NullCache):
                self.logger.warning(f"{cache} has been disabled")

    def _queue_task(self, coro: Listener, event: BaseEvent, *args, **kwargs) -> asyncio.Task:
        async def _async_wrap(_coro: Listener, _event: BaseEvent, *_args, **_kwargs) -> None:
            try:
                if (
                    not isinstance(_event, (events.Error, events.RawGatewayEvent))
                    and coro.delay_until_ready
                    and not self.is_ready
                ):
                    await self.wait_until_ready()

                # don't pass event object if listener doesn't expect it
                if _coro.pass_event_object:
                    await _coro(_event, *_args, **_kwargs)
                else:
                    if not _coro.warned_no_event_arg and len(_event.__attrs_attrs__) > 2 and _coro.event != "event":
                        self.logger.warning(
                            f"{_coro} is listening to {_coro.event} event which contains event data. "
                            f"Add an event argument to this listener to receive the event data object."
                        )
                        _coro.warned_no_event_arg = True
                    await _coro()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                if isinstance(event, events.Error):
                    # No infinite loops please
                    self.default_error_handler(repr(event), e)
                else:
                    self.dispatch(events.Error(source=repr(event), error=e))

        try:
            asyncio.get_running_loop()
            return asyncio.create_task(_async_wrap(coro, event, *args, **kwargs), name=f"flux:: {event.resolved_name}")
        except RuntimeError:
            self.logger.debug("Event loop is closed; queuing task for execution on startup")
            self.async_startup_tasks.append((_async_wrap, (coro, event, *args), kwargs))

    @staticmethod
    def default_error_handler(source: str, error: BaseException) -> None:
        """
        The default error logging behaviour.

        Args:
            source: The source of this error
            error: The exception itself

        """
        out = traceback.format_exception(error)

        if isinstance(error, HTTPException):
            # HTTPException's are of 3 known formats, we can parse them for human readable errors
            with contextlib.suppress(Exception):
                out = [str(error)]
        get_logger().error(
            "Ignoring exception in {}:{}{}".format(source, "\n" if len(out) > 1 else " ", "".join(out)),
        )

    @Listener.create(is_default_listener=True)
    async def on_error(self, event: events.Error) -> None:
        """
        Catches all errors dispatched by the library.

        By default it will format and print them to console.

        Listen to the `Error` event to overwrite this behaviour.

        """
        self.default_error_handler(event.source, event.error)

    @Listener.create()
    async def on_resume(self) -> None:
        self._ready.set()

    @Listener.create(is_default_listener=True)
    async def _on_websocket_ready(self, event: events.RawGatewayEvent) -> None:
        """
        Catches websocket ready and determines when to dispatch the client `READY` signal.

        Args:
            event: The websocket ready packet

        """
        data = event.data
        expected_guilds = {to_snowflake(guild["id"]) for guild in data["guilds"]}
        self._user._add_guilds(expected_guilds)

        if not self._startup:
            while len(self.guilds) != len(expected_guilds):
                try:  # wait to let guilds cache
                    await asyncio.wait_for(self._guild_event.wait(), self.guild_event_timeout)
                except asyncio.TimeoutError:
                    # this will *mostly* occur when a guild has been shadow deleted by discord T&S.
                    # there is no way to check for this, so we just need to wait for this to time out.
                    # We still log it though, just in case.
                    self.logger.debug("Timeout waiting for guilds cache")
                    break
                self._guild_event.clear()

            if self.fetch_members:
                # ensure all guilds have completed chunking
                for guild in self.guilds:
                    if guild and not guild.chunked.is_set():
                        self.logger.debug(f"Waiting for {guild.id} to chunk")
                        await guild.chunked.wait()

            self._startup = True
            self.dispatch(events.Startup())

        else:
            # reconnect ready
            ready_guilds = set()

            async def _temp_listener(_event: events.RawGatewayEvent) -> None:
                ready_guilds.add(_event.data["id"])

            listener = Listener.create("_on_raw_guild_create")(_temp_listener)
            self.add_listener(listener)

            while len(ready_guilds) != len(expected_guilds):
                try:
                    await asyncio.wait_for(self._guild_event.wait(), self.guild_event_timeout)
                except asyncio.TimeoutError:
                    break
                self._guild_event.clear()

            self.listeners["raw_guild_create"].remove(listener)

        self._ready.set()
        self.dispatch(events.Ready())

    async def login(self, token: str | None = None) -> None:
        """
        Login to discord via http.

        !!! note
            You will need to run Client.start_gateway() before you start receiving gateway events.

        Args:
            token str: Your bot's token

        """
        if not self.token and not token:
            raise RuntimeError(
                "No token provided - please provide a token in the client constructor or via the login method."
            )
        self.token = (token or self.token).strip()

        # i needed somewhere to put this call,
        # login will always run after initialisation
        # so im gathering commands here
        self._gather_callbacks()

        if any(v for v in constants.CLIENT_FEATURE_FLAGS.values()):
            # list all enabled flags
            enabled_flags = [k for k, v in constants.CLIENT_FEATURE_FLAGS.items() if v]
            self.logger.info(f"Enabled feature flags: {', '.join(enabled_flags)}")

        self.logger.debug("Attempting to login")
        me = await self.http.login(self.token)
        self._user = ClientUser.from_dict(me, self)
        self.cache.place_user_data(me)
        # self._app = Application.from_dict(await self.http.get_current_bot_information(), self)
        self._mention_reg = re.compile(rf"^(<@!?{self.user.id}*>\s)")

        if self.app.owner:
            self.owner_ids.add(self.app.owner.id)

        self.dispatch(events.Login())

    async def astart(self, token: str | None = None) -> None:
        """
        Asynchronous method to start the bot.

        Args:
            token: Your bot's token

        """
        await self.login(token)

        # run any pending startup tasks
        if self.async_startup_tasks:
            try:
                await asyncio.gather(
                    *[
                        task[0](*task[1] if len(task) > 1 else [], **task[2] if len(task) == 3 else {})
                        for task in self.async_startup_tasks
                    ]
                )
            except Exception as e:
                self.dispatch(events.Error(source="async-extension-loader", error=e))
        try:
            await self._connection_state.start()
        finally:
            await self.stop()

    def start(self, token: str | None = None) -> None:
        """
        Start the bot.

        If `uvloop` is installed, it will be used.

        info:
            This is the recommended method to start the bot
        """
        try:
            import uvloop

            has_uvloop = True
        except ImportError:
            has_uvloop = False

        with contextlib.suppress(KeyboardInterrupt):
            if has_uvloop:
                self.logger.info("uvloop is installed, using it")
                if sys.version_info >= (3, 11):
                    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
                        runner.run(self.astart(token))
                else:
                    uvloop.install()
                    asyncio.run(self.astart(token))
            else:
                asyncio.run(self.astart(token))

    async def start_gateway(self) -> None:
        """Starts the gateway connection."""
        try:
            await self._connection_state.start()
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Shutdown the bot."""
        self.logger.debug("Stopping the bot.")
        self._ready.clear()
        await self.http.close()
        await self._connection_state.stop()

    async def _process_waits(self, event: events.BaseEvent) -> None:
        if _waits := self.waits.get(event.resolved_name, []):
            index_to_remove = []
            for i, _wait in enumerate(_waits):
                result = await _wait(event)
                if result:
                    index_to_remove.append(i)

            for idx in sorted(index_to_remove, reverse=True):
                _waits.pop(idx)

    def dispatch(self, event: events.BaseEvent, *args, **kwargs) -> None:
        """
        Dispatch an event.

        Args:
            event: The event to be dispatched.

        """
        if listeners := self.listeners.get(event.resolved_name, []):
            self.logger.debug(f"Dispatching Event: {event.resolved_name}")
            event.bot = self
            for _listen in listeners:
                try:
                    self._queue_task(_listen, event, *args, **kwargs)
                except Exception as e:
                    raise BotException(
                        f"An error occurred attempting during {event.resolved_name} event processing"
                    ) from e

        try:
            asyncio.get_running_loop()
            _ = asyncio.create_task(self._process_waits(event))  # noqa: RUF006
        except RuntimeError:
            # dispatch attempt before event loop is running
            self.async_startup_tasks.append((self._process_waits, (event,), {}))

        if "event" in self.listeners:
            # special meta event listener
            for _listen in self.listeners["event"]:
                self._queue_task(_listen, event, *args, **kwargs)

    async def wait_until_ready(self) -> None:
        """Waits for the client to become ready."""
        await self._ready.wait()

    @overload
    def wait_for(
        self,
        event: type[EventT],
        checks: Absent[Callable[[EventT], bool] | Callable[[EventT], Awaitable[bool]]] = MISSING,
        timeout: Optional[float] = None,
    ) -> "Awaitable[EventT]": ...

    @overload
    def wait_for(
        self,
        event: str,
        checks: Callable[[EventT], bool] | Callable[[EventT], Awaitable[bool]],
        timeout: Optional[float] = None,
    ) -> "Awaitable[EventT]": ...

    @overload
    def wait_for(
        self,
        event: str,
        checks: Missing = MISSING,
        timeout: Optional[float] = None,
    ) -> Awaitable[Any]: ...

    def wait_for(
        self,
        event: Union[str, "type[BaseEvent]"],
        checks: Absent[Callable[[BaseEvent], bool] | Callable[[BaseEvent], Awaitable[bool]]] = MISSING,
        timeout: Optional[float] = None,
    ) -> Awaitable[Any]:
        """
        Waits for a WebSocket event to be dispatched.

        Args:
            event: The name of event to wait.
            checks: A predicate to check what to wait for.
            timeout: The number of seconds to wait before timing out.

        Returns:
            The event object.

        """
        event = get_event_name(event)

        if event not in self.waits:
            self.waits[event] = []

        future = asyncio.Future()
        self.waits[event].append(Wait(event, checks, future))

        return asyncio.wait_for(future, timeout)

    def listen(self, event_name: Absent[str] = MISSING) -> Callable[[AsyncCallable], Listener]:
        """
        A decorator to be used in situations that the library can't automatically hook your listeners. Ideally, the standard listen decorator should be used, not this.

        Args:
            event_name: The event name to use, if not the coroutine name

        Returns:
            A listener that can be used to hook into the event.

        """

        def wrapper(coro: AsyncCallable) -> Listener:
            listener = Listener.create(event_name)(coro)
            self.add_listener(listener)
            return listener

        return wrapper

    event = listen  # alias for easier migration

    def add_event_processor(self, event_name: Absent[str] = MISSING) -> Callable[[AsyncCallable], AsyncCallable]:
        """
        A decorator to be used to add event processors.

        Args:
            event_name: The event name to use, if not the coroutine name

        Returns:
            A function that can be used to hook into the event.

        """

        def wrapper(coro: AsyncCallable) -> AsyncCallable:
            name = event_name
            if name is MISSING:
                name = coro.__name__
            name = name.lstrip("_")
            name = name.removeprefix("on_")
            self.processors[name] = coro
            return coro

        return wrapper

    def add_listener(self, listener: Listener) -> None:
        """
        Add a listener for an event, if no event is passed, one is determined.

        Args:
            listener Listener: The listener to add to the client

        """
        if listener.event == "event":
            self.logger.critical(
                f"Subscribing to `{listener.event}` - Meta Events are very expensive; remember to remove it before"
                " releasing your bot"
            )

        if not listener.is_default_listener:
            # check that the required intents are enabled

            event_class_name = "".join([name.capitalize() for name in listener.event.split("_")])
            if event_class := globals().get(event_class_name):
                if required_intents := _INTENT_EVENTS.get(event_class):
                    if all(required_intent not in self.intents for required_intent in required_intents):
                        self.logger.warning(
                            f"Event `{listener.event}` will not work since the required intent is not set -> Requires"
                            f" any of: `{required_intents}`"
                        )

        # prevent the same callback being added twice
        if listener in self.listeners.get(listener.event, []):
            self.logger.debug(f"Listener {listener} has already been hooked, not re-hooking it again")
            return

        listener.lazy_parse_params()

        if listener.event not in self.listeners:
            self.listeners[listener.event] = []
        self.listeners[listener.event].append(listener)

        # check if other listeners are to be deleted
        default_listeners = [c_listener.is_default_listener for c_listener in self.listeners[listener.event]]
        removes_defaults = [c_listener.disable_default_listeners for c_listener in self.listeners[listener.event]]

        if any(default_listeners) and any(removes_defaults):
            self.listeners[listener.event] = [
                c_listener for c_listener in self.listeners[listener.event] if not c_listener.is_default_listener
            ]

    def add_command(self, func: Callable) -> None:
        """
        Add a command to the client.

        Args:
            func: The command to add

        """
        if isinstance(func, Listener):
            self.add_listener(func)

        for hook in self._add_command_hook:
            hook(func)

        if not func.callback:
            # for group = SlashCommand(...) usage
            return

        if isinstance(func.callback, functools.partial):
            ext = getattr(func, "extension", None)
            self.logger.debug(f"Added callback: {f'{ext.name}.' if ext else ''}{func.callback.func.__name__}")
        else:
            self.logger.debug(f"Added callback: {func.callback.__name__}")

        self.dispatch(CallbackAdded(callback=func, extension=func.extension if hasattr(func, "extension") else None))

    def _gather_callbacks(self) -> None:
        """Gathers callbacks from __main__ and self."""

        def process(callables, location: str) -> None:
            added = 0
            for func in callables:
                try:
                    self.add_command(func)
                    added += 1
                except TypeError:
                    self.logger.debug(f"Failed to add callback {func} from {location}")
                    continue

            self.logger.debug(f"{added} callbacks have been loaded from {location}.")

        main_commands = [
            obj for _, obj in inspect.getmembers(sys.modules["__main__"]) if isinstance(obj, CallbackObject)
        ]
        client_commands = [
            obj.copy_with_binding(self) for _, obj in inspect.getmembers(self) if isinstance(obj, CallbackObject)
        ]
        process(main_commands, "__main__")
        process(client_commands, self.__class__.__name__)

        [wrap_partial(obj, self) for _, obj in inspect.getmembers(self) if isinstance(obj, Task)]

    async def _disconnect(self) -> None:
        self._ready.clear()

    def get_extensions(self, name: str) -> list[Extension]:
        """
        Get all ext with a name or extension name.

        Args:
            name: The name of the extension, or the name of it's extension

        Returns:
            List of Extensions

        """
        if name not in self.ext.keys():
            return [ext for ext in self.ext.values() if ext.extension_name == name]

        return [self.ext.get(name, None)]

    def get_ext(self, name: str) -> Extension | None:
        """
        Get a extension with a name or extension name.

        Args:
            name: The name of the extension, or the name of it's extension

        Returns:
            A extension, if found

        """
        return ext[0] if (ext := self.get_extensions(name)) else None

    def __load_module(self, module, module_name, **load_kwargs) -> None:
        """Internal method that handles loading a module."""
        try:
            if setup := getattr(module, "setup", None):
                setup(self, **load_kwargs)
            else:
                self.logger.debug("No setup function found in %s", module_name)

                found = False
                objects = {name: obj for name, obj in inspect.getmembers(module) if isinstance(obj, type)}
                for obj_name, obj in objects.items():
                    if Extension in obj.__bases__:
                        self.logger.debug(f"Found extension class {obj_name} in {module_name}: Attempting to load")
                        obj(self, **load_kwargs)
                        found = True
                if not found:
                    raise ValueError(f"{module_name} contains no Extensions")

        except ExtensionLoadException:
            raise
        except Exception as e:
            sys.modules.pop(module_name, None)
            raise ExtensionLoadException(f"Unexpected Error loading {module_name}") from e

        else:
            self.logger.debug(f"Loaded Extension: {module_name}")
            self.__modules[module_name] = module

    def load_extension(
        self,
        name: str,
        package: str | None = None,
        **load_kwargs: Any,
    ) -> None:
        """
        Load an extension with given arguments.

        Args:
            name: The name of the extension.
            package: The package the extension is in
            **load_kwargs: The auto-filled mapping of the load keyword arguments

        """
        module_name = importlib.util.resolve_name(name, package)
        if module_name in self.__modules:
            raise Exception(f"{module_name} already loaded")

        module = importlib.import_module(module_name, package)
        self.__load_module(module, module_name, **load_kwargs)

    def load_extensions(
        self,
        *packages: str,
        recursive: bool = False,
        **load_kwargs: Any,
    ) -> None:
        """
        Load multiple extensions at once.

        Removes the need of manually looping through the package
        and loading the extensions.

        Args:
            *packages: The package(s) where the extensions are located.
            recursive: Whether to load extensions from the subdirectories within the package.

        """
        if not packages:
            raise ValueError("You must specify at least one package.")

        for package in packages:
            # If recursive then include subdirectories ('**')
            # otherwise just the package specified by the user.
            pattern = os.path.join(package, "**" if recursive else "", "*.py")

            # Find all files matching the pattern, and convert slashes to dots.
            extensions = [f.replace(os.path.sep, ".").replace(".py", "") for f in glob.glob(pattern, recursive=True)]

            for ext in extensions:
                self.load_extension(ext, **load_kwargs)

    def unload_extension(
        self, name: str, package: str | None = None, force: bool = False, **unload_kwargs: Any
    ) -> None:
        """
        Unload an extension with given arguments.

        Args:
            name: The name of the extension.
            package: The package the extension is in
            force: Whether to force unload the extension - for use in reversions
            **unload_kwargs: The auto-filled mapping of the unload keyword arguments

        """
        name = importlib.util.resolve_name(name, package)
        module = self.__modules.get(name)

        if module is None and not force:
            raise ExtensionNotFound(f"No extension called {name} is loaded")

        with contextlib.suppress(AttributeError):
            teardown = module.teardown
            teardown(**unload_kwargs)

        for ext in self.get_extensions(name):
            ext.drop(**unload_kwargs)

        sys.modules.pop(name, None)
        self.__modules.pop(name, None)

    def reload_extension(
        self,
        name: str,
        package: str | None = None,
        *,
        load_kwargs: Any = None,
        unload_kwargs: Any = None,
    ) -> None:
        """
        Helper method to reload an extension. Simply unloads, then loads the extension with given arguments.

        Args:
            name: The name of the extension.
            package: The package the extension is in
            load_kwargs: The manually-filled mapping of the load keyword arguments
            unload_kwargs: The manually-filled mapping of the unload keyword arguments

        """
        name = importlib.util.resolve_name(name, package)
        module = self.__modules.get(name)

        if module is None:
            self.logger.warning("Attempted to reload extension thats not loaded. Loading extension instead")
            return self.load_extension(name, package)

        backup = module

        try:
            if not load_kwargs:
                load_kwargs = {}
            if not unload_kwargs:
                unload_kwargs = {}

            self.unload_extension(name, package, **unload_kwargs)
            self.load_extension(name, package, **load_kwargs)
        except Exception as e:
            try:
                self.logger.error(f"Error reloading extension {name}: {e} - attempting to revert to previous state")
                try:
                    self.unload_extension(name, package, force=True, **unload_kwargs)  # make sure no remnants are left
                except Exception as t:
                    self.logger.debug(f"Suppressing error unloading extension {name} during reload revert: {t}")

                sys.modules[name] = backup
                self.__load_module(backup, name, **load_kwargs)
                self.logger.info(f"Reverted extension {name} to previous state ", exc_info=e)
            except Exception as ex:
                sys.modules.pop(name, None)
                raise ex from e

    async def fetch_guild(self, guild_id: "Snowflake_Type", *, force: bool = False) -> Optional[Guild]:
        """
        Fetch a guild.

        !!! note
            This method is an alias for the cache which will either return a cached object, or query discord for the object
            if its not already cached.

        Args:
            guild_id: The ID of the guild to get
            force: Whether to poll the API regardless of cache

        Returns:
            Guild Object if found, otherwise None

        """
        try:
            return await self.cache.fetch_guild(guild_id, force=force)
        except NotFound:
            return None

    def get_guild(self, guild_id: "Snowflake_Type") -> Optional[Guild]:
        """
        Get a guild.

        !!! note
            This method is an alias for the cache which will return a cached object.

        Args:
            guild_id: The ID of the guild to get

        Returns:
            Guild Object if found, otherwise None

        """
        return self.cache.get_guild(guild_id)

    async def create_guild_from_template(
        self,
        template_code: Union["GuildTemplate", str],
        name: str,
        icon: Absent[UPLOADABLE_TYPE] = MISSING,
    ) -> Optional[Guild]:
        """
        Creates a new guild based on a template.

        !!! note
            This endpoint can only be used by bots in less than 10 guilds.

        Args:
            template_code: The code of the template to use.
            name: The name of the guild (2-100 characters)
            icon: Location or File of icon to set

        Returns:
            The newly created guild object

        """
        if isinstance(template_code, GuildTemplate):
            template_code = template_code.code

        if icon:
            icon = to_image_data(icon)
        guild_data = await self.http.create_guild_from_guild_template(template_code, name, icon)
        return Guild.from_dict(guild_data, self)

    async def fetch_channel(self, channel_id: "Snowflake_Type", *, force: bool = False) -> Optional["TYPE_ALL_CHANNEL"]:
        """
        Fetch a channel.

        !!! note
            This method is an alias for the cache which will either return a cached object, or query discord for the object
            if its not already cached.

        Args:
            channel_id: The ID of the channel to get
            force: Whether to poll the API regardless of cache

        Returns:
            Channel Object if found, otherwise None

        """
        try:
            return await self.cache.fetch_channel(channel_id, force=force)
        except NotFound:
            return None

    def get_channel(self, channel_id: "Snowflake_Type") -> Optional["TYPE_ALL_CHANNEL"]:
        """
        Get a channel.

        !!! note
            This method is an alias for the cache which will return a cached object.

        Args:
            channel_id: The ID of the channel to get

        Returns:
            Channel Object if found, otherwise None

        """
        return self.cache.get_channel(channel_id)

    async def fetch_user(self, user_id: "Snowflake_Type", *, force: bool = False) -> Optional[User]:
        """
        Fetch a user.

        !!! note
            This method is an alias for the cache which will either return a cached object, or query discord for the object
            if its not already cached.

        Args:
            user_id: The ID of the user to get
            force: Whether to poll the API regardless of cache

        Returns:
            User Object if found, otherwise None

        """
        try:
            return await self.cache.fetch_user(user_id, force=force)
        except NotFound:
            return None

    def get_user(self, user_id: "Snowflake_Type") -> Optional[User]:
        """
        Get a user.

        !!! note
            This method is an alias for the cache which will return a cached object.

        Args:
            user_id: The ID of the user to get

        Returns:
            User Object if found, otherwise None

        """
        return self.cache.get_user(user_id)

    async def fetch_member(
        self, user_id: "Snowflake_Type", guild_id: "Snowflake_Type", *, force: bool = False
    ) -> Optional[Member]:
        """
        Fetch a member from a guild.

        !!! note
            This method is an alias for the cache which will either return a cached object, or query discord for the object
            if its not already cached.

        Args:
            user_id: The ID of the member
            guild_id: The ID of the guild to get the member from
            force: Whether to poll the API regardless of cache

        Returns:
            Member object if found, otherwise None

        """
        try:
            return await self.cache.fetch_member(guild_id, user_id, force=force)
        except NotFound:
            return None

    def get_member(self, user_id: "Snowflake_Type", guild_id: "Snowflake_Type") -> Optional[Member]:
        """
        Get a member from a guild.

        !!! note
            This method is an alias for the cache which will return a cached object.

        Args:
            user_id: The ID of the member
            guild_id: The ID of the guild to get the member from

        Returns:
            Member object if found, otherwise None

        """
        return self.cache.get_member(guild_id, user_id)

    async def fetch_scheduled_event(
        self,
        guild_id: "Snowflake_Type",
        scheduled_event_id: "Snowflake_Type",
        with_user_count: bool = False,
    ) -> Optional["ScheduledEvent"]:
        """
        Fetch a scheduled event by id.

        Args:
            guild_id: The ID of the guild to get the scheduled event from
            scheduled_event_id: The ID of the scheduled event to get
            with_user_count: Whether to include the user count in the response

        Returns:
            The scheduled event if found, otherwise None

        """
        try:
            scheduled_event_data = await self.http.get_scheduled_event(guild_id, scheduled_event_id, with_user_count)
            return self.cache.place_scheduled_event_data(scheduled_event_data)
        except NotFound:
            return None

    def get_scheduled_event(
        self,
        scheduled_event_id: "Snowflake_Type",
    ) -> Optional["ScheduledEvent"]:
        """
        Get a scheduled event by id.

        !!! note
            This method is an alias for the cache which will return a cached object.

        Args:
            scheduled_event_id: The ID of the scheduled event to get

        Returns:
            The scheduled event if found, otherwise None

        """
        return self.cache.get_scheduled_event(scheduled_event_id)

    async def fetch_custom_emoji(
        self, emoji_id: "Snowflake_Type", guild_id: "Snowflake_Type", *, force: bool = False
    ) -> Optional[CustomEmoji]:
        """
        Fetch a custom emoji by id.

        Args:
            emoji_id: The id of the custom emoji.
            guild_id: The id of the guild the emoji belongs to.
            force: Whether to poll the API regardless of cache.

        Returns:
            The custom emoji if found, otherwise None.

        """
        try:
            return await self.cache.fetch_emoji(guild_id, emoji_id, force=force)
        except NotFound:
            return None

    def get_custom_emoji(
        self, emoji_id: "Snowflake_Type", guild_id: Optional["Snowflake_Type"] = None
    ) -> Optional[CustomEmoji]:
        """
        Get a custom emoji by id.

        Args:
            emoji_id: The id of the custom emoji.
            guild_id: The id of the guild the emoji belongs to.

        Returns:
            The custom emoji if found, otherwise None.

        """
        emoji = self.cache.get_emoji(emoji_id)
        if emoji and (not guild_id or emoji._guild_id == to_snowflake(guild_id)):
            return emoji
        return None

    async def fetch_sticker(self, sticker_id: "Snowflake_Type") -> Optional[Sticker]:
        """
        Fetch a sticker by ID.

        Args:
            sticker_id: The ID of the sticker.

        Returns:
            A sticker object if found, otherwise None

        """
        try:
            sticker_data = await self.http.get_sticker(sticker_id)
            return Sticker.from_dict(sticker_data, self)
        except NotFound:
            return None

    async def fetch_nitro_packs(self) -> Optional[List["StickerPack"]]:
        """
        List the sticker packs available to Nitro subscribers.

        Returns:
            A list of StickerPack objects if found, otherwise returns None

        """
        try:
            packs_data = await self.http.list_nitro_sticker_packs()
            return [StickerPack.from_dict(data, self) for data in packs_data]

        except NotFound:
            return None

    async def fetch_voice_regions(self) -> List["VoiceRegion"]:
        """
        List the voice regions available on Discord.

        Returns:
            A list of voice regions.

        """
        regions_data = await self.http.list_voice_regions()
        return VoiceRegion.from_list(regions_data)

    async def connect_to_vc(
        self,
        guild_id: "Snowflake_Type",
        channel_id: "Snowflake_Type",
        muted: bool = False,
        deafened: bool = False,
    ) -> ActiveVoiceState:
        """
        Connect the bot to a voice channel.

        Args:
            guild_id: id of the guild the voice channel is in.
            channel_id: id of the voice channel client wants to join.
            muted: Whether the bot should be muted when connected.
            deafened: Whether the bot should be deafened when connected.

        Returns:
            The new active voice state on successfully connection.

        """
        return await self._connection_state.voice_connect(guild_id, channel_id, muted, deafened)

    def get_bot_voice_state(self, guild_id: "Snowflake_Type") -> Optional[ActiveVoiceState]:
        """
        Get the bot's voice state for a guild.

        Args:
            guild_id: The target guild's id.

        Returns:
            The bot's voice state for the guild if connected, otherwise None.

        """
        return self._connection_state.get_voice_state(guild_id)

    async def fetch_entitlements(
        self,
        *,
        user_id: "Optional[Snowflake_Type]" = None,
        sku_ids: "Optional[list[Snowflake_Type]]" = None,
        before: "Optional[Snowflake_Type]" = None,
        after: "Optional[Snowflake_Type]" = None,
        limit: Optional[int] = 100,
        guild_id: "Optional[Snowflake_Type]" = None,
        exclude_ended: Optional[bool] = None,
    ) -> List[Entitlement]:
        """
        Fetch the entitlements for the bot's application.

        Args:
            user_id: The ID of the user to filter entitlements by.
            sku_ids: The IDs of the SKUs to filter entitlements by.
            before: Get entitlements before this ID.
            after: Get entitlements after this ID.
            limit: The maximum number of entitlements to return. Maximum is 100.
            guild_id: The ID of the guild to filter entitlements by.
            exclude_ended: Whether to exclude ended entitlements.

        Returns:
            A list of entitlements.

        """
        entitlements_data = await self.http.get_entitlements(
            self.app.id,
            user_id=user_id,
            sku_ids=sku_ids,
            before=before,
            after=after,
            limit=limit,
            guild_id=guild_id,
            exclude_ended=exclude_ended,
        )
        return Entitlement.from_list(entitlements_data, self)

    async def create_test_entitlement(
        self, sku_id: "Snowflake_Type", owner_id: "Snowflake_Type", owner_type: int
    ) -> Entitlement:
        """
        Create a test entitlement for the bot's application.

        Args:
            sku_id: The ID of the SKU to create the entitlement for.
            owner_id: The ID of the owner of the entitlement.
            owner_type: The type of the owner of the entitlement. 1 for a guild subscription, 2 for a user subscription

        Returns:
            The created entitlement.

        """
        payload = {"sku_id": to_snowflake(sku_id), "owner_id": to_snowflake(owner_id), "owner_type": owner_type}

        entitlement_data = await self.http.create_test_entitlement(payload, self.app.id)
        return Entitlement.from_dict(entitlement_data, self)

    async def delete_test_entitlement(self, entitlement_id: "Snowflake_Type") -> None:
        """
        Delete a test entitlement for the bot's application.

        Args:
            entitlement_id: The ID of the entitlement to delete.

        """
        await self.http.delete_test_entitlement(self.app.id, to_snowflake(entitlement_id))

    async def consume_entitlement(self, entitlement_id: "Snowflake_Type") -> None:
        """
        For One-Time Purchase consumable SKUs, marks a given entitlement for the user as consumed.

        Args:
            entitlement_id: The ID of the entitlement to consume.

        """
        await self.http.consume_entitlement(self.app.id, entitlement_id)

    async def change_presence(
        self,
        status: Optional[Union[str, Status]] = Status.ONLINE,
        activity: Optional[Union[Activity, str]] = None,
    ) -> None:
        """
        Change the bots presence.

        Args:
            status: The status for the bot to be. i.e. online, afk, etc.
            activity: The activity for the bot to be displayed as doing.

        !!! note
            Bots may only be `playing` `streaming` `listening` `watching`  `competing` or `custom`

        """
        await self._connection_state.change_presence(status, activity)
