from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.dependencies import get_current_user
from app.schemas import UploadResponse
from app.services import repository, storage


router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse)
async def create_upload(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
) -> UploadResponse:
    image_bytes = await file.read()
    try:
        metadata = storage.validate_upload_bytes(image_bytes, file.content_type)
    except storage.UploadValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    stored_path = storage.save_upload_file(image_bytes, metadata.extension)
    upload = repository.create_upload(
        user_id=current_user["id"],
        original_name=file.filename or "upload",
        stored_path=stored_path,
        mime_type=file.content_type or "application/octet-stream",
        file_size=len(image_bytes),
        width=metadata.width,
        height=metadata.height,
    )
    upload_url = str(request.base_url).rstrip("/") + f"/media/{upload['stored_path']}"
    return UploadResponse(
        upload_id=upload["id"],
        upload_url=upload_url,
        width=upload["width"],
        height=upload["height"],
    )

