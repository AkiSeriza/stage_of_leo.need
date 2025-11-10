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
PHOTO_FOLDER = os.path.join(BASE_DIR, "Databases", "Photos")
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
                    with open(os.path.join(server_folders, j), "w") as f:
                        json.dump({}, f)
    
    def load_global_server_info(self):
        servers = os.path.join(QOTD_FOLDER, "qotd_servers.json")
        if not os.path.exists(servers):
            with open(servers, "w") as f:
                json.dump({}, f)
        with open(servers, "r") as f:
            return json.load(f)
    
    async def send_qotd(self, server_id, interaction):
        suggestion_file = os.path.join(QOTD_FOLDER, server_id, "suggestions.json")
        log_file = os.path.join(QOTD_FOLDER, server_id, "log.json")
        today = datetime.datetime.today()
        formatted = today.strftime("%Y-%m-%d") 
        with open(suggestion_file,"r") as f:
            suggest_file_open = json.load(f)
        keys = list(suggest_file_open.keys())
        today_selected = random.choice(keys)
        with open(log_file, "r") as f:
            log_file_open = json.load(f)
        selected = {}
        selected["question"] = suggest_file_open[today_selected]["suggestion"]
        selected["suggestor"] = suggest_file_open[today_selected]["suggestor"]
        selected["time"] = suggest_file_open[today_selected]["time"]
        self.check_server_folders()
        index = self.global_server_data[server_id]["index"]
        log_file_open[index] = selected
        suggest_file_open.pop(today_selected)
        with open(suggestion_file,"w", encoding="utf-8") as f:
            json.dump(suggest_file_open, f)
        with open(log_file,"w", encoding="utf-8") as f:
            json.dump(log_file_open, f)
        embed = discord.Embed(
            color=0x4169E1, 
            description= f"**<:ichiheart:1384047120704602112> Question of the Day #{index} for {formatted}**")
        self.global_server_data[server_id]["index"] += 1
        servers_file = os.path.join(QOTD_FOLDER, "qotd_servers.json")
        with open(servers_file, "w", encoding="utf-8") as f:
            json.dump(self.global_server_data, f, indent=4)
        channel_id = self.global_server_data[server_id]["channel_id"]
        channel = interaction.guild.get_channel(channel_id)
        role = self.global_server_data[server_id]["role"]
        embed.add_field(name=selected["question"], value=" ", inline=False)
        member = interaction.guild.get_member(selected["suggestor"])
        if not member: 
            try:
                member = await self.bot.fetch_user(selected["suggestor"])
            except:
                member = None

        member_name = member.display_name if member else f"User ID {selected['suggestor']}"
        embed.set_footer(text=f"Suggested by {member_name} on {selected["time"]}")
        await channel.send(f"<@&{role}>")
        await channel.send(embed=embed)


    



    @app_commands.command(
            name="qotdsetup", description="Setup QOTD funtionality for the server"
            )
    @app_commands.describe(
        channel = "Channel where the QOTD is sent",
        time = "Time in US Pacific time to send the QOTD (24H format eg. 1800)",
        role = "Role to ping when QOTD comes (Optional)"
        )
    @app_commands.checks.has_permissions(administrator=True)
    async def qotdsetup(self, interaction: discord.Interaction, channel: discord.TextChannel, time: str, role: discord.Role = None):
        file = discord.File(os.path.join(PHOTO_FOLDER,"Ichika_think.jpg"), filename="Ichika_think.jpg")
        embed = discord.Embed(
            color=0x4169E1,
            description= "Setup Complete!"
        )
        embed.set_thumbnail(url="attachment://Ichika_think.jpg")
        embed.add_field(name="Channel", value=channel, inline=True)
        embed.add_field(name="Role", value=role if role else "None", inline=True)
        embed.add_field(name="Time", value=time, inline=True)
        await interaction.response.send_message(embed=embed, file = file , ephemeral=True)
        server_id = str(interaction.guild.id)
        self.global_server_data.setdefault(server_id, {})
        self.global_server_data[server_id]["channel_id"] = channel.id
        self.global_server_data[server_id]["time"] = time
        self.global_server_data[server_id]["role"] = role.id if role else None
        self.global_server_data[server_id]["index"] = 1        
        with open(os.path.join(QOTD_FOLDER, "qotd_servers.json"), "w", encoding="utf-8") as f:
            json.dump(self.global_server_data, f, indent = 4)
        self.check_server_folders()

    @app_commands.command(name="qotdsuggest", description="Suggest a QOTD to the server")
    @app_commands.describe(suggestion = "Your Suggestion here")
    async def qotdsuggest(self, interaction: discord.Interaction, suggestion: str):
        now = datetime.datetime.now()
        formatted = now.strftime("%Y-%m-%d %H:%M:%S") 
        server = str(interaction.guild_id)
        message_id = str(interaction.id)
        server_file= os.path.join(QOTD_FOLDER, server, "suggestions.json")
        suggestionF = {}
        suggestionF.setdefault(message_id, {})
        suggestionF["suggestor"] = interaction.user.id
        suggestionF["suggestion"] = suggestion
        suggestionF["time"] = formatted
        with open(server_file, "r",encoding="utf-8") as f:
            temp_server_suggestions = json.load(f)
        temp_server_suggestions[message_id] = suggestionF
        with open(server_file, "w",encoding="utf-8") as f:
            json.dump(temp_server_suggestions, f)
        await interaction.response.send_message("Suggestion Recieved!")
    
    @app_commands.command(name="qotdforce", description="Force to send a QOTD")
    @app_commands.checks.has_permissions(administrator=True)
    async def qotdforce(self, interaction: discord.Interaction):
        server_id = str(interaction.guild.id)
        await self.send_qotd(server_id, interaction)
        await interaction.response.send_message("QOTD sent!", ephemeral=True)



    

async def setup(bot):
    await bot.add_cog(QOTD(bot))
            


    


