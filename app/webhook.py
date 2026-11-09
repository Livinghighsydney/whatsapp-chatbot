import os
import logging
from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse

from app.ai import get_reply, is_handoff
from app.whatsapp import send_message
from app import state
from app.handoff import is_staff, trigger, handle_staff_message, forward_to_staff

logger = logging.getLogger(__name__)
router = APIRouter()


async def process_message(from_: str, body: str) -> None:
    try:
        # ── Staff reply ────────────────────────────────────────────────────────
        if is_staff(from_):
            handle_staff_message(from_, body)
            return

        conv = state.get(from_)

        # ── Tenant message during active handoff ───────────────────────────────
        if conv.status == "handed_off":
            state.add_message(from_, "user", body)
            forward_to_staff(from_, body)
            return

        # ── Normal bot flow ────────────────────────────────────────────────────
        reply = await get_reply(body, history=conv.history)
        handoff, reason = is_handoff(reply)

        if handoff:
            state.add_message(from_, "user", body)
            trigger(from_, reason)
        else:
            state.add_message(from_, "user", body)
            state.add_message(from_, "assistant", reply)
            send_message(to=from_, body=reply)
            logger.info("Replied | to=%s | body=%s", from_, reply)

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

        logger.info("Incoming | from=%s | body=%s", from_, body)
        background_tasks.add_task(process_message, from_, body)

    except (KeyError, IndexError):
        pass

    return {"status": "ok"}
