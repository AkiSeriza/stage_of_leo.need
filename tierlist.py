import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import csv
from pathlib import Path
from datetime import datetime, time, timedelta
from typing import Dict, List
import pytz

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "Databases" / "Tierlist"
SONG_LIST_PATH = DB_DIR / "songslist.json"
SONG_SCORES_PATH = DB_DIR / "songscores.json"
SERVER_SETUP_PATH = DB_DIR / "serversetups.json"
VOTES_PATH = DB_DIR / "votes.json"
ACTIVE_VOTES_PATH = DB_DIR / "activevotes.json"


role_event = ""

def ensure_vote_file():
    if not VOTES_PATH.exists():
        VOTES_PATH.write_text("{}")

def load_votes():
    return load_json(VOTES_PATH)

def save_votes(data):
    save_json(VOTES_PATH, data)

DEFAULT_THRESHOLDS = {
    "S+": 7.0,
    "S": 6.0,
    "A": 5.0,
    "B": 4.0,
    "C": 3.0,
    "D": 0.0,
}

DEFAULT_SCORES = {
    "S+": 7,
    "S": 6,
    "A": 5,
    "B": 4,
    "C": 3,
    "D": 1,
}

def ensure_dirs():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    if not SONG_LIST_PATH.exists():
        SONG_LIST_PATH.write_text("{}")
    if not SONG_SCORES_PATH.exists():
        SONG_SCORES_PATH.write_text("{}")
    if not SERVER_SETUP_PATH.exists():
        SERVER_SETUP_PATH.write_text("{}")
    if not VOTES_PATH.exists():
        VOTES_PATH.write_text("{}") 
    if not ACTIVE_VOTES_PATH.exists():
        ACTIVE_VOTES_PATH.write_text("{}")

def load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

_active_vote_state: Dict[int, Dict[int, str]] = {}
_active_vote_message_song: Dict[int, str] = {}

class TierVoteView(discord.ui.View):
    def __init__(self, bot: commands.Bot, song_key: str, server_id: int, score_map: Dict[str,int]):
        super().__init__(timeout=None)
        self.bot = bot
        self.song_key = song_key
        self.server_id = str(server_id)
        self.score_map = score_map

        for label in ["S+", "S", "A", "B", "C", "D"]:
            self.add_item(TierButton(label, self))

class TierButton(discord.ui.Button):
    def __init__(self, label: str, view: TierVoteView):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.tier_view = view

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        msg_id = interaction.message.id
        song_key = self.tier_view.song_key
        server_id = str(self.tier_view.server_id)
        choice = self.label

        voters = _active_vote_state.setdefault(msg_id, {})
        prev_choice = voters.get(user_id)

        votes_data = load_votes()
        votes_data.setdefault(song_key, {}).setdefault(server_id, {})

        if prev_choice == choice:
            del voters[user_id]
            update_score_for_song(song_key, server_id, -self.tier_view.score_map[choice], -1)
            votes_data[song_key][server_id].pop(user_id, None)
            save_votes(votes_data)
            await interaction.response.send_message(f"Removed your vote ({choice}) for {song_key}", ephemeral=True)
            return

        if prev_choice:
            update_score_for_song(song_key, server_id, -self.tier_view.score_map[prev_choice], -1)

        voters[user_id] = choice
        update_score_for_song(song_key, server_id, self.tier_view.score_map[choice], 1)

        votes_data[song_key][server_id][user_id] = choice
        save_votes(votes_data)

        await interaction.response.send_message(f"Registered your vote ({choice}) for {song_key}", ephemeral=True)



def update_score_for_song(song_key: str, server_id: str, delta_score: int, delta_votes: int):
    data = load_json(SONG_SCORES_PATH)
    if song_key not in data:
        data[song_key] = {}
    server_scores = data[song_key].get(server_id, [0,0])
    server_scores[0] = int(server_scores[0]) + int(delta_score)
    server_scores[1] = int(server_scores[1]) + int(delta_votes)
    if server_scores[1] < 0:
        server_scores[1] = 0
    if server_scores[0] < 0:
        server_scores[0] = 0
    data[song_key][server_id] = server_scores
    save_json(SONG_SCORES_PATH, data)
    write_server_scores_csv(server_id, data)

