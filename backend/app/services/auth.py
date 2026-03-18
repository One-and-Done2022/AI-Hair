from __future__ import annotations

import hashlib

import httpx
from fastapi import HTTPException, status

from app.config import get_settings
from app.services import repository


async def _wechat_code_to_openid(code: str) -> str:
    settings = get_settings()
    if settings.allow_dev_login and (code.startswith("dev_") or code.startswith("dev-")):
        digest = hashlib.sha256(code.encode("utf-8")).hexdigest()[:24]
        return f"dev_{digest}"

    if not settings.wechat_app_id or not settings.wechat_app_secret:
        if settings.allow_dev_login:
            digest = hashlib.sha256(code.encode("utf-8")).hexdigest()[:24]
            return f"dev_{digest}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WeChat credentials are not configured.",
        )

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={
                "appid": settings.wechat_app_id,
                "secret": settings.wechat_app_secret,
                "js_code": code,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        payload = response.json()

    openid = payload.get("openid")
    if not openid:
        error_message = payload.get("errmsg", "Failed to exchange WeChat login code.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_message,
        )
    return openid


async def login_with_wechat_code(code: str) -> dict:
    openid = await _wechat_code_to_openid(code)
    user = repository.get_or_create_user(openid)
    token = repository.create_auth_token(user["id"])
    return {"token": token, "user_id": user["id"]}
