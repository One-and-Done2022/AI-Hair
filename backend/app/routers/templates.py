from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.exc import SQLAlchemyError

from app.routers.jobs import _job_response
from app.services import hair_color_reference

from app.schemas import (
    GenerationBackendOption,
    HairColorOption,
    HairColorTechniqueOption,
    MaleHairstylePresetItem,
    ProfessionalHairColorOption,
    ProfessionalHairColorSeriesOption,
    ShowcaseItem,
    ShowcaseResponse,
    TemplateCatalogResponse,
    TemplateItem,
)
from app.services import repository, storage, templates


router = APIRouter(prefix="/templates", tags=["templates"])


def _absolute_cover_url(request: Request, category: str, template_id: str) -> str:
    base_url = str(
        request.url_for("template_cover", category=category, template_id=template_id)
    )
    return f"{base_url}?v={templates.TEMPLATE_COVER_VERSION}"


def _real_cover_url(request: Request, item: dict) -> str | None:
    object_key = str(item.get("cover_image_path") or "").strip()
    if not object_key:
        return None
    base_url = str(request.base_url).rstrip("/")
    resolved = storage.media_url(object_key, base_url=base_url)
    if not resolved:
        return None
    version = str(item.get("cover_image_updated_at") or templates.TEMPLATE_COVER_VERSION).strip()
    if not version:
        return resolved
    normalized = "".join(ch for ch in version if ch.isalnum())[:24]
    if not normalized:
        return resolved
    return f"{resolved}?v={normalized}"


def _build_showcase_summary(item, descriptor: dict | None) -> str:
    if descriptor and str(descriptor.get("summary") or "").strip():
        return str(descriptor["summary"]).strip()
    if item.hair_color_professional_code:
        return f"{item.hair_color_professional_code} · {item.hair_color_professional_note or item.hair_color_tone_label or '完整历史成片'}"
    if item.hair_color_tone_label and item.hair_color_technique_label:
        return f"{item.hair_color_tone_label} · {item.hair_color_technique_label}"
    if item.hair_color_tone_label:
        return item.hair_color_tone_label
    return "服务端固定保留的历史成片，可一键套用"


def _build_fixed_historical_showcases(request: Request) -> list[ShowcaseItem]:
    fixed_entries = templates.get_fixed_showcase_jobs()
    if not fixed_entries:
        return []
    try:
        candidate_jobs = repository.list_jobs_by_ids(
            [entry["job_id"] for entry in fixed_entries if entry.get("job_id")]
        )
    except SQLAlchemyError:
        return []
    if not candidate_jobs:
        return []

    candidate_job_map = {str(job["id"]): job for job in candidate_jobs}
    items: list[ShowcaseItem] = []
    for fixed_entry in fixed_entries:
        job = candidate_job_map.get(str(fixed_entry.get("job_id") or "").strip())
        if job is None or str(job.get("status") or "").strip() != "succeeded":
            continue
        item = _job_response(request, job)
        if not (item.result_image_url or item.hair_preview_url):
            continue
        hairstyle = templates.get_hairstyle(item.hairstyle_id)
        scene = templates.get_scene(item.scene_id)
        if hairstyle is None or scene is None:
            continue
        descriptor = templates.find_curated_showcase_descriptor(
            preset_id=item.preset_id,
            hairstyle_id=item.hairstyle_id,
            scene_id=item.scene_id,
        )
        hairstyle_cover_url = _real_cover_url(request, hairstyle) or _absolute_cover_url(
            request,
            "hairstyles",
            hairstyle["id"],
        )
        scene_cover_url = _real_cover_url(request, scene) or _absolute_cover_url(
            request,
            "scenes",
            scene["id"],
        )
        items.append(
            ShowcaseItem(
                id=item.job_id,
                job_id=item.job_id,
                title=(
                    str(fixed_entry.get("title") or "").strip()
                    or (
                        str(descriptor.get("title") or "").strip()
                        if descriptor
                        else f"{item.hairstyle_name} · {item.scene_name}"
                    )
                ),
                summary=(
                    str(fixed_entry.get("summary") or "").strip()
                    or _build_showcase_summary(item, descriptor)
                ),
                cover_url=item.result_image_url or item.hair_preview_url or scene_cover_url,
                hairstyle_id=item.hairstyle_id,
                hairstyle_name=item.hairstyle_name,
                hairstyle_cover_url=hairstyle_cover_url,
                preset_id=item.preset_id,
                preset_name=item.preset_name,
                scene_id=item.scene_id,
                scene_name=item.scene_name,
                scene_cover_url=scene_cover_url,
                generator_backend=item.generator_backend or templates.DEFAULT_GENERATOR_BACKEND,
                aspect_ratio=item.aspect_ratio or templates.DEFAULT_ASPECT_RATIO,
                resolution=item.resolution or templates.DEFAULT_RESOLUTION,
                hair_color_selection_mode=(
                    "professional" if item.hair_color_professional_id else "basic"
                ),
                hair_color_tone=item.hair_color_tone,
                hair_color_tone_label=item.hair_color_tone_label,
                hair_color_technique=item.hair_color_technique,
                hair_color_technique_label=item.hair_color_technique_label,
                hair_color_professional_id=item.hair_color_professional_id,
                hair_color_professional_brand=item.hair_color_professional_brand,
                hair_color_professional_series=item.hair_color_professional_series,
                hair_color_professional_series_label=item.hair_color_professional_series_label,
                hair_color_professional_code=item.hair_color_professional_code,
                hair_color_professional_note=item.hair_color_professional_note,
                hair_color_professional_hex_estimate=item.hair_color_professional_hex_estimate,
                created_at=item.created_at,
            )
        )
    return items


