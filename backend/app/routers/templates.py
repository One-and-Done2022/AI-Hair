from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.schemas import GenerationBackendOption, TemplateCatalogResponse, TemplateItem
from app.services import templates


router = APIRouter(prefix="/templates", tags=["templates"])


def _absolute_cover_url(request: Request, category: str, template_id: str) -> str:
    base_url = str(
        request.url_for("template_cover", category=category, template_id=template_id)
    )
    return f"{base_url}?v={templates.TEMPLATE_COVER_VERSION}"


@router.get("", response_model=TemplateCatalogResponse)
def list_templates(request: Request) -> TemplateCatalogResponse:
    hairstyles = [
        TemplateItem(
            id=item["id"],
            name=item["name"],
            description=item["description"],
            cover_url=_absolute_cover_url(request, "hairstyles", item["id"]),
            gender=item.get("gender"),
            gender_label=item.get("gender_label"),
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
            cover_url=_absolute_cover_url(request, "scenes", item["id"]),
            gender=item.get("gender"),
            gender_label=item.get("gender_label"),
            style_line=item.get("style_line"),
            style_line_label=item.get("style_line_label"),
            tags=item.get("tags", []),
        )
        for item in templates.SCENES
    ]
    generation_backends = [
        GenerationBackendOption(**item)
        for item in templates.get_generation_backend_catalog()
    ]
    return TemplateCatalogResponse(
        hairstyles=hairstyles,
        scenes=scenes,
        generation_backends=generation_backends,
    )


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
