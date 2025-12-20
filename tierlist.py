import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import math
from io import BytesIO
import os
from datetime import datetime, timezone
from discord import File
import asyncio
from tierlistgen import tlm


#-----------------------------------------------IMPORTS-----------------------------------------------#

#Main Imports
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "Databases", "Tierlist")

#Bootup
SERVER_SETUP_PATH = os.path.join(DB_DIR, "serversetups.json")
SONG_LIST_PATH = os.path.join(DB_DIR, "songslist.json")

#Votes
SONG_VOTES = os.path.join(DB_DIR, "votesbysong.json")
USER_VOTES = os.path.join(DB_DIR, "votesbyuser.json")
SERVER_VOTES = os.path.join(DB_DIR, "tierlistbyserver.json")

#Misc
PHOTO_FOLDER = os.path.join(BASE_DIR, "Databases", "Photos")

pjsk_colors = {
    "VS": 0x00CDBA,
    "L":  0x4455DD,
    "M":  0x6CCB20,
    "V":  0xEE1166,
    "W":  0xFF9900,
    "N":  0x884499
}

standard_tiers = {
    ###Tier: [Score, Threshold]
    "SSS": [25,7],
    "S+": [10,7],
    "S": [7,6],
    "A": [5,4],
    "B": [4,1],
    "C": [3,0],
    "D": [2,0]
}
tier_limits = {
    "SSS": 3,
    "S+": 5,
    "S": 10
}
Standard_score = {
    "ScoreMap":{
        "SSS":25,
        "S+": 10,
        "S": 7,
        "A": 5,
        "B": 4,
        "C": 3,
        "D": 2
    },
    "Thresholds":{
        "SSS":7,
        "S+": 7,
        "S": 6,
        "A": 4,
        "B": 1,
        "C": 0,
        "D": 0
    }
}
#-----------------------------------------------INPUT/OUTPUT-----------------------------------------------#

def loadJSON(fileinput):
    with open(fileinput, "r", encoding="utf-8") as f:
        temp = json.load(f)
        return temp

def saveJSON(inputdict, fileoutput):
    with open(fileoutput, "w", encoding="utf-8") as f:
        json.dump(inputdict, f, indent=4)

#-----------------------------------------------HELPER FUNCTIONS-----------------------------------------------#
def recalculate_tierlist_from_votes():
    user_votes = loadJSON(USER_VOTES)
    server_data = loadJSON(SERVER_SETUP_PATH)
    write_file = {}
    #Compiles Users in the same server to singular total
    for server in server_data:
        server_scores = {}
        server_tierlist = {"SSS":[],"S+":[],"S":[],"A":[], "B":[],"C":[], "D":[]}
        for vote in user_votes[server]:
            for tier_scores in server_data[server]["ScoreMap"]:
                if tier_scores in user_votes[server][vote]:
                    for song in user_votes[server][vote][tier_scores]:
                        if song not in server_scores:
                            server_scores[song] = [0, 0]
                        server_scores[song][0] += server_data[server]["ScoreMap"].get(tier_scores, 0)
                        server_scores[song][1] += 1
        total_songs = 0
        for song in server_scores:
            total_songs +=1
            server_scores[song] = server_scores[song][0]/(server_scores[song][1]+3)
        tier_limits["A"] = math.ceil(total_songs * 0.2)
        tier_limits["B"] = math.ceil(total_songs * 0.4)
        tier_limits["C"] = 10000000000000000
        tier_limits["D"] = 10000000000000000
        server_scores = dict(sorted(server_scores.items(), key=lambda x:x[1], reverse=True))
        thresholds = server_data[server]["Thresholds"]
        for song in server_scores:
            for tiers in thresholds:
                if tiers in tier_limits:
                    if server_scores[song] > thresholds[tiers] and len(server_tierlist[tiers])<tier_limits[tiers]:
                        server_tierlist[tiers].append(song)
                        break
                else:
                    if server_scores[song] > thresholds[tiers]:
                        server_tierlist[tiers].append(song)
                        break
        write_file[server] = server_tierlist
    saveJSON(write_file,SERVER_VOTES)
