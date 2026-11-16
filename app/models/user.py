from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt
from app.core import db

ALGORITHM = "HS256"
TOKEN_DAYS = 30


def _secret() -> str:
    s = os.environ.get("JWT_SECRET", "")
    if not s:
        raise RuntimeError("JWT_SECRET env var is not set")
    return s


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(email: str, name: str, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS)
    return jwt.encode({"sub": email, "name": name, "role": role, "exp": exp}, _secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM])


def login(email: str, password: str) -> dict | None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "SELECT email, name, password_hash, role FROM staff_users WHERE email = %s",
            (email.lower().strip(),),
        )
        row = cur.fetchone()
    if not row or not verify_password(password, row[2]):
        return None
    return {"email": row[0], "name": row[1], "role": row[3]}


def create(email: str, name: str, password: str, role: str = "agent", whatsapp_number: str | None = None) -> None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT INTO staff_users (email, name, password_hash, role, whatsapp_number) "
            "VALUES (%s, %s, %s, %s, %s)",
            (email.lower().strip(), name.strip(), hash_password(password), role, whatsapp_number or None),
        )


def exists(email: str) -> bool:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("SELECT 1 FROM staff_users WHERE email = %s", (email.lower().strip(),))
        return cur.fetchone() is not None


def any_admin() -> bool:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("SELECT 1 FROM staff_users WHERE role = 'admin' LIMIT 1")
        return cur.fetchone() is not None


def list_all() -> list[dict]:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("SELECT id::text, email, name, role, whatsapp_number FROM staff_users ORDER BY created_at ASC")
        return [dict(zip(["id", "email", "name", "role", "whatsapp_number"], row)) for row in cur.fetchall()]


def delete(user_id: str) -> bool:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("DELETE FROM staff_users WHERE id = %s", [user_id])
        return cur.rowcount > 0


def get_id(email: str) -> str | None:
    with db.conn() as c:
        cur = c.cursor()
        cur.execute("SELECT id::text FROM staff_users WHERE email = %s", [email.lower().strip()])
        row = cur.fetchone()
        return row[0] if row else None
