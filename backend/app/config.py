from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _resolve_repo_path(value: str | Path) -> Path:
    path = value if isinstance(value, Path) else Path(value)
    if path.is_absolute():
        return path.resolve()
    return (ROOT_DIR / path).resolve()


def _normalize_database_url(raw_url: str) -> str:
    if not raw_url.startswith("sqlite:///"):
        return raw_url

    path_part = raw_url[len("sqlite:///") :].strip()
    if not path_part:
        return raw_url

    normalized_path = _resolve_repo_path(path_part)
    return f"sqlite:///{normalized_path}"


@dataclass(frozen=True, slots=True)
class ArkApiCredential:
    key_id: str
    api_key: str
    max_concurrency: int = 1
    weight: int = 1


def _parse_ark_api_keys() -> tuple[ArkApiCredential, ...]:
    raw_multi = os.getenv("ARK_API_KEYS", "").strip()
    default_max_concurrency = max(1, _env_int("ARK_API_KEY_MAX_CONCURRENCY", 1))
    default_weight = max(1, _env_int("ARK_API_KEY_DEFAULT_WEIGHT", 1))
    credentials: list[ArkApiCredential] = []

    if raw_multi:
        entries = [item.strip() for item in raw_multi.replace("\n", ",").split(",") if item.strip()]
        for index, entry in enumerate(entries, start=1):
            key_id, separator, api_key = entry.partition(":")
            if not separator:
                raise ValueError(
                    "ARK_API_KEYS must use the format 'key_id:api_key,key_id:api_key'."
                )
            cleaned_key_id = key_id.strip()
            cleaned_api_key = api_key.strip()
            if not cleaned_key_id or not cleaned_api_key:
                raise ValueError(
                    "ARK_API_KEYS contains an empty key_id or api_key entry."
                )
            credentials.append(
                ArkApiCredential(
                    key_id=cleaned_key_id,
                    api_key=cleaned_api_key,
                    max_concurrency=default_max_concurrency,
                    weight=default_weight,
                )
            )
        return tuple(credentials)

    single_key = os.getenv("ARK_API_KEY", "").strip()
    if not single_key:
        return ()
    return (
        ArkApiCredential(
            key_id=os.getenv("ARK_API_KEY_ID", "default").strip() or "default",
            api_key=single_key,
            max_concurrency=default_max_concurrency,
            weight=default_weight,
        ),
    )


@dataclass(slots=True)
class Settings:
    app_name: str
    api_prefix: str
    database_url: str
    db_pool_size: int
    db_max_overflow: int
    db_pool_timeout_seconds: int
    db_pool_recycle_seconds: int
    ark_api_key: str
    ark_api_keys: tuple[ArkApiCredential, ...]
    ark_base_url: str
    ark_image_model: str
    seedream_basic_model: str
    seedream_premium_model: str
    ark_key_cooldown_seconds: int
    image_generator_backend: str
    nano_banana_pro_api_key: str
    nano_banana_pro_base_url: str
    nano_banana_pro_model: str
    nano_banana_2_api_key: str
    nano_banana_2_base_url: str
    nano_banana_2_model: str
    sora_image_api_key: str
    sora_image_base_url: str
    sora_image_model: str
    image_understanding_api_key: str
    image_understanding_base_url: str
    image_understanding_model: str
    image_understanding_timeout_seconds: int
    job_worker_concurrency: int
    queue_backend: str
    redis_url: str
    redis_queue_key: str
    run_embedded_worker: bool
    object_storage_backend: str
    object_storage_public_base_url: str
    oss_endpoint: str
    oss_bucket_name: str
    oss_access_key_id: str
    oss_access_key_secret: str
    oss_prefix: str
    use_mock_generator: bool
    wechat_app_id: str
    wechat_app_secret: str
    allow_dev_login: bool
    enforce_face_detection: bool
    max_upload_size_mb: int
    media_retention_days: int
    api_token_ttl_hours: int
    cors_allow_origins: list[str]
    storage_dir: Path
    database_path: Path

    @property
    def upload_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def result_dir(self) -> Path:
        return self.storage_dir / "results"

    @property
    def uses_local_media(self) -> bool:
        return self.object_storage_backend == "local"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def ensure_directories(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        if self.uses_local_media:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            self.result_dir.mkdir(parents=True, exist_ok=True)
        if self.is_sqlite:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)


