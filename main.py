import logging
import os
import time

from Interfluxer import Client, Intents, listen, prefixed_command, PrefixedContext

logging.basicConfig()
logging.getLogger("Interfluxer").setLevel(logging.DEBUG)

bot = Client(
    default_prefix="!",
    intents=Intents.DEFAULT | Intents.MESSAGE_CONTENT | Intents.GUILD_MEMBERS,
)

COMMON_COLORS = {
    "red": "#FF0000",
    "green": "#00FF00",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "purple": "#800080",
    "orange": "#FFA500",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "white": "#FFFFFF",
}


@listen()
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

    guild = await bot.fetch_guild(1475048024970936470)

    existing_role_names = [role.name for role in guild.roles]
    for color_name, hex_code in COMMON_COLORS.items():
        role_name = f"Color: {color_name.capitalize()}"
        if role_name not in existing_role_names:
            print(f"Creating role {role_name} in {guild.name}")
            await guild.create_role(name=role_name, color=int(hex_code.lstrip("#"), 16))


@prefixed_command()
async def color(ctx: PrefixedContext, color_name: str | None = None):
    """Gives you a role color."""
    if not color_name or color_name.lower() not in COMMON_COLORS:
        colors_list = ", ".join(COMMON_COLORS.keys())
        await ctx.reply(f"Available colors: {colors_list}\nUse `!color <name>` to set your color.")
        return

    color_name = color_name.lower()
    role_name = f"Color: {color_name.capitalize()}"

    target_role = next((r for r in ctx.guild.roles if r.name == role_name), None)
    if not target_role:
        await ctx.reply(f"Error: Role `{role_name}` not found. Please wait for the bot to initialize it.")
        return

    if not target_role.is_assignable:
        await ctx.reply("Error: I do not have permission to assign this role. Please check my role position.")
        return

    color_role_names = [f"Color: {c.capitalize()}" for c in COMMON_COLORS.keys()]
    roles_to_remove = [r for r in ctx.author.roles if r.name in color_role_names and r.id != target_role.id]

    if roles_to_remove:
        await ctx.author.remove_roles(roles_to_remove)

    if not ctx.author.has_role(target_role):
        await ctx.author.add_role(target_role)
        await ctx.reply(f"Successfully applied the color: **{color_name}**")
    else:
        await ctx.reply(f"You already have the color: **{color_name}**")


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
