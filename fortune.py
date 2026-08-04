import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import random
import os
import json 
from database import Database
import time



FORTUNES = r"Databases/fortunes.json"
ACCOUNTS = r"Databases/usersfortune.json"
RAREFORTUNES = r"Databases/rarefortunes.json"

thing = """
"Let's go, Akito"

We both hold each other's hands and head over to Akito's house. We enter and change. (I wear Akito's comfy sweater and pants to sleep)

"Mafuyu,you look so cute, in my clothing"

"Thank you. Before we go to sleep, c-can we...uh.."

"Yes?"

"Akito-kun, I want to hug you"

"Sure, come here, Mafuyu-chan"

Akito holds me and we cuddle in the sheets. My head is on his chest, as he pats me softly. And smiles, sometimes he giggles cutely. It's so comfy, the sheets are so warm.

He hugs me and I can't help but smile all out. He's too cute. He starts reaching for something on his desk.

He puts the left air pod on my ears and the right one on his. So they match our positions. He smiles at me and I smile back. That means we both agree to listen to some music before we go to sleep."""




class Fortunes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.refresh.start()
        self.lastrefresh = datetime.date.today()
        self.db: Database = bot.db
        self.forced = []
        with open(FORTUNES, mode="r", encoding="utf-8") as f:
            self.fortunes = json.load(f)

        with open(ACCOUNTS, mode="r", encoding="utf-8") as f:
            self.accounts = json.load(f)

        with open(RAREFORTUNES, mode="r", encoding="utf-8") as f:
            self.rarefortunes = json.load(f)


    @app_commands.command(name= "fortune",description="Draw today's daily fortune!")
    async def fortune(self, interaction: discord.Interaction):
        print(self.forced)
        chance = random.randint(1,50)

        if chance == 1:
            embed = discord.Embed(
                title="Today's Fortune",
                description="**Lucky character:** Akito Shinonome",
                color=discord.Color.from_str("#FF7722")
            )
            embed.add_field(value=thing, name="Quote")
            embed.image("https://static.wikitide.net/projectsekaiwiki/thumb/2/2a/Akito_1_art.png/1920px-Akito_1_art.png")
            embed.set_footer("Your brain has been credited 100 mental damage for calling Mafuyu over.")
            await interaction.response.send_message(embed=embed)
            return 

        if interaction.user.id not in self.accounts:
            chance = random.randint(1,1000)
            print(f"{await self.bot.fetch_user(interaction.user.id)} drawed {chance}")
            if chance != 1:
                fortunetitle = random.choice(list(self.fortunes.keys()))
                fortune = self.fortunes[fortunetitle]
                if fortunetitle == "mafufuckyou":
                    fortune["balChange"] = -random.randint(1,10000)
                self.accounts[interaction.user.id] = fortunetitle
                await self.db.change_balance(interaction.user.id, fortune["balChange"],"Fortune", int(time.time()))
                balChange = f"Your account has been credited {fortune['balChange']} Ichicoins for this fortune"
            else: 
                fortunetitle = random.choice(list(self.rarefortunes.keys()))
                fortune = self.rarefortunes[fortunetitle]
                self.accounts[interaction.user.id] = fortunetitle
                await self.db.change_balance(interaction.user.id, fortune["balChange"],"Fortune", int(time.time()))
                balChange = f"Your account has been credited {fortune['balChange']} Ichicoins for this rare fortune"
        else:
            print("Got here")
            if self.accounts[interaction.user.id] == "comeheremafuyuchan":
                embed = discord.Embed(
                    title="Today's Fortune",
                    description="**Lucky character:** Akito Shinonome",
                    color=discord.Color.from_str("#FF7722")
                )
                print("Got here")
                embed.add_field(value=thing, name="Quote")
                print("Got here")
                embed.set_image(url="https://static.wikitide.net/projectsekaiwiki/thumb/2/2a/Akito_1_art.png/1920px-Akito_1_art.png")
                embed.set_footer(text ="Your brain has been credited 100 mental damage for calling Mafuyu over.")
                print("Got here")
                await interaction.response.send_message(embed=embed)
                print("Got here")
                return 
            fortunetitle = self.accounts[interaction.user.id]
            fortune = self.rarefortunes[fortunetitle] if fortunetitle == "goldenichi" or fortunetitle == "feedme" else self.fortunes[fortunetitle]
            balChange = "You have already drawn your fortune for today. Come back later!"
            print(fortunetitle)
            print(fortunetitle == "mafufuckyou")
            print(fortune)
            if interaction.user.id in self.forced:
                if fortunetitle == "mafufuckyou":
                    fortune["balChange"] = -random.randint(1,10000)
                self.forced.remove(interaction.user.id)
                await self.db.change_balance(interaction.user.id, fortune["balChange"],"Fortune", int(time.time()))
                balChange = f"Your account has been credited {fortune['balChange']} Ichicoins for this fortune"

        print("Hi")
        embed = discord.Embed(
            title="Today's Fortune",
            description="**Lucky character:** %s"%fortune["character"],
            color=discord.Color.from_str(fortune["colour"])
        )
        embed.set_thumbnail(url = fortune["thumbnailurl"])
        embed.add_field(name="Quote", value=fortune["entry"])
        embed.set_footer(text = balChange)
        print(self.accounts)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="fortunereset", description="Resets all fortunes")
    async def fortunereset(self, interaction:discord.Interaction):
        with open(ACCOUNTS, mode="w", encoding="utf-8") as f:
            json.dump({}, f)
        with open(ACCOUNTS, mode="r", encoding="utf-8") as f:
            self.accounts = json.load(f)
            print(self.accounts)
        await interaction.response.send_message("All fortunes reset!")

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="fortuneforce", description="Forces a specific fortune on a user")
    async def fortuneforce(self, interaction: discord.Interaction, target:discord.User, fortune:str):
        for i in self.rarefortunes:
            print(f"{i} {fortune} {i == fortune}")
        if fortune in self.fortunes or fortune in self.rarefortunes:
            self.accounts[target.id] = fortune
            if target.id not in self.forced:
                self.forced.append(target.id)
            await interaction.response.send_message("ok", ephemeral=True)
        else:
            await interaction.response.send_message("No fortune under that name", ephemeral=True)

    @tasks.loop(hours=3)
    async def refresh(self):
        if self.lastrefresh != datetime.date.today():
            self.lastrefresh = datetime.date.today()
            with open(ACCOUNTS, mode="w", encoding="utf-8") as f:
                json.dump({}, f)
        with open(ACCOUNTS, mode="r", encoding="utf-8") as f:
            self.accounts = json.load(f)
            

async def setup(bot):
    await bot.add_cog(Fortunes(bot))