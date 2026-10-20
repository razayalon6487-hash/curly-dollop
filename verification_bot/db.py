# db.py
"""Unified SQLite database management for:
1. Invite tracking & statistics
2. Member joins history
3. Welcome, Panel, Boost, Leave, Verification & Report channel settings
4. Verification states, verified users, & blocked verifications
5. Security audit logs & Member reports system
"""

import os
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
import aiosqlite
from config import SETTINGS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "invites.db")


async def init_db():
    """Initialize all tables with full schema support."""
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Invites table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invites (
                code TEXT PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                inviter_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            );
        """)
        # 2. Joins history table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS joins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                invite_code TEXT,
                inviter_id INTEGER,
                joined_user_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL
            );
        """)
        # 3. Unified Guild settings table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                welcome_channel_id INTEGER,
                panel_channel_id INTEGER,
                verified_role_id INTEGER,
                verification_channel_id INTEGER,
                log_channel_id INTEGER,
                boost_channel_id INTEGER,
                leave_channel_id INTEGER,
                report_channel_id INTEGER,
                message_log_channel_id INTEGER,
                report_log_channel_id INTEGER,
                verify_log_channel_id INTEGER,
                ticket_log_channel_id INTEGER,
                verification_access_locked INTEGER NOT NULL DEFAULT 0
            );
        """)
        # Dynamic migrations for added columns if table was created earlier
        for col in ["boost_channel_id", "leave_channel_id", "report_channel_id", "verification_access_locked",
                    "message_log_channel_id", "report_log_channel_id", "verify_log_channel_id", "ticket_log_channel_id"]:
            try:
                await db.execute(f"ALTER TABLE guild_settings ADD COLUMN {col} INTEGER;")
            except Exception:
                pass

        # 4. Verification anti-CSRF state tokens
        await db.execute("""
            CREATE TABLE IF NOT EXISTS verification_states (
                state TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS app_monitor_states (
                state TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS app_monitor_tokens (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                refresh_token TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS app_monitor_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                owner_message_id INTEGER,
                log_message_id INTEGER,
                created_at INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_app_installations (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL DEFAULT '',
                installed INTEGER NOT NULL DEFAULT 1,
                updated_at INTEGER NOT NULL
            )
        """)
        # 5. Verified members directory
        await db.execute("""
            CREATE TABLE IF NOT EXISTS verified_users (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                verified_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, guild_id)
            );
        """)
        # 6. Blocked from verification blacklist
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blocked_verifications (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                blocked_by INTEGER NOT NULL,
                blocked_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, guild_id)
            );
        """)
        # 7. Verification security audit logs
        await db.execute("""
            CREATE TABLE IF NOT EXISTS verification_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                note TEXT,
                timestamp INTEGER NOT NULL
            );
        """)
        # 8. Reports system table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                reporter_id INTEGER NOT NULL,
                target_user TEXT NOT NULL,
                reason TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                admin_response TEXT,
                appeal_text TEXT,
                appeal_image TEXT,
                log_message_id INTEGER,
                created_at INTEGER NOT NULL
            );
        """)
        for column in ["reporter_response TEXT", "punishment TEXT", "reporter_dm_message_id INTEGER"]:
            try:
                await db.execute(f"ALTER TABLE reports ADD COLUMN {column};")
            except Exception:
                pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_access_users (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                granted_by INTEGER NOT NULL,
                granted_at INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
        """)
        await db.commit()


# --- Paid bot access ---

async def has_bot_access(guild_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM bot_access_users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cursor:
            return await cursor.fetchone() is not None


async def grant_bot_access(guild_id: int, user_id: int, granted_by: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO bot_access_users (guild_id, user_id, granted_by, granted_at) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, granted_by, int(time.time())),
        )
        await db.commit()


