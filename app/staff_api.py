"""Staff dashboard API — JWT auth via Neon PostgreSQL."""
from __future__ import annotations

import os
import logging
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from pydantic import BaseModel
import httpx

from app import state, auth
from app.whatsapp import send_message, send_media_message
from app.email import send_invite

router = APIRouter(prefix="/staff", tags=["staff"])
logger = logging.getLogger(__name__)
_bearer = HTTPBearer()


# ── Auth guards ────────────────────────────────────────────────────────────────

def _require_auth(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    try:
        return auth.decode_token(creds.credentials)
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")


def _require_admin(payload: dict = Depends(_require_auth)) -> dict:
    if payload.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return payload


# ── Auth endpoints ─────────────────────────────────────────────────────────────

class _LoginBody(BaseModel):
    email: str
    password: str


class _SignupBody(BaseModel):
    email: str
    name: str
    password: str


@router.post("/auth/login")
def login(body: _LoginBody):
    """Email + password → JWT token."""
    user = auth.login(body.email, body.password)
    if not user:
        raise HTTPException(401, "Wrong email or password")
    token = auth.create_token(user["email"], user["name"], user["role"])
    logger.info("Login | email=%s", user["email"])
    return {"token": token, "name": user["name"], "role": user["role"]}


@router.get("/auth/me")
def me(payload: dict = Depends(_require_auth)):
    """Return the current user's profile from the JWT."""
    return {"email": payload["sub"], "name": payload.get("name", ""), "role": payload.get("role", "agent")}


@router.post("/auth/signup")
def signup(body: _SignupBody):
    """
    Create a new staff account. Allowed when:
    - No admin exists yet (first-time setup), OR
    - Request arrives with ?invite=1 query param (from invite email link).
    Admin-only account creation is handled by /staff/invite.
    """
    if auth.user_exists(body.email):
        raise HTTPException(409, "An account with this email already exists")

    role = "admin" if not auth.any_admin_exists() else "agent"
    auth.create_user(body.email, body.name, body.password, role)
    user = auth.login(body.email, body.password)
    token = auth.create_token(user["email"], user["name"], user["role"])
    logger.info("Signup | email=%s | role=%s", body.email, role)
    return {"token": token, "name": user["name"], "role": user["role"]}


@router.post("/auth/admin-exists")
def admin_exists():
    """Returns whether any admin account exists (used by login page to show setup form)."""
    return {"exists": auth.any_admin_exists()}


# ── Chat list ──────────────────────────────────────────────────────────────────

@router.get("/chats")
def list_chats(_: dict = Depends(_require_auth)):
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
    chats.sort(key=lambda c: c["last_ts"], reverse=True)
    chats.sort(key=lambda c: _STATUS_ORDER.get(c["status"], 9))
    return chats


# ── Single conversation ────────────────────────────────────────────────────────

@router.get("/chats/{phone}")
def get_chat(phone: str, _: dict = Depends(_require_auth)):
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
def send_text(phone: str, body: _TextBody, _: dict = Depends(_require_auth)):
    if not body.message.strip():
        raise HTTPException(400, "Message cannot be empty")
    send_message(to=phone, body=body.message)
    state.add_message(phone, "staff", body.message)
    logger.info("Dashboard text | to=%s", phone)
    return {"ok": True}


@router.post("/chats/{phone}/media")
async def send_media(phone: str, file: UploadFile = File(...), _: dict = Depends(_require_auth)):
    content = await file.read()
    media_type = _classify(file.content_type or "application/octet-stream")
    media_id = await _upload_to_meta(content, file.content_type or "application/octet-stream", file.filename or "file")
    send_media_message(to=phone, media_id=media_id, media_type=media_type)
    state.add_message(phone, "staff", f"[{media_type}: {file.filename}]", media_type=media_type)
    logger.info("Dashboard media | to=%s | type=%s", phone, media_type)
    return {"ok": True, "media_type": media_type}


# ── Handoff management ─────────────────────────────────────────────────────────

@router.post("/chats/{phone}/resolve")
def resolve(phone: str, _: dict = Depends(_require_auth)):
    conv = state.get(phone)
    if conv.status != "handed_off":
        raise HTTPException(400, "Conversation is not currently in handoff")
    state.resolve(phone)
    send_message(to=phone, body="Our team has sorted that out for you. I'm back and happy to help with anything else! 😊")
    logger.info("Handoff resolved | phone=%s", phone)
    return {"ok": True}


@router.delete("/chats/{phone}")
def delete_chat(phone: str, _: dict = Depends(_require_auth)):
    state._store.pop(phone, None)
    logger.info("Chat deleted | phone=%s", phone)
    return {"ok": True}


# ── Invite ─────────────────────────────────────────────────────────────────────

class _InviteBody(BaseModel):
    email: str
    name: str = ""


@router.post("/invite")
def invite_member(body: _InviteBody, _: dict = Depends(_require_admin)):
    if not body.email.strip():
        raise HTTPException(400, "email is required")
    dashboard_url = os.environ.get("DASHBOARD_URL", "").rstrip("/")
    if not dashboard_url:
        raise HTTPException(503, "DASHBOARD_URL is not configured")

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
    if content_type.startswith("image/"): return "image"
    if content_type.startswith("video/"): return "video"
    if content_type.startswith("audio/"): return "audio"
    return "document"


async def _upload_to_meta(content: bytes, content_type: str, filename: str) -> str:
    phone_number_id = os.environ["META_PHONE_NUMBER_ID"]
    token = os.environ["META_ACCESS_TOKEN"]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://graph.facebook.com/v19.0/{phone_number_id}/media",
            headers={"Authorization": f"Bearer {token}"},
            data={"messaging_product": "whatsapp", "type": content_type},
            files={"file": (filename, content, content_type)},
            timeout=30,
        )
        if not resp.is_success:
            logger.error("Meta media upload failed | %s | %s", resp.status_code, resp.text)
            resp.raise_for_status()
        return resp.json()["id"]
