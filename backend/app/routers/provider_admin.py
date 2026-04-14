from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse

from app.config import ROOT_DIR, get_settings
from app.dependencies import get_current_admin
from app.schemas import (
    NanoBananaProAdminResponse,
    ProviderAdminAlertRecord,
    ProviderAdminDashboardResponse,
    ProviderAdminDashboardSummary,
    ProviderAdminEntryItem,
    ProviderAdminGroupItem,
    ProviderAdminOrderRequest,
    ProviderAdminProbeStatus,
    ProviderAdminProfileItem,
    ProviderAdminRouteOrderRequest,
    ProviderAdminRouteTestRequest,
    ProviderAdminRouteTestResult,
    ProviderAdminTestRequest,
    ProviderAdminTestResult,
)
from app.services import image_understanding, provider_alerts, provider_connectivity, provider_routing
from app.services.admin_auth import current_admin_from_request
from app.services.generation import (
    GenerationContext,
    ImageGenerationError,
    NanoBanana2Generator,
    NanoBananaProGenerator,
    SeedreamGenerator,
)


router = APIRouter(tags=["provider-admin"])
_PAGE_PATH = Path(__file__).resolve().parents[1] / "static" / "provider_admin.html"
_DEFAULT_TEST_PROMPT = (
    "保持人物面部和五官高度一致，男生前刺短发，清晨窗边自然软光，"
    "写实人像写真，肤质干净，画面克制，高级感，单人半身构图。"
)
_STATUS_LABELS = {
    "healthy": "正常",
    "degraded": "降级",
    "unavailable": "不可用",
    "disabled": "已停用",
    "unknown": "未知",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _resolve_test_source_image_path() -> Path:
    candidates = (
        ROOT_DIR / "assets" / "male.jpg",
        ROOT_DIR / "assets" / "male1.jpg",
        ROOT_DIR / "assets" / "female.jpg",
    )
    for path in candidates:
        if path.exists():
            return path
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="未找到可用的测试图片，请先准备 assets/male.jpg 或同类样图。",
    )


def _save_test_preview(image_bytes: bytes, entry_id: str) -> str | None:
    settings = get_settings()
    if not settings.uses_local_media:
        return None
    preview_dir = settings.storage_dir / "provider_admin_tests"
    preview_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{entry_id}-{uuid.uuid4().hex}.png"
    path = preview_dir / file_name
    path.write_bytes(image_bytes)
    return f"/media/provider_admin_tests/{file_name}"


def _normalize_provider_key(value: str | None) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _status_label(status_name: str) -> str:
    return _STATUS_LABELS.get(status_name, "未知")


def _probe_status_from_payload(payload: dict | None) -> ProviderAdminProbeStatus | None:
    if not isinstance(payload, dict):
        return None
    if not any(payload.get(key) is not None for key in ("checked_at", "reachable", "healthy", "status_code", "detail")):
        return None
    return ProviderAdminProbeStatus(
        checked_at=payload.get("checked_at"),
        reachable=payload.get("reachable"),
        healthy=payload.get("healthy"),
        status_code=payload.get("status_code"),
        detail=payload.get("detail"),
    )


def _test_result_from_payload(payload: dict | None) -> ProviderAdminTestResult | None:
    if not isinstance(payload, dict):
        return None
    checked_at = str(payload.get("checked_at") or "").strip()
    if not checked_at:
        return None
    return ProviderAdminTestResult(
        checked_at=checked_at,
        success=bool(payload.get("success")),
        duration_seconds=float(payload.get("duration_seconds") or 0),
        error_code=payload.get("error_code"),
        error_message=payload.get("error_message"),
        preview_url=payload.get("preview_url"),
        summary=payload.get("summary"),
    )


