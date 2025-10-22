import os
import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands


SONGS_FOLDER = "Songs"
QUEUE_LIMIT = 5


queue = [] 
played_songs = []  
loop_enabled = False

async def unit_autocomplete(interaction: discord.Interaction, current: str):
    if not os.path.exists(SONGS_FOLDER):
        return []
    units = [
        entry for entry in os.listdir(SONGS_FOLDER)
        if os.path.isdir(os.path.join(SONGS_FOLDER, entry))
    ]
    filtered = [u for u in units if current.lower() in u.lower()]
    return [app_commands.Choice(name=u, value=u) for u in filtered[:25]]


async def song_autocomplete(interaction: discord.Interaction, current: str):
    unit = getattr(interaction.namespace, "unit", "LeoNeed") or "LeoNeed"
    unit_path = os.path.join(SONGS_FOLDER, unit, "music")
    if not os.path.exists(unit_path):
        return []
    songs = [
        os.path.splitext(f)[0] for f in os.listdir(unit_path)
        if f.lower().endswith((".mp3", ".wav", ".ogg"))
    ]
    filtered = [s for s in songs if current.lower() in s.lower()]
    return [app_commands.Choice(name=s, value=s) for s in filtered[:25]]


async def type_autocomplete(interaction: discord.Interaction, current: str):
    options = ["Normal", "Instrumental", "Vocals Only"]
    unit = getattr(interaction.namespace, "unit", None)
    song = getattr(interaction.namespace, "song", None)

    if unit and song:
        alt_path = os.path.join(SONGS_FOLDER, unit, "alt")
        if os.path.isdir(alt_path):
            for file in os.listdir(alt_path):
                filename, _ = os.path.splitext(file)
                if song.lower() in filename.lower():
                    alt_name = filename.replace(song, "").strip(" -_()")
                    if alt_name:
                        options.append(alt_name)

    filtered = [o for o in options if current.lower() in o.lower()]
    return [app_commands.Choice(name=o, value=o) for o in filtered[:25]]



