from __future__ import annotations
import logging
import os
from app.core import db
from app.models import conversation, settings
from app.models.shift import routing_target
from app.services.whatsapp import send_text, send_template

logger = logging.getLogger(__name__)

HANDOFF_TEMPLATE = "staff_handoff_alert"
_NO_STAFF_MSG = "Sorry, I couldn't reach a team member right now. Please email us at support@livinghigh.com.au or try again later."


def get_mode() -> str:
    return settings.get("handoff_mode", "dashboard") or "dashboard"


def is_staff(phone: str) -> bool:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("SELECT 1 FROM staff_users WHERE whatsapp_number = %s LIMIT 1", [phone])
        if cur.fetchone():
            return True
    raw = os.environ.get("STAFF_NUMBERS", "")
    return phone in [n.strip().lstrip("+") for n in raw.split(",") if n.strip()]


def trigger(phone: str, reason: str) -> None:
    target = routing_target()
    if not target:
        logger.warning("Handoff triggered but no shifts configured | phone=%s", phone)
        send_text(to=phone, body=_NO_STAFF_MSG)
        return

    session_id = settings.next_session_id()
    conversation.update(phone, status="handed_off", session_id=session_id,
                        handoff_reason=reason, assigned_staff_id=target["staff_user_id"])

    conv = conversation.get_or_create(phone)
    display = conv.get("tenant_name") or f"+{phone}"
    mode = get_mode()

    if mode == "whatsapp":
        wa = target.get("whatsapp_number")
        if not wa:
            logger.warning("WhatsApp mode: %s has no whatsapp_number", target["email"])
            send_text(to=phone, body=_NO_STAFF_MSG)
            return
        try:
            send_template(to=wa, template_name=HANDOFF_TEMPLATE, variables=[display, reason])
        except Exception:
            logger.exception("Failed to send handoff template to %s", wa)
        send_text(to=phone, body="Our team has been notified and will reach out to you directly on WhatsApp shortly.")
    else:
        send_text(to=phone, body="I've connected you with a team member who will be with you shortly.")

    logger.info("Handoff | phone=%s | session=%s | mode=%s | assigned=%s",
                phone, session_id, mode, target["email"])


def resolve(phone: str) -> None:
    conversation.update(phone, status="bot_active", session_id=None,
                        assigned_staff_id=None, handoff_reason=None)
    logger.info("Handoff resolved | phone=%s", phone)
