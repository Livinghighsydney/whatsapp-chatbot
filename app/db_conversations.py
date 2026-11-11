"""DB helpers for conversations and messages (replaces in-memory state.py)."""
from __future__ import annotations

import logging
from app import db

logger = logging.getLogger(__name__)

_COLS = (
    "id", "tenant_phone", "tenant_name", "property_address", "room",
    "status", "assigned_staff_id", "session_id", "handoff_reason", "info_collected",
)


def _row(row) -> dict:
    d = dict(zip(_COLS, row))
    # Stringify UUIDs
    if d.get("id"):
        d["id"] = str(d["id"])
    if d.get("assigned_staff_id"):
        d["assigned_staff_id"] = str(d["assigned_staff_id"])
    return d


def get_or_create(phone: str) -> dict:
    sel = ", ".join(_COLS)
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(f"SELECT {sel} FROM conversations WHERE tenant_phone = %s", [phone])
        row = cur.fetchone()
        if row:
            return _row(row)
        cur.execute(
            f"INSERT INTO conversations (tenant_phone) VALUES (%s) RETURNING {sel}",
            [phone],
        )
        return _row(cur.fetchone())


def update(phone: str, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = %s" for k in fields)
    vals = list(fields.values()) + [phone]
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            f"UPDATE conversations SET {cols}, updated_at = NOW() WHERE tenant_phone = %s",
            vals,
        )


def add_message(phone: str, role: str, content: str) -> None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("SELECT id FROM conversations WHERE tenant_phone = %s", [phone])
        row = cur.fetchone()
        if not row:
            return
        cur.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (%s, %s, %s)",
            [row[0], role, content],
        )


def get_history(phone: str, limit: int = 20) -> list[dict]:
    """Return last N messages as [{role, content}] suitable for Claude context."""
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            """
            SELECT m.role, m.content
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.tenant_phone = %s
            ORDER BY m.created_at DESC LIMIT %s
            """,
            [phone, limit],
        )
        rows = cur.fetchall()
        return [
            {"role": "assistant" if r[0] == "staff" else r[0], "content": r[1]}
            for r in reversed(rows)
        ]


def list_for_dashboard(staff_id: str | None = None) -> list[dict]:
    """
    Return conversations for the dashboard list view.
    Agents see only their assigned chats; admins see all.
    """
    with db.conn() as c:
        cur = c.cursor()
        query = """
            SELECT
                c.id::text, c.tenant_phone, c.tenant_name, c.property_address, c.room,
                c.status, c.session_id, c.updated_at::text,
                c.assigned_staff_id::text,
                u.name AS assigned_to_name,
                (SELECT m.content FROM messages m
                 WHERE m.conversation_id = c.id
                 ORDER BY m.created_at DESC LIMIT 1) AS last_message,
                (SELECT m.role FROM messages m
                 WHERE m.conversation_id = c.id
                 ORDER BY m.created_at DESC LIMIT 1) AS last_role,
                (SELECT m.created_at::text FROM messages m
                 WHERE m.conversation_id = c.id
                 ORDER BY m.created_at DESC LIMIT 1) AS last_ts,
                (SELECT COUNT(*) FROM messages m
                 WHERE m.conversation_id = c.id
                 AND m.role = 'user'
                 AND (c.last_read_at IS NULL OR m.created_at > c.last_read_at)
                ) AS unread_count
            FROM conversations c
            LEFT JOIN staff_users u ON u.id = c.assigned_staff_id
        """
        params: list = []
        if staff_id:
            query += " WHERE (c.assigned_staff_id = %s OR c.assigned_staff_id IS NULL)"
            params.append(staff_id)
        query += " ORDER BY c.updated_at DESC LIMIT 200"
        cur.execute(query, params)
        cols = [
            "id", "phone", "name", "property", "room", "status", "session_id",
            "updated_at", "assigned_to", "assigned_to_name",
            "last_message", "last_role", "last_ts", "unread_count",
        ]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_detail(phone: str) -> dict | None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            """
            SELECT
                c.id::text, c.tenant_phone, c.tenant_name, c.property_address, c.room,
                c.status, c.session_id, c.handoff_reason,
                c.assigned_staff_id::text, u.name AS assigned_to_name
            FROM conversations c
            LEFT JOIN staff_users u ON u.id = c.assigned_staff_id
            WHERE c.tenant_phone = %s
            """,
            [phone],
        )
        row = cur.fetchone()
        if not row:
            return None
        conv = dict(zip(
            ["id", "phone", "name", "property", "room", "status",
             "session_id", "handoff_reason", "assigned_to", "assigned_to_name"],
            row,
        ))
        cur.execute(
            "SELECT role, content, created_at::text FROM messages "
            "WHERE conversation_id = %s ORDER BY created_at ASC",
            [conv["id"]],
        )
        conv["history"] = [
            {"role": r[0], "content": r[1], "ts": r[2]}
            for r in cur.fetchall()
        ]
        return conv


def new_session_id() -> str:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "UPDATE settings SET value = (value::int + 1)::text "
            "WHERE key = 'session_counter' RETURNING value"
        )
        return f"T{cur.fetchone()[0]}"


def find_by_session(session_id: str) -> str | None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "SELECT tenant_phone FROM conversations "
            "WHERE session_id = %s AND status = 'handed_off'",
            [session_id.upper()],
        )
        row = cur.fetchone()
        return row[0] if row else None


def get_setting(key: str, default: str | None = None) -> str | None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("SELECT value FROM settings WHERE key = %s", [key])
        row = cur.fetchone()
        return row[0] if row else default


def set_setting(key: str, value: str) -> None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT INTO settings (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            [key, value],
        )


def mark_read(phone: str) -> None:
    """Stamp last_read_at = NOW() so unread_count resets to 0 for this conversation."""
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "UPDATE conversations SET last_read_at = NOW() WHERE tenant_phone = %s",
            [phone],
        )
