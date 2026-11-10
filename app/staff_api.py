"""Staff dashboard API.

Exposes all tenant conversations to the staff web UI.
Every route requires a valid Bearer token matching STAFF_DASHBOARD_TOKEN.

Endpoints consumed by the Lovable frontend:
  POST /staff/auth/verify          — check token on startup
  GET  /staff/chats                — list all conversations
  GET  /staff/chats/{phone}        — full history for one conversation
  POST /staff/chats/{phone}/send   — send text to tenant (from Living High number)
  POST /staff/chats/{phone}/media  — upload + send image/video/audio/document
  POST /staff/chats/{phone}/resolve — hand conversation back to bot
  DELETE /staff/chats/{phone}      — wipe conversation from memory
"""
from __future__ import annotations

import os
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import httpx

from app import state
from app.whatsapp import send_message, send_media_message
from app.email import send_invite

router = APIRouter(prefix="/staff", tags=["staff"])
logger = logging.getLogger(__name__)
_bearer = HTTPBearer()


# ── Auth ───────────────────────────────────────────────────────────────────────

def _require_auth(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    expected = os.environ.get("STAFF_DASHBOARD_TOKEN", "")
    if not expected:
        raise HTTPException(503, "STAFF_DASHBOARD_TOKEN is not configured")
    if creds.credentials != expected:
        raise HTTPException(401, "Invalid token")
    return creds.credentials


@router.post("/auth/verify")
def verify_token(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    """Called by the UI on startup to validate a stored token."""
    _require_auth(creds)
    return {"ok": True}


# ── Chat list ──────────────────────────────────────────────────────────────────

@router.get("/chats")
def list_chats(_: str = Depends(_require_auth)):
    """Return all known conversations, handed-off first, then most-recent first."""
    _STATUS_ORDER = {"handed_off": 0, "collecting_info": 1, "bot_active": 2}

    chats = []
    for phone, conv in state._store.items():
        last = conv.history[-1] if conv.history else None
        chats.append({
            "phone": phone,
            "name": conv.tenant_info.name or f"+{phone}",
            "property": conv.tenant_info.property_address,
            "room": conv.tenant_info.room,
            "status": conv.status,
            "session_id": conv.session_id,
            "last_message": last.get("content", "") if last else "",
            "last_role": last.get("role", "") if last else "",
            "last_ts": last.get("ts", "") if last else "",
            "message_count": len(conv.history),
        })

    # Stable sort: most-recent-first within each status group
    chats.sort(key=lambda c: c["last_ts"], reverse=True)
    chats.sort(key=lambda c: _STATUS_ORDER.get(c["status"], 9))
    return chats


# ── Single conversation ────────────────────────────────────────────────────────

@router.get("/chats/{phone}")
def get_chat(phone: str, _: str = Depends(_require_auth)):
    """Return full message history plus metadata for one tenant."""
    conv = state.get(phone)
    return {
        "phone": phone,
        "name": conv.tenant_info.name or f"+{phone}",
        "property": conv.tenant_info.property_address,
        "room": conv.tenant_info.room,
        "status": conv.status,
        "session_id": conv.session_id,
        "handed_off_at": conv.handed_off_at.isoformat() if conv.handed_off_at else None,
        "history": conv.history,
    }


# ── Send messages ──────────────────────────────────────────────────────────────

class _TextBody(BaseModel):
    message: str


@router.post("/chats/{phone}/send")
def send_text(phone: str, body: _TextBody, _: str = Depends(_require_auth)):
    """Send a plain-text message to a tenant from Living High's number."""
    if not body.message.strip():
        raise HTTPException(400, "Message cannot be empty")
    send_message(to=phone, body=body.message)
    state.add_message(phone, "staff", body.message)
    logger.info("Dashboard text | to=%s | msg=%s", phone, body.message)
    return {"ok": True}


@router.post("/chats/{phone}/media")
async def send_media(phone: str, file: UploadFile = File(...), _: str = Depends(_require_auth)):
    """
    Upload a media file to Meta, then send it to the tenant.
    Accepts image/*, video/*, audio/*, and any other file (sent as document).
    """
    content = await file.read()
    media_type = _classify(file.content_type or "application/octet-stream")
    media_id = await _upload_to_meta(content, file.content_type or "application/octet-stream", file.filename or "file")
    send_media_message(to=phone, media_id=media_id, media_type=media_type)
    state.add_message(phone, "staff", f"[{media_type}: {file.filename}]", media_type=media_type)
    logger.info("Dashboard media | to=%s | type=%s | file=%s", phone, media_type, file.filename)
    return {"ok": True, "media_type": media_type}


# ── Handoff management ─────────────────────────────────────────────────────────

@router.post("/chats/{phone}/resolve")
def resolve(phone: str, _: str = Depends(_require_auth)):
    """Return a handed-off conversation to bot control."""
    conv = state.get(phone)
    if conv.status != "handed_off":
        raise HTTPException(400, "Conversation is not currently in handoff")
    state.resolve(phone)
    send_message(
        to=phone,
        body="Our team has sorted that out for you. I'm back and happy to help with anything else! 😊",
    )
    logger.info("Handoff resolved via dashboard | phone=%s", phone)
    return {"ok": True}


@router.delete("/chats/{phone}")
def delete_chat(phone: str, _: str = Depends(_require_auth)):
    """Remove a conversation entirely from memory."""
    state._store.pop(phone, None)
    logger.info("Chat deleted via dashboard | phone=%s", phone)
    return {"ok": True}


# ── Invite ────────────────────────────────────────────────────────────────────

class _InviteBody(BaseModel):
    email: str
    name: str = ""


@router.post("/invite")
def invite_member(body: _InviteBody, _: str = Depends(_require_auth)):
    """Send a Resend invite email so a new staff member can sign up."""
    if not body.email.strip():
        raise HTTPException(400, "email is required")

    dashboard_url = os.environ.get("DASHBOARD_URL", "").rstrip("/")
    if not dashboard_url:
        raise HTTPException(503, "DASHBOARD_URL is not configured")

    import urllib.parse
    params = urllib.parse.urlencode({"invite": "1", "email": body.email.strip()})
    invite_url = f"{dashboard_url}?{params}"

    try:
        send_invite(to_email=body.email.strip(), to_name=body.name.strip(), invite_url=invite_url)
    except Exception as exc:
        logger.error("Failed to send invite | %s", exc)
        raise HTTPException(502, f"Email delivery failed: {exc}") from exc

    logger.info("Invite sent | to=%s", body.email)
    return {"ok": True}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _classify(content_type: str) -> str:
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("video/"):
        return "video"
    if content_type.startswith("audio/"):
        return "audio"
    return "document"


async def _upload_to_meta(content: bytes, content_type: str, filename: str) -> str:
    phone_number_id = os.environ["META_PHONE_NUMBER_ID"]
    token = os.environ["META_ACCESS_TOKEN"]
    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/media"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            data={"messaging_product": "whatsapp", "type": content_type},
            files={"file": (filename, content, content_type)},
            timeout=30,
        )
        if not resp.is_success:
            logger.error("Meta media upload failed | %s | %s", resp.status_code, resp.text)
            resp.raise_for_status()
        return resp.json()["id"]
