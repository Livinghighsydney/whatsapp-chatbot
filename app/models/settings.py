from __future__ import annotations
from app.core import db


def get(key: str, default: str | None = None) -> str | None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("SELECT value FROM settings WHERE key = %s", [key])
        row = cur.fetchone()
        return row[0] if row else default


def set(key: str, value: str) -> None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT INTO settings (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            [key, value],
        )


def next_session_id() -> str:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "UPDATE settings SET value = (value::int + 1)::text "
            "WHERE key = 'session_counter' RETURNING value"
        )
        return f"T{cur.fetchone()[0]}"
