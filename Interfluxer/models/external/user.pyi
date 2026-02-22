from .base import FluxerObject, ClientObject
from aiohttp import FormData
from datetime import datetime
from typing import type_check_only
import attrs

from Interfluxer.client import Client
from Interfluxer.client.const import Absent
from Interfluxer.client.mixins.send import SendMixin
from Interfluxer.models.external.activity import Activity
from Interfluxer.models.external.asset import Asset
from Interfluxer.models.external.channel import DM, TYPE_GUILD_CHANNEL
from Interfluxer.models.external.color import Color
from Interfluxer.models.external.enums import MemberFlags, Permissions, PremiumType, Status, UserFlags
from Interfluxer.models.external.file import UPLOADABLE_TYPE
from Interfluxer.models.external.guild import Guild
from Interfluxer.models.external.role import Role
from Interfluxer.models.external.snowflake import Snowflake_Type
from Interfluxer.models.external.timestamp import Timestamp
from Interfluxer.models.external.voice_state import VoiceState
from typing import Any, Dict, Iterable, List, Optional, Set, Union

class _SendDMMixin(SendMixin):
    id: Snowflake_Type
    async def _send_http_request(
        self, message_payload: Union[dict, "FormData"], files: Union[list["UPLOADABLE_TYPE"], None] = ...
    ) -> dict: ...

@attrs.define(eq=False, order=False, hash=False, kw_only=True)
class ConnectedAccount(ClientObject):
    id: str
    name: str
    type: str
    verified: bool
    friend_sync: bool
    show_activity: bool
    two_way_link: bool
    visibility: int

# note: what we're trying to achieve here is making isinstance checks as accurate as possible when typehinting
# Member, while "having" the attributes of User (because of __getattr__), is not actually a subclass of either
# BaseUser or User - it's its own seperate class
# we still want to typehint Member with all of the User attributes though, so what we do is create fake
# mixins that actually don't exist, and make BaseUser and User inherit from that
# then, we can make Member inheir the fake user mixin, and now we have a Member class with User attributes
# and that understands isinstance(member, User) is false

@type_check_only
@attrs.define(eq=False, order=False, hash=False, kw_only=True)  # properly typehints added attributes by attrs
class FakeBaseUserMixin(FluxerObject, _SendDMMixin):
    username: str
    global_name: str | None
    discriminator: str
    avatar: Asset
    def __str__(self) -> str: ...
    @classmethod
    def _process_dict(cls, data: Dict[str, Any], client: Client) -> Dict[str, Any]: ...
    @property
    def tag(self) -> str: ...
    @property
    def mention(self) -> str: ...
    @property
    def display_name(self) -> str: ...
    @property
    def display_avatar(self) -> Asset: ...
    @property
    def avatar_url(self) -> str: ...
    async def fetch_dm(self, *, force: bool) -> DM: ...
    def get_dm(self) -> Optional["DM"]: ...
    @property
    def mutual_guilds(self) -> List["Guild"]: ...

@attrs.define(eq=False, order=False, hash=False, kw_only=True)
class BaseUser(FakeBaseUserMixin): ...

@type_check_only
@attrs.define(eq=False, order=False, hash=False, kw_only=True)
class FakeUserMixin(FakeBaseUserMixin):
    bot: bool
    system: bool
    public_flags: UserFlags
    premium_type: PremiumType
    banner: Optional["Asset"]
    avatar_decoration: Optional["Asset"]
    accent_color: Optional["Color"]
    banner_color: Optional["Color"]
    bio: Optional[str]
    pronouns: Optional[str]
    activities: list[Activity]
    status: Absent[Status]
    _fetched: bool
    @classmethod
    def _process_dict(cls, data: Dict[str, Any], client: Client) -> Dict[str, Any]: ...
    @property
    def member_instances(self) -> List["Member"]: ...
    async def fetch_profile(self) -> "Profile": ...

@attrs.define(eq=False, order=False, hash=False, kw_only=True)
class User(FakeUserMixin, BaseUser): ...

@attrs.define(eq=False, order=False, hash=False, kw_only=True)
class Profile(FakeUserMixin, ClientObject):
    user: User
    connected_accounts: List[ConnectedAccount]
    _user_ref: frozenset
    def __str__(self) -> str: ...

