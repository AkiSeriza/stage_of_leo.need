import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

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
    "starboard"
]

async def load_extensions():
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"Loaded: {ext}")
        except Exception as e:
            print(f"Failed to load {ext}: {e}")

async def main():
    async with bot:
        await load_extensions()
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
