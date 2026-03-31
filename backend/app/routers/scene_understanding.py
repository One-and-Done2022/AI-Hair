from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.schemas import SceneUnderstandingRequest, SceneUnderstandingResponse
from app.services import image_understanding, repository, storage
from app.services.image_understanding import SceneDraftOptions


router = APIRouter(prefix="/scene-understanding", tags=["scene-understanding"])


@router.post("", response_model=SceneUnderstandingResponse)
def create_scene_understanding(
    payload: SceneUnderstandingRequest,
    current_user: dict = Depends(get_current_user),
) -> SceneUnderstandingResponse:
    upload = repository.get_upload(payload.upload_id)
    if upload is None or upload["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Upload not found.")

    try:
        image_bytes = storage.read_file_bytes(upload["stored_path"])
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "upload_file_missing", "message": "找不到这张参考图文件。"},
        ) from exc

    try:
        service = image_understanding.ImageUnderstandingService()
        result = service.extract_scene_blocks(image_bytes)
        scene_draft = image_understanding.build_scene_draft(
            result.blocks,
            options=SceneDraftOptions(
                scene_id=payload.scene_id,
                title=payload.title,
                style_line=payload.style_line,
                detail_tags=tuple(payload.detail_tags),
                pairing_advice=tuple(payload.pairing_advice),
                reference_source_ids=tuple(payload.reference_source_ids),
                reference_notes=payload.reference_notes,
            ),
        )
    except image_understanding.ImageUnderstandingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "scene_understanding_unavailable",
                "message": str(exc),
            },
        ) from exc

    return SceneUnderstandingResponse(
        upload_id=payload.upload_id,
        model_name=result.model_name,
        subject_gender=result.subject_gender,
        blocks=result.blocks,
        scene_draft=scene_draft,
    )
