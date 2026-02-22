<div align="center">

   # flux.py
   <br>

   ![](https://img.shields.io/pypi/v/discord-py-interactions.svg?label=Version&logo=pypi)
   ![](https://img.shields.io/badge/Python-3.10+-1081c1?logo=python)
   [![](https://img.shields.io/pypi/dm/discord-py-slash-command.svg?logo=python&label=Downloads)](https://pypi.org/project/discord-py-interactions/)

   [![](https://img.shields.io/badge/Code%20Style-black-000000.svg)](https://github.com/psf/black)
   [![License](https://img.shields.io/badge/License-MIT-blue)](https://github.com/interactions-py/interactions.py/blob/stable/LICENSE)

   [![](https://img.shields.io/badge/Docs-latest-x?logo=readthedocs)](https://interactions-py.github.io/interactions.py/)
   [![](https://img.shields.io/badge/Guides-latest-x?logo=readthedocs)](https://interactions-py.github.io/interactions.py/Guides/01%20Getting%20Started)
   [![image](https://discord.com/api/guilds/789032594456576001/embed.png)](https://discord.gg/interactions)

</div>

## A Feature-rich Fluxer Bot Framework for Python

A highly extensible, easy to use, and feature complete framework for Fluxer.

This project started from the `interactions.py` codebase and was reworked to target Fluxer’s API and ecosystem, with anything Discord-specific removed.
It is the culmination of years of experience with bot development.
This framework has been built from the ground up with community feedback and suggestions in mind.
Our framework provides a modern and intuitive set of language bindings for easy interaction with Discord.

## Key Features
interactions.py offers a wide range of features for building Python-powered Discord bots and web applications alike:
- ✅ Dynamic cache with TTL support
- ✅ Modern and Pythonic API for easy interaction with Fluxer
- ✅ Proper rate-limit handling
- ✅ Feature parity with most other Fluxer API wrappers

In addition to core functionality, `interactions.py` provides a range of optional extensions, allowing you to further customize your bot and add new features with ease.

## Extensibility

So the base library doesn't do what you want? No problem! With builtin extensions, you are able to extend the functionality of the library. And if none of those pique your interest, there are a myriad of other extension libraries available.

Just type `bot.load_extension("extension")`

<details>
    <summary>Extensions</summary>

  ### Debug Extension

  A fully featured debug and utilities suite to help you get your bots made

  ### Jurigged

  A hot reloading extension allowing you to automagically update your bot without reboots

  ### Sentry

  Integrates Sentry.io error tracking into your bot with a single line

  ### Console

  Adds `aiomonitor` support with enables cli commands over a web interface

</details>

## Where do I start?

Getting started with `flux.py` is easy! Simply install it via `pip` and start building your Discord application in Python:

```python
import flux

bot = flux.Client()


@flux.listen()
async def on_startup():
    print("Bot is ready!")


bot.start("token")
```

With `interactions.py`, you can quickly and easily build complex Fluxer applications with Python.
