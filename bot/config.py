from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo


def _parse_times(value: str) -> tuple[time, ...]:
    result: list[time] = []
    for raw in value.split(","):
        try:
            hour, minute = (int(part) for part in raw.strip().split(":"))
            result.append(time(hour=hour, minute=minute))
        except (TypeError, ValueError) as exc:
            raise ValueError("SEND_TIMES must look like 08:30,17:30") from exc
    if not result:
        raise ValueError("SEND_TIMES must contain at least one time")
    return tuple(sorted(set(result)))


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    send_times: tuple[time, ...]
    timezone: ZoneInfo
    data_dir: Path
    log_level: str
    allowed_user_ids: frozenset[int]

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

        timezone_name = os.getenv("TIMEZONE", "Europe/Moscow").strip()
        try:
            timezone = ZoneInfo(timezone_name)
        except Exception as exc:
            raise ValueError(f"Unknown TIMEZONE: {timezone_name}") from exc

        try:
            allowed = frozenset(
                int(item.strip())
                for item in os.getenv("ALLOWED_USER_IDS", "").split(",")
                if item.strip()
            )
        except ValueError as exc:
            raise ValueError("ALLOWED_USER_IDS must contain comma-separated numbers") from exc

        data_dir = Path(os.getenv("DATA_DIR", "./data")).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            telegram_token=token,
            send_times=_parse_times(os.getenv("SEND_TIMES", "08:30,17:30")),
            timezone=timezone,
            data_dir=data_dir,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            allowed_user_ids=allowed,
        )
