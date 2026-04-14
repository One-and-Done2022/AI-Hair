from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user
from app.schemas import (
    FeedbackPendingResponse,
    FeedbackSubmissionRequest,
    FeedbackSubmissionResponse,
)
from app.services import repository


router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/pending", response_model=FeedbackPendingResponse)
def get_pending_feedback(
    job_id: str = Query(min_length=1),
    current_user: dict = Depends(get_current_user),
) -> FeedbackPendingResponse:
    pending = repository.get_pending_feedback_for_job(current_user["id"], job_id)
    if pending is None:
        return FeedbackPendingResponse(pending=False)
    return FeedbackPendingResponse(
        pending=True,
        survey_type=pending["survey_type"],
        title=pending["title"],
        description=pending["description"],
        trigger_completed_jobs=pending["trigger_completed_jobs"],
        success_ordinal=pending["success_ordinal"],
        job_id=pending["job_id"],
    )


@router.post("/submissions", response_model=FeedbackSubmissionResponse, status_code=status.HTTP_201_CREATED)
def create_feedback_submission(
    payload: FeedbackSubmissionRequest,
    current_user: dict = Depends(get_current_user),
) -> FeedbackSubmissionResponse:
    existing = repository.get_feedback_submission_for_user(
        current_user["id"],
        payload.survey_type,
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前阶段的反馈已经提交过了。",
        )

    pending = repository.get_pending_feedback_for_job(current_user["id"], payload.job_id)
    if pending is None or pending["survey_type"] != payload.survey_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前任务没有待提交的对应反馈。",
        )

    try:
        submission = repository.create_feedback_submission(
            user_id=current_user["id"],
            job_id=payload.job_id,
            survey_type=payload.survey_type,
            trigger_completed_jobs=pending["trigger_completed_jobs"],
            hairstyle_expectation=payload.hairstyle_expectation,
            hair_color_satisfaction=payload.hair_color_satisfaction,
            scene_satisfaction=payload.scene_satisfaction,
            wait_time_feeling=payload.wait_time_feeling,
            image_clarity_satisfaction=payload.image_clarity_satisfaction,
            ui_usability=payload.ui_usability,
            improvement_suggestion=payload.improvement_suggestion,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前阶段的反馈已经提交过了。",
        ) from exc

    return FeedbackSubmissionResponse(
        submission_id=submission["id"],
        created_at=submission["created_at"],
        survey_type=submission["survey_type"],
        trigger_completed_jobs=int(submission["trigger_completed_jobs"]),
    )
