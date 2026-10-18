import logging
from fastapi import APIRouter, Form
from app.ai import get_reply
from app.whatsapp import send_message

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    Body: str = Form(...),
    From: str = Form(...),
):
    logger.info("Incoming | from=%s | body=%s", From, Body)
    reply = await get_reply(Body)
    send_message(to=From, body=reply)
    logger.info("Replied  | to=%s | body=%s", From, reply)
    return {"status": "ok"}
