from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies import get_current_user
from app.schemas import JobCreateRequest, JobResponse
from app.services import repository, storage, templates


router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_response(request: Request, job: dict) -> JobResponse:
    hairstyle = templates.get_hairstyle(job["hairstyle_id"])
    scene = templates.get_scene(job["scene_id"])
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
    return JobResponse(
        job_id=job["id"],
        status=job["status"],
        upload_url=upload_url,
        result_image_url=result_image_url,
        result_image_urls=result_image_urls,
        hairstyle_id=job["hairstyle_id"],
        hairstyle_name=hairstyle["name"] if hairstyle else job["hairstyle_id"],
        scene_id=job["scene_id"],
        scene_name=scene["name"] if scene else job["scene_id"],
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

    prompt = templates.build_prompt(
        hairstyle,
        scene,
        seed_source=f"{payload.upload_id}:{payload.hairstyle_id}:{payload.scene_id}",
    )
    job = repository.create_job(
        user_id=current_user["id"],
        upload_id=payload.upload_id,
        hairstyle_id=payload.hairstyle_id,
        scene_id=payload.scene_id,
        prompt=prompt,
        model_name=request.app.state.generator.model_name,
    )
    request.app.state.job_worker.enqueue(job["id"])
    return _job_response(request, job)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> JobResponse:
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
