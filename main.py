import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from logger import log

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

extensions = [
    "radio",
    "fun",
    "qotd",
    "starboard",
    #"songguess"
    'tierlist'
]

async def load_extensions():
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"Loaded: {ext}")
            log("info", f"StartUp, Loaded extension: {ext}")
        except Exception as e:
            print(f"Failed to load {ext}: {e}")
            log("error", f"StartUp, Failed to load {ext}: {e}")

async def main():
    async with bot:
        await load_extensions()
        await bot.start(os.getenv("DISCORD_TOKEN"))
        log("info", "Bot started successfully as {bot.user}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

