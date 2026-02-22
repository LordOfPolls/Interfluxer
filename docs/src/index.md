---
hide:
  - navigation
  - toc
  - feedback
search:
  exclude: true
---

We hope this documentation is helpful for you, but don't just ++ctrl+c++ and ++ctrl+v++.

A highly extensible, easy to use, and feature complete framework for Fluxer.

Interfluxer is the culmination of years of experience with bot development. This framework has been built from the ground up with community feedback and suggestions in mind. Our framework provides a modern and intuitive set of language bindings for easy interaction with Fluxer.

## Key Features
Interfluxer offers a wide range of features for building Python-powered Fluxer bots and web applications alike:

- ✅ Dynamic cache with TTL support

- ✅ Modern and Pythonic API for easy interaction with Fluxer

- ✅ Proper rate-limit handling

- ✅ Feature parity with most other Fluxer API wrappers

In addition to core functionality, Interfluxer provides a range of optional extensions, allowing you to further customize your bot and add new features with ease.

## Extensibility

So the base library doesn't do what you want? No problem! With builtin extensions, you are able to extend the functionality of the library. And if none of those pique your interest, there are a myriad of other extension libraries available.

Just type `bot.load_extension("extension")`

---

### Debug Ext

A fully featured debug and utilities suite to help you get your bots made

### Jurigged

A hot reloading extension allowing you to automagically update your bot without reboots

### Sentry

Integrates Sentry.io error tracking into your bot with a single line

---

## Where do I start?

Getting started with Interfluxer is easy! Simply install it via `pip` and start building your Fluxer application in Python:

`pip install Interfluxer`

```python
from Interfluxer import Client, Intents, listen, prefixed_command, PrefixedContext

bot = Client(
    default_prefix="!",
    intents=Intents.DEFAULT | Intents.MESSAGE_CONTENT,
)


@listen()
async def on_ready():
    print(f"Logged in as {bot.user}")


@prefixed_command()
async def ping(ctx: PrefixedContext):
    await ctx.reply("Pong!")


bot.start("token")
```
