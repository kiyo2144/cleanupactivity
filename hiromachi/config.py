"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path


def _as_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_positive_int(value: str | None, *, default: int) -> int:
    if value is None:
        return default
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("SESSION_LIFETIME_DAYS must be greater than zero")
    return parsed


def load_config(instance_path: str) -> dict[str, object]:
    """Build the default Flask configuration for one application instance."""

    instance_dir = Path(instance_path)
    environment = os.getenv("APP_ENV", "development").strip().lower()
    secret_key = os.getenv("SECRET_KEY")

    if environment == "production" and not secret_key:
        raise RuntimeError("SECRET_KEY is required when APP_ENV=production")

    database_path = Path(os.getenv("DATABASE_PATH", instance_dir / "hiromachi.sqlite3"))
    session_dir = Path(os.getenv("SESSION_DIR", instance_dir / "sessions"))

    return {
        "APP_ENV": environment,
        "SECRET_KEY": secret_key or "development-only-change-me",
        "DATABASE_PATH": str(database_path),
        "SESSION_DIR": str(session_dir),
        "SESSION_TYPE": "cachelib",
        "SESSION_SERIALIZATION_FORMAT": "json",
        "SESSION_PERMANENT": True,
        "SESSION_LIFETIME_DAYS": _as_positive_int(
            os.getenv("SESSION_LIFETIME_DAYS"), default=7
        ),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": _as_bool(os.getenv("SESSION_COOKIE_SECURE")),
        "WTF_CSRF_ENABLED": True,
    }
