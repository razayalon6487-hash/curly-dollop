'''
══════════════════════════════════════════════════════════════════════════════
👑 ✦ Discord Verification, Community, Invites & Boost Bot ✦ 👑
══════════════════════════════════════════════════════════════════════════════
המערכת המקיפה והמשודרגת:
1. 🛡️ מערכת אימות מהירה ומאובטחת ללא אזכור שמות טכניים, עם טקסט מעוצב ואימוג'ים
2. 🤖 כפתור מדריך להוספת הבוט ל-Apps ולשרתים
3. 🌐 שרת אימות אסינכרוני (aiohttp) בדפדפן + הודעה אישית בחדר האימות ובפרטי
4. 📩 מערכת מעקב הזמנות (Invite Tracker) + פאנל אינטראקטיבי ותיקון כפתור סגירת הודעה
5. 👋 כרטיסי קבלת פנים מרהיבים (Pillow) עם באנר מטושטש ואוואטר מעוצב
6. 🚀 מערכת התראות בוסטים (Server Boost Alert) עם טקסט יוקרתי ותמונת הבוסטר
7. 🤝 פקודת /partner לשליחת תוכן שותפות עם הכותרת "פרטנר חדש!"
8. 📸 פקודת /legit להעלאת הוכחות/לגיטים לערוץ
══════════════════════════════════════════════════════════════════════════════
'''

import os
import sys
import io
import time
import secrets
import asyncio
import logging
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import (Dict, List, Optional, Any)
from urllib.parse import urlparse
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
import aiohttp
from aiohttp import web
import discord
from discord import app_commands
from discord.ext import commands
from PIL import (Image, ImageDraw, ImageFont, ImageFilter, ImageOps)
from config import SETTINGS
import db
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger('unified_bot')
EMBED_COLOR_PRIMARY = 5793266
EMBED_COLOR_SUCCESS = 3066993
EMBED_COLOR_WARNING = 15844367
EMBED_COLOR_DANGER = 15158332
EMBED_COLOR_BOOST = 16023551
BOT_ACCESS_ROLE_NAME = "גישה לבוט"
STATS_CATEGORY_NAME = "📊 Server Stats"
STATS_MEMBERS_PREFIX = "Members:"
STATS_ONLINE_PREFIX = "Online:"


def _is_staff_role(role: discord.Role) -> bool:
    p = role.permissions
    return any((p.administrator, p.manage_guild, p.manage_channels, p.manage_roles,
                p.manage_messages, p.view_audit_log, p.kick_members, p.ban_members,
                p.moderate_members))


async def apply_verification_access(guild: discord.Guild, channel=None):
    settings = await db.get_guild_settings(guild.id)
    if not settings.get("verification_access_locked"):
        return 0
    role = guild.get_role(settings.get("verified_role_id") or 0)
    verify_id = settings.get("verification_channel_id")
    welcome_id = settings.get("welcome_channel_id")
    if role is None or not verify_id or not welcome_id:
        return 0
    me = guild.me
    if me is None or not (me.guild_permissions.manage_channels and me.guild_permissions.manage_roles):
        return 0
    public_ids = {verify_id, welcome_id}
    changed = 0
    for ch in ([channel] if channel is not None else list(guild.channels)):
        everyone = ch.overwrites_for(guild.default_role)
        expected = ch.id in public_ids
        if everyone.view_channel is not expected:
            everyone.view_channel = expected
            await ch.set_permissions(guild.default_role, overwrite=everyone, reason="Restrict unverified channel access")
        verified = ch.overwrites_for(role)
        if verified.view_channel is not True:
            verified.view_channel = True
            await ch.set_permissions(role, overwrite=verified, reason="Grant verified member access")
        for target, overwrite in list(ch.overwrites.items()):
            if target in (guild.default_role, role):
                continue
            if isinstance(target, discord.Role) and _is_staff_role(target):
                continue
            if isinstance(target, discord.Member) and role in target.roles:
                if overwrite.view_channel is not True:
                    overwrite.view_channel = True
                    await ch.set_permissions(target, overwrite=overwrite, reason="Grant verified member access")
                continue
            if overwrite.view_channel is not False:
                overwrite.view_channel = False
                await ch.set_permissions(target, overwrite=overwrite, reason="Restrict unverified channel access")
        changed += 1
    return changed


async def refresh_stats_channels(guild: discord.Guild):
    me = guild.me
    if me is None or not (me.guild_permissions.manage_channels and me.guild_permissions.manage_roles):
        logger.warning("Cannot manage locked stats channels in %s", guild.name)
        return
    everyone = discord.PermissionOverwrite(view_channel=True, connect=False)
    category = discord.utils.get(guild.categories, name=STATS_CATEGORY_NAME)
    if category is None:
        category = await guild.create_category(STATS_CATEGORY_NAME, overwrites={guild.default_role: everyone})
    async def lock_channel(ch):
        for target, overwrite in list(ch.overwrites.items()):
            if overwrite.connect is True:
                overwrite.connect = False
                await ch.set_permissions(target, overwrite=overwrite, reason="Keep stats voice channels locked")
        await ch.set_permissions(guild.default_role, overwrite=everyone, reason="Stats channels are visible but not joinable")
    await lock_channel(category)
    members = next((c for c in category.voice_channels if c.name.startswith(STATS_MEMBERS_PREFIX)), None)
    online = next((c for c in category.voice_channels if c.name.startswith(STATS_ONLINE_PREFIX)), None)
    if members is None:
        members = await guild.create_voice_channel(f"{STATS_MEMBERS_PREFIX} 0", category=category, overwrites={guild.default_role: everyone})
    if online is None:
        online = await guild.create_voice_channel(f"{STATS_ONLINE_PREFIX} 0", category=category, overwrites={guild.default_role: everyone})
    await lock_channel(members)
    await lock_channel(online)
    total = guild.member_count or len(guild.members)
    online_count = sum(m.status in (discord.Status.online, discord.Status.idle, discord.Status.dnd) for m in guild.members)
    if members.name != f"{STATS_MEMBERS_PREFIX} {total}":
        await members.edit(name=f"{STATS_MEMBERS_PREFIX} {total}")
    if online.name != f"{STATS_ONLINE_PREFIX} {online_count}":
        await online.edit(name=f"{STATS_ONLINE_PREFIX} {online_count}")


def schedule_stats_refresh(guild: discord.Guild, delay: float = 10.0):
    task = bot.stats_refresh_tasks.get(guild.id)
    if task and not task.done():
        task.cancel()
    async def delayed():
        try:
            await asyncio.sleep(delay)
            await refresh_stats_channels(guild)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Stats refresh failed for guild %s", guild.id)
        finally:
            if bot.stats_refresh_tasks.get(guild.id) is asyncio.current_task():
                bot.stats_refresh_tasks.pop(guild.id, None)
    bot.stats_refresh_tasks[guild.id] = asyncio.create_task(delayed())


class InviteTracker:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.cache = {}

    async def sync_guild(self, guild: discord.Guild):
        if not guild.me.guild_permissions.manage_guild:
            return
        try:
            invites = await guild.invites()
        except Exception:
            return
        try:
            self.cache[guild.id] = {invite.code: invite.uses for invite in invites}
        except Exception:
            return

    async def sync_all_guilds(self):
        for guild in self.bot.guilds:
            await self.sync_guild(guild)

    def add_invite(self, invite: discord.Invite):
        if invite.guild.id not in self.cache:
            self.cache[invite.guild.id] = {}
        self.cache[invite.guild.id][invite.code] = invite.uses or 0

    def remove_invite(self, invite: discord.Invite):
        if invite.guild.id in self.cache:
            self.cache[invite.guild.id].pop(invite.code, None)

    async def find_used_invite(self, member: discord.Member) -> Optional[discord.Invite]:
        guild = member.guild
        if guild.id not in self.cache:
            await self.sync_guild(guild)
        cached_invites = self.cache.get(guild.id, {})
        try:
            current_invites = await guild.invites()
        except Exception:
            return
        used_invite = None
        for invite in current_invites:
            old_uses = cached_invites.get(invite.code, 0)
            if not invite.uses > old_uses:
                continue
            used_invite = invite
            break
        self.cache[guild.id] = {invite.code: invite.uses for invite in current_invites}
        return used_invite


def get_font(size: int, bold: bool=True):
    font_names = ['segoeuib.ttf', 'arialbd.ttf'] if bold else ['segoeui.ttf', 'arial.ttf']
    win_fonts = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
    for fname in font_names:
        fpath = os.path.join(win_fonts, fname)
        if os.path.exists(fpath):
            try:
                pass
            except Exception:
                continue
            return ImageFont.truetype(fpath, size)
    return ImageFont.load_default()

