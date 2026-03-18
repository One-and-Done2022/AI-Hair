from __future__ import annotations

from fastapi import APIRouter

from app.schemas import AuthResponse, LoginRequest
from app.services.auth import login_with_wechat_code


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/wechat/login", response_model=AuthResponse)
async def wechat_login(payload: LoginRequest) -> AuthResponse:
    data = await login_with_wechat_code(payload.code)
    return AuthResponse(**data)