def _entry_status(
    *,
    enabled: bool,
    probe: ProviderAdminProbeStatus | None,
    last_test: ProviderAdminTestResult | None,
) -> tuple[str, str]:
    if not enabled:
        return "disabled", _status_label("disabled")
    if last_test is not None:
        if last_test.success:
            return "healthy", _status_label("healthy")
        if probe is not None and probe.healthy:
            return "degraded", _status_label("degraded")
        return "unavailable", _status_label("unavailable")
    if probe is not None:
        if probe.healthy:
            return "healthy", _status_label("healthy")
        if probe.reachable is False or probe.healthy is False:
            return "unavailable", _status_label("unavailable")
    return "unknown", _status_label("unknown")


def _group_status(entries: list[ProviderAdminEntryItem]) -> tuple[str, str]:
    enabled_entries = [entry for entry in entries if entry.enabled]
    if not enabled_entries:
        return "disabled", _status_label("disabled")
    statuses = {entry.status for entry in enabled_entries}
    if statuses == {"healthy"}:
        return "healthy", _status_label("healthy")
    if "unavailable" in statuses:
        if statuses == {"unavailable"}:
            return "unavailable", _status_label("unavailable")
        return "degraded", _status_label("degraded")
    if "degraded" in statuses:
        return "degraded", _status_label("degraded")
    if "healthy" in statuses and statuses.issubset({"healthy", "unknown"}):
        return "healthy", _status_label("healthy")
    return "unknown", _status_label("unknown")


def _build_dashboard_response() -> ProviderAdminDashboardResponse:
    settings = get_settings()
    connectivity_state = provider_connectivity.load_state()
    probe_map = {
        item.get("target_id"): item
        for item in connectivity_state.get("targets", [])
        if isinstance(item, dict) and item.get("target_id")
    }
    alert_models = [
        ProviderAdminAlertRecord(
            alert_id=str(item.get("alert_id") or ""),
            message=str(item.get("message") or "").strip(),
            updated_at=item.get("updated_at"),
        )
        for item in provider_alerts.list_alert_records()
        if str(item.get("message") or "").strip()
    ]
    alerts_by_provider: dict[str, list[ProviderAdminAlertRecord]] = {}
    for alert in alert_models:
        provider_id = _normalize_provider_key(alert.alert_id.split(":", 1)[0])
        alerts_by_provider.setdefault(provider_id, []).append(alert)

    providers: list[ProviderAdminGroupItem] = []
    routing_updated_at_values: list[str] = []
    status_counts = {
        "healthy": 0,
        "degraded": 0,
        "unavailable": 0,
        "disabled": 0,
        "unknown": 0,
    }

    for provider in provider_routing.list_provider_definitions(settings):
        provider_state = provider_routing.get_provider_state(provider.provider_id, settings)
        if provider_state.get("updated_at"):
            routing_updated_at_values.append(str(provider_state.get("updated_at")))
        state_entry_map = {
            str(item.get("entry_id") or ""): item
            for item in provider_state.get("entries", [])
            if isinstance(item, dict) and item.get("entry_id")
        }
        last_test_results = provider_state.get("last_test_results") or {}
        ordered_state_entries = sorted(
            state_entry_map.values(),
            key=lambda item: (int(item.get("priority") or 0), str(item.get("entry_id") or "")),
        )
        entries: list[ProviderAdminEntryItem] = []
        for index, state_item in enumerate(ordered_state_entries, start=1):
            entry_id = str(state_item.get("entry_id") or "").strip()
            if not entry_id:
                continue
            entry_definition = provider_routing.get_provider_entry_definition(
                provider.provider_id,
                entry_id,
                settings,
            )
            probe_status = _probe_status_from_payload(probe_map.get(f"{provider.provider_id}.{entry_id}"))
            last_test = _test_result_from_payload(last_test_results.get(entry_id))
            status_name, status_label = _entry_status(
                enabled=bool(state_item.get("enabled", True)),
                probe=probe_status,
                last_test=last_test,
            )
            status_counts[status_name] += 1
            entries.append(
                ProviderAdminEntryItem(
                    entry_id=entry_definition.entry_id,
                    entry_label=entry_definition.entry_label,
                    priority=int(state_item.get("priority") or index),
                    enabled=bool(state_item.get("enabled", True)),
                    protocol=entry_definition.protocol,
                    base_url=entry_definition.base_url,
                    endpoint=entry_definition.endpoint,
                    model_name=entry_definition.model_name,
                    credential_label=entry_definition.credential_label,
                    console_url=entry_definition.console_url,
                    docs_url=entry_definition.docs_url,
                    status=status_name,
                    status_label=status_label,
                    note=entry_definition.note,
                    probe=probe_status,
                    last_test=last_test,
                )
            )
        entries.sort(key=lambda item: (item.priority, item.entry_id))
        group_status_name, group_status_label = _group_status(entries)
        providers.append(
            ProviderAdminGroupItem(
                provider_id=provider.provider_id,
                provider_label=provider.provider_label,
                category=provider.category,
                runtime_policy=provider.runtime_policy,
                runtime_note=provider.runtime_note,
                supports_reorder=provider.supports_reorder,
                status=group_status_name,
                status_label=group_status_label,
                updated_at=provider_state.get("updated_at"),
                alerts=alerts_by_provider.get(provider.provider_id, []),
                entries=entries,
            )
        )

    summary = ProviderAdminDashboardSummary(
        provider_count=len(providers),
        enabled_provider_count=sum(1 for provider in providers if provider.status != "disabled"),
        entry_count=sum(len(provider.entries) for provider in providers),
        enabled_entry_count=sum(1 for provider in providers for entry in provider.entries if entry.enabled),
        healthy_entry_count=status_counts["healthy"],
        degraded_entry_count=status_counts["degraded"],
        unavailable_entry_count=status_counts["unavailable"],
        disabled_entry_count=status_counts["disabled"],
        unknown_entry_count=status_counts["unknown"],
        updated_at=max(routing_updated_at_values) if routing_updated_at_values else None,
    )
    return ProviderAdminDashboardResponse(
        updated_at=summary.updated_at,
        connectivity_updated_at=connectivity_state.get("updated_at"),
        summary=summary,
        providers=providers,
        alerts=alert_models,
    )