async def generate_welcome_card(member: discord.Member) -> io.BytesIO:
    width, height = 900, 380
    card = Image.new('RGBA', (width, height), (15, 23, 42, 255))
    guild = member.guild
    bg_bytes = None
    if guild.banner:
        try:
            bg_bytes = await guild.banner.read()
        except Exception:
            pass
    if not bg_bytes:
        if guild.icon:
            try:
                bg_bytes = await guild.icon.read()
            except Exception:
                pass
    if bg_bytes:
        try:
            bg_img = Image.open(io.BytesIO(bg_bytes)).convert('RGBA')
            bg_img = ImageOps.fit(bg_img, (width, height), method=Image.Resampling.LANCZOS)
            bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=10))
            overlay = Image.new('RGBA', (width, height), (0, 0, 0, 205))
            bg_img = Image.alpha_composite(bg_img, overlay)
            card.paste(bg_img, (0, 0))
        except Exception:
            pass
    draw = ImageDraw.Draw(card)
    accent_green = (57, 255, 20)
    text_white = (235, 240, 245)
    text_gray = (148, 163, 184)
    draw.rectangle([(0, 0), (width, 4)], fill=accent_green)
    draw.rectangle([(0, height - 4), (width, height)], fill=accent_green)
    av_size = 130
    av_x = (width - av_size) // 2
    av_y = 28
    avatar_bytes = None
    if member.display_avatar:
        try:
            avatar_bytes = await member.display_avatar.read()
        except Exception:
            pass
        else:
            if avatar_bytes:
                try:
                    av_img = Image.open(io.BytesIO(avatar_bytes)).convert('RGBA')
                    av_img = av_img.resize((av_size, av_size), Image.Resampling.LANCZOS)
                    mask = Image.new('L', (av_size * 2, av_size * 2), 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, av_size * 2, av_size * 2), fill=255)
                    mask = mask.resize((av_size, av_size), Image.Resampling.LANCZOS)
                    draw.ellipse([(av_x - 10, av_y - 10), (av_x + av_size + 10, av_y + av_size + 10)], outline=(0, 120, 0), width=4)
                    draw.ellipse([(av_x - 5, av_y - 5), (av_x + av_size + 5, av_y + av_size + 5)], outline=accent_green, width=3)
                    card.paste(av_img, (av_x, av_y), mask)
                except Exception:
                    pass
    font_welcome = get_font(38, bold=True)
    font_username = get_font(28, bold=True)
    font_member = get_font(19, bold=False)
    text_start_y = av_y + av_size + 18
    w_box = draw.textbbox((0, 0), 'WELCOME', font=font_welcome)
    draw.text(((width - (w_box[2] - w_box[0])) // 2, text_start_y), 'WELCOME', fill=accent_green, font=font_welcome)
    username_str = f'@{member.name}'
    u_box = draw.textbbox((0, 0), username_str, font=font_username)
    draw.text(((width - (u_box[2] - u_box[0])) // 2, text_start_y + 48), username_str, fill=text_white, font=font_username)
    member_str = f'MEMBER  #{guild.member_count}'
    m_box = draw.textbbox((0, 0), member_str, font=font_member)
    draw.text(((width - (m_box[2] - m_box[0])) // 2, text_start_y + 84), member_str, fill=text_gray, font=font_member)
    buffer = io.BytesIO()
    card.convert('RGB').save(buffer, format='PNG')
    buffer.seek(0)
    return buffer

async def generate_leave_card(member: discord.Member) -> io.BytesIO:
    width, height = 900, 380
    card = Image.new('RGBA', (width, height), (15, 23, 42, 255))
    guild = member.guild
    bg_bytes = None
    if guild.banner:
        try:
            bg_bytes = await guild.banner.read()
        except Exception:
            pass
    if not bg_bytes:
        if guild.icon:
            try:
                bg_bytes = await guild.icon.read()
            except Exception:
                pass
    if bg_bytes:
        try:
            bg_img = Image.open(io.BytesIO(bg_bytes)).convert('RGBA')
            bg_img = ImageOps.fit(bg_img, (width, height), method=Image.Resampling.LANCZOS)
            bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=10))
            overlay = Image.new('RGBA', (width, height), (0, 0, 0, 215))
            bg_img = Image.alpha_composite(bg_img, overlay)
            card.paste(bg_img, (0, 0))
        except Exception:
            pass
    draw = ImageDraw.Draw(card)
    accent_red = (255, 75, 75)
    text_white = (235, 240, 245)
    text_gray = (148, 163, 184)
    draw.rectangle([(0, 0), (width, 4)], fill=accent_red)
    draw.rectangle([(0, height - 4), (width, height)], fill=accent_red)
    av_size = 130
    av_x = (width - av_size) // 2
    av_y = 28
    avatar_bytes = None
    if member.display_avatar:
        try:
            avatar_bytes = await member.display_avatar.read()
        except Exception:
            pass
        else:
            if avatar_bytes:
                try:
                    av_img = Image.open(io.BytesIO(avatar_bytes)).convert('RGBA')
                    av_img = av_img.resize((av_size, av_size), Image.Resampling.LANCZOS)
                    mask = Image.new('L', (av_size * 2, av_size * 2), 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, av_size * 2, av_size * 2), fill=255)
                    mask = mask.resize((av_size, av_size), Image.Resampling.LANCZOS)
                    draw.ellipse([(av_x - 10, av_y - 10), (av_x + av_size + 10, av_y + av_size + 10)], outline=(120, 0, 0), width=4)
                    draw.ellipse([(av_x - 5, av_y - 5), (av_x + av_size + 5, av_y + av_size + 5)], outline=accent_red, width=3)
                    card.paste(av_img, (av_x, av_y), mask)
                except Exception:
                    pass
    font_leave = get_font(38, bold=True)
    font_username = get_font(28, bold=True)
    font_member = get_font(19, bold=False)
    text_start_y = av_y + av_size + 18
    w_box = draw.textbbox((0, 0), 'GOODBYE', font=font_leave)
    draw.text(((width - (w_box[2] - w_box[0])) // 2, text_start_y), 'GOODBYE', fill=accent_red, font=font_leave)
    username_str = f'@{member.name}'
    u_box = draw.textbbox((0, 0), username_str, font=font_username)
    draw.text(((width - (u_box[2] - u_box[0])) // 2, text_start_y + 48), username_str, fill=text_white, font=font_username)
    member_str = f'MEMBERS LEFT  #{guild.member_count}'
    m_box = draw.textbbox((0, 0), member_str, font=font_member)
    draw.text(((width - (m_box[2] - m_box[0])) // 2, text_start_y + 84), member_str, fill=text_gray, font=font_member)
    buffer = io.BytesIO()
    card.convert('RGB').save(buffer, format='PNG')
    buffer.seek(0)
    return buffer

async def get_report_log_channel(guild: discord.Guild):
    settings = await db.get_guild_settings(guild.id)
    channel_id = settings.get("report_channel_id") or settings.get("log_channel_id")
    return guild.get_channel(channel_id) if channel_id else None


async def resolve_report_target(guild: discord.Guild, value: str):
    value = value.strip()
    match = re.fullmatch(r"<@!?(\d+)>", value)
    user_id = match.group(1) if match else value
    if user_id.isdecimal():
        member = guild.get_member(int(user_id))
        if member:
            return member, None
        try:
            return await guild.fetch_member(int(user_id)), None
        except discord.NotFound:
            return None, "המשתמש שדווח אינו נמצא בשרת."
        except discord.HTTPException:
            return None, "לא הצלחתי לאתר את המשתמש לפי המזהה."
    exact = [m for m in guild.members if value.casefold() in {
        m.name.casefold(), m.display_name.casefold(), (m.global_name or "").casefold()
    }]
    if len(exact) == 1:
        return exact[0], None
    if len(exact) > 1:
        return None, "נמצאו כמה משתמשים בשם הזה. בקש מהמדווח לציין @mention או User ID."
    return None, "לא מצאתי משתמש תואם. בקש מהמדווח לציין @mention או User ID."


class ReportModal(discord.ui.Modal, title="📢 דיווח על משתמש"):
    target_user = discord.ui.TextInput(label="שם המשתמש או User ID", placeholder="עדיף לתייג את המשתמש או לציין User ID", max_length=100)
    reason = discord.ui.TextInput(label="סיבת הדיווח", placeholder="לדוגמה: הטרדה, ספאם או התנהגות לא ראויה", max_length=200)
    description = discord.ui.TextInput(label="תיאור מפורט", style=discord.TextStyle.paragraph, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("אפשר לשלוח דיווח רק מתוך שרת.", ephemeral=True)
            return
        channel = await get_report_log_channel(guild)
        if channel is None:
            await interaction.response.send_message("❌ לא הוגדר ערוץ לוג לדיווחים. בקש ממנהל להגדיר set_report_channel.", ephemeral=True)
            return
        report_id = await db.create_report(
            guild_id=guild.id, reporter_id=interaction.user.id,
            target_user=self.target_user.value, reason=self.reason.value,
            description=self.description.value,
        )
        embed = discord.Embed(title=f"📢 דיווח חדש | #{report_id}", color=EMBED_COLOR_WARNING)
        embed.add_field(name="👤 מדווח", value=interaction.user.mention, inline=True)
        embed.add_field(name="🎯 נגד", value=self.target_user.value, inline=True)
        embed.add_field(name="📋 סיבה", value=self.reason.value, inline=False)
        embed.add_field(name="📝 תיאור", value=self.description.value, inline=False)
        embed.add_field(name="🔖 מצב", value="⏳ ממתין לבחינה", inline=True)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"ID: {interaction.user.id} | זמן: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        try:
            msg = await channel.send(embed=embed, view=ReportAdminView(report_id, guild.id))
            await db.update_report(report_id, log_message_id=msg.id)
        except discord.HTTPException:
            logger.exception("Failed to deliver report %s", report_id)
            await interaction.response.send_message("❌ לא הצלחתי לשלוח את הדיווח ללוג. בדוק הרשאות בוט בערוץ.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ הדיווח נשלח", description="הצוות יבדוק את הדיווח וישלח לך עדכון בפרטי.", color=EMBED_COLOR_SUCCESS),
            ephemeral=True,
        )


async def apply_report_sanction(guild: discord.Guild, target: discord.Member, sanction: str, duration: str, report_id: int, note: str) -> str:
    me = guild.me
    if me is None or target.id in {guild.owner_id, me.id}:
        raise ValueError("אי אפשר להפעיל פעולה על בעל השרת או על הבוט.")
    if target.top_role >= me.top_role:
        raise ValueError("תפקיד המשתמש שווה לתפקיד הבוט או גבוה ממנו.")
    reason = f"Report #{report_id} approved: {note}"[:480]
    if sanction == "ban":
        if not me.guild_permissions.ban_members:
            raise ValueError("לבוט חסרה הרשאת Ban Members.")
        await guild.ban(target, reason=reason)
        return "🚫 באן"
    if sanction == "kick":
        if not me.guild_permissions.kick_members:
            raise ValueError("לבוט חסרה הרשאת Kick Members.")
        await target.kick(reason=reason)
        return "👢 קיק"
    if sanction == "timeout":
        if not me.guild_permissions.moderate_members:
            raise ValueError("לבוט חסרה הרשאת Moderate Members.")
        try:
            minutes = int(duration.strip())
        except (TypeError, ValueError):
            raise ValueError("להשתקה יש להזין משך בדקות, בין 1 ל־40320.")
        if not 1 <= minutes <= 40320:
            raise ValueError("משך ההשתקה חייב להיות בין 1 ל־40320 דקות.")
        await target.timeout(timedelta(minutes=minutes), reason=reason)
        return f"🔇 השתקה ל־{minutes} דקות"
    raise ValueError("סוג הפעולה לא תקין.")


class ReportSanctionSelect(discord.ui.Select):
    def __init__(self, report_id: int, guild: discord.Guild):
        self.report_id, self.guild = report_id, guild
        super().__init__(
            placeholder="בחר פעולה עבור המשתמש",
            options=[
                discord.SelectOption(label="Ban", value="ban"),
                discord.SelectOption(label="Kick", value="kick"),
                discord.SelectOption(label="Mute / Timeout", value="timeout"),
            ],
            min_values=1, max_values=1, custom_id=f"report_sanction:{report_id}",
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild_id != self.guild.id or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ רק מנהל השרת שבו נשלח הדיווח יכול לטפל בו.", ephemeral=True)
            return
        await interaction.response.send_modal(AdminResponseModal(self.report_id, "approved", self.guild, self.values[0]))


class ReportSanctionView(discord.ui.View):
    def __init__(self, report_id: int, guild: discord.Guild):
        super().__init__(timeout=120)
        self.add_item(ReportSanctionSelect(report_id, guild))


class AdminResponseModal(discord.ui.Modal, title="✏️ תגובת הצוות"):
    response_text = discord.ui.TextInput(label="תגובה שתישלח למדווח", style=discord.TextStyle.paragraph, max_length=1000)
    mute_duration = discord.ui.TextInput(label="משך השתקה בדקות (רק ל־Mute)", required=False, max_length=5)

    def __init__(self, report_id: int, action: str, guild: discord.Guild, sanction: Optional[str] = None):
        super().__init__()
        self.report_id, self.action, self.guild, self.sanction = report_id, action, guild, sanction

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ רק מנהל יכול לטפל בדיווח.", ephemeral=True)
            return
        report = await db.get_report(self.report_id)
        if not report:
            await interaction.response.send_message("❌ הדיווח לא נמצא.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        sanction_label = None
        if self.action == "approved":
            target, error = await resolve_report_target(self.guild, report["target_user"])
            if error:
                await interaction.followup.send(f"❌ {error}", ephemeral=True)
                return
            try:
                sanction_label = await apply_report_sanction(
                    self.guild, target, self.sanction or "",
                    self.mute_duration.value or "", self.report_id, self.response_text.value,
                )
            except (ValueError, discord.Forbidden, discord.HTTPException) as exc:
                await interaction.followup.send(f"❌ לא ניתן לבצע את הפעולה: {exc}", ephemeral=True)
                return
        status = {"approved": "✅ אושר", "pending": "⏳ בבדיקה", "rejected": "❌ נדחה"}.get(self.action, self.action)
        if sanction_label:
            status += f" — {sanction_label}"
        await db.update_report(self.report_id, status=self.action, admin_response=self.response_text.value)
        try:
            channel = await get_report_log_channel(self.guild)
            if channel and report.get("log_message_id"):
                msg = await channel.fetch_message(report["log_message_id"])
                embed = msg.embeds[0] if msg.embeds else discord.Embed()
                fields = [f for f in embed.fields if f.name not in {"🔖 מצב", "💬 תגובת הצוות", "🛡️ פעולה שננקטה"}]
                embed.clear_fields()
                for f in fields:
                    embed.add_field(name=f.name, value=f.value, inline=f.inline)
                embed.add_field(name="🔖 מצב", value=status, inline=True)
                embed.add_field(name="💬 תגובת הצוות", value=self.response_text.value, inline=False)
                if sanction_label:
                    embed.add_field(name="🛡️ פעולה שננקטה", value=sanction_label, inline=True)
                view = ReportAdminView(self.report_id, self.guild.id)
                if self.action != "pending":
                    view.disable_all_items()
                await msg.edit(embed=embed, view=view)
        except Exception:
            logger.exception("Could not update report log message %s", self.report_id)
        reporter = self.guild.get_member(report["reporter_id"])
        if reporter:
            dm = discord.Embed(title=status, description=f"דיווח #{self.report_id} על **{report['target_user']}**", color=EMBED_COLOR_SUCCESS if self.action == "approved" else EMBED_COLOR_WARNING if self.action == "pending" else EMBED_COLOR_DANGER)
            dm.add_field(name="💬 הודעת הצוות", value=self.response_text.value, inline=False)
            if self.action == "rejected":
                dm.description += "\n\nהצוות לא אישר את הדיווח. אפשר להגיב או לערער בכפתור למטה ולצרף קישור לצילום מסך."
            if sanction_label:
                dm.add_field(name="🛡️ פעולה", value=sanction_label, inline=True)
            dm.set_footer(text=f"דיווח #{self.report_id}")
            try:
                await reporter.send(embed=dm, view=ReportAppealView(self.report_id))
            except discord.Forbidden:
                logger.info("Could not DM reporter for report %s", self.report_id)
        await interaction.followup.send(f"✅ הדיווח עודכן: {status}", ephemeral=True)


class ReportAppealModal(discord.ui.Modal, title="📨 תגובה / ערעור"):
    appeal_text = discord.ui.TextInput(label="תגובה לצוות", style=discord.TextStyle.paragraph, max_length=1000)
    image_url = discord.ui.TextInput(label="קישור לצילום מסך (אופציונלי)", required=False, max_length=500)

    def __init__(self, report_id: int):
        super().__init__()
        self.report_id = report_id

    async def on_submit(self, interaction: discord.Interaction):
        report = await db.get_report(self.report_id)
        if not report or interaction.user.id != report["reporter_id"]:
            await interaction.response.send_message("❌ רק המדווח יכול להגיב לדיווח הזה.", ephemeral=True)
            return
        guild = interaction.client.get_guild(report["guild_id"])
        channel = await get_report_log_channel(guild) if guild else None
        if channel is None:
            await interaction.response.send_message("❌ ערוץ הלוג אינו זמין.", ephemeral=True)
            return
        embed = discord.Embed(title=f"📨 תגובה לדיווח #{self.report_id}", color=EMBED_COLOR_PRIMARY)
        embed.add_field(name="👤 מדווח", value=interaction.user.mention, inline=True)
        embed.add_field(name="🎯 נגד", value=report["target_user"], inline=True)
        embed.add_field(name="📝 תגובה", value=self.appeal_text.value, inline=False)
        image = self.image_url.value.strip()
        if image:
            if not image.startswith(("https://", "http://")):
                await interaction.response.send_message("❌ קישור התמונה צריך להתחיל ב־http:// או https://.", ephemeral=True)
                return
            embed.set_image(url=image)
        embed.set_footer(text=f"תגובה לדיווח #{self.report_id}")
        try:
            await channel.send(embed=embed)
            await db.update_report(self.report_id, appeal_text=self.appeal_text.value, appeal_image=image or None)
        except discord.HTTPException:
            logger.exception("Could not send report reply to log")
            await interaction.response.send_message("❌ לא הצלחתי להעביר את התגובה לצוות.", ephemeral=True)
            return
        await interaction.response.send_message("✅ התגובה נשלחה לצוות.", ephemeral=True)


class ReportAppealView(discord.ui.View):
    def __init__(self, report_id: int):
        super().__init__(timeout=None)
        self.report_id = report_id
        button = discord.ui.Button(label="📨 הוסף תגובה / ערעור", style=discord.ButtonStyle.primary, custom_id=f"report_reply:{report_id}")
        button.callback = self.appeal_button
        self.add_item(button)

    async def appeal_button(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ReportAppealModal(self.report_id))


class ReportAdminView(discord.ui.View):
    def __init__(self, report_id: int, guild: discord.Guild | int):
        super().__init__(timeout=None)
        self.report_id = report_id
        self.guild_id = guild.id if isinstance(guild, discord.Guild) else guild

    async def require_admin(self, interaction: discord.Interaction):
        if interaction.guild_id != self.guild_id or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ רק מנהל השרת יכול לטפל בדיווחים.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ אשר", style=discord.ButtonStyle.success, custom_id="btn_report_approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.require_admin(interaction):
            await interaction.response.send_message("בחר פעולה עבור המשתמש:", view=ReportSanctionView(self.report_id, interaction.guild), ephemeral=True)

    @discord.ui.button(label="⏳ בבדיקה", style=discord.ButtonStyle.secondary, custom_id="btn_report_pending")
    async def pending_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.require_admin(interaction):
            await interaction.response.send_modal(AdminResponseModal(self.report_id, "pending", interaction.guild))

    @discord.ui.button(label="❌ דחה", style=discord.ButtonStyle.danger, custom_id="btn_report_reject")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.require_admin(interaction):
            await interaction.response.send_modal(AdminResponseModal(self.report_id, "rejected", interaction.guild))


class ReportView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="דווח על משתמש", style=discord.ButtonStyle.danger, custom_id="btn_report_open", emoji="🚨")
    async def open_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReportModal())

class VerifyView(discord.ui.View):
    '''
    פאנל האימות הראשי – כולל כפתור אימות מאובטח וכפתור מדריך הוספת הבוט.
    '''

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='אמת את החשבון', style=discord.ButtonStyle.success, custom_id='verify_button_persistent', emoji='🔓')
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message('❌ ניתן לבצע אימות רק בתוך שרת דיסקורד.', ephemeral=True)
            return
        guild = interaction.guild
        member = interaction.user
        blocked = await db.get_blocked_verification(member.id, guild.id)
        if blocked:
            await interaction.response.send_message(f"🚫 אינך יכול לבצע אימות בשרת הזה.\n**סיבה:** {blocked.get('reason') or 'לא נמסרה סיבה.'}", ephemeral=True)
            return
        settings = await db.get_guild_settings(guild.id)
        role_id = settings.get('verified_role_id')
        role = guild.get_role(role_id) if role_id else discord.utils.get(guild.roles, name='מאומת')
        if role and role in member.roles:
            await db.add_verified_user(member.id, guild.id)
            await interaction.response.send_message('✅ אתה כבר מאומת ויש לך את רול האימות.', ephemeral=True)
            return
        if not SETTINGS.CLIENT_ID or not SETTINGS.CLIENT_SECRET or not SETTINGS.REDIRECT_URI:
            await interaction.response.send_message('❌ הגדרות OAuth חסרות. מנהל הבוט צריך להגדיר CLIENT_ID ו־REDIRECT_URI בקובץ .env.', ephemeral=True)
            return
        if interaction.channel:
            await db.update_guild_settings(guild.id, verification_channel_id=interaction.channel.id)
        state = secrets.token_urlsafe(32)
        await db.store_verification_state(state, member.id, guild.id)
        params = {
            'client_id': SETTINGS.CLIENT_ID,
            'redirect_uri': SETTINGS.REDIRECT_URI,
            'response_type': 'code',
            'scope': 'identify',
            'state': state,
            'prompt': 'consent',
        }
        oauth_url = f"https://discord.com/api/oauth2/authorize?{urllib.parse.urlencode(params)}"
        embed = discord.Embed(
            title='✨ השלמת תהליך האימות',
            description='לחץ על הכפתור כדי לעבור לאישור המאובטח של Discord. אחרי האישור תחזור לדיסקורד ותקבל את רול האימות.',
            color=EMBED_COLOR_PRIMARY,
        )
        embed.set_footer(text='קישור האימות תקף ל־10 דקות')
        view = discord.ui.View(timeout=600)
        view.add_item(discord.ui.Button(label='מעבר לאימות ✅', url=oauth_url, style=discord.ButtonStyle.link))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    @discord.ui.button(label='הוסף את הבוט', style=discord.ButtonStyle.secondary, custom_id='btn_add_bot_guide', emoji='🤖')
    async def add_bot_guide_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        '''פותח מדריך מיוחד להוספת הבוט ל-Apps ולשרתים'''
        if not any(role.name == 'גישה לבוט' for role in interaction.user.roles):
            await interaction.response.send_message(
                'על מנת להשתמש בבוט לשרת האישי שלך, תצטרך לקנות את חבילת הבוט.',
                ephemeral=True,
            )
            return

        client_id = SETTINGS.CLIENT_ID
        bot_invite_url = f'https://discord.com/oauth2/authorize?client_id={client_id}&permissions=8&integration_type=0&scope=bot+applications.commands'
        user_app_url = f'https://discord.com/oauth2/authorize?client_id={client_id}&integration_type=1&scope=applications.commands'
        embed = discord.Embed(title='📱 ✦ מדריך הוספת הבוט ל-Apps ולשרתים ✦ 🤖', description="רוצה להוסיף את הבוט לשרת שלך או להשתמש בו באפליקציות שלך בכל מקום בדיסקורד? 🚀\n\n╭──────────────────────────────────────╮\n  ⚙️ **איך מוסיפים את הבוט לשרת או לחשבון?**\n╰──────────────────────────────────────╯\n\n🔹 **אפשרות 1: הוספה לפרופיל האישי (User Apps)**\n✦ לחץ על פרופיל הבוט בדיסקורד.\n✦ לחץ על הכפתור **「 Add App 」** (הוסף אפליקציה).\n✦ בחר 'Use in all servers / DMs' ותוכל להשתמש בפקודות בכל מקום!\n\n🔹 **אפשרות 2: הוספה ישירה לשרת שלך**\n✦ לחץ על הכפתור למטה **「 הוספה לשרת שלי 」**.\n✦ בחר את השרת שבו יש לך הרשאות ניהול ואשר את ההרשאות.\n\n✨ *הבוט כולל מערכת אימות, מעקב הזמנות, התראות בוסטים ועוד!*", color=EMBED_COLOR_PRIMARY)
        embed.set_footer(text='מדריך הרחבות ו-Apps לדיסקורד 🌟')
        guide_view = discord.ui.View()
        guide_view.add_item(discord.ui.Button(label='🔗 הוספה לשרת שלי', url=bot_invite_url, style=discord.ButtonStyle.link, emoji='🌐'))
        guide_view.add_item(discord.ui.Button(label='📱 הוספה ל-Apps שלי', url=user_app_url, style=discord.ButtonStyle.link, emoji='✨'))
        await interaction.response.send_message(embed=embed, view=guide_view, ephemeral=True)


class CloseMessageView(discord.ui.View):
    '''
    כפתור סגירת הודעה שתוקן לחלוטין – מוחק את ההודעה בצורה חלקה ללא שגיאות.
    '''

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='סגור הודעה ✕', style=discord.ButtonStyle.secondary, custom_id='btn_close_response')
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
            await interaction.delete_original_response()
        except Exception:
            try:
                await interaction.response.edit_message(content='🗑️ *ההודעה נסגרה בהצלחה.*', embed=None, view=None)
                return
            except Exception:
                return


class InvitePanelView(discord.ui.View):
    '''
    פאנל ניהול הזמנות עם 4 הכפתורים המלאים וניהול הודעות חכם.
    '''

    def __init__(self):
        super().__init__(timeout=None)

    async def send_or_update(self, interaction: discord.Interaction, embed: discord.Embed):
        view = CloseMessageView()
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
            return
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label='צור קישור 🔗', style=discord.ButtonStyle.success, custom_id='invite_btn_create')
    async def create_invite_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        channel = interaction.channel
        if not guild:
            embed = discord.Embed(title='⚠️ שגיאה', description='ניתן להשתמש בכפתור זה רק בתוך שרת.', color=EMBED_COLOR_DANGER)
            await self.send_or_update(interaction, embed)
            return
        try:
            target_channel = channel
            if isinstance(channel, discord.TextChannel):
                perms = channel.permissions_for(guild.default_role)
                if not perms.view_channel:
                    for ch in guild.text_channels:
                        if not ch.permissions_for(guild.default_role).view_channel:
                            continue
                        if not ch.permissions_for(guild.me).create_instant_invite:
                            continue
                        target_channel = ch
                        break
            invite = await target_channel.create_invite(max_age=0, max_uses=0, unique=True, reason=f'קישור אישי נוצר על ידי {interaction.user.name}')
            await db.save_invite(invite.code, guild.id, interaction.user.id, target_channel.id)
            if hasattr(interaction.client, 'tracker'):
                interaction.client.tracker.add_invite(invite)
            embed = discord.Embed(title='✨ יצרת קישור הזמנה בהצלחה! ✨', description=f'👤 {interaction.user.mention}, הקישור שלך מוכן:\n\n`{invite.url}`', color=EMBED_COLOR_SUCCESS)
            await self.send_or_update(interaction, embed)
        except Exception as e:
            embed = discord.Embed(title='❌ שגיאה', description=f'שגיאה ביצירת קישור: {e}', color=EMBED_COLOR_DANGER)
            await self.send_or_update(interaction, embed)

    @discord.ui.button(label='ראה קישורים 📋', style=discord.ButtonStyle.secondary, custom_id='invite_btn_view')
    async def view_invites_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user_id = interaction.user.id
        user_invites = await db.get_user_invites(guild.id, user_id, only_active=True)
        if not user_invites:
            embed = discord.Embed(title='📋 הקישורים שלך', description='❌ לא נמצאו קישורים פעילים כרגע.', color=EMBED_COLOR_WARNING)
            await self.send_or_update(interaction, embed)
            return
        guild_invites_dict = {}
        try:
            guild_invites = await guild.invites()
        except Exception:
            pass
        try:
            guild_invites_dict = {inv.code: inv for inv in guild_invites}
        except Exception:
            pass
        lines = []
        for row in user_invites:
            code = row['code']
            uses = guild_invites_dict[code].uses if code in guild_invites_dict else await db.get_invite_joins_count(guild.id, code)
            lines.append(f'🔹 https://discord.gg/{code} ➔ 👥 **{uses}** אנשים נכנסו')
        embed = discord.Embed(title='📋 הקישורים הפעילים שלך', description='\n'.join(lines), color=EMBED_COLOR_PRIMARY)
        await self.send_or_update(interaction, embed)

    @discord.ui.button(label='כמה אנשים נכנסו? 📊', style=discord.ButtonStyle.primary, custom_id='invite_btn_stats')
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user_id = interaction.user.id
        db_joins = await db.get_user_total_joins(guild.id, user_id)
        try:
            live_uses = sum((inv.uses for inv in await guild.invites() if inv.inviter or inv.inviter.id == user_id))
            total_joins = max(db_joins, live_uses)
        except Exception:
            total_joins = db_joins
        embed = discord.Embed(title='📊 סטטיסטיקת ההזמנות שלך', description=f'👥 סך הכל אנשים שנכנסו דרכך: **{total_joins}** משתמשים!', color=EMBED_COLOR_WARNING)
        await self.send_or_update(interaction, embed)

    @discord.ui.button(label='אפס את כל הקישורים 🗑️', style=discord.ButtonStyle.danger, custom_id='invite_btn_reset')
    async def reset_invites_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user_id = interaction.user.id
        user_invites = await db.get_user_invites(guild.id, user_id, only_active=True)
        user_codes = {row['code'] for row in user_invites}
        if not user_codes:
            embed = discord.Embed(title='ℹ️ אין קישורים לאיפוס', description='לא נמצאו קישורים פעילים למחיקה.', color=EMBED_COLOR_WARNING)
            await self.send_or_update(interaction, embed)
            return
        deleted_count = 0
        try:
            async for invite in guild.invites():
                if invite.code in user_codes:
                    await invite.delete(reason='איפוס קישורים אישיים')
                    deleted_count += 1
                    if hasattr(interaction.client, 'tracker'):
                        interaction.client.tracker.remove_invite(invite)
        except Exception:
            pass
        db_deactivated = await db.deactivate_user_invites(guild.id, user_id)
        total_affected = max(deleted_count, db_deactivated)
        embed = discord.Embed(title='🗑️ הקישורים האישיים שלך אופסו בהצלחה!', description=f'✅ **{total_affected}** מהקישורים האישיים שלך בוטלו ונמחקו לחלוטין.\n(שאר הקישורים של שאר החברים לא נפגעו).', color=EMBED_COLOR_DANGER)
        await self.send_or_update(interaction, embed)


intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.invites = True
intents.presences = True
intents.message_content = True

class UnifiedBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=None)
        self.tracker = InviteTracker(self)
        self.http_session = None
        self.web_runner = None
        self.stats_refresh_tasks: Dict[int, asyncio.Task] = {}
        self.command_revocations: set[tuple[int, int]] = set()

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession()
        await db.init_db()
        self.add_view(InvitePanelView())
        self.add_view(CloseMessageView())
        self.add_view(VerifyView())
        self.add_view(ReportView())
        for report in await db.get_reports_with_log_messages():
            self.add_view(ReportAdminView(report['id'], report['guild_id']), message_id=report['log_message_id'])
            self.add_view(ReportAppealView(report['id']))
        asyncio.create_task(self.start_oauth_server())
        try:
            synced = await self.tree.sync()
            logger.info(f'⚡ סונכרנו בהצלחה {len(synced)} פקודות סלאש.')
        except Exception as e:
            logger.error(f'שגיאה בסנכרון פקודות סלאש: {e}')

    async def start_oauth_server(self):
        '''שרת אינטרנט אסינכרוני המטפל בסיום האימות בדפדפן'''

        app = web.Application()
        def get_success_html(username: str, guild_name: str) -> str:
            return f'<!DOCTYPE html>\n<html lang="he" dir="rtl">\n<head>\n    <meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n    <title>אימות הצליח | {guild_name}</title>\n    <style>\n        body {{\n            font-family: \'Segoe UI\', Tahoma, Geneva, Verdana, sans-serif;\n            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);\n            color: #f8fafc;\n            display: flex;\n            align-items: center;\n            justify-content: center;\n            min-height: 100vh;\n            margin: 0;\n            padding: 20px;\n        }}\n        .card {{\n            background: rgba(30, 41, 59, 0.85);\n            backdrop-filter: blur(12px);\n            border: 1px solid rgba(255, 255, 255, 0.1);\n            border-radius: 20px;\n            padding: 40px 30px;\n            max-width: 480px;\n            width: 100%;\n            text-align: center;\n            box-shadow: 0 20px 40px rgba(0,0,0,0.4);\n        }}\n        .icon {{\n            width: 80px;\n            height: 80px;\n            background: #22c55e;\n            color: white;\n            font-size: 42px;\n            display: flex;\n            align-items: center;\n            justify-content: center;\n            border-radius: 50%;\n            margin: 0 auto 20px;\n            box-shadow: 0 0 25px rgba(34, 197, 94, 0.5);\n        }}\n        h1 {{\n            font-size: 26px;\n            margin-bottom: 10px;\n            color: #ffffff;\n        }}\n        p {{\n            font-size: 16px;\n            color: #cbd5e1;\n            line-height: 1.6;\n            margin: 10px 0;\n        }}\n        .badge {{\n            display: inline-block;\n            background: rgba(88, 101, 242, 0.2);\n            color: #818cf8;\n            border: 1px solid rgba(88, 101, 242, 0.4);\n            padding: 6px 14px;\n            border-radius: 20px;\n            font-weight: bold;\n            margin: 15px 0;\n        }}\n        .footer-note {{\n            font-size: 14px;\n            color: #94a3b8;\n            margin-top: 25px;\n            border-top: 1px solid rgba(255, 255, 255, 0.08);\n            padding-top: 15px;\n        }}\n    </style>\n</head>\n<body>\n    <div class="card">\n        <div class="icon">✓</div>\n        <h1>האימות הושלם בהצלחה!</h1>\n        <div class="badge">שלום, {username} 👋</div>\n        <p>חשבונך אומת בהצלחה בשרת <strong>{guild_name}</strong>.</p>\n        <p>הרול <strong>מאומת</strong> הוענק לחשבונך וכעת יש לך גישה מלאה לכל ערוצי השרת!</p>\n        <div class="footer-note">\n            אתה יכול לסגור חלון זה בבטחה ולחזור ל-Discord. 🚀\n        </div>\n    </div>\n</body>\n</html>'

        def get_error_html(title: str, message: str) -> str:
            return f'<!DOCTYPE html>\n<html lang="he" dir="rtl">\n<head>\n    <meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n    <title>שגיאת אימות</title>\n    <style>\n        body {{\n            font-family: \'Segoe UI\', Tahoma, Geneva, Verdana, sans-serif;\n            background: linear-gradient(135deg, #1e1b2e 0%, #111827 100%);\n            color: #f8fafc;\n            display: flex;\n            align-items: center;\n            justify-content: center;\n            min-height: 100vh;\n            margin: 0;\n            padding: 20px;\n        }}\n        .card {{\n            background: rgba(30, 41, 59, 0.85);\n            backdrop-filter: blur(12px);\n            border: 1px solid rgba(239, 68, 68, 0.2);\n            border-radius: 20px;\n            padding: 40px 30px;\n            max-width: 480px;\n            width: 100%;\n            text-align: center;\n            box-shadow: 0 20px 40px rgba(0,0,0,0.4);\n        }}\n        .icon {{\n            width: 80px;\n            height: 80px;\n            background: #ef4444;\n            color: white;\n            font-size: 42px;\n            display: flex;\n            align-items: center;\n            justify-content: center;\n            border-radius: 50%;\n            margin: 0 auto 20px;\n            box-shadow: 0 0 25px rgba(239, 68, 68, 0.5);\n        }}\n        h1 {{\n            font-size: 24px;\n            margin-bottom: 10px;\n            color: #fca5a5;\n        }}\n        p {{\n            font-size: 16px;\n            color: #cbd5e1;\n            line-height: 1.6;\n        }}\n    </style>\n</head>\n<body>\n    <div class="card">\n        <div class="icon">✕</div>\n        <h1>{title}</h1>\n        <p>{message}</p>\n        <p style="font-size: 14px; color: #94a3b8; margin-top: 20px;">\n            אנא חזור לדיסקורד ולחץ שוב על כפתור האימות כדי לנסות מחדש.\n        </p>\n    </div>\n</body>\n</html>'

        async def oauth_callback_handler(request: web.Request):
            params = request.rel_url.query
            if params.get('error'):
                return web.Response(text=get_error_html('האימות בוטל', 'האישור בוטל על ידך בדיסקורד. כדי לקבל גישה יש ללחוץ שוב ולאשר.'), content_type='text/html', status=400)
            code = params.get('code')
            state = params.get('state')
            if not code or not state:
                return web.Response(text=get_error_html('פרמטרים חסרים', 'הבקשה אינה מכילה קוד אימות תקף.'), content_type='text/html', status=400)
            record = await db.get_verification_state(state)
            if not record:
                return web.Response(text=get_error_html('קישור פג תוקף', 'קישור האימות אינו תקף או שפג תוקפו (מוגבל ל-10 דקות). נסה ללחוץ שוב על הכפתור בדיסקורד.'), content_type='text/html', status=400)
            user_id = record['user_id']
            guild_id = record['guild_id']
            token_url = 'https://discord.com/api/oauth2/token'
            data = {'client_id': SETTINGS.CLIENT_ID, 'client_secret': SETTINGS.CLIENT_SECRET, 'grant_type': 'authorization_code', 'code': code, 'redirect_uri': SETTINGS.REDIRECT_URI}
            try:
                async with self.http_session.post(token_url, data=data) as resp:
                    token_data = await resp.json()
            except Exception as e:
                logger.error(f'שגיאה בהתחברות ל-Token API: {e}')
                return web.Response(text=get_error_html('שגיאת תקשורת', 'אירעה שגיאה בתקשורת עם Discord. נסה שוב בעוד מספר דקות.'), content_type='text/html', status=500)
            access_token = token_data.get('access_token')
            if not access_token:
                await db.log_verification_event(user_id, guild_id, 'failed', f'Token error: {token_data.get('error_description')}')
                return web.Response(text=get_error_html('כישלון בהרשאה', 'לא ניתן היה לקבל אישור מ-Discord. נסה ללחוץ שוב על הכפתור בדיסקורד.'), content_type='text/html', status=400)
            user_url = 'https://discord.com/api/users/@me'
            headers = {'Authorization': f'Bearer {access_token}'}
            try:
                async with self.http_session.get(user_url, headers=headers) as resp:
                    user_data = await resp.json()
            except Exception as e:
                logger.error(f'שגיאה בקבלת נתוני משתמש: {e}')
                return web.Response(text=get_error_html('שגיאת זיהוי', 'לא ניתן היה לאמת את פרטי המשתמש.'), content_type='text/html', status=500)
            discord_user_id = int(user_data.get('id', 0))
            if discord_user_id != user_id:
                await db.log_verification_event(user_id, guild_id, 'tamper_detected', f'Mismatch: expected {user_id}, got {discord_user_id}')
                return web.Response(text=get_error_html('אי-התאמה בחשבון', 'החשבון שאושר בדפדפן אינו החשבון שלחץ על הכפתור בשרת!'), content_type='text/html', status=403)
            username = user_data.get('username', 'חבר קהילה')
            guild = self.get_guild(guild_id)
            if not guild:
                for g in self.guilds:
                    if not g.id == guild_id:
                        continue
                    guild = g
                    break
            if not guild:
                await db.log_verification_event(user_id, guild_id, 'failed', 'Guild not found')
                return web.Response(text=get_error_html('שגיאה', 'הבוט אינו מחובר לשרת היעד.'), content_type='text/html', status=404)
            member = guild.get_member(user_id)
            if not member:
                try:
                    member = await guild.fetch_member(user_id)
                except Exception:
                    member = None
            if not member:
                await db.log_verification_event(user_id, guild_id, 'failed', 'Member not in guild')
                return web.Response(text=get_error_html('משתמש לא נמצא', 'המשתמש אינו חבר בשרת זה.'), content_type='text/html', status=404)
            settings = await db.get_guild_settings(guild_id)
            role_id = settings.get('verified_role_id')
            role = guild.get_role(role_id) if role_id else discord.utils.get(guild.roles, name='מאומת')
            if not role:
                try:
                    role = await guild.create_role(name='מאומת', reason='תפקיד אימות אוטומטי ע״י הבוט')
                    await db.update_guild_settings(guild_id, verified_role_id=role.id)
                except Exception:
                    pass
            if role:
                try:
                    await member.add_roles(role, reason='אימות הושלם בהצלחה')
                except Exception as ex:
                    logger.error(f'שגיאת הרשאות בהוספת רול: {ex}')
                    await db.log_verification_event(user_id, guild_id, 'role_failed', f'Permission error: {ex}')
                    return web.Response(text=get_error_html('שגיאת הרשאות', 'האימות הצליח אך לבוט חסרות הרשאות להעניק את הרול (ודא שרול הבוט ממוקם מעל רול המאומתים).'), content_type='text/html', status=500)
            await db.add_verified_user(user_id, guild_id)
            await apply_verification_access(guild)
            await db.log_verification_event(user_id, guild_id, 'success', f'אומת בהצלחה: {username}')
            await db.delete_verification_state(state)
            try:
                dm_embed = discord.Embed(title='🎉 החשבון שלך אומת בהצלחה!', description=f'שלום {member.mention}, תהליך האימות בשרת **{guild.name}** הסתיים בהצלחה וקיבלת את הרול **{role.name if role else 'מאומת'}**!', color=EMBED_COLOR_SUCCESS)
                await member.send(embed=dm_embed)
            except Exception:
                pass
            v_chan_id = settings.get('verification_channel_id')
            v_chan = guild.get_channel(v_chan_id) if v_chan_id else None
            if v_chan:
                try:
                    v_embed = discord.Embed(description='אומתת בהצלחה! 👍 עכשיו תוכל להיות ממבר בשרת! ✅', color=EMBED_COLOR_SUCCESS)
                    v_embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
                    await v_chan.send(content=f'{member.mention}', embed=v_embed)
                except Exception as ex:
                    logger.warning(f'לא ניתן לשלוח הודעה בערוץ האימות: {ex}')
            log_chan_id = settings.get('log_channel_id')
            if log_chan_id:
                log_chan = guild.get_channel(log_chan_id)
                if log_chan:
                    log_embed = discord.Embed(title='✅ חבר חדש אומת בהצלחה', description=f'{member.mention} השלים אימות בהצלחה.', color=EMBED_COLOR_SUCCESS)
                    log_embed.set_thumbnail(url=member.display_avatar.url)
                    log_embed.add_field(name='שם משתמש', value=f'`{username}`', inline=True)
                    log_embed.add_field(name='מזהה (ID)', value=f'`{user_id}`', inline=True)
                    if role:
                        log_embed.add_field(name='רול שהוענק', value=role.mention, inline=False)
                    await log_chan.send(embed=log_embed)
            return web.Response(text=get_success_html(username, guild.name), content_type='text/html')

        parsed_uri = urlparse(SETTINGS.REDIRECT_URI)
        server_port = SETTINGS.OAUTH_BIND_PORT or parsed_uri.port or 8080
        server_host = SETTINGS.OAUTH_BIND_HOST or '0.0.0.0'
        route_path = parsed_uri.path if parsed_uri.path else '/callback'
        app.router.add_get(route_path, oauth_callback_handler)
        if route_path != '/callback':
            app.router.add_get('/callback', oauth_callback_handler)
        if route_path != '/oauth/callback':
            app.router.add_get('/oauth/callback', oauth_callback_handler)
        self.web_runner = web.AppRunner(app)
        await self.web_runner.setup()
        site = web.TCPSite(self.web_runner, server_host, server_port)
        await site.start()
        logger.info('OAuth callback server listening on %s:%s%s', server_host, server_port, route_path)

    async def close(self):
        if self.http_session:
            await self.http_session.close()
        if self.web_runner:
            await self.web_runner.cleanup()
        await super().close()


bot = UnifiedBot()

@bot.event
async def on_ready():
    logger.info('═══════════════════════════════════════════════════')
    logger.info(f'🤖 הבוט מחובר בהצלחה בתור: {bot.user.name} (ID: {bot.user.id})')
    logger.info(f'🌐 שרתים מחוברים: {len(bot.guilds)}')
    logger.info('═══════════════════════════════════════════════════')
    await bot.tracker.sync_all_guilds()
    for guild in bot.guilds:
        await refresh_stats_channels(guild)
        await apply_verification_access(guild)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='בקהילה ובאימותים 🛡️ | /panel'))

@bot.event
async def on_guild_join(guild: discord.Guild):
    await bot.tracker.sync_guild(guild)
    await refresh_stats_channels(guild)
    await apply_verification_access(guild)

@bot.event
async def on_invite_create(invite: discord.Invite):
    bot.tracker.add_invite(invite)

@bot.event
async def on_invite_delete(invite: discord.Invite):
    bot.tracker.remove_invite(invite)

@bot.event
async def on_member_join(member: discord.Member):
    schedule_stats_refresh(member.guild)
    if member.bot:
        return
    guild = member.guild
    used_invite = await bot.tracker.find_used_invite(member)
    invite_code = used_invite.code if used_invite else None
    inviter_id = used_invite.inviter.id if used_invite and used_invite.inviter else None
    await db.record_join(guild.id, invite_code, inviter_id, member.id)
    target_channel = None
    saved_channel_id = await db.get_welcome_channel(guild.id)
    if saved_channel_id:
        target_channel = guild.get_channel(saved_channel_id)
    if not target_channel:
        for ch in guild.text_channels:
            if not any((k in ch.name.lower() for k in ('welcome', 'ברוכים', 'שלום', 'הצטרפות'))):
                continue
            target_channel = ch
            break
    if not target_channel:
        target_channel = guild.system_channel or (guild.text_channels[0] if guild.text_channels else None)
    if not target_channel:
        return
    welcome_file = None
    try:
        card_buffer = await generate_welcome_card(member)
        welcome_file = discord.File(fp=card_buffer, filename='welcome.png')
    except Exception as e:
        logger.warning(f'שגיאה ביצירת Welcome Card: {e}')
    joined_str = f'<t:{int(member.joined_at.timestamp())}:f>' if member.joined_at else 'עכשיו'
    embed = discord.Embed(title='🎉 ברוך הבא לשרת!', description=f'👋 היי {member.mention}, שמחים לראות אותך כאן!\n\n✨ אנחנו מקווים שתיהנה מהשרת, תכיר אנשים חדשים ותהיה חלק מהקהילה שלנו.\n\n📜 אל תשכח לעבור על חוקי השרת ולהשלים אימות בערוץ האימות.', color=EMBED_COLOR_PRIMARY)
    embed.add_field(name='🎉 מספר חבר', value=f'החבר ה־**{guild.member_count}**', inline=True)
    embed.add_field(name='📅 הצטרפות ב', value=joined_str, inline=True)
    if used_invite and used_invite.inviter:
        inviter_total = await db.get_user_total_joins(guild.id, inviter_id)
        embed.add_field(name='🎁 הוזמן על ידי', value=f'{used_invite.inviter.mention} (סה"כ: {inviter_total})', inline=False)
    else:
        embed.add_field(name='💙 איחולים', value='שיהיה לך בהצלחה ותהנה מהשהייה!', inline=False)
    if welcome_file:
        embed.set_image(url='attachment://welcome.png')
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    try:
        if welcome_file:
            await target_channel.send(content=f'👋 ברוך הבא, {member.mention}!', embed=embed, file=welcome_file)
            return
        await target_channel.send(content=f'👋 ברוך הבא, {member.mention}!', embed=embed)
    except Exception as e:
        logger.error(f'שגיאה בשליחת הודעת ברוך הבא: {e}')

@bot.event
async def on_member_remove(member: discord.Member):
    schedule_stats_refresh(member.guild)
    if member.bot:
        return
    guild = member.guild
    target_channel = None
    saved_channel_id = await db.get_leave_channel(guild.id)
    if saved_channel_id:
        target_channel = guild.get_channel(saved_channel_id)
    if not target_channel:
        welcome_chan_id = await db.get_welcome_channel(guild.id)
        if welcome_chan_id:
            target_channel = guild.get_channel(welcome_chan_id)
    if not target_channel:
        for ch in guild.text_channels:
            if not any((k in ch.name.lower() for k in ('leave', 'עזיבה', 'פרידה', 'goodbye'))):
                continue
            target_channel = ch
            break
    if not target_channel:
        target_channel = guild.system_channel or (guild.text_channels[0] if guild.text_channels else None)
    if not target_channel:
        return
    leave_file = None
    try:
        card_buffer = await generate_leave_card(member)
        leave_file = discord.File(fp=card_buffer, filename='leave.png')
    except Exception as e:
        logger.warning(f'שגיאה ביצירת Leave Card: {e}')
    embed = discord.Embed(title='👋 להתראות, נתראה בקרוב!', description=f'😢 חבל לנו לראות אותך עוזב, **{member.display_name}**...\n\n✨ תודה שהיית חלק מהקהילה שלנו! מקווים לראות אותך שוב בעתיד.', color=EMBED_COLOR_DANGER)
    embed.add_field(name='👥 נשארו בשרת', value=f'החבר ה־**{guild.member_count}**', inline=True)
    if member.joined_at:
        joined_str = f'<t:{int(member.joined_at.timestamp())}:R>'
        embed.add_field(name='📅 היה איתנו מאז', value=joined_str, inline=True)
    if leave_file:
        embed.set_image(url='attachment://leave.png')
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=f'{guild.name} • שער הפרידה והעזיבה', icon_url=guild.icon.url if guild.icon else None)
    try:
        if leave_file:
            await target_channel.send(content=f'👋 **להתראות, {member.name}!**', embed=embed, file=leave_file)
            return
        await target_channel.send(content=f'👋 **להתראות, {member.name}!**', embed=embed)
    except Exception as e:
        logger.error(f'שגיאה בשליחת הודעת עזיבה: {e}')

async def send_boost_announcement(guild: discord.Guild, booster: discord.Member):
    '''שולח הודעת בוסט מעוצבת ומרשימה בערוץ המוגדר'''

    settings = await db.get_guild_settings(guild.id)
    boost_chan_id = settings.get('boost_channel_id')
    target_channel = guild.get_channel(boost_chan_id) if boost_chan_id else guild.system_channel
    if not target_channel:
        for ch in guild.text_channels:
            if not any((k in ch.name.lower() for k in ('boost', 'בוסט', 'תודות', 'general', 'ראשי'))):
                continue
            target_channel = ch
            break
    if not target_channel:
        return
    embed = discord.Embed(title='🚀 ✦ בוסט חדש ומטורף לשרת! ✦ 💎', description=f'╭────────────────────────────────────────╮\n  💜 **תודה ענקית על הבוסט שלך!** 💜\n╰────────────────────────────────────────╯\n\n✨ משתמש יקר: {booster.mention}\n💎 תודה רבה על שחיזקת את השרת שלנו עם Server Boost! בזכותך הקהילה שלנו מתקדמת וצומחת! 🌟\n\n📊 **סטטיסטיקת הבוסטים של השרת:**\n✦ **סה"כ בוסטים:** `{guild.premium_subscription_count}` בוסטים 🚀\n✦ **רמת השרת (Tier):** `רמה {guild.premium_tier}` 🏆\n\n👑 **ההטבות שקיבלת:**\n✦ רול בוסטר זוהר ואקסקלוסיבי בשרת!\n✦ גישה לאימוג\'ים וסטיקרים מיוחדים!\n✦ הערכה ענקית מכל חברי הקהילה וההנהלה! 💜', color=EMBED_COLOR_BOOST)
    embed.set_thumbnail(url=booster.display_avatar.url)
    if booster.avatar:
        embed.set_image(url=booster.display_avatar.url)
    embed.set_footer(text=f'{guild.name} • תודה לכל הבוסטרים האלופים! 🚀', icon_url=guild.icon.url if guild.icon else None)
    try:
        await target_channel.send(content=f'🚀🎉 **בוסט חדש הגיע! תודה ל-{booster.mention}!**', embed=embed)
    except Exception as e:
        logger.error(f'שגיאה בשליחת הודעת בוסט: {e}')

async def find_role_removal_reason(member: discord.Member, role: discord.Role):
    try:
        async for entry in member.guild.audit_logs(limit=8, action=discord.AuditLogAction.member_role_update):
            if entry.target and entry.target.id == member.id and datetime.now().timestamp() - entry.created_at.timestamp() < 20:
                before_roles = getattr(entry.before, "roles", [])
                after_roles = getattr(entry.after, "roles", [])
                if role in before_roles and role not in after_roles:
                    return entry.user, entry.reason or "לא נמסרה סיבה"
    except (discord.Forbidden, discord.HTTPException):
        pass
    return None, "הרול הוסר ידנית"

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    schedule_stats_refresh(after.guild, 5)
    settings = await db.get_guild_settings(after.guild.id)
    verified_role = after.guild.get_role(settings.get("verified_role_id") or 0)
    if verified_role and verified_role in before.roles and verified_role not in after.roles:
        key = (after.guild.id, after.id)
        if key in bot.command_revocations:
            bot.command_revocations.discard(key)
        else:
            await db.remove_verified_user(after.id, after.guild.id)
            actor, reason = await find_role_removal_reason(after, verified_role)
            try:
                await after.send(f"ℹ️ רול האימות שלך הוסר בשרת **{after.guild.name}**.\n**סיבה:** {reason}" + (f"\n**על ידי:** {actor}" if actor else ""))
            except discord.Forbidden:
                pass
    if not before.premium_since and after.premium_since:
        await send_boost_announcement(after.guild, after)

@bot.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    if before.status != after.status:
        schedule_stats_refresh(after.guild, 8)

@bot.event
async def on_guild_channel_create(channel: discord.abc.GuildChannel):
    await apply_verification_access(channel.guild, channel)

@bot.event
async def on_message(message: discord.Message):
    boost_types = discord.MessageType.premium_guild_subscription, discord.MessageType.premium_guild_tier_1, discord.MessageType.premium_guild_tier_2, discord.MessageType.premium_guild_tier_3
    if message.type in boost_types and message.guild and isinstance(message.author, discord.Member):
        await send_boost_announcement(message.guild, message.author)
    await bot.process_commands(message)

@bot.tree.command(name='verify_setup', description='שולח את פאנל האימות המעוצב לערוץ הנוכחי')
@app_commands.checks.has_permissions(administrator=True)
async def verify_setup_slash(interaction: discord.Interaction):
    embed = discord.Embed(title='👑 ✦ שער האימות והאבטחה ✦ 👑', description='╭───────────────────────────────╮\n  👋 **ברוכים הבאים לשרת שלנו!**\n╰───────────────────────────────╯\n\n🛡️ **למה חובה לבצע אימות?**\n✦ **קהילה נקייה ובטוחה:** הגנה מלאה על השרת מפני בוטים, ספאמרים ורמאים.\n✦ **גישה מלאה לשרת:** קבלת גישה מיידית לכל החדרים, הדיונים, ההגרלות והאירועים!\n✦ **חוויית קהילה אקסקלוסיבית:** זיהוי מהיר שמוודא שאתה משתמש אמיתי.\n\n⚡ **איך מאמתים את החשבון?**\n1️⃣ לוחצים על הכפתור הירוק למטה **「 🔓 אמת את החשבון 」**.\n2️⃣ בחלון שייפתח לוחצים על **「 מעבר לאימות ✅ 」**.\n3️⃣ מאשרים את הבדיקה הקצרה של דיסקורד – וזהו, אתם בפנים!\n\n> 💎 *לחיצה על הכפתור מעניקה את רול האימות באופן מיידי!*', color=EMBED_COLOR_PRIMARY)
    embed.set_footer(text=f'{interaction.guild.name} • מערכת אבטחה ואימות קהילתית ✨')
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    await db.update_guild_settings(interaction.guild.id, verification_channel_id=interaction.channel.id)
    await interaction.channel.send(embed=embed, view=VerifyView())
    await interaction.response.send_message('✅ פאנל האימות נשלח בהצלחה!', ephemeral=True)

@bot.tree.command(name='verify_status', description='בדיקת סטטוס האימות של משתמש')
@app_commands.describe(user='המשתמש לבדיקה (ברירת מחדל: אתה)')
async def verify_status_slash(interaction: discord.Interaction, user: Optional[discord.Member]=None):
    target = user or interaction.user
    guild_id = interaction.guild.id
    status = await db.get_user_verification(target.id, guild_id)
    settings = await db.get_guild_settings(guild_id)
    role = interaction.guild.get_role(settings['verified_role_id']) or discord.utils.get(interaction.guild.roles, name='מאומת')
    has_role = role in target.roles if role else False
    embed = discord.Embed(title=f'📋 סטטוס אימות עבור {target.display_name}', color=EMBED_COLOR_SUCCESS if status else EMBED_COLOR_DANGER)
    embed.set_thumbnail(url=target.display_avatar.url)
    if status:
        verified_time = datetime.fromtimestamp(status['verified_at']).strftime('%d/%m/%Y %H:%M:%S')
        embed.add_field(name='🔹 סטטוס במערכת', value='✅ **מאומת רשמי**', inline=False)
        embed.add_field(name='🕒 זמן אימות', value=verified_time, inline=False)
        embed.add_field(name='🎭 רול בשרת', value='✅ קיים' if has_role else '⚠️ רול חסר', inline=False)
    else:
        embed.add_field(name='🔹 סטטוס במערכת', value='❌ **לא מאומת**', inline=False)
        embed.add_field(name='🎭 רול בשרת', value='רול קיים ללא רישום' if has_role else 'ללא רול', inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name='verify_config', description='הגדרת רול המאומתים וערוץ האימות של השרת')
@app_commands.describe(role='רול המאומתים להענקה', channel='ערוץ האימות')
@app_commands.checks.has_permissions(administrator=True)
async def verify_config_slash(interaction: discord.Interaction, role: Optional[discord.Role]=None, channel: Optional[discord.TextChannel]=None):
    guild_id = interaction.guild.id
    r_id = role.id if role else None
    c_id = channel.id if channel else None
    await db.update_guild_settings(guild_id, verified_role_id=r_id, verification_channel_id=c_id)
    settings = await db.get_guild_settings(guild_id)
    embed = discord.Embed(title='⚙️ הגדרות אימות עודכנו בהצלחה', color=EMBED_COLOR_SUCCESS)
    embed.add_field(name='🎭 רול מאומתים', value=f'<@&{settings['verified_role_id']}>' if settings['verified_role_id'] else 'לא הוגדר', inline=False)
    embed.add_field(name='📢 ערוץ אימות', value=f'<#{settings['verification_channel_id']}>' if settings['verification_channel_id'] else 'לא הוגדר', inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name='verify_block', description='חוסם משתמש מהשלמת אימות בשרת')
@app_commands.checks.has_permissions(administrator=True)
async def verify_block_slash(interaction: discord.Interaction, user: discord.Member, reason: str):
    await db.block_user_verification(user.id, interaction.guild.id, reason, interaction.user.id)
    try:
        await user.send(f'🚫 נחסמת מהשלמת אימות בשרת **{interaction.guild.name}**.\n**סיבה:** {reason}')
    except discord.Forbidden:
        pass
    await interaction.response.send_message(f'✅ {user.mention} נחסם מאימות. סיבה: {reason}', ephemeral=True)

@bot.tree.command(name='verify_unblock', description='מסיר חסימה מאימות')
@app_commands.checks.has_permissions(administrator=True)
async def verify_unblock_slash(interaction: discord.Interaction, user: discord.Member):
    await db.unblock_user_verification(user.id, interaction.guild.id)
    try:
        await user.send(f'✅ החסימה שלך מהשלמת אימות בשרת **{interaction.guild.name}** הוסרה. אפשר לנסות שוב.')
    except discord.Forbidden:
        pass
    await interaction.response.send_message(f'✅ החסימה של {user.mention} הוסרה.', ephemeral=True)

@bot.tree.command(name='lock_unverified_channels', description='מציג ללא מאומתים רק את ערוצי האימות והברוכים הבאים')
@app_commands.checks.has_permissions(administrator=True)
async def lock_unverified_channels_slash(interaction: discord.Interaction, enabled: bool = True):
    await interaction.response.defer(ephemeral=True)
    await db.set_verification_access_locked(interaction.guild.id, enabled)
    if enabled:
        changed = await apply_verification_access(interaction.guild)
        await interaction.followup.send(f'✅ הגבלת הערוצים הופעלה. עודכנו {changed} ערוצים. ודא שהוגדרו ערוץ אימות וערוץ ברוכים הבאים.', ephemeral=True)
    else:
        await interaction.followup.send('✅ מצב ההגבלה כובה. הרשאות הערוצים לא שוחזרו אוטומטית; יש לשנותן ידנית בשרת.', ephemeral=True)

@bot.tree.command(name='give_access', description='נותן למשתמש את רול גישה לבוט')
@app_commands.checks.has_permissions(administrator=True)
async def give_access_slash(interaction: discord.Interaction, user: discord.Member):
    role = discord.utils.get(interaction.guild.roles, name=BOT_ACCESS_ROLE_NAME)
    if role is None:
        await interaction.response.send_message(f'❌ לא נמצא רול בשם **{BOT_ACCESS_ROLE_NAME}**.', ephemeral=True)
        return
    try:
        await user.add_roles(role, reason=f'גישה לבוט ניתנה על ידי {interaction.user}')
    except discord.Forbidden:
        await interaction.response.send_message('❌ הבוט לא יכול להעניק את הרול. בדוק Manage Roles ומיקום הרול.', ephemeral=True)
        return
    await interaction.response.send_message(f'✅ רול {role.mention} ניתן ל־{user.mention}.', ephemeral=True)

@bot.tree.command(name='set_report_channel', description='מגדיר את ערוץ הלוג לדיווחים')
@app_commands.checks.has_permissions(administrator=True)
async def set_report_channel_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    await db.set_report_channel(interaction.guild.id, channel.id)
    await interaction.response.send_message(f'✅ דיווחים יישלחו אל {channel.mention}.', ephemeral=True)

@bot.tree.command(name='report_setup', description='שולח פאנל דיווח על משתמש')
@app_commands.checks.has_permissions(administrator=True)
async def report_setup_slash(interaction: discord.Interaction):
    embed = discord.Embed(title='🚨 דיווח על משתמש', description='לחץ על הכפתור כדי לדווח לצוות. מלא את שם המשתמש, הסיבה ותיאור מפורט. הדיווח יישלח לצוות באופן פרטי.', color=EMBED_COLOR_PRIMARY)
    await interaction.channel.send(embed=embed, view=ReportView())
    await interaction.response.send_message('✅ פאנל הדיווחים נשלח.', ephemeral=True)
@bot.tree.command(name='verify_logs', description='הגדרת ערוץ תיעוד ולוגים לאימות')
@app_commands.describe(channel='ערוץ הלוגים')
@app_commands.checks.has_permissions(administrator=True)
async def verify_logs_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    await db.update_guild_settings(interaction.guild.id, log_channel_id=channel.id)
    embed = discord.Embed(title='🧾 ערוץ לוגים הוגדר בהצלחה', description=f'כל אירועי האימות והביטולים יתועדו בערוץ: {channel.mention}', color=EMBED_COLOR_PRIMARY)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name='verify_revoke', description='ביטול אימות של משתמש והסרת הרול (מנהלים בלבד)')
@app_commands.describe(user='המשתמש לביטול', reason='סיבת הביטול')
@app_commands.checks.has_permissions(administrator=True)
async def verify_revoke_slash(interaction: discord.Interaction, user: discord.Member, reason: Optional[str]='בוטל ע"י מנהל'):
    guild_id = interaction.guild.id
    settings = await db.get_guild_settings(guild_id)
    role = interaction.guild.get_role(settings['verified_role_id']) or discord.utils.get(interaction.guild.roles, name='מאומת')
    if role and role in user.roles:
        try:
            bot.command_revocations.add((guild_id, user.id))
            await user.remove_roles(role, reason=f'אימות בוטל: {reason}')
            async def clear_revocation_marker():
                await asyncio.sleep(20)
                bot.command_revocations.discard((guild_id, user.id))
            asyncio.create_task(clear_revocation_marker())
            try:
                await user.send(f'ℹ️ האימות שלך בשרת **{interaction.guild.name}** בוטל.\n**סיבה:** {reason}')
            except discord.Forbidden:
                pass
        except Exception as e:
            await interaction.response.send_message(f'⚠️ שגיאה בהסרת הרול: {e}', ephemeral=True)
    await db.remove_verified_user(user.id, guild_id)
    await db.log_verification_event(user.id, guild_id, 'revoked', reason)
    if settings.get('log_channel_id'):
        log_chan = interaction.guild.get_channel(settings['log_channel_id'])
        if log_chan:
            log_embed = discord.Embed(title='🚫 אימות בוטל', description=f'האימות של {user.mention} בוטל על ידי {interaction.user.mention}.', color=EMBED_COLOR_DANGER)
            log_embed.add_field(name='סיבה', value=reason)
            log_embed.set_thumbnail(url=user.display_avatar.url)
            await log_chan.send(embed=log_embed)
    embed = discord.Embed(title='✅ אימות בוטל בהצלחה', description=f'האימות של {user.mention} בוטל והרול הוסר.', color=EMBED_COLOR_WARNING)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name='verify_stats', description='הצגת סטטיסטיקות אימות מלאות בשרת')
