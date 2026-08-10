import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import aiosqlite
import bot
from database import Database
import html

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
ECON = "Databases/economy.db"

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

extensions = [
    "radio",
    "fun",
    "qotd",
    "starboard",
    "jobs",
    ###"songguess",
    'tierlist',
    'economy',
    'fortune'
    ###"jeopardy"
]

async def load_extensions():
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"Loaded: {ext}")
        except Exception as e:
            print(f"Failed to load {ext}: {e}")

@bot.command(name="close")
@commands.is_owner()
async def close(ctx):
    await ctx.send("Shutting down...")
    await bot.close()

async def main():
    conn = await aiosqlite.connect(ECON)
    await conn.execute("PRAGMA foreign_keys = ON")
    bot.db = Database(conn)
    async with bot:
        await load_extensions()
        await bot.start(os.getenv("DISCORD_TOKEN"))
    await bot.db.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

