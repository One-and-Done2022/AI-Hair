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
    detected_hair_color: "UploadHairColorEstimate | None" = None


class TemplateItem(BaseModel):
    id: str
    name: str
    description: str
    cover_url: str
    gender: str | None = None
    gender_label: str | None = None
    category_key: str | None = None
    category_label: str | None = None
    style_line: str | None = None
    style_line_label: str | None = None
    tags: list[str] = Field(default_factory=list)


class MaleHairstylePresetItem(TemplateItem):
    preset_id: str
    display_group: str | None = None
    display_group_key: str | None = None
    structure_id: str | None = None
    modifier_ids: list[str] = Field(default_factory=list)
    technique_ids: list[str] = Field(default_factory=list)
    source_hairstyle_id: str | None = None


class HairColorTechniqueOption(BaseModel):
    id: str
    label: str
    description: str


class HairColorOption(BaseModel):
    id: str
    label: str
    hex: str
    description: str
    allowed_techniques: list[str] = Field(default_factory=list)
    default_technique: str


class ProfessionalHairColorSeriesOption(BaseModel):
    id: str
    label: str
    description: str
    brand: str
    option_count: int
    recommended_option_count: int
    cover_hex: str | None = None
    is_recommended_for_generation: bool = True


class ProfessionalHairColorOption(BaseModel):
    id: str
    brand: str
    series_name: str
    series_type: str
    series_description: str
    code: str
    label: str
    depth_prefix: str
    depth_level: int | None = None
    tone_primary: str | None = None
    tone_secondary: str | None = None
    visual_note: str
    hex_estimate: str
    rgb_estimate: str | None = None
    keywords: list[str] = Field(default_factory=list)
    mapped_tone_id: str
    mapped_tone_label: str | None = None
    mapped_technique_ids: list[str] = Field(default_factory=list)
    mapped_technique_labels: list[str] = Field(default_factory=list)
    mapped_temperature: str | None = None
    mapped_depth_bucket: str | None = None
    prompt_alias: str | None = None
    is_recommended_for_generation: bool = True


class TemplateCatalogResponse(BaseModel):
    hairstyles: list[TemplateItem]
    hairstyle_presets_male: list[MaleHairstylePresetItem] = Field(default_factory=list)
    scenes: list[TemplateItem]
    hair_colors: list[HairColorOption] = Field(default_factory=list)
    hair_color_techniques: list[HairColorTechniqueOption] = Field(default_factory=list)
    hair_color_professional_series: list[ProfessionalHairColorSeriesOption] = Field(default_factory=list)
    hair_color_professional_options: list[ProfessionalHairColorOption] = Field(default_factory=list)
    generation_backends: list["GenerationBackendOption"] = Field(default_factory=list)


class ShowcaseItem(BaseModel):
    id: str
    title: str
    summary: str
    cover_url: str
    hairstyle_id: str
    hairstyle_name: str
    hairstyle_cover_url: str
    scene_id: str
    scene_name: str
    scene_cover_url: str
    generator_backend: str
    aspect_ratio: str
    resolution: str | None = None


class ShowcaseResponse(BaseModel):
    items: list[ShowcaseItem] = Field(default_factory=list)


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


class UploadHairColorEstimate(BaseModel):
    tone_id: str
    label: str
    confidence: float
    sample_hex: str | None = None


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
    makeup: str
    outfit: str
    styling_constraints: str
    scene_constraints: str


class SceneLightingProfile(BaseModel):
    lightDirection: str
    lightQuality: str
    colorTemperature: str
    contrastLevel: str
    shadowDensity: str
    hairHighlightMode: str
    skinRendering: str
    exposureBias: str
    practicalLightsAllowed: bool = False


class SceneSampleImageIds(BaseModel):
    female: list[str] = Field(default_factory=list)
    male: list[str] = Field(default_factory=list)


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
    lightingProfile: SceneLightingProfile
    styleMood: str
    detailTags: list[str] = Field(default_factory=list)
    expressions: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    outfitHints: list[str] = Field(default_factory=list)
    outfitPalette: list[str] = Field(default_factory=list)
    outfitMaterials: list[str] = Field(default_factory=list)
    outfitShapes: list[str] = Field(default_factory=list)
    outfitAvoids: list[str] = Field(default_factory=list)
    pairingAdvice: list[str] = Field(default_factory=list)
    shotAdvice: str
    constraints: list[str] = Field(default_factory=list)
    controlProfile: SceneControlProfile
    sampleImageIds: SceneSampleImageIds
    referenceNotes: str
    referenceSourceIds: list[str] = Field(default_factory=list)