def _build_legacy_nano_banana_pro_response() -> NanoBananaProAdminResponse:
    dashboard = _build_dashboard_response()
    group = next(
        (item for item in dashboard.providers if item.provider_id == "nano_banana_pro"),
        None,
    )
    if group is None:
        return NanoBananaProAdminResponse(
            provider_name="nano_banana_pro",
            updated_at=None,
            connectivity_updated_at=dashboard.connectivity_updated_at,
            alerts=[],
            profiles=[],
        )
    profiles = [
        ProviderAdminProfileItem(
            profile_id=entry.entry_id,
            profile_label=entry.entry_label,
            priority=entry.priority,
            enabled=entry.enabled,
            protocol=entry.protocol,
            base_url=entry.base_url,
            endpoint=entry.endpoint,
            model_name=entry.model_name,
            probe=entry.probe,
            last_test=(
                ProviderAdminRouteTestResult.model_validate(entry.last_test.model_dump())
                if entry.last_test is not None
                else None
            ),
        )
        for entry in group.entries
    ]
    return NanoBananaProAdminResponse(
        provider_name="nano_banana_pro",
        updated_at=group.updated_at,
        connectivity_updated_at=dashboard.connectivity_updated_at,
        alerts=[item.message for item in group.alerts],
        profiles=profiles,
    )


def _build_generation_context(payload: ProviderAdminTestRequest) -> GenerationContext:
    return GenerationContext(
        hairstyle_name="后台线路探测",
        scene_name="后台线路探测",
        aspect_ratio=payload.aspect_ratio,
        resolution=payload.resolution,
        image_count=1,
    )