def write_server_scores_csv(server_id: str, full_scores_data=None):
    if full_scores_data is None:
        full_scores_data = load_json(SONG_SCORES_PATH)
    server_dir = DB_DIR / server_id
    server_dir.mkdir(parents=True, exist_ok=True)
    csv_path = server_dir / "scores.csv"
    csv_lines = ["name,total_score,votes,average"]
    for song, servers in full_scores_data.items():
        if server_id in servers:
            total, votes = servers[server_id]
            avg = (total / votes) if votes>0 else 0
            csv_lines.append(f"{song},{total},{votes},{avg:.3f}")
    csv_path.write_text("\n".join(csv_lines), encoding='utf-8')

def assign_tiers_for_server(server_id: str, thresholds: Dict[str,float]=None):
    thresholds = thresholds or DEFAULT_THRESHOLDS
    full_scores = load_json(SONG_SCORES_PATH)
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

def write_tier_csv(server_id: str, tiers: Dict[str,List[Dict]]):
    server_dir = DB_DIR / server_id
    server_dir.mkdir(parents=True, exist_ok=True)
    csv_path = server_dir / "tier.csv"
    csv_lines = ["Tier,Name,Average,Total,Votes"]
    for tier in ["S+","S","A","B","C","D"]:
        entries = tiers.get(tier, [])
        for e in entries:
            csv_lines.append(f"{tier},{e['name']},{e['avg']:.3f},{e['total']},{e['votes']}")
    csv_path.write_text("\n".join(csv_lines), encoding='utf-8')

def get_next_song_for_server(server_id: str):
    setups = load_json(SERVER_SETUP_PATH)
    setups.setdefault(server_id, {})
    cfg = setups[server_id]
    idx = cfg.get("index", 0)
    songs = list(load_json(SONG_LIST_PATH).keys())
    if not songs:
        return None
    song_key = songs[idx % len(songs)]
    cfg["index"] = (idx + 1) % len(songs)
    setups[server_id] = cfg
    save_json(SERVER_SETUP_PATH, setups)
    return song_key