class SceneUnderstandingResponse(BaseModel):
    upload_id: str
    model_name: str
    subject_gender: Literal["male", "female", "unknown"] = "unknown"
    blocks: SceneUnderstandingBlocks
    scene_draft: SceneDraft


class JobCreateRequest(BaseModel):
    upload_id: str = Field(min_length=1)
    hairstyle_id: str | None = Field(default=None, min_length=1)
    preset_id: str | None = Field(default=None, min_length=1)
    scene_id: str = Field(min_length=1)
    generator_backend: Literal["basic", "premium"] = "premium"
    aspect_ratio: str | None = None
    resolution: str | None = None
    hair_color_tone: str | None = None
    hair_color_technique: str | None = None
    hair_color_professional_id: str | None = None


class JobResponse(BaseModel):
    job_id: str
    status: Literal[
        "pending",
        "hair_generating",
        "hair_ready",
        "scene_generating",
        "scene_partial",
        "succeeded",
        "failed",
    ]
    upload_url: str | None = None
    hair_preview_url: str | None = None
    result_image_url: str | None = None
    result_image_urls: list[str] = Field(default_factory=list)
    completed_scene_count: int = 0
    media_expired: bool = False
    media_expires_at: str
    hairstyle_id: str
    hairstyle_name: str
    preset_id: str | None = None
    preset_name: str | None = None
    scene_id: str
    scene_name: str
    generator_backend: str | None = None
    aspect_ratio: str | None = None
    resolution: str | None = None
    hair_color_tone: str | None = None
    hair_color_tone_label: str | None = None
    hair_color_technique: str | None = None
    hair_color_technique_label: str | None = None
    hair_color_professional_id: str | None = None
    hair_color_professional_brand: str | None = None
    hair_color_professional_series: str | None = None
    hair_color_professional_series_label: str | None = None
    hair_color_professional_code: str | None = None
    hair_color_professional_note: str | None = None
    hair_color_professional_hex_estimate: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class HistoryResponse(BaseModel):
    items: list[JobResponse]


class AdminSessionLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)


class AdminSessionResponse(BaseModel):
    configured: bool
    authenticated: bool
    username: str | None = None
    expires_at: str | None = None


class AdminHistoryItem(JobResponse):
    user_id: int
    nickname: str
    model_name: str
    upload_id: str
    upload_path: str | None = None
    upload_absolute_path: str | None = None
    hair_preview_path: str | None = None
    hair_preview_absolute_path: str | None = None
    result_dir_path: str | None = None
    result_dir_absolute_path: str | None = None
    result_image_paths: list[str] = Field(default_factory=list)
    result_image_absolute_paths: list[str] = Field(default_factory=list)


class AdminHistoryResponse(BaseModel):
    page: int
    page_size: int
    total: int
    storage_root: str
    items: list[AdminHistoryItem] = Field(default_factory=list)


class MeResponse(BaseModel):
    user_id: int
    nickname: str
    member_status: str
    remaining_quota: int
    monthly_used: int
    free_quota_total: int
    free_quota_used: int
    free_remaining: int
    paid_remaining: int
    total_remaining: int
    total_jobs: int
    completed_jobs: int
    processing_jobs: int
    provider_alerts: list[str] = Field(default_factory=list)
    created_at: str


class PurchaseCatalogItem(BaseModel):
    product_id: str
    name: str
    description: str
    price_cents: int
    price_label: str
    generation_count: int
    is_default: bool = True


class PurchaseCatalogResponse(BaseModel):
    items: list[PurchaseCatalogItem] = Field(default_factory=list)


class PurchaseOrderCreateRequest(BaseModel):
    product_id: str = Field(min_length=1)


class PurchaseOrderResponse(BaseModel):
    order_id: str
    product_id: str
    product_name: str
    quantity: int
    unit_price_cents: int
    amount_cents: int
    amount_label: str
    status: Literal["pending", "payment_prepared", "confirmed"]
    wechat_prepay_id: str | None = None
    wechat_transaction_id: str | None = None
    created_at: str
    updated_at: str
    confirmed_at: str | None = None


