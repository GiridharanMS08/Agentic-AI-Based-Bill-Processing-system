from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / "config" / "db_config.env"
load_dotenv(ENV_FILE)


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


class Settings:
    APP_ENV = os.getenv("APP_ENV", "production").strip()
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()

    DB_HOST = os.getenv("DB_HOST", "127.0.0.1").strip()
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root").strip()
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "bill_analyzer").strip()
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    # Free-tier friendly model; override in env when needed.
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    GEMINI_ENABLED = _bool("GEMINI_ENABLED", True)
    GEMINI_MAX_CALLS_PER_FILE = int(os.getenv("GEMINI_MAX_CALLS_PER_FILE", "2"))
    GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
    GEMINI_RETRY_SECONDS = float(os.getenv("GEMINI_RETRY_SECONDS", "2"))
    GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "60"))

    RAPIDOCR_DPI = int(os.getenv("RAPIDOCR_DPI", "200"))
    OCR_MIN_CONFIDENCE = float(os.getenv("OCR_MIN_CONFIDENCE", "60"))

    INPUT_DIR = str(BASE_DIR / os.getenv("INPUT_DIR", "input_bills"))
    OUTPUT_DIR = str(BASE_DIR / os.getenv("OUTPUT_DIR", "output"))
    CATEGORY_CONFIG_PATH = str(BASE_DIR / "config" / "categories.json")
    MAX_FILES_PER_RUN = int(os.getenv("MAX_FILES_PER_RUN", "500"))

    @property
    def database_url(self) -> str:
        user = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASSWORD)
        host = self.DB_HOST
        port = self.DB_PORT
        db = quote_plus(self.DB_NAME)
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset=utf8mb4"


settings = Settings()
