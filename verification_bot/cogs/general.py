# cogs/general.py
"""General community and server management cog:
- Invite tracking and leaderboard
- Beautiful Hebrew welcome messages
- Partnership application modal system
"""

import discord
from discord import app_commands
from discord.ext import commands

from db import (
    increment_user_invites,
    get_user_invites,
    get_top_inviters,
    create_partner_application,
    get_guild_settings,
)


class PartnershipModal(discord.ui.Modal, title="🤝 טופס בקשת שותפות"):
    server_name = discord.ui.TextInput(
        label="שם השרת שלך",
        placeholder="לדוגמה: קהילת הגיימינג הישראלית",
        max_length=100,
        required=True
    )
    invite_link = discord.ui.TextInput(
        label="קישור הזמנה קבוע לשרת",
        placeholder="https://discord.gg/xxxxxx",
        max_length=100,
        required=True
    )
    description = discord.ui.TextInput(
        label="תיאור השרת ומספר חברים",
        style=discord.TextStyle.paragraph,
        placeholder="ספרו לנו על השרת שלכם, נושא הקהילה ומדוע תרצו שותפות...",
        max_length=1000,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        app_id = await create_partner_application(
            interaction.user.id,
            interaction.guild.id,
            self.server_name.value,
            self.invite_link.value,
            self.description.value
        )

        settings = await get_guild_settings(interaction.guild.id)
        # Notify log / staff channel if exists
        if settings.get("log_channel_id"):
            log_chan = interaction.guild.get_channel(settings["log_channel_id"])
            if log_chan:
                embed = discord.Embed(
                    title=f"🤝 בקשת שותפות חדשה #{app_id}",
                    color=discord.Color.purple()
                )
                embed.add_field(name="👤 מגיש הבקשה", value=interaction.user.mention, inline=True)
                embed.add_field(name="🏷️ שם השרת", value=self.server_name.value, inline=True)
                embed.add_field(name="🔗 קישור", value=self.invite_link.value, inline=False)
                embed.add_field(name="📝 תיאור", value=self.description.value, inline=False)
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                await log_chan.send(embed=embed)

        await interaction.response.send_message(
            "✅ בקשת השותפות שלך הוגשה בהצלחה ונשלחה לבדיקת הצוות!",
            ephemeral=True
        )


class PartnerButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="📝 הגש בקשת שותפות",
            style=discord.ButtonStyle.primary,
            custom_id="partner_apply_button",
            emoji="🤝"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PartnershipModal())


class PartnerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PartnerButton())


class GeneralCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Cache guild invites to track who invited who: {guild_id: {code: uses}}
        self.invites_cache = {}

    async def cog_load(self):
        self.bot.add_view(PartnerView())
        # Cache invites for joined guilds
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                self.invites_cache[guild.id] = {inv.code: inv.uses for inv in invites}
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        try:
            invites = await guild.invites()
            self.invites_cache[guild.id] = {inv.code: inv.uses for inv in invites}
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        inviter = None

        # Check invites
        if guild.id in self.invites_cache:
            try:
                new_invites = await guild.invites()
                old_invites = self.invites_cache[guild.id]
                for inv in new_invites:
                    if inv.code in old_invites and inv.uses > old_invites[inv.code]:
                        inviter = inv.inviter
                        break
                self.invites_cache[guild.id] = {inv.code: inv.uses for inv in new_invites}
            except Exception:
                pass

        if inviter:
            await increment_user_invites(guild.id, inviter.id, 1)

        # Welcome message in system channel or first text channel
        channel = guild.system_channel
        if not channel:
            channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)

        if channel:
            embed = discord.Embed(
                title=f"👋 ברוכים הבאים ל-{guild.name}!",
                description=(
                    f"שלום {member.mention}! שמחים שהצטרפת אלינו 🎉\n\n"
                    f"🔐 אנא בצע אימות בערוץ האימות כדי לקבל גישה מלאה לשרת."
                ),
                color=discord.Color.teal()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            if inviter:
                total_invites = await get_user_invites(guild.id, inviter.id)
                embed.set_footer(text=f"הוזמן על ידי {inviter.display_name} (סה\"כ הזמנות: {total_invites})")
            try:
                await channel.send(embed=embed)
            except Exception:
                pass

    # --- Slash commands ---

    @app_commands.command(name="invites", description="בדיקת כמות ההזמנות שלך או של משתמש אחר")
    @app_commands.describe(user="המשתמש לבדיקה")
    async def invites(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        count = await get_user_invites(interaction.guild.id, target.id)

        embed = discord.Embed(
            title="📊 מונה הזמנות",
            description=f"למשתמש {target.mention} יש **{count}** הזמנות בשרת!",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="invites_leaderboard", description="טבלת מובילים של ההזמנות בשרת")
    async def invites_leaderboard(self, interaction: discord.Interaction):
        top = await get_top_inviters(interaction.guild.id, limit=10)
        embed = discord.Embed(
            title="🏆 טבלת מובילי ההזמנות",
            color=discord.Color.gold()
        )
        if not top:
            embed.description = "עדיין אין נתוני הזמנות מתועדים בשרת."
        else:
            lines = []
            for i, item in enumerate(top, 1):
                lines.append(f"**#{i}** <@{item['user_id']}> — `{item['invites_count']}` הזמנות")
            embed.description = "\n".join(lines)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="partner_setup", description="יצירת פאנל הגשת שותפויות בערוץ (מנהלים)")
    @app_commands.checks.has_permissions(administrator=True)
    async def partner_setup(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤝 שותפויות ושיתופי פעולה | Partnerships",
            description=(
                "מעוניינים לעשות שותפות עם השרת שלנו? נשמח לשתף פעולה! 🌟\n\n"
                "לחצו על הכפתור למטה ומלאו את הטופס הקצר עם פרטי השרת שלכם.\n"
                "הצוות שלנו יבדוק את הבקשה ויחזור אליכם בהקדם."
            ),
            color=discord.Color.purple()
        )
        embed.set_footer(text=f"{interaction.guild.name} • שותפויות")
        view = PartnerView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ פאנל השותפויות נוצר בהצלחה!", ephemeral=True)

    @app_commands.command(name="partner_apply", description="פתיחת טופס הגשת שותפות ישירות")
    async def partner_apply(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PartnershipModal())


async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCog(bot))
