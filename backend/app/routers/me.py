from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.schemas import MeProfileUpdateRequest, MeResponse
from app.services import provider_alerts, repository


router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeResponse)
def get_me(current_user: dict = Depends(get_current_user)) -> MeResponse:
    summary = repository.get_user_profile_summary(current_user["id"])
    return MeResponse(
        **summary,
        provider_alerts=provider_alerts.list_alert_messages(),
    )


@router.patch("/profile", response_model=MeResponse)
def update_me_profile(
    payload: MeProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
) -> MeResponse:
    repository.update_user_nickname(current_user["id"], payload.nickname)
    summary = repository.get_user_profile_summary(current_user["id"])
    return MeResponse(
        **summary,
        provider_alerts=provider_alerts.list_alert_messages(),
    )
