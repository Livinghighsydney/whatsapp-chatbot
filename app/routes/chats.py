from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from app.models import conversation, conversation_queries, message, user as user_model
from app.services import whatsapp as wa, handoff as handoff_svc
from app.core import sse
from app.routes.deps import require_auth
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chats")


@router.get("")
def list_chats(payload: dict = Depends(require_auth)):
    if payload.get("role") == "admin":
        return conversation_queries.list_for_dashboard()
    staff_id = user_model.get_id(payload["sub"])
    return conversation_queries.list_for_dashboard(staff_id=staff_id)


@router.get("/{phone}")
def get_chat(phone: str, _: dict = Depends(require_auth)):
    conversation.mark_read(phone)
    conv = conversation_queries.get_detail(phone)
    if not conv:
        return {"phone": phone, "name": None, "property": None, "room": None,
                "status": "bot_active", "session_id": None, "history": []}
    return conv


class _TextBody(BaseModel):
    message: str


@router.post("/{phone}/send")
def send_text(phone: str, body: _TextBody, payload: dict = Depends(require_auth)):
    if not body.message.strip():
        raise HTTPException(400, "Message cannot be empty")
    conv = conversation.get_or_create(phone)
    if conv["status"] != "handed_off":
        staff_id = user_model.get_id(payload["sub"])
        conversation.update(phone, status="handed_off", assigned_staff_id=staff_id,
                            handoff_reason="Staff intervened directly from dashboard")
    wa.send_text(to=phone, body=body.message)
    message.add(phone, "staff", body.message)
    conversation.mark_read(phone)
    sse.push("refresh")
    return {"ok": True}


@router.post("/{phone}/media")
async def send_media(phone: str, file: UploadFile = File(...), _: dict = Depends(require_auth)):
    content = await file.read()
    media_type = wa.classify_media(file.content_type or "application/octet-stream")
    media_id = await wa.upload_media(content, file.content_type or "application/octet-stream", file.filename or "file")
    wa.send_media(to=phone, media_id=media_id, media_type=media_type)
    message.add(phone, "staff", f"[{media_type}: {file.filename}]")
    return {"ok": True, "media_type": media_type}


@router.post("/{phone}/resolve")
def resolve(phone: str, _: dict = Depends(require_auth)):
    conv = conversation.get_or_create(phone)
    if conv["status"] != "handed_off":
        raise HTTPException(400, "Conversation is not currently in handoff")
    handoff_svc.resolve(phone)
    wa.send_text(to=phone, body="Our team has sorted that out for you. I'm back and happy to help!")
    return {"ok": True}


@router.post("/{phone}/assign")
def assign(phone: str, body: dict, _: dict = Depends(require_auth)):
    conversation.update(phone, assigned_staff_id=body.get("staff_id"))
    return {"ok": True}


@router.delete("/{phone}")
def delete_chat(phone: str, _: dict = Depends(require_auth)):
    conversation.delete(phone)
    sse.push("refresh")
    return {"ok": True}
