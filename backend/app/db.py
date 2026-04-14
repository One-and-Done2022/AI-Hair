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
    inspect,
    text,
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
    Column("nickname", String(255)),
    Column("created_at", String(64), nullable=False),
    Column("free_quota_total", Integer, nullable=False, server_default=text("10")),
    Column("free_quota_used", Integer, nullable=False, server_default=text("0")),
    Column("paid_quota_balance", Integer, nullable=False, server_default=text("0")),
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
    Column("hair_started_at", String(64)),
    Column("first_image_ready_at", String(64)),
    Column("scene_started_at", String(64)),
    Column("first_scene_ready_at", String(64)),
    Column("completed_at", String(64)),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
)

purchase_orders = Table(
    "purchase_orders",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("product_id", String(128), nullable=False),
    Column("product_name", String(255), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("unit_price_cents", Integer, nullable=False),
    Column("amount_cents", Integer, nullable=False),
    Column("status", String(32), nullable=False),
    Column("wechat_prepay_id", String(255)),
    Column("wechat_transaction_id", String(255)),
    Column("payment_payload", Text),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
    Column("confirmed_at", String(64)),
)

feedback_submissions = Table(
    "feedback_submissions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("job_id", String(64), ForeignKey("jobs.id", ondelete="SET NULL")),
    Column("survey_type", String(64), nullable=False),
    Column("trigger_completed_jobs", Integer, nullable=False),
    Column("hairstyle_expectation", String(64), nullable=False),
    Column("hair_color_satisfaction", String(64), nullable=False),
    Column("scene_satisfaction", String(64), nullable=False),
    Column("wait_time_feeling", String(64), nullable=False),
    Column("image_clarity_satisfaction", String(64), nullable=False),
    Column("ui_usability", String(64), nullable=False),
    Column("improvement_suggestion", Text),
    Column("created_at", String(64), nullable=False),
)

Index("idx_auth_tokens_user_id", auth_tokens.c.user_id)
Index("idx_uploads_user_id", uploads.c.user_id)
Index("idx_jobs_user_id", jobs.c.user_id)
Index("idx_jobs_status", jobs.c.status)
Index("idx_purchase_orders_user_id", purchase_orders.c.user_id)
Index("idx_feedback_submissions_user_id", feedback_submissions.c.user_id)
Index("idx_feedback_submissions_created_at", feedback_submissions.c.created_at)
Index(
    "uq_feedback_submissions_user_survey_type",
    feedback_submissions.c.user_id,
    feedback_submissions.c.survey_type,
    unique=True,
)


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
    engine = get_engine()
    metadata.create_all(engine)
    _migrate_users_table(engine)
    _migrate_jobs_table(engine)
    _migrate_purchase_orders_table(engine)


def _migrate_users_table(engine: Engine) -> None:
    inspector = inspect(engine)
    try:
        existing_columns = {column["name"] for column in inspector.get_columns("users")}
    except Exception:
        existing_columns = set()

    statements: list[str] = []
    if "free_quota_total" not in existing_columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN free_quota_total INTEGER NOT NULL DEFAULT 10"
        )
    if "free_quota_used" not in existing_columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN free_quota_used INTEGER NOT NULL DEFAULT 0"
        )
    if "paid_quota_balance" not in existing_columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN paid_quota_balance INTEGER NOT NULL DEFAULT 0"
        )
    if "nickname" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN nickname VARCHAR(255)")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)


def _migrate_jobs_table(engine: Engine) -> None:
    inspector = inspect(engine)
    try:
        existing_columns = {column["name"] for column in inspector.get_columns("jobs")}
    except Exception:
        existing_columns = set()

    statements: list[str] = []
    if "hair_started_at" not in existing_columns:
        statements.append("ALTER TABLE jobs ADD COLUMN hair_started_at VARCHAR(64)")
    if "first_image_ready_at" not in existing_columns:
        statements.append("ALTER TABLE jobs ADD COLUMN first_image_ready_at VARCHAR(64)")
    if "scene_started_at" not in existing_columns:
        statements.append("ALTER TABLE jobs ADD COLUMN scene_started_at VARCHAR(64)")
    if "first_scene_ready_at" not in existing_columns:
        statements.append("ALTER TABLE jobs ADD COLUMN first_scene_ready_at VARCHAR(64)")
    if "completed_at" not in existing_columns:
        statements.append("ALTER TABLE jobs ADD COLUMN completed_at VARCHAR(64)")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)


def _migrate_purchase_orders_table(engine: Engine) -> None:
    inspector = inspect(engine)
    try:
        existing_columns = {
            column["name"] for column in inspector.get_columns("purchase_orders")
        }
    except Exception:
        existing_columns = set()

    statements: list[str] = []
    if "wechat_prepay_id" not in existing_columns:
        statements.append(
            "ALTER TABLE purchase_orders ADD COLUMN wechat_prepay_id VARCHAR(255)"
        )
    if "wechat_transaction_id" not in existing_columns:
        statements.append(
            "ALTER TABLE purchase_orders ADD COLUMN wechat_transaction_id VARCHAR(255)"
        )
    if "payment_payload" not in existing_columns:
        statements.append(
            "ALTER TABLE purchase_orders ADD COLUMN payment_payload TEXT"
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)
