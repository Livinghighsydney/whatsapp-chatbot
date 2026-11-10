"""Human handoff orchestration.

Flow:
  1. Bot detects it cannot answer → begin_collection() transitions tenant to
     collecting_info and asks for name / property / room.
  2. Tenant replies → complete_collection() stores identity, assigns a session
     ID (T1, T2…), and fires the handoff.
  3. Staff receives a template alert via the Living High chat, then on first
     reply gets a full brief: conversation history + tenant's direct number.
  4. Staff opens a direct WhatsApp to the tenant's number — that becomes a
     dedicated, isolated chat tile per tenant on the staff member's phone.
  5. Any further tenant messages are forwarded to staff as notifications so
     they're not missed while the direct chat is being set up.
  6. Staff types "DONE T1" (or bare "DONE" if only one active handoff) in the
     Living High chat to hand control back to the bot.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone

from app import state
from app.whatsapp import send_message, send_template

logger = logging.getLogger(__name__)

HANDOFF_TEMPLATE = "staff_handoff_alert"

_INFO_PROMPT = (
    "Before I connect you with a team member, could you share your "
    "*name*, *property address*, and *room number*? 🙏"
)
_NO_STAFF_MSG = (
    "Sorry, I couldn't reach a team member right now. "
    "Please email us at support@livinghigh.com.au or try again later."
)


# ── Staff roster ───────────────────────────────────────────────────────────────

def get_staff_numbers() -> list[str]:
    raw = os.environ.get("STAFF_NUMBERS", "")
    return [n.strip().lstrip("+") for n in raw.split(",") if n.strip()]


def is_staff(phone: str) -> bool:
    return phone in get_staff_numbers()


# ── Info collection (pre-handoff) ──────────────────────────────────────────────

def begin_collection(tenant_number: str, reason: str) -> None:
    """Ask the tenant for identity details before escalating."""
    conv = state.get(tenant_number)

    # If we already have their info from a previous session, skip collection
    if conv.tenant_info.name:
        complete_collection(tenant_number, reason=reason, raw_reply=None)
        return

    conv.status = "collecting_info"
    conv.handoff_reason = reason
    send_message(to=tenant_number, body=_INFO_PROMPT)
    state.add_message(tenant_number, "assistant", _INFO_PROMPT)
    logger.info("Info collection started | tenant=%s", tenant_number)


def complete_collection(tenant_number: str, raw_reply: str | None, reason: str | None = None) -> None:
    """Store tenant identity from their reply, then fire the handoff."""
    conv = state.get(tenant_number)

    if raw_reply is not None:
        _parse_tenant_info(conv, raw_reply)

    if reason:
        conv.handoff_reason = reason

    logger.info(
        "Tenant info collected | tenant=%s | name=%s | property=%s | room=%s",
        tenant_number, conv.tenant_info.name,
        conv.tenant_info.property_address, conv.tenant_info.room,
    )
    _trigger(tenant_number)


def _parse_tenant_info(conv: state.Conversation, raw: str) -> None:
    """
    Best-effort parse of "Name, Property, Room".
    Structured extraction via Google Sheets lookup lands in Phase 3 —
    for now we split on commas and fall back to storing the raw string.
    """
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) >= 3:
        conv.tenant_info.name = parts[0]
        conv.tenant_info.property_address = parts[1]
        conv.tenant_info.room = ", ".join(parts[2:])  # handles "Room 3, Level 2" etc.
    elif len(parts) == 2:
        conv.tenant_info.name = parts[0]
        conv.tenant_info.property_address = parts[1]
    else:
        conv.tenant_info.name = raw  # single-word reply; use as name


# ── Handoff trigger ────────────────────────────────────────────────────────────

def _trigger(tenant_number: str) -> None:
    """Flip conversation to handed_off, notify staff, confirm to tenant."""
    staff_numbers = get_staff_numbers()
    if not staff_numbers:
        logger.warning("Handoff triggered but STAFF_NUMBERS not configured")
        send_message(to=tenant_number, body=_NO_STAFF_MSG)
        return

    conv = state.get(tenant_number)
    conv.status = "handed_off"
    conv.assigned_staff = list(staff_numbers)
    conv.handed_off_at = datetime.now(timezone.utc)
    conv.session_id = state.new_session(tenant_number)

    send_message(
        to=tenant_number,
        body="Our team has been notified and will reach out to you directly on WhatsApp shortly. 🙏",
    )

    # Template variable 1 = tenant display name, variable 2 = reason
    display = conv.tenant_info.name or f"+{tenant_number}"
    for staff_number in staff_numbers:
        send_template(
            to=staff_number,
            template_name=HANDOFF_TEMPLATE,
            variables=[display, conv.handoff_reason],
        )

    logger.info(
        "Handoff triggered | tenant=%s | session=%s | staff=%s | reason=%s",
        tenant_number, conv.session_id, staff_numbers, conv.handoff_reason,
    )


# ── Staff message handling ─────────────────────────────────────────────────────

def handle_staff_message(staff_number: str, body: str) -> None:
    """Route an incoming message from a staff member in the Living High chat."""
    stripped = body.strip()

    if stripped.upper().startswith("DONE"):
        _handle_done(staff_number, stripped)
        return

    # Any other reply: open the brief for each unseen active handoff
    _handle_first_reply(staff_number)


def _handle_done(staff_number: str, body: str) -> None:
    """
    Resolve a handoff.
      "DONE T1"  → closes session T1 specifically
      "DONE"     → closes the only active handoff (errors if there are several)
    """
    parts = body.split(maxsplit=1)
    session_ref = parts[1].strip().upper() if len(parts) > 1 else None

    if session_ref:
        tenant_number = state.find_tenant_by_session(session_ref)
        if not tenant_number:
            send_message(to=staff_number, body=f"Session '{session_ref}' not found.")
            return
    else:
        active = state.find_active_handoffs_for_staff(staff_number)
        if not active:
            send_message(to=staff_number, body="No active handoffs to close.")
            return
        if len(active) > 1:
            ids = "  ".join(conv.session_id for _, conv in active)
            send_message(
                to=staff_number,
                body=f"Multiple active handoffs: {ids}\nSpecify which to close, e.g. *DONE T1*",
            )
            return
        tenant_number = active[0][0]

    _resolve(staff_number, tenant_number)


def _handle_first_reply(staff_number: str) -> None:
    """
    When a staff member replies to the template, the 24-hour free-form window
    opens. Use it immediately to send the full handoff brief for every active
    handoff they haven't seen yet.
    """
    active = state.find_active_handoffs_for_staff(staff_number)

    if not active:
        send_message(to=staff_number, body="No active handoffs at the moment.")
        return

    for tenant_number, conv in active:
        if staff_number not in conv.staff_history_sent:
            conv.staff_history_sent.add(staff_number)
            _send_handoff_brief(staff_number, tenant_number, conv)


def _send_handoff_brief(
    staff_number: str,
    tenant_number: str,
    conv: state.Conversation,
) -> None:
    """Send the full context package to a staff member for one handoff."""
    info = conv.tenant_info
    history_text = _format_history(conv.history)

    lines = [f"📋 *{conv.session_id}*"]
    if info.name:
        lines.append(f"👤 {info.name}")
    if info.property_address:
        lines.append(f"📍 {info.property_address}")
    if info.room:
        lines.append(f"🚪 {info.room}")
    lines.append(f"📞 Direct number: +{tenant_number}")
    lines.append("")
    lines.append("*Conversation history:*")
    lines.append(history_text)
    lines.append("")
    lines.append(f"Message the tenant directly at +{tenant_number}")
    lines.append(f"Type *DONE {conv.session_id}* when you're finished.")

    send_message(to=staff_number, body="\n".join(lines))


def _resolve(staff_number: str, tenant_number: str) -> None:
    conv = state.get(tenant_number)
    session_id = conv.session_id  # capture before resolve() clears it

    send_message(to=staff_number, body=f"✅ Handoff {session_id} closed.")
    send_message(
        to=tenant_number,
        body="Our team has sorted that out for you. I'm back and happy to help with anything else! 😊",
    )

    state.resolve(tenant_number)
    logger.info("Handoff resolved | session=%s | tenant=%s | staff=%s", session_id, tenant_number, staff_number)


# ── Tenant messages during active handoff ──────────────────────────────────────

def forward_to_staff(tenant_number: str, body: str) -> None:
    """
    Notify staff of a new tenant message during handoff.
    Staff replies directly to the tenant's number — this is informational only.
    """
    conv = state.get(tenant_number)
    if not conv.assigned_staff:
        logger.warning("Handoff active for %s but no assigned_staff", tenant_number)
        return

    label = conv.tenant_info.name or f"+{tenant_number}"
    notification = f"[{conv.session_id} | {label}]\n{body}"

    for staff_number in conv.assigned_staff:
        send_message(to=staff_number, body=notification)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _format_history(history: list[dict]) -> str:
    labels = {"user": "Tenant", "assistant": "Bot", "staff": "Staff"}
    lines = [f"*{labels.get(m['role'], m['role'])}:* {m['content']}" for m in history]
    return "\n".join(lines) if lines else "(no previous messages)"