@attrs.define(eq=False, order=False, hash=False, kw_only=True)
class ClientUser(User):
    verified: bool
    mfa_enabled: bool
    email: Optional[str]
    locale: Optional[str]
    flags: UserFlags
    _guild_ids: Set["Snowflake_Type"]
    def _add_guilds(self, guild_ids: Set["Snowflake_Type"]) -> None: ...
    @property
    def guilds(self) -> List["Guild"]: ...
    @property
    def guild_count(self) -> int: ...
    async def edit(
        self,
        *,
        username: Absent[str] = ...,
        avatar: Absent[UPLOADABLE_TYPE] = ...,
        banner: Absent[UPLOADABLE_TYPE] = ...,
    ) -> None: ...

@attrs.define(eq=False, order=False, hash=False, kw_only=True)
class Member(FakeUserMixin):
    bot: bool
    nick: Optional[str]
    deaf: bool
    mute: bool
    flags: MemberFlags
    joined_at: Timestamp
    premium_since: Optional["Timestamp"]
    pending: Optional[bool]
    guild_avatar: Asset
    guild_banner: Optional[Asset]
    communication_disabled_until: Optional["Timestamp"]
    _guild_id: Snowflake_Type
    _role_ids: List["Snowflake_Type"]
    _user_ref: frozenset
    @classmethod
    def _process_dict(cls, data: Dict[str, Any], client: Client) -> Dict[str, Any]: ...
    def update_from_dict(self, data) -> None: ...
    @property
    def user(self) -> User: ...
    def __str__(self) -> str: ...
    @property
    def nickname(self) -> str: ...
    @nickname.setter
    def nickname(self, nickname: str) -> None: ...
    @property
    def guild(self) -> Guild: ...
    @property
    def roles(self) -> List["Role"]: ...
    @property
    def top_role(self) -> Role: ...
    @property
    def display_name(self) -> str: ...
    @property
    def display_avatar(self) -> Asset: ...
    @property
    def avatar_url(self) -> str: ...
    @property
    def banner(self) -> Optional[Asset]: ...
    @property
    def premium(self) -> bool: ...
    @property
    def guild_permissions(self) -> Permissions: ...
    @property
    def voice(self) -> Optional["VoiceState"]: ...
    def has_permission(self, *permissions: Permissions) -> bool: ...
    def channel_permissions(self, channel: TYPE_GUILD_CHANNEL) -> Permissions: ...
    async def edit_nickname(self, new_nickname: Absent[str] = ..., reason: Absent[str] = ...) -> None: ...
    async def add_role(self, role: Union[Snowflake_Type, Role], reason: Absent[str] = ...) -> None: ...
    async def add_roles(self, roles: Iterable[Union[Snowflake_Type, Role]], reason: Absent[str] = ...) -> None: ...
    async def remove_role(self, role: Union[Snowflake_Type, Role], reason: Absent[str] = ...) -> None: ...
    async def remove_roles(self, roles: Iterable[Union[Snowflake_Type, Role]], reason: Absent[str] = ...) -> None: ...
    def has_role(self, *roles: Union[Snowflake_Type, Role]) -> bool: ...
    def has_any_role(self, roles: List[Union[Snowflake_Type, Role]]) -> bool: ...
    async def timeout(
        self,
        communication_disabled_until: Union["Timestamp", datetime, int, float, str, None],
        reason: Absent[str] = ...,
    ) -> dict: ...
    async def move(self, channel_id: Snowflake_Type) -> None: ...
    async def disconnect(self) -> None: ...
    async def edit(
        self,
        *,
        nickname: Absent[str] = ...,
        roles: Absent[Iterable["Snowflake_Type"]] = ...,
        mute: Absent[bool] = ...,
        deaf: Absent[bool] = ...,
        channel_id: Absent["Snowflake_Type"] = ...,
        communication_disabled_until: Absent[Union["Timestamp", None]] = ...,
        flags: Absent[int] = ...,
        reason: Absent[str] = ...,
    ) -> None: ...
    async def kick(self, reason: Absent[str] = ...) -> None: ...
    async def ban(
        self, delete_message_days: Absent[int] = ..., delete_message_seconds: int = ..., reason: Absent[str] = ...
    ) -> None: ...