def _run_test_for_provider(
    provider_id: str,
    entry_id: str,
    payload: ProviderAdminTestRequest,
) -> ProviderAdminTestResult:
    provider_routing.get_provider_entry_definition(provider_id, entry_id)
    source_path = _resolve_test_source_image_path()
    started_at = time.perf_counter()
    preview_url = None
    summary = None

    try:
        if provider_id == "nano_banana_pro":
            generator = NanoBananaProGenerator()
            profile = next((item for item in generator._profiles if item.profile_id == entry_id), None)
            if profile is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到线路: {entry_id}")
            result = generator._generate_once(
                profile=profile,
                source_image_path=str(source_path),
                prompt=(payload.prompt or _DEFAULT_TEST_PROMPT).strip() or _DEFAULT_TEST_PROMPT,
                context=_build_generation_context(payload),
            )
            if result.primary_image_bytes:
                preview_url = _save_test_preview(result.primary_image_bytes, entry_id)
        elif provider_id == "nano_banana_2":
            generator = NanoBanana2Generator()
            profile = next((item for item in generator._profiles if item.profile_id == entry_id), None)
            if profile is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到线路: {entry_id}")
            result = generator._generate_once(
                profile=profile,
                source_image_path=str(source_path),
                prompt=(payload.prompt or _DEFAULT_TEST_PROMPT).strip() or _DEFAULT_TEST_PROMPT,
                context=_build_generation_context(payload),
            )
            if result.primary_image_bytes:
                preview_url = _save_test_preview(result.primary_image_bytes, entry_id)
        elif provider_id == "seedream":
            generator = SeedreamGenerator(entry_id=entry_id)
            result = generator.generate(
                source_image_path=str(source_path),
                prompt=(payload.prompt or _DEFAULT_TEST_PROMPT).strip() or _DEFAULT_TEST_PROMPT,
                context=_build_generation_context(payload),
                enforce_enabled=False,
            )
            if result.primary_image_bytes:
                preview_url = _save_test_preview(result.primary_image_bytes, entry_id)
        elif provider_id == "image_understanding":
            service = image_understanding.ImageUnderstandingService()
            scene_result = service.extract_scene_blocks(
                source_path.read_bytes(),
                enforce_enabled=False,
            )
            summary = (
                f"主体性别: {scene_result.subject_gender}；"
                f"环境: {scene_result.blocks['scene_environment']}；"
                f"灯光: {scene_result.blocks['scene_lighting']}；"
                f"情绪: {scene_result.blocks['scene_mood']}"
            )
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未知 provider: {provider_id}")

        response = ProviderAdminTestResult(
            checked_at=_utc_now(),
            success=True,
            duration_seconds=round(time.perf_counter() - started_at, 2),
            preview_url=preview_url,
            summary=summary,
        )
    except HTTPException:
        raise
    except ImageGenerationError as exc:
        response = ProviderAdminTestResult(
            checked_at=_utc_now(),
            success=False,
            duration_seconds=round(time.perf_counter() - started_at, 2),
            error_code=exc.code,
            error_message=str(exc),
        )
    except image_understanding.ImageUnderstandingError as exc:
        response = ProviderAdminTestResult(
            checked_at=_utc_now(),
            success=False,
            duration_seconds=round(time.perf_counter() - started_at, 2),
            error_code="image_understanding_error",
            error_message=str(exc),
        )
    except provider_routing.ProviderRoutingError as exc:
        response = ProviderAdminTestResult(
            checked_at=_utc_now(),
            success=False,
            duration_seconds=round(time.perf_counter() - started_at, 2),
            error_code="provider_routing_error",
            error_message=str(exc),
        )
    except Exception as exc:  # pragma: no cover
        response = ProviderAdminTestResult(
            checked_at=_utc_now(),
            success=False,
            duration_seconds=round(time.perf_counter() - started_at, 2),
            error_code="unexpected_error",
            error_message=str(exc),
        )

    provider_routing.record_provider_test_result(
        provider_id,
        entry_id,
        response.model_dump(),
    )
    return response


