from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Protocol, TypeVar

from app.config import Settings, get_settings


_STATE_LOCK = Lock()
_STATE_ROOT_KEY = "providers"
_TEST_RESULT_KEYS = {
    "checked_at",
    "success",
    "duration_seconds",
    "error_code",
    "error_message",
    "preview_url",
    "summary",
}
_PROVIDER_ORDER = (
    "seedream",
    "nano_banana_pro",
    "nano_banana_2",
    "image_understanding",
)
_ENTRY_LINKS: dict[tuple[str, str], dict[str, str]] = {
    ("seedream", "basic"): {
        "console_url": "https://console.volcengine.com/auth/login/",
    },
    ("seedream", "premium"): {
        "console_url": "https://console.volcengine.com/auth/login/",
    },
    ("nano_banana_pro", "primary"): {
        "console_url": "http://15.204.106.42:17935/token",
    },
    ("nano_banana_pro", "route1"): {
        "console_url": "https://api2ok.qalgoai.com/console",
    },
    ("nano_banana_pro", "route2"): {
        "console_url": "https://xais.dchai.cn/",
        "docs_url": "https://my.feishu.cn/wiki/AdrXwbi7HikISik5vh6c8NhOnFd",
    },
    ("nano_banana_2", "primary"): {
        "console_url": "http://15.204.106.42:17935/token",
    },
    ("image_understanding", "primary"): {
        "console_url": "http://15.204.106.42:17935/token",
    },
}


class ProviderRoutingError(ValueError):
    pass


class _SupportsEntryId(Protocol):
    profile_id: str


ProfileT = TypeVar("ProfileT", bound=_SupportsEntryId)


@dataclass(frozen=True, slots=True)
class ProviderEntryDefinition:
    provider_id: str
    provider_label: str
    entry_id: str
    entry_label: str
    protocol: str
    base_url: str
    model_name: str
    endpoint: str
    credential_label: str | None = None
    category: str = "image_generation"
    supports_preview: bool = True
    note: str | None = None
    console_url: str | None = None
    docs_url: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    provider_id: str
    provider_label: str
    category: str
    runtime_policy: str
    runtime_note: str | None
    supports_reorder: bool
    entries: tuple[ProviderEntryDefinition, ...]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _state_file() -> Path:
    settings = get_settings()
    settings.ensure_directories()
    return settings.storage_dir / "provider_routing.json"


