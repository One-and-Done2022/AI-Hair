from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.schemas import (
    HairColorOption,
    HairColorTechniqueOption,
    GenerationBackendOption,
    ShowcaseItem,
    ShowcaseResponse,
    TemplateCatalogResponse,
    TemplateItem,
)
from app.services import storage, templates


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
    hair_colors = [
        HairColorOption(**item)
        for item in templates.get_hair_color_catalog()
    ]
    hair_color_techniques = [
        HairColorTechniqueOption(**item)
        for item in templates.get_hair_color_technique_catalog()
    ]
    generation_backends = [
        GenerationBackendOption(**item)
        for item in templates.get_generation_backend_catalog()
    ]
    return TemplateCatalogResponse(
        hairstyles=hairstyles,
        scenes=scenes,
        hair_colors=hair_colors,
        hair_color_techniques=hair_color_techniques,
        generation_backends=generation_backends,
    )


@router.get("/showcases", response_model=ShowcaseResponse)
def list_showcases(request: Request) -> ShowcaseResponse:
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
                title=showcase["title"],
                summary=showcase["summary"],
                cover_url=scene_cover_url,
                hairstyle_id=hairstyle["id"],
                hairstyle_name=hairstyle["name"],
                hairstyle_cover_url=hairstyle_cover_url,
                scene_id=scene["id"],
                scene_name=scene["name"],
                scene_cover_url=scene_cover_url,
                generator_backend=showcase["generator_backend"],
                aspect_ratio=showcase["aspect_ratio"],
                resolution=showcase.get("resolution"),
            )
        )
    return ShowcaseResponse(items=items)


@router.get("/covers/{category}/{template_id}.svg", name="template_cover")
def template_cover(category: str, template_id: str) -> Response:
    if category == "hairstyles":
        template = templates.get_hairstyle(template_id)
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
