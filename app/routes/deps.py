from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from app.models import user as user_model

_bearer = HTTPBearer()


def require_auth(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    try:
        return user_model.decode_token(creds.credentials)
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")


def require_auth_query(token: str = Query("")) -> dict:
    try:
        return user_model.decode_token(token)
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")


def require_admin(payload: dict = Depends(require_auth)) -> dict:
    if payload.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return payload
