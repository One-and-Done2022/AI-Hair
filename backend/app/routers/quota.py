from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user
from app.schemas import (
    AdUnlockClaimRequest,
    AdUnlockSessionResponse,
    QuotaSnapshotResponse,
)
from app.services import repository


router = APIRouter(prefix="/quota", tags=["quota"])


def _quota_response(summary: dict) -> QuotaSnapshotResponse:
    return QuotaSnapshotResponse(
        remaining_quota=int(summary.get("remaining_quota") or 0),
        free_quota_total=int(summary.get("free_quota_total") or 0),
        free_quota_used=int(summary.get("free_quota_used") or 0),
        free_remaining=int(summary.get("free_remaining") or 0),
        initial_free_total=int(summary.get("initial_free_total") or 0),
        initial_free_used=int(summary.get("initial_free_used") or 0),
        initial_free_remaining=int(summary.get("initial_free_remaining") or 0),
        reward_ad_grant_total=int(summary.get("reward_ad_grant_total") or 0),
        reward_ad_used=int(summary.get("reward_ad_used") or 0),
        reward_ad_remaining=int(summary.get("reward_ad_remaining") or 0),
        reward_ad_max=int(summary.get("reward_ad_max") or 0),
        reward_ad_available_to_claim=int(
            summary.get("reward_ad_available_to_claim") or 0
        ),
        can_unlock_by_ad=bool(summary.get("can_unlock_by_ad")),
        paid_remaining=int(summary.get("paid_remaining") or 0),
        total_remaining=int(summary.get("total_remaining") or 0),
    )


def _quota_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    if code == "quota_still_available":
        return HTTPException(
            status_code=409,
            detail={
                "code": "quota_still_available",
                "message": "你当前还有可用次数，无需通过广告解锁。",
            },
        )
    if code == "reward_ad_limit_reached":
        return HTTPException(
            status_code=409,
            detail={
                "code": "reward_ad_limit_reached",
                "message": "广告解锁次数已用完，请直接购买 1 次生成包。",
            },
        )
    if code == "ad_unlock_session_not_found":
        return HTTPException(
            status_code=404,
            detail={
                "code": "ad_unlock_session_not_found",
                "message": "未找到本次广告解锁会话，请重新开始。",
            },
        )
    if code == "ad_unlock_session_expired":
        return HTTPException(
            status_code=409,
            detail={
                "code": "ad_unlock_session_expired",
                "message": "广告解锁会话已过期，请重新观看广告。",
            },
        )
    if code == "ad_unlock_session_already_claimed":
        return HTTPException(
            status_code=409,
            detail={
                "code": "ad_unlock_session_already_claimed",
                "message": "本次广告奖励已领取，请勿重复提交。",
            },
        )
    raise HTTPException(
        status_code=400,
        detail={
            "code": "ad_unlock_failed",
            "message": "广告解锁失败，请稍后再试。",
        },
    )


@router.post("/ad-unlock/session", response_model=AdUnlockSessionResponse)
def create_ad_unlock_session(
    current_user: dict = Depends(get_current_user),
) -> AdUnlockSessionResponse:
    try:
        session_payload = repository.create_ad_unlock_session(current_user["id"])
    except ValueError as exc:
        raise _quota_error(exc) from exc
    return AdUnlockSessionResponse(**session_payload)


@router.post("/ad-unlock/claim", response_model=QuotaSnapshotResponse)
def claim_ad_unlock_session(
    payload: AdUnlockClaimRequest,
    current_user: dict = Depends(get_current_user),
) -> QuotaSnapshotResponse:
    try:
        summary = repository.claim_ad_unlock_session(
            user_id=current_user["id"],
            session_id=payload.session_id,
        )
    except ValueError as exc:
        raise _quota_error(exc) from exc
    return _quota_response(summary)
