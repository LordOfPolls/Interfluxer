---
search:
  boost: 3
---

# Examples

## `main.py`

```python
import logging
from Interfluxer import Client, Intents, listen, prefixed_command, PrefixedContext

# define your own logger with custom logging settings
logging.basicConfig()
cls_log = logging.getLogger("MyLogger")
cls_log.setLevel(logging.DEBUG)

bot = Client(
    default_prefix="!",
    intents=Intents.DEFAULT | Intents.MESSAGE_CONTENT,
    logger=cls_log
)


@listen()
async def on_ready():
    print("Ready")
    print(f"This bot is owned by {bot.owner}")


@listen()
async def on_guild_join(event):
    print(f"guild joined : {event.guild.name}")


@prefixed_command()
async def ping(ctx: PrefixedContext):
    await ctx.reply(f"Pong! Latency: {bot.latency * 1000:.0f}ms")


bot.load_extension("my_extension")
bot.start("Token")
```

## `my_extension.py`

```python
from Interfluxer import Extension, prefixed_command, PrefixedContext


class MyExtension(Extension):
    @prefixed_command()
    async def echo(self, ctx: PrefixedContext, *, message: str):
        await ctx.reply(message)

    @echo.error
    async def echo_error(self, e, ctx):
        print(f"Echo command hit error: {e}")


def setup(bot):
    MyExtension(bot)
```
