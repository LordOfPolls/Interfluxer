import logging
import os
import time

from flux import Client, Intents, listen, prefixed_command, PrefixedContext

logging.basicConfig()
logging.getLogger("flux").setLevel(logging.DEBUG)

bot = Client(
    default_prefix="!",
    intents=Intents.DEFAULT | Intents.MESSAGE_CONTENT,
)


@listen()
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")


@prefixed_command()
async def ping(ctx: PrefixedContext):
    """Responds with pong and the bot's latency."""
    await ctx.reply(f"Pong! `{bot.latency * 1000:.0f}ms`")


@prefixed_command()
async def echo(ctx: PrefixedContext, *, message: str):
    """Repeats back whatever you say."""
    await ctx.reply(message)


@prefixed_command()
async def say(ctx: PrefixedContext, channel_id: int, *, message: str):
    """Sends a message to a specified channel."""
    channel = await bot.fetch_channel(channel_id)
    if channel:
        await channel.send(message)
        await ctx.reply(f"Message sent to <#{channel_id}>")
    else:
        await ctx.reply("Channel not found.")


@prefixed_command(name="info")
async def info_cmd(ctx: PrefixedContext):
    """Shows basic bot info."""
    await ctx.reply(
        f"**Bot:** {bot.user.username}\n"
        f"**Guilds:** {bot.guild_count}\n"
        f"**Latency:** {bot.latency * 1000:.0f}ms\n"
        f"**Prefix:** `!`"
    )


while True:
    backoff = 1

    try:
        bot.start(os.environ["TOKEN"])
    except KeyboardInterrupt:
        break
    except Exception as e:
        print(e)
        backoff *= 2
        if backoff > 30:
            break
        time.sleep(backoff)
