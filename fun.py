import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import io
from saygen import generate_say, IMG_SOURCE
from PIL import Image


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "Databases", "ichika_anthology.json")

thing = """I don't belong in this world, I'm just a waste of space. I'm just someone that happens to be here. I start sobbing. "*sob* I can't do anything! I'm just stupid and lazy! I can't do it! I don't want to try!!!"

My sobbing slowly turns into crying. I can't focus anymore. I leave my additional homework sitting on the desk. I can't even bother to take it off. Who even cares that it's there?. I land on my bed, crying. It's Friday afternoon and I'm crying. I shouldn't be crying.
I shouldn't be crying, this day is supposed to be happy and an amazing day. Yet, I'm still crying. I don't want to bother my online friends, I really don't want to.

"Mafuyu! I came here to gi-"

I slowly raise my head up. What a great time to be here, Akito. He's holding a little sack with some food inside. I don't feel like eating, I feel like dying.

"Go away"

"Mafuyu, I won't"

Akito keeps looking at me. I can't help but look at his eyes. They're beautiful and brave. Mine are wet, from the tears I just shed before.

"Mafuyu, I don't want those pretty eyes to be wet for tears, here"

Akito hands me a napkin. Why is he here? He's supposed to be playing videogames right now. He always plays them on Fridays. Yet, he's here. I place the napkin on my face and wipe off my tears. With him, I somehow immediately feel better.

"Hey, you know I always spend the Friday afternoon and night playing videogames with the rest of my friends, but today I want to spend it with my cute girlfriend Mafuyu"

"c-cute?"

My mouth rises up. I smile softly at his words. I almost never smile when I'm alone. When I'm in the sekai, with Miku. I never smile. Yet now I only feel like smiling.

"Your smile looks so pretty, you should

"This is..very nice of you, Akito-kun"

We place the sheet on the ground of my room. I turn on the lights.

"Hey, do you want to go outside, Mafuyu?"

"S-Sure! Let's go!"

This is the first the time I feel genuinely happy to go outside, especially when it's just with a person I care about. We now place the sheet in the garden's grass. The sun's light flashes on us, Akito's eyes are the prettiest in the sun. We place the food on the sheet.

"P-Pancakes.."

"Do you not like them?"

"Oh, of course I do, Akito-kun!" Akito laughs.

"I know you're used eating cheesecakes with Ena, right?"

"Yes, I do. But I wanna try this"

I grab the pancake with a fork and pop it into my mouth. The pancake is full of flavor. The chocolate that was put on it makes the flavor double, the sprinkles even more. It's the first time I see a pancake with chocolate on it. It tastes amazingly.

"Let's go, Akito"

We both hold each other's hands and head over to Akito's house. We enter and change. (I wear Akito's comfy sweater and pants to sleep)

"Mafuyu,you look so cute, in my clothing"

"Thank you. Before we go to sleep, c-can we...uh.."

"Yes?"

"Akito-kun, I want to hug you"

Akito giggles.

"Sure, come here, Mafuyu-chan"

Akito holds me and we cuddle in the sheets. My head is on his chest, as he pats me softly. And smiles, sometimes he giggles cutely. It's so comfy, the sheets are so warm.

He hugs me and I can't help but smile all out. He's too cute. He starts reaching for something on his desk.

He pulls out some air pods. 

He puts the left air pod on my ears and the right one on his. So they match our positions. He smiles at me and I smile back. That means we both agree to listen to some music before we go to sleep.

The music is calming and the piano notes are very nice. The song is a "Nocturne" by the composer Chopin.

The night sky travels though Akito's windows and the light of the stars shines on us, we look at each other and I quickly steal him a kiss on the lips, he kisses me back, as the night slowly starts to become dark and we fall asleep."""

