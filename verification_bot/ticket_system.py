import io
import asyncio
import html
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import discord
import db


logger = logging.getLogger("ticket_system")
TICKET_DATA_PATH = Path(__file__).resolve().with_name("ticket_data.json")
TICKET_CATEGORIES = {
    "staff_contact": ("🛡️ פנייה לצוות", "פנייה ישירה לצוות השרת."),
    "general": ("❔ שאלה כללית", "שאלה כללית או בקשת מידע."),
    "purchase": ("🛒 קנייה", "שאלות או בקשות בנוגע לרכישה."),
    "purchase_issue": ("⚠️ בעיה בקנייה", "עזרה עם רכישה שלא עברה או בעיית תשלום."),
    "bot_issue": ("🤖 בעיה בבוט", "דיווח על בעיה או תקלה בבוט."),
    "bug": ("🐛 באג", "דיווח על באג או התנהגות לא צפויה."),
    "report": ("🚨 דיווח על משתמש", "דיווח על הטרדה או הפרת חוקי השרת."),
}
TRANSCRIPT_LIMIT = 7 * 1024 * 1024
STAFF_ROLE_ID = 1560000264637784214
HIGH_STAFF_ROLE_ID = 1562057989920137348


def ticket_embed(title, description, color=None):
    return discord.Embed(
        title=title,
        description=description,
        color=color or discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    )


async def respond_with_embed(interaction, description, *, ephemeral=True, title="🎫 מערכת הטיקטים", color=None):
    sender = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
    await sender(
        embed=ticket_embed(title, description, color),
        ephemeral=ephemeral,
    )


async def followup_with_embed(interaction, description, *, ephemeral=True, title="🎫 מערכת הטיקטים", color=None):
    await interaction.followup.send(
        embed=ticket_embed(title, description, color),
        ephemeral=ephemeral,
    )


