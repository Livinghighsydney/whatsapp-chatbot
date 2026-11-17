from __future__ import annotations
import logging
import os
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import PlainTextResponse
from app.services import ai, structured, whatsapp as wa, handoff, handoff_wa
from app.rag.retrieve import retrieve
from app.models import conversation, message
from app.core import sse

logger = logging.getLogger(__name__)
router = APIRouter()

_INFO_PROMPT = (
    "Hi! I'm the Living High assistant.\n\n"
    "Before I help, could you quickly share your *name*, *property address*, and *room number*?"
)


async def _process(from_: str, body: str, message_id: str) -> None:
    try:
        wa.mark_read_typing(message_id)

        if handoff.get_mode() == "whatsapp" and handoff.is_staff(from_):
            handoff_wa.handle_message(from_, body)
            return

        conv = conversation.get_or_create(from_)
        message.add(from_, "user", body)
        sse.push("message")

        if conv["status"] == "handed_off":
            if handoff.get_mode() == "whatsapp":
                handoff_wa.forward_to_staff(from_, body)
            return

        if conv["status"] == "collecting_info":
            info = await structured.extract_tenant_info(body)
            conversation.update(from_, tenant_name=info.get("name"),
                                property_address=info.get("property_address"),
                                room=info.get("room"), info_collected=True, status="bot_active")
            name = info.get("name") or "there"
            reply = f"Thanks {name}! How can I help you today?"
            message.add(from_, "assistant", reply)
            wa.send_text(to=from_, body=reply)
            return

        if not conv["info_collected"]:
            conversation.update(from_, status="collecting_info")
            message.add(from_, "assistant", _INFO_PROMPT)
            wa.send_text(to=from_, body=_INFO_PROMPT)
            return

        hist = message.history(from_)
        conv = conversation.get_or_create(from_)
        reply = await ai.get_reply(body, history=hist, conv=conv)
        is_hoff, reason = ai.is_handoff(reply)

        if is_hoff:
            handoff.trigger(from_, reason)
        else:
            message.add(from_, "assistant", reply)
            wa.send_text(to=from_, body=reply)
            _send_images(from_, body, conv)
            sse.push("refresh")
            logger.info("Replied | to=%s", from_)

    except Exception:
        logger.exception("Failed to process message from %s", from_)


def _send_images(to: str, query: str, conv: dict) -> None:
    chunks = retrieve(query, property_address=conv.get("property_address"),
                      room_number=conv.get("room"))
    sent_urls: set[str] = set()
    for chunk in chunks:
        if chunk["similarity"] < 0.45 or not chunk.get("images"):
            continue
        for img in chunk["images"]:
            url = img.get("src", "")
            if not url or url in sent_urls or len(sent_urls) >= 2:
                continue
            try:
                wa.send_image_url(to=to, url=url, caption=img.get("caption", ""))
                sent_urls.add(url)
            except Exception:
                logger.warning("Failed to send image | url=%s", url)
        if sent_urls:
            return


@router.get("/webhook/whatsapp")
async def verify(request: Request):
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == os.environ["META_VERIFY_TOKEN"]:
        return PlainTextResponse(p.get("hub.challenge"))
    return PlainTextResponse("Forbidden", status_code=403)


@router.post("/webhook/whatsapp")
async def receive(request: Request, bg: BackgroundTasks):
    data = await request.json()
    try:
        changes = data["entry"][0]["changes"][0]["value"]
        messages = changes.get("messages")
        if not messages:
            return {"status": "ok"}
        msg = messages[0]
        if msg.get("type") != "text":
            return {"status": "ok"}
        logger.info("Incoming | from=%s | body=%s", msg["from"], msg["text"]["body"])
        bg.add_task(_process, msg["from"], msg["text"]["body"], msg["id"])
    except (KeyError, IndexError):
        pass
    return {"status": "ok"}