@router.get("", response_model=TemplateCatalogResponse)
def list_templates(request: Request) -> TemplateCatalogResponse:
    hairstyles = [
        TemplateItem(
            id=item["id"],
            name=item["name"],
            description=item["description"],
            cover_url=_real_cover_url(request, item)
            or _absolute_cover_url(request, "hairstyles", item["id"]),
            gender=item.get("gender"),
            gender_label=item.get("gender_label"),
            category_key=item.get("category_key"),
            category_label=item.get("category_label"),
            style_line=item.get("style_line"),
            style_line_label=item.get("style_line_label"),
            tags=item.get("tags", []),
        )
        for item in templates.HAIRSTYLES
    ]
    hairstyle_presets_male = [
        MaleHairstylePresetItem(
            id=item["id"],
            preset_id=item.get("preset_id") or item["id"],
            name=item["name"],
            description=item["description"],
            cover_url=_real_cover_url(request, item)
            or _absolute_cover_url(request, "male-hairstyle-presets", item["id"]),
            gender=item.get("gender"),
            gender_label=item.get("gender_label"),
            category_key=item.get("category_key"),
            category_label=item.get("category_label"),
            style_line=item.get("style_line"),
            style_line_label=item.get("style_line_label"),
            tags=item.get("tags", []),
            display_group=item.get("display_group"),
            display_group_key=item.get("display_group_key"),
            structure_id=item.get("structure_id"),
            modifier_ids=item.get("modifier_ids", []),
            technique_ids=item.get("technique_ids", []),
            source_hairstyle_id=item.get("source_hairstyle_id") or None,
        )
        for item in templates.get_male_hairstyle_presets()
    ]
    scenes = [
        TemplateItem(
            id=item["id"],
            name=item["name"],
            description=item["description"],
            cover_url=_real_cover_url(request, item)
            or _absolute_cover_url(request, "scenes", item["id"]),
            gender=item.get("gender"),
            gender_label=item.get("gender_label"),
            style_line=item.get("style_line"),
            style_line_label=item.get("style_line_label"),
            tags=item.get("tags", []),
        )
        for item in templates.SCENES
    ]
    hair_colors = [HairColorOption(**item) for item in templates.get_hair_color_catalog()]
    hair_color_techniques = [
        HairColorTechniqueOption(**item)
        for item in templates.get_hair_color_technique_catalog()
    ]
    hair_color_professional_series = [
        ProfessionalHairColorSeriesOption(**item)
        for item in templates.get_professional_hair_color_series_catalog()
    ]
    hair_color_professional_options = [
        ProfessionalHairColorOption(**item)
        for item in templates.get_professional_hair_color_catalog()
    ]
    generation_backends = [
        GenerationBackendOption(**item)
        for item in templates.get_generation_backend_catalog()
    ]
    return TemplateCatalogResponse(
        hairstyles=hairstyles,
        hairstyle_presets_male=hairstyle_presets_male,
        scenes=scenes,
        hair_colors=hair_colors,
        hair_color_techniques=hair_color_techniques,
        hair_color_professional_series=hair_color_professional_series,
        hair_color_professional_options=hair_color_professional_options,
        generation_backends=generation_backends,
    )


