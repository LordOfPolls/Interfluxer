"""
Sets up a Sentry Logger

And then call `bot.load_extension('flux.ext.sentry', dsn=SENTRY_DSN)`
Optionally takes a filter function that will be called before sending the event to Sentry.
"""

import functools
import logging
from typing import Any, Callable, Optional

from flux.api.events.internal import Error
from flux.client.const import get_logger
from flux.models.internal.tasks.task import Task

try:
    import sentry_sdk
except ModuleNotFoundError:
    get_logger().error(
        "sentry-sdk not installed, cannot enable sentry integration.  Install with `pip install external-py-flux[sentry]`"
    )
    raise

from flux import Client, Extension, listen

__all__ = ("default_sentry_filter", "setup")


def default_sentry_filter(event: dict[str, Any], hint: dict[str, Any]) -> Optional[dict[str, Any]]:
    if "log_record" in hint:
        record: logging.LogRecord = hint["log_record"]
        if "flux" in record.name:
            #  There are some logging messages that are not worth sending to sentry.
            if ": 403" in record.message:
                return None
            if record.message.startswith("Ignoring exception in "):
                return None

    if "exc_info" in hint:
        _, exc_value, _ = hint["exc_info"]
        if isinstance(exc_value, KeyboardInterrupt):
            #  We don't need to report a ctrl+c
            return None
    return event


class SentryExtension(Extension):
    @listen()
    async def on_startup(self) -> None:
        sentry_sdk.set_context(
            "bot",
            {
                "name": str(self.bot.user),
                "intents": repr(self.bot.intents),
            },
        )
        sentry_sdk.set_tag("bot_name", str(self.bot.user))

    @listen(disable_default_listeners=False)
    async def on_error(self, event: Error) -> None:
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("source", event.source)
            if event.ctx:
                scope.set_context(
                    type(event.ctx).__name__,
                    {
                        "args": getattr(event.ctx, "args", None),
                        "kwargs": getattr(event.ctx, "kwargs", None),
                        "message": getattr(event.ctx, "message", None),
                    },
                )
                if getattr(event.ctx, "author", None):
                    scope.set_user({"id": event.ctx.author.id, "username": event.ctx.author.tag})
            sentry_sdk.capture_exception(event.error)


class HookedTask(Task):
    """We're subclassing purely for the type hinting.  The following method will be transplanted onto Task."""

    def on_error_sentry_hook(self: Task, error: Exception) -> None:
        with sentry_sdk.configure_scope() as scope:
            if isinstance(self.callback, functools.partial):
                scope.set_tag("task", self.callback.func.__name__)
            else:
                scope.set_tag("task", self.callback.__name__)

            scope.set_tag("iteration", self.iteration)
            sentry_sdk.capture_exception(error)


def setup(
    bot: Client,
    dsn: str | None = None,
    filter: Optional[Callable[[dict[str, Any], dict[str, Any]], Optional[dict[str, Any]]]] = None,
    token: str | None = None,
    **kwargs,
) -> None:
    dsn = dsn or token
    if not dsn:
        bot.logger.error("Cannot enable sentry integration, no Sentry DSN provided")
        return
    if filter is None:
        filter = default_sentry_filter
    sentry_sdk.init(dsn, before_send=filter, **kwargs)
    Task.on_error_sentry_hook = HookedTask.on_error_sentry_hook  # type: ignore
    SentryExtension(bot)