@app_commands.checks.has_permissions(administrator=True)
async def verify_stats_slash(interaction: discord.Interaction):
    guild = interaction.guild
    verified_count = await db.get_guild_verification_count(guild.id)
    total_members = guild.member_count or 1
    unverified_count = max(0, total_members - verified_count)
    percentage = round(verified_count / total_members * 100, 1)
    embed = discord.Embed(title=f'📊 סטטיסטיקות אימות • {guild.name}', color=EMBED_COLOR_PRIMARY)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name='👥 סה"כ חברים', value=f'`{total_members}`', inline=True)
    embed.add_field(name='✅ מאומתים', value=f'`{verified_count}` ({percentage}%)', inline=True)
    embed.add_field(name='❌ לא מאומתים', value=f'`{unverified_count}`', inline=True)
    recent_logs = await db.get_recent_logs(guild.id, limit=5)
    if recent_logs:
        lines = []
        for item in recent_logs:
            dt = datetime.fromtimestamp(item['timestamp']).strftime('%H:%M:%S')
            lines.append(f'• `{dt}` - <@{item['user_id']}>: **{item['status']}** ({item['note'] or 'ללא'})')
        embed.add_field(name='📜 לוגים אחרונים', value='\n'.join(lines), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name='partner', description='פרסום שותפות חדשה בערוץ')
