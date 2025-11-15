import discord
from discord import app_commands
from discord.ext import commands    
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_FOLDER = os.path.join(BASE_DIR, "Databases")

ichipeek_count = os.path.join(DATABASE_FOLDER, "ichipeek_counts.csv")

def ensure_exist(path):
    NEW_PATH = os.path.join(BASE_DIR, path)
    if not os.path.exists(NEW_PATH):
        os.makedirs(NEW_PATH)

def load_json(paths):
    ensure_exist(paths)
    with open(paths, "r", encoding="utf-8") as f:
        print("hi")
        files = json.load(f)
    print(files)
    return files

def save_json(path, new_data):
    ensure_exist(path)
    previous_file = load_json(path)
    with open(path, "w", encoding="utc-8") as f:
        files = json.load(f)
    return files

test = load_json(r"E:\Code\DiscordBots\stage-of-leo.need\Databases\ichika_anthology.json")
print(os.path.exists(ichipeek_count))
print(type(test))

"""

class counter(commands.Cog):
    def __init__(self,bot):
        pass
"""
    
        
