import discord
import aiosqlite
from discord.ext import commands
import random
from database import Database
from discord.ext import commands, tasks
from discord import app_commands
from ocrmain import process_image, process_image_sync
from humanfriendly import format_timespan
import os
import aiofiles
import html

IMAGE_FOLDER = r"D:\Code\DiscordBots\stage-of-leo.need\Databases\ResultsTemp"

clearcon = {
    "AP": 1000, 
    "FC": 750,
    "Clear": 250,
    "Play": 50
}

Units = {
    "VIRTUAL SINGER": "A VIRTUAL SINGERsong",
    "Leo/Need": "A Leo/Need song",
    "MORE MORE JUMP!": "A MORE MORE JUMP! song",
    "Vivid BAD SQUAD": "A Vivid BAD SQUAD song",
    "Wonderlands×Showtime": "A Wonderlands×Showtime song",
    "25-ji, Nightcord de.": "A 25-ji, Nightcord de. song"
}

diffcon = {
    "ANY": 1,
    "EASY":1.5,
    "NORMAL":1.7,
    "HARD": 2,
    "EXPERT": 2.5,
    "MASTER": 3.75,
    "APPEND": 5
}


class Jobs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db: Database = bot.db
        self.processingqueue = []

    async def createcommission(self):
        jobseed = random.randint(1,20)
        clearseed = random.choice(clearcon)
        if jobseed == 1:
            diffseed = random.choice(diffcon)
            song = await self.db.fetchone("SELECT * FROM songdata ORDER BY RAND() LIMIT 1")
            checkappend =  song[27]
            if not checkappend and diffseed== "APPEND":
                diffseed = "MASTER"
            songtitle, songid = html.unescape(song[2]), song[1]
            await self.db.write("INSERT INTO activecommissions SET (ClearCondition, SongReq, DiffReq, Reward)", (clearseed,songid, diffseed, 2500*2))
        


    async def imagetodata(self, attachment: discord.message.Attachment) -> dict:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            file_path = os.path.join(IMAGE_FOLDER, f"{attachment.id}_{attachment.filename}")
            print(f"Downloading image asset: {attachment.filename} -> {file_path}")
        try:
            async with aiofiles.open(file_path, mode='wb') as f:
                await f.write(await attachment.read())
            ocr_results = await process_image(file_path, self.db)
            return(ocr_results,file_path)
        except Exception as e:
            print(f"Error handling attachment pipeline: {e}")
            return "Error"

    @app_commands.command(name="ichicommission")

    @app_commands.command(name="ichisubmit",  description="Submit a play")
    async def ichisubmit(self,interaction: discord.Interaction, attachment:discord.Attachment):
        await interaction.response.defer
        data = (await self.imagetodata(attachment))[0]
        list_data = []
        for i in data:
            try: 
                list_data.append(int(data[i]))
            except:
                list_data.append(data[i])
        print(type(data))
        print(list_data)
            

    


async def setup(bot):
    await bot.add_cog(Jobs(bot))