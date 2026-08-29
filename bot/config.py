from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    admin_ids: frozenset[int]
    encryption_key: str
    data_dir: Path
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        key = os.getenv("ENCRYPTION_KEY", "").strip()
        raw_ids = os.getenv("ADMIN_USER_IDS", "")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not key:
            raise ValueError("ENCRYPTION_KEY is required")
        try:
            admin_ids = frozenset(int(value.strip()) for value in raw_ids.split(",") if value.strip())
        except ValueError as exc:
            raise ValueError("ADMIN_USER_IDS must contain comma-separated numbers") from exc
        if not admin_ids:
            raise ValueError("ADMIN_USER_IDS must contain at least one Telegram user ID")
        data_dir = Path(os.getenv("DATA_DIR", "./data")).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        return cls(token, admin_ids, key, data_dir, os.getenv("LOG_LEVEL", "INFO"))

