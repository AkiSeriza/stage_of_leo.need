import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import bot
from database import Database

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
    bot.db = await Database.create()
    async with bot:
        await load_extensions()
        await bot.start(os.getenv("DISCORD_TOKEN"))
    await bot.db.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