async def revoke_bot_access(guild_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM bot_access_users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


# --- Invite Management Functions ---

async def save_invite(code: str, guild_id: int, inviter_id: int, channel_id: int):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO invites (code, guild_id, inviter_id, channel_id, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (code, guild_id, inviter_id, channel_id, now))
        await db.commit()


async def get_user_invites(guild_id: int, inviter_id: int, only_active: bool = True) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT * FROM invites 
            WHERE guild_id = ? AND inviter_id = ?
        """
        if only_active:
            query += " AND is_active = 1"
        query += " ORDER BY created_at DESC"
        
        async with db.execute(query, (guild_id, inviter_id)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_invite_owner(code: str) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT inviter_id FROM invites WHERE code = ?", (code,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def deactivate_user_invites(guild_id: int, inviter_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            UPDATE invites 
            SET is_active = 0 
            WHERE guild_id = ? AND inviter_id = ? AND is_active = 1
        """, (guild_id, inviter_id))
        count = cursor.rowcount
        await db.commit()
        return count


async def record_join(guild_id: int, invite_code: Optional[str], inviter_id: Optional[int], joined_user_id: int):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO joins (guild_id, invite_code, inviter_id, joined_user_id, joined_at)
            VALUES (?, ?, ?, ?, ?)
        """, (guild_id, invite_code, inviter_id, joined_user_id, now))
        await db.commit()


async def get_user_total_joins(guild_id: int, inviter_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT COUNT(*) AS total 
            FROM joins 
            WHERE guild_id = ? AND inviter_id = ?
        """, (guild_id, inviter_id)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_invite_joins_count(guild_id: int, invite_code: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT COUNT(*) AS total 
            FROM joins 
            WHERE guild_id = ? AND invite_code = ?
        """, (guild_id, invite_code)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


# --- Channel & Feature Settings ---

async def set_welcome_channel(guild_id: int, channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_settings (guild_id, welcome_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET welcome_channel_id = excluded.welcome_channel_id
        """, (guild_id, channel_id))
        await db.commit()


