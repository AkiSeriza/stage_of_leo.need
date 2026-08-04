import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import math
from io import BytesIO
import os
import time
from datetime import datetime, timezone
from discord import File
import asyncio
from tierlistgen import tlm
from songslist import songs as song_database
import random
import re
from database import Database

#-----------------------------------------------IMPORTS-----------------------------------------------#

#Main Imports
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "Databases", "Tierlist")

#Bootup
SERVER_SETUP_PATH = os.path.join(DB_DIR, "serversetups.json")

#Votes
SONG_VOTES = os.path.join(DB_DIR, "votesbysong.json")
USER_VOTES = os.path.join(DB_DIR, "votesbyuser.json")
SERVER_VOTES = os.path.join(DB_DIR, "tierlistbyserver.json")

#Misc
PHOTO_FOLDER = os.path.join(BASE_DIR, "Databases", "Photos")
ENTRIES_DIR = os.path.join(DB_DIR, "Entries")
SONG_JACKETS_DIR = os.path.join(DB_DIR, "Song Jackets")

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
    "SSS": 7,
    "S+": 14,
    "S": 21
}
Standard_score = {
    "ScoreMap": {
        "SSS": 25,
        "S+": 10,
        "S": 7,
        "A": 5,
        "B": 4,
        "C": 3,
        "D": 2
    },
    "Thresholds": {
        "SSS": 8,
        "S+": 6.5,
        "S": 5.5,
        "A": 4.5,
        "B": 4.2,
        "C": 4,
        "D": 3.7
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
    print("DEBUG: Starting tierlist recalculation")
    user_votes = loadJSON(USER_VOTES)
    server_data = loadJSON(SERVER_SETUP_PATH)
    write_file = {}

    for server in server_data:
        print(f"DEBUG: Processing server {server}")
        server_scores = {}
        server_tierlist = {"SSS":[],"S+":[],"S":[],"A":[], "B":[],"C":[], "D":[]}
        for vote in user_votes[server] if server in user_votes else []:
            for tier_scores in server_data[server]["ScoreMap"]:
                if tier_scores in user_votes[server][vote]:
                    for song in user_votes[server][vote][tier_scores]:
                        if song not in server_scores:
                            server_scores[song] = [0, 0]
                        server_scores[song][0] += server_data[server]["ScoreMap"].get(tier_scores, 0)
                        server_scores[song][1] += 1
        for song in server_scores:
            server_scores[song] = server_scores[song][0]/(server_scores[song][1]+5)
        remaining  = len(server_scores) - tier_limits["SSS"] - tier_limits["S+"] - tier_limits["S"]    
        tier_limits["A"] = round(remaining*0.2)
        tier_limits["B"] = round(remaining*0.3)
        tier_limits["C"] = round(remaining*0.4)
        tier_limits["D"] = 100000000000000000000000000
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
        print(server_scores)
    
    saveJSON(write_file,SERVER_VOTES)
    print("DEBUG: Tierlist recalculation completed")

recalculate_tierlist_from_votes()

async def song_autocomplete(interaction: discord.Interaction, current: str):
    current = current or ""
    filtered = [song for song in song_database if current.lower() in song.lower()]
    return [app_commands.Choice(name=song, value=song) for song in filtered[:25]]

#-----------------------------------------------VIEWS-----------------------------------------------#
class TierlistButtons(discord.ui.View):
    def __init__(self, selected_song, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.selected_song = selected_song
        for tier in standard_tiers:
            button = discord.ui.Button(label=tier, style=discord.ButtonStyle.primary)
            async def button_callback(interaction: discord.Interaction, tier=tier):
                await interaction.response.defer()
                print(f"DEBUG: Button clicked for tier {tier} on song {self.selected_song}")
                user_votes = cog.user_votes.get(str(interaction.guild.id), {}).get(str(interaction.user.id), {})
                sss_votes = user_votes.get("SSS", [])
                print(sss_votes)
                if tier == "SSS" and len(sss_votes) >= 7:
                    print(f"DEBUG: User {interaction.user.id} has too many SSS votes")
                    await interaction.followup.send(f"You already have 7 Votes of SSS; use /tierlistself to see which songs you have dedicated your SSS votes for!", ephemeral=True)
                    return 0
                print("Why here")
                await self.cog.register_vote(interaction.user.id, interaction.guild.id, self.selected_song, tier)
                await interaction.followup.send(f"You voted {tier} for {self.selected_song}!", ephemeral=True)
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

        await interaction.response.defer(ephemeral=True)
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
        print("DEBUG: Initializing TierList cog")
        self.vote_lock = asyncio.Lock()
        self.bot = bot    
        self.db: Database = bot.db
        try:
            self.user_votes = loadJSON(USER_VOTES)
            print("DEBUG: Loaded user_votes")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"DEBUG: Failed to load user_votes: {e}, initializing empty")
            self.user_votes = {}
        try:
            self.song_vote = loadJSON(SONG_VOTES)
            print("DEBUG: Loaded song_vote")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"DEBUG: Failed to load song_vote: {e}, initializing empty")
            self.song_vote = {}
        try:
            self.server_data = loadJSON(SERVER_SETUP_PATH)
            print("DEBUG: Loaded server_data")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"DEBUG: Failed to load server_data: {e}, initializing empty")
            self.server_data = {}
        self.saving.start() 
        self.recalc.start()
        self.daily.start()
        print("DEBUG: TierList cog initialized")

