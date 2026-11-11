"""Human handoff orchestration — Dashboard and WhatsApp modes.

Dashboard mode: assigns conversation to on-shift agent in DB; staff reply via dashboard UI.
WhatsApp mode:  texts the on-shift agent's personal WhatsApp number; staff reply directly.
"""
from __future__ import annotations

import logging
import os

from app import db
from app import db_conversations as dbc
from app import shifts
from app.whatsapp import send_message, send_template

logger = logging.getLogger(__name__)

HANDOFF_TEMPLATE = "staff_handoff_alert"
_NO_STAFF_MSG = (
    "Sorry, I couldn't reach a team member right now. "
    "Please email us at support@livinghigh.com.au or try again later."
)


# ── Mode ───────────────────────────────────────────────────────────────────────

def get_mode() -> str:
    return dbc.get_setting("handoff_mode", "dashboard") or "dashboard"


# ── Staff detection (WhatsApp mode) ───────────────────────────────────────────

def is_staff(phone: str) -> bool:
    """True if the sender's number belongs to a staff member."""
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "SELECT 1 FROM staff_users WHERE whatsapp_number = %s LIMIT 1", [phone]
        )
        if cur.fetchone():
            return True
    # Fallback: STAFF_NUMBERS env var (legacy)
    raw = os.environ.get("STAFF_NUMBERS", "")
    return phone in [n.strip().lstrip("+") for n in raw.split(",") if n.strip()]


# ── Trigger ────────────────────────────────────────────────────────────────────

def trigger(phone: str, reason: str) -> None:
    """
    Mark conversation as handed_off, assign to the on-shift agent,
    and notify either via dashboard (silent) or WhatsApp template.
    """
    target = shifts.routing_target()

    if not target:
        logger.warning("Handoff triggered but no shifts configured | phone=%s", phone)
        send_message(to=phone, body=_NO_STAFF_MSG)
        return

    session_id = dbc.new_session_id()
    dbc.update(
        phone,
        status="handed_off",
        session_id=session_id,
        handoff_reason=reason,
        assigned_staff_id=target["staff_user_id"],
    )
    conv = dbc.get_or_create(phone)
    display = conv.get("tenant_name") or f"+{phone}"
    mode = get_mode()

    if mode == "whatsapp":
        wa = target.get("whatsapp_number")
        if not wa:
            logger.warning("WhatsApp mode: %s has no whatsapp_number", target["email"])
            send_message(to=phone, body=_NO_STAFF_MSG)
            return
        try:
            send_template(
                to=wa,
                template_name=HANDOFF_TEMPLATE,
                variables=[display, reason],
            )
        except Exception:
            logger.exception("Failed to send handoff template to %s", wa)
        send_message(
            to=phone,
            body="Our team has been notified and will reach out to you directly on WhatsApp shortly. 🙏",
        )
    else:
        # Dashboard mode — tenant gets a holding message; agent sees it in the dashboard
        send_message(
            to=phone,
            body="I've connected you with a team member who will be with you shortly. 🙏",
        )

    logger.info(
        "Handoff triggered | phone=%s | session=%s | mode=%s | assigned=%s",
        phone, session_id, mode, target["email"],
    )


# ── Dashboard-mode: staff replies via API ─────────────────────────────────────

def resolve(phone: str) -> None:
    dbc.update(
        phone,
        status="bot_active",
        session_id=None,
        assigned_staff_id=None,
        handoff_reason=None,
    )
    logger.info("Handoff resolved | phone=%s", phone)


# ── WhatsApp-mode: staff reply via their own phone ────────────────────────────

def handle_staff_whatsapp_message(staff_phone: str, body: str) -> None:
    """Route an incoming WhatsApp message from a staff member."""
    stripped = body.strip()
    if stripped.upper().startswith("DONE"):
        _handle_done(staff_phone, stripped)
    else:
        _send_active_briefs(staff_phone)


def _handle_done(staff_phone: str, body: str) -> None:
    parts = body.split(maxsplit=1)
    session_ref = parts[1].strip().upper() if len(parts) > 1 else None

    if session_ref:
        tenant_phone = dbc.find_by_session(session_ref)
        if not tenant_phone:
            send_message(to=staff_phone, body=f"Session '{session_ref}' not found.")
            return
    else:
        active = _active_for_staff_wa(staff_phone)
        if not active:
            send_message(to=staff_phone, body="No active handoffs to close.")
            return
        if len(active) > 1:
            ids = "  ".join(r[1] for r in active if r[1])
            send_message(
                to=staff_phone,
                body=f"Multiple active handoffs: {ids}\nSpecify which, e.g. *DONE T1*",
            )
            return
        tenant_phone = active[0][0]

    resolve(tenant_phone)
    conv = dbc.get_or_create(tenant_phone)
    send_message(to=staff_phone, body=f"✅ Handoff {conv.get('session_id') or ''} closed.")
    send_message(
        to=tenant_phone,
        body="Our team has sorted that out for you. I'm back and happy to help with anything else! 😊",
    )


def _active_for_staff_wa(staff_phone: str) -> list[tuple[str, str]]:
    """Returns list of (tenant_phone, session_id) for active handoffs for this WA number."""
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


def _send_active_briefs(staff_phone: str) -> None:
    """On first staff reply to the template, send full brief for each active handoff."""
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
        send_message(to=staff_phone, body="No active handoffs at the moment.")
        return

    for phone, name, prop, room, sid, reason in rows:
        history = dbc.get_history(phone, limit=20)
        lines = [f"📋 *{sid}*"]
        if name:
            lines.append(f"👤 {name}")
        if prop:
            lines.append(f"📍 {prop}")
        if room:
            lines.append(f"🚪 {room}")
        lines.append(f"📞 Direct: +{phone}")
        if reason:
            lines.append(f"❓ Reason: {reason}")
        lines += ["", "*Conversation:*"]
        for m in history:
            label = "Tenant" if m["role"] == "user" else "Bot"
            lines.append(f"*{label}:* {m['content']}")
        lines += ["", f"Type *DONE {sid}* when resolved."]
        send_message(to=staff_phone, body="\n".join(lines))


def forward_to_staff(phone: str, body: str) -> None:
    """Notify assigned staff of a new tenant message during active handoff (WhatsApp mode)."""
    conv = dbc.get_or_create(phone)
    if not conv.get("assigned_staff_id"):
        return
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "SELECT whatsapp_number FROM staff_users WHERE id = %s",
            [conv["assigned_staff_id"]],
        )
        row = cur.fetchone()
    if not row or not row[0]:
        return
    label = conv.get("tenant_name") or f"+{phone}"
    send_message(to=row[0], body=f"[{conv.get('session_id')} | {label}]\n{body}")