def _entry_endpoint(base_url: str, protocol: str, model_name: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    if protocol == "openai_chat_markdown":
        if normalized.endswith("/chat/completions"):
            return normalized
        return f"{normalized}/chat/completions"
    if protocol == "gemini_v1beta":
        return f"{normalized}/v1beta/models/{model_name}:generateContent"
    if protocol == "ark_images_generation":
        return f"{normalized}/images/generations"
    return normalized


def _credential_label_for_allowed_keys(
    allowed_key_ids: tuple[str, ...],
    total_key_count: int,
) -> str:
    cleaned_ids = [item.strip() for item in allowed_key_ids if item.strip()]
    if cleaned_ids:
        return f"Ark Key 组: {', '.join(cleaned_ids)}"
    return f"Ark Key Pool ({total_key_count})"


def _entry_link_kwargs(provider_id: str, entry_id: str) -> dict[str, str]:
    payload = _ENTRY_LINKS.get((provider_id, entry_id))
    return dict(payload) if payload else {}


def _build_seedream_provider(settings: Settings) -> ProviderDefinition | None:
    if not settings.ark_api_keys:
        return None
    base_url = settings.ark_base_url.rstrip("/")
    entries = (
        ProviderEntryDefinition(
            provider_id="seedream",
            provider_label="Seedream / Ark",
            entry_id="basic",
            entry_label="基础模型",
            protocol="ark_images_generation",
            base_url=base_url,
            model_name=settings.seedream_basic_model,
            endpoint=_entry_endpoint(base_url, "ark_images_generation", settings.seedream_basic_model),
            credential_label=_credential_label_for_allowed_keys(
                settings.seedream_basic_allowed_key_ids,
                len(settings.ark_api_keys),
            ),
            note="适合基础场景生成。",
            **_entry_link_kwargs("seedream", "basic"),
        ),
        ProviderEntryDefinition(
            provider_id="seedream",
            provider_label="Seedream / Ark",
            entry_id="premium",
            entry_label="高级模型",
            protocol="ark_images_generation",
            base_url=base_url,
            model_name=settings.seedream_premium_model,
            endpoint=_entry_endpoint(base_url, "ark_images_generation", settings.seedream_premium_model),
            credential_label=_credential_label_for_allowed_keys(
                settings.seedream_premium_allowed_key_ids,
                len(settings.ark_api_keys),
            ),
            note="当前默认场景成片主要走这一档。",
            **_entry_link_kwargs("seedream", "premium"),
        ),
    )
    return ProviderDefinition(
        provider_id="seedream",
        provider_label="Seedream / Ark",
        category="image_generation",
        runtime_policy="preferred_order",
        runtime_note="basic/premium 是不同模型入口，不是自动 fallback 队列；默认 Seedream 后端会参考组内顺序。",
        supports_reorder=True,
        entries=entries,
    )


def _build_nano_banana_pro_provider(settings: Settings) -> ProviderDefinition | None:
    raw_profiles = settings.nano_banana_pro_profiles()
    if not raw_profiles:
        return None
    entries = tuple(
        ProviderEntryDefinition(
            provider_id="nano_banana_pro",
            provider_label="Nano Banana Pro",
            entry_id=profile_id,
            entry_label=profile_label,
            protocol=protocol,
            base_url=base_url.rstrip("/"),
            model_name=model_name,
            endpoint=_entry_endpoint(base_url, protocol, model_name),
            credential_label="独立密钥",
            **_entry_link_kwargs("nano_banana_pro", profile_id),
        )
        for profile_id, profile_label, base_url, _api_key, protocol, model_name in raw_profiles
    )
    return ProviderDefinition(
        provider_id="nano_banana_pro",
        provider_label="Nano Banana Pro",
        category="image_generation",
        runtime_policy="ordered_fallback",
        runtime_note="按组内顺序自动回退到下一条线路。",
        supports_reorder=len(entries) > 1,
        entries=entries,
    )


def _build_nano_banana_2_provider(settings: Settings) -> ProviderDefinition | None:
    if not settings.nano_banana_2_api_key.strip() or not settings.nano_banana_2_base_url.strip():
        return None
    base_url = settings.nano_banana_2_base_url.rstrip("/")
    entry = ProviderEntryDefinition(
        provider_id="nano_banana_2",
        provider_label="Nano Banana 2",
        entry_id="primary",
        entry_label="主线路",
        protocol="gemini_v1beta",
        base_url=base_url,
        model_name=settings.nano_banana_2_model,
        endpoint=_entry_endpoint(base_url, "gemini_v1beta", settings.nano_banana_2_model),
        credential_label="独立密钥",
        **_entry_link_kwargs("nano_banana_2", "primary"),
    )
    return ProviderDefinition(
        provider_id="nano_banana_2",
        provider_label="Nano Banana 2",
        category="image_generation",
        runtime_policy="single_route",
        runtime_note="单线路 provider，只支持启停和测试。",
        supports_reorder=False,
        entries=(entry,),
    )


def _build_image_understanding_provider(settings: Settings) -> ProviderDefinition | None:
    if (
        not settings.image_understanding_api_key.strip()
        or not settings.image_understanding_base_url.strip()
    ):
        return None
    base_url = settings.image_understanding_base_url.rstrip("/")
    entry = ProviderEntryDefinition(
        provider_id="image_understanding",
        provider_label="图片理解",
        entry_id="primary",
        entry_label="主线路",
        protocol="openai_chat_markdown",
        base_url=base_url,
        model_name=settings.image_understanding_model,
        endpoint=_entry_endpoint(base_url, "openai_chat_markdown", settings.image_understanding_model),
        credential_label="独立密钥",
        category="image_understanding",
        supports_preview=False,
        note="真实测试会返回结构化理解结果摘要。",
        **_entry_link_kwargs("image_understanding", "primary"),
    )
    return ProviderDefinition(
        provider_id="image_understanding",
        provider_label="图片理解",
        category="image_understanding",
        runtime_policy="single_route",
        runtime_note="单线路服务，只支持启停和测试。",
        supports_reorder=False,
        entries=(entry,),
    )


def list_provider_definitions(
    settings: Settings | None = None,
) -> tuple[ProviderDefinition, ...]:
    current = settings or get_settings()
    providers: list[ProviderDefinition] = []
    for builder in (
        _build_seedream_provider,
        _build_nano_banana_pro_provider,
        _build_nano_banana_2_provider,
        _build_image_understanding_provider,
    ):
        provider = builder(current)
        if provider is not None:
            providers.append(provider)
    providers.sort(key=lambda item: _PROVIDER_ORDER.index(item.provider_id))
    return tuple(providers)


def get_provider_definition(
    provider_id: str,
    settings: Settings | None = None,
) -> ProviderDefinition:
    normalized_provider_id = str(provider_id or "").strip()
    for provider in list_provider_definitions(settings):
        if provider.provider_id == normalized_provider_id:
            return provider
    raise ProviderRoutingError(f"未知 provider: {normalized_provider_id}")


def get_provider_entry_definition(
    provider_id: str,
    entry_id: str,
    settings: Settings | None = None,
) -> ProviderEntryDefinition:
    provider = get_provider_definition(provider_id, settings)
    normalized_entry_id = str(entry_id or "").strip()
    for entry in provider.entries:
        if entry.entry_id == normalized_entry_id:
            return entry
    raise ProviderRoutingError(f"未知 provider entry: {provider.provider_id}.{normalized_entry_id}")


def _load_raw_state() -> dict[str, Any]:
    path = _state_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict[str, Any]) -> None:
    path = _state_file()
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _default_provider_state(provider: ProviderDefinition) -> dict[str, Any]:
    return {
        "updated_at": None,
        "entries": [
            {
                "entry_id": entry.entry_id,
                "enabled": True,
                "priority": index,
            }
            for index, entry in enumerate(provider.entries, start=1)
        ],
        "last_test_results": {},
    }


