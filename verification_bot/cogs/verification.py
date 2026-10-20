# cogs/verification.py
"""Verification cog for Discord Verification Bot.
Provides Slash commands, interactive UI buttons, persistent views,
and OAuth2 URL generation with state anti-tampering.
"""

import secrets
import urllib.parse
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import SETTINGS
from db import (
    store_verification_state,
    get_user_verification,
    remove_verified_user,
    get_guild_verification_count,
    log_verification_event,
    get_guild_settings,
    update_guild_settings,
    get_recent_logs,
)


class VerifyButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="🔓 אמת את החשבון שלי",
            style=discord.ButtonStyle.success,
            custom_id="verify_button_persistent",
            emoji="✅"
        )

    async def callback(self, interaction: discord.Interaction):
        # Prevent actions outside guilds
        if not interaction.guild:
            await interaction.response.send_message("❌ ניתן לבצע אימות רק בתוך שרת דיסקורד.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_id = interaction.user.id

        # Check if already verified
        is_verified = await get_user_verification(user_id, guild_id)
        settings = await get_guild_settings(guild_id)
        role = interaction.guild.get_role(settings["verified_role_id"])

        if is_verified and role and role in interaction.user.roles:
            embed = discord.Embed(
                title="✨ חשבונך כבר מאומת!",
                description="החשבון שלך אומת בעבר וכבר יש לך את התפקיד המאומת בשרת. אין צורך לבצע אימות נוסף.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Generate unique cryptographically secure state
        state = secrets.token_urlsafe(32)
        await store_verification_state(state, user_id, guild_id)

        # Build Discord OAuth2 URL
        params = {
            "client_id": SETTINGS.CLIENT_ID,
            "redirect_uri": SETTINGS.REDIRECT_URI,
            "response_type": "code",
            "scope": "identify",
            "state": state,
            "prompt": "consent"
        }
        oauth_url = f"https://discord.com/api/oauth2/authorize?{urllib.parse.urlencode(params)}"

        embed = discord.Embed(
            title="🔐 תהליך אימות חשבון מאובטח (OAuth2)",
            description=(
                "כדי למנוע בוטים וזיופים, האימות מתבצע דרך פורטל ההרשאות הרשמי של Discord.\n\n"
                "📌 **הוראות:**\n"
                "1. לחץ על הכפתור למטה כדי לעבור לדף האישור הרשמי.\n"
                "2. אשר את ההרשאה הבסיסית (`identify` בלבד - ללא סיסמאות או גישה לחשבון).\n"
                "3. לאחר האישור, המערכת תעניק לך את הרול באופן אוטומטי!\n\n"
                "⏳ *הקישור תקף ל-10 דקות בלבד.*"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="מערכת אימות מתקדמת • Discord OAuth2")

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="🌐 המשך לאימות ב-Discord", url=oauth_url, style=discord.ButtonStyle.link))

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(VerifyButton())


class VerificationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Register persistent view so button works across bot restarts
        self.bot.add_view(VerificationView())

    # --- Slash Commands ---

    @app_commands.command(name="verify_setup", description="יצירת פאנל האימות המעוצב בערוץ הנוכחי")
    @app_commands.checks.has_permissions(administrator=True)
    async def verify_setup(self, interaction: discord.Interaction):
        """שולח את הודעת האימות הראשית עם הכפתור האינטראקטיבי."""
        embed = discord.Embed(
            title="🛡️ מערכת אימות | Verification System",
            description=(
                "ברוכים הבאים לשרת! 🌟\n\n"
                "על מנת לקבל גישה מלאה לכל ערוצי השרת ולהגן על הקהילה מפני בוטים וספאמרים, "
                "עליך לבצע אימות קצר ומהיר באמצעות **Discord OAuth2**.\n\n"
                "🔒 **למה OAuth2?**\n"
                "האימות מוודא שהמשתמש הוא אדם אמיתי ומאומת ע\"י דיסקורד. "
                "הבוט מבקש הרשאת זיהוי בסיסית בלבד (`identify`), ולעולם אינו דורש סיסמה או פרטים אישיים.\n\n"
                "👇 **לחצו על הכפתור למטה כדי להתחיל:**"
            ),
            color=discord.Color.from_rgb(88, 101, 242)
        )
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(text=f"{interaction.guild.name} • מערכת הגנה ואימות", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

        view = VerificationView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ פאנל האימות נוצר בהצלחה בערוץ זה!", ephemeral=True)

    @app_commands.command(name="verify_status", description="בדיקת סטטוס האימות של משתמש")
    @app_commands.describe(user="המשתמש לבדיקה (ברירת מחדל: אתה)")
    async def verify_status(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        guild_id = interaction.guild.id

        status = await get_user_verification(target.id, guild_id)
        settings = await get_guild_settings(guild_id)
        role = interaction.guild.get_role(settings["verified_role_id"])
        has_role = role in target.roles if role else False

        embed = discord.Embed(
            title=f"📋 סטטוס אימות עבור {target.display_name}",
            color=discord.Color.green() if status else discord.Color.red()
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        if status:
            verified_time = datetime.fromtimestamp(status["verified_at"]).strftime("%d/%m/%Y %H:%M:%S")
            embed.add_field(name="🔹 סטטוס במערכת", value="✅ **מאומת (OAuth2)**", inline=False)
            embed.add_field(name="🕒 זמן אימות", value=verified_time, inline=False)
            embed.add_field(name="🎭 רול בשרת", value="✅ קיים" if has_role else "⚠️ רול חסר (נדרש רענון)", inline=False)
        else:
            embed.add_field(name="🔹 סטטוס במערכת", value="❌ **לא מאומת**", inline=False)
            embed.add_field(name="🎭 רול בשרת", value="יש לו רול אך אינו רשום ב-DB" if has_role else "ללא רול", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="verify_config", description="הגדרת ערוץ האימות ורול המאומתים לשרת")
    @app_commands.describe(role="רול המאומתים להענקה", channel="ערוץ האימות הראשי")
    @app_commands.checks.has_permissions(administrator=True)
    async def verify_config(self, interaction: discord.Interaction, role: Optional[discord.Role] = None, channel: Optional[discord.TextChannel] = None):
        guild_id = interaction.guild.id
        role_id = role.id if role else None
        channel_id = channel.id if channel else None

        await update_guild_settings(guild_id, verified_role_id=role_id, verification_channel_id=channel_id)
        settings = await get_guild_settings(guild_id)

        embed = discord.Embed(
            title="⚙️ הגדרות אימות עודכנו בהצלחה",
            color=discord.Color.green()
        )
        embed.add_field(name="🎭 רול מאומתים", value=f"<@&{settings['verified_role_id']}>" if settings['verified_role_id'] else "לא הוגדר", inline=False)
        embed.add_field(name="📢 ערוץ אימות", value=f"<#{settings['verification_channel_id']}>" if settings['verification_channel_id'] else "לא הוגדר", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="verify_logs", description="הגדרת ערוץ תיעוד ולוגים לאימות")
    @app_commands.describe(channel="ערוץ הלוגים")
    @app_commands.checks.has_permissions(administrator=True)
    async def verify_logs(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild_id = interaction.guild.id
        await update_guild_settings(guild_id, log_channel_id=channel.id)

        embed = discord.Embed(
            title="🧾 ערוץ לוגים הוגדר בהצלחה",
            description=f"כל אירועי האימות והביטולים יתועדו בערוץ: {channel.mention}",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="verify_revoke", description="הסרת רול אימות ממשתמש וביטול רישומו (מנהלים בלבד)")
    @app_commands.describe(user="המשתמש להסרה", reason="סיבת הביטול")
    @app_commands.checks.has_permissions(administrator=True)
    async def verify_revoke(self, interaction: discord.Interaction, user: discord.Member, reason: Optional[str] = "בוטל ע\"י מנהל"):
        guild_id = interaction.guild.id
        settings = await get_guild_settings(guild_id)
        role = interaction.guild.get_role(settings["verified_role_id"])

        # Remove role if present
        if role and role in user.roles:
            try:
                await user.remove_roles(role, reason=f"אימות בוטל: {reason}")
            except Exception as e:
                await interaction.response.send_message(f"⚠️ שגיאה בהסרת הרול: {e}", ephemeral=True)
                return

        # Remove from DB
        await remove_verified_user(user.id, guild_id)
        await log_verification_event(user.id, guild_id, "revoked", reason)

        # Notify log channel if configured
        if settings["log_channel_id"]:
            log_chan = interaction.guild.get_channel(settings["log_channel_id"])
            if log_chan:
                log_embed = discord.Embed(
                    title="🚫 אימות בוטל",
                    description=f"האימות של {user.mention} בוטל ע\"י {interaction.user.mention}.",
                    color=discord.Color.red()
                )
                log_embed.add_field(name="סיבה", value=reason)
                log_embed.set_thumbnail(url=user.display_avatar.url)
                await log_chan.send(embed=log_embed)

        embed = discord.Embed(
            title="✅ אימות בוטל בהצלחה",
            description=f"האימות של {user.mention} הוסר והרול נלקח.",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="verify_stats", description="הצגת סטטיסטיקות אימות בשרת")
    @app_commands.checks.has_permissions(administrator=True)
    async def verify_stats(self, interaction: discord.Interaction):
        guild = interaction.guild
        verified_count = await get_guild_verification_count(guild.id)
        total_members = guild.member_count or 1
        unverified_count = max(0, total_members - verified_count)
        percentage = round((verified_count / total_members) * 100, 1)

        embed = discord.Embed(
            title=f"📊 סטטיסטיקות אימות • {guild.name}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="👥 סה\"כ חברים בשרת", value=f"`{total_members}`", inline=True)
        embed.add_field(name="✅ מאומתים", value=f"`{verified_count}` ({percentage}%)", inline=True)
        embed.add_field(name="❌ לא מאומתים", value=f"`{unverified_count}`", inline=True)

        recent_logs = await get_recent_logs(guild.id, limit=5)
        if recent_logs:
            log_lines = []
            for item in recent_logs:
                dt = datetime.fromtimestamp(item["timestamp"]).strftime("%H:%M:%S")
                log_lines.append(f"• `{dt}` - <@{item['user_id']}>: **{item['status']}** ({item['note'] or 'ללא הערה'})")
            embed.add_field(name="📜 לוגים אחרונים", value="\n".join(log_lines), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(VerificationCog(bot))
