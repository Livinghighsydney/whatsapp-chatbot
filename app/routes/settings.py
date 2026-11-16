from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.models import settings as settings_model
from app.routes.deps import require_auth, require_admin

router = APIRouter(prefix="/settings")


@router.get("/handoff-mode")
def get_mode(_: dict = Depends(require_auth)):
    return {"mode": settings_model.get("handoff_mode", "dashboard")}


class _ModeBody(BaseModel):
    mode: str


@router.put("/handoff-mode")
def set_mode(body: _ModeBody, _: dict = Depends(require_admin)):
    if body.mode not in ("dashboard", "whatsapp"):
        raise HTTPException(400, "mode must be 'dashboard' or 'whatsapp'")
    settings_model.set("handoff_mode", body.mode)
    return {"mode": body.mode}
