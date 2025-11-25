import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
from tierlistgen import tierlistmake as tlm
import os
from typing import Dict, List
import pytz
from datetime import datetime
from discord import File

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "Databases", "Tierlist")
SONG_LIST_PATH = os.path.join(DB_DIR, "songslist.json")
SERVER_SETUP_PATH = os.path.join(DB_DIR, "serversetups.json")
VOTES_PATH = os.path.join(DB_DIR, "votes.json")
SONGSCORES_PATH = os.path.join(DB_DIR, "songscores.json")
PHOTO_FOLDER = os.path.join(BASE_DIR, "Databases", "Photos")
REVOTES_PATH = os.path.join(DB_DIR, "revotes.json")

def load_revotes():
    return load_json(REVOTES_PATH)

def save_revotes(data):
    save_json(REVOTES_PATH, data)

Standard_score = {
    "Thresholds": {"S+": 7.0, "S": 6.0, "A": 5.0, "B": 4.0, "C": 3.0, "D": 0.0},
    "ScoreMap": {"S+": 10, "S": 7, "A": 5, "B": 4, "C": 2, "D": 1}
}

def write_tier_csv(server_id: str, tiers: Dict[str, List[Dict]]):
    server_dir = os.path.join(DB_DIR, str(server_id))
    os.makedirs(server_dir, exist_ok=True)
    csv_path = os.path.join(server_dir, "tier.csv")
    lines = ["Tier,Name,Average,Total,Votes"]
    for tier in ["S+", "S", "A", "B", "C", "D"]:
        for e in tiers.get(tier, []):
            lines.append(f"{tier},{e['name']},{e['avg']:.3f},{e['total']},{e['votes']}")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def assign_tiers_for_server(server_id: str, thresholds: Dict[str,float]=None):
    thresholds = thresholds or Standard_score["Thresholds"]
    full_scores = load_json(SONGSCORES_PATH)
    song_list = []
    for song, servers in full_scores.items():
        if server_id in servers:
            total, votes = servers[server_id]
            avg = (total / votes) if votes>0 else 0
            song_list.append((song, avg, total, votes))
    song_list.sort(key=lambda x: (x[1], x[3], x[0]), reverse=True)
    n = len(song_list)
    tiers = {"S+":[], "S":[], "A":[], "B":[], "C":[], "D":[]}
    if n == 0:
        write_tier_csv(server_id, tiers)
        return tiers
    idx = 0
    def pop_slice(k):
        nonlocal idx
        slice_items = song_list[idx:idx+k]
        idx += k
        return slice_items
    s_plus_slice = pop_slice(min(3, n))
    s_slice = pop_slice(min(5, max(0, n-idx)))
    a_slice = pop_slice(min(10, max(0, n-idx)))
    remaining = song_list[idx:]
    rem_n = len(remaining)
    b_count = int(rem_n * 0.5)
    b_slice = remaining[:b_count]
    c_count = int(rem_n * 0.4)
    c_slice = remaining[b_count:b_count+c_count]
    d_slice = remaining[b_count+c_count:]
    def add_if_meets(slice_items, tier_name):
        for song, avg, total, votes in slice_items:
            if avg >= thresholds.get(tier_name, 0):
                tiers[tier_name].append({"name":song, "avg":avg, "total":total, "votes":votes})
            else:
                lower_order = ["S+","S","A","B","C","D"]
                i = lower_order.index(tier_name)
                placed = False
                for j in range(i+1, len(lower_order)):
                    lower = lower_order[j]
                    if avg >= thresholds.get(lower, 0):
                        tiers[lower].append({"name":song, "avg":avg, "total":total, "votes":votes})
                        placed = True
                        break
                if not placed:
                    tiers["D"].append({"name":song, "avg":avg, "total":total, "votes":votes})
    add_if_meets(s_plus_slice, "S+")
    add_if_meets(s_slice, "S")
    add_if_meets(a_slice, "A")
    add_if_meets(b_slice, "B")
    add_if_meets(c_slice, "C")
    add_if_meets(d_slice, "D")
    write_tier_csv(server_id, tiers)
    return tiers

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        
def tierlistembed(selected_song):
    song_dict = load_json(SONG_LIST_PATH)
    song = song_dict[selected_song]
    embed = discord.Embed(
        title=selected_song,
        description=f"[{song.get('eng', 'No English title')}]({song.get('yt', '')})",
        color=0x4169E1
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


class RevoteSelect(discord.ui.Select):
    def __init__(self, all_songs, server_id, score_map):
        song_list = load_json(SONG_LIST_PATH)
        votes_data = load_json(VOTES_PATH)
        server_id_str = str(server_id)

        # Only keep songs that have votes in this server
        filtered_songs = [
            song for song in all_songs
            if votes_data.get(song, {}).get(server_id_str)
        ]

        options = []
        for song in filtered_songs:
            desc = song_list.get(song, {}).get("Commission", "-")
            if len(desc) > 96:
                desc = desc[:96] + "..."
            options.append(discord.SelectOption(label=song, description=desc))

        super().__init__(placeholder="Select a song to revote...", min_values=1, max_values=1, options=options)
        self.server_id = server_id
        self.score_map = score_map

    async def callback(self, interaction: discord.Interaction):
        selected_song = self.values[0]
        self.view.clear_items()
        await interaction.response.edit_message(
            content=f"You selected **{selected_song}**. Cast your vote below:",
            embed=tierlistembed(selected_song),
            view=TierVoteView(selected_song, self.server_id, self.score_map)
        )

class RevoteView(discord.ui.View):
    def __init__(self, all_songs, server_id, score_map):
        super().__init__(timeout=120)
        self.add_item(RevoteSelect(all_songs, server_id, score_map))

class TierButton(discord.ui.Button):
    def __init__(self, song, server_id, tier, score_map):
        super().__init__(label=tier, style=discord.ButtonStyle.primary)
        self.song = song
        self.server_id = str(server_id)
        self.tier = tier
        self.score_map = score_map

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        votes = load_json(VOTES_PATH)
        votes.setdefault(self.song, {}).setdefault(self.server_id, {})
        prev_vote = votes[self.song][self.server_id].get(user_id)
        votes[self.song][self.server_id][user_id] = self.tier
        save_json(VOTES_PATH, votes)

        songscores = load_json(SONGSCORES_PATH)
        songscores.setdefault(self.song, {}).setdefault(self.server_id, [0, 0])
        if prev_vote:
            songscores[self.song][self.server_id][0] -= self.score_map.get(prev_vote, 0)
            songscores[self.song][self.server_id][1] -= 1
        songscores[self.song][self.server_id][0] += self.score_map[self.tier]
        songscores[self.song][self.server_id][1] += 1
        save_json(SONGSCORES_PATH, songscores)

        await interaction.response.send_message(
            f"Your vote ({self.tier}) for **{self.song}** has been recorded.",
            ephemeral=True
        )

class TierVoteView(discord.ui.View):
    def __init__(self, song, server_id, score_map):
        super().__init__(timeout=None)
        for tier in score_map:
            self.add_item(TierButton(song, server_id, tier, score_map))

def get_next_song(server_id):
    server_id = str(server_id)
    data = load_json(SERVER_SETUP_PATH)
    current_index = data[server_id]["index"]
    songs = list(load_json(SONG_LIST_PATH).keys())
    data[server_id]["index"] += 1
    save_json(SERVER_SETUP_PATH, data)
    return songs[current_index % len(songs)]

class TierList(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_tierlist_task.start()

    @app_commands.command(name="tierlistsetup", description="Configure the tierlist system for this server")
    @app_commands.describe(
        channel = "Channel where the Daily Tierlist is sent",
        time = "Time in US Pacific time to send the Tierlist (24H format eg. 1800)",
        role = "Role to ping when Tierlist comes (Optional)"
        )
    @app_commands.checks.has_permissions(administrator=True)
    async def tierlistsetup(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role, time: str):
        """
        time_pacific: string in HH:MM 24-hour Pacific time
        """
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
        setups = load_json(SERVER_SETUP_PATH)
        setups.setdefault(server_id, {})
        setups[server_id]["Channel"] = str(channel.id)
        setups[server_id]["Role"] = str(role.id)
        setups[server_id].setdefault("ScoreMap", Standard_score["ScoreMap"])
        setups[server_id].setdefault("Thresholds", Standard_score["Thresholds"])
        setups[server_id].setdefault("index", 0)
        setups[server_id]["Time"] = f"{hh:02d}:{mm:02d}"  
        save_json(SERVER_SETUP_PATH, setups)
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

    @app_commands.command(name="tierlistshow", description="Show the server's current tier list")
    async def tierlistshow(self, interaction: discord.Interaction):
        server_id = str(interaction.guild_id)
        await interaction.response.defer(thinking=True)
        server_setups = load_json(SERVER_SETUP_PATH).get(server_id, {})
        thresholds = server_setups.get("Thresholds", Standard_score["Thresholds"])
        assign_tiers_for_server(server_id, thresholds)
        server_dir = os.path.join(DB_DIR, server_id)
        tier_csv = os.path.join(server_dir, "tier.csv")
        if not os.path.exists(tier_csv):
            await interaction.response.send_message(
                "No tierlist CSV found. Wait for some votes or force a post.",
                ephemeral=True
            )
            return
        print("hi")
        img = tlm(tier_csv, SONG_LIST_PATH)
        img_path = os.path.join(server_dir, "tierlist.png")
        img.save(img_path)
        """await interaction.followup.send(file=discord.File(img_path))"""
        embed = discord.Embed(
            color=0x4169E1,
            title=f"{interaction.guild}'s Tierlist"
        )

        img_path = os.path.join(server_dir, "tierlist.png")
        img.save(img_path)
        file = File(img_path, filename="tierlist.png")
        embed.set_image(url="attachment://tierlist.png") 
        embed.set_footer(text="Use /tierlistrevote to vote on a previously voted song!", icon_url="https://i.namu.wiki/i/J4ZwMcNsF1aC5H9jpfYiKZqOhjI2ucqXytSd5zAfx-Qy6GTLXdwvW86KW_lDthZChvdwMoU4cXK9hpJhKEzYsA.webp")
        await interaction.followup.send(embed=embed, file=file)

    @app_commands.command(name="admintierlistforce", description="Send today's tierlist song manually")
    @app_commands.checks.has_permissions(administrator=True)
    async def tierlistforce(self, interaction: discord.Interaction):
        server_id = str(interaction.guild_id)
        next_song = get_next_song(server_id)
        server_data = load_json(SERVER_SETUP_PATH)[server_id]
        channel = self.bot.get_channel(int(server_data["Channel"]))

        await channel.send(f"<@&{server_data['Role']}>")
        view = TierVoteView(next_song, server_id, server_data["ScoreMap"])
        message = await channel.send(embed=tierlistembed(next_song), view=view)
        thread = await message.create_thread(
            name=f"Tierlist Discussion: {next_song}",
            auto_archive_duration=1440,
            reason="Tierlist Discussion"
        )
        await interaction.response.send_message(f"Forced tierlist to advance to {next_song}", ephemeral=True)

    @app_commands.command(name="tierlistrevote", description="Vote on any song")
    async def tierlistrevote(self, interaction: discord.Interaction):
        server_id = str(interaction.guild_id)
        server_data = load_json(SERVER_SETUP_PATH).get(server_id, {})
        score_map = server_data.get("ScoreMap", Standard_score["ScoreMap"])
        votes_data = load_json(VOTES_PATH)
        all_songs_with_votes = [
            song for song, servers in votes_data.items()
            if server_id in servers and bool(servers[server_id])  
        ]

        if not all_songs_with_votes:
            await interaction.response.send_message(
                "No songs have votes yet in this server, so revoting is not possible.",
                ephemeral=True
            )
            return

        view = RevoteView(all_songs_with_votes, server_id, score_map)
        await interaction.response.send_message(
            "Select a song to revote and see its info:",
            view=view,
            ephemeral=True
        )


    @tasks.loop(seconds=5)
    async def daily_tierlist_task(self):
        setups = load_json(SERVER_SETUP_PATH)
        pacific_tz = pytz.timezone("US/Pacific")
        now = datetime.now(pacific_tz)
        current_time_str = now.strftime("%H:%M")

        for server_id, server_data in setups.items():
            scheduled_time = server_data.get("Time")
            if not scheduled_time:
                continue 
            if current_time_str != scheduled_time:
                continue

            channel_id = int(server_data.get("Channel"))
            role_id = int(server_data.get("Role", 0))
            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue 

            next_song = get_next_song(server_id)
            view = TierVoteView(next_song, server_id, server_data["ScoreMap"])

            ping_text = f"<@&{role_id}>" if role_id else ""
            await channel.send(ping_text)
            message = await channel.send(embed=tierlistembed(next_song), view=view)
            thread = await message.create_thread(
                name=f"Tierlist Discussion: {next_song}",
                auto_archive_duration=1440,
                reason="Tierlist Discussion"
            )

    @daily_tierlist_task.before_loop
    async def before_daily_tierlist(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(TierList(bot))
