from __future__ import annotations
import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo
from app.core import db

logger = logging.getLogger(__name__)
AEST = ZoneInfo("Australia/Sydney")


def add(staff_user_id: str, weekday: int, start_time: str, end_time: str) -> str:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT INTO shifts (staff_user_id, weekday, start_time, end_time) "
            "VALUES (%s, %s, %s, %s) RETURNING id::text",
            [staff_user_id, weekday, start_time, end_time],
        )
        return cur.fetchone()[0]


def delete(shift_id: str) -> bool:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("DELETE FROM shifts WHERE id = %s", [shift_id])
        return cur.rowcount > 0


def list_all() -> list[dict]:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            """
            SELECT s.id::text, s.staff_user_id::text, s.weekday,
                   s.start_time::text, s.end_time::text,
                   u.name, u.email
            FROM shifts s
            JOIN staff_users u ON u.id = s.staff_user_id
            ORDER BY s.weekday, s.start_time
            """
        )
        cols = ["id", "staff_user_id", "weekday", "start_time", "end_time", "staff_name", "staff_email"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _is_active(start: time, end: time, now: time) -> bool:
    if start <= end:
        return start <= now < end
    return now >= start or now < end  # overnight shift


def routing_target() -> dict | None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            """
            SELECT s.staff_user_id::text, s.weekday, s.start_time, s.end_time,
                   u.name, u.email, u.whatsapp_number
            FROM shifts s JOIN staff_users u ON u.id = s.staff_user_id
            """
        )
        all_shifts = cur.fetchall()

    if not all_shifts:
        return None

    now_aest = datetime.now(AEST)
    today_wd = now_aest.weekday()
    cur_time = now_aest.time().replace(second=0, microsecond=0)

    active = [
        (s[2], s[0], s[4], s[5], s[6])
        for s in all_shifts
        if s[1] == today_wd and _is_active(s[2], s[3], cur_time)
    ]
    if active:
        active.sort(key=lambda x: x[0], reverse=True)
        _, uid, name, email, wa = active[0]
        return {"staff_user_id": uid, "name": name, "email": email, "whatsapp_number": wa}

    for days_ahead in range(7):
        check_wd = (today_wd + days_ahead) % 7
        candidates = [
            (s[2], s[0], s[4], s[5], s[6])
            for s in all_shifts if s[1] == check_wd
        ]
        for start_t, uid, name, email, wa in sorted(candidates):
            if days_ahead == 0 and start_t <= cur_time:
                continue
            return {"staff_user_id": uid, "name": name, "email": email, "whatsapp_number": wa}

    return None
