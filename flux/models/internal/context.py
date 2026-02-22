import abc
import typing
from typing_extensions import Self

from flux.client.const import MISSING, ClientT
from flux.models.discord.snowflake import Snowflake
from flux.models.internal.command import BaseCommand

if typing.TYPE_CHECKING:
    import flux

__all__ = ("BaseContext",)


class BaseContext(typing.Generic[ClientT], metaclass=abc.ABCMeta):
    """
    Base context class for all contexts.

    Define your own context class by inheriting from this class. For compatibility with the library, you must define a `from_dict` classmethod that takes a dict and returns an instance of your context class.

    """

    command: BaseCommand
    """The command this context invokes."""

    author_id: Snowflake
    """The id of the user that invoked this context."""
    channel_id: Snowflake
    """The id of the channel this context was invoked in."""
    message_id: Snowflake
    """The id of the message that invoked this context."""
    guild_id: typing.Optional[Snowflake]
    """The id of the guild this context was invoked in, if any."""

    def __init__(self, client: ClientT) -> None:
        self.client: ClientT = client
        """The client that created this context."""

        self.author_id = MISSING
        self.channel_id = MISSING
        self.message_id = MISSING
        self.guild_id = MISSING

    @property
    def guild(self) -> typing.Optional["flux.Guild"]:
        """The guild this context was invoked in."""
        return self.client.cache.get_guild(self.guild_id)

    @property
    def user(self) -> "flux.User":
        """The user that invoked this context."""
        return self.client.cache.get_user(self.author_id)

    @property
    def member(self) -> typing.Optional["flux.Member"]:
        """The member object that invoked this context."""
        return self.client.cache.get_member(self.guild_id, self.author_id)

    @property
    def author(self) -> "flux.Member | flux.User":
        """The member or user that invoked this context."""
        return self.member or self.user

    @property
    def channel(self) -> "flux.TYPE_MESSAGEABLE_CHANNEL":
        """The channel this context was invoked in."""
        if self.guild_id:
            return self.client.cache.get_channel(self.channel_id)
        return self.client.cache.get_dm_channel(self.author_id)

    @property
    def voice_state(self) -> typing.Optional["flux.VoiceState"]:
        """The current voice state of the bot in the guild this context was invoked in, if any."""
        return self.client.cache.get_bot_voice_state(self.guild_id)

    @property
    def bot(self) -> "ClientT":
        return self.client

    @classmethod
    @abc.abstractmethod
    def from_dict(cls, client: "ClientT", payload: dict) -> Self:
        """
        Create a context instance from a dict.

        Args:
            client: The client creating this context.
            payload: The dict to create the context from.

        Returns:
            The context instance.

        """
        raise NotImplementedError
