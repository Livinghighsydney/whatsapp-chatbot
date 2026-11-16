from __future__ import annotations
import logging
import os
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.models import user as user_model
from app.services.email import send_invite
from app.routes.deps import require_auth, require_admin

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/users")
def list_users(_: dict = Depends(require_auth)):
    return [
        {"id": u["id"], "full_name": u["name"], "email": u["email"],
         "role": u["role"], "whatsapp_number": u["whatsapp_number"]}
        for u in user_model.list_all()
    ]


@router.delete("/users/{user_id}")
def delete_user(user_id: str, _: dict = Depends(require_admin)):
    if not user_model.delete(user_id):
        raise HTTPException(404, "User not found")
    return {"ok": True}


class _InviteBody(BaseModel):
    email: str
    name: str = ""
    role: str = "agent"
    whatsapp_number: str | None = None


@router.post("/invite")
def invite(body: _InviteBody, _: dict = Depends(require_admin)):
    if not body.email.strip():
        raise HTTPException(400, "email is required")
    dashboard_url = os.environ.get("DASHBOARD_URL", "").rstrip("/")
    if not dashboard_url:
        raise HTTPException(503, "DASHBOARD_URL is not configured")
    role = body.role if body.role in ("admin", "agent") else "agent"
    params = urllib.parse.urlencode({"invite": "1", "email": body.email.strip(), "role": role})
    try:
        send_invite(to_email=body.email.strip(), to_name=body.name.strip(),
                    invite_url=f"{dashboard_url}?{params}")
    except Exception as exc:
        raise HTTPException(502, f"Email delivery failed: {exc}") from exc
    logger.info("Invite sent | to=%s | role=%s", body.email, role)
    return {"ok": True}
