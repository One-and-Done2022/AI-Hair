from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("openid", String(255), nullable=False, unique=True),
    Column("created_at", String(64), nullable=False),
)

auth_tokens = Table(
    "auth_tokens",
    metadata,
    Column("token", String(255), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", String(64), nullable=False),
    Column("expires_at", String(64), nullable=False),
)

uploads = Table(
    "uploads",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("original_name", String(255), nullable=False),
    Column("stored_path", String(1024), nullable=False),
    Column("mime_type", String(128), nullable=False),
    Column("file_size", Integer, nullable=False),
    Column("width", Integer, nullable=False),
    Column("height", Integer, nullable=False),
    Column("created_at", String(64), nullable=False),
)

jobs = Table(
    "jobs",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("upload_id", String(64), ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False),
    Column("hairstyle_id", String(255), nullable=False),
    Column("scene_id", String(255), nullable=False),
    Column("status", String(64), nullable=False),
    Column("prompt", Text, nullable=False),
    Column("model_name", String(255), nullable=False),
    Column("assigned_key_id", String(255)),
    Column("result_path", String(1024)),
    Column("error_code", String(255)),
    Column("error_message", Text),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
)

Index("idx_auth_tokens_user_id", auth_tokens.c.user_id)
Index("idx_uploads_user_id", uploads.c.user_id)
Index("idx_jobs_user_id", jobs.c.user_id)
Index("idx_jobs_status", jobs.c.status)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    settings.ensure_directories()

    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, object] = {
        "future": True,
        "pool_pre_ping": True,
    }
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    else:
        engine_kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout_seconds,
            pool_recycle=settings.db_pool_recycle_seconds,
        )

    return create_engine(
        settings.database_url,
        connect_args=connect_args,
        **engine_kwargs,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


@contextmanager
def session_scope() -> Session:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    metadata.create_all(get_engine())
