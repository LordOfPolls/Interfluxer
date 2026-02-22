import flux

# Now, let's create an instance of a bot.
intents = flux.Intents.DEFAULT | flux.Intents.MESSAGE_CONTENT
client = flux.Client(intents=intents)


@flux.listen()
async def on_ready():
    # We can use the client "app" attribute to get information about the bot.
    print(f"We're online! We've logged in as {client.app.name}.")

    # We're also able to use property methods to gather additional data.
    print(f"Our latency is {round(client.latency)} ms.")


@flux.listen("on_message_create")
async def on_message_create(message_create: flux.events.MessageCreate):
    message: flux.Message = message_create.message
    print(f"We've received a message from {message.author.username}. The message is: {message.content}.")


client.start("Your token here.")
