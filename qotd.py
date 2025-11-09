import discord
from discord import app_commands
from discord.ext import commands    
import os
import json
import datetime
import random
from logger import log

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QOTD_FOLDER = os.path.join(BASE_DIR, "Databases", "QOTD")
expected_files = ["suggestions.json", "log.json"]


class QOTD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_server_folders()

    def check_server_folders(self):
        self.global_server_data = self.load_global_server_info()
        self.server_ids = list(self.global_server_data.keys())
        for i in self.server_ids:
            server_folders = os.path.join(QOTD_FOLDER, i)
            if not os.path.exists(server_folders):
                os.makedirs(server_folders)
            for j in expected_files:
                if not os.path.exists(os.path.join(server_folders, j)):
                    with open(os.path.join(server_folders, j), "w"):
                        pass
    
    def load_global_server_info(self):
        servers = os.path.join(QOTD_FOLDER, "qotd_servers.json")
        if not os.path.exists(servers):
            with open(servers, "w") as f:
                json.dump({}, f)
        with open(servers, "r") as f:
            return json.load(f)
        

    @app_commands.command(
            name="qotdsetup", description="Setup QOTD funtionality for the server"
            )
    @app_commands.describe(
        channel = "Channel where the QOTD is sent",
        time = "Time in US Pacific time to send the QOTD (24H format eg. 1800)",
        role = "Role to ping when QOTD comes (Optional)"
        )
    async def qotd_setup(self, interaction: discord.Interaction, channel: discord.TextChannel, time: str, role: discord.Role = None):
        server_id = str(interaction.guild.id)
        self.global_server_data.setdefault(server_id, {})
        self.global_server_data[server_id]["channel_id"] = channel.id
        self.global_server_data[server_id]["time"] = time
        self.global_server_data[server_id]["role"] = role.id if role else None
        self.global_server_data[server_id]["index"] = 1        
        with open(os.path.join(QOTD_FOLDER, "qotd_servers.json"), "w", encoding="utf-8") as f:
            json.dump(self.global_server_data, f, indent = 4)
        self.check_server_folders()
        await discord.Message()

    """@app_commands.command(name="qotdsuggest", description="Suggest a QOTD to the server")
    @app_commands.describe(suggestion = "Your Suggestion here")
"""

        
        
async def setup(bot):
    await bot.add_cog(QOTD(bot))
            


    


