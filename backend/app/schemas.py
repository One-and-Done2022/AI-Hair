from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class AuthResponse(BaseModel):
    token: str
    user_id: int


class UploadResponse(BaseModel):
    upload_id: str
    upload_url: str
    width: int
    height: int


class TemplateItem(BaseModel):
    id: str
    name: str
    description: str
    cover_url: str
    gender: str | None = None
    gender_label: str | None = None
    style_line: str | None = None
    style_line_label: str | None = None
    tags: list[str] = Field(default_factory=list)


class TemplateCatalogResponse(BaseModel):
    hairstyles: list[TemplateItem]
    scenes: list[TemplateItem]


class JobCreateRequest(BaseModel):
    upload_id: str = Field(min_length=1)
    hairstyle_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)


class JobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "processing", "preview_ready", "succeeded", "failed"]
    upload_url: str | None = None
    result_image_url: str | None = None
    result_image_urls: list[str] = Field(default_factory=list)
    hairstyle_id: str
    hairstyle_name: str
    scene_id: str
    scene_name: str
    error_code: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class HistoryResponse(BaseModel):
    items: list[JobResponse]