async def get_welcome_channel(guild_id: int) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT welcome_channel_id FROM guild_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_panel_channel(guild_id: int, channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_settings (guild_id, panel_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET panel_channel_id = excluded.panel_channel_id
        """, (guild_id, channel_id))
        await db.commit()


async def get_panel_channel(guild_id: int) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT panel_channel_id FROM guild_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_boost_channel(guild_id: int, channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_settings (guild_id, boost_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET boost_channel_id = excluded.boost_channel_id
        """, (guild_id, channel_id))
        await db.commit()


async def get_boost_channel(guild_id: int) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT boost_channel_id FROM guild_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_leave_channel(guild_id: int, channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_settings (guild_id, leave_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET leave_channel_id = excluded.leave_channel_id
        """, (guild_id, channel_id))
        await db.commit()


async def get_leave_channel(guild_id: int) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT leave_channel_id FROM guild_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_report_channel(guild_id: int, channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_settings (guild_id, report_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET report_channel_id = excluded.report_channel_id
        """, (guild_id, channel_id))
        await db.commit()


async def get_report_channel(guild_id: int) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT report_channel_id FROM guild_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


# --- Verification States & Users ---

async def record_user_app_installation(user_id: int, username: str, installed: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_app_installations (user_id, username, installed, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                installed=excluded.installed,
                updated_at=excluded.updated_at
        """, (user_id, username, int(installed), int(time.time())))
        await db.commit()


async def get_user_app_installations(installed: bool = True) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, username, updated_at FROM user_app_installations WHERE installed=? ORDER BY updated_at DESC",
            (int(installed),),
        ) as cur:
            rows = await cur.fetchall()
    return [{"user_id": row[0], "username": row[1], "updated_at": row[2]} for row in rows]

async def store_app_monitor_state(state: str, user_id: int, guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO app_monitor_states VALUES (?, ?, ?, ?)", (state, user_id, guild_id, int(time.time())))
        await db.commit()


async def consume_app_monitor_state(state: str) -> Optional[Dict[str, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, guild_id, created_at FROM app_monitor_states WHERE state = ?", (state,)) as cur:
            row = await cur.fetchone()
        await db.execute("DELETE FROM app_monitor_states WHERE state = ?", (state,))
        await db.commit()
    if not row or int(time.time()) - row[2] > SETTINGS.STATE_EXPIRATION_SECONDS:
        return None
    return {"user_id": row[0], "guild_id": row[1]}


async def store_app_monitor_token(user_id: int, guild_id: int, encrypted_refresh_token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""INSERT INTO app_monitor_tokens VALUES (?, ?, ?, 'active', ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET refresh_token=excluded.refresh_token, status='active', updated_at=excluded.updated_at""",
            (user_id, guild_id, encrypted_refresh_token, int(time.time())))
        await db.commit()


async def get_active_app_monitor_tokens() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, guild_id, refresh_token FROM app_monitor_tokens WHERE status='active'") as cur:
            rows = await cur.fetchall()
    return [{"user_id": r[0], "guild_id": r[1], "refresh_token": r[2]} for r in rows]


async def deactivate_app_monitor_token(user_id: int, guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE app_monitor_tokens SET status='revoked', updated_at=? WHERE user_id=? AND guild_id=?", (int(time.time()), user_id, guild_id))
        await db.commit()


async def create_app_monitor_review(user_id: int, guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT INTO app_monitor_reviews (user_id, guild_id, created_at) VALUES (?, ?, ?)", (user_id, guild_id, int(time.time())))
        await db.commit()
        return cur.lastrowid


async def get_pending_app_monitor_reviews() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, user_id, guild_id, owner_message_id FROM app_monitor_reviews WHERE status='pending'") as cur:
            rows = await cur.fetchall()
    return [{"id": r[0], "user_id": r[1], "guild_id": r[2], "owner_message_id": r[3]} for r in rows]


async def set_app_monitor_review_message(review_id: int, message_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE app_monitor_reviews SET owner_message_id=? WHERE id=?", (message_id, review_id))
        await db.commit()


async def resolve_app_monitor_review(review_id: int, status: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("UPDATE app_monitor_reviews SET status=? WHERE id=? AND status='pending'", (status, review_id))
        await db.commit()
        return cur.rowcount > 0

async def store_verification_state(state: str, user_id: int, guild_id: int):
    ts = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO verification_states (state, user_id, guild_id, created_at) VALUES (?, ?, ?, ?)",
            (state, user_id, guild_id, ts),
        )
        await db.commit()


async def get_verification_state(state: str) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT state, user_id, guild_id, created_at FROM verification_states WHERE state = ?",
            (state,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            created = row[3]
            if int(time.time()) - created > SETTINGS.STATE_EXPIRATION_SECONDS:
                await delete_verification_state(state)
                return None
            return {
                "state": row[0],
                "user_id": row[1],
                "guild_id": row[2],
                "created_at": row[3],
            }


async def delete_verification_state(state: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM verification_states WHERE state = ?", (state,))
        await db.commit()


async def add_verified_user(user_id: int, guild_id: int):
    ts = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO verified_users (user_id, guild_id, verified_at) VALUES (?, ?, ?)",
            (user_id, guild_id, ts),
        )
        await db.commit()


async def remove_verified_user(user_id: int, guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM verified_users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
        await db.commit()


async def get_user_verification(user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, guild_id, verified_at FROM verified_users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return {"user_id": row[0], "guild_id": row[1], "verified_at": row[2]}


async def get_guild_verification_count(guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM verified_users WHERE guild_id = ?",
            (guild_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


# --- Blocked Verifications Management ---

async def block_user_verification(user_id: int, guild_id: int, reason: str, blocked_by: int):
    ts = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO blocked_verifications (user_id, guild_id, reason, blocked_by, blocked_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, guild_id, reason, blocked_by, ts))
        await db.commit()


async def unblock_user_verification(user_id: int, guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM blocked_verifications WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
        await db.commit()


async def get_blocked_verification(user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, guild_id, reason, blocked_by, blocked_at FROM blocked_verifications WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "user_id": row[0],
                "guild_id": row[1],
                "reason": row[2],
                "blocked_by": row[3],
                "blocked_at": row[4],
            }


async def log_verification_event(user_id: int, guild_id: int, status: str, note: Optional[str] = None):
    ts = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO verification_logs (user_id, guild_id, status, note, timestamp) VALUES (?, ?, ?, ?, ?)",
            (user_id, guild_id, status, note, ts),
        )
        await db.commit()


async def get_recent_logs(guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, user_id, status, note, timestamp FROM verification_logs WHERE guild_id = ? ORDER BY id DESC LIMIT ?",
            (guild_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {"id": r[0], "user_id": r[1], "status": r[2], "note": r[3], "timestamp": r[4]}
                for r in rows
            ]


# --- Combined Guild Settings ---

async def get_guild_settings(guild_id: int) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT welcome_channel_id, panel_channel_id, verified_role_id, verification_channel_id, log_channel_id, boost_channel_id, leave_channel_id, report_channel_id, verification_access_locked, message_log_channel_id, report_log_channel_id, verify_log_channel_id, ticket_log_channel_id FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "welcome_channel_id": row[0],
                    "panel_channel_id": row[1],
                    "verified_role_id": row[2] or SETTINGS.VERIFIED_ROLE_ID,
                    "verification_channel_id": row[3] or SETTINGS.VERIFICATION_CHANNEL_ID,
                    "log_channel_id": row[9] or row[4] or SETTINGS.LOG_CHANNEL_ID,
                    "boost_channel_id": row[5],
                    "leave_channel_id": row[6],
                    "report_channel_id": row[10] or row[7],
                    "message_log_channel_id": row[9] or row[4] or SETTINGS.LOG_CHANNEL_ID,
                    "report_log_channel_id": row[10] or row[7],
                    "verify_log_channel_id": row[11],
                    "ticket_log_channel_id": row[12],
                    "verification_access_locked": bool(row[8]),
                }
    return {
        "welcome_channel_id": None,
        "panel_channel_id": None,
        "verified_role_id": SETTINGS.VERIFIED_ROLE_ID,
        "verification_channel_id": SETTINGS.VERIFICATION_CHANNEL_ID,
        "log_channel_id": SETTINGS.LOG_CHANNEL_ID,
        "boost_channel_id": None,
        "leave_channel_id": None,
        "report_channel_id": None,
        "message_log_channel_id": SETTINGS.LOG_CHANNEL_ID,
        "report_log_channel_id": None,
        "verify_log_channel_id": None,
        "ticket_log_channel_id": None,
        "verification_access_locked": False,
    }


async def set_verification_access_locked(guild_id: int, enabled: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO guild_settings (guild_id, verification_access_locked) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET verification_access_locked = excluded.verification_access_locked",
            (guild_id, int(enabled)),
        )
        await db.commit()


async def update_guild_settings(
    guild_id: int,
    welcome_channel_id: Optional[int] = None,
    panel_channel_id: Optional[int] = None,
    verified_role_id: Optional[int] = None,
    verification_channel_id: Optional[int] = None,
    log_channel_id: Optional[int] = None,
    boost_channel_id: Optional[int] = None,
    leave_channel_id: Optional[int] = None,
    report_channel_id: Optional[int] = None,
    message_log_channel_id: Optional[int] = None,
    report_log_channel_id: Optional[int] = None,
    verify_log_channel_id: Optional[int] = None,
    ticket_log_channel_id: Optional[int] = None,
):
    current = await get_guild_settings(guild_id)
    w_ch = welcome_channel_id if welcome_channel_id is not None else current["welcome_channel_id"]
    p_ch = panel_channel_id if panel_channel_id is not None else current["panel_channel_id"]
    v_role = verified_role_id if verified_role_id is not None else current["verified_role_id"]
    v_ch = verification_channel_id if verification_channel_id is not None else current["verification_channel_id"]
    l_ch = log_channel_id if log_channel_id is not None else current["log_channel_id"]
    b_ch = boost_channel_id if boost_channel_id is not None else current["boost_channel_id"]
    lv_ch = leave_channel_id if leave_channel_id is not None else current["leave_channel_id"]
    rp_ch = report_channel_id if report_channel_id is not None else current["report_channel_id"]
    ml_ch = message_log_channel_id if message_log_channel_id is not None else current["message_log_channel_id"]
    rl_ch = report_log_channel_id if report_log_channel_id is not None else current["report_log_channel_id"]
    vl_ch = verify_log_channel_id if verify_log_channel_id is not None else current["verify_log_channel_id"]
    tl_ch = ticket_log_channel_id if ticket_log_channel_id is not None else current["ticket_log_channel_id"]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_settings (guild_id, welcome_channel_id, panel_channel_id, verified_role_id, verification_channel_id, log_channel_id, boost_channel_id, leave_channel_id, report_channel_id, message_log_channel_id, report_log_channel_id, verify_log_channel_id, ticket_log_channel_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                welcome_channel_id = excluded.welcome_channel_id,
                panel_channel_id = excluded.panel_channel_id,
                verified_role_id = excluded.verified_role_id,
                verification_channel_id = excluded.verification_channel_id,
                log_channel_id = excluded.log_channel_id,
                boost_channel_id = excluded.boost_channel_id,
                leave_channel_id = excluded.leave_channel_id,
                report_channel_id = excluded.report_channel_id,
                message_log_channel_id = excluded.message_log_channel_id,
                report_log_channel_id = excluded.report_log_channel_id,
                verify_log_channel_id = excluded.verify_log_channel_id,
                ticket_log_channel_id = excluded.ticket_log_channel_id
        """, (guild_id, w_ch, p_ch, v_role, v_ch, l_ch, b_ch, lv_ch, rp_ch, ml_ch, rl_ch, vl_ch, tl_ch))
        await db.commit()


# --- Reports Database System ---

async def create_report(guild_id: int, reporter_id: int, target_user: str, reason: str, description: str) -> int:
    ts = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO reports (guild_id, reporter_id, target_user, reason, description, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (guild_id, reporter_id, target_user, reason, description, ts))
        await db.commit()
        return cursor.lastrowid


async def get_report(report_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_reports_with_log_messages() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, guild_id, log_message_id, reporter_id, status, reporter_dm_message_id FROM reports WHERE log_message_id IS NOT NULL"
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "guild_id": row[1],
                    "log_message_id": row[2],
                    "reporter_id": row[3],
                    "status": row[4],
                    "reporter_dm_message_id": row[5],
                }
                for row in rows
            ]


async def get_report_waiting_for_appeal_image(reporter_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM reports WHERE reporter_id = ? AND status = 'appealed' AND appeal_text IS NOT NULL AND appeal_image IS NULL ORDER BY id DESC LIMIT 1",
            (reporter_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_report(
    report_id: int,
    status: Optional[str] = None,
    admin_response: Optional[str] = None,
    appeal_text: Optional[str] = None,
    appeal_image: Optional[str] = None,
    log_message_id: Optional[int] = None,
    reporter_response: Optional[str] = None,
    punishment: Optional[str] = None,
    reporter_dm_message_id: Optional[int] = None,
):
    current = await get_report(report_id)
    if not current:
        return
    st = status if status is not None else current["status"]
    adm = admin_response if admin_response is not None else current["admin_response"]
    app_t = appeal_text if appeal_text is not None else current["appeal_text"]
    app_i = appeal_image if appeal_image is not None else current["appeal_image"]
    msg_id = log_message_id if log_message_id is not None else current["log_message_id"]
    reporter_reply = reporter_response if reporter_response is not None else current.get("reporter_response")
    action = punishment if punishment is not None else current.get("punishment")
    dm_id = reporter_dm_message_id if reporter_dm_message_id is not None else current.get("reporter_dm_message_id")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE reports SET
                status = ?,
                admin_response = ?,
                appeal_text = ?,
                appeal_image = ?,
                log_message_id = ?,
                reporter_response = ?,
                punishment = ?,
                reporter_dm_message_id = ?
            WHERE id = ?
        """, (st, adm, app_t, app_i, msg_id, reporter_reply, action, dm_id, report_id))
        await db.commit()
