import discord
import os
import random
import asyncio
from discord import app_commands
from discord.ext import commands
from mutagen.mp3 import MP3
from radio import radio_active

song_guess = False 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SONGS_FOLDER = os.path.join(BASE_DIR, "Songs")


async def song_autocomplete(interaction: discord.Interaction, current: str):
    cog: SongGuess = interaction.client.get_cog("SongGuess")
    if not cog:
        return []

    config = cog.config.get(interaction.guild_id, {})
    unit = config.get("unit")
    if not unit:
        return []

    if unit not in cog.song_cache:
        unit_path = os.path.join(SONGS_FOLDER, unit, "music")
        if not os.path.exists(unit_path):
            return []
        cog.song_cache[unit] = [
            os.path.splitext(f)[0]
            for f in os.listdir(unit_path)
            if f.lower().endswith((".mp3", ".wav", ".ogg"))
        ]

    songs = cog.song_cache[unit]
    filtered = [s for s in songs if current.lower() in s.lower()]
    return [app_commands.Choice(name=s, value=s) for s in filtered[:25]]


async def unit_autocomplete(interaction: discord.Interaction, current: str):
    if not os.path.exists(SONGS_FOLDER):
        return []
    units = [
        entry
        for entry in os.listdir(SONGS_FOLDER)
        if os.path.isdir(os.path.join(SONGS_FOLDER, entry))
    ]
    filtered = [u for u in units if current.lower() in u.lower()]
    return [app_commands.Choice(name=u, value=u) for u in filtered[:25]]


class SongGuess(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = {}
        self.active_games = {}
        self.scores = {}
        self.current_song = {}
        self.song_cache = {}

    @app_commands.command(name="guessconfig", description="Configure the Song Guess game")
    @app_commands.describe(
        time="Time limit for guessing (seconds)",
        unit="Select the unit for the songs"
    )
    @app_commands.autocomplete(unit=unit_autocomplete)
    async def songguessconfig(self, interaction: discord.Interaction, time: int, unit: str):
        self.config[interaction.guild_id] = {"time": time, "unit": unit}
        await interaction.response.send_message(
            f"Config set!\n**Unit:** {unit}\n**Time:** {time}s"
        )

    @app_commands.command(name="guesssong", description="Starts the Song Guess game in your current VC")
    async def guesssong(self, interaction: discord.Interaction):
        global song_guess
        guild_id = interaction.guild_id
        await interaction.response.defer(ephemeral=False)

        if radio_active:
            return await interaction.followup.send("Radio is active — can't start song guessing.")
        if self.active_games.get(guild_id) or song_guess:
            return await interaction.followup.send("Song Guess is already running!")

        config = self.config.get(guild_id)
        if not config:
            return await interaction.followup.send("Please run `/songguessconfig` first!")

        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.followup.send("Join a voice channel first!")

        voice_channel = interaction.user.voice.channel
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_connected():
            await voice_client.move_to(voice_channel)
        else:
            voice_client = await voice_channel.connect()

        # 👇 Get the text channel directly
        text_channel = interaction.channel

        await text_channel.send("🎵 Song Guess game started! Get ready...")

        self.active_games[guild_id] = True
        self.scores[guild_id] = {}
        song_guess = True

        while self.active_games.get(guild_id):
            await self.play_round(interaction, voice_client, text_channel)

        if voice_client.is_connected():
            await voice_client.disconnect()

        song_guess = False

    async def play_round(self, interaction, voice_client, text_channel):
        guild_id = interaction.guild_id
        config = self.config[guild_id]
        time_limit = config["time"]
        unit = config["unit"]

        music_path = os.path.join(SONGS_FOLDER, unit, "music")
        if not os.path.isdir(music_path):
            await text_channel.send("No songs found matching config.")
            self.active_games[guild_id] = False
            return

        all_songs = [
            os.path.join(music_path, f)
            for f in os.listdir(music_path)
            if f.lower().endswith(".mp3")
        ]

        if not all_songs:
            await text_channel.send("No songs found matching config.")
            self.active_games[guild_id] = False
            return

        # Pick random song
        file_path = random.choice(all_songs)
        song_name = os.path.splitext(os.path.basename(file_path))[0]
        self.current_song[guild_id] = (song_name, file_path)

        # Prepare audio slice
        audio_info = MP3(file_path)
        length = audio_info.info.length
        start_time = random.uniform(0, max(0, length - time_limit))

        source = discord.FFmpegPCMAudio(
            file_path,
            before_options=f"-ss {start_time}",
            options=f"-t {time_limit}"
        )

        if voice_client.is_playing():
            voice_client.stop()
        voice_client.play(source)

        # Create NEW embed for each new song
        embed = discord.Embed(
            title="🎵 Guess the Song!",
            description=f"Time Remaining: **{time_limit}** seconds",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Use /guess <song name> to answer!")
        message = await text_channel.send(embed=embed)

        # Countdown updates (edits only this round’s message)
        for t in range(time_limit, 0, -1):
            if not self.active_games.get(guild_id):
                return
            embed.description = f"Time Remaining: **{t}** seconds"
            await message.edit(embed=embed)
            await asyncio.sleep(1)

        voice_client.stop()

        # Build scoreboard
        score_lines = []
        for uid, (correct, total) in self.scores.get(guild_id, {}).items():
            user = interaction.guild.get_member(uid)
            if user:
                accuracy = correct / total if total else 0
                score_lines.append(f"**{user.display_name}** — {correct}/{total} ({accuracy:.0%})")

        scoreboard = "\n".join(score_lines) if score_lines else "No guesses yet!"

        reveal = discord.Embed(
            title="⏰ Time's Up!",
            description=f"The song was **{song_name}**!\n\n**Standings:**\n{scoreboard}",
            color=discord.Color.green()
        )
        await text_channel.send(embed=reveal)
        await asyncio.sleep(5)


    @app_commands.command(name="guess", description="Make a guess for the current song.")
    @app_commands.autocomplete(song=song_autocomplete)
    async def guess(self, interaction: discord.Interaction, song: str):
        guild_id = interaction.guild_id
        current = self.current_song.get(guild_id)

        if not self.active_games.get(guild_id):
            return await interaction.response.send_message("No active song to guess right now.", ephemeral=True)
        if not current:
            return await interaction.response.send_message("Song not yet selected.", ephemeral=True)

        song_name, _ = current
        user_id = interaction.user.id
        self.scores.setdefault(guild_id, {}).setdefault(user_id, [0, 0])
        self.scores[guild_id][user_id][1] += 1

        if song.lower() == song_name.lower():
            self.scores[guild_id][user_id][0] += 1
            await interaction.response.send_message("✅ Correct guess!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Wrong guess!", ephemeral=True)

    @app_commands.command(name="guessend", description="End the Song Guess game.")
    async def songguessend(self, interaction: discord.Interaction):
        global song_guess
        guild_id = interaction.guild_id
        if not self.active_games.get(guild_id):
            return await interaction.response.send_message("No active game running.")

        self.active_games[guild_id] = False
        self.current_song.pop(guild_id, None)
        self.scores.pop(guild_id, None)

        vc = interaction.guild.voice_client
        if vc and vc.is_connected():
            vc.stop()
            await vc.disconnect()

        song_guess = False 
        await interaction.response.send_message("Song Guess game ended and scores reset.")


async def setup(bot: commands.Bot):
    await bot.add_cog(SongGuess(bot))
