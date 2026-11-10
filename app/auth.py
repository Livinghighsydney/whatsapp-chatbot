"""JWT auth helpers for the staff dashboard."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app import db

ALGORITHM = "HS256"
TOKEN_DAYS = 30


def _secret() -> str:
    s = os.environ.get("JWT_SECRET", "")
    if not s:
        raise RuntimeError("JWT_SECRET env var is not set")
    return s


# ── Password ───────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT ────────────────────────────────────────────────────────────────────────

def create_token(email: str, name: str, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS)
    return jwt.encode({"sub": email, "name": name, "role": role, "exp": exp}, _secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Returns payload dict or raises JWTError."""
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM])


# ── Database helpers ───────────────────────────────────────────────────────────

def login(email: str, password: str) -> dict | None:
    """Verify credentials. Returns user dict or None."""
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("SELECT email, name, password_hash, role FROM staff_users WHERE email = %s", (email.lower().strip(),))
        row = cur.fetchone()
    if not row:
        return None
    email_db, name, pw_hash, role = row
    if not verify_password(password, pw_hash):
        return None
    return {"email": email_db, "name": name, "role": role}


def create_user(email: str, name: str, password: str, role: str = "agent") -> None:
    pw_hash = hash_password(password)
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT INTO staff_users (email, name, password_hash, role) VALUES (%s, %s, %s, %s)",
            (email.lower().strip(), name.strip(), pw_hash, role),
        )


def user_exists(email: str) -> bool:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("SELECT 1 FROM staff_users WHERE email = %s", (email.lower().strip(),))
        return cur.fetchone() is not None


def any_admin_exists() -> bool:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("SELECT 1 FROM staff_users WHERE role = 'admin' LIMIT 1")
        return cur.fetchone() is not None
