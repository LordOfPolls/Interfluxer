---
search:
  boost: 3
---

# Creating Commands

Prefixed commands are commands that are triggered when a user sends a normal message with a designated "prefix" in front of them (e.g. `!ping`).

Interfluxer has an extensive and familiar prefixed command architecture built directly into the core library.

## Setup

To use prefixed commands, you need to ensure your bot has the `MESSAGE_CONTENT` intent enabled. You can also specify a `default_prefix` when initializing the `Client`.

```python
from Interfluxer import Client, Intents

# MESSAGE_CONTENT is required to see message text for prefixed commands
client = Client(
    default_prefix="!",
    intents=Intents.DEFAULT | Intents.MESSAGE_CONTENT
)
```

By default, the bot will also respond to being mentioned as a prefix (e.g. `@bot hello`).

## Your First Command

To create a prefixed command, simply define an asynchronous function and use the `@prefixed_command()` decorator above it.

```python
from Interfluxer import prefixed_command, PrefixedContext


@prefixed_command(name="ping")
async def ping_command(ctx: PrefixedContext):
    await ctx.reply("Pong!")
```

???+ note "Command Name"
    If `name` is not specified, Interfluxer will automatically use the function's name as the command's name.

## Subcommands

Subcommands allow you to group related commands together:

```python
@prefixed_command()
async def base(ctx: PrefixedContext):
    await ctx.reply("This is the base command.")

@base.subcommand()
async def sub(ctx: PrefixedContext):
    await ctx.reply("This is a subcommand.")
```

A user would invoke the subcommand by typing `!base sub`.

## Parameters

You can easily parse arguments from the user's message by adding parameters to your function.

```python
@prefixed_command()
async def echo(ctx: PrefixedContext, message: str):
    await ctx.reply(f"You said: {message}")
```

If the user types `!echo hello`, the `message` parameter will be `"hello"`.
If the user wants to pass multiple words as a single argument, they can wrap them in quotes: `!echo "hello world"`.

### Variable and Consume Rest Arguments

#### Variable Arguments

If you want to receive an undetermined amount of arguments as a tuple, use `*args`:

```python
@prefixed_command()
async def multi(ctx: PrefixedContext, *args: str):
    await ctx.reply(f"Received {len(args)} arguments: {', '.join(args)}")
```

#### Consume Rest

If you want to take the remainder of the message as a single argument (without needing quotes), use a keyword-only argument:

```python
@prefixed_command()
async def say(ctx: PrefixedContext, *, message: str):
    await ctx.reply(message)
```

## Typehinting and Converters

Interfluxer will automatically attempt to convert arguments to the type specified in your typehints.

```python
@prefixed_command()
async def add(ctx: PrefixedContext, a: int, b: int):
    await ctx.reply(f"Result: {a + b}")
```

### Fluxer Converters

You can typehint Fluxer models like `Member`, `Role`, or `GuildText`. Interfluxer will attempt to resolve these from the user's input (handles mentions, IDs, and names).

```python
from Interfluxer import Member

@prefixed_command()
async def poke(ctx: PrefixedContext, target: Member):
    await ctx.reply(f"{target.mention}, you got poked by {ctx.author.mention}!")
```

For more complex conversions, see the [Converters Guide](08 Converters.md).

## Help Command

Interfluxer provides a `PrefixedHelpCommand` to easily add a help command to your bot:

```python
from Interfluxer import PrefixedHelpCommand

help_cmd = PrefixedHelpCommand(client)
help_cmd.register()
```

## Other Notes
- **Checks and Cooldowns:** Standard checks and cooldowns work seamlessly with prefixed commands.
- **Error Handling:** You can use the `@command.error` decorator to handle errors specific to a command.