@app_commands.describe(text='הטקסט של הפרטנר להפצה')
@app_commands.checks.has_permissions(manage_messages=True)
async def partner_slash(interaction: discord.Interaction, text: str):
    embed = discord.Embed(title='🤝 פרטנר חדש!', description=text, color=EMBED_COLOR_PRIMARY)
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=f'פורסם על ידי {interaction.user.name}', icon_url=interaction.user.display_avatar.url)
    await interaction.channel.send(content='🤝 **פרטנר חדש!**', embed=embed)
    await interaction.response.send_message('✅ הפרטנר פורסם בהצלחה!', ephemeral=True)

@bot.tree.command(name='set_boost_channel', description='מגדיר את החדר שבו יישלחו התראות הבוסטים')
@app_commands.describe(channel='ערוץ הבוסטים')
@app_commands.checks.has_permissions(administrator=True)
async def set_boost_channel_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    await db.set_boost_channel(interaction.guild.id, channel.id)
    embed = discord.Embed(title='🚀 חדר בוסטים הוגדר בהצלחה', description=f'מעכשיו כל בוסט שייכנס ייחגג בערוץ: {channel.mention}', color=EMBED_COLOR_BOOST)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name='test_boost', description='בדיקה: שליחת הודעת בוסט מעוצבת לדוגמה')
