"""Shift management and AEST-based handoff routing.

Weekday convention: Monday=0 … Sunday=6 (ISO).
Timezone: Australia/Sydney (handles both AEST UTC+10 and AEDT UTC+11).
Overlap rule: when two shifts overlap, the one that started most recently wins.
No-one on shift: returns the agent whose next shift starts soonest (up to 7 days ahead).
"""
from __future__ import annotations

import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app import db

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
                   u.name AS staff_name, u.email AS staff_email
            FROM shifts s
            JOIN staff_users u ON u.id = s.staff_user_id
            ORDER BY s.weekday, s.start_time
            """
        )
        cols = ["id", "staff_user_id", "weekday", "start_time", "end_time",
                "staff_name", "staff_email"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _is_active(start: time, end: time, now: time) -> bool:
    if start <= end:
        return start <= now < end
    # Overnight shift (e.g. 22:00–06:00)
    return now >= start or now < end


def routing_target() -> dict | None:
    """
    Returns the staff member who should receive the next handoff.
    Returns None if no shifts are configured at all.
    """
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            """
            SELECT s.staff_user_id::text, s.weekday, s.start_time, s.end_time,
                   u.name, u.email, u.whatsapp_number
            FROM shifts s
            JOIN staff_users u ON u.id = s.staff_user_id
            """
        )
        all_shifts = cur.fetchall()

    if not all_shifts:
        return None

    now_aest = datetime.now(AEST)
    today_wd = now_aest.weekday()  # Monday=0
    cur_time = now_aest.time().replace(second=0, microsecond=0)

    # Currently active shifts
    active = [
        (s[3], s[0], s[4], s[5], s[6])  # (end_time, uid, name, email, wa)
        for s in all_shifts
        if s[1] == today_wd and _is_active(s[2], s[3], cur_time)
    ]
    # Sort by start_time DESC so the most recently started is first.
    # Re-derive start_time from the original data.
    if active:
        active_with_start = [
            (s[2], s[0], s[4], s[5], s[6])  # (start_time, uid, name, email, wa)
            for s in all_shifts
            if s[1] == today_wd and _is_active(s[2], s[3], cur_time)
        ]
        active_with_start.sort(key=lambda x: x[0], reverse=True)
        _, uid, name, email, wa = active_with_start[0]
        return {"staff_user_id": uid, "name": name, "email": email, "whatsapp_number": wa}

    # No one on shift — find soonest upcoming (up to 7 days ahead)
    for days_ahead in range(7):
        check_wd = (today_wd + days_ahead) % 7
        candidates = [
            (s[2], s[0], s[4], s[5], s[6])  # (start_time, uid, name, email, wa)
            for s in all_shifts if s[1] == check_wd
        ]
        for start_t, uid, name, email, wa in sorted(candidates):
            if days_ahead == 0 and start_t <= cur_time:
                continue  # shift already ended today
            return {"staff_user_id": uid, "name": name, "email": email, "whatsapp_number": wa}

    return None