@router.get("/provider-admin", include_in_schema=False)
def legacy_provider_admin_page() -> RedirectResponse:
    return RedirectResponse(
        url="/admin/providers",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get("/admin/providers", response_class=FileResponse)
def provider_admin_page(request: Request):
    if current_admin_from_request(request) is None:
        return RedirectResponse(
            url="/admin?next=/admin/providers",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return FileResponse(_PAGE_PATH)


@router.get("/api/provider-admin/providers", response_model=ProviderAdminDashboardResponse)
def get_provider_dashboard(
    current_admin: dict = Depends(get_current_admin),
) -> ProviderAdminDashboardResponse:
    del current_admin
    return _build_dashboard_response()


@router.post("/api/provider-admin/providers/probe", response_model=ProviderAdminDashboardResponse)
def probe_all_providers(
    current_admin: dict = Depends(get_current_admin),
) -> ProviderAdminDashboardResponse:
    del current_admin
    provider_connectivity.run_probe_once()
    return _build_dashboard_response()


@router.post("/api/provider-admin/providers/{provider_id}/probe", response_model=ProviderAdminDashboardResponse)
def probe_provider(
    provider_id: str,
    current_admin: dict = Depends(get_current_admin),
) -> ProviderAdminDashboardResponse:
    del current_admin
    try:
        provider_connectivity.run_probe_once(provider_id=provider_id)
    except provider_routing.ProviderRoutingError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _build_dashboard_response()


@router.put("/api/provider-admin/providers/{provider_id}/order", response_model=ProviderAdminDashboardResponse)
def update_provider_order(
    provider_id: str,
    payload: ProviderAdminOrderRequest,
    current_admin: dict = Depends(get_current_admin),
) -> ProviderAdminDashboardResponse:
    del current_admin
    try:
        provider_routing.update_provider_entries(
            provider_id,
            [item.model_dump() for item in payload.items],
        )
    except provider_routing.ProviderRoutingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _build_dashboard_response()


@router.post(
    "/api/provider-admin/providers/{provider_id}/entries/{entry_id}/test",
    response_model=ProviderAdminTestResult,
)
def test_provider_entry(
    provider_id: str,
    entry_id: str,
    payload: ProviderAdminTestRequest,
    current_admin: dict = Depends(get_current_admin),
) -> ProviderAdminTestResult:
    del current_admin
    if payload.entry_id != entry_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求体 entry_id 与路径 entry_id 不一致。",
        )
    try:
        return _run_test_for_provider(provider_id, entry_id, payload)
    except provider_routing.ProviderRoutingError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/api/provider-admin/nano-pro", response_model=NanoBananaProAdminResponse)
def get_nano_banana_pro_admin(
    current_admin: dict = Depends(get_current_admin),
) -> NanoBananaProAdminResponse:
    del current_admin
    return _build_legacy_nano_banana_pro_response()


@router.post("/api/provider-admin/nano-pro/probe", response_model=NanoBananaProAdminResponse)
def probe_nano_banana_pro_admin(
    current_admin: dict = Depends(get_current_admin),
) -> NanoBananaProAdminResponse:
    del current_admin
    provider_connectivity.run_probe_once(provider_id="nano_banana_pro")
    return _build_legacy_nano_banana_pro_response()


@router.put("/api/provider-admin/nano-pro/order", response_model=NanoBananaProAdminResponse)
def update_nano_banana_pro_order(
    payload: ProviderAdminRouteOrderRequest,
    current_admin: dict = Depends(get_current_admin),
) -> NanoBananaProAdminResponse:
    del current_admin
    try:
        provider_routing.update_provider_entries(
            "nano_banana_pro",
            [
                {
                    "entry_id": item.profile_id,
                    "enabled": item.enabled,
                }
                for item in payload.items
            ],
        )
    except provider_routing.ProviderRoutingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _build_legacy_nano_banana_pro_response()


@router.post(
    "/api/provider-admin/nano-pro/test",
    response_model=ProviderAdminRouteTestResult,
)
def test_nano_banana_pro_route(
    payload: ProviderAdminRouteTestRequest,
    current_admin: dict = Depends(get_current_admin),
) -> ProviderAdminRouteTestResult:
    del current_admin
    result = _run_test_for_provider(
        "nano_banana_pro",
        payload.profile_id,
        ProviderAdminTestRequest(
            entry_id=payload.profile_id,
            prompt=payload.prompt,
            aspect_ratio=payload.aspect_ratio,
            resolution=payload.resolution,
        ),
    )
    return ProviderAdminRouteTestResult.model_validate(result.model_dump())
