from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .messages import MESSAGES

EPOCH = date(2026, 1, 1)


def message_for(date_value: date, slot: int) -> str:
    day_number = (date_value - EPOCH).days
    return MESSAGES[(day_number * 2 + slot) % len(MESSAGES)]


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    raw_chat_ids = os.environ.get("TELEGRAM_CHAT_IDS", "").strip()
    if not token or not raw_chat_ids:
        raise SystemExit("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS are required")

    now = datetime.now(ZoneInfo("Europe/Moscow"))
    requested_slot = os.environ.get("DELIVERY_SLOT", "").strip().lower()
    slot = {"morning": 0, "evening": 1}.get(requested_slot, 0 if now.hour < 15 else 1)
    message = message_for(now.date(), slot)

    for raw_chat_id in raw_chat_ids.split(","):
        payload = json.dumps({"chat_id": int(raw_chat_id.strip()), "text": message}).encode()
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            details = exc.read().decode(errors="replace")
            print(f"Telegram rejected chat {raw_chat_id}: {details}", file=sys.stderr)
            raise SystemExit(1) from exc
        if not result.get("ok"):
            raise SystemExit(f"Telegram error for chat {raw_chat_id}: {result}")
        print(f"Delivered to chat {raw_chat_id.strip()}")


if __name__ == "__main__":
    main()