def _normalize_test_result(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    normalized = {
        key: value.get(key)
        for key in _TEST_RESULT_KEYS
        if key in value
    }
    return normalized or None


def _normalize_provider_state(
    raw_state: dict[str, Any] | None,
    provider: ProviderDefinition,
) -> dict[str, Any]:
    defaults = _default_provider_state(provider)
    configured_ids = [item["entry_id"] for item in defaults["entries"]]
    raw_entries = None
    if isinstance(raw_state, dict):
        raw_entries = raw_state.get("entries")
        if not isinstance(raw_entries, list):
            raw_entries = raw_state.get("profiles")
    raw_results = raw_state.get("last_test_results") if isinstance(raw_state, dict) else None

    raw_entry_map: dict[str, dict[str, Any]] = {}
    if isinstance(raw_entries, list):
        for item in raw_entries:
            if not isinstance(item, dict):
                continue
            entry_id = str(
                item.get("entry_id")
                or item.get("profile_id")
                or ""
            ).strip()
            if entry_id:
                raw_entry_map[entry_id] = item

    normalized_entries: list[dict[str, Any]] = []
    for default in defaults["entries"]:
        raw_item = raw_entry_map.get(default["entry_id"], {})
        priority = raw_item.get("priority", default["priority"])
        try:
            normalized_priority = int(priority)
        except (TypeError, ValueError):
            normalized_priority = default["priority"]
        normalized_entries.append(
            {
                "entry_id": default["entry_id"],
                "enabled": bool(raw_item.get("enabled", True)),
                "priority": normalized_priority,
            }
        )

    order_map = {entry_id: index for index, entry_id in enumerate(configured_ids)}
    normalized_entries.sort(
        key=lambda item: (
            item["priority"],
            order_map.get(item["entry_id"], len(order_map)),
        )
    )
    normalized_entries = [
        {
            "entry_id": item["entry_id"],
            "enabled": bool(item["enabled"]),
            "priority": index,
        }
        for index, item in enumerate(normalized_entries, start=1)
    ]

    normalized_results: dict[str, dict[str, Any]] = {}
    if isinstance(raw_results, dict):
        for entry_id in configured_ids:
            result = _normalize_test_result(raw_results.get(entry_id))
            if result is not None:
                normalized_results[entry_id] = result

    return {
        "updated_at": raw_state.get("updated_at") if isinstance(raw_state, dict) else None,
        "entries": normalized_entries,
        "last_test_results": normalized_results,
    }


def _normalize_state(
    raw_state: dict[str, Any] | None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    providers = list_provider_definitions(settings)
    raw_root = raw_state if isinstance(raw_state, dict) else {}
    raw_providers = raw_root.get(_STATE_ROOT_KEY)
    if not isinstance(raw_providers, dict):
        raw_providers = {}
        for provider_id in _PROVIDER_ORDER:
            provider_raw = raw_root.get(provider_id)
            if isinstance(provider_raw, dict):
                raw_providers[provider_id] = provider_raw

    normalized_providers: dict[str, dict[str, Any]] = {}
    for provider in providers:
        normalized_providers[provider.provider_id] = _normalize_provider_state(
            raw_providers.get(provider.provider_id),
            provider,
        )

    return {
        _STATE_ROOT_KEY: normalized_providers,
    }


def load_state(settings: Settings | None = None) -> dict[str, Any]:
    current = settings or get_settings()
    with _STATE_LOCK:
        raw_state = _load_raw_state()
        normalized = _normalize_state(raw_state, current)
        if raw_state != normalized:
            _save_state(normalized)
        return normalized


def get_provider_state(
    provider_id: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    normalized_provider_id = str(provider_id or "").strip()
    state = load_state(settings)
    provider = get_provider_definition(normalized_provider_id, settings)
    return state[_STATE_ROOT_KEY].get(
        provider.provider_id,
        _default_provider_state(provider),
    )


def update_provider_entries(
    provider_id: str,
    items: list[dict[str, Any]],
    settings: Settings | None = None,
) -> dict[str, Any]:
    current = settings or get_settings()
    provider = get_provider_definition(provider_id, current)
    configured_ids = [entry.entry_id for entry in provider.entries]

    normalized_items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(items, start=1):
        entry_id = str(item.get("entry_id") or item.get("profile_id") or "").strip()
        if not entry_id or entry_id in seen_ids:
            raise ProviderRoutingError("线路配置包含空的或重复的 entry_id。")
        seen_ids.add(entry_id)
        normalized_items.append(
            {
                "entry_id": entry_id,
                "enabled": bool(item.get("enabled", True)),
                "priority": index,
            }
        )

    if len(normalized_items) != len(configured_ids) or seen_ids != set(configured_ids):
        raise ProviderRoutingError("提交的线路集合必须与当前已配置 entry 完全一致。")

    with _STATE_LOCK:
        state = _normalize_state(_load_raw_state(), current)
        previous = state[_STATE_ROOT_KEY].get(provider.provider_id, _default_provider_state(provider))
        updated = {
            "updated_at": _utc_now(),
            "entries": normalized_items,
            "last_test_results": previous.get("last_test_results", {}),
        }
        state[_STATE_ROOT_KEY][provider.provider_id] = updated
        _save_state(state)
        return updated


def record_provider_test_result(
    provider_id: str,
    entry_id: str,
    result: dict[str, Any],
    settings: Settings | None = None,
) -> dict[str, Any]:
    current = settings or get_settings()
    provider = get_provider_definition(provider_id, current)
    normalized_entry_id = str(entry_id or "").strip()
    configured_ids = {entry.entry_id for entry in provider.entries}
    if normalized_entry_id not in configured_ids:
        raise ProviderRoutingError(
            f"Unknown provider entry: {provider.provider_id}.{normalized_entry_id}"
        )

    normalized_result = _normalize_test_result(result)
    if normalized_result is None:
        raise ProviderRoutingError("测试结果格式无效。")

    with _STATE_LOCK:
        state = _normalize_state(_load_raw_state(), current)
        provider_state = state[_STATE_ROOT_KEY].get(provider.provider_id, _default_provider_state(provider))
        last_test_results = dict(provider_state.get("last_test_results", {}))
        last_test_results[normalized_entry_id] = normalized_result
        updated = {
            **provider_state,
            "last_test_results": last_test_results,
        }
        state[_STATE_ROOT_KEY][provider.provider_id] = updated
        _save_state(state)
        return updated


def list_enabled_entry_ids(
    provider_id: str,
    settings: Settings | None = None,
) -> tuple[str, ...]:
    state = get_provider_state(provider_id, settings)
    enabled = [
        item["entry_id"]
        for item in state.get("entries", [])
        if item.get("enabled", True)
    ]
    return tuple(enabled)


def first_enabled_entry_id(
    provider_id: str,
    settings: Settings | None = None,
) -> str | None:
    enabled = list_enabled_entry_ids(provider_id, settings)
    if enabled:
        return enabled[0]
    return None


def is_entry_enabled(
    provider_id: str,
    entry_id: str,
    settings: Settings | None = None,
) -> bool:
    normalized_entry_id = str(entry_id or "").strip()
    state = get_provider_state(provider_id, settings)
    for item in state.get("entries", []):
        if item.get("entry_id") == normalized_entry_id:
            return bool(item.get("enabled", True))
    return False


def ensure_entry_enabled(
    provider_id: str,
    entry_id: str,
    settings: Settings | None = None,
) -> None:
    provider = get_provider_definition(provider_id, settings)
    if is_entry_enabled(provider.provider_id, entry_id, settings):
        return
    entry_label = entry_id
    for entry in provider.entries:
        if entry.entry_id == entry_id:
            entry_label = entry.entry_label
            break
    raise ProviderRoutingError(f"{provider.provider_label} {entry_label} 当前已在管理台中停用。")


def seedream_model_name_for_entry(
    entry_id: str,
    settings: Settings | None = None,
) -> str:
    current = settings or get_settings()
    normalized_entry_id = str(entry_id or "").strip().lower()
    if normalized_entry_id == "basic":
        return current.seedream_basic_model
    if normalized_entry_id == "premium":
        return current.seedream_premium_model
    raise ProviderRoutingError(f"未知 seedream entry: {normalized_entry_id}")


def seedream_entry_id_for_model(
    model_name: str | None,
    settings: Settings | None = None,
) -> str:
    current = settings or get_settings()
    normalized_model = (model_name or "").strip()
    if not normalized_model:
        return first_enabled_entry_id("seedream", current) or "premium"
    if normalized_model == current.seedream_basic_model and normalized_model != current.seedream_premium_model:
        return "basic"
    if normalized_model == current.seedream_premium_model:
        return "premium"
    if normalized_model == current.ark_image_model and normalized_model != current.seedream_basic_model:
        return "premium"
    return "premium"


def apply_provider_entry_routing(
    provider_id: str,
    entries: tuple[ProfileT, ...] | list[ProfileT],
    settings: Settings | None = None,
) -> tuple[ProfileT, ...]:
    configured_entries = tuple(entries)
    provider_state = get_provider_state(provider_id, settings)
    available_by_id = {entry.profile_id: entry for entry in configured_entries}
    ordered: list[ProfileT] = []

    for item in provider_state.get("entries", []):
        entry = available_by_id.pop(item["entry_id"], None)
        if entry is None:
            continue
        if item.get("enabled", True):
            ordered.append(entry)

    return tuple(ordered)


def apply_nano_banana_pro_routing(
    profiles: tuple[ProfileT, ...] | list[ProfileT],
    settings: Settings | None = None,
) -> tuple[ProfileT, ...]:
    return apply_provider_entry_routing("nano_banana_pro", profiles, settings)


def get_nano_banana_pro_state(
    settings: Settings | None = None,
) -> dict[str, Any]:
    return get_provider_state("nano_banana_pro", settings)


def update_nano_banana_pro_profiles(
    items: list[dict[str, Any]],
    settings: Settings | None = None,
) -> dict[str, Any]:
    return update_provider_entries("nano_banana_pro", items, settings)


def record_nano_banana_pro_test_result(
    profile_id: str,
    result: dict[str, Any],
    settings: Settings | None = None,
) -> dict[str, Any]:
    return record_provider_test_result("nano_banana_pro", profile_id, result, settings)
