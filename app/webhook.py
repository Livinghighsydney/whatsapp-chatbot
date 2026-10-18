import logging
from fastapi import APIRouter, Form, BackgroundTasks
from app.ai import get_reply
from app.whatsapp import send_message

logger = logging.getLogger(__name__)
router = APIRouter()


async def process_message(from_: str, body: str) -> None:
    try:
        reply = await get_reply(body)
        send_message(to=from_, body=reply)
        logger.info("Replied  | to=%s | body=%s", from_, reply)
    except Exception:
        logger.exception("Failed to process message from %s", from_)


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    Body: str = Form(...),
    From: str = Form(...),
):
    logger.info("Incoming | from=%s | body=%s", From, Body)
    background_tasks.add_task(process_message, From, Body)
    return {"status": "ok"}