def _default_database_url(storage_dir: Path) -> str:
    configured_url = os.getenv("DATABASE_URL", "").strip()
    if configured_url:
        return _normalize_database_url(configured_url)

    legacy_database_path = _resolve_repo_path(
        os.getenv("DATABASE_PATH", storage_dir / "app.db")
    )
    return f"sqlite:///{legacy_database_path}"


def _database_path_from_url(database_url: str, storage_dir: Path) -> Path:
    if database_url.startswith("sqlite:///"):
        raw_path = database_url[len("sqlite:///") :].strip()
        if raw_path:
            return _resolve_repo_path(raw_path)
    return _resolve_repo_path(os.getenv("DATABASE_PATH", storage_dir / "app.db"))


@lru_cache
def get_settings() -> Settings:
    storage_dir = _resolve_repo_path(os.getenv("STORAGE_DIR", ROOT_DIR / "storage"))
    database_url = _default_database_url(storage_dir)
    database_path = _database_path_from_url(database_url, storage_dir)
    cors_raw = os.getenv("CORS_ALLOW_ORIGINS", "*")
    cors_allow_origins = [item.strip() for item in cors_raw.split(",") if item.strip()]
    ark_api_keys = _parse_ark_api_keys()
    default_worker_concurrency = max(
        1,
        sum(credential.max_concurrency for credential in ark_api_keys) or 1,
    )
    queue_backend = os.getenv(
        "JOB_QUEUE_BACKEND",
        "redis" if os.getenv("REDIS_URL", "").strip() else "local",
    ).strip().lower()
    object_storage_backend = os.getenv(
        "OBJECT_STORAGE_BACKEND",
        "local",
    ).strip().lower()
    default_embedded_worker = queue_backend != "redis"
    run_embedded_worker = _env_bool(
        "RUN_EMBEDDED_WORKER",
        default=default_embedded_worker,
    )

    if queue_backend not in {"local", "redis"}:
        raise ValueError("JOB_QUEUE_BACKEND must be either 'local' or 'redis'.")

    if object_storage_backend not in {"local", "aliyun_oss"}:
        raise ValueError(
            "OBJECT_STORAGE_BACKEND must be either 'local' or 'aliyun_oss'."
        )

    image_generator_backend = os.getenv(
        "IMAGE_GENERATOR_BACKEND",
        "seedream",
    ).strip().lower()

    if image_generator_backend not in {
        "seedream",
        "nano_banana_pro",
        "nano_banana_2",
        "sora_image",
    }:
        raise ValueError(
            "IMAGE_GENERATOR_BACKEND must be one of 'seedream', 'nano_banana_pro', 'nano_banana_2', or 'sora_image'."
        )

    if queue_backend == "local" and not run_embedded_worker:
        raise ValueError(
            "RUN_EMBEDDED_WORKER must stay enabled when JOB_QUEUE_BACKEND=local."
        )

    return Settings(
        app_name="AI Hair Remix API",
        api_prefix="/api",
        database_url=database_url,
        db_pool_size=max(1, _env_int("DB_POOL_SIZE", 8)),
        db_max_overflow=max(0, _env_int("DB_MAX_OVERFLOW", 16)),
        db_pool_timeout_seconds=max(1, _env_int("DB_POOL_TIMEOUT_SECONDS", 30)),
        db_pool_recycle_seconds=max(30, _env_int("DB_POOL_RECYCLE_SECONDS", 1800)),
        ark_api_key=(ark_api_keys[0].api_key if ark_api_keys else "").strip(),
        ark_api_keys=ark_api_keys,
        ark_base_url=os.getenv(
            "ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
        ).strip(),
        ark_image_model=os.getenv(
            "ARK_IMAGE_MODEL", "doubao-seedream-5-0-260128"
        ).strip(),
        seedream_basic_model=os.getenv(
            "SEEDREAM_BASIC_MODEL", "doubao-seedream-4-5-251128"
        ).strip(),
        seedream_premium_model=os.getenv(
            "SEEDREAM_PREMIUM_MODEL",
            os.getenv("ARK_IMAGE_MODEL", "doubao-seedream-5-0-260128"),
        ).strip(),
        ark_key_cooldown_seconds=_env_int("ARK_API_KEY_COOLDOWN_SECONDS", 120),
        image_generator_backend=image_generator_backend,
        nano_banana_pro_api_key=os.getenv("NANO_BANANA_PRO_API_KEY", "").strip(),
        nano_banana_pro_base_url=os.getenv(
            "NANO_BANANA_PRO_BASE_URL", "https://api.apiyi.com"
        ).strip().rstrip("/"),
        nano_banana_pro_model=os.getenv(
            "NANO_BANANA_PRO_MODEL", "gemini-3-pro-image-preview"
        ).strip(),
        nano_banana_2_api_key=os.getenv("NANO_BANANA_2_API_KEY", "").strip(),
        nano_banana_2_base_url=os.getenv(
            "NANO_BANANA_2_BASE_URL", "https://api.apiyi.com"
        ).strip().rstrip("/"),
        nano_banana_2_model=os.getenv(
            "NANO_BANANA_2_MODEL", "gemini-3.1-flash-image-preview"
        ).strip(),
        sora_image_api_key=os.getenv("SORA_IMAGE_API_KEY", "").strip(),
        sora_image_base_url=os.getenv(
            "SORA_IMAGE_BASE_URL", "https://api.apiyi.com/v1"
        ).strip().rstrip("/"),
        sora_image_model=os.getenv(
            "SORA_IMAGE_MODEL", "sora_image"
        ).strip(),
        image_understanding_api_key=os.getenv(
            "IMAGE_UNDERSTANDING_API_KEY", ""
        ).strip(),
        image_understanding_base_url=os.getenv(
            "IMAGE_UNDERSTANDING_BASE_URL", "https://api.apiyi.com/v1"
        ).strip().rstrip("/"),
        image_understanding_model=os.getenv(
            "IMAGE_UNDERSTANDING_MODEL", "gemini-3-pro-preview"
        ).strip(),
        image_understanding_timeout_seconds=max(
            30,
            _env_int("IMAGE_UNDERSTANDING_TIMEOUT_SECONDS", 120),
        ),
        job_worker_concurrency=max(
            1,
            _env_int("JOB_WORKER_CONCURRENCY", default_worker_concurrency),
        ),
        queue_backend=queue_backend,
        redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0").strip(),
        redis_queue_key=os.getenv("REDIS_QUEUE_KEY", "aiface:jobs").strip(),
        run_embedded_worker=run_embedded_worker,
        object_storage_backend=object_storage_backend,
        object_storage_public_base_url=os.getenv(
            "OBJECT_STORAGE_PUBLIC_BASE_URL", ""
        ).strip(),
        oss_endpoint=os.getenv("OSS_ENDPOINT", "").strip(),
        oss_bucket_name=os.getenv("OSS_BUCKET_NAME", "").strip(),
        oss_access_key_id=os.getenv("OSS_ACCESS_KEY_ID", "").strip(),
        oss_access_key_secret=os.getenv("OSS_ACCESS_KEY_SECRET", "").strip(),
        oss_prefix=os.getenv("OSS_PREFIX", "aiface").strip("/"),
        use_mock_generator=_env_bool(
            "USE_MOCK_GENERATOR", default=not bool(ark_api_keys)
        ),
        wechat_app_id=os.getenv("WECHAT_APP_ID", "").strip(),
        wechat_app_secret=os.getenv("WECHAT_APP_SECRET", "").strip(),
        allow_dev_login=_env_bool("ALLOW_DEV_LOGIN", True),
        enforce_face_detection=_env_bool("ENFORCE_FACE_DETECTION", True),
        max_upload_size_mb=int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")),
        media_retention_days=max(1, _env_int("MEDIA_RETENTION_DAYS", 7)),
        api_token_ttl_hours=int(os.getenv("API_TOKEN_TTL_HOURS", "72")),
        cors_allow_origins=cors_allow_origins or ["*"],
        storage_dir=storage_dir,
        database_path=database_path,
    )
