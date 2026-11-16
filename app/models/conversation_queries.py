from __future__ import annotations
from app.core import db


def list_for_dashboard(staff_id: str | None = None) -> list[dict]:
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
            SELECT c.id::text, c.tenant_phone, c.tenant_name, c.property_address, c.room,
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
        conv["history"] = [{"role": r[0], "content": r[1], "ts": r[2]} for r in cur.fetchall()]
        return conv
