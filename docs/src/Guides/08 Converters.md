---
search:
  boost: 3
---

# Converters

If your bot is complex enough, you might find yourself wanting to use custom models in your commands. Converters are classes that allow you to convert user input into complex objects, and can be used in prefixed commands.

This can be useful if you frequently find yourself starting commands with `thing = lookup(thing_name)`.

## Inline Converters

If you do not wish to create an entirely new class, you can simply add a `convert` function in your existing class:

```python
class DatabaseEntry():
    name: str
    description: str
    score: int

    @classmethod  # you can also use staticmethod
    async def convert(cls, ctx: BaseContext, value: str) -> DatabaseEntry:
        """This is where the magic happens"""
        return cls(hypothetical_database.lookup(ctx.guild.id, value))

# Prefixed Command:
@prefixed_command()
async def my_command_function(ctx: PrefixedContext, thing: DatabaseEntry):
    await ctx.reply(f"***{thing.name}***\n{thing.description}\nScore: {thing.score}/10")
```

As you can see, a converter can transparently convert what Fluxer sends you (a string, a user, etc) into something more complex (a pokemon card, a scoresheet, etc).

## `Converter`

You may also use the `Converter` class that `Interfluxer` has as well.

```python
from Interfluxer import Converter


class UpperConverter(Converter):
    async def convert(ctx: BaseContext, argument: str):
        return argument.upper()


# Prefixed Command:
@prefixed_command()
async def upper(ctx: PrefixedContext, to_upper: UpperConverter):
    await ctx.reply(to_upper)
```

## Fluxer Model Converters

There are `Converter`s that represent some Fluxer models that you can subclass from. These are largely useful for prefixed commands, but you may find a use for them elsewhere.

A table of objects and their respective converter is as follows:

| Fluxer Model                          | Converter                     |
|----------------------------------------|-------------------------------|
| `SnowflakeObject`                      | `SnowflakeConverter`          |
| `BaseChannel`, `TYPE_ALL_CHANNEL`      | `BaseChannelConverter`        |
| `DMChannel`, `TYPE_DM_CHANNEL`         | `DMChannelConverter`          |
| `DM`                                   | `DMConverter`                 |
| `DMGroup`                              | `DMGroupConverter`            |
| `GuildChannel`, `TYPE_GUILD_CHANNEL`   | `GuildChannelConverter`       |
| `GuildNews`                            | `GuildNewsConverter`          |
| `GuildCategory`                        | `GuildCategoryConverter`      |
| `GuildText`                            | `GuildTextConverter`          |
| `ThreadChannel`, `TYPE_THREAD_CHANNEL` | `ThreadChannelConverter`      |
| `GuildNewsThread`                      | `GuildNewsThreadConverter`    |
| `GuildPublicThread`                    | `GuildPublicThreadConverter`  |
| `GuildPrivateThread`                   | `GuildPrivateThreadConverter` |
| `VoiceChannel`, `TYPE_VOICE_CHANNEL`   | `VoiceChannelConverter`       |
| `GuildVoice`                           | `GuildVoiceConverter`         |
| `GuildStageVoice`                      | `GuildStageVoiceConverter`    |
| `TYPE_MESSAGEABLE_CHANNEL`             | `MessageableChannelConverter` |
| `User`                                 | `UserConverter`               |
| `Member`                               | `MemberConverter`             |
| `Guild`                                | `GuildConverter`              |
| `Role`                                 | `RoleConverter`               |
| `PartialEmoji`                         | `PartialEmojiConverter`       |
| `CustomEmoji`                          | `CustomEmojiConverter`        |


## `typing.Annotated`

Using `typing.Annotated` can allow you to have more proper typehints when using converters:

```python
from typing import Annotated

class UpperConverter(Converter):
    async def convert(ctx: BaseContext, argument: str):
        return argument.upper()

# Prefixed Command:
@prefixed_command()
async def upper(ctx: PrefixedContext, to_upper: Annotated[str, UpperConverter]):
    await ctx.reply(to_upper)
```

For prefixed commands, Interfluxer will use the second parameter in `Annotated` as the actual converter/parameter to process.
