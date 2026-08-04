# bot.py
from discord.ext import commands
from database import Database

class MyBot(commands.Bot):
    db: Database