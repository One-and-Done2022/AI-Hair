from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import get_current_user
from app.schemas import RecommendationResponse
from app.services import recommendations, repository


router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendationRequest(BaseModel):
    upload_id: str = Field(min_length=1)


@router.post("", response_model=RecommendationResponse)
def create_recommendation(
    payload: RecommendationRequest,
    current_user: dict = Depends(get_current_user),
) -> RecommendationResponse:
    upload = repository.get_upload(payload.upload_id)
    if upload is None or upload["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Upload not found.")
    try:
        result = recommendations.build_recommendation_payload(upload)
    except recommendations.RecommendationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "recommendation_unavailable", "message": str(exc)},
        ) from exc
    return RecommendationResponse(
        upload_id=payload.upload_id,
        **result,
    )
