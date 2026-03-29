import discord
import os
from groq import Groq

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

intents = discord.Intents.all()
client = discord.Client(intents=intents)

ai = Groq(api_key=GROQ_API_KEY)

@client.event
async def on_ready():
    print(f"GopalBot is online as {client.user}")

@client.event
async def on_message(message):
    print(f"Message received from {message.author}: {message.content}")

    if message.author == client.user:
        return

    bot_mentioned = client.user.mentioned_in(message)
    has_bot_name = "gopalbot" in message.content.lower()
    is_dm = isinstance(message.channel, discord.DMChannel)

    if bot_mentioned or has_bot_name or is_dm:
        prompt = message.content
        prompt = prompt.replace(f"<@{client.user.id}>", "").strip()
        prompt = prompt.replace(f"<@!{client.user.id}>", "").strip()
        prompt = prompt.replace("gopalbot", "").strip()
        prompt = prompt.replace("GopalBot", "").strip()

        if not prompt:
            await message.channel.send("Hi! Ask me anything!")
            return

        print(f"Responding to: {prompt}")
        async with message.channel.typing():
            try:
                response = ai.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "You are GopalBot, a helpful AI assistant in a Discord server. Keep answers concise and friendly."},
                        {"role": "user", "content": prompt}
                    ]
                )
                reply = response.choices[0].message.content
                if len(reply) > 2000:
                    reply = reply[:1997] + "..."
                await message.channel.send(reply)
                print(f"Replied successfully!")
            except Exception as e:
                print(f"Error: {e}")
                await message.channel.send("Sorry, something went wrong!")

client.run(DISCORD_TOKEN)
    