#-----------------------------------------------METHODS-----------------------------------------------#
    async def register_vote(self, user, server, song, vote):
        print(f"DEBUG: Registering vote for user {user} in server {server} on song {song} with tier {vote}")
        async with self.vote_lock:
            check = await self.db.fetchall("SELECT LastVoteTime FROM econ WHERE UserID = ?", (user,))
            check = check[0][0] if check else 0
            if int(time.time()) - check > 86400:
                await self.db.change_balance(user,50000,"Tierlist Participation", int(time.time()))
                await self.db.write("UPDATE econ SET LastVoteTime = ? WHERE UserID = ?", (int(time.time()),user))
            print(check)
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
            print(f"DEBUG: Vote registered successfully")

    async def remove_vote(self, user, server, song):
        async with self.vote_lock:
            user = str(user)
            server = str(server)
            # --- user tierlist ---
            user_data = self.user_votes
            for tier in standard_tiers:
                if song in user_data.get(server, {}).get(user, {}).get(tier, []):
                    user_data[server][user][tier].remove(song)
            saveJSON(user_data, USER_VOTES)
            # --- song votes ---
            votes = self.song_vote
            if song in votes and server in votes[song] and user in votes[song][server]:
                del votes[song][server][user]
            saveJSON(votes, SONG_VOTES)

    async def send_embed(self, interaction: discord.Interaction,selected_song, channel_id,boolresponse=False, content=""):
        print(f"DEBUG: Sending embed for song {selected_song}, channel_id {channel_id}, boolresponse {boolresponse}")
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', selected_song)
        image_path = os.path.join(ENTRIES_DIR, f"{clean_name}.png")
        print(f"DEBUG: Image path: {image_path}")
        embed = discord.Embed(
            title=selected_song,
            color=0x4169E1
        )
        embed.set_image(url="attachment://song.png")
        embed.set_footer(text="Use /tierlistrevote to vote on a previously voted song!", icon_url="https://i.namu.wiki/i/J4ZwMcNsF1aC5H9jpfYiKZqOhjI2ucqXytSd5zAfx-Qy6GTLXdwvW86KW_lDthZChvdwMoU4cXK9hpJhKEzYsA.webp")
        file = File(image_path, filename="song.png")
        if interaction == None:
            print("DEBUG: Interaction is None, sending to channel")
            print("recieved none argument 2")
            channel = await self.bot.fetch_channel(channel_id)
            print("eyyyyyyyyy")
            view =  TierlistButtons(selected_song,self)
            message = await channel.send(content=content, embed=embed, view=view, file=file)
            print(f"DEBUG: Message sent to channel {channel_id}")
            return message
        guild_id = str(interaction.guild.id)
        if guild_id not in self.server_data:
            print(f"DEBUG: Guild {guild_id} not configured")
            await interaction.response.send_message("This server is not configured.", ephemeral=True)
            return
        if not channel_id:
            print(f"DEBUG: No channel configured for guild {guild_id}")
            await interaction.response.send_message("No channel is configured for this server.", ephemeral=True)
            return
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            print(f"DEBUG: Channel {channel_id} not found")
            await interaction.response.send_message("Configured channel not found.", ephemeral=True)
            return
        view = TierlistButtons(selected_song,self)
        if boolresponse:
            print("DEBUG: Sending followup")
            await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=True, file=file)
            return None
        else:
            print("DEBUG: Sending to channel")
            message = await channel.send(content=content, embed=embed, view=view, file=file)
            print(f"DEBUG: Message sent to channel {channel_id}")
            return message


