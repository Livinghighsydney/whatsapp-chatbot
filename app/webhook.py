import os
import logging
from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse

from app.ai import get_reply, is_handoff
from app.whatsapp import send_message, mark_read_and_typing
from app import db_conversations as dbc
from app import sse
from app.handoff import trigger, is_staff, handle_staff_whatsapp_message, forward_to_staff, get_mode
from app.structured import extract_tenant_info

logger = logging.getLogger(__name__)
router = APIRouter()

_INFO_PROMPT = (
    "Hi! I'm the Living High assistant. 👋\n\n"
    "Before I help, could you quickly share your *name*, *property address*, "
    "and *room number*? 🙏"
)


async def process_message(from_: str, body: str, message_id: str) -> None:
    try:
        mark_read_and_typing(message_id)

        # Staff messaging via WhatsApp (WhatsApp mode only — DONE T1 etc.)
        if get_mode() == "whatsapp" and is_staff(from_):
            handle_staff_whatsapp_message(from_, body)
            return

        conv = dbc.get_or_create(from_)
        dbc.add_message(from_, "user", body)
        sse.push()

        # Active handoff — tenant sent another message
        if conv["status"] == "handed_off":
            if get_mode() == "whatsapp":
                forward_to_staff(from_, body)
            send_message(
                to=from_,
                body="Our team has been notified and will be with you shortly. 🙏",
            )
            return

        # Collecting tenant identity details
        if conv["status"] == "collecting_info":
            info = await extract_tenant_info(body)
            dbc.update(
                from_,
                tenant_name=info.get("name"),
                property_address=info.get("property_address"),
                room=info.get("room"),
                info_collected=True,
                status="bot_active",
            )
            name = info.get("name") or "there"
            reply = f"Thanks {name}! 😊 How can I help you today?"
            dbc.add_message(from_, "assistant", reply)
            send_message(to=from_, body=reply)
            return

        # First ever message from this tenant — start proactive info collection
        if not conv["info_collected"]:
            dbc.update(from_, status="collecting_info")
            dbc.add_message(from_, "assistant", _INFO_PROMPT)
            send_message(to=from_, body=_INFO_PROMPT)
            return

        # Normal bot flow
        history = dbc.get_history(from_)
        # Re-fetch conv to get latest tenant info for Claude context
        conv = dbc.get_or_create(from_)
        reply = await get_reply(body, history=history, conv=conv)
        handoff, reason = is_handoff(reply)

        if handoff:
            trigger(from_, reason)
        else:
            dbc.add_message(from_, "assistant", reply)
            send_message(to=from_, body=reply)
            sse.push()
            logger.info("Replied | to=%s", from_)

    except Exception:
        logger.exception("Failed to process message from %s", from_)


@router.get("/webhook/whatsapp")
async def verify_webhook(request: Request):
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == os.environ["META_VERIFY_TOKEN"]
    ):
        logger.info("Webhook verified by Meta")
        return PlainTextResponse(params.get("hub.challenge"))
    return PlainTextResponse("Forbidden", status_code=403)


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]["value"]
        messages = changes.get("messages")
        if not messages:
            return {"status": "ok"}
        message = messages[0]
        if message.get("type") != "text":
            return {"status": "ok"}
        from_ = message["from"]
        body = message["text"]["body"]
        message_id = message["id"]
        logger.info("Incoming | from=%s | body=%s", from_, body)
        background_tasks.add_task(process_message, from_, body, message_id)
    except (KeyError, IndexError):
        pass
    return {"status": "ok"}
