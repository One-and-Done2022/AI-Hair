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
    generation_backends: list["GenerationBackendOption"] = Field(default_factory=list)


class GenerationBackendOption(BaseModel):
    id: str
    name: str
    description: str
    enabled: bool
    supports_reference_image: bool = True
    aspect_ratios: list[str] = Field(default_factory=list)
    resolutions: list[str] = Field(default_factory=list)
    default_aspect_ratio: str
    default_resolution: str | None = None


class RecommendationFaceShape(BaseModel):
    id: str
    label: str


class RecommendationItem(BaseModel):
    id: str
    name: str
    score: int
    reasons: list[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    upload_id: str
    face_shape: RecommendationFaceShape
    feature_tags: list[str] = Field(default_factory=list)
    summary: str
    measurements: dict[str, float] = Field(default_factory=dict)
    recommended_hairstyles: dict[str, list[RecommendationItem]] = Field(default_factory=dict)
    recommended_scenes: list[RecommendationItem] = Field(default_factory=list)


class SceneUnderstandingRequest(BaseModel):
    upload_id: str = Field(min_length=1)
    scene_id: str | None = None
    title: str | None = None
    style_line: Literal["realistic_editorial", "fashion_editorial"] | None = None
    detail_tags: list[str] = Field(default_factory=list)
    pairing_advice: list[str] = Field(default_factory=list)
    reference_source_ids: list[str] = Field(default_factory=list)
    reference_notes: str | None = None


class SceneUnderstandingBlocks(BaseModel):
    shot: str
    scene_environment: str
    scene_lighting: str
    scene_mood: str
    expression: str
    subject_action: str
    outfit: str
    scene_constraints: str


class SceneControlProfile(BaseModel):
    windLevel: str
    humidityLook: str
    backgroundComplexity: str
    lightingHardness: str
    mirrorRisk: str
    compatibleHairstyleTags: list[str] = Field(default_factory=list)
    recommendedHairstyleIds: list[str] = Field(default_factory=list)


class SceneDraft(BaseModel):
    id: str
    title: str
    styleLine: str
    summary: str
    environment: str
    lighting: str
    styleMood: str
    detailTags: list[str] = Field(default_factory=list)
    expressions: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    outfitHints: list[str] = Field(default_factory=list)
    pairingAdvice: list[str] = Field(default_factory=list)
    shotAdvice: str
    constraints: list[str] = Field(default_factory=list)
    controlProfile: SceneControlProfile
    referenceNotes: str
    referenceSourceIds: list[str] = Field(default_factory=list)


class SceneUnderstandingResponse(BaseModel):
    upload_id: str
    model_name: str
    blocks: SceneUnderstandingBlocks
    scene_draft: SceneDraft


class JobCreateRequest(BaseModel):
    upload_id: str = Field(min_length=1)
    hairstyle_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    generator_backend: Literal[
        "seedream",
        "nano_banana_pro",
        "nano_banana_2",
        "sora_image",
    ] = "seedream"
    aspect_ratio: str | None = "3:4"
    resolution: str | None = "4K"


class JobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "processing", "preview_ready", "succeeded", "failed"]
    upload_url: str | None = None
    result_image_url: str | None = None
    result_image_urls: list[str] = Field(default_factory=list)
    media_expired: bool = False
    media_expires_at: str
    hairstyle_id: str
    hairstyle_name: str
    scene_id: str
    scene_name: str
    generator_backend: str | None = None
    aspect_ratio: str | None = None
    resolution: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class HistoryResponse(BaseModel):
    items: list[JobResponse]


class MeResponse(BaseModel):
    user_id: int
    nickname: str
    member_status: str
    remaining_quota: int
    monthly_used: int
    total_jobs: int
    completed_jobs: int
    processing_jobs: int
    created_at: str
