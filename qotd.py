import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import asyncio
from datetime import datetime
import pytz
import os
import random

SETTINGS_FILE = "Databases/qotd_settings.json"
SUGGESTIONS_FILE = "Databases/qotd_suggestions.json"
SENT_FILE = "Databases/qotd_sent.json"


class QOTDRoleButton(discord.ui.View):
    def __init__(self, role: discord.Role):
        super().__init__(timeout=None)
        self.role = role

    @discord.ui.button(label="Toggle QOTD Role", style=discord.ButtonStyle.blurple)
    async def toggle_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        role = self.role

        if role in member.roles:
            await member.remove_roles(role, reason="User opted out of QOTD role.")
            await interaction.response.send_message(
                f"You’ve been **removed** from {role.mention}.", ephemeral=True
            )
        else:
            await member.add_roles(role, reason="User opted in to QOTD role.")
            await interaction.response.send_message(
                f"You’ve been **added** to {role.mention}!", ephemeral=True
            )

class QOTD(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_qotd_time.start()

    def cog_unload(self):
        self.check_qotd_time.cancel()

    def load_json(self, file):
        if not os.path.exists(file):
            os.makedirs(os.path.dirname(file), exist_ok=True)
            with open(file, "w") as f:
                json.dump({}, f)
        with open(file, "r") as f:
            return json.load(f)

    def save_json(self, file, data):
        with open(file, "w") as f:
            json.dump(data, f, indent=4)

    async def send_qotd(self, guild: discord.Guild):
        settings = self.load_json(SETTINGS_FILE)
        suggestions = self.load_json(SUGGESTIONS_FILE)
        sent = self.load_json(SENT_FILE)

        if str(guild.id) not in settings:
            return

        data = settings[str(guild.id)]
        channel_id = data.get("channel_id")
        role_id = data.get("role_id") 
        time_str = data.get("time")

        channel = guild.get_channel(channel_id)
        if not channel:
            return

        role = guild.get_role(role_id) if role_id else None

        if len(suggestions.get(str(guild.id), [])) == 0:
            await channel.send("<:ichiyelp:1419613277662482472> No QOTD suggestions available!")
            return

        index = random.randint(0, len(suggestions[str(guild.id)]) - 1)
        suggestion = suggestions[str(guild.id)].pop(index)
        self.save_json(SUGGESTIONS_FILE, suggestions)

        embed = discord.Embed(
            title="<:ichiheart:1384047120704602112> Question of the Day!",
            description=f"**{suggestion['question']}**",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Suggested by {suggestion['author']}")

        content = role.mention if role else None

        view = QOTDRoleButton(role) if role else None

        await channel.send(content=content, embed=embed, view=view)

        date_str = datetime.now(pytz.timezone("US/Pacific")).strftime("%Y-%m-%d")
        if str(guild.id) not in sent:
            sent[str(guild.id)] = []
        sent[str(guild.id)].append({
            "date": date_str,
            "question": suggestion['question'],
            "author": suggestion['author'],
            "ordinal": len(sent[str(guild.id)]) + 1
        })
        self.save_json(SENT_FILE, sent)

    @app_commands.command(name="qotdsetup", description="Set up the QOTD channel, role, and daily send time (PST, 24h format).")
    @app_commands.describe(
        channel="The channel to post QOTDs in.",
        role="The role to ping and toggle (e.g., @qotd).",
        time_24h="Time in PST (24-hour format, e.g. 18:00)."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def qotdsetup(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role, time_24h: str):
        settings = self.load_json(SETTINGS_FILE)
        settings[str(interaction.guild.id)] = {
            "channel_id": channel.id,
            "role_id": role.id,
            "time": time_24h
        }
        self.save_json(SETTINGS_FILE, settings)

        await interaction.response.send_message(
            f"<:ichiheart:1384047120704602112> QOTD setup complete!\n"
            f"Questions will post in {channel.mention} at **{time_24h} PST**, and ping {role.mention}.",
            ephemeral=True
        )

    @app_commands.command(name="qotdsuggest", description="Suggest a Question of the Day.")
    @app_commands.describe(question="Your question suggestion.")
    async def qotdsuggest(self, interaction: discord.Interaction, question: str):
        settings = self.load_json(SETTINGS_FILE)
        if str(interaction.guild.id) not in settings:
            await interaction.response.send_message("<:ichisip:1365858916361306192> QOTD is not set up in this server yet.", ephemeral=True)
            return

        suggestions = self.load_json(SUGGESTIONS_FILE)
        if str(interaction.guild.id) not in suggestions:
            suggestions[str(interaction.guild.id)] = []

        suggestions[str(interaction.guild.id)].append({
            "author": str(interaction.user),
            "question": question
        })

        self.save_json(SUGGESTIONS_FILE, suggestions)
        await interaction.response.send_message("<:ichiheart:1384047120704602112> Your QOTD suggestion has been added!", ephemeral=True)

    @app_commands.command(name="qotdforce", description="Force send a QOTD immediately.")
    @app_commands.checks.has_permissions(administrator=True)
    async def qotdforce(self, interaction: discord.Interaction):
        settings = self.load_json(SETTINGS_FILE)
        if str(interaction.guild.id) not in settings:
            await interaction.response.send_message("<:ichisip:1365858916361306192> QOTD is not set up in this server yet.", ephemeral=True)
            return

        await self.send_qotd(interaction.guild)
        await interaction.response.send_message("<:ichiheart:1384047120704602112> QOTD sent successfully!", ephemeral=True)

    @tasks.loop(minutes=1)
    async def check_qotd_time(self):
        now_pst = datetime.now(pytz.timezone("US/Pacific"))
        current_time = now_pst.strftime("%H:%M")

        settings = self.load_json(SETTINGS_FILE)
        for guild_id, data in settings.items():
            if data["time"] == current_time:
                guild = self.bot.get_guild(int(guild_id))
                if guild:
                    await self.send_qotd(guild)

    @check_qotd_time.before_loop
    async def before_check_qotd_time(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="togglerp", description="Gain or Remove the RP role for access to roleplay channels.")
    async def joinrp(self, interaction: discord.Interaction):
        guild = interaction.guild
        role = discord.utils.get(guild.roles, name="RP")
        if not role:
            await interaction.response.send_message("<:ichisip:1365858916361306192> RP role does not exist.", ephemeral=True)
            return
        member = interaction.user
        if role in member.roles:
            await interaction.response.send_message("<:ichisip:1365858916361306192> You already have the RP role.", ephemeral=True)
            await member.remove_roles(role, reason="User opted out of RP role.")
            return
        await member.add_roles(role, reason="User opted in to RP role.")
        await interaction.response.send_message("<:ichiheart:1384047120704602112> You have been given the RP role!", ephemeral=True)

    @app_commands.command(name="qotdlog", description="See data about the QOTDs sent in this server.")
    async def qotdlog(self, interaction: discord.Interaction):
        sent = self.load_json(SENT_FILE)
        suggestions = self.load_json(SUGGESTIONS_FILE)
        suggestcount = len(suggestions.get(str(interaction.guild.id), []))
        if str(interaction.guild.id) not in sent or len(sent[str(interaction.guild.id)]) == 0:
            await interaction.response.send_message("<:ichisip:1365858916361306192> No QOTDs have been sent in this server yet.", ephemeral=True)
            return

        log_entries = sent[str(interaction.guild.id)]
        embed = discord.Embed(
            title="QOTD Log",
            color=discord.Color.blurple()
        )

        for entry in log_entries[-3:]:
            embed.add_field(
                name=f"#{entry['ordinal']} - {entry['date']}",
                value=f"**Question:** {entry['question']}\n**Suggested by:** {entry['author']} \n\n",
                inline=False
            )
        footer = f"{suggestcount} more custom QOTDs pending" if suggestcount > 0 else "No pending custom QOTDs."
        killme = footer
        embed.set_footer(text=f"{killme}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(QOTD(bot))

