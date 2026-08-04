import os
import random
import asyncio
import discord
import yt_dlp
import json
from collections import deque
from discord import app_commands
from discord.ext import commands

FFMPEG_OPTIONS = "-vn -b:a 128k -threads 1"
songs_list = "Databases/songs.json"

declineresopnses = [
    "<:ichiscared:1428366257601908797> %s? is that a Miku song I don't know about?",
    "<:ichishy:1419613335363522571> Vocaloid only, sadly... Not that I hate other singers...",
    "<:SAKIWAHHH:1483401358508953734> Sorry, but I dont think we can perform this one... Maybe we'll practice it next time!",
    "<:sakiplead:1442774865387065434> Hmm...%s... %s... Huh? Sorry but I cant find the music sheets for that one!",
    "<:HonamiFear:1515969788613099571>I'll take note of that! Leo/Need will take that request!",
    "<:honathink:1526178426602520596> Sorry... we can't perform a song we don't know.",
    "<:shihopeek:1488730401404096683>... What?",
    "<:shiho_annoyed:1493500607275995146> That's not in our repertoire."
]

ydl_opts = {
    'format': 'worst_audio/worst',  # Forces lowest quality to save massive CPU
    'noplaylist': True,
    'quiet': True,
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 64k'  # -vn drops video entirely; -b:a caps audio bitrate at 64kbps
}
with open(songs_list, mode="r", encoding="utf-8") as f:
    URL_DICTIONARY = json.load(f)
SONG_LIST = list(URL_DICTIONARY.keys())



queues = {}

async def play_next_audio(interaction, serverID):

    if serverID not in queues or not queues[serverID]:
        return

    req_queue = queues[serverID][1]
    radio_queue = queues[serverID][2]

    if req_queue:
        next_song = req_queue.popleft()
    elif radio_queue:
        next_song = radio_queue.popleft()
    else:
        queues[serverID][0] = None  
        return

    queues[serverID][0] = next_song

    if not interaction.response.is_done():
        await interaction.response.defer()

    try:
        url = URL_DICTIONARY[next_song]
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(
            None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False)
        )
        audio_url = info['url']
        
        source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)
        voice_client = interaction.guild.voice_client
        
        if voice_client and voice_client.is_connected():
            def handle_next(error):
                if error:
                    print(f"Player error: {error}")
                asyncio.run_coroutine_threadsafe(
                    play_next_audio(interaction, serverID), loop
                )
            while len(queues[serverID][2]) <= 3:
                queues[serverID][2].append(random.choice(SONG_LIST))
            voice_client.play(source, after=handle_next)

    except Exception as e:
        print(f"Error playing audio: {e}")
        await play_next_audio(interaction, serverID)


class Radio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="radiostart", description="Play a random song from the radio")
    async def radiostart(self, interaction: discord.Interaction):
        # 1. Check if user is in a voice channel
        if interaction.user.voice is None:
            await interaction.response.send_message("Leo/need can't perform without a stage, y'know?", ephemeral=True)
            return
            
        currentserver = interaction.guild_id
        voice_channel = interaction.user.voice.channel
        voice_client = interaction.guild.voice_client

        # 2. Check if bot is already playing elsewhere
        if voice_client is not None:
            await interaction.response.send_message("Leo/need is already performing elsewhere in the server!", ephemeral=True)
            return

        # 3. Read songs from database

        if not SONG_LIST:
            await interaction.response.send_message("Our Music Sheets! They're Gone! Or maybe Aki's holding maintainance. Probably the latter.<:ichided:1384756489297723402>", ephemeral=True)
            return

        # 4. Correctly seed the queues using deque instances
        # We set index 0 to None because play_next_audio will instantly populate it
        queues[currentserver] = [
            None, 
            deque(), 
            deque([random.choice(SONG_LIST) for _ in range(4)])
        ]

        # 5. Connect the bot to the voice channel
        await voice_channel.connect()

        await interaction.response.send_message("<:ichiicon:1441075829588365462> Let's Play!")
        # 6. Fire off the combined audio playback loop
        await play_next_audio(interaction, currentserver)

    @app_commands.command(name="radiostop", description="Stop the radio and disconnect the bot")
    async def radiostop(self, interaction: discord.Interaction):
        currentserver = interaction.guild_id
        if currentserver in queues:
            queues.pop(currentserver, None)
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.is_connected():
                await voice_client.disconnect()
                await interaction.response.send_message("<:shihoicon:1441076069074599936> See ya next time, eh?")
    
    async def song_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ):
        matches = [
            app_commands.Choice(name=song, value=song) 
            for song in SONG_LIST
            if current.lower() in song.lower()
        ]
        return matches[:25]


    @app_commands.command(name="radiorequest", description="Request a specific song within the database")
    @app_commands.autocomplete(song=song_autocomplete)
    async def radiorequest(self, interaction:discord.Interaction, song:str):
        if interaction.guild_id not in queues:
            await interaction.response.send_message("*crickets* The Stage is empty... Maybe commission them to perform first?")
            return
        if song not in SONG_LIST:
            response = random.choice(declineresopnses)
            try:
                response = response % (song, song)
            except TypeError:
                pass
            await interaction.response.send_message(response)
            return
        await interaction.response.send_message("<:sakiicon:1441076000363515956> Gotcha! We'll add **%s** to the list!" % song)
        queues[interaction.guild_id][1].append(song)

    @app_commands.command(name="radioskip", description="Skips the current song to the next one in queue")
    async def  radioskip(self, interaction:discord.Interaction):
        if interaction.guild_id not in queues:
            await interaction.response.send_message("You can't really skip something if they arent playing, y'know?")
            return
        while len(queues[interaction.guild_id][2]) <= 2:
            queues[interaction.guild_id][2].append(random.choice(SONG_LIST))
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(
            "<:honaicon:1441076167619903642> Alright everyone! Next song!"
        )
    
    @app_commands.command(name="radioqueue", description="Displays the current queue")
    async def radioqueue(self, interaction:discord.Interaction):
        server = interaction.guild_id
        if server not in queues:
            await interaction.response.send_message("... Are we supposed to be playing right now?")
        serverqueue = queues[server]
        embed = discord.Embed(
            color=discord.Color.blue(),
            title="Leo/Need's Stagelist",
            description="💿Currently playing: **%s**" % serverqueue[0]
        )
        requested_queue = "".join([f"{i+1}. {song}\n" for i, song in enumerate(serverqueue[1])])
        embed.add_field(name="Requests Queue", value=requested_queue or "No songs requested")
        random_queue = "".join([f"{i+1}. {song}\n" for i, song in enumerate(serverqueue[2])])
        embed.add_field(name="Radio Queue", value=random_queue)
        embed.set_footer(text="Use /radiorequest to request a song!", icon_url="https://cdn.discordapp.com/emojis/1484485476151722026.webp?size=96&quality=lossless")
        embed.set_image(url="https://www.sekaipedia.org/wiki/Hoshino_Ichika/Gallery#/media/File:2nd_ANNIVERSARY_SPECIAL_STAGE_LN_key_visual_sticker.png")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Radio(bot))
