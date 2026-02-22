---
search:
  boost: 3
---

# Migrating from 4.X

Version 5.X (and beyond) is a major rewrite of Interfluxer compared to 4.X, though there have been major improvements to compensate for the change. 5.X was designed to be more stable and flexible, solving many of the bugs and UX issues 4.X had while also adding additional features you may like.

**You will need to do some updating and rewriting of your code,** but it's not as daunting as it may seem. We've provided this document as a starting point (*though it is not exhaustive*), and we have plenty of guides and documentation to help you learn the other parts of this library. Lastly, our support team is always here to help if you need it [in our Fluxer server](discord.gg/Interfluxer).

Now, let's get started, shall we?

???+ note
    In v5's documentation, you will often see imports using the format `from Interfluxer import X`, unlike v4. You can still use `import Interfluxer` and do `Interfluxer.X` though.

    Events, errors, and utilities are under their own sub-namespace when using `import Interfluxer`. For example, events are under `Interfluxer.events.X`.

## Python Version Change

Starting from version 5, **Python 3.10 or higher is now required**, whereas version 4 only needed 3.8+. This is because 5.x incorporates many new and exciting features introduced in more recent versions of Python.

For Windows users, this is usually as simple as downloading 3.10 or higher (ideally the latest version for the most speed and features) and possibly removing the old version if you have no other projects that depend on older versions.

For Linux and MacOS, we recommend using [pyenv](https://github.com/pyenv/pyenv); _pyenv lets you easily switch between multiple versions of Python. It's simple, unobtrusive, and follows the UNIX tradition of single-purpose tools that do one thing well._ We strongly suggest consulting pyenv's guides on installation.

If you prefer not to use pyenv, there are many guides available that can help you safely install a newer version of Python alongside your existing version.

## Commands

Commands function differently from v4's commands - it's worth taking a good look at the guide to see [how they work in the library now](../03 Creating Commands).

Big changes include the fact that `@bot.command` (we'll get to extensions later) is now `@Interfluxer.prefixed_command`, and `CommandContext` is now `PrefixedContext`. There may be some slight renamings elsewhere too in the decorators itself - it's suggested you look over the options for the new decorator and appropriately adapt your code.

## Events

Similarly to Slash Commands, events have also been reworked in v5. Instead of `@bot.event` and `@extension_listener`, the way to listen to events is now `@listen`. There are multiple ways to subscribe to events, whether it is using the function name or the argument of the `@listen` decorator. You can find more information on handling events using v5 [on its own guide page](../10 Events).

An important note: events now dispatch an event object that contains every part about an event, instead of the object that directly corresponds to an event. For example, message creation now looks like this:

```python
from Interfluxer import listen
from Interfluxer.api.events import MessageCreate


@listen()
async def on_message_create(event: MessageCreate):
    event.message  # actual message
```

This is more notable with events that used to have two or more arguments. They *also* now only have one event object:

```python
from Interfluxer.api.events import MemberUpdate


@listen()
async def on_member_update(event: MemberUpdate):
    event.before  # before update
    event.after  # after update
```

## Extensions (cogs)

Extensions have not been changed too much. `await teardown(...)` is now just `drop(...)` (note how drop is *not* async), and you use `bot.load_extension`/`bot.unload_extension` instead of `bot.load`/`bot.unload`.

There is one major difference though that isn't fully related to extensions themselves: *you use the same decorator for both commands/events in your main file and commands/events in extensions in v5.* Basically, instead of having `bot.command` and `Interfluxer.extension_command`, you *just* have `Interfluxer.prefixed_command` (and so on for events, etc.), which functions seemlessly in both contexts.

Also, you no longer require a `setup` function. They can still be used, but if you have no need for them other than just loading the extension, you can get rid of them if you want.

## Cache and Interfluxer.get

Instead of the `await Interfluxer.get` function in v4, v5 introduces the `await bot.fetch_X` and `bot.get_X` functions, where `X` will be the type of object that you would like to retrieve (user, guild, role...). You might ask, what is the difference between fetch and get?

The answer is simple, `get` will look for an object that has been cached, and therefore is a synchronous function that can return None if this object has never been cached before.

On the other hand, `fetch` is an asynchronous function that will request the Fluxer API to find that object if it has not been cached before. This will *fetch* the latest version of the object from Fluxer, provided that the IDs you inputted are valid.

## Library extensions

In v4, many extensions could be separately added to your bot to add external functionalities (molter, paginator, tasks, etc...). Many of those extensions were merged in the main library for v5, therefore you will NOT need to download additional packages for functionalities such as sharding or tasks.

## asyncio Changes

In recent Python versions, `asyncio` has gone through a major change on how it treats its "loops," the major thing that controls asynchronous programming. Instead of allowing libraries to create and manage their own loops, `asyncio` now encourages (and soon will enforce) users to use one loop managed by `asyncio` itself.

What this means to you is that *the `Client` does not have a loop variable, and no `asyncio` loop exists until the bot is started (if you use `bot.start()`).*

For accessing the loop itself, there is [`asyncio.get_running_loop()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_running_loop) to, well, get the running loop, though you're probably using the loop to run a task - it's better to use [`asyncio.create_task(...)`](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task) for that instead if you are.

However, as for the second point... it shouldn't impact most users, but this may if you use `create_task` to run an asynchronous function before the bot starts - *this including loading in an extension that uses it before the bot is properly started.* Both of the above functions will error out if used, so using them isn't an option.

So what do you do? Simple - create the loop "yourself" and use `bot.astart()` instead!

Before:

```python
import Interfluxer

# if there's no loop detected, v4 would create the loop for you at this point
# it also stores the loop in bot._loop
bot = Interfluxer.Client(...)

bot._loop.create_task(some_func())
bot.load("an_ext_that_uses_the_event_loop")

bot.start()
```

After:

```python
import asyncio
import Interfluxer

# no bot._loop, loop also does not exist yet
bot = Interfluxer.Client(...)


async def main():
    # loop now exists, woo!
    asyncio.create_task(some_func())
    bot.load_extension("an_ext_that_uses_the_event_loop")
    await bot.astart()


# a function in asyncio that creates the loop for you and runs
# the function within
asyncio.run(main())
```

It's worth noting that you can continue to use `bot.start()` and not change your code if you never relied on `asyncio` like this.
