import discord
from discord import app_commands
from discord.ext import commands
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "Databases", "ichika_anthology.json")

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.load_database()

    def load_database(self):
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                self.database = json.load(f)
        else:
            self.database = {}

    def save_database(self):
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(self.database, f, ensure_ascii=False, indent=2)

    @app_commands.command(
        name="ichianthologyadd",
        description="Add your own page to the Ichika Anthology to preach the greatness of Ichika",
    )
    @app_commands.describe(entry="Your message or 'page' to add to the anthology")
    async def ichianthologyadd(self, interaction: discord.Interaction, entry: str):
        user_id = str(interaction.user.id)
        username = interaction.user.display_name

        if user_id in self.database:
            await interaction.response.send_message(
                f"{username}, you already have a page in the anthology! Use `/ichianthologysearch {username}` to see it.",
                ephemeral=True,
            )
            return

        self.database[user_id] = {"username": username, "entry": entry}
        self.save_database()
        await interaction.response.send_message(f"📖 Added your page to the Ichika Anthology, {username}!")

    @app_commands.command(
        name="ichianthologyedit",
        description="Edit your existing page in the Ichika Anthology",
    )
    @app_commands.describe(entry="Your new message or 'page' content")
    async def ichianthologyedit(self, interaction: discord.Interaction, entry: str):
        user_id = str(interaction.user.id)
        username = interaction.user.display_name

        if user_id not in self.database:
            self.database[user_id] = {"username": username, "entry": entry}
            self.save_database()
            await interaction.response.send_message(
                f"<:ichiganba:1381502507225710716> You didn’t have a page yet, {username}"
            )
            return

        old_entry = self.database[user_id]["entry"]
        self.database[user_id]["entry"] = entry
        self.database[user_id]["username"] = username
        self.save_database()

        embed = discord.Embed(
            title=f"📖 Ichika Anthology — {username}'s Page Updated",
            description=f"**Old Entry:**\n{old_entry}\n\n**New Entry:**\n{entry}",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ichianthology", description="Browse the Ichika Anthology")
    async def ichianthology(self, interaction: discord.Interaction):
        if not self.database:
            await interaction.response.send_message(
                "<:ichishy:1419613335363522571> The anthology is currently empty. Be the first to write with `/ichianthologyadd`!"
            )
            return

        pages = list(self.database.values())
        index = 0

        embed = discord.Embed(
            title=f"📖 Ichika Anthology — Page {index + 1}/{len(pages)}",
            description=f"**{pages[index]['username']}**\n\n{pages[index]['entry']}",
            color=discord.Color.pink(),
        )
        embed.set_footer(text="Use ◀️ ▶️ to flip pages")

        view = AnthologyView(pages, index)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(
        name="ichianthologysearch",
        description="Jump directly to someone's page in the anthology",
    )
    @app_commands.describe(username="The username to search for")
    async def ichianthologysearch(self, interaction: discord.Interaction, username: str):
        matches = [v for v in self.database.values() if v["username"].lower() == username.lower()]

        if not matches:
            await interaction.response.send_message(f"<:ichisip:1365858916361306192>No page found for **{username}**.")
            return

        entry = matches[0]
        embed = discord.Embed(
            title=f"📖 Ichika Anthology — {entry['username']}'s Page",
            description=entry["entry"],
            color=discord.Color.pink(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ichianthologyclear", description="Clear your entry from Ichika Anthology")
    async def ichianthologyclear(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id in self.database:
            del self.database[user_id]
            self.save_database()
            await interaction.response.send_message("<:ichided:1384756489297723402> Your entry has been removed from the anthology.", ephemeral=True)
        else:
            await interaction.response.send_message("<:ichisip:1365858916361306192> You don’t have an entry in the anthology.", ephemeral=True)

    @app_commands.command(name="ichikamention", description="ICHIKA HOSHINO MENTIONED?!")
    async def slash_copypasta(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "ICHIKA HOSHINO MENTIONED?! Oh Ichika, you are the love of my life. It's been 3 years ever since i have laid my eyes upon you... Your captivating and amazing voice is music in my ears, your eyes shine like the most beautiful of galaxies out there and your looks are the most exquisite and gorgeous ones i can ever find... Oh, you are my reason to wake up, to eat, to walk, to play pjsk, to grind for your rank, to go to school, to study and to sleep. You are the most precious being in the entire world and you are NOT just a fictional character to me... You are the reason how i see the world now, your presence changed everything for me and i'm so thankful that you exist in this world... You are the most amazing, beautiful, pretty, gorgeous, jaw-dropping, cute, adorable, whimsical, exquisite and loving character to exist ever..."
        )
class AnthologyView(discord.ui.View):
    def __init__(self, pages, index):
        super().__init__(timeout=120)
        self.pages = pages
        self.index = index

    async def update_embed(self, interaction: discord.Interaction):
        page = self.pages[self.index]
        embed = discord.Embed(
            title=f"📖 Ichika Anthology — Page {self.index + 1}/{len(self.pages)}",
            description=f"**{page['username']}**\n\n{page['entry']}",
            color=discord.Color.pink(),
        )
        embed.set_footer(text="Use ◀️ ▶️ to flip pages")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.blurple)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(self.pages)
        await self.update_embed(interaction)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.pages)
        await self.update_embed(interaction)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        self.stop()





async def setup(bot):
    await bot.add_cog(Fun(bot))
