from typing import TYPE_CHECKING

from ._template import EventMixinTemplate

if TYPE_CHECKING:
    pass

__all__ = ("IntegrationEvents",)


class IntegrationEvents(EventMixinTemplate):
    pass