class Radio(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    def resolve_unit_folder(self, unit: str):
        if not os.path.exists(SONGS_FOLDER):
            return unit
        for entry in os.listdir(SONGS_FOLDER):
            if entry.lower() == unit.lower():
                return entry
        return unit

    def get_song_path(self, unit: str, song_name: str, song_type: str = "music"):
        type_folder_map = {
            "norm": "music",
            "music": "music",
            "inst": "instrumental",
            "instrumental": "instrumental",
            "voc": "vocals",
            "vocals": "vocals",
            "alt": "alt",
        }
        folder_name = type_folder_map.get(song_type.lower(), "music")
        unit_folder = self.resolve_unit_folder(unit)
        path = os.path.join(SONGS_FOLDER, unit_folder, folder_name)
        if not os.path.exists(path):
            return None

        for f in os.listdir(path):
            base, _ = os.path.splitext(f)
            if base.lower().startswith(song_name.lower()):
                return os.path.abspath(os.path.join(path, f))
        return None

    async def play_next(self, vc: discord.VoiceClient):
        global queue, played_songs, loop_enabled

        if not vc or vc.is_playing():
            return

        if loop_enabled and hasattr(vc, "current_song"):
            song_name, song_version = vc.current_song
            song_file = self.get_song_path("LeoNeed", song_name)
            if song_file:
                source = discord.FFmpegPCMAudio(executable="ffmpeg", source=song_file)
                vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(vc), self.bot.loop))
                return

        if queue:
            song_path, display_name, version = queue.pop(0)
        else:
            music_path = os.path.join(SONGS_FOLDER, "LeoNeed", "music")
            if not os.path.exists(music_path):
                return
            candidates = [
                os.path.join(music_path, f)
                for f in os.listdir(music_path)
                if f.lower().endswith((".mp3", ".wav", ".ogg"))
            ]
            if not candidates:
                return
            song_path = random.choice(candidates)
            display_name = os.path.splitext(os.path.basename(song_path))[0]
            version = "Normal"

        if not os.path.exists(song_path):
            await self.play_next(vc)
            return

        source = discord.FFmpegPCMAudio(executable="ffmpeg", source=song_path)
        vc.current_song = (display_name, version)
        played_songs.append((display_name, version))
        if len(played_songs) > 5:
            played_songs.pop(0)

        vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(vc), self.bot.loop))

    @app_commands.command(name="radio", description="Start music radio loop")
    async def radio(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("<:ichisip:1365858916361306192> You are not connected to a voice channel.")
            return

        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        await self.play_next(vc)
        await interaction.response.send_message("<:ichiganba:1381502507225710716> Started radio loop.")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭ Skipped current song.")
        else:
            await interaction.response.send_message("<:ichisip:1365858916361306192> No song currently playing.")

    @app_commands.command(name="stop", description="Stop music and disconnect")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect()
            await interaction.response.send_message("<:ichiheart:1384047120704602112> Disconnected.")
        else:
            await interaction.response.send_message("<:ichisip:1365858916361306192> Not in a voice channel.")

    @app_commands.command(name="history", description="Show the last 5 played songs")
    async def history(self, interaction: discord.Interaction):
        global played_songs
        await interaction.response.defer(thinking=False)

        if not played_songs:
            await interaction.followup.send("<:ichisip:1365858916361306192> No songs have been played yet.")
            return

        embed = discord.Embed(title="📜 Recently Played", color=discord.Color.blue())
        history_text = "\n".join(
            f"{i}. {song} — ({version})"
            for i, (song, version) in enumerate(reversed(played_songs[-5:]), start=1)
        )
        embed.description = history_text

        image_path = "Other/LeoNeedPerform.png"
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="LeoNeedPerform.png")
            embed.set_image(url="attachment://LeoNeedPerform.png")
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="loop", description="Toggle looping for current song")
    async def loop(self, interaction: discord.Interaction):
        global loop_enabled
        vc = interaction.guild.voice_client
        if not vc or not hasattr(vc, "current_song"):
            await interaction.response.send_message("<:ichisip:1365858916361306192> No song playing to loop.")
            return

        loop_enabled = not loop_enabled
        await interaction.response.send_message("🔁 Loop enabled" if loop_enabled else "➡️ Loop disabled.")

    @app_commands.command(name="request", description="Request a song to add to the queue")
    @app_commands.describe(
        unit="Song group or folder name",
        song="Song name",
        song_type="Type: Normal, Instrumental, Vocals Only, or a specific Alt version"
    )
    @app_commands.autocomplete(
        unit=unit_autocomplete,
        song=song_autocomplete,
        song_type=type_autocomplete
    )
    async def request(self, interaction: discord.Interaction, unit: str, song: str, song_type: str = "Normal"):
        global queue

        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message("<:ichisip:1365858916361306192> Bot is not connected to a voice channel.")
            return

        if len(queue) >= QUEUE_LIMIT:
            await interaction.response.send_message(
                f"<:ichiyelp:1419613277662482472> Queue is full (max {QUEUE_LIMIT}). Please wait for songs to finish."
            )
            return

        type_map = {
            "normal": "music",
            "instrumental": "instrumental",
            "vocals only": "vocals",
            "vocals": "vocals",
        }

        chosen_type = type_map.get(song_type.strip().lower(), None)

        if chosen_type:
            song_path = self.get_song_path(unit, song, chosen_type)
        else:
            alt_path = os.path.join(SONGS_FOLDER, unit, "alt")
            song_path = None
            if os.path.isdir(alt_path):
                for file in os.listdir(alt_path):
                    filename, _ = os.path.splitext(file)
                    if song.lower() in filename.lower() and song_type.lower() in filename.lower():
                        song_path = os.path.join(alt_path, file)
                        break

        if not song_path:
            await interaction.response.send_message("<:ichiyelp:1419613277662482472> Song not found.")
            return

        queue.append((song_path, song, song_type))
        await interaction.response.send_message(
            f"🎵 Added **{song}** ({song_type}) to the queue. ({len(queue)}/{QUEUE_LIMIT})"
        )

       
    @app_commands.command(name="queue", description="Show all upcoming requested songs")
    async def queue_cmd(self, interaction: discord.Interaction):
        global queue
        await interaction.response.defer(thinking=False)

        if not queue:
            await interaction.followup.send("<:ichisip:1365858916361306192> The queue is currently empty.")
            return

        embed = discord.Embed(title="🎶 Upcoming Queue", color=discord.Color.blue())
        queue_text = "\n".join(
            f"{i}. {song} — ({version})"
            for i, (_, song, version) in enumerate(queue[:QUEUE_LIMIT], start=1)
        )
        embed.description = queue_text

        image_path = "Other/LeoNeedPerform.png"
        if os.path.exists(image_path):
            file = discord.File(image_path, filename="LeoNeedPerform.png")
            embed.set_image(url="attachment://LeoNeedPerform.png")
            embed.add_field(
                name="‎",
                value="[Source](https://x.com/ColorfulStageEN/status/1689034430264881152/photo/1)",
                inline=False
            )
            await interaction.followup.send(embed=embed, file=file)
        else:
            embed.add_field(
                name="‎",
                value="[Source](https://x.com/ColorfulStageEN/status/1689034430264881152/photo/1)",
                inline=False
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="clear", description="Clear the entire request queue")
    async def clear(self, interaction: discord.Interaction):
        global queue
        await interaction.response.defer(thinking=False)

        if not queue:
            await interaction.followup.send("<:ichisip:1365858916361306192> The queue is already empty.")
            return

        queue.clear()
        await interaction.followup.send("<:ichiyelp:1419613277662482472> Cleared the request queue.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Radio(bot))
