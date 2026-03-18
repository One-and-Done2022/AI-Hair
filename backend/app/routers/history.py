from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.dependencies import get_current_user
from app.routers.jobs import _job_response
from app.schemas import HistoryResponse
from app.services import repository


router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=HistoryResponse)
def get_history(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> HistoryResponse:
    items = [
        _job_response(request, job)
        for job in repository.list_jobs_for_user(current_user["id"])
    ]
    return HistoryResponse(items=items)