@router.get("/showcases", response_model=ShowcaseResponse)
def list_showcases(request: Request) -> ShowcaseResponse:
    historical_items = _build_fixed_historical_showcases(request)
    if historical_items:
        return ShowcaseResponse(items=historical_items)

    items: list[ShowcaseItem] = []
    for showcase in templates.get_curated_showcases():
        hairstyle = templates.get_hairstyle(showcase["hairstyle_id"])
        scene = templates.get_scene(showcase["scene_id"])
        if hairstyle is None or scene is None:
            continue
        hairstyle_cover_url = _real_cover_url(request, hairstyle) or _absolute_cover_url(
            request,
            "hairstyles",
            hairstyle["id"],
        )
        scene_cover_url = _real_cover_url(request, scene) or _absolute_cover_url(
            request,
            "scenes",
            scene["id"],
        )
        items.append(
            ShowcaseItem(
                id=showcase["id"],
                job_id=None,
                title=showcase["title"],
                summary=showcase["summary"],
                cover_url=scene_cover_url,
                hairstyle_id=hairstyle["id"],
                hairstyle_name=hairstyle["name"],
                hairstyle_cover_url=hairstyle_cover_url,
                preset_id=showcase.get("preset_id"),
                preset_name=showcase.get("preset_name"),
                scene_id=scene["id"],
                scene_name=scene["name"],
                scene_cover_url=scene_cover_url,
                generator_backend=showcase["generator_backend"],
                aspect_ratio=showcase["aspect_ratio"],
                resolution=showcase.get("resolution"),
                hair_color_selection_mode=showcase.get("hair_color_selection_mode"),
                hair_color_tone=showcase.get("hair_color_tone"),
                hair_color_tone_label=showcase.get("hair_color_tone_label"),
                hair_color_technique=showcase.get("hair_color_technique"),
                hair_color_technique_label=showcase.get("hair_color_technique_label"),
                hair_color_professional_id=showcase.get("hair_color_professional_id"),
                hair_color_professional_brand=showcase.get("hair_color_professional_brand"),
                hair_color_professional_series=showcase.get("hair_color_professional_series"),
                hair_color_professional_series_label=showcase.get("hair_color_professional_series_label"),
                hair_color_professional_code=showcase.get("hair_color_professional_code"),
                hair_color_professional_note=showcase.get("hair_color_professional_note"),
                hair_color_professional_hex_estimate=showcase.get("hair_color_professional_hex_estimate"),
                created_at=showcase.get("created_at"),
            )
        )
    return ShowcaseResponse(items=items)


@router.get("/hair-color-reference.pdf")
def professional_hair_color_reference_pdf() -> Response:
    object_key = hair_color_reference.ensure_professional_hair_color_reference_pdf_cached()
    return Response(
        content=storage.read_file_bytes(object_key),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{hair_color_reference.REFERENCE_PDF_FILENAME}"',
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.get("/hair-color-reference-link")
def professional_hair_color_reference_link(request: Request) -> dict[str, str]:
    base_url = str(request.base_url).rstrip("/")
    static_url = hair_color_reference.get_professional_hair_color_reference_static_url(
        base_url=base_url,
    )
    api_url = str(request.url_for("professional_hair_color_reference_pdf"))
    return {
        "filename": hair_color_reference.REFERENCE_PDF_FILENAME,
        "url": static_url,
        "static_url": static_url,
        "api_url": api_url,
    }


@router.get("/covers/{category}/{template_id}.svg", name="template_cover")
def template_cover(category: str, template_id: str) -> Response:
    if category == "hairstyles":
        template = templates.get_hairstyle(template_id)
    elif category == "male-hairstyle-presets":
        template = templates.get_male_hairstyle_preset(template_id)
    elif category == "scenes":
        template = templates.get_scene(template_id)
    else:
        template = None

    if template is None:
        raise HTTPException(status_code=404, detail="Template not found.")

    return Response(
        content=templates.template_cover_svg(category, template),
        media_type="image/svg+xml",
    )
