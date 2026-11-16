from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.models import user as user_model
from app.routes.deps import require_auth

router = APIRouter(prefix="/auth")


class _LoginBody(BaseModel):
    email: str
    password: str


class _SignupBody(BaseModel):
    email: str
    name: str
    password: str
    role: str = "agent"
    whatsapp_number: str | None = None


@router.post("/login")
def login(body: _LoginBody):
    u = user_model.login(body.email, body.password)
    if not u:
        raise HTTPException(401, "Wrong email or password")
    token = user_model.create_token(u["email"], u["name"], u["role"])
    return {"token": token, "name": u["name"], "role": u["role"]}


@router.get("/me")
def me(payload: dict = Depends(require_auth)):
    return {"email": payload["sub"], "name": payload.get("name", ""), "role": payload.get("role", "agent")}


@router.post("/signup")
def signup(body: _SignupBody):
    if user_model.exists(body.email):
        raise HTTPException(409, "An account with this email already exists")
    role = "admin" if not user_model.any_admin() else body.role
    if role not in ("admin", "agent"):
        role = "agent"
    user_model.create(body.email, body.name, body.password, role, body.whatsapp_number)
    u = user_model.login(body.email, body.password)
    token = user_model.create_token(u["email"], u["name"], u["role"])
    return {"token": token, "name": u["name"], "role": u["role"]}


@router.post("/admin-exists")
def admin_exists():
    return {"exists": user_model.any_admin()}