@app_commands.checks.has_permissions(administrator=True)
async def test_boost_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await send_boost_announcement(interaction.guild, interaction.user)
    await interaction.followup.send('✅ הודעת בוסט לדוגמה נשלחה בהצלחה!', ephemeral=True)

@bot.tree.command(name='panel', description='שולח את פאנל ההזמנות הרשמי עם הכפתורים לערוץ הנוכחי')
@app_commands.checks.has_permissions(administrator=True)
async def panel_slash(interaction: discord.Interaction):
    embed = discord.Embed(title='🚀 מערכת ההזמנות והפרסים של השרת! 🎁', description='לחץ על אחד הכפתורים למטה כדי לנהל את הקישורים שלך ולבדוק סטטיסטיקות!', color=EMBED_COLOR_PRIMARY)
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text='מערכת ההזמנות הרשמית ✨')
    await interaction.channel.send(embed=embed, view=InvitePanelView())
    await interaction.response.send_message('✅ פאנל ההזמנות נשלח בהצלחה!', ephemeral=True)

@bot.tree.command(name='legit', description='מעלה הוכחה/לגיט חדשה עם תמונה לערוץ הנוכחי')
@app_commands.describe(image='העלה או גרור לכאן את תמונת ההוכחה', description='תיאור נוסף (אופציונלי)')
@app_commands.checks.has_permissions(manage_messages=True)
async def legit_slash(interaction: discord.Interaction, image: discord.Attachment, description: Optional[str]=None):
    await interaction.response.defer(ephemeral=True)
    try:
        image_bytes = await image.read()
        file = discord.File(fp=io.BytesIO(image_bytes), filename=image.filename)
    except Exception as e:
        await interaction.followup.send(f'❌ שגיאה בקריאת התמונה: {e}', ephemeral=True)
    embed = discord.Embed(description=description if description else 'הוכחה חדשה נוספה בהצלחה! ✅', color=EMBED_COLOR_SUCCESS)
    embed.set_image(url=f'attachment://{image.filename}')
    embed.set_footer(text=f'הועלה על ידי {interaction.user.name}', icon_url=interaction.user.display_avatar.url)
    await interaction.channel.send(content='📸 **הוכחה חדשה!**', embed=embed, file=file)
    await interaction.followup.send('✅ ההוכחה הועלתה בהצלחה לערוץ!', ephemeral=True)

