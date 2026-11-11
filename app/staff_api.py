"""Staff dashboard API — JWT auth, DB-backed conversations, shifts, settings."""
from __future__ import annotations

import os
import logging
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from pydantic import BaseModel
import httpx

from app import sse as sse_mod

from app import auth
from app import db_conversations as dbc
from app import shifts as shifts_mod
from app.whatsapp import send_message, send_media_message
from app.email import send_invite
from app.handoff import resolve as resolve_handoff

router = APIRouter(prefix="/staff", tags=["staff"])
logger = logging.getLogger(__name__)
_bearer = HTTPBearer()


# ── Auth guards ────────────────────────────────────────────────────────────────

def _require_auth(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    try:
        return auth.decode_token(creds.credentials)
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")


def _require_auth_query(token: str = Query("")) -> dict:
    """Auth via query param — used for EventSource which can't set headers."""
    try:
        return auth.decode_token(token)
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
    role: str = "agent"
    whatsapp_number: str | None = None


@router.post("/auth/login")
def login(body: _LoginBody):
    user = auth.login(body.email, body.password)
    if not user:
        raise HTTPException(401, "Wrong email or password")
    token = auth.create_token(user["email"], user["name"], user["role"])
    return {"token": token, "name": user["name"], "role": user["role"]}


@router.get("/auth/me")
def me(payload: dict = Depends(_require_auth)):
    return {
        "email": payload["sub"],
        "name": payload.get("name", ""),
        "role": payload.get("role", "agent"),
    }


@router.post("/auth/signup")
def signup(body: _SignupBody):
    if auth.user_exists(body.email):
        raise HTTPException(409, "An account with this email already exists")
    # First user ever becomes admin regardless of requested role
    role = "admin" if not auth.any_admin_exists() else body.role
    if role not in ("admin", "agent"):
        role = "agent"
    auth.create_user(body.email, body.name, body.password, role, body.whatsapp_number)
    user = auth.login(body.email, body.password)
    token = auth.create_token(user["email"], user["name"], user["role"])
    return {"token": token, "name": user["name"], "role": user["role"]}


@router.post("/auth/admin-exists")
def admin_exists():
    return {"exists": auth.any_admin_exists()}


# ── Users ──────────────────────────────────────────────────────────────────────

@router.get("/users")
def list_users(_: dict = Depends(_require_auth)):
    users = auth.list_users()
    # Reshape to match the Member type the frontend expects
    return [
        {
            "id": u["id"],
            "full_name": u["name"],
            "email": u["email"],
            "role": u["role"],
            "whatsapp_number": u["whatsapp_number"],
        }
        for u in users
    ]


@router.delete("/users/{user_id}")
def delete_user(user_id: str, payload: dict = Depends(_require_admin)):
    if not auth.delete_user(user_id):
        raise HTTPException(404, "User not found")
    return {"ok": True}


# ── Handoff mode ───────────────────────────────────────────────────────────────

@router.get("/settings/handoff-mode")
def get_handoff_mode(_: dict = Depends(_require_auth)):
    return {"mode": dbc.get_setting("handoff_mode", "dashboard")}


class _ModeBody(BaseModel):
    mode: str


@router.put("/settings/handoff-mode")
def set_handoff_mode(body: _ModeBody, _: dict = Depends(_require_admin)):
    if body.mode not in ("dashboard", "whatsapp"):
        raise HTTPException(400, "mode must be 'dashboard' or 'whatsapp'")
    dbc.set_setting("handoff_mode", body.mode)
    return {"mode": body.mode}


# ── Shifts ─────────────────────────────────────────────────────────────────────

@router.get("/shifts")
def list_shifts(_: dict = Depends(_require_auth)):
    return shifts_mod.list_all()


class _ShiftBody(BaseModel):
    staff_user_id: str
    weekday: int
    start_time: str  # "HH:MM"
    end_time: str    # "HH:MM"


@router.post("/shifts", status_code=201)
def add_shift(body: _ShiftBody, _: dict = Depends(_require_admin)):
    if not (0 <= body.weekday <= 6):
        raise HTTPException(400, "weekday must be 0–6")
    shift_id = shifts_mod.add(
        body.staff_user_id, body.weekday, body.start_time, body.end_time
    )
    return {"id": shift_id}


@router.delete("/shifts/{shift_id}")
def delete_shift(shift_id: str, _: dict = Depends(_require_admin)):
    if not shifts_mod.delete(shift_id):
        raise HTTPException(404, "Shift not found")
    return {"ok": True}


# ── SSE real-time feed ─────────────────────────────────────────────────────────

@router.get("/events")
async def events(_: dict = Depends(_require_auth_query)):
    return StreamingResponse(
        sse_mod.stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Chat list ──────────────────────────────────────────────────────────────────

@router.get("/chats")
def list_chats(payload: dict = Depends(_require_auth)):
    is_admin = payload.get("role") == "admin"
    if is_admin:
        return dbc.list_for_dashboard()
    staff_id = auth.get_user_id(payload["sub"])
    return dbc.list_for_dashboard(staff_id=staff_id)


# ── Single conversation ────────────────────────────────────────────────────────

@router.get("/chats/{phone}")
def get_chat(phone: str, _: dict = Depends(_require_auth)):
    conv = dbc.get_detail(phone)
    if not conv:
        # Return empty shell so the frontend doesn't crash on a first visit
        return {
            "phone": phone, "name": None, "property": None, "room": None,
            "status": "bot_active", "session_id": None, "history": [],
        }
    return conv


# ── Send messages ──────────────────────────────────────────────────────────────

class _TextBody(BaseModel):
    message: str


@router.post("/chats/{phone}/send")
def send_text(phone: str, body: _TextBody, _: dict = Depends(_require_auth)):
    if not body.message.strip():
        raise HTTPException(400, "Message cannot be empty")
    send_message(to=phone, body=body.message)
    dbc.add_message(phone, "staff", body.message)
    logger.info("Dashboard reply | to=%s", phone)
    return {"ok": True}


@router.post("/chats/{phone}/media")
async def send_media(phone: str, file: UploadFile = File(...), _: dict = Depends(_require_auth)):
    content = await file.read()
    media_type = _classify(file.content_type or "application/octet-stream")
    media_id = await _upload_to_meta(content, file.content_type or "application/octet-stream", file.filename or "file")
    send_media_message(to=phone, media_id=media_id, media_type=media_type)
    dbc.add_message(phone, "staff", f"[{media_type}: {file.filename}]")
    return {"ok": True, "media_type": media_type}


# ── Handoff management ─────────────────────────────────────────────────────────

@router.post("/chats/{phone}/resolve")
def resolve(phone: str, _: dict = Depends(_require_auth)):
    conv = dbc.get_or_create(phone)
    if conv["status"] != "handed_off":
        raise HTTPException(400, "Conversation is not currently in handoff")
    resolve_handoff(phone)
    send_message(
        to=phone,
        body="Our team has sorted that out for you. I'm back and happy to help with anything else! 😊",
    )
    return {"ok": True}


@router.post("/chats/{phone}/assign")
def assign_chat(phone: str, body: dict, payload: dict = Depends(_require_auth)):
    staff_id = body.get("staff_id")
    dbc.update(phone, assigned_staff_id=staff_id)
    return {"ok": True}


@router.delete("/chats/{phone}")
def delete_chat(phone: str, _: dict = Depends(_require_auth)):
    # Soft delete: reset to bot_active with no history (delete messages)
    conv = dbc.get_or_create(phone)
    if conv.get("id"):
        from app import db
        with db.conn() as c:
            cur = c.cursor()
            cur.execute("DELETE FROM messages WHERE conversation_id = %s", [conv["id"]])
        dbc.update(
            phone,
            status="bot_active", session_id=None, assigned_staff_id=None,
            handoff_reason=None, info_collected=False,
            tenant_name=None, property_address=None, room=None,
        )
    return {"ok": True}


# ── Invite ─────────────────────────────────────────────────────────────────────

class _InviteBody(BaseModel):
    email: str
    name: str = ""
    role: str = "agent"
    whatsapp_number: str | None = None


@router.post("/invite")
def invite_member(body: _InviteBody, _: dict = Depends(_require_admin)):
    if not body.email.strip():
        raise HTTPException(400, "email is required")
    dashboard_url = os.environ.get("DASHBOARD_URL", "").rstrip("/")
    if not dashboard_url:
        raise HTTPException(503, "DASHBOARD_URL is not configured")

    role = body.role if body.role in ("admin", "agent") else "agent"
    params = urllib.parse.urlencode({
        "invite": "1",
        "email": body.email.strip(),
        "role": role,
    })
    invite_url = f"{dashboard_url}?{params}"

    try:
        send_invite(to_email=body.email.strip(), to_name=body.name.strip(), invite_url=invite_url)
    except Exception as exc:
        logger.error("Failed to send invite: %s", exc)
        raise HTTPException(502, f"Email delivery failed: {exc}") from exc

    logger.info("Invite sent | to=%s | role=%s", body.email, role)
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