class TicketSystem:
    def __init__(self, bot):
        self.bot = bot
        self.data = self._load_data()
        self.pending_duplicate_opens = set()
        self.last_ticket_open = {}
        self.pending_closes = {}

    @staticmethod
    def _load_data():
        if not TICKET_DATA_PATH.exists():
            return {"tickets": {}, "banned_users": {}}
        try:
            with TICKET_DATA_PATH.open("r", encoding="utf-8") as data_file:
                data = json.load(data_file)
            if not isinstance(data, dict):
                raise ValueError("Ticket data must be a JSON object")
            data.setdefault("tickets", {})
            data.setdefault("banned_users", {})
            return data
        except (OSError, json.JSONDecodeError, ValueError):
            logger.exception("Could not load ticket data")
            return {"tickets": {}, "banned_users": {}}

    def save(self):
        temporary_path = TICKET_DATA_PATH.with_suffix(".tmp")
        with temporary_path.open("w", encoding="utf-8") as data_file:
            json.dump(self.data, data_file, ensure_ascii=False, indent=2)
        temporary_path.replace(TICKET_DATA_PATH)

    def register_persistent_views(self):
        self.bot.add_view(TicketPanelView(self))
        self.bot.add_view(TicketControlsView(self))
        self.bot.add_view(ClosedTicketView(self))

    async def lock_verified_role_out_of_existing_tickets(self, guild):
        """Repair existing ticket overwrites so verified users can't see others' tickets."""
        settings = await db.get_guild_settings(guild.id)
        role_id = settings.get("verified_role_id")
        verified_role = guild.get_role(role_id) if role_id else None
        if verified_role is None:
            return

        for ticket in self.data["tickets"].values():
            try:
                ticket_guild_id = int(ticket.get("guild_id", 0))
                channel_id = int(ticket.get("channel_id", 0))
            except (TypeError, ValueError):
                continue
            if ticket_guild_id != guild.id:
                continue
            channel = guild.get_channel(channel_id)
            if channel is None:
                continue
            overwrite = channel.overwrites_for(verified_role)
            if overwrite.view_channel is False:
                continue
            overwrite.view_channel = False
            try:
                await channel.set_permissions(
                    verified_role,
                    overwrite=overwrite,
                    reason="Keep ticket private from the verified role",
                )
            except (discord.Forbidden, discord.HTTPException):
                logger.exception("Could not restrict verified role in ticket %s", channel.id)

    async def post_panel(self, destination):
        interaction = isinstance(destination, discord.Interaction)
        if interaction:
            await destination.response.defer(ephemeral=True)
        channel = destination.channel
        embed = discord.Embed(
            title="🛠️ HACKTOOL | TICKET CENTER 🛠️",
            description=(
                "> **ברוכים הבאים למרכז הטיקטים והתמיכה הרשמי של HackTool!**\n"
                "> השרת שלנו כאן כדי לספק לכם את המענה המהיר, המקצועי והמדויק ביותר.\n"
                "> לפני פתיחת טיקט, אנא קראו את ההנחיות ובחרו את הקטגוריה המתאימה.\n\n"
                "---\n\n"
                "### 📜 **חוקים והנחיות חשובות**\n"
                "> 📌 **מידע מפורט:** הזינו את כל הפרטים, צילומי המסך או הודעות השגיאה כבר בהודעה הראשונה.\n"
                "> 📌 **סבלנות:** הצוות עונה בהקדם Possible. אין לתייג מנהלים או לפתוח טיקטים כפולים.\n"
                "> 📌 **כבוד הדדי:** שיח פוגעני או מזלזל יוביל לסגירת הטיקט ונקיטת צעדים.\n\n"
                "---\n\n"
                "### 📂 **נושאי הפניות וקטגוריות**\n\n"
                "🛡️ **פנייה לצוות** — פנייה ישירה לצוות השרת\n"
                "❔ **שאלה כללית** — שאלה כללית או בקשת מידע\n"
                "🛒 **קנייה** — שאלות או בקשות בנוגע לרכישה\n"
                "⚠️ **בעיה בקנייה** — עזרה עם רכישה או בעיית תשלום\n"
                "🤖 **בעיה בבוט** — דיווח על בעיה או תקלה בבוט\n"
                "🐛 **באג** — דיווח על באג או התנהגות לא צפויה\n"
                "🚨 **דיווח על משתמש** — דיווח על הטרדה או הפרת חוקי השרת\n\n"
                "```fix\nלחצו על הכפתור המתאים למטה כדי לפתוח טיקט חדש! 👇\n```"
            ),
            color=discord.Color.blurple(),
        )
        await channel.send(embed=embed, view=TicketPanelView(self))
        if interaction:
            await destination.followup.send("✅ פאנל הטיקטים נשלח לערוץ הזה.", ephemeral=True)
        else:
            await destination.send("✅ פאנל הטיקטים נשלח.")

    def staff_roles(self, guild):
        return [role for role_id in (STAFF_ROLE_ID, HIGH_STAFF_ROLE_ID) if (role := guild.get_role(role_id))]

    @staticmethod
    def is_staff(member):
        return isinstance(member, discord.Member) and any(
            role.id in (STAFF_ROLE_ID, HIGH_STAFF_ROLE_ID) for role in member.roles
        )

    @staticmethod
    def is_high_staff(member):
        return isinstance(member, discord.Member) and any(role.id == HIGH_STAFF_ROLE_ID for role in member.roles)

    @staticmethod
    async def send_ticket_log(guild, title, description, *, file=None):
        settings = await db.get_guild_settings(guild.id)
        channel_id = settings.get("ticket_log_channel_id")
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return False
        try:
            embed = ticket_embed(title, description)
            await channel.send(embed=embed, file=file, allowed_mentions=discord.AllowedMentions.none())
            return True
        except discord.HTTPException:
            logger.exception("Could not send ticket log in guild %s", guild.id)
            return False

    def ticket_for(self, interaction):
        if interaction.guild is None or interaction.channel is None:
            return None
        ticket = self.data["tickets"].get(str(interaction.channel.id))
        if ticket and ticket.get("guild_id") == interaction.guild.id:
            return ticket
        return None

    def can_manage_ticket(self, interaction, ticket):
        return self.is_staff(interaction.user)

    async def create_ticket(self, interaction, category_key, *, allow_duplicate=False):
        guild = interaction.guild
        if guild is None:
            await respond_with_embed(
                interaction,
                "אפשר לפתוח טיקט רק בתוך שרת Discord.",
                color=discord.Color.red(),
            )
            return

        user_id = str(interaction.user.id)
        guild_id = str(guild.id)
        banned_users = self.data["banned_users"].get(guild_id, [])
        if user_id in banned_users:
            await respond_with_embed(
                interaction,
                "נחסמתם מפתיחת טיקטים בשרת הזה. פנו לצוות אם זו טעות.",
                title="⛔ פתיחת טיקט חסומה",
                color=discord.Color.red(),
            )
            return

        existing = next(
            (
                ticket
                for ticket in self.data["tickets"].values()
                if ticket.get("guild_id") == guild.id
                and ticket.get("owner_id") == interaction.user.id
                and not ticket.get("closed")
                and guild.get_channel(ticket.get("channel_id")) is not None
            ),
            None,
        )
        if existing and not allow_duplicate:
            existing_channel = guild.get_channel(existing.get("channel_id"))
            description = (
                f"כבר יש לכם טיקט פתוח: {existing_channel.mention}\n\n"
                "אם מדובר בנושא אחר או בתקלה בטיקט הקיים, אפשר לפתוח טיקט נוסף. "
                "לחצו על הכפתור והמתינו 30 שניות לפני הפתיחה."
                if existing_channel
                else "כבר יש לכם טיקט פתוח. אם צריך לפתוח טיקט נוסף, לחצו למטה והמתינו 30 שניות."
            )
            await interaction.response.send_message(
                embed=ticket_embed("🎫 כבר יש לכם טיקט פתוח", description),
                view=OpenAnywayView(self, interaction.user.id, category_key),
                ephemeral=True,
            )
            return

        cooldown_key = (guild.id, interaction.user.id)
        loop = asyncio.get_running_loop()
        remaining = self.last_ticket_open.get(cooldown_key, 0) + 30 - loop.time()
        if remaining > 0 and not allow_duplicate:
            await respond_with_embed(
                interaction,
                f"כדי למנוע ספאם, אפשר לפתוח טיקט נוסף בעוד **{int(remaining) + 1} שניות**.",
                title="⏳ המתינו לפני פתיחת טיקט נוסף",
            )
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            parent = discord.utils.get(guild.categories, name="Tickets")
            if parent is None:
                parent = await guild.create_category("Tickets", reason="יצירת מערכת טיקטים")

            settings = await db.get_guild_settings(guild.id)
            verified_role_id = settings.get("verified_role_id")
            verified_role = guild.get_role(verified_role_id) if verified_role_id else None

            bot_member = guild.get_member(self.bot.user.id)
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False)
            }
            if verified_role is not None:
                overwrites[verified_role] = discord.PermissionOverwrite(view_channel=False)
            if bot_member is not None:
                overwrites[bot_member] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True,
                    manage_messages=True,
                    attach_files=True,
                )
            overwrites[interaction.user] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            )
            for role in self.staff_roles(guild):
                if role == verified_role:
                    continue
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                )

            username = re.sub(r"[^a-z0-9-]", "-", interaction.user.name.lower()).strip("-")
            username = username[:20] or "member"
            channel = await guild.create_text_channel(
                name=f"ticket-{category_key}-{username}",
                category=parent,
                topic=f"Ticket for {interaction.user} ({interaction.user.id}) | {category_key}",
                overwrites=overwrites,
                reason=f"Ticket opened by {interaction.user}",
            )
            ticket = {
                "channel_id": channel.id,
                "guild_id": guild.id,
                "owner_id": interaction.user.id,
                "category": category_key,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "claimed_by": None,
                "closed": False,
                "locked": False,
                "rating": None,
            }
            self.data["tickets"][str(channel.id)] = ticket
            self.save()
            self.last_ticket_open[cooldown_key] = loop.time()

            category_name = TICKET_CATEGORIES[category_key][0]
            opened_at = datetime.now(timezone.utc)
            welcome = discord.Embed(
                title=f"🎟️ טיקט חדש נפתח | נושא: {category_name}",
                description=(
                    f"שלום {interaction.user.mention}! 👋\n\n"
                    f"תודה שפנית לצוות התמיכה של **{guild.name}**.\n\n"
                    "כדי שנוכל לסייע לך, פרט/י את סיבת הפנייה:\n"
                    "• תיאור הבעיה / השאלה\n"
                    "• הוכחות / צילומי מסך (אם רלוונטי)\n"
                    "• שם משתמש / מזהה במשחק\n\n"
                    "⏳ חבר צוות יתפנה אליך בהקדם. אין צורך לתייג מנהלים לחינם."
                ),
                color=discord.Color.green(),
                timestamp=opened_at,
            )
            welcome.add_field(
                name="📋 פרטי הטיקט",
                value=(
                    f"**נושא:** {category_name}\n"
                    f"**נפתח על ידי:** {interaction.user.mention}\n"
                    f"**מזהה משתמש:** `{interaction.user.id}`\n"
                    f"**מזהה טיקט:** `{channel.id}`\n"
                    f"**נפתח:** <t:{int(opened_at.timestamp())}:F> (<t:{int(opened_at.timestamp())}:R>)"
                ),
                inline=False,
            )
            account_created_at = interaction.user.created_at
            welcome.add_field(
                name="👤 פרטי המשתמש",
                value=(
                    f"**גיל חשבון Discord:** <t:{int(account_created_at.timestamp())}:R>\n"
                    f"**נוצר בתאריך:** <t:{int(account_created_at.timestamp())}:F>"
                ),
                inline=False,
            )
            if interaction.user.joined_at is not None:
                welcome.add_field(
                    name="📅 הצטרפות לשרת",
                    value=f"<t:{int(interaction.user.joined_at.timestamp())}:F> (<t:{int(interaction.user.joined_at.timestamp())}:R>)",
                    inline=False,
                )
            await channel.send(embed=welcome, view=TicketControlsView(self))
            await self.send_ticket_log(
                guild,
                "🎫 טיקט חדש נפתח",
                f"**משתמש:** {interaction.user.mention} (`{interaction.user.id}`)\n**נושא:** {category_name}\n**ערוץ:** {channel.mention}\n**נפתח בתאריך:** {opened_at.isoformat()}",
            )
        except discord.Forbidden:
            await followup_with_embed(
                interaction,
                "חסרות לבוט הרשאות לניהול ערוצים או לצפייה/שליחה בערוץ החדש.",
                color=discord.Color.red(),
            )
            return
        except (discord.HTTPException, OSError):
            logger.exception("Could not open ticket in guild %s", guild.id)
            await followup_with_embed(
                interaction,
                "פתיחת הטיקט נכשלה. בדקו הרשאות ונסו שוב.",
                color=discord.Color.red(),
            )
            return

        await followup_with_embed(interaction, f"הטיקט נפתח בהצלחה: {channel.mention}", title="✅ הטיקט נפתח")

    async def open_duplicate_after_wait(self, interaction, category_key):
        key = (interaction.guild.id, interaction.user.id)
        if key in self.pending_duplicate_opens:
            await respond_with_embed(interaction, "בקשת פתיחה כבר ממתינה. הטיקט ייפתח בסיום ההמתנה.")
            return
        loop = asyncio.get_running_loop()
        remaining = self.last_ticket_open.get(key, 0) + 30 - loop.time()
        if remaining > 0:
            await respond_with_embed(
                interaction,
                f"פתחתם טיקט לפני רגע. נסו שוב בעוד **{int(remaining) + 1} שניות**.",
                title="⏳ המתינו מעט",
            )
            return

        self.pending_duplicate_opens.add(key)
        await interaction.response.defer(ephemeral=True, thinking=True)
        await interaction.followup.send("⏳ בקשתכם התקבלה. הטיקט ייפתח בעוד 30 שניות כדי למנוע ספאם.", ephemeral=True)
        try:
            await asyncio.sleep(30)
            await self.create_ticket(interaction, category_key, allow_duplicate=True)
        finally:
            self.pending_duplicate_opens.discard(key)

    async def close_ticket(self, interaction):
        ticket = self.ticket_for(interaction)
        if ticket is None:
            await respond_with_embed(interaction, "הערוץ הזה אינו טיקט פעיל.", color=discord.Color.red())
            return
        if interaction.user.id != ticket["owner_id"] and not self.is_staff(interaction.user):
            await respond_with_embed(interaction, "אין לך הרשאה לסגור את הטיקט הזה.", color=discord.Color.red())
            return
        if ticket.get("closed"):
            await respond_with_embed(interaction, "הטיקט כבר סגור.")
            return

        if interaction.channel.id in self.pending_closes:
            await respond_with_embed(interaction, "סגירת הטיקט כבר נספרת לאחור.")
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        close_at = datetime.now(timezone.utc).timestamp() + 10
        countdown = await interaction.channel.send(
            f"⏳ הטיקט ייסגר בעוד 10 שניות (<t:{int(close_at)}:R>). לאחר הסגירה הוא יוסתר ממך; הצוות יוכל לפתוח אותו מחדש.",
            allowed_mentions=discord.AllowedMentions.none(),
        )
        task = asyncio.create_task(self._finish_ticket_close(interaction.channel, ticket, interaction.user.id, countdown))
        self.pending_closes[interaction.channel.id] = task
        await interaction.followup.send("התחילה ספירה לאחור של 10 שניות לסגירת הטיקט.", ephemeral=True)

    async def _finish_ticket_close(self, channel, ticket, closed_by, countdown):
        try:
            await asyncio.sleep(10)
            guild = channel.guild
            closed_at = datetime.now(timezone.utc).isoformat()
            ticket["closed_at"] = closed_at
            transcript, filename = await self.build_transcript(channel, guild, ticket)
            await self.send_ticket_log(
                guild,
                "🔒 טיקט נסגר",
                f"**ערוץ:** #{channel.name} (`{channel.id}`)\n**נפתח על ידי:** <@{ticket['owner_id']}> (`{ticket['owner_id']}`)\n**נסגר על ידי:** <@{closed_by}> (`{closed_by}`)\n**נפתח בתאריך:** {ticket.get('created_at', 'לא ידוע')}\n**נסגר בתאריך:** {closed_at}",
                file=discord.File(io.BytesIO(transcript), filename=filename),
            )
            ticket["closed"] = True
            ticket["closed_by"] = closed_by
            ticket["closed_user_permissions"] = {}
            for target, overwrite in list(channel.overwrites.items()):
                if not isinstance(target, discord.Member) or target.id == getattr(self.bot.user, "id", None):
                    continue
                if self.is_staff(target):
                    overwrite.view_channel = True
                    overwrite.send_messages = True
                    await channel.set_permissions(target, overwrite=overwrite, reason="Keep ticket available to staff after close")
                    continue
                ticket["closed_user_permissions"][str(target.id)] = {
                    "view_channel": overwrite.view_channel,
                    "send_messages": overwrite.send_messages,
                }
                overwrite.view_channel = False
                overwrite.send_messages = False
                await channel.set_permissions(target, overwrite=overwrite, reason="Hide closed ticket from non-staff participants")
            for role in self.staff_roles(guild):
                await channel.set_permissions(
                    role,
                    overwrite=discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                    reason="Keep closed ticket available to staff",
                )
            self.save()
            await countdown.edit(
                content=f"🔒 הטיקט נסגר. התמליל נשמר בערוץ הלוגים. הצוות יכול לפתוח אותו מחדש או למחוק אותו.",
                view=ClosedTicketView(self),
            )
        except asyncio.CancelledError:
            raise
        except (discord.Forbidden, discord.HTTPException, OSError):
            logger.exception("Could not finish closing ticket %s", channel.id)
            try:
                await countdown.edit(content="⚠️ סגירת הטיקט נכשלה. הוא נשאר פתוח; בדקו את הרשאות הבוט ונסו שוב.", view=None)
            except discord.HTTPException:
                pass
        finally:
            if self.pending_closes.get(channel.id) is asyncio.current_task():
                self.pending_closes.pop(channel.id, None)

    async def build_transcript(self, channel, guild, ticket):
        created_at = ticket.get("created_at", "לא ידוע")
        closed_at = ticket.get("closed_at", "עדיין פתוח")
        header = (
            "<!doctype html><html lang=\"he\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>Ticket transcript</title><style>"
            "body{font:15px Arial,sans-serif;background:#16181c;color:#e5e7eb;max-width:900px;"
            "margin:24px auto;padding:0 16px}h1{color:#8ab4f8}.message{background:#22252b;"
            "border-radius:8px;padding:12px 16px;margin:12px 0}.meta{color:#aab2bf;font-size:13px}"
            ".content{white-space:pre-wrap;overflow-wrap:anywhere;margin-top:8px}a{color:#8ab4f8}"
            "</style></head><body>"
            f"<h1>Ticket #{channel.id}</h1>"
            f"<p>שרת: {html.escape(guild.name)} ({guild.id})<br>"
            f"נפתח: {html.escape(str(created_at))}<br>נסגר: {html.escape(str(closed_at))}</p>"
        )
        entries = []
        size = len(header.encode("utf-8"))
        truncated = False
        async for message in channel.history(limit=None, oldest_first=True):
            timestamp = message.created_at.astimezone(timezone.utc).isoformat()
            content = html.escape(message.content or "").replace("\n", "<br>")
            if message.embeds:
                embed_content = []
                for embed in message.embeds:
                    if embed.title:
                        embed_content.append(f"<strong>{html.escape(embed.title)}</strong>")
                    if embed.description:
                        embed_content.append(html.escape(embed.description).replace("\n", "<br>"))
                    for field in embed.fields:
                        embed_content.append(
                            f"<strong>{html.escape(field.name)}</strong>: "
                            f"{html.escape(field.value).replace(chr(10), '<br>')}"
                        )
                if embed_content:
                    content += "<div class=\"content\">" + "<br>".join(embed_content) + "</div>"
            if message.attachments:
                attachment_links = "<br>".join(
                    f"<a href=\"{html.escape(attachment.url, quote=True)}\">"
                    f"{html.escape(attachment.filename)}</a>"
                    for attachment in message.attachments
                )
                content += f"<div class=\"content\">Attachments:<br>{attachment_links}</div>"
            entry = (
                "<article class=\"message\"><div class=\"meta\">"
                f"{html.escape(str(message.author))} ({message.author.id}) — {html.escape(timestamp)}"
                f"</div><div class=\"content\">{content or '<em>No text content</em>'}</div></article>"
            )
            entry_size = len(entry.encode("utf-8"))
            if size + entry_size > TRANSCRIPT_LIMIT:
                truncated = True
                break
            entries.append(entry)
            size += entry_size
        if truncated:
            entries.append("<p><em>Transcript truncated at 7 MiB.</em></p>")
        transcript = (header + "".join(entries) + "</body></html>").encode("utf-8")
        return transcript, f"ticket-{channel.id}-transcript.html"

    async def send_transcript(self, interaction):
        ticket = self.ticket_for(interaction)
        if ticket is None or not self.can_manage_ticket(interaction, ticket):
            await respond_with_embed(interaction, "רק צוות השרת יכול להוריד את תמליל הטיקט הזה.", color=discord.Color.red())
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            transcript, filename = await self.build_transcript(interaction.channel, interaction.guild, ticket)
            await interaction.followup.send(
                embed=ticket_embed("📥 היסטוריית השיחה", "קובץ התמליל המלא מצורף להודעה להורדה."),
                file=discord.File(io.BytesIO(transcript), filename=filename),
                ephemeral=True,
            )
        except (discord.HTTPException, discord.Forbidden):
            logger.exception("Could not send transcript for ticket %s", interaction.channel.id)
            await interaction.followup.send(
                embed=ticket_embed("❌ יצירת התמליל נכשלה", "לא ניתן לשלוח את קובץ התמליל. בדקו את הרשאות הבוט ונסו שוב.", discord.Color.red()),
                ephemeral=True,
            )

    async def remind_staff(self, interaction):
        ticket = self.ticket_for(interaction)
        if ticket is None or not self.can_manage_ticket(interaction, ticket):
            await respond_with_embed(interaction, "אין לך הרשאה להשתמש בתזכורת הזו.", color=discord.Color.red())
            return
        if ticket.get("closed"):
            await respond_with_embed(interaction, "אי אפשר להזכיר לצוות בטיקט סגור.")
            return
        mentions = " ".join(role.mention for role in self.staff_roles(interaction.guild))
        try:
            await interaction.channel.send(
                content=mentions or None,
                embed=ticket_embed("🔔 תזכורת לצוות", f"{interaction.channel.mention} ממתין למענה."),
                allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
            )
        except discord.HTTPException:
            logger.exception("Could not send ticket reminder %s", interaction.channel.id)
            await respond_with_embed(interaction, "שליחת התזכורת נכשלה.", color=discord.Color.red())
            return
        await respond_with_embed(interaction, "נשלחה תזכורת לצוות.", title="✅ התזכורת נשלחה", color=discord.Color.green())

    async def add_member(self, interaction, raw_user_id):
        ticket = self.ticket_for(interaction)
        if ticket is None or not self.can_manage_ticket(interaction, ticket):
            await respond_with_embed(interaction, "אין לך הרשאה להוסיף חבר לטיקט הזה.", color=discord.Color.red())
            return
        if ticket.get("closed"):
            await respond_with_embed(interaction, "אי אפשר להוסיף חבר לטיקט סגור.")
            return
        match = re.fullmatch(r"<@!?(\d+)>|(\d+)", raw_user_id.strip())
        if match is None:
            await respond_with_embed(interaction, "הכניסו מזהה משתמש או תיוג תקין.", color=discord.Color.red())
            return
        user_id = int(match.group(1) or match.group(2))
        member = interaction.guild.get_member(user_id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(user_id)
            except discord.NotFound:
                await respond_with_embed(interaction, "המשתמש אינו נמצא בשרת.", color=discord.Color.red())
                return
            except discord.HTTPException:
                await respond_with_embed(interaction, "לא ניתן למצוא את המשתמש כרגע.", color=discord.Color.red())
                return
        try:
            await interaction.channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                reason=f"Added to ticket by {interaction.user}",
            )
        except discord.Forbidden:
            await respond_with_embed(interaction, "לבוט חסרה הרשאה לעדכן הרשאות ערוץ.", color=discord.Color.red())
            return
        except discord.HTTPException:
            logger.exception("Could not add member to ticket %s", interaction.channel.id)
            await respond_with_embed(interaction, "הוספת המשתמש נכשלה.", color=discord.Color.red())
            return
        await respond_with_embed(interaction, f"{member.mention} נוסף לטיקט.", title="✅ המשתמש נוסף", color=discord.Color.green())
        await interaction.channel.send(
            embed=ticket_embed("➕ משתמש נוסף לטיקט", f"{member.mention} נוסף על ידי {interaction.user.mention}.")
        )

    async def claim_ticket(self, interaction):
        ticket = self.ticket_for(interaction)
        if ticket is None or not self.is_staff(interaction.user):
            await respond_with_embed(interaction, "רק צוות השרת יכול לקחת אחריות על טיקט.", color=discord.Color.red())
            return
        if ticket.get("closed"):
            await respond_with_embed(interaction, "הטיקט סגור.")
            return
        claimed_by = ticket.get("claimed_by")
        if claimed_by and claimed_by != interaction.user.id:
            claimed_member = interaction.guild.get_member(claimed_by)
            claimed_name = claimed_member.mention if claimed_member else f"<@{claimed_by}>"
            await respond_with_embed(interaction, f"הטיקט כבר בטיפול של {claimed_name}.")
            return
        ticket["claimed_by"] = interaction.user.id
        try:
            staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
            high_role = interaction.guild.get_role(HIGH_STAFF_ROLE_ID)
            if staff_role:
                await interaction.channel.set_permissions(
                    staff_role,
                    overwrite=discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True),
                    reason=f"Ticket claimed by {interaction.user}",
                )
            if high_role:
                await interaction.channel.set_permissions(
                    high_role,
                    overwrite=discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                    reason="High staff can always write in claimed tickets",
                )
            await interaction.channel.set_permissions(
                interaction.user,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                reason="Allow the staff member handling this ticket to write",
            )
            self.save()
        except (discord.Forbidden, discord.HTTPException, OSError):
            logger.exception("Could not save ticket claim %s", interaction.channel.id)
            await respond_with_embed(interaction, "לקיחת האחריות נכשלה. בדקו הרשאות בוט.", color=discord.Color.red())
            return
        await respond_with_embed(interaction, "הטיקט כעת באחריותך.", title="📌 הטיקט נלקח לטיפול", color=discord.Color.green())
        await interaction.channel.send(
            embed=ticket_embed("📌 הטיקט נלקח לטיפול", f"{interaction.user.mention} לקח/ה אחריות על הטיקט.")
        )
        await self.send_ticket_log(interaction.guild, "📌 טיקט נלקח לטיפול", f"**טיקט:** {interaction.channel.mention}\n**אחראי:** {interaction.user.mention}")

    async def toggle_lock(self, interaction):
        ticket = self.ticket_for(interaction)
        if ticket is None or not self.is_staff(interaction.user):
            await respond_with_embed(interaction, "רק צוות השרת יכול לנעול טיקט.", color=discord.Color.red())
            return
        if ticket.get("closed"):
            await respond_with_embed(interaction, "הטיקט כבר סגור.")
            return
        owner = interaction.guild.get_member(ticket["owner_id"])
        if owner is None:
            await respond_with_embed(interaction, "לא ניתן למצוא את בעל הטיקט.", color=discord.Color.red())
            return
        locked = not ticket.get("locked", False)
        overwrite = interaction.channel.overwrites_for(owner)
        overwrite.view_channel = True
        overwrite.send_messages = not locked
        try:
            await interaction.channel.set_permissions(
                owner, overwrite=overwrite, reason=f"Ticket {'locked' if locked else 'unlocked'} by {interaction.user}"
            )
            ticket["locked"] = locked
            self.save()
        except discord.Forbidden:
            await respond_with_embed(interaction, "לבוט חסרה הרשאה לעדכן הרשאות ערוץ.", color=discord.Color.red())
            return
        except (discord.HTTPException, OSError):
            logger.exception("Could not toggle ticket lock %s", interaction.channel.id)
            await respond_with_embed(interaction, "עדכון הנעילה נכשל.", color=discord.Color.red())
            return
        await respond_with_embed(
            interaction,
            "הטיקט ננעל למשתמש." if locked else "הטיקט נפתח מחדש למשתמש.",
            title="🔒 נעילת הטיקט עודכנה",
            color=discord.Color.green(),
        )
        await interaction.channel.send(
            embed=ticket_embed(
                "🔒 הטיקט ננעל" if locked else "🔓 הטיקט נפתח",
                f"עודכן על ידי {interaction.user.mention}.",
            )
        )

    async def choose_department(self, interaction):
        ticket = self.ticket_for(interaction)
        if ticket is None or not self.is_staff(interaction.user):
            await respond_with_embed(interaction, "רק צוות השרת יכול להעביר טיקט.", color=discord.Color.red())
            return
        categories = interaction.guild.categories[:25]
        if not categories:
            await respond_with_embed(interaction, "לא נמצאו מחלקות בשרת.")
            return
        await interaction.response.send_message(
            embed=ticket_embed("🏷️ העברת טיקט", "בחרו קטגוריית שרת להעברת הטיקט:"),
            view=DepartmentTransferView(self, interaction.user.id, interaction.channel.id, categories),
            ephemeral=True,
        )

    async def transfer_ticket(self, interaction, category_id):
        ticket = self.ticket_for(interaction)
        if ticket is None or not self.is_staff(interaction.user):
            await respond_with_embed(interaction, "רק צוות השרת יכול להעביר טיקט.", color=discord.Color.red())
            return
        category = interaction.guild.get_channel(category_id)
        if not isinstance(category, discord.CategoryChannel):
            await respond_with_embed(interaction, "המחלקה שנבחרה אינה זמינה.", color=discord.Color.red())
            return
        try:
            await interaction.channel.edit(
                category=category,
                sync_permissions=False,
                reason=f"Ticket transferred by {interaction.user}",
            )
            ticket["department_id"] = category.id
            self.save()
        except discord.Forbidden:
            await respond_with_embed(interaction, "לבוט חסרה הרשאה להעביר את הערוץ.", color=discord.Color.red())
            return
        except (discord.HTTPException, OSError):
            logger.exception("Could not transfer ticket %s", interaction.channel.id)
            await respond_with_embed(interaction, "העברת הטיקט נכשלה.", color=discord.Color.red())
            return
        await respond_with_embed(
            interaction,
            f"הטיקט הועבר אל **{category.name}**.",
            title="✅ הטיקט הועבר",
            color=discord.Color.green(),
        )

    async def ban_from_tickets(self, interaction):
        ticket = self.ticket_for(interaction)
        if ticket is None or not self.is_staff(interaction.user):
            await respond_with_embed(interaction, "רק צוות השרת יכול לחסום משתמש ממערכת הטיקטים.", color=discord.Color.red())
            return
        owner = interaction.guild.get_member(ticket["owner_id"])
        if owner is None:
            try:
                owner = await interaction.guild.fetch_member(ticket["owner_id"])
            except discord.NotFound:
                owner = None
            except discord.HTTPException:
                await respond_with_embed(
                    interaction,
                    "לא ניתן לבדוק כרגע אם בעל הטיקט הוא חבר צוות.",
                    color=discord.Color.red(),
                )
                return
        if owner is not None and self.is_staff(owner):
            await respond_with_embed(interaction, "אי אפשר לחסום חבר צוות ממערכת הטיקטים.", color=discord.Color.red())
            return
        guild_id = str(interaction.guild.id)
        banned_users = self.data["banned_users"].setdefault(guild_id, [])
        owner_id = str(ticket["owner_id"])
        if owner_id not in banned_users:
            banned_users.append(owner_id)
        try:
            self.save()
        except OSError:
            logger.exception("Could not save ticket ban in guild %s", interaction.guild.id)
            await respond_with_embed(interaction, "שמירת החסימה נכשלה.", color=discord.Color.red())
            return
        await respond_with_embed(
            interaction,
            f"המשתמש <@{owner_id}> נחסם מפתיחת טיקטים חדשים בשרת.",
            title="⛔ המשתמש נחסם מטיקטים",
            color=discord.Color.red(),
        )

    async def unban_from_tickets(self, interaction, raw_user_id):
        if interaction.guild is None or not self.is_staff(interaction.user):
            await respond_with_embed(interaction, "רק צוות השרת יכול להסיר חסימה.", color=discord.Color.red())
            return
        match = re.fullmatch(r"<@!?(\d+)>|(\d+)", raw_user_id.strip())
        if match is None:
            await respond_with_embed(interaction, "הכניסו מזהה משתמש או תיוג תקין.", color=discord.Color.red())
            return
        user_id = match.group(1) or match.group(2)
        banned_users = self.data["banned_users"].setdefault(str(interaction.guild.id), [])
        if user_id not in banned_users:
            await respond_with_embed(interaction, "המשתמש הזה אינו חסום מטיקטים.")
            return
        banned_users.remove(user_id)
        try:
            self.save()
        except OSError:
            logger.exception("Could not remove ticket ban for user %s in guild %s", user_id, interaction.guild.id)
            await respond_with_embed(interaction, "הסרת החסימה נכשלה.", color=discord.Color.red())
            return
        await respond_with_embed(
            interaction,
            f"הוסרה החסימה של <@{user_id}>; כעת הוא יכול לפתוח טיקטים.",
            title="🔓 החסימה הוסרה",
            color=discord.Color.green(),
        )

    async def rate_ticket(self, interaction, rating):
        ticket = self.ticket_for(interaction)
        if ticket is None or interaction.user.id != ticket["owner_id"]:
            await respond_with_embed(interaction, "רק בעל הטיקט יכול לדרג אותו.", color=discord.Color.red())
            return
        if not ticket.get("closed"):
            await respond_with_embed(interaction, "אפשר לדרג את הטיקט לאחר סגירתו.")
            return
        if ticket.get("rating") is not None:
            await respond_with_embed(interaction, "הדירוג שלך כבר נשמר, תודה!")
            return
        ticket["rating"] = rating
        ticket["rated_by"] = interaction.user.id
        try:
            self.save()
        except OSError:
            logger.exception("Could not save ticket rating %s", interaction.channel.id)
            await respond_with_embed(interaction, "שמירת הדירוג נכשלה.", color=discord.Color.red())
            return
        await respond_with_embed(
            interaction,
            f"תודה על הדירוג: {'⭐' * rating}",
            title="⭐ הדירוג נשמר",
            color=discord.Color.green(),
        )
        await interaction.channel.send(
            embed=ticket_embed("⭐ התקבל דירוג שירות", f"{interaction.user.mention} דירג/ה את השירות: **{rating}/5**.")
        )


