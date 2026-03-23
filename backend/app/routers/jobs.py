from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import get_settings
from app.dependencies import get_current_user
from app.schemas import JobCreateRequest, JobResponse
from app.services.generation import ImageGenerationError, build_generator
from app.services import repository, retention, storage, templates


router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_response(request: Request, job: dict) -> JobResponse:
    hairstyle = templates.get_hairstyle(job["hairstyle_id"])
    scene = templates.get_scene(job["scene_id"])
    prompt_payload = templates.parse_job_prompt_payload(job.get("prompt") or "")
    upload = repository.get_upload(job["upload_id"])
    base_url = str(request.base_url).rstrip("/")
    upload_url = (
        storage.media_url(upload["stored_path"], base_url=base_url)
        if upload
        else None
    )
    result_paths = storage.list_result_candidates(job["id"], job.get("result_path"))
    result_image_urls: list[str] = []
    for path in result_paths:
        resolved = storage.media_url(path, base_url=base_url)
        if resolved:
            result_image_urls.append(resolved)
    result_image_url = result_image_urls[0] if result_image_urls else None
    media_expires_at = retention.media_expires_at(job["created_at"])
    media_expired = retention.is_media_expired(job["created_at"])
    return JobResponse(
        job_id=job["id"],
        status=job["status"],
        upload_url=upload_url,
        result_image_url=result_image_url,
        result_image_urls=result_image_urls,
        media_expired=media_expired,
        media_expires_at=media_expires_at,
        hairstyle_id=job["hairstyle_id"],
        hairstyle_name=hairstyle["name"] if hairstyle else job["hairstyle_id"],
        scene_id=job["scene_id"],
        scene_name=scene["name"] if scene else job["scene_id"],
        generator_backend=prompt_payload["output_options"]["generator_backend"],
        aspect_ratio=prompt_payload["output_options"]["aspect_ratio"],
        resolution=prompt_payload["output_options"]["resolution"],
        error_code=job.get("error_code"),
        error_message=job.get("error_message"),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> JobResponse:
    upload = repository.get_upload(payload.upload_id)
    if upload is None or upload["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Upload not found.")

    hairstyle = templates.get_hairstyle(payload.hairstyle_id)
    scene = templates.get_scene(payload.scene_id)
    if hairstyle is None or scene is None:
        raise HTTPException(status_code=400, detail="Invalid hairstyle or scene template.")

    try:
        settings = get_settings()
        if payload.generator_backend == settings.image_generator_backend:
            selected_generator = request.app.state.generator
        else:
            selected_generator = build_generator(payload.generator_backend)
        prompt = templates.build_job_prompt_payload(
            hairstyle,
            scene,
            generator_backend=payload.generator_backend,
            aspect_ratio=payload.aspect_ratio,
            resolution=payload.resolution,
            seed_source=f"{payload.upload_id}:{payload.hairstyle_id}:{payload.scene_id}",
        )
    except (ValueError, ImageGenerationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = repository.create_job(
        user_id=current_user["id"],
        upload_id=payload.upload_id,
        hairstyle_id=payload.hairstyle_id,
        scene_id=payload.scene_id,
        prompt=prompt,
        model_name=selected_generator.model_name,
    )
    request.app.state.job_worker.enqueue(job["id"])
    return _job_response(request, job)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> JobResponse:
    retention.purge_expired_media()
    job = repository.get_job_for_user(job_id, current_user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _job_response(request, job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
) -> None:
    deleted = repository.delete_job_for_user(job_id, current_user["id"])
    if deleted is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    storage.delete_result_bundle(job_id)

    upload = repository.get_upload(deleted["upload_id"])
    if upload is not None and repository.count_jobs_for_upload(deleted["upload_id"]) == 0:
        storage.delete_media_object(upload.get("stored_path"))
        repository.delete_upload(deleted["upload_id"])
