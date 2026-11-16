from __future__ import annotations
import logging
from app.core import db
from app.models import conversation, message
from app.services.whatsapp import send_text
from app.services.handoff import resolve

logger = logging.getLogger(__name__)


def handle_message(staff_phone: str, body: str) -> None:
    stripped = body.strip()
    if stripped.upper().startswith("DONE"):
        _handle_done(staff_phone, stripped)
    else:
        _send_briefs(staff_phone)


def _handle_done(staff_phone: str, body: str) -> None:
    parts = body.split(maxsplit=1)
    session_ref = parts[1].strip().upper() if len(parts) > 1 else None

    if session_ref:
        tenant_phone = conversation.find_by_session(session_ref)
        if not tenant_phone:
            send_text(to=staff_phone, body=f"Session '{session_ref}' not found.")
            return
    else:
        active = _active_for_staff(staff_phone)
        if not active:
            send_text(to=staff_phone, body="No active handoffs to close.")
            return
        if len(active) > 1:
            ids = "  ".join(r[1] for r in active if r[1])
            send_text(to=staff_phone, body=f"Multiple active handoffs: {ids}\nSpecify which, e.g. *DONE T1*")
            return
        tenant_phone = active[0][0]

    resolve(tenant_phone)
    conv = conversation.get_or_create(tenant_phone)
    send_text(to=staff_phone, body=f"Handoff {conv.get('session_id') or ''} closed.")
    send_text(to=tenant_phone, body="Our team has sorted that out for you. I'm back and happy to help!")


def forward_to_staff(phone: str, body: str) -> None:
    conv = conversation.get_or_create(phone)
    if not conv.get("assigned_staff_id"):
        return
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("SELECT whatsapp_number FROM staff_users WHERE id = %s", [conv["assigned_staff_id"]])
        row = cur.fetchone()
    if not row or not row[0]:
        return
    label = conv.get("tenant_name") or f"+{phone}"
    send_text(to=row[0], body=f"[{conv.get('session_id')} | {label}]\n{body}")


def _active_for_staff(staff_phone: str) -> list[tuple[str, str]]:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            """
            SELECT c.tenant_phone, c.session_id
            FROM conversations c
            JOIN staff_users u ON u.id = c.assigned_staff_id
            WHERE u.whatsapp_number = %s AND c.status = 'handed_off'
            """,
            [staff_phone],
        )
        return [(r[0], r[1]) for r in cur.fetchall()]


def _send_briefs(staff_phone: str) -> None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            """
            SELECT c.tenant_phone, c.tenant_name, c.property_address,
                   c.room, c.session_id, c.handoff_reason
            FROM conversations c
            JOIN staff_users u ON u.id = c.assigned_staff_id
            WHERE u.whatsapp_number = %s AND c.status = 'handed_off'
            """,
            [staff_phone],
        )
        rows = cur.fetchall()
    if not rows:
        send_text(to=staff_phone, body="No active handoffs at the moment.")
        return
    for phone, name, prop, room, sid, reason in rows:
        hist = message.history(phone, limit=20)
        lines = [f"*{sid}*"]
        if name: lines.append(f"Name: {name}")
        if prop: lines.append(f"Property: {prop}")
        if room: lines.append(f"Room: {room}")
        lines.append(f"Direct: +{phone}")
        if reason: lines.append(f"Reason: {reason}")
        lines += ["", "*Conversation:*"]
        for m in hist:
            lines.append(f"*{'Tenant' if m['role'] == 'user' else 'Bot'}:* {m['content']}")
        lines += ["", f"Type *DONE {sid}* when resolved."]
        send_text(to=staff_phone, body="\n".join(lines))