class WechatPaymentParams(BaseModel):
    timeStamp: str
    nonceStr: str
    package: str
    signType: Literal["RSA"] = "RSA"
    paySign: str


class PurchasePaymentPrepareResponse(BaseModel):
    order: PurchaseOrderResponse
    payment: WechatPaymentParams

class ProviderAdminAlertRecord(BaseModel):
    alert_id: str
    message: str
    updated_at: str | None = None


class ProviderAdminProbeStatus(BaseModel):
    checked_at: str | None = None
    reachable: bool | None = None
    healthy: bool | None = None
    status_code: int | None = None
    detail: str | None = None


class ProviderAdminTestResult(BaseModel):
    checked_at: str
    success: bool
    duration_seconds: float
    error_code: str | None = None
    error_message: str | None = None
    preview_url: str | None = None
    summary: str | None = None


class ProviderAdminEntryItem(BaseModel):
    entry_id: str
    entry_label: str
    priority: int
    enabled: bool
    protocol: str
    base_url: str
    endpoint: str
    model_name: str
    credential_label: str | None = None
    console_url: str | None = None
    docs_url: str | None = None
    status: str
    status_label: str
    note: str | None = None
    probe: ProviderAdminProbeStatus | None = None
    last_test: ProviderAdminTestResult | None = None


class ProviderAdminGroupItem(BaseModel):
    provider_id: str
    provider_label: str
    category: str
    runtime_policy: str
    runtime_note: str | None = None
    supports_reorder: bool
    status: str
    status_label: str
    updated_at: str | None = None
    alerts: list[ProviderAdminAlertRecord] = Field(default_factory=list)
    entries: list[ProviderAdminEntryItem] = Field(default_factory=list)


class ProviderAdminDashboardSummary(BaseModel):
    provider_count: int
    enabled_provider_count: int
    entry_count: int
    enabled_entry_count: int
    healthy_entry_count: int
    degraded_entry_count: int
    unavailable_entry_count: int
    disabled_entry_count: int
    unknown_entry_count: int
    updated_at: str | None = None


class ProviderAdminDashboardResponse(BaseModel):
    updated_at: str | None = None
    connectivity_updated_at: str | None = None
    summary: ProviderAdminDashboardSummary
    providers: list[ProviderAdminGroupItem] = Field(default_factory=list)
    alerts: list[ProviderAdminAlertRecord] = Field(default_factory=list)


class ProviderAdminOrderItem(BaseModel):
    entry_id: str
    enabled: bool = True


class ProviderAdminOrderRequest(BaseModel):
    items: list[ProviderAdminOrderItem] = Field(default_factory=list)


class ProviderAdminTestRequest(BaseModel):
    entry_id: str
    prompt: str | None = None
    aspect_ratio: Literal["1:1", "3:4", "4:3", "9:16", "16:9"] = "3:4"
    resolution: Literal["1K", "2K", "4K"] = "2K"


class ProviderAdminRouteTestResult(ProviderAdminTestResult):
    pass


class ProviderAdminProfileItem(BaseModel):
    profile_id: str
    profile_label: str
    priority: int
    enabled: bool
    protocol: str
    base_url: str
    endpoint: str
    model_name: str
    probe: ProviderAdminProbeStatus | None = None
    last_test: ProviderAdminRouteTestResult | None = None


class NanoBananaProAdminResponse(BaseModel):
    provider_name: str
    updated_at: str | None = None
    connectivity_updated_at: str | None = None
    alerts: list[str] = Field(default_factory=list)
    profiles: list[ProviderAdminProfileItem] = Field(default_factory=list)


class ProviderAdminRouteOrderItem(BaseModel):
    profile_id: str
    enabled: bool = True


class ProviderAdminRouteOrderRequest(BaseModel):
    items: list[ProviderAdminRouteOrderItem] = Field(default_factory=list)


class ProviderAdminRouteTestRequest(BaseModel):
    profile_id: str
    prompt: str | None = None
    aspect_ratio: Literal["1:1", "3:4", "4:3", "9:16", "16:9"] = "3:4"
    resolution: Literal["1K", "2K", "4K"] = "2K"