@bot.tree.command(name='set_welcome_channel', description='מגדיר את חדר קבלת הפנים')
@app_commands.describe(channel='הערוץ שבו תישלח ההודעה')
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_channel_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    await db.set_welcome_channel(interaction.guild.id, channel.id)
    await interaction.response.send_message(f'✅ ערוץ ברוכים הבאים הוגדר ל־{channel.mention}', ephemeral=True)

@bot.tree.command(name='test_welcome', description='בודק ושולח הודעת שלום ותמונה לדוגמה')
@app_commands.checks.has_permissions(administrator=True)
async def test_welcome_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    card_buffer = await generate_welcome_card(interaction.user)
    file = discord.File(fp=card_buffer, filename='welcome_test.png')
    joined_str = f'<t:{int(interaction.user.joined_at.timestamp())}:f>' if interaction.user.joined_at else 'עכשיו'
    embed = discord.Embed(title='🎉 ברוך הבא לשרת!', description=f'👋 היי {interaction.user.mention}, שמחים לראות אותך כאן!\n\n✨ אנחנו מקווים שתיהנה מהשרת, תכיר אנשים חדשים ותהיה חלק מהקהילה שלנו.\n\n📜 אל תשכח לעבור על חוקי השרת ולהתעדכן בערוצים השונים.', color=EMBED_COLOR_PRIMARY)
    embed.add_field(name='🎉 מספר חבר', value=f'החבר ה־**{interaction.guild.member_count}**', inline=True)
    embed.add_field(name='📅 הצטרפות ב', value=joined_str, inline=True)
    embed.add_field(name='💙 איחולים', value='שיהיה לך בהצלחה ותהנה מהשהייה!', inline=False)
    embed.set_image(url='attachment://welcome_test.png')
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    await interaction.channel.send(content=f'🎉 **בדיקה עבור {interaction.user.mention}!**', embed=embed, file=file)
    await interaction.followup.send('✅ הודעת הבדיקה נשלחה!', ephemeral=True)

