"""Human handoff logic.

When the bot cannot answer, it triggers a handoff:
  1. Tenant gets a "connecting you with a team member" message.
  2. The assigned staff member receives the full conversation history on their
     personal WhatsApp, via the same bot number.
  3. Everything the staff member types is relayed to the tenant (and vice versa).
  4. Staff types DONE to return the conversation to the bot.

From the tenant's perspective the thread never changes — all messages come from
the same +61 450 879 134 number regardless of who is replying.
"""
import os
import logging
from datetime import datetime, timezone

from app import state
from app.whatsapp import send_message, send_template

HANDOFF_TEMPLATE = "staff_handoff_alert"

logger = logging.getLogger(__name__)


def get_staff_numbers() -> list[str]:
    """Return configured staff WhatsApp numbers (without +)."""
    raw = os.environ.get("STAFF_NUMBERS", "")
    return [n.strip().lstrip("+") for n in raw.split(",") if n.strip()]


def is_staff(phone: str) -> bool:
    return phone in get_staff_numbers()


def _format_history(history: list[dict]) -> str:
    labels = {"user": "Tenant", "assistant": "Bot", "staff": "Staff"}
    lines = [f"*{labels.get(m['role'], m['role'])}:* {m['content']}" for m in history]
    return "\n".join(lines) if lines else "(no previous messages)"


def trigger(tenant_number: str, reason: str) -> None:
    """Flip conversation to handed_off and alert the first available staff member."""
    staff_numbers = get_staff_numbers()
    if not staff_numbers:
        logger.warning("Handoff triggered but STAFF_NUMBERS not configured")
        send_message(
            to=tenant_number,
            body="Sorry, I couldn't connect you with a team member right now. "
                 "Please email us at support@livinghigh.com.au or try again later.",
        )
        return

    conv = state.get(tenant_number)
    conv.status = "handed_off"
    conv.assigned_staff = staff_numbers  # all staff can respond
    conv.handed_off_at = datetime.now(timezone.utc)

    send_message(
        to=tenant_number,
        body="I've connected you with one of our team members — they'll reply shortly! 🙏",
    )

    for staff_number in staff_numbers:
        send_template(
            to=staff_number,
            template_name=HANDOFF_TEMPLATE,
            variables=[tenant_number, reason],
        )

    logger.info("Handoff triggered | tenant=%s → staff=%s | reason=%s", tenant_number, staff_numbers, reason)


def handle_staff_message(staff_number: str, body: str) -> None:
    """Route a message from a staff member: relay to tenant or resolve handoff."""
    tenant_number = state.find_tenant_for_staff(staff_number)

    if not tenant_number:
        send_message(to=staff_number, body="No active handoff conversation at the moment.")
        return

    # First reply from this staff member — send conversation history now that
    # the window is open (template opened the conversation, reply unlocks free-form)
    conv = state.get(tenant_number)
    if staff_number not in conv.staff_history_sent:
        conv.staff_history_sent.add(staff_number)
        history_text = _format_history(conv.history)
        send_message(
            to=staff_number,
            body=f"📋 *Conversation history:*\n\n{history_text}\n\n"
                 "You can now reply directly to the tenant above. Type *DONE* when finished.",
        )
        return

    if body.strip().upper() == "DONE":
        conv = state.get(tenant_number)
        conv.status = "bot_active"
        conv.assigned_staff = []
        conv.handed_off_at = None
        conv.staff_history_sent = set()

        for s in (conv.assigned_staff or [staff_number]):
            send_message(to=s, body="✅ Conversation returned to bot.")
        send_message(
            to=tenant_number,
            body="Our team member has sorted that out for you. I'm back and happy to help with anything else! 😊",
        )
        logger.info("Handoff resolved | tenant=%s | staff=%s", tenant_number, staff_number)
    else:
        state.add_message(tenant_number, "staff", body)
        send_message(to=tenant_number, body=body)
        send_message(to=staff_number, body="✅ Sent.")
        logger.info("Staff relay | staff=%s → tenant=%s | body=%s", staff_number, tenant_number, body)


def forward_to_staff(tenant_number: str, body: str) -> None:
    """Forward a tenant message to the assigned staff member during an active handoff."""
    conv = state.get(tenant_number)
    if conv.assigned_staff:
        for staff_number in conv.assigned_staff:
            send_message(to=staff_number, body=f"[Tenant] {body}")
    else:
        logger.warning("Handoff active for %s but no assigned_staff", tenant_number)
