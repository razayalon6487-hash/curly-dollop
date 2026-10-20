'''
══════════════════════════════════════════════════════════════════════════════
👑 ✦ Discord Verification, Community, Invites & Boost Bot ✦ 👑
══════════════════════════════════════════════════════════════════════════════
המערכת המקיפה והמשודרגת:
1. 🛡️ מערכת אימות מהירה ומאובטחת ללא אזכור שמות טכניים, עם טקסט מעוצב ואימוג'ים
2. 🤖 כפתור מדריך להוספת הבוט ל-Apps ולשרתים
3. 🔐 אימות באמצעות כפתור או תגובת ✅ והענקת תפקיד מתוך השרת
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
import asyncio
import logging
import json
import re
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta
from typing import (Dict, List, Optional, Any)
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
import discord
from discord import app_commands
from discord.ext import commands
from PIL import (Image, ImageDraw, ImageFont, ImageFilter, ImageOps)
from config import SETTINGS
import db
from ticket_system import TicketSystem
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger('unified_bot')
EMBED_COLOR_PRIMARY = 5793266
EMBED_COLOR_SUCCESS = 3066993
EMBED_COLOR_WARNING = 15844367
EMBED_COLOR_DANGER = 15158332
EMBED_COLOR_BOOST = 16023551
VERIFY_EMOJI = '✅'
VERIFY_CONFIG_PATH = Path(__file__).resolve().with_name('verification_config.json')

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

async def grant_verification_role(interaction: discord.Interaction, guild: discord.Guild):
    member = interaction.user
    if not isinstance(member, discord.Member):
        await interaction.response.send_message('אפשר לבצע אימות רק מתוך שרת.', ephemeral=True)
        return

    blocked = await db.get_blocked_verification(member.id, guild.id)
    if blocked:
        reason = blocked.get('reason') or 'לא צוינה סיבה.'
        await interaction.response.send_message(f'⛔ האימות חסום עבורך.\n**סיבה:** {reason}', ephemeral=True)
        return

    settings = await db.get_guild_settings(guild.id)
    config = bot.verification_configs.get(str(guild.id), {})
    role_id = config.get('role_id') or settings.get('verified_role_id')
    role = guild.get_role(role_id) if role_id else None
    role = role or discord.utils.get(guild.roles, name='Verified') or discord.utils.get(guild.roles, name='מאומת')
    if role is None:
        await interaction.response.send_message('לא הוגדר תפקיד אימות. בקשו ממנהל להריץ `!setup`.', ephemeral=True)
        return
    if role in member.roles:
        await interaction.response.send_message(
            embed=discord.Embed(
                title='✨ כבר אומתת!',
                description='תפקיד האימות כבר נמצא אצלך. אפשר להמשיך וליהנות מהשרת! 🎉',
                color=discord.Color.green(),
            ),
            ephemeral=True,
        )
        return

    install_view = discord.ui.View(timeout=60)
    install_view.add_item(app_install_button(interaction.client))
    await interaction.response.send_message(
        embed=discord.Embed(
            title='📲 שיוך האפליקציה ל־Apps',
            description=(
                'אפשר לפתוח את מסך ההוספה של Discord דרך הכפתור למטה. '
                'תהליך האימות בשרת ימשיך במקביל.'
            ),
            color=discord.Color.blurple(),
        ),
        view=install_view,
        ephemeral=True,
    )
    await asyncio.sleep(5)

    try:
        await member.add_roles(role, reason='השלמת אימות בשרת')
    except discord.Forbidden:
        await interaction.followup.send(
            embed=discord.Embed(
                title='⚠️ לא ניתן להוסיף את תפקיד האימות',
                description='חסרה לבוט הרשאה מתאימה. פנו למנהלי השרת. 🛡️',
                color=discord.Color.orange(),
            ),
            ephemeral=True,
        )
        return
    except discord.HTTPException:
        logger.exception('Could not assign verification role in guild %s', guild.id)
        await interaction.followup.send(
            embed=discord.Embed(
                title='❌ האימות נכשל',
                description='אירעה שגיאה. נסו שוב בעוד רגע או פנו לצוות השרת.',
                color=discord.Color.red(),
            ),
            ephemeral=True,
        )
        return

    await db.add_verified_user(member.id, guild.id)
    await db.log_verification_event(member.id, guild.id, 'success', 'אומת באמצעות הכפתור לאחר פתיחת קישור Apps')
    await interaction.followup.send(
        embed=discord.Embed(
            title='🎉 האימות הושלם בהצלחה!',
            description=f'קיבלת את התפקיד {role.mention}. ברוך הבא לשרת! ✅',
            color=discord.Color.green(),
        ),
        ephemeral=True,
    )


def app_install_button(bot_instance):
    application_id = bot_instance.application_id or bot_instance.user.id
    install_url = 'https://discord.com/oauth2/authorize?' + urllib.parse.urlencode({
        'client_id': application_id,
        'scope': 'applications.commands',
        'integration_type': 1,
    })
    return discord.ui.Button(
        label='הוסף את הבוט ל־Apps',
        emoji='📲',
        style=discord.ButtonStyle.link,
        url=install_url,
    )

class VerifyRoleButton(discord.ui.Button):
    def __init__(self, guild_id: Optional[int] = None):
        custom_id = f'verify_role:{guild_id}' if guild_id else 'verify_button_persistent'
        super().__init__(label='אמת', style=discord.ButtonStyle.success, custom_id=custom_id, emoji='✅')

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message('אפשר לבצע אימות רק מתוך שרת.', ephemeral=True)
            return
        await grant_verification_role(interaction, interaction.guild)


class VerificationButtonView(discord.ui.View):
    def __init__(self, guild_id: Optional[int] = None):
        super().__init__(timeout=None)
        self.add_item(VerifyRoleButton(guild_id))


class VerifyView(VerificationButtonView):
    def __init__(self):
        super().__init__()
        self.add_item(AddBotGuideButton())


class AddBotGuideButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label='הוסף את הבוט', style=discord.ButtonStyle.secondary, custom_id='btn_add_bot_guide', emoji='🤖')

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        access_role = discord.utils.get(guild.roles, name='גישה לבוט') if guild else None
        if not access_role or access_role not in interaction.user.roles:
            await interaction.response.send_message('⛔ האפשרות זמינה רק למשתמשים שקיבלו את תפקיד „גישה לבוט”.', ephemeral=True)
            return
        application_id = interaction.client.application_id or interaction.client.user.id
        bot_invite_url = 'https://discord.com/oauth2/authorize?' + urllib.parse.urlencode({
            'client_id': application_id, 'permissions': 8, 'integration_type': 0,
            'scope': 'bot applications.commands',
        })
        user_app_url = 'https://discord.com/oauth2/authorize?' + urllib.parse.urlencode({
            'client_id': application_id, 'integration_type': 1, 'scope': 'applications.commands',
        })
        guide_view = discord.ui.View()
        guide_view.add_item(discord.ui.Button(label='הוספה לשרת', url=bot_invite_url, style=discord.ButtonStyle.link))
        guide_view.add_item(discord.ui.Button(label='הוספה ל-Apps', url=user_app_url, style=discord.ButtonStyle.link))
        await interaction.response.send_message(
            'הקישורים הבאים פותחים את מסכי ההוספה של Discord. הם אינם חלק מתהליך האימות.',
            view=guide_view, ephemeral=True,
        )


class SetupView(discord.ui.View):
    def __init__(self, bot_instance, author_id: int, guild: discord.Guild):
        super().__init__(timeout=180)
        self.bot_instance = bot_instance
        self.author_id = author_id
        channels = guild.text_channels[:25]
        if channels:
            self.add_item(VerificationChannelSelect(bot_instance, author_id, guild, channels))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message('רק מי שהפעיל את ההגדרה יכול להשתמש בתפריט הזה.', ephemeral=True)
            return False
        return True


class VerificationChannelSelect(discord.ui.Select):
    def __init__(self, bot_instance, author_id: int, guild: discord.Guild, channels):
        self.bot_instance = bot_instance
        self.author_id = author_id
        self.guild = guild
        options = [discord.SelectOption(label=channel.name[:100], value=str(channel.id)) for channel in channels]
        super().__init__(placeholder='בחרו את הערוץ שבו תופיע הודעת האימות', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        channel = self.guild.get_channel(int(self.values[0]))
        if channel is None:
            await interaction.response.send_message('הערוץ כבר לא זמין.', ephemeral=True)
            return
        await interaction.response.send_modal(VerificationMessageModal(self.bot_instance, self.author_id, channel))


class VerificationMessageModal(discord.ui.Modal, title='הודעת אימות'):
    message = discord.ui.TextInput(
        label='מה הבוט יכתוב בערוץ?', placeholder='לדוגמה: לחצו על הכפתור כדי לקבל גישה.',
        max_length=1500, style=discord.TextStyle.paragraph,
    )

    def __init__(self, bot_instance, author_id: int, channel: discord.TextChannel):
        super().__init__()
        self.bot_instance = bot_instance
        self.author_id = author_id
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f'ההודעה תישלח אל {self.channel.mention}. בחרו שיטת אימות:',
            view=VerificationMethodView(self.bot_instance, self.author_id, self.channel, str(self.message)),
            ephemeral=True,
        )


class VerificationMethodView(discord.ui.View):
    def __init__(self, bot_instance, author_id: int, channel: discord.TextChannel, message: str):
        super().__init__(timeout=180)
        self.bot_instance = bot_instance
        self.author_id = author_id
        self.channel = channel
        self.message = message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message('רק מנהל שהתחיל את ההגדרה יכול לבחור את השיטה.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='באימוג׳י ✅', style=discord.ButtonStyle.secondary)
    async def choose_reaction(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish_setup(interaction, 'reaction')

    @discord.ui.button(label='בכפתור', style=discord.ButtonStyle.primary)
    async def choose_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish_setup(interaction, 'button')

    async def finish_setup(self, interaction: discord.Interaction, method: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = self.channel.guild
        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_roles:
            await interaction.followup.send('כדי להגדיר אימות, צריך לתת לבוט הרשאת Manage Roles.', ephemeral=True)
            return

        settings = await db.get_guild_settings(guild.id)
        role = guild.get_role(settings.get('verified_role_id')) if settings.get('verified_role_id') else None
        role = role or discord.utils.get(guild.roles, name='Verified') or discord.utils.get(guild.roles, name='מאומת')
        try:
            if role is None:
                role = await guild.create_role(name='Verified', reason='הגדרת מערכת אימות')
            if role >= bot_member.top_role:
                await interaction.followup.send('תפקיד הבוט חייב להיות גבוה מתפקיד האימות ברשימת התפקידים.', ephemeral=True)
                return
            embed = discord.Embed(
                title='🔐 אימות חשבון',
                description=f'{self.message}\n\n✅ לחצו על **אמת** לקבלת תפקיד האימות.' if method == 'button' else f'{self.message}\n\n✅ הוסיפו תגובת ✅ להודעה כדי לקבל את תפקיד האימות.',
                color=EMBED_COLOR_PRIMARY,
            )
            view = VerificationButtonView(guild.id) if method == 'button' else None
            panel_message = await self.channel.send(embed=embed, view=view)
            if method == 'reaction':
                await panel_message.add_reaction(VERIFY_EMOJI)
            await db.update_guild_settings(guild.id, verified_role_id=role.id, verification_channel_id=self.channel.id)
            self.bot_instance.verification_configs[str(guild.id)] = {
                'channel_id': self.channel.id, 'message_id': panel_message.id,
                'role_id': role.id, 'method': method,
            }
            self.bot_instance.save_verification_configs()
            if method == 'button':
                self.bot_instance.add_view(VerificationButtonView(guild.id), message_id=panel_message.id)
        except discord.Forbidden:
            await interaction.followup.send('חסרות לבוט הרשאות לניהול תפקידים או לשליחת הודעה בערוץ.', ephemeral=True)
            return
        except (discord.HTTPException, OSError):
            logger.exception('Could not complete verification setup in guild %s', guild.id)
            await interaction.followup.send('ההגדרה נכשלה. בדקו את הרשאות הבוט ונסו שוב.', ephemeral=True)
            return
        method_label = 'תגובה ✅' if method == 'reaction' else 'כפתור'
        await interaction.followup.send(f'האימות הוגדר בהצלחה בערוץ {self.channel.mention} באמצעות {method_label}.', ephemeral=True)


async def grant_verified_channel_access(guild: discord.Guild, role: discord.Role) -> list[str]:
    """Allow the verified role to view every channel in the guild.

    Synced channels inherit the permission from their category, so only
    categories, uncategorized channels, and channels with custom overwrites
    need an explicit role overwrite.
    """
    failures = []
    for channel in guild.channels:
        if isinstance(channel, discord.CategoryChannel):
            needs_overwrite = True
        else:
            needs_overwrite = channel.category is None or not channel.permissions_synced
        if not needs_overwrite:
            continue

        overwrite = channel.overwrites_for(role)
        if overwrite.view_channel is True:
            continue
        overwrite.view_channel = True
        try:
            await channel.set_permissions(
                role,
                overwrite=overwrite,
                reason="Grant verified members visibility to all server channels",
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            failures.append(f"{channel.name}: {exc}")
    return failures


async def set_unverified_channel_lock(
    guild: discord.Guild,
    enabled: bool,
    visible_channel_ids: set[int],
) -> list[str]:
    """Restrict @everyone to the verification and welcome channels."""
    failures = []
    for channel in guild.channels:
        overwrite = channel.overwrites_for(guild.default_role)
        wanted = channel.id in visible_channel_ids if enabled else None
        if overwrite.view_channel is wanted:
            continue
        overwrite.view_channel = wanted
        try:
            await channel.set_permissions(
                guild.default_role,
                overwrite=overwrite,
                reason="Restrict unverified members to verification and welcome channels",
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            failures.append(f"{channel.name}: {exc}")
    return failures


class CloseMessageView(discord.ui.View):
    '''
    כפתור סגירת הודעה שתוקן לחלוטין – מוחק את ההודעה בצורה חלקה ללא שגיאות.
    '''

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='סגור הודעה ✕', style=discord.ButtonStyle.secondary, custom_id='btn_close_response')
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # This button belongs to the private response, never to the public panel.
            await interaction.response.edit_message(
                content='🗑️ *ההודעה הפרטית נסגרה.*',
                embed=None,
                view=None,
            )
        except discord.HTTPException:
            if not interaction.response.is_done():
                await interaction.response.send_message('לא הצלחתי לסגור את ההודעה הזו.', ephemeral=True)


class InvitePanelView(discord.ui.View):
    '''
    פאנל ניהול הזמנות עם 4 הכפתורים המלאים וניהול הודעות חכם.
    '''

    def __init__(self):
        super().__init__(timeout=None)

    async def send_or_update(self, interaction: discord.Interaction, embed: discord.Embed):
        # Always send a separate ephemeral response. The public invite panel is
        # never edited when someone presses one of its buttons.
        await interaction.followup.send(embed=embed, view=CloseMessageView(), ephemeral=True)

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
            live_uses = sum(inv.uses for inv in await guild.invites() if inv.inviter and inv.inviter.id == user_id)
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


TICKET_TYPES = [
    ('תמיכה כללית', 'שאלה או בקשה כללית', '💬'),
    ('בעיה טכנית', 'תקלה או בעיה טכנית', '🛠️'),
    ('דיווח על משתמש', 'דיווח שדורש בדיקה של הצוות', '🚨'),
    ('ערעור על עונש', 'בקשה לבדיקה מחדש של עונש', '⚖️'),
    ('רכישה וחבילות', 'שאלות על רכישה או חבילה', '🛒'),
    ('בעיה בתשלום', 'עזרה בנושא תשלום או חיוב', '💳'),
    ('שיתוף פעולה', 'פנייה בנושא שיתוף פעולה', '🤝'),
    ('פנייה לצוות', 'בקשה לשוחח עם חבר צוות', '🛡️'),
    ('נושא אחר', 'כל פנייה שלא מתאימה לקטגוריות האחרות', '📩'),
]

TICKET_SUBTOPICS = {
    'תמיכה כללית': '💬 מה רציתם לברר?\n🧩 מה כבר ניסיתם לעשות?',
    'בעיה טכנית': '🛠️ מה לא עובד?\n📱 באיזה מכשיר או תוכנה מדובר?\n📸 אפשר לצרף צילום מסך או הודעת שגיאה.',
    'דיווח על משתמש': '🚨 על מי תרצו לדווח?\n🕒 מתי זה קרה?\n📎 צרפו פרטים או הוכחות רלוונטיות.',
    'ערעור על עונש': '⚖️ איזה עונש קיבלתם ומתי?\n📝 למה לדעתכם כדאי לבדוק אותו מחדש?\n📎 צרפו מידע שיכול לעזור בבדיקה.',
    'רכישה וחבילות': '🛒 באיזו חבילה מדובר?\n📅 מתי בוצעה הרכישה או הבקשה?\n🔎 כתבו מה תרצו לדעת.',
    'בעיה בתשלום': '💳 תארו את בעיית התשלום.\n🧾 ציינו תאריך וסכום, אם רלוונטי.\n🔐 אל תשלחו פרטי כרטיס או סיסמה.',
    'שיתוף פעולה': '🤝 עם איזה שרת או גורם תרצו לשתף פעולה?\n📈 מה אתם מציעים?\n🔗 צרפו קישורים רלוונטיים.',
    'פנייה לצוות': '🛡️ עם איזה נושא תרצו עזרה?\n👥 אם הפנייה קשורה למשתמש מסוים, ציינו את שמו.\n💬 כתבו כל פרט שחשוב לצוות לדעת.',
    'נושא אחר': '📩 תארו בקצרה במה נוכל לעזור.\n🧭 הוסיפו כל פרט שיעזור לצוות לטפל בפנייה.',
}


def is_ticket_staff(member: discord.Member) -> bool:
    permissions = member.guild_permissions
    return permissions.administrator or permissions.manage_messages or permissions.manage_channels


async def post_ticket_action(interaction: discord.Interaction, content: str):
    """Post successful ticket actions in the ticket channel for everyone to see."""
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        return
    await channel.send(content)
    confirmation = '✅ הפעולה בוצעה והעדכון פורסם בטיקט.'
    if interaction.response.is_done():
        await interaction.followup.send(confirmation, ephemeral=True)
    else:
        await interaction.response.send_message(confirmation, ephemeral=True)


TICKET_PRIORITIES = {
    'normal': ('🟢', 'לא דחוף'),
    'medium': ('🟡', 'קצת דחוף'),
    'urgent': ('🔴', 'דחוף מאוד'),
}


def set_ticket_topic_value(topic: str, key: str, value: str | None) -> str:
    """Replace or remove one pipe-delimited ticket metadata field."""
    topic = re.sub(rf'\s*\|\s*{re.escape(key)}=[^|]+', '', topic or '').strip()
    if value is not None:
        topic = f'{topic} | {key}={value}' if topic else f'{key}={value}'
    return topic


def ticket_name_with_priority(channel: discord.TextChannel, priority: str) -> str:
    emoji = TICKET_PRIORITIES[priority][0]
    base_name = re.sub(r'^(?:🟢|🟡|🔴)-?', '', channel.name).strip('-') or 'ticket'
    return f'{emoji}-{base_name}'[:100]


def ticket_priority_from_channel(channel: discord.TextChannel, topic: str | None = None) -> str:
    """Prefer the channel-name marker, which survives priority changes without editing the topic."""
    for priority, (emoji, _label) in TICKET_PRIORITIES.items():
        if channel.name.startswith(f'{emoji}-'):
            return priority
    match = re.search(r'ticket_priority=([^|]+)', topic or channel.topic or '')
    priority = match.group(1).strip() if match else 'normal'
    return priority if priority in TICKET_PRIORITIES else 'normal'


async def find_ticket_control_message(channel: discord.TextChannel, preferred_id: int | None = None):
    """Find the ticket's controls without storing their message ID with a channel PATCH."""
    if preferred_id:
        try:
            return await channel.fetch_message(preferred_id)
        except discord.HTTPException:
            pass
    if not bot.user:
        return None
    control_ids = {
        'ticket_claim_button', 'ticket_close_button', 'ticket_cancel_close_button',
        'ticket_reopen_button',
    }
    async for message in channel.history(limit=100):
        if message.author.id != bot.user.id:
            continue
        component_ids = {
            component.custom_id
            for row in message.components
            for component in getattr(row, 'children', [])
            if getattr(component, 'custom_id', None)
        }
        if component_ids & control_ids:
            return message
    return None


async def rename_ticket_for_priority(channel: discord.TextChannel, priority: str):
    """Rename in the background so Discord's channel-edit cooldown never stalls a button."""
    tasks = getattr(bot, 'ticket_name_tasks', None)
    if tasks is None:
        tasks = bot.ticket_name_tasks = {}
    desired = getattr(bot, 'ticket_name_priorities', None)
    if desired is None:
        desired = bot.ticket_name_priorities = {}
    desired[channel.id] = priority
    current = tasks.get(channel.id)
    if current and not current.done():
        return

    async def worker():
        try:
            while True:
                wanted = desired.get(channel.id, priority)
                live_channel = bot.get_channel(channel.id)
                if not isinstance(live_channel, discord.TextChannel):
                    return
                expected_name = ticket_name_with_priority(live_channel, wanted)
                if live_channel.name != expected_name:
                    await live_channel.edit(name=expected_name, reason='Ticket priority changed')
                if desired.get(channel.id, wanted) == wanted:
                    return
        except discord.HTTPException:
            logger.exception('Could not update priority marker on ticket channel %s', channel.id)
        finally:
            if tasks.get(channel.id) is asyncio.current_task():
                tasks.pop(channel.id, None)
                desired.pop(channel.id, None)

    tasks[channel.id] = asyncio.create_task(worker())


async def update_ticket_priority(channel: discord.TextChannel, priority: str, actor: discord.abc.User):
    emoji, label = TICKET_PRIORITIES[priority]
    message_match = re.search(r'ticket_message=(\d+)', channel.topic or '')
    try:
        message = await find_ticket_control_message(
            channel, int(message_match.group(1)) if message_match else None
        )
        if message and message.embeds:
            embed = discord.Embed.from_dict(message.embeds[0].to_dict())
            for index, field in enumerate(embed.fields):
                if field.name == '🚦 רמת דחיפות':
                    embed.set_field_at(index, name='🚦 רמת דחיפות', value=f'{emoji} **{label}**', inline=True)
                    await message.edit(embed=embed)
                    break
    except discord.HTTPException:
        logger.warning('Could not refresh priority field on ticket channel %s', channel.id)
    await rename_ticket_for_priority(channel, priority)
    return emoji, label


class TicketPrioritySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='לא דחוף', value='normal', emoji='🟢', description='טיפול רגיל'),
            discord.SelectOption(label='קצת דחוף', value='medium', emoji='🟡', description='דורש תשומת לב בקרוב'),
            discord.SelectOption(label='דחוף מאוד', value='urgent', emoji='🔴', description='דורש טיפול בהקדם האפשרי'),
        ]
        super().__init__(
            placeholder='בחרו רמת דחיפות…',
            min_values=1,
            max_values=1,
            options=options,
            custom_id='ticket_priority_select',
        )

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not is_ticket_staff(interaction.user):
            await interaction.response.send_message('⛔ שינוי דחיפות זמין לצוות בלבד.', ephemeral=True)
            return
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or 'ticket_owner=' not in (channel.topic or ''):
            await interaction.response.send_message('האפשרות זמינה רק בתוך ערוץ טיקט.', ephemeral=True)
            return

        priority = self.values[0]
        emoji, label = TICKET_PRIORITIES[priority]
        await interaction.response.defer()
        try:
            emoji, label = await update_ticket_priority(channel, priority, interaction.user)
            await post_ticket_action(
                interaction,
                f'{emoji} **עדכון דחיפות:** הדחיפות עודכנה ל־**{label}** על ידי {interaction.user.mention}.\n'
                'ℹ️ הכרטיס מתעדכן מיד; Discord עשוי לעכב את שינוי שם הערוץ.'
            )
        except discord.Forbidden:
            await interaction.followup.send('❌ אין לבוט הרשאה לעדכן את פרטי הטיקט.', ephemeral=True)
        except discord.HTTPException:
            await interaction.followup.send('❌ לא הצלחתי לעדכן את הדחיפות. נסו שוב.', ephemeral=True)


class TicketPriorityView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(TicketPrioritySelect())


class TicketAddMemberSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(
            placeholder='בחרו משתמש לצירוף לטיקט (צוות בלבד)',
            min_values=1,
            max_values=1,
            custom_id='ticket_add_member_select',
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not is_ticket_staff(interaction.user):
            await interaction.response.send_message('⛔ האפשרות הזו מיועדת לצוות בלבד.', ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel) or 'ticket_owner=' not in (interaction.channel.topic or ''):
            await interaction.response.send_message('הפעולה זמינה רק בתוך ערוץ טיקט.', ephemeral=True)
            return
        target = self.values[0]
        if not isinstance(target, discord.Member):
            target = interaction.guild.get_member(target.id) if interaction.guild else None
        if not target:
            await interaction.response.send_message('לא מצאתי את המשתמש בשרת.', ephemeral=True)
            return
        await interaction.response.defer()
        try:
            await interaction.channel.set_permissions(
                target,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                reason=f'Ticket participant added by {interaction.user}',
            )
            await post_ticket_action(interaction, f'➕ הגישה של {target.mention} לטיקט נוספה על ידי {interaction.user.mention}.')
        except discord.Forbidden:
            await interaction.followup.send('❌ אין לבוט הרשאה לעדכן הרשאות לערוץ.', ephemeral=True)
        except discord.HTTPException:
            await interaction.followup.send('❌ לא הצלחתי לצרף את המשתמש כרגע.', ephemeral=True)


class TicketRemoveMemberSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(
            placeholder='בחרו משתמש להסרה מהטיקט (צוות בלבד)',
            min_values=1,
            max_values=1,
            custom_id='ticket_remove_member_select',
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not is_ticket_staff(interaction.user):
            await interaction.response.send_message('⛔ האפשרות הזו מיועדת לצוות בלבד.', ephemeral=True)
            return
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or 'ticket_owner=' not in (channel.topic or ''):
            await interaction.response.send_message('הפעולה זמינה רק בתוך ערוץ טיקט.', ephemeral=True)
            return
        owner_match = re.search(r'ticket_owner=(\d+)', channel.topic or '')
        target = self.values[0]
        if owner_match and target.id == int(owner_match.group(1)):
            await interaction.response.send_message('אי אפשר להסיר את פותח הטיקט מהערוץ שלו.', ephemeral=True)
            return
        await interaction.response.defer()
        try:
            await channel.set_permissions(target, overwrite=None, reason=f'Ticket participant removed by {interaction.user}')
            await post_ticket_action(interaction, f'➖ הגישה של {target.mention} לטיקט הוסרה על ידי {interaction.user.mention}.')
        except discord.Forbidden:
            await interaction.followup.send('❌ אין לבוט הרשאה לעדכן הרשאות לערוץ.', ephemeral=True)
        except discord.HTTPException:
            await interaction.followup.send('❌ לא הצלחתי להסיר את המשתמש כרגע.', ephemeral=True)


async def finalize_ticket_close(channel_id: int, close_at: float, message_id: int):
    """Show the 10-second countdown, then lock the owner out and leave reopen controls."""
    try:
        while True:
            channel = bot.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                return
            topic = channel.topic or ''
            tasks = getattr(bot, 'ticket_close_tasks', {})
            if tasks.get(channel_id) is not asyncio.current_task():
                return
            remaining = max(0, int(close_at - time.time() + 0.999))
            changed_members = []
            message = None
            try:
                message = await channel.fetch_message(message_id)
                if remaining:
                    await message.edit(
                        content=f'⏳ הטיקט ייסגר בעוד **{remaining} שניות** (<t:{int(close_at)}:R>). אפשר לעצור את הסגירה בכפתור למטה.',
                        view=TicketClosingView(),
                    )
                else:
                    hidden_member_states = []
                    for target, overwrite in channel.overwrites.items():
                        if not isinstance(target, discord.Member) or target.id == getattr(bot.user, 'id', None) or is_ticket_staff(target):
                            continue
                        if overwrite.view_channel is False:
                            continue
                        original_view = {True: '1', False: '0', None: 'n'}[overwrite.view_channel]
                        original_send = {True: '1', False: '0', None: 'n'}[overwrite.send_messages]
                        overwrite.view_channel = False
                        overwrite.send_messages = False
                        await channel.set_permissions(target, overwrite=overwrite, reason='Ticket closed after countdown')
                        changed_members.append((target, original_view, original_send))
                        hidden_member_states.append(f'{target.id}:{original_view}:{original_send}')
                    closed_topic = set_ticket_topic_value(topic, 'ticket_status', 'closed')
                    closed_topic = set_ticket_topic_value(closed_topic, 'ticket_close_requested_at', None)
                    closed_topic = set_ticket_topic_value(closed_topic, 'ticket_closed_viewers', ';'.join(hidden_member_states) or 'none')
                    # Persist the final state once. Starting/cancelling the countdown does not
                    # PATCH the channel, avoiding Discord's long channel-edit cooldown.
                    await channel.edit(topic=closed_topic, reason='Ticket closed after 10-second countdown')
                    await message.edit(
                        content='🔒 הטיקט נסגר. הצוות יכול להמשיך לצפות בו, ופותח הטיקט או הצוות יכולים לפתוח אותו מחדש.',
                        view=TicketClosedView(),
                    )
                    await channel.send('🔒 הטיקט נסגר. אפשר לפתוח אותו מחדש באמצעות הכפתור שמופיע בהודעת הטיקט.')
                    return
            except discord.Forbidden:
                logger.exception('Missing permissions while closing ticket %s', channel_id)
                permission_values = {'1': True, '0': False, 'n': None}
                for target, original_view, original_send in changed_members:
                    try:
                        overwrite = channel.overwrites_for(target)
                        overwrite.view_channel = permission_values[original_view]
                        overwrite.send_messages = permission_values[original_send]
                        await channel.set_permissions(target, overwrite=overwrite, reason='Restore permissions after failed ticket close')
                    except discord.HTTPException:
                        logger.exception('Could not restore participant access in ticket %s', channel_id)
                try:
                    if 'ticket_status=closing' in topic:
                        reopened_topic = set_ticket_topic_value(topic, 'ticket_status', 'open')
                        reopened_topic = set_ticket_topic_value(reopened_topic, 'ticket_close_requested_at', None)
                        await channel.edit(topic=reopened_topic, reason='Cancel legacy ticket close because permissions are missing')
                    error_text = '⚠️ הסגירה לא הושלמה כי חסרות לבוט הרשאות לשינוי גישת חברים. בדקו שיש לו Manage Channels ו־Manage Roles, ואז נסו שוב.'
                    if message:
                        await message.edit(content=error_text, view=ticket_open_view_for(channel))
                    else:
                        await channel.send(error_text, view=ticket_open_view_for(channel))
                    await channel.send('⚠️ הטיקט נשאר פתוח. יש להוסיף לבוט הרשאת **Manage Roles** וגם **Manage Channels** כדי לסגור ולהסתיר אותו מהמשתמש.')
                except discord.HTTPException:
                    logger.exception('Could not report ticket close permission failure for %s', channel_id)
                return
            except discord.NotFound:
                return
            except discord.HTTPException:
                logger.exception('Could not update closing ticket %s', channel_id)
            await asyncio.sleep(min(1, max(0.05, close_at - time.time())))
    except asyncio.CancelledError:
        raise
    finally:
        tasks = getattr(bot, 'ticket_close_tasks', {})
        current = tasks.get(channel_id)
        if current is asyncio.current_task():
            tasks.pop(channel_id, None)


def schedule_ticket_close(channel: discord.TextChannel, close_at: float, message_id: int):
    tasks = getattr(bot, 'ticket_close_tasks', None)
    if tasks is None:
        tasks = bot.ticket_close_tasks = {}
    previous = tasks.get(channel.id)
    if previous and not previous.done():
        previous.cancel()
    tasks[channel.id] = asyncio.create_task(finalize_ticket_close(channel.id, close_at, message_id))


class TicketClosingView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='בטל את הסגירה', style=discord.ButtonStyle.success, emoji='↩️', custom_id='ticket_cancel_close_button')
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not interaction.guild:
            await interaction.response.send_message('הפעולה זמינה רק בתוך ערוץ טיקט.', ephemeral=True)
            return
        topic = channel.topic or ''
        owner_match = re.search(r'ticket_owner=(\d+)', topic)
        owner_id = int(owner_match.group(1)) if owner_match else None
        is_staff = isinstance(interaction.user, discord.Member) and is_ticket_staff(interaction.user)
        if interaction.user.id != owner_id and not is_staff:
            await interaction.response.send_message('⛔ רק פותח הטיקט או חבר צוות יכולים לעצור את הסגירה.', ephemeral=True)
            return
        task = getattr(bot, 'ticket_close_tasks', {}).get(channel.id)
        if (not task or task.done()) and 'ticket_status=closing' not in topic:
            await interaction.response.send_message('אין כרגע ספירה לאחור פעילה.', ephemeral=True)
            return
        await interaction.response.defer()
        try:
            task = getattr(bot, 'ticket_close_tasks', {}).pop(channel.id, None)
            if task and not task.done():
                task.cancel()
            if 'ticket_status=closing' in topic:
                updated_topic = set_ticket_topic_value(topic, 'ticket_status', 'open')
                updated_topic = set_ticket_topic_value(updated_topic, 'ticket_close_requested_at', None)
                await channel.edit(topic=updated_topic, reason=f'Legacy ticket closing cancelled by {interaction.user}')
            if interaction.message:
                await interaction.message.edit(content=None, view=ticket_open_view_for(channel))
            await channel.send(f'↩️ {interaction.user.mention} עצר/ה את סגירת הטיקט. הטיקט נשאר פתוח.')
        except discord.HTTPException:
            await interaction.followup.send('❌ לא הצלחתי לעצור את הסגירה. נסו שוב.', ephemeral=True)


class TicketClosedView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='פתח טיקט מחדש', style=discord.ButtonStyle.primary, emoji='🔓', custom_id='ticket_reopen_button')
    async def reopen_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or not interaction.guild:
            await interaction.response.send_message('הפעולה זמינה רק בתוך ערוץ טיקט.', ephemeral=True)
            return
        topic = channel.topic or ''
        owner_match = re.search(r'ticket_owner=(\d+)', topic)
        owner_id = int(owner_match.group(1)) if owner_match else None
        is_staff = isinstance(interaction.user, discord.Member) and is_ticket_staff(interaction.user)
        if not is_staff:
            await interaction.response.send_message('⛔ פתיחת טיקט סגור מחדש זמינה לצוות בלבד.', ephemeral=True)
            return
        owner = interaction.guild.get_member(owner_id) if owner_id else None
        owner_hidden = bool(owner and channel.overwrites_for(owner).view_channel is False)
        if not owner_hidden and 'ticket_status=closed' not in topic:
            await interaction.response.send_message('הטיקט הזה אינו סגור.', ephemeral=True)
            return
        await interaction.response.defer()
        try:
            closed_viewers = re.search(r'ticket_closed_viewers=([^|]+)', topic)
            permission_values = {'1': True, '0': False, 'n': None}
            viewer_states = {}
            if closed_viewers:
                for entry in closed_viewers.group(1).strip().split(';'):
                    parts = entry.split(':')
                    if len(parts) == 3 and parts[0].isdigit():
                        viewer_states[parts[0]] = (permission_values.get(parts[1]), permission_values.get(parts[2]))
            for target in channel.overwrites:
                if isinstance(target, discord.Member) and str(target.id) in viewer_states:
                    overwrite = channel.overwrites_for(target)
                    overwrite.view_channel, overwrite.send_messages = viewer_states[str(target.id)]
                    await channel.set_permissions(target, overwrite=overwrite, reason=f'Ticket reopened by {interaction.user}')
            # The restored owner overwrite is the open-state marker. Avoid another channel PATCH.
            if owner_id and not owner_hidden:
                updated_topic = set_ticket_topic_value(topic, 'ticket_status', 'open')
                updated_topic = set_ticket_topic_value(updated_topic, 'ticket_closed_viewers', None)
                await channel.edit(topic=updated_topic, reason=f'Ticket reopened by {interaction.user}')
            if interaction.message:
                await interaction.message.edit(content=None, view=ticket_open_view_for(channel))
            await channel.send(f'🔓 הטיקט נפתח מחדש על ידי {interaction.user.mention}. אפשר להמשיך לכתוב כאן.')
        except discord.HTTPException:
            await interaction.followup.send('❌ לא הצלחתי לפתוח מחדש את הטיקט. בדקו את הרשאות הבוט ונסו שוב.', ephemeral=True)


class TicketCloseView(discord.ui.View):
    def __init__(self, claimed_by: discord.Member | None = None):
        super().__init__(timeout=None)
        self.add_item(TicketPrioritySelect())
        if claimed_by:
            for item in self.children:
                if getattr(item, 'custom_id', None) == 'ticket_claim_button':
                    item.disabled = True
                    item.label = f'נלקח: {claimed_by.display_name}'[:80]

    @discord.ui.button(label='קבל טיקט', style=discord.ButtonStyle.primary, emoji='🙋', custom_id='ticket_claim_button', row=0)
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_ticket_staff(interaction.user):
            await interaction.response.send_message('⛔ האפשרות הזו מיועדת לצוות בלבד.', ephemeral=True)
            return
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel) or 'ticket_owner=' not in (channel.topic or ''):
            await interaction.response.send_message('הפעולה זמינה רק בתוך ערוץ טיקט.', ephemeral=True)
            return
        topic = channel.topic or ''
        claimed = re.search(r'ticket_claimed_by=(\d+)', topic)
        if claimed and int(claimed.group(1)) != interaction.user.id:
            claimed_member = interaction.guild.get_member(int(claimed.group(1))) if interaction.guild else None
            claimed_name = claimed_member.mention if claimed_member else f'<@{claimed.group(1)}>'
            await interaction.response.send_message(f'הטיקט כבר בטיפול של {claimed_name}.', ephemeral=True)
            return
        await interaction.response.defer()
        try:
            button.disabled = True
            button.label = f'בטיפול: {interaction.user.display_name}'[:80]
            if interaction.message:
                await interaction.message.edit(view=self)
            await post_ticket_action(interaction, f'🙋 הטיקט נלקח לטיפול על ידי {interaction.user.mention}.')
        except discord.Forbidden:
            await interaction.followup.send('❌ אין לבוט הרשאה לעדכן את פרטי הטיקט.', ephemeral=True)
        except discord.HTTPException:
            await interaction.followup.send('❌ לא הצלחתי לעדכן את הטיקט כרגע.', ephemeral=True)

    @discord.ui.button(label='סגור טיקט', style=discord.ButtonStyle.danger, emoji='🔒', custom_id='ticket_close_button')
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        guild = interaction.guild
        if not isinstance(channel, discord.TextChannel) or not guild:
            await interaction.response.send_message('אפשר לסגור טיקט רק בתוך ערוץ טיקט.', ephemeral=True)
            return

        topic = channel.topic or ''
        owner_match = re.search(r'ticket_owner=(\d+)', topic)
        owner_id = int(owner_match.group(1)) if owner_match else None
        is_staff = isinstance(interaction.user, discord.Member) and is_ticket_staff(interaction.user)
        if interaction.user.id != owner_id and not is_staff:
            await interaction.response.send_message('⛔ רק פותח הטיקט או חבר צוות יכולים לסגור אותו.', ephemeral=True)
            return
        if 'ticket_status=closed' in topic:
            await interaction.response.send_message('הטיקט הזה כבר סגור.', ephemeral=True)
            return
        active_close = getattr(bot, 'ticket_close_tasks', {}).get(channel.id)
        if (active_close and not active_close.done()) or 'ticket_status=closing' in topic:
            await interaction.response.send_message('הסגירה כבר נספרת לאחור. אפשר לעצור אותה בכפתור שבהודעת הטיקט.', ephemeral=True)
            return
        close_at = time.time() + 10
        await interaction.response.defer()
        try:
            countdown_message = interaction.message
            if countdown_message is None:
                message_match = re.search(r'ticket_message=(\d+)', topic)
                countdown_message = await find_ticket_control_message(
                    channel, int(message_match.group(1)) if message_match else None
                )
            countdown_text = f'⏳ הטיקט ייסגר בעוד **10 שניות** (<t:{int(close_at)}:R>). פותח הטיקט או כל חבר צוות יכולים לעצור את הספירה.'
            if countdown_message:
                await countdown_message.edit(content=countdown_text, view=TicketClosingView())
            else:
                countdown_message = await channel.send(countdown_text, view=TicketClosingView())
            schedule_ticket_close(channel, close_at, countdown_message.id)
            await channel.send(f'🔒 {interaction.user.mention} התחיל/ה ספירה של 10 שניות לסגירת הטיקט.')
        except discord.Forbidden:
            await interaction.followup.send('❌ אין לבוט הרשאה לעדכן את הטיקט. בדקו את הרשאות Manage Channels.', ephemeral=True)
        except discord.HTTPException:
            await interaction.followup.send('❌ לא הצלחתי לסגור את הטיקט כרגע.', ephemeral=True)


def ticket_open_view_for(channel: discord.TextChannel) -> TicketCloseView:
    claimed_match = re.search(r'ticket_claimed_by=(\d+)', channel.topic or '')
    if not claimed_match:
        return TicketCloseView()
    claimed_by = channel.guild.get_member(int(claimed_match.group(1)))
    view = TicketCloseView(claimed_by=claimed_by)
    if claimed_by is None:
        for item in view.children:
            if getattr(item, 'custom_id', None) == 'ticket_claim_button':
                item.disabled = True
                item.label = 'הטיקט נלקח לטיפול'
    return view


class TicketCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=label, description=description, emoji=emoji, value=label)
            for label, description, emoji in TICKET_TYPES
        ]
        super().__init__(
            placeholder='בחרו את נושא הפנייה כדי לפתוח טיקט…',
            min_values=1,
            max_values=1,
            options=options,
            custom_id='ticket_category_select',
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message('פתיחת טיקט זמינה רק מתוך שרת.', ephemeral=True)
            return

        existing = next(
            (
                channel for channel in guild.text_channels
                if channel.topic and f'ticket_owner={interaction.user.id}' in channel.topic
                and ('ticket_status=open' in channel.topic or 'ticket_status=closing' in channel.topic)
            ),
            None,
        )
        if existing:
            await interaction.response.send_message(f'כבר יש לך טיקט פתוח: {existing.mention}', ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        selected = self.values[0]
        slug = re.sub(r'[^a-z0-9-]+', '-', interaction.user.display_name.lower()).strip('-')[:35] or 'member'
        category = discord.utils.get(guild.categories, name='טיקטים')
        everyone = guild.default_role
        staff_roles = [
            role for role in guild.roles
            if role != everyone and (role.permissions.administrator or role.permissions.manage_messages or role.permissions.manage_channels)
        ]
        overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True
            ),
        }
        for role in staff_roles:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, manage_messages=True
            )
        if guild.me:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, manage_channels=True
            )

        try:
            channel = await guild.create_text_channel(
                name=f'🟢-ticket-{slug}'[:100],
                category=category,
                topic=f'ticket_owner={interaction.user.id} | ticket_type={selected} | ticket_status=open | ticket_priority=normal',
                overwrites=overwrites,
                reason=f'Ticket opened by {interaction.user} ({selected})',
            )
            embed = discord.Embed(
                title=f'🎫・{selected}・🎫',
                description=(
                    f'╭・✨・ברוך הבא, {interaction.user.mention}!・✨・╮\n\n'
                    'הפנייה שלך נפתחה בהצלחה. צוות השרת יעבור עליה ויחזור אליך בהקדם.\n'
                    'כדי שנוכל לעזור בצורה הטובה ביותר, אפשר לשלוח הודעה עם הפרטים הבאים:\n\n'
                    '╭・📝・**נושאים שכדאי לכלול**・📝・╮\n'
                    f'{TICKET_SUBTOPICS.get(selected, "📩 כתבו כאן את פרטי הפנייה.")}\n\n'
                    '╰・🔐・הערוץ פרטי ונגיש רק לך ולצוות השרת・🔐・╯\n\n'
                    '💡 אפשר לצרף תמונות וקבצים. אין לשלוח סיסמאות או פרטי תשלום.'
                ),
                color=EMBED_COLOR_PRIMARY,
            )
            embed.add_field(name='📍 מצב הטיקט', value='🟡 ממתין למענה הצוות', inline=True)
            embed.add_field(name='🚦 רמת דחיפות', value='🟢 **לא דחוף**', inline=True)
            embed.add_field(name='🧑‍💻 פעולות צוות', value='קבלת הטיקט • בחירת דחיפות • סגירת הטיקט', inline=False)
            embed.set_footer(text=f'{guild.name} • מרכז התמיכה הרשמי 🎟️', icon_url=guild.icon.url if guild.icon else None)
            try:
                ticket_message = await channel.send(content=interaction.user.mention, embed=embed, view=TicketCloseView())
            except discord.HTTPException:
                logger.exception('Could not send the full opening message in ticket channel %s', channel.id)
                try:
                    ticket_message = await channel.send(
                        content=f'🎫 {interaction.user.mention} הטיקט שלך נפתח בנושא **{selected}**. צוות השרת יענה כאן בהקדם.',
                        view=TicketCloseView(),
                    )
                except discord.HTTPException:
                    logger.exception('Could not send ticket controls in channel %s; sending a text-only fallback', channel.id)
                    ticket_message = await channel.send(
                        f'🎫 {interaction.user.mention} הטיקט שלך נפתח בנושא **{selected}**. צוות השרת יענה כאן בהקדם.'
                    )
            await interaction.followup.send(f'✅ הטיקט נפתח בהצלחה: {channel.mention}', ephemeral=True)
        except discord.Forbidden:
            logger.exception('Permission failure while creating ticket for %s in guild %s', interaction.user.id, guild.id)
            await interaction.followup.send('❌ אין לבוט הרשאות ליצור ערוץ פרטי. צריך הרשאות Manage Channels ו-Manage Roles.', ephemeral=True)
        except discord.HTTPException:
            logger.exception('Discord API error while creating ticket for %s in guild %s', interaction.user.id, guild.id)
            await interaction.followup.send('❌ לא הצלחתי לפתוח טיקט כרגע. נסו שוב בעוד רגע.', ephemeral=True)


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect())


async def refresh_legacy_ticket_channels(guild: discord.Guild):
    """Restore ticket controls without editing channel metadata on every bot startup."""
    for channel in guild.text_channels:
        topic = channel.topic or ''
        owner_match = re.search(r'ticket_owner=(\d+)', topic)
        if not owner_match:
            continue
        owner_id = int(owner_match.group(1))
        message_match = re.search(r'ticket_message=(\d+)', topic)
        message = await find_ticket_control_message(
            channel, int(message_match.group(1)) if message_match else None
        )

        # Older versions recorded the deadline in the topic. New versions put a
        # Discord relative timestamp in the countdown message instead.
        close_match = re.search(r'ticket_close_requested_at=([0-9.]+)', topic)
        close_at = None
        if close_match:
            try:
                close_at = float(close_match.group(1))
            except ValueError:
                logger.warning('Invalid close countdown metadata in ticket channel %s', channel.id)
        if message and message.content:
            visible_deadline = re.search(r'<t:(\d+):R>', message.content)
            if visible_deadline and '⏳' in message.content:
                close_at = float(visible_deadline.group(1))
        if message and close_at is not None and (
            'ticket_status=closing' in topic or (message.content and '⏳' in message.content)
        ):
            schedule_ticket_close(channel, close_at, message.id)
            continue

        owner = guild.get_member(owner_id)
        owner_overwrite = channel.overwrites_for(owner) if owner else None
        owner_hidden = bool(owner_overwrite and owner_overwrite.view_channel is False)
        is_closed = owner_hidden or (
            'ticket_status=closed' in topic and (owner is None or is_ticket_staff(owner))
        )
        if is_closed:
            hidden_member_states = []
            for target, overwrite in channel.overwrites.items():
                if not isinstance(target, discord.Member) or target.id == getattr(bot.user, 'id', None) or is_ticket_staff(target):
                    continue
                if overwrite.view_channel is False:
                    continue
                legacy_owner = target.id == owner_id
                original_view = '1' if legacy_owner else {True: '1', False: '0', None: 'n'}[overwrite.view_channel]
                original_send = '1' if legacy_owner else {True: '1', False: '0', None: 'n'}[overwrite.send_messages]
                overwrite.view_channel = False
                overwrite.send_messages = False
                await channel.set_permissions(target, overwrite=overwrite, reason='Keep closed ticket visible to staff only')
                hidden_member_states.append(f'{target.id}:{original_view}:{original_send}')
            if hidden_member_states and not re.search(r'ticket_closed_viewers=([^|]+)', topic):
                topic = set_ticket_topic_value(topic, 'ticket_closed_viewers', ';'.join(hidden_member_states))
                try:
                    await channel.edit(topic=topic, reason='Save legacy closed ticket permissions')
                except discord.HTTPException:
                    logger.warning('Could not save closed ticket permissions for channel %s', channel.id)
            if message and 'ticket_reopen_button' not in {
                component.custom_id
                for row in message.components
                for component in getattr(row, 'children', [])
                if getattr(component, 'custom_id', None)
            }:
                try:
                    await message.edit(view=TicketClosedView())
                except discord.HTTPException:
                    logger.warning('Could not refresh closed ticket controls in channel %s', channel.id)
            continue

        if message:
            # The registered persistent view already handles these custom IDs.
            # Leave the message untouched to preserve the claim state and avoid PATCHes.
            continue

        type_match = re.search(r'ticket_type=([^|]+)', topic)
        selected = type_match.group(1).strip() if type_match else 'נושא אחר'
        if selected not in TICKET_SUBTOPICS:
            selected = 'נושא אחר'
        priority = ticket_priority_from_channel(channel, topic)
        emoji, label = TICKET_PRIORITIES.get(priority, TICKET_PRIORITIES['normal'])
        greeting = f'שלום {owner.mention}! צוות השרת ימשיך לטפל בפנייה כאן.' if owner else 'צוות השרת ימשיך לטפל בפנייה כאן.'

        embed = discord.Embed(
            title=f'🎫・{selected}・🎫',
            description=(
                f'🔄 **הטיקט עודכן לגרסה החדשה**\n'
                f'{greeting}\n\n'
                '📝 **פרטים שיעזרו לנו**\n'
                f'{TICKET_SUBTOPICS[selected]}\n\n'
                '🔐 הערוץ פרטי למשתתפי הטיקט ולצוות השרת. אפשר לצרף תמונות וקבצים, אך אין לשלוח סיסמאות או פרטי תשלום.'
            ),
            color=EMBED_COLOR_PRIMARY,
        )
        embed.add_field(name='🚦 רמת דחיפות', value=f'{emoji} **{label}**', inline=True)
        embed.add_field(name='🧑‍💻 פעולות צוות', value='קבלת הטיקט • בחירת דחיפות • סגירת הטיקט', inline=False)
        embed.set_footer(text=f'{guild.name} • מרכז התמיכה הרשמי 🎟️', icon_url=guild.icon.url if guild.icon else None)
        try:
            await channel.send(embed=embed, view=TicketCloseView())
            logger.info('Refreshed legacy ticket channel %s in guild %s', channel.id, guild.id)
        except discord.Forbidden:
            logger.warning('Missing permissions to refresh legacy ticket channel %s', channel.id)
        except discord.HTTPException:
            logger.exception('Could not refresh legacy ticket channel %s', channel.id)


intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.invites = True
intents.message_content = True

class UnifiedBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=None)
        self.tracker = InviteTracker(self)
        self._verification_revocation_reasons = {}
        self.ticket_system = TicketSystem(self)
        self.verification_configs = self.load_verification_configs()

    @staticmethod
    def load_verification_configs():
        if not VERIFY_CONFIG_PATH.exists():
            return {}
        try:
            with VERIFY_CONFIG_PATH.open('r', encoding='utf-8') as config_file:
                configs = json.load(config_file)
            return configs if isinstance(configs, dict) else {}
        except (OSError, json.JSONDecodeError):
            logger.exception('Could not load verification configuration')
            return {}

    def save_verification_configs(self):
        temporary_path = VERIFY_CONFIG_PATH.with_suffix('.tmp')
        with temporary_path.open('w', encoding='utf-8') as config_file:
            json.dump(self.verification_configs, config_file, ensure_ascii=False, indent=2)
        temporary_path.replace(VERIFY_CONFIG_PATH)

    async def setup_hook(self):
        await db.init_db()
        self.add_view(InvitePanelView())
        self.add_view(CloseMessageView())
        self.add_view(VerifyView())
        for guild_id, config in self.verification_configs.items():
            if config.get('method') == 'button':
                self.add_view(VerificationButtonView(int(guild_id)), message_id=config.get('message_id'))
        self.add_view(ReportPanelView())
        self.ticket_system.register_persistent_views()
        self.add_view(TicketCloseView())
        self.add_view(TicketClosingView())
        self.add_view(TicketClosedView())
        for report in await db.get_reports_with_log_messages():
            self.add_view(
                ReportReviewView(report['id'], disabled=report['status'] == 'approved'),
                message_id=report['log_message_id'],
            )
            if report.get('reporter_dm_message_id'):
                self.add_view(
                    ReportUserView(report['id'], can_appeal=report['status'] == 'rejected'),
                    message_id=report['reporter_dm_message_id'],
                )
        try:
            synced = await self.tree.sync()
            logger.info(f'⚡ סונכרנו בהצלחה {len(synced)} פקודות סלאש.')
        except Exception as e:
            logger.error(f'שגיאה בסנכרון פקודות סלאש: {e}')

    async def close(self):
        await super().close()


bot = UnifiedBot()


def report_status_label(status: str) -> str:
    return {
        'pending': 'ממתין לבדיקה',
        'under_review': 'בבדיקה',
        'approved': 'אושר וטופל',
        'rejected': 'לא אושר',
        'appealed': 'הוגש ערעור',
    }.get(status, status)


def build_report_embed(report: Dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(
        title=f"📨 דיווח #{report['id']} • {report_status_label(report['status'])}",
        description=(
            f"**דווח על:** {report['target_user']}\n"
            f"**סיבה:** {report['reason']}\n\n"
            f"**תיאור:**\n{report['description']}"
        )[:4096],
        color={
            'pending': EMBED_COLOR_WARNING,
            'under_review': EMBED_COLOR_WARNING,
            'approved': EMBED_COLOR_SUCCESS,
            'rejected': EMBED_COLOR_DANGER,
            'appealed': EMBED_COLOR_PRIMARY,
        }.get(report['status'], EMBED_COLOR_PRIMARY),
    )
    embed.add_field(name='📤 מדווח', value=f"<@{report['reporter_id']}> (`{report['reporter_id']}`)", inline=False)
    if report.get('punishment'):
        embed.add_field(name='⚖️ פעולה', value=report['punishment'], inline=True)
    if report.get('admin_response'):
        embed.add_field(name='💬 תגובת הצוות', value=report['admin_response'][:1024], inline=False)
    if report.get('reporter_response'):
        embed.add_field(name='🗨️ תגובת המדווח', value=report['reporter_response'][:1024], inline=False)
    if report.get('appeal_text'):
        embed.add_field(name='📄 ערעור', value=report['appeal_text'][:1024], inline=False)
    if report.get('appeal_image'):
        embed.set_image(url=report['appeal_image'])
    embed.timestamp = datetime.fromtimestamp(report['created_at'])
    embed.set_footer(text=f"מזהה דיווח: {report['id']}")
    return embed


class ReportDecisionModal(discord.ui.Modal):
    def __init__(self, report_id: int, decision: str, punishment: Optional[str] = None):
        self.report_id = report_id
        self.decision = decision
        self.punishment = punishment
        title = {
            'approved': 'אישור דיווח ובחירת פעולה',
            'under_review': 'העברת הדיווח לבדיקה',
            'rejected': 'דחיית הדיווח',
        }[decision]
        super().__init__(title=title, timeout=300)
        self.response_input = discord.ui.TextInput(
            label='תגובה אישית למדווח (אופציונלי)',
            style=discord.TextStyle.paragraph,
            max_length=800,
            required=False,
            placeholder='הוסף הודעה שתישלח למדווח בפרטי',
        )
        self.add_item(self.response_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild or not (interaction.user.guild_permissions.manage_messages or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message('❌ רק חבר צוות עם Manage Messages יכול לטפל בדיווח.', ephemeral=True)
            return
        report = await db.get_report(self.report_id)
        if not report or report['guild_id'] != interaction.guild.id:
            await interaction.response.send_message('❌ הדיווח לא נמצא בשרת הזה.', ephemeral=True)
            return
        admin_response = str(self.response_input.value).strip()
        punishment = self.punishment
        if self.decision == 'approved':
            if punishment not in {'ban', 'kick', 'mute'}:
                await interaction.response.send_message('❌ צריך לבחור ban, kick או mute.', ephemeral=True)
                return
            target, error = await resolve_report_target(interaction.guild, report['target_user'])
            if error:
                await interaction.response.send_message(f'❌ לא בוצעה פעולה: {error}', ephemeral=True)
                return
            try:
                reason = f"Report #{self.report_id}" + (f": {admin_response}" if admin_response else '')
                if punishment == 'ban':
                    await interaction.guild.ban(target, reason=reason)
                elif punishment == 'kick':
                    await target.kick(reason=reason)
                else:
                    await target.timeout(timedelta(days=1), reason=reason)
            except (discord.Forbidden, discord.HTTPException) as exc:
                await interaction.response.send_message(f'❌ לא הצלחתי לבצע {punishment}: {exc}', ephemeral=True)
                return

        await db.update_report(
            self.report_id,
            status=self.decision,
            admin_response=admin_response,
            punishment=punishment,
        )
        report = await db.get_report(self.report_id)
        await refresh_report_log(interaction.guild, report)
        await notify_reporter(interaction.guild, report)
        await interaction.response.send_message(
            f"✅ הדיווח עודכן לסטטוס **{report_status_label(self.decision)}**" + (f" והפעולה `{punishment}` בוצעה." if punishment else '.'),
            ephemeral=True,
        )


class ReportSubmitModal(discord.ui.Modal, title='דיווח על משתמש'):
    target_input = discord.ui.TextInput(label='שם המשתמש או מזהה Discord', max_length=100, placeholder='אפשר להזכיר משתמש או להדביק ID')
    reason_input = discord.ui.TextInput(label='סיבת הדיווח', max_length=200)
    description_input = discord.ui.TextInput(label='תיאור ופרטים', style=discord.TextStyle.paragraph, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        settings = await db.get_guild_settings(interaction.guild.id)
        log_channel_id = settings.get('report_channel_id')
        log_channel = interaction.guild.get_channel(log_channel_id) if log_channel_id else None
        if not isinstance(log_channel, discord.TextChannel):
            await interaction.response.send_message('❌ צוות השרת עדיין לא הגדיר חדר לוגים לדיווחים.', ephemeral=True)
            return
        report_id = await db.create_report(
            interaction.guild.id,
            interaction.user.id,
            str(self.target_input.value).strip(),
            str(self.reason_input.value).strip(),
            str(self.description_input.value).strip(),
        )
        report = await db.get_report(report_id)
        log_message = await log_channel.send(
            embed=build_report_embed(report),
            view=ReportReviewView(report_id),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        await db.update_report(report_id, log_message_id=log_message.id)
        report = await db.get_report(report_id)
        try:
            dm_message = await interaction.user.send(
                embed=reporter_report_embed(report),
                view=ReportUserView(report_id, can_appeal=False),
            )
            await db.update_report(report_id, reporter_dm_message_id=dm_message.id)
        except (discord.Forbidden, discord.HTTPException):
            pass
        await interaction.response.send_message('✅ הדיווח נשלח לצוות לבדיקה. עדכונים ותגובות יישלחו אליך בפרטי.', ephemeral=True)


class ReportAppealModal(discord.ui.Modal):
    appeal_input = discord.ui.TextInput(label='הסבר הערעור', style=discord.TextStyle.paragraph, max_length=1000)
    image_input = discord.ui.TextInput(
        label='קישור לצילום מסך (אופציונלי)',
        required=False,
        max_length=400,
        placeholder='או שלח את התמונה כהודעה נפרדת בצ׳אט הזה לאחר ההגשה',
    )

    def __init__(self, report_id: int):
        self.report_id = report_id
        super().__init__(title='ערעור על דיווח', timeout=300)

    async def on_submit(self, interaction: discord.Interaction):
        report = await db.get_report(self.report_id)
        if not report or report['reporter_id'] != interaction.user.id or report['status'] != 'rejected':
            await interaction.response.send_message('❌ לא ניתן להגיש ערעור לדיווח הזה.', ephemeral=True)
            return
        image_url = str(self.image_input.value).strip() or None
        if image_url and not image_url.startswith(('https://', 'http://')):
            await interaction.response.send_message('❌ קישור צילום המסך צריך להתחיל ב־https:// או http://.', ephemeral=True)
            return
        await db.update_report(
            self.report_id,
            status='appealed',
            appeal_text=str(self.appeal_input.value).strip(),
            appeal_image=image_url,
        )
        report = await db.get_report(self.report_id)
        guild = bot.get_guild(report['guild_id'])
        if guild:
            await refresh_report_log(guild, report)
        await interaction.response.send_message(
            '✅ הערעור נשלח לצוות. אם לא הוספת קישור לצילום מסך, שלח את התמונה כהודעה נפרדת בצ׳אט הפרטי הזה.',
            ephemeral=True,
        )


class ReportReplyModal(discord.ui.Modal, title='תגובה לדיווח'):
    response_input = discord.ui.TextInput(label='התגובה שלך', style=discord.TextStyle.paragraph, max_length=1000)

    def __init__(self, report_id: int):
        self.report_id = report_id
        super().__init__(title='תגובה לדיווח', timeout=300)

    async def on_submit(self, interaction: discord.Interaction):
        report = await db.get_report(self.report_id)
        if not report or report['reporter_id'] != interaction.user.id:
            await interaction.response.send_message('❌ הדיווח לא נמצא בחשבון שלך.', ephemeral=True)
            return
        await db.update_report(self.report_id, reporter_response=str(self.response_input.value).strip())
        report = await db.get_report(self.report_id)
        guild = bot.get_guild(report['guild_id'])
        if guild:
            await refresh_report_log(guild, report)
        await interaction.response.send_message('✅ התגובה שלך נשלחה לצוות ונרשמה בלוג.', ephemeral=True)


class ReportOpenButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label='דווח על משתמש', style=discord.ButtonStyle.danger, emoji='🚨', custom_id='report:open')

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message('❌ אפשר להגיש דיווח מתוך השרת בלבד.', ephemeral=True)
            return
        await interaction.response.send_modal(ReportSubmitModal())


class ReportPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ReportOpenButton())


class ReportActionSelect(discord.ui.Select):
    def __init__(self, report_id: int):
        self.report_id = report_id
        super().__init__(
            placeholder='בחר עונש לדיווח הזה',
            custom_id=f'report:action:{report_id}',
            options=[
                discord.SelectOption(label='באן', value='ban', description='חסימת המשתמש מהשרת'),
                discord.SelectOption(label='קיק', value='kick', description='הוצאת המשתמש מהשרת'),
                discord.SelectOption(label='השתקה ליום אחד', value='mute', description='הגבלת שליחת הודעות וכניסה לקול ליום אחד'),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not (interaction.user.guild_permissions.manage_messages or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message('❌ רק צוות השרת יכול לטפל בדיווח.', ephemeral=True)
            return
        await interaction.response.send_modal(ReportDecisionModal(self.report_id, 'approved', self.values[0]))


class ReportActionView(discord.ui.View):
    def __init__(self, report_id: int):
        super().__init__(timeout=180)
        self.add_item(ReportActionSelect(report_id))


class ReportReviewButton(discord.ui.Button):
    def __init__(self, report_id: int, label: str, style: discord.ButtonStyle, decision: str, disabled: bool):
        self.report_id = report_id
        self.decision = decision
        super().__init__(
            label=label,
            style=style,
            custom_id=f'report:review:{decision}:{report_id}',
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not (interaction.user.guild_permissions.manage_messages or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message('❌ רק צוות השרת יכול לטפל בדיווח.', ephemeral=True)
            return
        report = await db.get_report(self.report_id)
        if not report or report['guild_id'] != interaction.guild.id or report['status'] == 'approved':
            await interaction.response.send_message('ℹ️ הדיווח כבר טופל או שאינו זמין.', ephemeral=True)
            return
        if self.decision == 'approved':
            await interaction.response.send_message(
                'בחר את הפעולה שברצונך לבצע. השתקה היא ליום אחד.',
                view=ReportActionView(self.report_id),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(ReportDecisionModal(self.report_id, self.decision))


class ReportReviewView(discord.ui.View):
    def __init__(self, report_id: int, disabled: bool = False):
        super().__init__(timeout=None)
        for label, style, decision in (
            ('אשר וטפל', discord.ButtonStyle.success, 'approved'),
            ('בהמתנה', discord.ButtonStyle.secondary, 'under_review'),
            ('לא מאושר', discord.ButtonStyle.danger, 'rejected'),
        ):
            self.add_item(ReportReviewButton(report_id, label, style, decision, disabled))


class ReportUserButton(discord.ui.Button):
    def __init__(self, report_id: int, appeal: bool):
        self.report_id = report_id
        self.appeal = appeal
        super().__init__(
            label='הגש ערעור' if appeal else 'הוסף תגובה',
            style=discord.ButtonStyle.secondary if appeal else discord.ButtonStyle.primary,
            emoji='📎' if appeal else '💬',
            custom_id=f"report:{'appeal' if appeal else 'user_reply'}:{report_id}",
        )

    async def callback(self, interaction: discord.Interaction):
        if self.appeal:
            await interaction.response.send_modal(ReportAppealModal(self.report_id))
        else:
            await interaction.response.send_modal(ReportReplyModal(self.report_id))


class ReportUserView(discord.ui.View):
    def __init__(self, report_id: int, can_appeal: bool):
        super().__init__(timeout=None)
        self.add_item(ReportUserButton(report_id, appeal=False))
        if can_appeal:
            self.add_item(ReportUserButton(report_id, appeal=True))


def reporter_report_embed(report: Dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(
        title=f"עדכון על הדיווח שלך #{report['id']}",
        description=f"**סטטוס:** {report_status_label(report['status'])}\n**דווח על:** {report['target_user']}",
        color=EMBED_COLOR_PRIMARY,
    )
    if report.get('admin_response'):
        embed.add_field(name='💬 הודעת הצוות', value=report['admin_response'][:1024], inline=False)
    if report.get('punishment'):
        embed.add_field(name='⚖️ פעולה שנבחרה', value=report['punishment'], inline=False)
    if report['status'] == 'rejected':
        embed.description += (
            '\n\nהצוות לא אישר את הבקשה ובטוח שהמשתמש לא עשה דבר. '
            'אפשר להגיש ערעור ולהוסיף צילום מסך באמצעות הכפתור למטה.'
        )
    return embed


async def resolve_report_target(guild: discord.Guild, target_text: str):
    value = target_text.strip()
    match = re.fullmatch(r'<@!?(\d+)>', value)
    user_id = int(match.group(1)) if match else (int(value) if value.isdigit() else None)
    if user_id:
        member = guild.get_member(user_id)
        if member:
            return member, None
        try:
            return await guild.fetch_member(user_id), None
        except discord.NotFound:
            return None, 'המשתמש שדווח עליו אינו חבר בשרת.'
        except discord.HTTPException as exc:
            return None, f'לא ניתן למצוא את המשתמש: {exc}'
    lowered = value.casefold()
    for member in guild.members:
        if lowered in {member.name.casefold(), member.display_name.casefold(), (member.global_name or '').casefold()}:
            return member, None
    return None, 'לא מצאתי חבר שרת בשם הזה. בדיווח הבא השתמש בתיוג או במזהה Discord כדי לאפשר טיפול אוטומטי.'


async def refresh_report_log(guild: discord.Guild, report: Dict[str, Any]):
    channel_id = await db.get_report_channel(guild.id)
    channel = guild.get_channel(channel_id) if channel_id else None
    if not isinstance(channel, discord.TextChannel) or not report.get('log_message_id'):
        return
    try:
        message = await channel.fetch_message(report['log_message_id'])
        await message.edit(
            embed=build_report_embed(report),
            view=ReportReviewView(report['id'], disabled=report['status'] == 'approved'),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
        logger.warning('Could not update report log message %s: %s', report['id'], exc)


async def notify_reporter(guild: discord.Guild, report: Dict[str, Any]):
    try:
        user = bot.get_user(report['reporter_id']) or await bot.fetch_user(report['reporter_id'])
        view = ReportUserView(report['id'], can_appeal=report['status'] == 'rejected')
        embed = reporter_report_embed(report)
        if report.get('reporter_dm_message_id'):
            try:
                dm_channel = user.dm_channel or await user.create_dm()
                message = await dm_channel.fetch_message(report['reporter_dm_message_id'])
                await message.edit(embed=embed, view=view)
                return
            except (discord.NotFound, discord.HTTPException):
                pass
        message = await user.send(embed=embed, view=view)
        await db.update_report(report['id'], reporter_dm_message_id=message.id)
    except (discord.Forbidden, discord.HTTPException) as exc:
        logger.info('Could not DM report update to %s: %s', report['reporter_id'], exc)

@bot.event
async def on_ready():
    logger.info('═══════════════════════════════════════════════════')
    logger.info(f'🤖 הבוט מחובר בהצלחה בתור: {bot.user.name} (ID: {bot.user.id})')
    logger.info(f'🌐 שרתים מחוברים: {len(bot.guilds)}')
    logger.info('═══════════════════════════════════════════════════')
    await bot.tracker.sync_all_guilds()
    for guild in bot.guilds:
        try:
            settings = await db.get_guild_settings(guild.id)
            role_id = settings.get('verified_role_id')
            role = guild.get_role(role_id) if role_id else None
            if role:
                access_failures = await grant_verified_channel_access(guild, role)
                if access_failures:
                    logger.warning(
                        'Could not grant verified role access in some channels for guild %s: %s',
                        guild.id,
                        '; '.join(access_failures),
                    )
            if settings.get('verification_access_locked'):
                visible_ids = {
                    channel_id for channel_id in (
                        settings.get('verification_channel_id'),
                        settings.get('welcome_channel_id'),
                    ) if channel_id
                }
                lock_failures = await set_unverified_channel_lock(guild, True, visible_ids)
                role_id = settings.get('verified_role_id')
                role = guild.get_role(role_id) if role_id else None
                if role:
                    lock_failures.extend(await grant_verified_channel_access(guild, role))
                if lock_failures:
                    logger.warning(
                        'Could not apply unverified channel restrictions in guild %s: %s',
                        guild.id,
                        '; '.join(lock_failures),
                    )
            await refresh_legacy_ticket_channels(guild)
        except Exception:
            logger.exception('Failed to configure verified channel access for guild %s', guild.id)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='בוט של השרת-https://discord.gg/T7A6DfcMU'))

@bot.event
async def on_guild_join(guild: discord.Guild):
    await bot.tracker.sync_guild(guild)

@bot.event
async def on_guild_channel_create(channel: discord.abc.GuildChannel):
    guild = channel.guild
    settings = await db.get_guild_settings(guild.id)
    role_id = settings.get('verified_role_id')
    role = guild.get_role(role_id) if role_id else None
    if role:
        await grant_verified_channel_access(guild, role)
    if settings.get('verification_access_locked'):
        visible_ids = {
            channel_id for channel_id in (
                settings.get('verification_channel_id'),
                settings.get('welcome_channel_id'),
            ) if channel_id
        }
        await set_unverified_channel_lock(guild, True, visible_ids)
        if role:
            await grant_verified_channel_access(guild, role)

@bot.event
async def on_invite_create(invite: discord.Invite):
    bot.tracker.add_invite(invite)

@bot.event
async def on_invite_delete(invite: discord.Invite):
    bot.tracker.remove_invite(invite)

@bot.event
async def on_member_join(member: discord.Member):
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

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.roles != after.roles:
        settings = await db.get_guild_settings(after.guild.id)
        verified_role_id = settings.get('verified_role_id')
        verified_role = after.guild.get_role(verified_role_id) if verified_role_id else None
        if verified_role and verified_role in before.roles and verified_role not in after.roles:
            reason = bot._verification_revocation_reasons.pop((after.guild.id, after.id), None)
            if not reason:
                try:
                    async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                        if entry.target and entry.target.id == after.id:
                            reason = entry.reason
                            break
                except (discord.Forbidden, discord.HTTPException):
                    pass
            reason = reason or 'רול האימות הוסר על ידי צוות השרת.'
            await db.remove_verified_user(after.id, after.guild.id)
            await db.log_verification_event(after.id, after.guild.id, 'role_removed', reason)
            try:
                await after.send(
                    f'ℹ️ רול האימות שלך בשרת **{after.guild.name}** הוסר.\n**סיבה:** {reason}'
                )
            except discord.Forbidden:
                pass
            except discord.HTTPException as exc:
                logger.warning('Could not DM member %s about verification role removal: %s', after.id, exc)
    if not before.premium_since:
        if after.premium_since:
            await send_boost_announcement(after.guild, after)

@bot.event
async def on_message(message: discord.Message):
    if message.guild is None and not message.author.bot and message.attachments:
        pending_appeal = await db.get_report_waiting_for_appeal_image(message.author.id)
        if pending_appeal:
            image = next(
                (
                    item for item in message.attachments
                    if (item.content_type and item.content_type.startswith('image/'))
                    or item.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
                ),
                None,
            )
            if image:
                await db.update_report(pending_appeal['id'], appeal_image=image.url)
                updated_report = await db.get_report(pending_appeal['id'])
                guild = bot.get_guild(updated_report['guild_id'])
                if guild:
                    await refresh_report_log(guild, updated_report)
                await message.channel.send('✅ צילום המסך צורף לערעור ונשלח לצוות.')
                return
    boost_types = discord.MessageType.premium_guild_subscription, discord.MessageType.premium_guild_tier_1, discord.MessageType.premium_guild_tier_2, discord.MessageType.premium_guild_tier_3
    if message.type in boost_types and message.guild and isinstance(message.author, discord.Member):
        await send_boost_announcement(message.guild, message.author)
    await bot.process_commands(message)

def build_verification_panel_embed(guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(
        title='👑 ✦ שער האימות והאבטחה ✦ 👑',
        description=(
            '╭───────────────────────────────╮\n'
            '  👋 **ברוכים הבאים לשרת שלנו!**\n'
            '╰───────────────────────────────╯\n\n'
            '🛡️ **למה חובה לבצע אימות?**\n'
            '✦ **קהילה נקייה ובטוחה:** הגנה על השרת מפני בוטים, ספאמרים ורמאים.\n'
            '✦ **גישה מלאה לשרת:** לאחר האימות תוכלו לראות את כל חדרי השרת.\n'
            '✦ **חוויית קהילה טובה יותר:** האימות עוזר לוודא שמצטרפים משתמשים אמיתיים.\n\n'
            '⚡ **איך מאמתים את החשבון?**\n'
            'לחצו על כפתור **אמת** או הוסיפו תגובת ✅ להודעה, בהתאם לאפשרות שהוגדרה.\n'
            'תפקיד האימות יינתן ישירות בתוך השרת.\n\n'
            '🤖 **רוצים להוסיף את הבוט לשרת שלכם?**\n'
            'לחצו על **„הוסף את הבוט”** לקבלת קישורי ההוספה. האפשרות זמינה למי שקיבל את הרול **„גישה לבוט”**.\n\n'
            '> 💎 *כפתורי הפאנל ישלחו לכם תשובה פרטית; הפאנל הזה יישאר זמין לכולם.*'
        ),
        color=EMBED_COLOR_PRIMARY,
    )
    embed.set_footer(text=f'{guild.name} • מערכת אבטחה ואימות קהילתית ✨')
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    return embed


async def post_verification_panel(channel: discord.abc.Messageable, guild: discord.Guild):
    settings = await db.get_guild_settings(guild.id)
    role = guild.get_role(settings.get('verified_role_id')) if settings.get('verified_role_id') else None
    role = role or discord.utils.get(guild.roles, name='Verified') or discord.utils.get(guild.roles, name='מאומת')
    if role is None:
        role = await guild.create_role(name='Verified', reason='הגדרת מערכת אימות')
    await db.update_guild_settings(guild.id, verified_role_id=role.id, verification_channel_id=channel.id)
    panel_message = await channel.send(embed=build_verification_panel_embed(guild), view=VerifyView())
    bot.verification_configs[str(guild.id)] = {
        'channel_id': channel.id, 'message_id': panel_message.id,
        'role_id': role.id, 'method': 'button',
    }
    bot.save_verification_configs()


@bot.tree.command(name='verify_setup', description='שולח את פאנל האימות המעוצב לערוץ הנוכחי')
@app_commands.guild_only()
@app_commands.checks.has_permissions(administrator=True)
async def verify_setup_slash(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)
    await post_verification_panel(interaction.channel, interaction.guild)
    await interaction.followup.send('✅ פאנל האימות נשלח בהצלחה!', ephemeral=True)


@bot.command(name='setup')
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def setup_verification_command(ctx: commands.Context):
    channels = ctx.guild.text_channels[:25]
    if not channels:
        await ctx.send('לא נמצאו חדרי טקסט בשרת.')
        return
    await ctx.send(
        'בוא נגדיר אימות. בחרו ערוץ (מוצגים עד 25 ערוצים):',
        view=SetupView(bot, ctx.author.id, ctx.guild),
    )


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if bot.user is not None and payload.user_id == bot.user.id:
        return
    config = bot.verification_configs.get(str(payload.guild_id))
    if (
        config is None or config.get('method') != 'reaction'
        or payload.message_id != config.get('message_id')
        or str(payload.emoji) != VERIFY_EMOJI
    ):
        return
    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return
    member = payload.member or guild.get_member(payload.user_id)
    if member is None:
        try:
            member = await guild.fetch_member(payload.user_id)
        except discord.HTTPException:
            logger.exception('Could not fetch member %s', payload.user_id)
            return
    role = guild.get_role(config.get('role_id'))
    if role is None or role in member.roles:
        return
    blocked = await db.get_blocked_verification(member.id, guild.id)
    if blocked:
        return
    try:
        await member.add_roles(role, reason='השלמת אימות באמצעות תגובת ✅')
    except discord.Forbidden:
        logger.error('Missing permission to assign verification role in guild %s', guild.id)
        return
    except discord.HTTPException:
        logger.exception('Could not assign verification role in guild %s', guild.id)
        return
    await db.add_verified_user(member.id, guild.id)
    await db.log_verification_event(member.id, guild.id, 'success', 'אומת באמצעות תגובת ✅')

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

@bot.tree.command(name='lock_unverified_channels', description='מגביל משתמשים לא מאומתים לערוץ האימות וברוכים הבאים')
@app_commands.describe(enabled='הפעלת ההגבלה; false מסיר את הגדרת ההגבלה')
@app_commands.checks.has_permissions(administrator=True)
async def lock_unverified_channels_slash(interaction: discord.Interaction, enabled: bool = True):
    settings = await db.get_guild_settings(interaction.guild.id)
    verification_id = settings.get('verification_channel_id')
    welcome_id = settings.get('welcome_channel_id')
    if enabled and (not verification_id or not welcome_id):
        await interaction.response.send_message(
            '❌ צריך להגדיר קודם ערוץ אימות עם `/verify_setup` וערוץ ברוכים הבאים עם `/set_welcome_channel`.',
            ephemeral=True,
        )
        return
    await db.set_verification_access_locked(interaction.guild.id, enabled)
    visible_ids = {channel_id for channel_id in (verification_id, welcome_id) if channel_id}
    failures = await set_unverified_channel_lock(interaction.guild, enabled, visible_ids)
    if enabled:
        role_id = settings.get('verified_role_id')
        verified_role = interaction.guild.get_role(role_id) if role_id else None
        if verified_role:
            failures.extend(await grant_verified_channel_access(interaction.guild, verified_role))
    if failures:
        logger.warning('Failed to update channel restrictions in guild %s: %s', interaction.guild.id, '; '.join(failures))
        await interaction.response.send_message(
            f'⚠️ ההגדרה נשמרה, אך לא ניתן היה לעדכן {len(failures)} חדרים. בדוק שלבוט יש הרשאת Manage Channels.',
            ephemeral=True,
        )
        return
    status = 'הופעלה' if enabled else 'הוסרה'
    await interaction.response.send_message(
        f'✅ הגבלת הגישה למשתמשים לא מאומתים {status}.',
        ephemeral=True,
    )

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
            bot._verification_revocation_reasons[(guild_id, user.id)] = reason or 'בוטל על ידי מנהל.'
            await user.remove_roles(role, reason=f'אימות בוטל: {reason}')
        except Exception as e:
            bot._verification_revocation_reasons.pop((guild_id, user.id), None)
            await interaction.response.send_message(f'⚠️ שגיאה בהסרת הרול: {e}', ephemeral=True)
            return
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

@bot.tree.command(name='verify_block', description='חוסם משתמש מביצוע אימות בשרת')
@app_commands.describe(user='המשתמש לחסימה', reason='הסיבה לחסימה')
@app_commands.checks.has_permissions(administrator=True)
async def verify_block_slash(interaction: discord.Interaction, user: discord.Member, reason: str):
    await db.block_user_verification(user.id, interaction.guild.id, reason, interaction.user.id)
    await db.log_verification_event(user.id, interaction.guild.id, 'blocked', reason)
    try:
        await user.send(f'⛔ אינך יכול לבצע אימות בשרת **{interaction.guild.name}** כרגע.\n**סיבה:** {reason}')
    except (discord.Forbidden, discord.HTTPException):
        pass
    await interaction.response.send_message(
        f'⛔ {user.mention} נחסם מביצוע אימות. הסיבה תוצג לו כשהוא ילחץ על כפתור האימות.',
        ephemeral=True,
    )

@bot.tree.command(name='verify_unblock', description='מסיר חסימה של משתמש מאימות')
@app_commands.describe(user='המשתמש להסרת החסימה')
@app_commands.checks.has_permissions(administrator=True)
async def verify_unblock_slash(interaction: discord.Interaction, user: discord.Member):
    await db.unblock_user_verification(user.id, interaction.guild.id)
    await db.log_verification_event(user.id, interaction.guild.id, 'unblocked', f'Unblocked by {interaction.user.id}')
    await interaction.response.send_message(f'✅ חסימת האימות של {user.mention} הוסרה.', ephemeral=True)

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
    embed = discord.Embed(
        title='🚀 מערכת ההזמנות והפרסים של השרת! 🎁',
        description=(
            'ברוכים הבאים למרכז ההזמנות האישי שלך! כאן אפשר ליצור קישור, לעקוב אחרי המצטרפים ולנהל את ההזמנות שלך.\n\n'
            '🔗 **צור קישור** — יצירת קישור הזמנה אישי לשרת.\n'
            '📋 **ראה קישורים** — הצגת הקישורים הפעילים שלך ומספר המצטרפים מכל קישור.\n'
            '📊 **כמה אנשים נכנסו?** — צפייה בסך המצטרפים שהגיעו דרך ההזמנות שלך.\n'
            '🗑️ **אפס את כל הקישורים** — ביטול הקישורים האישיים שלך בלבד.\n\n'
            '🔒 התוצאות נשלחות אליך בפרטי, והפאנל נשאר זמין לאחר הלחיצה.'
        ),
        color=EMBED_COLOR_PRIMARY,
    )
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text='מערכת ההזמנות הרשמית ✨')
    await interaction.channel.send(embed=embed, view=InvitePanelView())
    await interaction.response.send_message('✅ פאנל ההזמנות נשלח בהצלחה!', ephemeral=True)


@bot.tree.command(name='ticket_setup', description='שולח את פאנל הטיקטים החדש (מנהלים בלבד)')
@app_commands.guild_only()
@app_commands.checks.has_permissions(administrator=True)
async def ticket_setup_slash(interaction: discord.Interaction):
    await bot.ticket_system.post_panel(interaction)


@bot.command(name='ticket_setup')
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def ticket_setup_command(ctx: commands.Context):
    await bot.ticket_system.post_panel(ctx)


@bot.tree.command(name='report_setup', description='שולח פאנל דיווח ומגדיר את חדר הלוגים לדיווחים')
@app_commands.describe(log_channel='חדר צוות פרטי שבו יופיעו דיווחים')
@app_commands.checks.has_permissions(administrator=True)
async def report_setup_slash(interaction: discord.Interaction, log_channel: discord.TextChannel):
    await db.set_report_channel(interaction.guild.id, log_channel.id)
    embed = discord.Embed(
        title='🚨 ✦ מערכת הדיווחים ✦ 🚨',
        description=(
            '📢 **ראית משהו חשוד? דווח!**\n'
            '━━━━━━━━━━━━━━━━━━━━\n\n'
            '🛡️ **כיצד הדיווח עוזר לקהילה?**\n'
            '✦ שמירה על סביבה בטוחה ונעימה לכולם.\n'
            '✦ הצוות מקבל את הדיווח ובוחן אותו במהירות.\n'
            '✦ כל דיווח נשאר פרטי וחסוי מהציבור.\n\n'
            '📝 **מה ממלאים בטופס?**\n'
            '1️⃣ שם המשתמש שעליו מדווחים.\n'
            '2️⃣ סיבת הדיווח (הטרדה, ספאם, שגיאה וכו׳).\n'
            '3️⃣ תיאור מפורט של המקרה.\n\n'
            '💎 *כל הדיווחים נבחנים ברצינות מלאה!*'
        ),
        color=EMBED_COLOR_PRIMARY,
    )
    embed.set_footer(text=f'{interaction.guild.name} • מערכת הדיווחים הרשמית 🛡️')
    await interaction.channel.send(embed=embed, view=ReportPanelView())
    await interaction.response.send_message(
        f'✅ פאנל הדיווחים נשלח לכאן. הדיווחים יישלחו אל {log_channel.mention}.',
        ephemeral=True,
    )

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


@bot.tree.command(name='give_access', description='נותן למשתמש גישה לכפתור הוספת הבוט (מנהלים בלבד)')
@app_commands.describe(member='המשתמש שרכש את חבילת הבוט ויקבל גישה')
@app_commands.checks.has_permissions(administrator=True)
async def give_access_slash(interaction: discord.Interaction, member: discord.Member):
    role = discord.utils.get(interaction.guild.roles, name='גישה לבוט')
    if not role:
        await interaction.response.send_message('❌ לא נמצא בשרת רול בשם „גישה לבוט”. צור את הרול ונסה שוב.', ephemeral=True)
        return
    try:
        await member.add_roles(role, reason=f'Bot package access granted by {interaction.user.id}')
    except discord.Forbidden:
        await interaction.response.send_message('❌ אין לבוט הרשאה לתת את הרול. ודא שרול הבוט נמצא מעל „גישה לבוט”.', ephemeral=True)
        return
    embed = discord.Embed(
        title='✨ הגישה לחבילת הבוט הופעלה',
        description=(
            f'המשתמש {member.mention} קיבל גישה להוספת הבוט לשרת שלו.\n\n'
            f'🎟️ הרול שניתן: {role.mention}\n'
            '🔓 כפתור **„הוסף את הבוט”** זמין עכשיו עבורו.'
        ),
        color=discord.Color.green(),
    )
    embed.set_footer(text=f'הגישה ניתנה על ידי {interaction.user.display_name}')
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name='remove_access', description='מסיר ממשתמש גישה לכפתור הוספת הבוט (מנהלים בלבד)')
@app_commands.describe(member='המשתמש שברצונך להסיר ממנו את הגישה')
@app_commands.checks.has_permissions(administrator=True)
async def remove_access_slash(interaction: discord.Interaction, member: discord.Member):
    role = discord.utils.get(interaction.guild.roles, name='גישה לבוט')
    if not role:
        await interaction.response.send_message('❌ לא נמצא בשרת רול בשם „גישה לבוט”.', ephemeral=True)
        return
    if role not in member.roles:
        await interaction.response.send_message(f'ℹ️ ל־{member.mention} אין כרגע את רול „גישה לבוט”.', ephemeral=True)
        return
    try:
        await member.remove_roles(role, reason=f'Bot package access revoked by {interaction.user.id}')
    except discord.Forbidden:
        await interaction.response.send_message('❌ אין לבוט הרשאה להסיר את הרול. ודא שרול הבוט נמצא מעל „גישה לבוט”.', ephemeral=True)
        return
    await interaction.response.send_message(f'✅ הוסר מ־{member.mention} רול „גישה לבוט”.', ephemeral=True)

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
