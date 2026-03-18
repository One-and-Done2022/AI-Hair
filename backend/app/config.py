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


@dataclass(slots=True)
class Settings:
    app_name: str
    api_prefix: str
    ark_api_key: str
    ark_base_url: str
    ark_image_model: str
    use_mock_generator: bool
    wechat_app_id: str
    wechat_app_secret: str
    allow_dev_login: bool
    enforce_face_detection: bool
    max_upload_size_mb: int
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

    def ensure_directories(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    storage_dir = Path(os.getenv("STORAGE_DIR", ROOT_DIR / "storage")).resolve()
    database_path = Path(
        os.getenv("DATABASE_PATH", storage_dir / "app.db")
    ).resolve()
    cors_raw = os.getenv("CORS_ALLOW_ORIGINS", "*")
    cors_allow_origins = [item.strip() for item in cors_raw.split(",") if item.strip()]

    return Settings(
        app_name="AI Hair Remix API",
        api_prefix="/api",
        ark_api_key=os.getenv("ARK_API_KEY", "").strip(),
        ark_base_url=os.getenv(
            "ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
        ).strip(),
        ark_image_model=os.getenv(
            "ARK_IMAGE_MODEL", "doubao-seedream-4-5-251128"
        ).strip(),
        use_mock_generator=_env_bool(
            "USE_MOCK_GENERATOR", default=not bool(os.getenv("ARK_API_KEY"))
        ),
        wechat_app_id=os.getenv("WECHAT_APP_ID", "").strip(),
        wechat_app_secret=os.getenv("WECHAT_APP_SECRET", "").strip(),
        allow_dev_login=_env_bool("ALLOW_DEV_LOGIN", True),
        enforce_face_detection=_env_bool("ENFORCE_FACE_DETECTION", False),
        max_upload_size_mb=int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")),
        api_token_ttl_hours=int(os.getenv("API_TOKEN_TTL_HOURS", "72")),
        cors_allow_origins=cors_allow_origins or ["*"],
        storage_dir=storage_dir,
        database_path=database_path,
    )