class OpenAnywayView(discord.ui.View):
    def __init__(self, ticket_system, author_id, category_key):
        super().__init__(timeout=180)
        self.ticket_system = ticket_system
        self.author_id = author_id
        self.category_key = category_key

    @discord.ui.button(label="פתח בכל זאת · המתנה של 30 שניות", style=discord.ButtonStyle.primary, emoji="⏳")
    async def open_anyway(self, interaction, button):
        if interaction.user.id != self.author_id:
            await respond_with_embed(interaction, "הכפתור הזה שייך למי שביקש לפתוח את הטיקט.", color=discord.Color.red())
            return
        await self.ticket_system.open_duplicate_after_wait(interaction, self.category_key)


class TicketPanelView(discord.ui.View):
    def __init__(self, ticket_system):
        super().__init__(timeout=None)
        self.ticket_system = ticket_system
        self.add_item(TicketCategorySelect(ticket_system))

    @discord.ui.button(label="🔓 הסר חסימה מטיקטים", style=discord.ButtonStyle.secondary, custom_id="tickets:unban", row=1)
    async def unban(self, interaction, button):
        if not self.ticket_system.is_staff(interaction.user):
            await respond_with_embed(interaction, "רק צוות השרת יכול להסיר חסימה.", color=discord.Color.red())
            return
        await interaction.response.send_modal(UnbanTicketUserModal(self.ticket_system))


