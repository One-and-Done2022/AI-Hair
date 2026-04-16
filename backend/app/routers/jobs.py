from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies import get_current_user
from app.schemas import JobCreateRequest, JobResponse
from app.services.generation import ImageGenerationError
from app.services import hair_color, repository, retention, storage, templates


router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_response(request: Request, job: dict) -> JobResponse:
    hairstyle = templates.get_hairstyle(job["hairstyle_id"])
    scene = templates.get_scene(job["scene_id"])
    prompt_payload = templates.parse_job_prompt_payload(job.get("prompt") or "")
    template_selection = prompt_payload.get("template_selection") or {}
    preset_id = str(template_selection.get("preset_id") or "").strip() or None
    preset_name = str(template_selection.get("preset_name") or "").strip() or None
    resolved_hairstyle_name = str(template_selection.get("resolved_hairstyle_name") or "").strip() or None
    upload = repository.get_upload(job["upload_id"])
    base_url = str(request.base_url).rstrip("/")
    upload_url = (
        storage.media_url(upload["stored_path"], base_url=base_url)
        if upload
        else None
    )
    hair_preview_path = storage.get_hair_preview_path(job["id"])
    hair_preview_url = (
        storage.media_url(hair_preview_path, base_url=base_url)
        if hair_preview_path
        else None
    )
    scene_paths = storage.list_scene_results(job["id"])
    result_image_urls: list[str] = []
    for path in scene_paths:
        resolved = storage.media_url(path, base_url=base_url)
        if resolved:
            result_image_urls.append(resolved)
    result_image_url = result_image_urls[0] if result_image_urls else hair_preview_url
    media_expires_at = retention.media_expires_at(job["created_at"])
    media_expired = retention.is_media_expired(job["created_at"])
    hair_color_selection = prompt_payload.get("hair_color_selection") or {}
    hair_color_tone = str(hair_color_selection.get("tone_id") or "").strip() or None
    hair_color_tone_label = str(hair_color_selection.get("tone_label") or "").strip() or None
    hair_color_technique = str(hair_color_selection.get("technique_id") or "").strip() or None
    hair_color_technique_label = (
        str(hair_color_selection.get("technique_label") or "").strip() or None
    )
    hair_color_professional_id = str(hair_color_selection.get("professional_id") or "").strip() or None
    hair_color_professional_brand = str(hair_color_selection.get("professional_brand") or "").strip() or None
    hair_color_professional_series = str(hair_color_selection.get("professional_series") or "").strip() or None
    hair_color_professional_series_label = (
        str(hair_color_selection.get("professional_series_label") or "").strip() or None
    )
    hair_color_professional_code = str(hair_color_selection.get("professional_code") or "").strip() or None
    hair_color_professional_note = str(hair_color_selection.get("professional_note") or "").strip() or None
    hair_color_professional_hex_estimate = (
        str(hair_color_selection.get("professional_hex_estimate") or "").strip() or None
    )
    return JobResponse(
        job_id=job["id"],
        status=job["status"],
        upload_url=upload_url,
        hair_preview_url=hair_preview_url,
        result_image_url=result_image_url,
        result_image_urls=result_image_urls,
        completed_scene_count=len(result_image_urls),
        media_expired=media_expired,
        media_expires_at=media_expires_at,
        hairstyle_id=job["hairstyle_id"],
        hairstyle_name=preset_name or (hairstyle["name"] if hairstyle else (resolved_hairstyle_name or job["hairstyle_id"])),
        preset_id=preset_id,
        preset_name=preset_name,
        scene_id=job["scene_id"],
        scene_name=scene["name"] if scene else job["scene_id"],
        generator_backend=prompt_payload["output_options"]["generator_backend"],
        aspect_ratio=prompt_payload["output_options"]["aspect_ratio"],
        resolution=prompt_payload["output_options"]["resolution"],
        hair_color_tone=hair_color_tone,
        hair_color_tone_label=hair_color_tone_label,
        hair_color_technique=hair_color_technique,
        hair_color_technique_label=hair_color_technique_label,
        hair_color_professional_id=hair_color_professional_id,
        hair_color_professional_brand=hair_color_professional_brand,
        hair_color_professional_series=hair_color_professional_series,
        hair_color_professional_series_label=hair_color_professional_series_label,
        hair_color_professional_code=hair_color_professional_code,
        hair_color_professional_note=hair_color_professional_note,
        hair_color_professional_hex_estimate=hair_color_professional_hex_estimate,
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
    if not str(upload.get("stored_path") or "").strip():
        raise HTTPException(
            status_code=400,
            detail={
                "code": "upload_expired",
                "message": "上传图片已失效，请重新上传照片。",
            },
        )

    selected_hairstyle_id = payload.preset_id or payload.hairstyle_id
    if not selected_hairstyle_id:
        raise HTTPException(status_code=400, detail="Missing hairstyle_id or preset_id.")

    if payload.preset_id:
        hairstyle = templates.resolve_male_hairstyle_preset(payload.preset_id)
    else:
        hairstyle = templates.get_hairstyle(payload.hairstyle_id or "")
    scene = templates.get_scene(payload.scene_id)
    if hairstyle is None or scene is None:
        raise HTTPException(status_code=400, detail="Invalid hairstyle or scene template.")

    stored_hairstyle_id = (
        str(hairstyle.get("source_hairstyle_id") or "").strip()
        or str(hairstyle.get("resolved_hairstyle_id") or "").strip()
        or str(hairstyle.get("id") or "").strip()
    )

    try:
        generation_plan = templates.get_generation_plan(payload.generator_backend)
        if generation_plan is None:
            raise ValueError(f"Unsupported generator backend: {payload.generator_backend}")
        if not any(
            item["id"] == generation_plan["id"] and item["enabled"]
            for item in templates.get_generation_backend_catalog()
        ):
            raise ValueError("Selected generation plan is not currently available.")
        try:
            upload_bytes = storage.read_file_bytes(upload["stored_path"])
        except OSError as exc:
            raise ValueError("上传图片已失效，请重新上传照片。") from exc
        detected_hair_color_tone_id = None
        detected_hair_color = hair_color.estimate_hair_color(upload_bytes)
        if detected_hair_color is not None:
            detected_hair_color_tone_id = detected_hair_color.tone_id
        prompt = templates.build_job_prompt_payload(
            hairstyle,
            scene,
            generator_backend=payload.generator_backend,
            aspect_ratio=payload.aspect_ratio,
            resolution=payload.resolution,
            hair_color_tone_id=payload.hair_color_tone,
            hair_color_technique_id=payload.hair_color_technique,
            hair_color_professional_id=payload.hair_color_professional_id,
            detected_hair_color_tone_id=detected_hair_color_tone_id,
            seed_source=f"{payload.upload_id}:{selected_hairstyle_id}:{payload.scene_id}",
        )
    except (ValueError, ImageGenerationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        job = repository.create_job_consuming_quota(
            user_id=current_user["id"],
            upload_id=payload.upload_id,
            hairstyle_id=stored_hairstyle_id,
            scene_id=payload.scene_id,
            prompt=prompt,
            model_name=f"{generation_plan['hair_backend']}+{generation_plan['scene_model_name']}",
        )
    except repository.QuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "quota_exhausted",
                "message": "免费次数已用完，请购买 1 次生成包后继续。",
                "quota": exc.quota,
            },
        ) from exc
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
