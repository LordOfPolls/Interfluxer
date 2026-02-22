import asyncio
import logging
import os
import time
import uuid

from interactions.models.internal.context import SlashContext

import interactions
from interactions import (
    Client,
    listen,
    slash_command,
    BrandColours,
    slash_option,
    File,
    global_autocomplete,
    FlatUIColours,
    MaterialColours,
    ButtonStyle,
)

logging.basicConfig()
logging.getLogger("interactions").setLevel(logging.DEBUG)

bot = Client()

@listen()
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

    channel = await bot.fetch_channel(1475048024970936473)

    await channel.send("Hello World from interactions.py")

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


