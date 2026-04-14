from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from app.services import repository
from app.services import admin_auth


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    token = authorization.replace("Bearer ", "", 1).strip()
    user = repository.get_user_by_token(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )
    return user


def get_current_admin(request: Request) -> dict:
    if not admin_auth.is_admin_auth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="管理员后台未配置账号密码。",
        )

    admin = admin_auth.current_admin_from_request(request)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员登录已失效或未登录。",
        )
    return admin
