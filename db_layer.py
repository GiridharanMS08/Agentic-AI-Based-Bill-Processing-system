from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app_config import settings

log = logging.getLogger("bill_agent.db")

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def db_health() -> bool:
    try:
        with engine.connect() as conn:
            return conn.execute(text("SELECT 1")).scalar() == 1
    except SQLAlchemyError as exc:
        log.error("Database health check failed: %s", exc)
        return False


def sync_categories() -> None:
    path = Path(settings.CATEGORY_CONFIG_PATH)
    data: dict[str, list[str]] = json.loads(path.read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        for name, keywords in data.items():
            db.execute(
                text(
                    "INSERT INTO categories(name, keywords, is_active) "
                    "VALUES(:name, :keywords, 1) "
                    "ON DUPLICATE KEY UPDATE keywords=:keywords2, is_active=1"
                ),
                {
                    "name": name,
                    "keywords": json.dumps(keywords, ensure_ascii=False),
                    "keywords2": json.dumps(keywords, ensure_ascii=False),
                },
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def database_summary() -> dict[str, Any]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT COUNT(*) AS bill_count, MIN(bill_date) AS min_date, MAX(bill_date) AS max_date FROM bills")
        ).mappings().one()
    return dict(row)
