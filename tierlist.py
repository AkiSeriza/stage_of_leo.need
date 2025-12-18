import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import math
##from tierlistgen import tierlistmake as tlm
import os
from typing import Dict, List
import pytz
from datetime import datetime
from discord import File


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
        print(write_file)
    saveJSON(write_file,SERVER_VOTES)

#-----------------------------------------------VIEWS-----------------------------------------------#
class TierlistButtons(discord.ui.View):
    def __init__(self, selected_song, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.selected_song = selected_song
        for tier in standard_tiers:
            button = discord.ui.Button(label=tier, style=discord.ButtonStyle.primary)
            async def button_callback(interaction: discord.Interaction, tier=tier):
                user_votes = cog.user_votes.get(interaction.guild.id, {}).get(interaction.user.id, {})
                sss_votes = user_votes.get("SSS", [])
                if tier == "SSS" and len(sss_votes) >= 3:
                    await interaction.response.send_message(f"You already have 3 Votes of SSS", ephemeral=True)
                    return 0
                self.cog.register_vote(interaction.user.id, interaction.guild.id, self.selected_song, tier)
                await interaction.response.send_message(f"You voted {tier} for {self.selected_song}!", ephemeral=True)
                recalculate_tierlist_from_votes()
            button.callback = button_callback
            self.add_item(button)

#-----------------------------------------------BOT INITIALIZE-----------------------------------------------#
class TierList(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot    
        self.user_votes = loadJSON(USER_VOTES)
        self.song_vote = loadJSON(SONG_VOTES)
        self.song_list = loadJSON(SONG_LIST_PATH)
        self.server_data = loadJSON(SERVER_SETUP_PATH)
        self.saving.start() 
        self.recalc.start()

#-----------------------------------------------METHODS-----------------------------------------------#
    def register_vote(self, user, server, song, vote):
        if song not in self.song_vote:
            self.song_vote[song] = {}
        if server not in self.song_vote[song]:
            self.song_vote[song][server] = {}
        if server not in self.user_votes:
            self.user_votes[server] = {}
        if user not in self.user_votes[server]:
            self.user_votes[server][user] = {}
        for tier, songs in list(self.user_votes[server][user].items()):
            if song in songs:
                songs.remove(song)
                if not songs:
                    del self.user_votes[server][user][tier]
                if self.song_vote.get(song, {}).get(server, {}).get(user):
                    del self.song_vote[song][server][user]
        self.song_vote[song][server][user] = vote
        if vote not in self.user_votes[server][user]:
            self.user_votes[server][user][vote] = []
        self.user_votes[server][user][vote].append(song)
        return True


    def remove_vote(self, user, server, song):
        if server in self.user_votes and user in self.user_votes[server]:
            for tier in list(self.user_votes[server][user].keys()):
                if song in self.user_votes[server][user][tier]:
                    self.user_votes[server][user][tier].remove(song)
                    if not self.user_votes[server][user][tier]:
                        del self.user_votes[server][user][tier]
        if song in self.song_vote and server in self.song_vote[song]:
            self.song_vote[song][server].pop(user, None)
    
    def tierlistembed(selected_song):
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

#-----------------------------------------------LOOPS-----------------------------------------------#

    @tasks.loop(minutes=15)
    async def saving(self):
        saveJSON(self.user_votes, USER_VOTES)
        saveJSON(self.song_vote, SONG_VOTES)
    
    @tasks.loop(hours=3)
    async def recalc(self):
        recalculate_tierlist_from_votes()

    @saving.before_loop
    async def before_saving(self):
        await self.bot.wait_until_ready()
    
#-----------------------------------------------COMMANDS-----------------------------------------------#
    @app_commands.command(
        name="adminforcetierlist",
        description="Send the next song in the server's configured channel"
    )
    async def adminforcetierlist(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        print("recieved")
        if guild_id not in self.server_data:
            await interaction.response.send_message("This server is not configured.", ephemeral=True)
            return

        server_info = self.server_data[guild_id]
        channel_id = server_info.get("Channel")
        index = server_info.get("index", 0)
        print("recieved data")
        if not channel_id:
            await interaction.response.send_message("No channel is configured for this server.", ephemeral=True)
            return

        song_names = list(self.song_list.keys())
        if index >= len(song_names):
            await interaction.response.send_message("All songs have already been sent!", ephemeral=True)
            return

        selected_song = song_names[index]
        embed = TierList.tierlistembed(selected_song)  # Your embed method

        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message("Configured channel not found.", ephemeral=True)
            return
        view = TierlistButtons(selected_song,self)
        await channel.send(embed=embed, view=view)

        # Increment the index and save back
        self.server_data[guild_id]["index"] = index + 1
        saveJSON(self.server_data, SERVER_SETUP_PATH)

        await interaction.response.send_message(
            f"Sent **{selected_song}** in <#{channel_id}>!", ephemeral=True
        )
                
async def setup(bot):
    await bot.add_cog(TierList(bot))



        
