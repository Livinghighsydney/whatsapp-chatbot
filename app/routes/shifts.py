from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.models import shift as shift_model
from app.routes.deps import require_auth, require_admin

router = APIRouter(prefix="/shifts")


class _ShiftBody(BaseModel):
    staff_user_id: str
    weekday: int
    start_time: str
    end_time: str


@router.get("")
def list_shifts(_: dict = Depends(require_auth)):
    return shift_model.list_all()


@router.post("", status_code=201)
def add_shift(body: _ShiftBody, _: dict = Depends(require_admin)):
    if not (0 <= body.weekday <= 6):
        raise HTTPException(400, "weekday must be 0–6")
    return {"id": shift_model.add(body.staff_user_id, body.weekday, body.start_time, body.end_time)}


@router.delete("/{shift_id}")
def delete_shift(shift_id: str, _: dict = Depends(require_admin)):
    if not shift_model.delete(shift_id):
        raise HTTPException(404, "Shift not found")
    return {"ok": True}