class TierListCog(commands.Cog):
    @tasks.loop(minutes=10.0)
    async def check_expired_votes(self):
        pacific_tz = pytz.timezone('America/Los_Angeles')
        active_votes = load_json(ACTIVE_VOTES_PATH)
        now = datetime.now(pacific_tz)
        to_remove = []
        for msg_id, info in list(active_votes.items()):
            try:
                ts = info.get("timestamp")
                if not ts:
                    to_remove.append(msg_id)
                    continue
                timestamp = datetime.fromisoformat(ts)
                if timestamp.tzinfo is None:
                    timestamp = pacific_tz.localize(timestamp)
                else:
                    timestamp = timestamp.astimezone(pacific_tz)

                if (now - timestamp) > timedelta(days=1):
                    server_id = int(info.get("server_id", 0))
                    msg_id_int = int(msg_id)
                    channel = None
                    setups = load_json(SERVER_SETUP_PATH)
                    if str(server_id) in setups:
                        channel_id = setups[str(server_id)].get("Channel")
                        if channel_id:
                            channel = self.bot.get_channel(int(channel_id))

                    if channel:
                        try:
                            msg = await channel.fetch_message(msg_id_int)
                            await msg.delete()
                        except discord.NotFound:
                            pass

                    to_remove.append(msg_id)
            except Exception as e:
                print("Error checking expired vote:", e)
                to_remove.append(msg_id)

        for msg_id in to_remove:
            active_votes.pop(msg_id, None)
        if to_remove:
            save_json(ACTIVE_VOTES_PATH, active_votes)

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        ensure_dirs()
        self.check_schedule.start()
        self.midnight_task.start()
        try:
            self.check_expired_votes.start()
        except RuntimeError:
            pass

    def cog_unload(self):
        self.check_schedule.cancel()
        self.midnight_task.cancel()
        try:
            self.check_expired_votes.cancel()
        except Exception:
            pass

    @tasks.loop(seconds=60.0)
    async def check_schedule(self):
        pacific_tz = pytz.timezone('America/Los_Angeles')
        now_pacific = datetime.now(pacific_tz)
        hhmm = now_pacific.strftime("%H:%M")
        pacific_date = now_pacific.strftime("%Y-%m-%d")
        setups = load_json(SERVER_SETUP_PATH)
        for sid, cfg in setups.items():
            channel_id = cfg.get("Channel")
            send_time = cfg.get("Time")
            last_sent = cfg.get("last_sent")
            role = cfg.get("Role")
            if not channel_id or not send_time:
                continue
            if send_time == hhmm and last_sent != pacific_date:
                try:
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        song_key = get_next_song_for_server(str(sid))
                        if song_key:
                            await self.send_song_embed(channel, song_key, int(sid),role)
                            setups[sid]["last_sent"] = pacific_date
                            save_json(SERVER_SETUP_PATH, setups)
                except Exception as e:
                    print("Error sending scheduled song:", e)


    @tasks.loop(time=time(hour=0, minute=0, tzinfo=pytz.timezone('America/Los_Angeles')))
    async def midnight_task(self):
        print("Running midnight tier assignment")
        setups = load_json(SERVER_SETUP_PATH)
        for sid, cfg in setups.items():
            thresholds = cfg.get("Thresholds", DEFAULT_THRESHOLDS)
            assign_tiers_for_server(str(sid), thresholds)

    @midnight_task.before_loop
    async def before_midnight(self):
        await self.bot.wait_until_ready()

    @check_schedule.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @check_expired_votes.before_loop
    async def before_check_expired(self):
        await self.bot.wait_until_ready()

    async def send_song_embed(self, channel: discord.abc.Messageable, song_key: str, server_id: int, mention_role: int):
        songs = load_json(SONG_LIST_PATH)
        song = songs.get(song_key, {})
        if mention_role:
            await channel.send(
                f"<@&{mention_role}> Daily Tierlist is here!",
                allowed_mentions=discord.AllowedMentions(roles=True)
            )

        embed = discord.Embed(
            title=song_key,
            description=song.get("Commission", ""),
            color=0x4169E1
        )

        if song.get("link"):
            embed.set_thumbnail(url=song.get("link"))

        fields = [
            ("**Arranger**", song.get("Arranger", "-")),
            ("**Composer**", song.get("Composer", "-")),
            ("**Lyricist**", song.get("Lyricist", "-")),
            ("**JP Release**", song.get("JP Release", "-")),
        ]
        for name, val in fields:
            embed.add_field(name=name, value=val, inline=True)

        setups = load_json(SERVER_SETUP_PATH)
        cfg = setups.get(str(server_id), {})
        score_map = cfg.get("ScoreMap", DEFAULT_SCORES)
        view = TierVoteView(self.bot, song_key, server_id, score_map)

        msg = await channel.send(embed=embed, view=view)

        _active_vote_state[msg.id] = {}
        _active_vote_message_song[msg.id] = song_key

        active_votes = load_json(ACTIVE_VOTES_PATH)
        pacific_tz = pytz.timezone('America/Los_Angeles')
        active_votes[str(msg.id)] = {
            "server_id": str(server_id),
            "song_key": song_key,
            "timestamp": datetime.now(pacific_tz).isoformat()
        }
        save_json(ACTIVE_VOTES_PATH, active_votes)

    @app_commands.command(name="tierlist", description="Show the server's current tier list")
    async def slash_tierlist(self, interaction: discord.Interaction):
        setups = load_json(SERVER_SETUP_PATH)
        sid = str(interaction.guild.id)
        server_dir = DB_DIR / sid
        tier_csv = server_dir / "tier.csv"
        if not tier_csv.exists():
            await interaction.response.send_message("No tier list found for this server. Make sure setup is complete.", ephemeral=True)
            return

        out_lines = []
        with open(tier_csv, newline='', encoding='utf-8') as f:
            csv_reader = csv.reader(f)
            next(csv_reader, None)  # Skip header row
            current_tier = None
            for tier, name, avg, total, votes in csv_reader:
                if tier != current_tier:
                    out_lines.append(f"\n**{tier} Tier**")
                    current_tier = tier
                out_lines.append(f"- {name} ({float(avg):.2f} avg, {votes} votes)")

        text = "\n".join(out_lines)
        await interaction.response.send_message(text if text.strip() else "(empty tier list)", ephemeral=True)


    @app_commands.command(name="tierlistsetup", description="Configure the tierlist system for this server (Pacific Time)")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_setup(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role, time_pacific: str):
        try:
            hh, mm = time_pacific.split(":")
            hh = int(hh); mm = int(mm)
            assert 0 <= hh < 24 and 0 <= mm < 60
        except Exception:
            await interaction.response.send_message("Time must be in HH:MM 24-hour Pacific time format.", ephemeral=True)
            return
        setups = load_json(SERVER_SETUP_PATH)
        sid = str(interaction.guild.id)
        setups.setdefault(sid, {})
        setups[sid]["Channel"] = str(channel.id)
        setups[sid]["Role"] = str(role.id)
        setups[sid]["Time"] = f"{hh:02d}:{mm:02d}"
        setups[sid].setdefault("index", 0)
        setups[sid].setdefault("Thresholds", DEFAULT_THRESHOLDS)
        setups[sid].setdefault("ScoreMap", DEFAULT_SCORES)
        save_json(SERVER_SETUP_PATH, setups)
        await interaction.response.send_message(f"Tierlist scheduled to post daily at {hh:02d}:{mm:02d} Pacific Time in {channel.mention}")

    @app_commands.command(name="forceupdate", description="Force an immediate update of the server's tier list.")
    @app_commands.checks.has_permissions(administrator=True)
    async def force_update(self, interaction: discord.Interaction):
        sid = interaction.guild_id
        if not sid:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return
        sid_str = str(sid)
        setups = load_json(SERVER_SETUP_PATH)
        cfg = setups.get(sid_str, {})
        if not cfg:
            await interaction.response.send_message("This server is not configured. Use /tierlist_setup first.", ephemeral=True)
            return
        try:
            thresholds = cfg.get("Thresholds", DEFAULT_THRESHOLDS)
            assign_tiers_for_server(sid_str, thresholds)
            await interaction.response.send_message("✅ Tier list has been updated. Use /tierlist to see the changes.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error updating tier list: {str(e)}", ephemeral=True)

    @app_commands.command(name="forcedailypost", description="Force the next daily tierlist post to send immediately and advance the list.")
    @app_commands.checks.has_permissions(administrator=True)
    async def force_daily_post(self, interaction: discord.Interaction):
        sid = interaction.guild_id
        if not sid:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        sid_str = str(sid)
        setups = load_json(SERVER_SETUP_PATH)
        cfg = setups.get(sid_str, {})

        channel_id = cfg.get("Channel")
        role_id = cfg.get("Role")
        if not channel_id or not role_id:
            await interaction.response.send_message(
                "No channel or role configured for this server. Use `/tierlistsetup` first.",
                ephemeral=True
            )
            return

        # get the next song
        song_key = get_next_song_for_server(sid_str)
        if not song_key:
            await interaction.response.send_message("No songs available to post.", ephemeral=True)
            return

        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message("Configured channel not found.", ephemeral=True)
            return

        # Post the embed with the role mention
        await self.send_song_embed(channel, song_key, int(sid_str), int(role_id))

        # Mark that today's post has been sent
        pacific_tz = pytz.timezone('America/Los_Angeles')
        pacific_date = datetime.now(pacific_tz).strftime("%Y-%m-%d")

        setups.setdefault(sid_str, {})
        setups[sid_str]["last_sent"] = pacific_date
        setups[sid_str]["index"] = setups[sid_str].get("index", 0) + 1
        save_json(SERVER_SETUP_PATH, setups)

        await interaction.response.send_message(
            f"✅ Forced daily post executed and advanced to the next song ({song_key}).",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TierListCog(bot))

