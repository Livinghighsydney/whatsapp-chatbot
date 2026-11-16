from __future__ import annotations
from app.core import db


def add(phone: str, role: str, content: str) -> None:
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


def history(phone: str, limit: int = 20) -> list[dict]:
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
