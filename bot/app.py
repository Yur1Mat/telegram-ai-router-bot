from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Any

import aiohttp

from .config import Settings
from .messages import MESSAGES
from .storage import Storage

HELP = """🌤 <b>Бот добрых пожеланий</b>

Я присылаю разные тёплые и немного смешные пожелания каждый день в 08:30 и 17:30 по Москве.

/start — включить сообщения
/stop — остановить сообщения
/status — проверить подписку и расписание
/test — получить пробное пожелание прямо сейчас
/help — показать эту справку"""


class TelegramError(RuntimeError):
    def __init__(self, description: str, error_code: int = 0):
        super().__init__(description)
        self.description = description
        self.error_code = error_code


def next_scheduled_at(now: datetime, send_times: tuple[time, ...]) -> datetime:
    for send_time in send_times:
        candidate = datetime.combine(now.date(), send_time, tzinfo=now.tzinfo)
        if candidate > now:
            return candidate
    return datetime.combine(now.date() + timedelta(days=1), send_times[0], tzinfo=now.tzinfo)


class TelegramBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.storage = Storage(settings.data_dir / "kindness.sqlite3")
        self.api = f"https://api.telegram.org/bot{settings.telegram_token}"

    async def run(self) -> None:
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            await self._call(session, "deleteWebhook", {"drop_pending_updates": False})
            await self._set_commands(session)
            try:
                async with asyncio.TaskGroup() as tasks:
                    tasks.create_task(self._poll(session))
                    tasks.create_task(self._schedule(session))
            finally:
                self.storage.close()

    async def _poll(self, session: aiohttp.ClientSession) -> None:
        offset = 0
        while True:
            try:
                updates = await self._call(
                    session, "getUpdates",
                    {"offset": offset, "timeout": 45, "allowed_updates": ["message"]},
                )
                for update in updates:
                    offset = update["update_id"] + 1
                    await self._handle(session, update)
            except (aiohttp.ClientError, asyncio.TimeoutError, TelegramError) as exc:
                logging.warning("Telegram connection error: %s", exc)
                await asyncio.sleep(3)

    async def _schedule(self, session: aiohttp.ClientSession) -> None:
        while True:
            now = datetime.now(self.settings.timezone)
            planned = next_scheduled_at(now, self.settings.send_times)
            logging.info("Next delivery: %s", planned.isoformat())
            await asyncio.sleep(max(0, (planned - now).total_seconds()))
            await self._broadcast(session, planned)

    async def _broadcast(self, session: aiohttp.ClientSession, planned: datetime) -> None:
        subscribers = self.storage.subscribers()
        if not subscribers:
            logging.info("No subscribers; delivery skipped")
            return
        slot_key = planned.strftime("%Y-%m-%dT%H:%M")
        message = MESSAGES[self.storage.message_for_slot(slot_key, len(MESSAGES))]
        for chat_id in subscribers:
            if self.storage.delivered(slot_key, chat_id):
                continue
            try:
                await self._send(session, chat_id, message)
                self.storage.mark_delivered(slot_key, chat_id)
            except TelegramError as exc:
                logging.warning("Could not send to %s: %s", chat_id, exc)
                if exc.error_code == 403:
                    self.storage.unsubscribe(chat_id)

    async def _handle(self, session: aiohttp.ClientSession, update: dict[str, Any]) -> None:
        message = update.get("message")
        if not message or "text" not in message:
            return
        user = message.get("from", {})
        user_id = user.get("id")
        chat_id = message["chat"]["id"]
        if self.settings.allowed_user_ids and user_id not in self.settings.allowed_user_ids:
            await self._send(session, chat_id, "Этот бот работает только для приглашённых пользователей.")
            return

        command = message["text"].strip().split(maxsplit=1)[0].split("@", 1)[0].lower()
        if command == "/start":
            self.storage.subscribe(chat_id, user.get("first_name", ""))
            await self._send(session, chat_id, "Готово! Добрые сообщения включены. 💛\n\n" + HELP)
        elif command == "/stop":
            self.storage.unsubscribe(chat_id)
            await self._send(session, chat_id, "Хорошо, сообщения остановлены. Вернуться можно командой /start.")
        elif command == "/status":
            status = "включены ✅" if self.storage.is_subscribed(chat_id) else "выключены ⏸"
            times = " и ".join(item.strftime("%H:%M") for item in self.settings.send_times)
            await self._send(
                session, chat_id,
                f"Сообщения: <b>{status}</b>\nРасписание: <b>{times}</b> по Москве\n"
                f"В каталоге: <b>{len(MESSAGES)}</b> вариантов",
            )
        elif command == "/test":
            sample_id = datetime.now(self.settings.timezone).toordinal() % len(MESSAGES)
            await self._send(session, chat_id, MESSAGES[sample_id])
        elif command in {"/help", "/about"}:
            await self._send(session, chat_id, HELP)
        else:
            await self._send(session, chat_id, "Я понимаю команды /start, /stop, /status и /test.")

    async def _set_commands(self, session: aiohttp.ClientSession) -> None:
        commands = [
            {"command": "start", "description": "Включить добрые сообщения"},
            {"command": "stop", "description": "Остановить сообщения"},
            {"command": "status", "description": "Статус и расписание"},
            {"command": "test", "description": "Пробное пожелание"},
            {"command": "help", "description": "Помощь"},
        ]
        await self._call(session, "setMyCommands", {"commands": commands})

    async def _send(self, session: aiohttp.ClientSession, chat_id: int, text: str) -> None:
        await self._call(session, "sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

    async def _call(self, session: aiohttp.ClientSession, method: str, payload: dict[str, Any]) -> Any:
        async with session.post(f"{self.api}/{method}", json=payload) as response:
            data = await response.json(content_type=None)
            if not data.get("ok"):
                raise TelegramError(data.get("description", str(data)), data.get("error_code", 0))
            return data["result"]


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    asyncio.run(TelegramBot(settings).run())