class TicketCategorySelect(discord.ui.Select):
    def __init__(self, ticket_system):
        self.ticket_system = ticket_system
        options = [
            discord.SelectOption(label=label, value=key, description=description)
            for key, (label, description) in TICKET_CATEGORIES.items()
        ]
        super().__init__(
            custom_id="tickets:category",
            placeholder="⬇️ בחרו את נושא הפנייה",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        await self.ticket_system.create_ticket(interaction, self.values[0])


class TicketControlsView(discord.ui.View):
    def __init__(self, ticket_system):
        super().__init__(timeout=None)
        self.ticket_system = ticket_system

    async def interaction_check(self, interaction):
        custom_id = (interaction.data or {}).get("custom_id", "")
        if custom_id == "tickets:close" or self.ticket_system.is_staff(interaction.user):
            return True
        await respond_with_embed(interaction, "רק צוות השרת יכול להשתמש בכפתורי הטיקט; אפשר ללחוץ על סגור טיקט.", color=discord.Color.red())
        return False

    @discord.ui.button(label="🔒 סגור טיקט", style=discord.ButtonStyle.danger, custom_id="tickets:close", row=0)
    async def close(self, interaction, button):
        await self.ticket_system.close_ticket(interaction)

    @discord.ui.button(label="🔔 תזכורת לצוות", style=discord.ButtonStyle.secondary, custom_id="tickets:remind", row=0)
    async def remind(self, interaction, button):
        await self.ticket_system.remind_staff(interaction)

    @discord.ui.button(label="➕ הוסף חבר", style=discord.ButtonStyle.secondary, custom_id="tickets:add_member", row=0)
    async def add_member(self, interaction, button):
        await interaction.response.send_modal(AddTicketMemberModal(self.ticket_system))

    @discord.ui.button(label="📥 תמליל", style=discord.ButtonStyle.secondary, custom_id="tickets:transcript", row=1)
    async def transcript(self, interaction, button):
        await self.ticket_system.send_transcript(interaction)

    @discord.ui.button(label="📌 קח אחריות", style=discord.ButtonStyle.primary, custom_id="tickets:claim", row=1)
    async def claim(self, interaction, button):
        await self.ticket_system.claim_ticket(interaction)

    @discord.ui.button(label="🔐 נעילה / פתיחה", style=discord.ButtonStyle.secondary, custom_id="tickets:lock", row=1)
    async def lock(self, interaction, button):
        await self.ticket_system.toggle_lock(interaction)

    @discord.ui.button(label="🏷️ העבר מחלקה", style=discord.ButtonStyle.secondary, custom_id="tickets:transfer", row=2)
    async def transfer(self, interaction, button):
        await self.ticket_system.choose_department(interaction)

    @discord.ui.button(label="⛔ חסום מטיקטים", style=discord.ButtonStyle.danger, custom_id="tickets:ban", row=2)
    async def ban(self, interaction, button):
        await self.ticket_system.ban_from_tickets(interaction)

    @discord.ui.button(label="🚨 התראה לצוות הגבוה", style=discord.ButtonStyle.danger, custom_id="tickets:high_alert", row=3)
    async def high_alert(self, interaction, button):
        ticket = self.ticket_system.ticket_for(interaction)
        if ticket is None or not self.ticket_system.is_staff(interaction.user):
            await respond_with_embed(interaction, "רק צוות השרת יכול לשלוח התראה לצוות הגבוה.", color=discord.Color.red())
            return
        await interaction.response.send_modal(HighStaffAlertModal(self.ticket_system, interaction.channel.id))


class HighStaffAlertModal(discord.ui.Modal, title="התראה לצוות הגבוה"):
    reason = discord.ui.TextInput(label="סיבת ההתראה", style=discord.TextStyle.paragraph, max_length=1000)

    def __init__(self, ticket_system, channel_id):
        super().__init__()
        self.ticket_system = ticket_system
        self.channel_id = channel_id

    async def on_submit(self, interaction):
        ticket = self.ticket_system.data["tickets"].get(str(self.channel_id))
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        high_role = interaction.guild.get_role(HIGH_STAFF_ROLE_ID) if interaction.guild else None
        if not ticket or not channel or not high_role:
            await interaction.response.send_message("הטיקט או רול הצוות הגבוה לא זמינים.", ephemeral=True)
            return
        reason = str(self.reason.value).strip()
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await channel.send(
                content=f"🚨 {high_role.mention} נשלחה התראה על ידי {interaction.user.mention}. הצוות הגבוה מתבקש לבדוק את הטיקט.",
                embed=ticket_embed("🚨 התראה לצוות הגבוה", reason),
                allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
            )
            delivered = 0
            ticket_url = f"https://discord.com/channels/{interaction.guild.id}/{channel.id}"
            for member in high_role.members:
                try:
                    await member.send(
                        embed=ticket_embed("🚨 התראה על טיקט", f"**שרת:** {interaction.guild.name}\n**קישור לטיקט:** {ticket_url}\n**נשלח על ידי:** {interaction.user} (`{interaction.user.id}`)\n**סיבה:** {reason}\n\nהצוות ממתין למענה שלכם."),
                        view=HighStaffResponseView(self.ticket_system, interaction.guild.id, channel.id),
                    )
                    delivered += 1
                except discord.HTTPException:
                    continue
            await self.ticket_system.send_ticket_log(interaction.guild, "🚨 התראה לצוות הגבוה", f"**טיקט:** {channel.mention}\n**נשלחה על ידי:** {interaction.user.mention}\n**נשלחו הודעות בפרטי:** {delivered}\n**סיבה:** {reason}")
            await interaction.followup.send(f"ההתראה נשלחה בפרטי ל־{delivered} חברי צוות גבוה.", ephemeral=True)
        except discord.HTTPException:
            logger.exception("Could not send high-staff ticket alert for %s", channel.id)
            await interaction.followup.send("לא הצלחתי לשלוח את ההתראה כרגע.", ephemeral=True)


class HighStaffResponseView(discord.ui.View):
    def __init__(self, ticket_system, guild_id, channel_id):
        super().__init__(timeout=7 * 24 * 60 * 60)
        self.ticket_system = ticket_system
        self.guild_id = guild_id
        self.channel_id = channel_id

    @discord.ui.button(label="הוסף מענה / סיבה", style=discord.ButtonStyle.primary)
    async def respond(self, interaction, button):
        guild = self.ticket_system.bot.get_guild(self.guild_id)
        member = guild.get_member(interaction.user.id) if guild else None
        if guild and member is None:
            try:
                member = await guild.fetch_member(interaction.user.id)
            except discord.HTTPException:
                member = None
        if member is None or not self.ticket_system.is_high_staff(member):
            await interaction.response.send_message("האפשרות מיועדת לצוות הגבוה בלבד.", ephemeral=True)
            return
        await interaction.response.send_modal(HighStaffReplyModal(self.ticket_system, self.guild_id, self.channel_id))


class HighStaffReplyModal(discord.ui.Modal, title="מענה צוות גבוה"):
    reason = discord.ui.TextInput(label="המענה או הסיבה", style=discord.TextStyle.paragraph, max_length=1000)

    def __init__(self, ticket_system, guild_id, channel_id):
        super().__init__()
        self.ticket_system = ticket_system
        self.guild_id = guild_id
        self.channel_id = channel_id

    async def on_submit(self, interaction):
        guild = self.ticket_system.bot.get_guild(self.guild_id)
        channel = guild.get_channel(self.channel_id) if guild else None
        member = guild.get_member(interaction.user.id) if guild else None
        if guild and member is None:
            try:
                member = await guild.fetch_member(interaction.user.id)
            except discord.HTTPException:
                member = None
        if not channel or not member or not self.ticket_system.is_high_staff(member):
            await interaction.response.send_message("ההרשאה או הטיקט אינם זמינים.", ephemeral=True)
            return
        reason = str(self.reason.value).strip()
        await channel.send(embed=ticket_embed("📬 מענה מהצוות הגבוה", f"**מאת:** {member.mention}\n**מענה:** {reason}"))
        await self.ticket_system.send_ticket_log(guild, "📬 מענה צוות גבוה לטיקט", f"**טיקט:** {channel.mention}\n**מאת:** {member.mention}\n**מענה:** {reason}")
        await interaction.response.send_message("המענה נשלח לטיקט ונרשם בלוג.", ephemeral=True)


class AddTicketMemberModal(discord.ui.Modal, title="הוספת חבר לטיקט"):
    user_id = discord.ui.TextInput(
        label="מזהה משתמש או תיוג",
        placeholder="לדוגמה: 123456789012345678 או @user",
        max_length=30,
    )

    def __init__(self, ticket_system):
        super().__init__()
        self.ticket_system = ticket_system

    async def on_submit(self, interaction):
        await self.ticket_system.add_member(interaction, str(self.user_id))


class UnbanTicketUserModal(discord.ui.Modal, title="הסרת חסימה מטיקטים"):
    user_id = discord.ui.TextInput(
        label="מזהה המשתמש או תיוג",
        placeholder="לדוגמה: 123456789012345678 או @user",
        max_length=30,
    )

    def __init__(self, ticket_system):
        super().__init__()
        self.ticket_system = ticket_system

    async def on_submit(self, interaction):
        await self.ticket_system.unban_from_tickets(interaction, str(self.user_id))


class DepartmentTransferView(discord.ui.View):
    def __init__(self, ticket_system, author_id, channel_id, categories):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.add_item(DepartmentSelect(ticket_system, channel_id, categories))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await respond_with_embed(interaction, "רק מי שפתח את התפריט יכול להשתמש בו.", color=discord.Color.red())
            return False
        return True


class DepartmentSelect(discord.ui.Select):
    def __init__(self, ticket_system, channel_id, categories):
        self.ticket_system = ticket_system
        self.channel_id = channel_id
        super().__init__(
            placeholder="בחרו מחלקה",
            min_values=1,
            max_values=1,
            options=[discord.SelectOption(label=category.name[:100], value=str(category.id)) for category in categories],
        )

    async def callback(self, interaction):
        if interaction.channel_id != self.channel_id:
            await respond_with_embed(interaction, "הערוץ כבר אינו זמין.", color=discord.Color.red())
            return
        await self.ticket_system.transfer_ticket(interaction, int(self.values[0]))


class ClosedTicketView(discord.ui.View):
    def __init__(self, ticket_system):
        super().__init__(timeout=None)
        self.ticket_system = ticket_system

    async def interaction_check(self, interaction):
        if self.ticket_system.is_staff(interaction.user):
            return True
        await respond_with_embed(interaction, "רק צוות השרת יכול לבצע פעולות בטיקט סגור.", color=discord.Color.red())
        return False

    @discord.ui.button(label="📥 הורדת תמליל", style=discord.ButtonStyle.secondary, custom_id="tickets:closed_transcript", row=0)
    async def transcript(self, interaction, button):
        await self.ticket_system.send_transcript(interaction)

    @discord.ui.button(label="🔓 פתח מחדש", style=discord.ButtonStyle.success, custom_id="tickets:reopen", row=0)
    async def reopen(self, interaction, button):
        ticket = self.ticket_system.ticket_for(interaction)
        if not ticket or not self.ticket_system.is_staff(interaction.user):
            await respond_with_embed(interaction, "רק צוות השרת יכול לפתוח טיקט מחדש.", color=discord.Color.red())
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        permission_values = ticket.get("closed_user_permissions", {})
        try:
            for raw_id, values in permission_values.items():
                member = interaction.guild.get_member(int(raw_id))
                if member is None:
                    continue
                overwrite = interaction.channel.overwrites_for(member)
                overwrite.view_channel = values.get("view_channel")
                overwrite.send_messages = values.get("send_messages")
                await interaction.channel.set_permissions(member, overwrite=overwrite, reason=f"Ticket reopened by {interaction.user}")
            ticket["closed"] = False
            ticket["reopened_by"] = interaction.user.id
            ticket["reopened_at"] = datetime.now(timezone.utc).isoformat()
            ticket.pop("closed_user_permissions", None)
            self.ticket_system.save()
            await interaction.message.edit(content=None, view=TicketControlsView(self.ticket_system))
            await interaction.channel.send(f"🔓 הטיקט נפתח מחדש על ידי {interaction.user.mention}.")
            await self.ticket_system.send_ticket_log(interaction.guild, "🔓 טיקט נפתח מחדש", f"**טיקט:** {interaction.channel.mention}\n**נפתח מחדש על ידי:** {interaction.user.mention}")
            await interaction.followup.send("הטיקט נפתח מחדש.", ephemeral=True)
        except (discord.HTTPException, OSError):
            logger.exception("Could not reopen ticket %s", interaction.channel.id)
            await interaction.followup.send("לא הצלחתי לפתוח מחדש את הטיקט.", ephemeral=True)

    @discord.ui.button(label="🗑️ מחק לצמיתות", style=discord.ButtonStyle.danger, custom_id="tickets:delete", row=0)
    async def delete(self, interaction, button):
        ticket = self.ticket_system.ticket_for(interaction)
        if not ticket or not self.ticket_system.is_staff(interaction.user):
            await respond_with_embed(interaction, "רק צוות השרת יכול למחוק טיקט.", color=discord.Color.red())
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        channel = interaction.channel
        await self.ticket_system.send_ticket_log(interaction.guild, "🗑️ טיקט נמחק לצמיתות", f"**ערוץ:** #{channel.name} (`{channel.id}`)\n**נמחק על ידי:** {interaction.user.mention}")
        self.ticket_system.data["tickets"].pop(str(channel.id), None)
        try:
            self.ticket_system.save()
            await channel.delete(reason=f"Ticket permanently deleted by {interaction.user}")
            await interaction.followup.send("הטיקט נמחק לצמיתות.", ephemeral=True)
        except (discord.HTTPException, OSError):
            logger.exception("Could not delete ticket %s", channel.id)
            await interaction.followup.send("מחיקת הטיקט נכשלה. נסו שוב.", ephemeral=True)
