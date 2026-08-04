import discord
from discord import app_commands
from discord.ext import commands
import json
import os

DB_FILE = "Databases/starboard_configs.json"

class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs("Databases", exist_ok=True)
        if not os.path.exists(DB_FILE):
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f)
        self.starboard_messages = {}

    def load_config(self, guild_id):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            all_configs = json.load(f)
        return all_configs.get(str(guild_id), {"emoji": "⭐", "channel_id": None})

    def save_config(self, guild_id, config):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            all_configs = json.load(f)
        all_configs[str(guild_id)] = config
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(all_configs, f, indent=4)

    @app_commands.command(
        name="starboardsetup",
        description="Setup the starboard channel and emoji"
    )
    @app_commands.describe(
        channel="Channel to post starred messages",
        emoji="Emoji to track"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_starboard(self, interaction: discord.Interaction, channel: discord.TextChannel, emoji: str = "⭐"):
        config = {"emoji": emoji, "channel_id": channel.id}
        self.save_config(interaction.guild.id, config)
        await interaction.response.send_message(
            f"Starboard set to {channel.mention} tracking {emoji} reactions!", ephemeral=True
        )

    @app_commands.command(
        name="starboardinfo",
        description="Show current starboard settings"
    )
    async def starboard_info(self, interaction: discord.Interaction):
        config = self.load_config(interaction.guild.id)
        channel_id = config.get("channel_id")
        emoji = config.get("emoji")
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            await interaction.response.send_message(
                f"Starboard is set to {channel.mention} and tracks {emoji} reactions.", ephemeral=True
            )
        else:
            await interaction.response.send_message("Starboard is not set up yet.", ephemeral=True)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot or reaction.message.guild is None:
            return

        guild_id = reaction.message.guild.id
        config = self.load_config(guild_id)
        emoji = config.get("emoji")
        channel_id = config.get("channel_id")
        if str(reaction.emoji) != emoji or not channel_id:
            return

        starboard_channel = self.bot.get_channel(channel_id)
        if not starboard_channel:
            return

        emoji_count = 0
        for react in reaction.message.reactions:
            if str(react.emoji) == emoji:
                emoji_count = react.count
                break

        star_msg_id = self.starboard_messages.get(reaction.message.id)
        if star_msg_id:
            try:
                star_msg = await starboard_channel.fetch_message(star_msg_id)
                await star_msg.edit(content=f"{emoji} {emoji_count}")
                return
            except discord.NotFound:
                del self.starboard_messages[reaction.message.id]

        embed = discord.Embed(
            description=reaction.message.content or "‎",
            color=discord.Color.blue()
        )
        embed.set_author(
            name=reaction.message.author.display_name,
            icon_url=reaction.message.author.display_avatar.url
        )
        if reaction.message.attachments:
            embed.set_image(url=reaction.message.attachments[0].url)
        embed.add_field(
            name="\u200b",
            value=".⋆ ˖ ࣪ ⊹ ° ┗━°✦✦⌜星乃一歌⌟✦✦°━┛° ⊹ ࣪ ˖ ⋆.",
            inline=False
        )
        embed.add_field(
            name="Source",
            value=f"[Jump!]({reaction.message.jump_url})",
            inline=False
        )

        timestamp = reaction.message.created_at.strftime("%Y-%m-%d %H:%M")
        channel_name = reaction.message.channel.name
        embed.set_footer(text=f"Sent: {timestamp} | Channel: #{channel_name}")
        star_msg = await starboard_channel.send(content=f"{emoji} {emoji_count}", embed=embed)
        self.starboard_messages[reaction.message.id] = star_msg.id


async def setup(bot):
    await bot.add_cog(Starboard(bot))
