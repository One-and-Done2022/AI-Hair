from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.schemas import MeResponse
from app.services import repository


router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeResponse)
def get_me(current_user: dict = Depends(get_current_user)) -> MeResponse:
    summary = repository.get_user_profile_summary(current_user["id"])
    return MeResponse(**summary)