@bot.tree.command(name='set_leave_channel', description='מגדיר את חדר הודעות העזיבה מהשרת')
@app_commands.describe(channel='הערוץ שבו תישלח ההודעה')
@app_commands.checks.has_permissions(administrator=True)
async def set_leave_channel_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    await db.set_leave_channel(interaction.guild.id, channel.id)
    embed = discord.Embed(title='🚪 חדר עזיבה הוגדר בהצלחה', description=f'מעכשיו הודעות עזיבה ופרידה יישלחו בערוץ: {channel.mention}', color=EMBED_COLOR_WARNING)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name='test_leave', description='בודק ושולח הודעת עזיבה ותמונת פרידה לדוגמה')
@app_commands.checks.has_permissions(administrator=True)
async def test_leave_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    card_buffer = await generate_leave_card(interaction.user)
    file = discord.File(fp=card_buffer, filename='leave_test.png')
    embed = discord.Embed(title='👋 להתראות, נתראה בקרוב!', description=f'😢 חבל לנו לראות אותך עוזב, **{interaction.user.display_name}**...\n\n✨ תודה שהיית חלק מהקהילה שלנו! מקווים לראות אותך שוב בעתיד.', color=EMBED_COLOR_DANGER)
    embed.add_field(name='👥 נשארו בשרת', value=f'החבר ה־**{interaction.guild.member_count}**', inline=True)
    if interaction.user.joined_at:
        joined_str = f'<t:{int(interaction.user.joined_at.timestamp())}:R>'
        embed.add_field(name='📅 היה איתנו מאז', value=joined_str, inline=True)
    embed.set_image(url='attachment://leave_test.png')
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=f'{interaction.guild.name} • שער העזיבה', icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    await interaction.channel.send(content=f'👋 **בדיקת עזיבה עבור {interaction.user.mention}!**', embed=embed, file=file)
    await interaction.followup.send('✅ הודעת בדיקת עזיבה נשלחה בהצלחה!', ephemeral=True)

async def main():
    token = SETTINGS.DISCORD_TOKEN
    if not token:
        logger.error('❌ לא נמצא DISCORD_TOKEN! אנא ודא שהטוקן מוגדר בקובץ .env')
        return
    async with bot:
        await bot.start(token)

if __name__ == '__main__':
    print('🚀 מפעיל את הבוט המאוחד...')
    asyncio.run(main())