async def send_long(interaction, text):
    chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]

    await interaction.response.send_message(chunks[0])

    for chunk in chunks[1:]:
        await interaction.followup.send(chunk)

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.load_database()
        self.roleplay_count = {}  # Track "⚔️ Roleplay" count per channel

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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bot messages
        if message.author.bot:
            return
        
        channel_id = message.channel.id
        
        # Check if message contains "⚔️ Roleplay"
        if "⚔️ Roleplay" in message.content:
            # Increment count for this channel
            self.roleplay_count[channel_id] = self.roleplay_count.get(channel_id, 0) + 1
            count = self.roleplay_count[channel_id]
            
            # Respond based on count
            if count == 5:
                await message.channel.send("What")
            elif count == 10:
                await message.channel.send("Shut up")
            elif count == 20:
                await message.channel.send("IM GONNA SHUT YOU DOWN")
                self.roleplay_count[channel_id] = 0  
        else:
            # Reset count if anything else is said
            if channel_id in self.roleplay_count:
                self.roleplay_count[channel_id] = 0

    @app_commands.command(
        name = "saychara",
        description = "Generate an image of a character (Default Ichika) saying your text! (Max 500 characters)"
    )
    @app_commands.describe(text="The text you want the character to say", character="The character to use (default: Ichika)", outfit="The outfit for the character (default: casual2)")
    async def saychara(self, interaction: discord.Interaction, text: str, character: str = "Ichika", outfit: str = "casual2"):
        # Implementation for the /say command
        await interaction.response.defer()
        image_ = Image.open(f"{IMG_SOURCE}/{character}/{outfit}.webp").convert("RGBA")
        image = generate_say(text, image_)
        await interaction.followup.send(file=discord.File(image, "say.png"))
    
    @app_commands.command(
        name = "say",
        description = "Generate an image of a user's pfp sayong something of your choice"
    )
    @app_commands.describe(text="The text you want the character to say", user = "The profile picture of the user to use")
    async def say(self, interaction: discord.Interaction, text: str, user: discord.User):
        await interaction.response.defer()
        avatar_asset = user.avatar or user.default_avatar
        print(avatar_asset)
        avatar_bytes = await avatar_asset.read()
        
        avatar_buffer = io.BytesIO(avatar_bytes)
        image_ = Image.open(avatar_buffer)
        print(image_)
        image = generate_say(text, image_)
        print(image)
        await interaction.followup.send(file=discord.File(image, "say.png"))
    

    @app_commands.command(
        name="anthologyadd",
        description="Add your own page to the Anthology to preach the greatness of Ichika",
    )
    @app_commands.describe(entry="Your message or 'page' to add to the anthology")
    async def anthologyadd(self, interaction: discord.Interaction, entry: str):
        user_id = str(interaction.user.id)
        username = interaction.user.display_name

        if user_id in self.database:
            await interaction.response.send_message(
                f"{username}, you already have a page in the anthology! Use `/anthologysearch {username}` to see it.",
                ephemeral=True,
            )
            return

        self.database[user_id] = {"username": username, "entry": entry}
        self.save_database()
        await interaction.response.send_message(f"📖 Added your page to the Anthology, {username}!")

    @app_commands.command(
        name="anthologyedit",
        description="Edit your existing page in the Anthology",
    )
    @app_commands.describe(entry="Your new message or 'page' content")
    async def anthologyedit(self, interaction: discord.Interaction, entry: str):
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
            title=f"Anthology — {username}'s Page Updated",
            description=f"**Old Entry:**\n{old_entry}\n\n**New Entry:**\n{entry}",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="anthologybrowse", description="Browse the Anthology")
    async def anthology(self, interaction: discord.Interaction):
        if not self.database:
            await interaction.response.send_message(
                "<:ichishy:1419613335363522571> The anthology is currently empty. Be the first to write with `/anthologyadd`!"
            )
            return

        pages = list(self.database.values())
        index = 0

        embed = discord.Embed(
            title=f"Anthology — Page {index + 1}/{len(pages)}",
            description=f"**{pages[index]['username']}**\n\n{pages[index]['entry']}",
            color=discord.Color.pink(),
        )
        embed.set_footer(text="Use ◀️ ▶️ to flip pages")

        view = AnthologyView(pages, index)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(
        name="anthologysearch",
        description="Jump directly to someone's page in the anthology",
    )
    @app_commands.describe(username="The username to search for")
    async def anthologysearch(self, interaction: discord.Interaction, username: str):
        matches = [v for v in self.database.values() if v["username"].lower() == username.lower()]

        if not matches:
            await interaction.response.send_message(f"<:ichisip:1365858916361306192>No page found for **{username}**.")
            return

        entry = matches[0]
        embed = discord.Embed(
            title=f"Anthology — {entry['username']}'s Page",
            description=entry["entry"],
            color=discord.Color.pink(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="anthologyclear", description="Clear your entry from the Anthology")
    async def anthologyclear(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id in self.database:
            del self.database[user_id]
            self.save_database()
            await interaction.response.send_message("<:ichided:1384756489297723402> Your entry has been removed from the anthology.", ephemeral=True)
        else:
            await interaction.response.send_message("<:ichisip:1365858916361306192> You don’t have an entry in the anthology.", ephemeral=True)

    @app_commands.command(name="minorimention", description="MINORI HANASATO MENTIONED?!")
    async def slash_minocopypasta(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "MINORI?????????????? Minori Hanasato mentioned??????? Have I said that I L-O-V-E Minori Hanasato 🌸 from the hit game Project Sekai: Colorful Stage! feat. Minori Hanasato 🌸? So, I love Minori Hanasato 🌸 from the hit game Project Sekai: Colorful Stage! feat. Minori Hanasato 🌸. Yes, now you know, that I love Minori Hanasato 🌸 from the hit game Project Sekai: Colorful Stage! feat. Minori Hanasato 🌸. \n Minori Hanasato 🌸 is the best idol in the game. She's so resilient and strong. Minori 🌸 has failed many times but never gave up. Minori 🌸 is the light in a sea of darkness. Minori 🌸 can save peoples, states, societies, continents, Earth, Sun, stars, galaxies, the Universe by her singing and dancing. Minori Hanasato 🌸 is Love. Minori Hanasato 🌸 gives Hope. Minori Hanasato 🌸 represents the Life.  \n Be a Minori 🌸 fan today!~ 🌸 🌸 🌸 🌸 🌸 🌸 🌸"
        )
    
    @app_commands.command(name="honamimention", description="MOCHIZUKI HONAMI MENTIONED?!")
    async def slash_honamicopypasta(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "OH MY APPLE PIE HONAMI MOCHIZUKI MENTIONED?! you do not know how much i love honami and her absolutely bottomless greed for apple pie AND I WILL KEEP DEFENDING HER UNTIL THE DAY I DIE. SHE DIDNT RUN OVER TSUKASA! SHE IS A LAW ABIDING CITIZEN! SHE **THREW THE CAR** DIRECTLY AT TSUKASA THE OLD FASHIONED WAY! SHE DINT'T STEAL THOSE APPLE PIES! SHE **BARGAINED AWAY THE CHEF'S LIFE TO THE DEMON LORD**TO CLAIM THEM! LIKE A NORMAL PERSON WOULD! All of you who are accusing my beloved honami of being a criminal are just jealous of her and her perfection. Instead, follow me her. Practice your drumming or Taiko skills until you drop dead. Bake like you will never bake again. FOR IT IS HER, THE ONE AND ONLT HONAMI MOCHIZUKI WHO CAN CLEANSE YOU OF YOUR FLAWS"
        )

    @app_commands.command(name="shihomention", description="SHIHO HINOMORI MENTIONED?!")
    async def slash_shihcopypasta(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "SHIHO HINOMORI MENTIONED!!! she really tried the whole \“I don’t need anyone\” thing but it’s always 4 = 1 like clockwork  every time something’s off (especially with Ichika) she glitches for a second then acts like nothing happened, and the wild part is she KNOWS exactly how much she cares but just refuses to say it  she shows up, supports everyone, carries the bass and the group’s stability, adjusts instantly, remembers everything, and still acts like it’s nothing… at this point it’s not even development it’s a loop, she just keeps choosing them over and over again and 4 = 1 isn’t even math anymore it’s literally just Shiho ~~I LOVE HER~~ WE LOVE HER"
        )

    @app_commands.command(name="ichikamention", description="ICHIKA HOSHINO MENTIONED?!")
    async def slash_ichicopypasta(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "ICHIKA HOSHINO MENTIONED?! Oh Ichika, you are the love of my life. It's been 3 years ever since i have laid my eyes upon you... Your captivating and amazing voice is music in my ears, your eyes shine like the most beautiful of galaxies out there and your looks are the most exquisite and gorgeous ones i can ever find... Oh, you are my reason to wake up, to eat, to walk, to play pjsk, to grind for your rank, to go to school, to study and to sleep. You are the most precious being in the entire world and you are NOT just a fictional character to me... You are the reason how i see the world now, your presence changed everything for me and i'm so thankful that you exist in this world... You are the most amazing, beautiful, pretty, gorgeous, jaw-dropping, cute, adorable, whimsical, exquisite and loving character to exist ever..."
        )

    @app_commands.command(name="comeheremafuyuchan", description="Unleash carnage")
    async def slash_mafuyucopypasta(self, interaction: discord.Interaction):
        print("Recieved command to unleash carnage")
        await send_long(interaction, thing)  

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

async def setup(bot):
    await bot.add_cog(Fun(bot))