#-----------------------------------------------LOOPS-----------------------------------------------#
    @tasks.loop(seconds = 60)
    async def saving(self):
        print("DEBUG: Starting save loop")
        self.server_data = loadJSON(SERVER_SETUP_PATH)
        saveJSON(self.user_votes, USER_VOTES)
        saveJSON(self.song_vote, SONG_VOTES)
        print("DEBUG: Save loop completed")
    
    @tasks.loop(hours=3)
    async def recalc(self):
        print("DEBUG: Starting scheduled recalc")
        recalculate_tierlist_from_votes()
        print("DEBUG: Scheduled recalc completed")

    @saving.before_loop
    async def before_saving(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(seconds = 60)
    async def daily(self):
        now_utc = datetime.now(timezone.utc)
        hours_minutes = now_utc.strftime("%H:%M")
        print(f"DEBUG: Daily loop running at {hours_minutes}")
        for guild_id in self.server_data:
            print(f"DEBUG: Checking guild {guild_id}")
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                print(f"DEBUG: Guild {guild_id} not found")
                continue
            else:
                if self.server_data[guild_id]["Time"] == hours_minutes and ("sent" not in self.server_data[guild_id] or self.server_data[guild_id]["sent"] != hours_minutes):
                    print(f"DEBUG: Time matches for guild {guild_id}, sending daily song")
                    channel_id = int(self.server_data[guild_id].get("Channel"))
                    channel = await self.bot.fetch_channel(channel_id)
                    completed = self.server_data[guild_id].get("completed_songs", [])
                    available = [s for s in song_database if s not in completed]
                    print(f"DEBUG: Completed songs: {len(completed)}, Available: {len(available)}")
                    if not available:
                        print("DEBUG: No available songs, resetting completed list")
                        available = song_database  # reset if all done
                        self.server_data[guild_id]["completed_songs"] = []
                    selected_song = random.choice(available)
                    print(f"DEBUG: Selected song: {selected_song}")
                    message = await self.send_embed(None, selected_song, channel_id, content=f"<@&{self.server_data[guild_id]['Role']}>")
                    self.server_data[guild_id]["completed_songs"].append(selected_song)
                    thread = await message.create_thread(
                        name=f"Tierlist Discussion: {selected_song}",
                        auto_archive_duration=1440,
                        reason="Tierlist Discussion"
                    )
                    print(f"DEBUG: Thread created: {thread.name}")
                    server_votes = loadJSON(SERVER_VOTES)
                    server_id = guild_id
                    requested_tierlist = server_votes[server_id]
                    img = tlm(requested_tierlist, SONG_JACKETS_DIR)
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
                    self.server_data[guild_id]["sent"] = hours_minutes
                    saveJSON(self.server_data, SERVER_SETUP_PATH)
                    print(f"DEBUG: Daily task completed for guild {guild_id}")
    

#-----------------------------------------------COMMANDS-----------------------------------------------#
    @app_commands.command(name="tierlistsetup", description="Configure the tierlist system for this server")
    @app_commands.describe(
        channel = "Channel where the Daily Tierlist is sent",
        time = "Time in US Pacific time to send the Tierlist (24H format eg. 18:00)",
        role = "Role to ping when Tierlist comes (Optional)"
        )
    @app_commands.checks.has_permissions(administrator=True)
    async def tierlistsetup(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role, time: str):
        print(f"DEBUG: Setting up tierlist for guild {interaction.guild.id}")
        try:
            hh, mm = map(int, time.split(":"))
            if not (0 <= hh < 24 and 0 <= mm < 60):
                raise ValueError
        except Exception:
            print(f"DEBUG: Invalid time format: {time}")
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
        setups[server_id].setdefault("completed_songs", [])
        setups[server_id]["Time"] = f"{hh:02d}:{mm:02d}"  
        saveJSON(setups, SERVER_SETUP_PATH)
        print(f"DEBUG: Setup completed for guild {server_id}")
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
    @app_commands.checks.has_permissions(administrator=True)
    async def adminforcetierlist(self, interaction: discord.Interaction):
        self.server_data = loadJSON(SERVER_SETUP_PATH)
        guild_id = interaction.guild.id
        guild_id = str(guild_id)
        channel_id = self.server_data[guild_id].get("Channel")
        channel = self.bot.get_channel(int(channel_id))
        completed = self.server_data[guild_id].get("completed_songs", [])
        available = [s for s in song_database if s not in completed]
        if not available:
            available = song_database
            self.server_data[guild_id]["completed_songs"] = []
        selected_song = random.choice(available)
        print(selected_song)
        message = await self.send_embed(interaction, selected_song, channel_id, content=f"<@&{self.server_data[guild_id]["Role"]}>")
        thread = await message.create_thread(
            name=f"Tierlist Discussion: {selected_song}",
            auto_archive_duration=1440,
            reason="Tierlist Discussion"
        )
        server_votes = loadJSON(SERVER_VOTES)
        server_id = str(interaction.guild_id)
        requested_tierlist = server_votes[server_id]
        img = tlm(requested_tierlist, SONG_JACKETS_DIR)
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
        self.server_data[guild_id]["completed_songs"].append(selected_song)
        saveJSON(self.server_data, SERVER_SETUP_PATH)
        await interaction.response.send_message(f"Forced the tierlist to advance to {selected_song}")

    @app_commands.command(
        name="adminforcespecificsong",
        description="Send a specific song in the server's configured channel (Admin only)"
    )
    @app_commands.describe(
        song = "The name of the song to send"
    )
    @app_commands.autocomplete(song=song_autocomplete)
    @app_commands.checks.has_permissions(administrator=True)
    async def adminforcespecificsong(self, interaction: discord.Interaction, song: str):
        print(f"DEBUG: Forcing specific song: {song}")
        if song not in song_database:
            print(f"DEBUG: Song {song} not found in database")
            await interaction.response.send_message(f"Song '{song}' not found in the database.", ephemeral=True)
            return
        self.server_data = loadJSON(SERVER_SETUP_PATH)
        guild_id = str(interaction.guild.id)
        if guild_id not in self.server_data:
            print(f"DEBUG: Guild {guild_id} not configured")
            await interaction.response.send_message("This server is not configured.", ephemeral=True)
            return
        channel_id = self.server_data[guild_id].get("Channel")
        if not channel_id:
            print(f"DEBUG: No channel configured for guild {guild_id}")
            await interaction.response.send_message("No channel is configured for this server.", ephemeral=True)
            return
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            print(f"DEBUG: Channel {channel_id} not found")
            await interaction.response.send_message("Configured channel not found.", ephemeral=True)
            return
        print(f"DEBUG: Sending song {song} to channel {channel_id}")
        message = await self.send_embed(None, song, channel_id, content=f"<@&{self.server_data[guild_id]['Role']}>")
        thread = await message.create_thread(
            name=f"Tierlist Discussion: {song}",
            auto_archive_duration=1440,
            reason="Tierlist Discussion"
        )
        server_votes = loadJSON(SERVER_VOTES)
        server_id = str(interaction.guild_id)
        requested_tierlist = server_votes.get(server_id, {})
        img = tlm(requested_tierlist, SONG_JACKETS_DIR)
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
        # Optionally add to completed_songs
        self.server_data[guild_id]["completed_songs"].append(song)
        saveJSON(self.server_data, SERVER_SETUP_PATH)
        await interaction.response.send_message(f"Forced the specific song '{song}' to be sent.", ephemeral=True)

    @app_commands.command(
        name="tierlistrevote",
        description="Revote for a song you missed out on"
    )
    async def revote(self, interaction: discord.Interaction):
        print("revote command triggered")
        try:
            print("interaction.guild:", interaction.guild)
            if interaction.guild is None:
                print("Guild is None (DM command)")
                await interaction.response.send_message(
                    "This command can only be used in a server.",
                    ephemeral=True
                )
                return
            guild_id = str(interaction.guild.id)
            print("guild_id:", guild_id)
            print("server_data keys:", list(self.server_data.keys()))
            completed_songs = self.server_data.get(guild_id, {}).get("completed_songs", [])
            print("completed_songs length:", len(completed_songs))
            if not completed_songs:
                print("No completed songs found")
                await interaction.response.send_message(
                    "No songs available to revote.",
                    ephemeral=True
                )
                return
            print("building options")
            options = []
            for s in completed_songs:
                print("adding option:", s)
                options.append(discord.SelectOption(label=s[:100]))
            print("splitting into pages")
            pages = [options[i:i+25] for i in range(0, len(options), 25)]
            print("number of pages:", len(pages))
            print("creating RevoteDropdown view")
            view = RevoteDropdown(pages, self)
            print("sending message")
            await interaction.response.send_message(
                "Revote Here",
                view=view,
                ephemeral=True
            )
            print("message sent successfully")
        except Exception as e:
            print("ERROR in revote command:", e)
            import traceback
            traceback.print_exc() 

    @app_commands.command(
        name="tierlistserver",
        description="Show the tierlist for the server"
    )
    async def servertierlist(self, interaction: discord.Interaction):
        print("recieved request")
        await interaction.response.defer(ephemeral=False)
        server_votes = loadJSON(SERVER_VOTES)
        server_id = str(interaction.guild_id)
        print(server_id)
        requested_tierlist = server_votes[server_id]
        img = tlm(requested_tierlist, SONG_JACKETS_DIR)
        print(requested_tierlist)
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
        await interaction.followup.send(embed=embed, file=file, ephemeral=False)

    @app_commands.command(
        name="tierlistself",
        description="Show own tierlist (please use sparingly the server might die)"
    )
    async def usertierlist(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        user_id = str(interaction.user.id)
        user_votes = loadJSON(USER_VOTES)
        server_id = str(interaction.guild_id)
        print(user_votes[server_id][user_id])
        requested_tierlist = user_votes[server_id][user_id]
        img = tlm(requested_tierlist, SONG_JACKETS_DIR)
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


    @app_commands.command(
        name = "songinfo",
        description = "Show the card for a specific song"
    )
    @app_commands.describe(
        song = "The name of the song to show the card for"
    )
    @app_commands.autocomplete(song=song_autocomplete)
    async def songinfo(self, interaction: discord.Interaction, song: str):
        print(f"DEBUG: songinfo command triggered for song {song}")
        tierlist = loadJSON(SERVER_VOTES)
        print(f"DEBUG: Loaded tierlistbyserver")
        current_tier = None
        rank = 0
        found = False
        for tier in tierlist[str(interaction.guild_id)]:
            print(f"DEBUG: Checking tier {tier} for song {song}")
            for s in tierlist[str(interaction.guild_id)][tier]:
                rank += 1
                if s == song:
                    current_tier = tier
                    found = True
                    print(f"DEBUG: Found song {song} in tier {tier}")
                    break
            if found:
                break
        if not current_tier:
            rank = "Unranked"   
            current_tier = "Unranked"
        print(f"DEBUG: User requested info for song {song} currently in tier {current_tier}")
        print(f"DEBUG: Showing card for song: {song}")
        if song not in song_database:
            print(f"DEBUG: Song {song} not found in database")
            await interaction.response.send_message(f"Song '{song}' not found in the database.", ephemeral=True)
            return
        image_path = os.path.join(ENTRIES_DIR, f"{song}.png")
        if not os.path.isfile(image_path):
            print(f"DEBUG: Image for song {song} not found at path {image_path}")
            await interaction.response.send_message(f"Image for song '{song}' not found.", ephemeral=True)
            return
        file = File(image_path, filename=f"{song}.png")
        embed = discord.Embed(
            title=song,
            color=0x4169E1
        )
        embed.set_image(url=f"attachment://{song}.png")
        embed.set_footer(text=f"Current Tier: {current_tier} (Rank {rank})", icon_url="https://i.namu.wiki/i/J4ZwMcNsF1aC5H9jpfYiKZqOhjI2ucqXytSd5zAfx-Qy6GTLXdwvW86KW_lDthZChvdwMoU4cXK9hpJhKEzYsA.webp")
        await interaction.response.send_message(embed=embed, file=file) 
        
async def setup(bot):
    await bot.add_cog(TierList(bot))



        
