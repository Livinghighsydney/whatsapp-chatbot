from __future__ import annotations
from app.core import db

_COLS = (
    "id", "tenant_phone", "tenant_name", "property_address", "room",
    "status", "assigned_staff_id", "session_id", "handoff_reason", "info_collected",
)


def _row(row) -> dict:
    d = dict(zip(_COLS, row))
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


def mark_read(phone: str) -> None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "UPDATE conversations SET last_read_at = NOW() WHERE tenant_phone = %s", [phone]
        )


def find_by_session(session_id: str) -> str | None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "SELECT tenant_phone FROM conversations WHERE session_id = %s AND status = 'handed_off'",
            [session_id.upper()],
        )
        row = cur.fetchone()
        return row[0] if row else None


def delete(phone: str) -> None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("DELETE FROM conversations WHERE tenant_phone = %s", [phone])