recalculate_tierlist_from_votes()
#-----------------------------------------------VIEWS-----------------------------------------------#
class TierlistButtons(discord.ui.View):
    def __init__(self, selected_song, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.selected_song = selected_song
        for tier in standard_tiers:
            button = discord.ui.Button(label=tier, style=discord.ButtonStyle.primary)
            async def button_callback(interaction: discord.Interaction, tier=tier):
                user_votes = cog.user_votes.get(str(interaction.guild.id), {}).get(str(interaction.user.id), {})
                sss_votes = user_votes.get("SSS", [])
                if tier == "SSS" and len(sss_votes) >= 3:
                    await interaction.response.send_message(f"You already have 3 Votes of SSS; use /tierlistself to see which songs you have dedicated your SSS votes for!", ephemeral=True)
                    return 0
                await self.cog.register_vote(interaction.user.id, interaction.guild.id, self.selected_song, tier)
                await interaction.response.send_message(f"You voted {tier} for {self.selected_song}!", ephemeral=True)
            button.callback = button_callback
            self.add_item(button)

class RevoteDropdown(discord.ui.View):
    def __init__(self, pages, cog):
        super().__init__(timeout=None)
        self.pages = pages
        self.cog = cog
        self.page_index = 0
        self.select = discord.ui.Select(options=self.pages[self.page_index])
        self.select.callback = self.select_callback
        self.add_item(self.select)
        self.prev_button = discord.ui.Button(label="⬅️", style=discord.ButtonStyle.blurple)
        self.next_button = discord.ui.Button(label="➡️", style=discord.ButtonStyle.blurple)
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page
        self.add_item(self.prev_button)
        self.add_item(self.next_button)

    async def select_callback(self, interaction: discord.Interaction):
        chosen = self.select.values[0]

        # Use followup if already responded
        await interaction.response.defer(ephemeral=True)  # ephemeral response
        await self.cog.send_embed(interaction, chosen, interaction.channel.id, boolresponse=True)

    async def prev_page(self, interaction: discord.Interaction):
        if self.page_index > 0:
            self.page_index -= 1
            self.update_select()
            await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        if self.page_index < len(self.pages) - 1:
            self.page_index += 1
            self.update_select()
            await interaction.response.edit_message(view=self)

    def update_select(self):
        self.remove_item(self.select)
        self.select = discord.ui.Select(options=self.pages[self.page_index])
        self.select.callback = self.select_callback
        self.add_item(self.select)



#-----------------------------------------------BOT INITIALIZE-----------------------------------------------#
class TierList(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.vote_lock = asyncio.Lock()
        self.bot = bot    
        self.user_votes = loadJSON(USER_VOTES)
        self.song_vote = loadJSON(SONG_VOTES)
        self.song_list = loadJSON(SONG_LIST_PATH)
        self.server_data = loadJSON(SERVER_SETUP_PATH)
        self.saving.start() 
        self.recalc.start()
        self.daily.start()
#-----------------------------------------------METHODS-----------------------------------------------#
    async def register_vote(self, user, server, song, vote):
        async with self.vote_lock:
            user = str(user)
            server = str(server)
            # --- user tierlist ---
            user_data = self.user_votes
            user_data.setdefault(server, {}).setdefault(user, {})
            for tier in standard_tiers:
                user_data[server][user].setdefault(tier, [])                
            for tier in standard_tiers:
                if song in user_data[server][user][tier]:
                    user_data[server][user][tier].remove(song)
            user_data[server][user][vote].append(song)
            saveJSON(user_data, USER_VOTES)
            # --- song votes ---
            votes = self.song_vote
            votes.setdefault(song, {}).setdefault(server, {})
            votes[song][server][user] = vote
            saveJSON(votes, SONG_VOTES)

    def remove_vote(self, user, server, song):
        if server in self.user_votes and user in self.user_votes[server]:
            for tier in list(self.user_votes[server][user].keys()):
                if song in self.user_votes[server][user][tier]:
                    self.user_votes[server][user][tier].remove(song)
                    if not self.user_votes[server][user][tier]:
                        del self.user_votes[server][user][tier]
        if song in self.song_vote and server in self.song_vote[song]:
            self.song_vote[song][server].pop(user, None)
    
    def tierlistembed(self, selected_song):
        song_dict = loadJSON(SONG_LIST_PATH)
        song = song_dict[selected_song]
        embed = discord.Embed(
            title=selected_song,
            description=f"[{song.get('eng', 'No English title')}]({song.get('yt', '')})",
            color=pjsk_colors[song["unit"]]
        )
        embed.add_field(name="", value=song.get("Commission", "-"), inline=False)
        embed.add_field(name="**Arranger**", value=song.get("Arranger", "-"), inline=True)
        embed.add_field(name="**Composer**", value=song.get("Composer", "-"), inline=True)
        embed.add_field(name="**Lyricist**", value=song.get("Lyricist", "-"), inline=True)
        embed.add_field(name="**JP Release**", value=song.get("JP Release", "-"), inline=True)
        embed.set_footer(text="Use /tierlistrevote to vote on a previously voted song!", icon_url="https://i.namu.wiki/i/J4ZwMcNsF1aC5H9jpfYiKZqOhjI2ucqXytSd5zAfx-Qy6GTLXdwvW86KW_lDthZChvdwMoU4cXK9hpJhKEzYsA.webp")
        if song.get("link"):
            embed.set_thumbnail(url=song["link"])
        return embed

    async def send_embed(self, interaction: discord.Interaction,selected_song, channel_id,boolresponse=False):
        embed = self.tierlistembed(selected_song)
        if interaction == None:
            print("recieved none argument 2")
            channel = await self.bot.fetch_channel(channel_id)
            print("eyyyyyyyyy")
            view =  TierlistButtons(selected_song,self)
            message = await channel.send(embed=embed, view=view)
            return message
        guild_id = str(interaction.guild.id)
        if guild_id not in self.server_data:
            await interaction.response.send_message("This server is not configured.", ephemeral=True)
            return
        if not channel_id:
            await interaction.response.send_message("No channel is configured for this server.", ephemeral=True)
            return
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message("Configured channel not found.", ephemeral=True)
            return
        view = TierlistButtons(selected_song,self)
        if boolresponse:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return None
        else:
            message = await channel.send(embed=embed, view=view)
            return message


#-----------------------------------------------LOOPS-----------------------------------------------#
    @tasks.loop(seconds = 60)
    async def saving(self):
        self.server_data = loadJSON(SERVER_SETUP_PATH)
        self.song_list = loadJSON(SONG_LIST_PATH)
        saveJSON(self.user_votes, USER_VOTES)
        saveJSON(self.song_vote, SONG_VOTES)
    
    @tasks.loop(hours=3)
    async def recalc(self):
        recalculate_tierlist_from_votes()

    @saving.before_loop
    async def before_saving(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(seconds = 60)
    async def daily(self):
        now_utc = datetime.now(timezone.utc)
        hours_minutes = now_utc.strftime("%H:%M")
        for guild_id in self.server_data:
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                break
            else:
                if self.server_data[guild_id]["Time"] == hours_minutes:
                    channel_id = int(self.server_data[guild_id].get("Channel"))
                    channel = await self.bot.fetch_channel(channel_id)
                    index = self.server_data[guild_id].get("index", 0)
                    song_names = list(self.song_list.keys())
                    if index >= len(song_names):
                        index = index % len(song_names)
                    selected_song = song_names[index]
                    await channel.send(f"<@&{self.server_data[guild_id]["Role"]}>")
                    message = await self.send_embed(None, selected_song, channel_id)
                    self.server_data[guild_id]["index"] = index + 1
                    thread = await message.create_thread(
                        name=f"Tierlist Discussion: {selected_song}",
                        auto_archive_duration=1440,
                        reason="Tierlist Discussion"
                    )
                    server_votes = loadJSON(SERVER_VOTES)
                    server_id = guild_id
                    requested_tierlist = server_votes[server_id]
                    img = tlm(requested_tierlist,SONG_LIST_PATH)
                    buffer = BytesIO()
                    img.save(buffer, format="PNG")
                    buffer.seek(0)
                    server = self.bot.get_guild(int(server_id))
                    embed = discord.Embed(
                        color=0x4169E1,
                        title=f"Current Tierlist for {server.name}"
                    )
                    embed.set_image(url="attachment://tierlist.png")
                    embed.set_footer(
                        text="Use /tierlistrevote to vote on a previously voted song!",
                        icon_url="https://i.namu.wiki/i/J4ZwMcNsF1aC5H9jpfYiKZqOhjI2ucqXytSd5zAfx-Qy6GTLXdwvW86KW_lDthZChvdwMoU4cXK9hpJhKEzYsA.webp"
                    )
                    file = File(buffer, filename="tierlist.png")
                    await thread.send(embed=embed, file=file)
                    saveJSON(self.server_data, SERVER_SETUP_PATH)
    

#-----------------------------------------------COMMANDS-----------------------------------------------#
    @app_commands.command(name="tierlistsetup", description="Configure the tierlist system for this server")
    @app_commands.describe(
        channel = "Channel where the Daily Tierlist is sent",
        time = "Time in US Pacific time to send the Tierlist (24H format eg. 18:00)",
        role = "Role to ping when Tierlist comes (Optional)"
        )
    @app_commands.checks.has_permissions(administrator=True)
    async def tierlistsetup(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role, time: str):
        try:
            hh, mm = map(int, time.split(":"))
            if not (0 <= hh < 24 and 0 <= mm < 60):
                raise ValueError
        except Exception:
            await interaction.response.send_message(
                "Time must be in HH:MM 24-hour Pacific time format.", ephemeral=True
            )
            return
        server_id = str(interaction.guild_id)
        setups = loadJSON(SERVER_SETUP_PATH)
        setups.setdefault(server_id, {})
        setups[server_id]["Channel"] = str(channel.id)
        setups[server_id]["Role"] = str(role.id)
        setups[server_id].setdefault("ScoreMap", Standard_score["ScoreMap"])
        setups[server_id].setdefault("Thresholds", Standard_score["Thresholds"])
        setups[server_id].setdefault("index", 0)
        setups[server_id]["Time"] = f"{hh:02d}:{mm:02d}"  
        saveJSON(setups, SERVER_SETUP_PATH)
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

   
    @app_commands.command(
        name="adminforcetierlist",
        description="Send the next song in the server's configured channel"
    )
    async def adminforcetierlist(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        guild_id = str(guild_id)
        channel_id = self.server_data[guild_id].get("Channel")
        channel = self.bot.get_channel(int(channel_id))
        index = self.server_data[guild_id].get("index", 0)
        song_names = list(self.song_list.keys())
        if index >= len(song_names):
            index = index % len(song_names)
        selected_song = song_names[index]
        await channel.send(f"<@&{self.server_data[guild_id]["Role"]}>")
        message = await self.send_embed(interaction, selected_song, channel_id)
        thread = await message.create_thread(
            name=f"Tierlist Discussion: {selected_song}",
            auto_archive_duration=1440,
            reason="Tierlist Discussion"
        )
        server_votes = loadJSON(SERVER_VOTES)
        server_id = str(interaction.guild_id)
        requested_tierlist = server_votes[server_id]
        img = tlm(requested_tierlist,SONG_LIST_PATH)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        server = self.bot.get_guild(int(server_id))
        embed = discord.Embed(
            color=0x4169E1,
            title=f"Current Tierlist for {server.name}"
        )
        embed.set_image(url="attachment://tierlist.png")
        embed.set_footer(
            text="Use /tierlistrevote to vote on a previously voted song!",
            icon_url="https://i.namu.wiki/i/J4ZwMcNsF1aC5H9jpfYiKZqOhjI2ucqXytSd5zAfx-Qy6GTLXdwvW86KW_lDthZChvdwMoU4cXK9hpJhKEzYsA.webp"
        )
        file = File(buffer, filename="tierlist.png")
        await thread.send(embed=embed, file=file)
        self.server_data[guild_id]["index"] = index + 1
        saveJSON(self.server_data, SERVER_SETUP_PATH)
        await interaction.response.send_message(f"Forced the tierlist to advance to {selected_song}")

    @app_commands.command(
        name="tierlistrecalc",
        description="Recalculates the tierlist"
    )
    async def recalcs(self, interaction: discord.Interaction):
        recalculate_tierlist_from_votes()

    @app_commands.command(
        name="tierlistrevote",
        description="Revote for a song you missed out on"
    )
    async def revote(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        completed_songs = self.server_data[guild_id]["index"]
        slist = list(self.song_list)
        options = [discord.SelectOption(label=f"{i}") for i in slist[:completed_songs]]  # 75 total
        pages = [options[i:i+25] for i in range(0, len(options), 25)]
        view = RevoteDropdown(pages, self)
        await interaction.response.send_message("Revote Here", view=view, ephemeral=True)
    
    @app_commands.command(
        name="tierlistserver",
        description="Show the tierlist for the server"
    )
    async def servertierlist(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        server_votes = loadJSON(SERVER_VOTES)
        server_id = interaction.guild_id
        requested_tierlist = server_votes[server_id]
        img = tlm(requested_tierlist,SONG_LIST_PATH)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        server = self.bot.get_guild(int(server_id))
        embed = discord.Embed(
            color=0x4169E1,
            title=f"Current Tierlist for {server.name}"
        )
        embed.set_image(url="attachment://tierlist.png")
        embed.set_footer(
            text="Use /tierlistrevote to vote on a previously voted song!",
            icon_url="https://i.namu.wiki/i/J4ZwMcNsF1aC5H9jpfYiKZqOhjI2ucqXytSd5zAfx-Qy6GTLXdwvW86KW_lDthZChvdwMoU4cXK9hpJhKEzYsA.webp"
        )
        file = File(buffer, filename="tierlist.png")
        await interaction.followup.send(embed=embed, file=file)

    @app_commands.command(
        name="tierlistself",
        description="Show own tierlist (please use sparingly the server might die)"
    )
    async def usertierlist(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        user_votes = loadJSON(USER_VOTES)
        server_id = str(interaction.guild_id)
        print(user_votes[server_id][user_id])
        requested_tierlist = user_votes[server_id][user_id]
        img = tlm(requested_tierlist,SONG_LIST_PATH)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        server = self.bot.get_guild(int(server_id))
        embed = discord.Embed(
            color=0x4169E1,
            title=f"{interaction.user.name}'s Tierlist on  {server.name}"
        )
        embed.set_image(url="attachment://tierlist.png")
        embed.set_footer(
            text="Use /tierlistrevote to vote on a previously voted song!",
            icon_url="https://i.namu.wiki/i/J4ZwMcNsF1aC5H9jpfYiKZqOhjI2ucqXytSd5zAfx-Qy6GTLXdwvW86KW_lDthZChvdwMoU4cXK9hpJhKEzYsA.webp"
        )
        file = File(buffer, filename="tierlist.png")
        await interaction.followup.send(embed=embed, file=file)

async def setup(bot):
    await bot.add_cog(TierList(bot))



        
