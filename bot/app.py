from __future__ import annotations

import asyncio
import html
import logging
from typing import Any

import aiohttp

from .config import Settings
from .providers import PRESETS, ProviderError, ask
from .storage import Storage

HELP = """<b>AI Router Bot</b>

/providers — выбрать AI
/setkey &lt;provider&gt; &lt;key&gt; — сохранить API-ключ
/model &lt;model&gt; — сменить модель
/endpoint &lt;url&gt; — URL для custom API
/system &lt;prompt&gt; — системная инструкция
/status — текущая конфигурация
/clear — очистить контекст
/help — эта справка

Провайдеры: openai, anthropic, deepseek, custom.
Сообщение с ключом бот постарается сразу удалить. Используйте бота только в личном чате."""


class TelegramBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.storage = Storage(settings.data_dir / "bot.sqlite3", settings.encryption_key)
        self.api = f"https://api.telegram.org/bot{settings.telegram_token}"

    async def run(self) -> None:
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            offset = 0
            await self._call(session, "deleteWebhook", {"drop_pending_updates": False})
            while True:
                try:
                    result = await self._call(session, "getUpdates", {"offset": offset, "timeout": 45, "allowed_updates": ["message", "callback_query"]})
                    for update in result:
                        offset = update["update_id"] + 1
                        await self._handle(session, update)
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    logging.warning("Telegram connection error: %s", exc)
                    await asyncio.sleep(3)

    async def _handle(self, session: aiohttp.ClientSession, update: dict[str, Any]) -> None:
        message = update.get("message")
        callback = update.get("callback_query")
        user = (message or callback or {}).get("from", {})
        user_id = user.get("id")
        if user_id not in self.settings.admin_ids:
            if message:
                await self._send(session, message["chat"]["id"], "Доступ запрещён.")
            return
        if callback:
            await self._select_provider(session, callback, user_id)
            return
        if not message or "text" not in message:
            return
        chat_id, text = message["chat"]["id"], message["text"].strip()
        command, _, argument = text.partition(" ")
        command = command.split("@", 1)[0].lower()
        if command in {"/start", "/help"}:
            await self._send(session, chat_id, HELP)
        elif command == "/providers":
            keyboard = [[{"text": p.title, "callback_data": f"provider:{key}"}] for key, p in PRESETS.items()]
            await self._send(session, chat_id, "Выберите провайдера:", {"inline_keyboard": keyboard})
        elif command == "/setkey":
            await self._set_key(session, message, argument)
        elif command == "/model":
            await self._set_value(session, chat_id, user_id, "model", argument, "Модель")
        elif command == "/endpoint":
            if argument and not argument.startswith("https://"):
                await self._send(session, chat_id, "Endpoint должен начинаться с https://")
            else:
                await self._set_value(session, chat_id, user_id, "base_url", argument, "Endpoint")
        elif command == "/system":
            await self._set_value(session, chat_id, user_id, "system_prompt", argument, "Системная инструкция")
        elif command == "/status":
            await self._status(session, chat_id, user_id)
        elif command == "/clear":
            self.storage.clear_history(user_id)
            await self._send(session, chat_id, "Контекст очищен.")
        elif text.startswith("/"):
            await self._send(session, chat_id, "Неизвестная команда. Используйте /help")
        else:
            await self._chat(session, chat_id, user_id, text)

    async def _select_provider(self, session: aiohttp.ClientSession, callback: dict[str, Any], user_id: int) -> None:
        data = callback.get("data", "")
        provider = data.removeprefix("provider:")
        if provider not in PRESETS:
            return
        self.storage.update(user_id, provider=provider, model=PRESETS[provider].default_model or None)
        self.storage.clear_history(user_id)
        await self._call(session, "answerCallbackQuery", {"callback_query_id": callback["id"], "text": f"Выбран {PRESETS[provider].title}"})
        await self._send(session, callback["message"]["chat"]["id"], f"Активен <b>{html.escape(PRESETS[provider].title)}</b>. Контекст очищен.")

    async def _set_key(self, session: aiohttp.ClientSession, message: dict[str, Any], argument: str) -> None:
        chat_id, user_id = message["chat"]["id"], message["from"]["id"]
        provider, sep, key = argument.partition(" ")
        try:
            await self._call(session, "deleteMessage", {"chat_id": chat_id, "message_id": message["message_id"]})
        except RuntimeError:
            pass
        if not sep or provider not in PRESETS or not key.strip():
            await self._send(session, chat_id, "Формат: /setkey openai sk-... (также: anthropic, deepseek, custom)")
            return
        self.storage.set_key(user_id, provider, key.strip())
        await self._send(session, chat_id, f"Ключ для <b>{html.escape(PRESETS[provider].title)}</b> сохранён в зашифрованном виде.")

    async def _set_value(self, session: aiohttp.ClientSession, chat_id: int, user_id: int, field: str, value: str, label: str) -> None:
        if not value:
            await self._send(session, chat_id, f"Укажите значение после команды.")
            return
        self.storage.update(user_id, **{field: value})
        if field in {"model", "system_prompt", "base_url"}:
            self.storage.clear_history(user_id)
        await self._send(session, chat_id, f"{label}: <code>{html.escape(value)}</code>. Контекст очищен.")

    async def _status(self, session: aiohttp.ClientSession, chat_id: int, user_id: int) -> None:
        cfg = self.storage.settings(user_id)
        provider = str(cfg["provider"])
        model = cfg["model"] or PRESETS[provider].default_model or "не задана"
        endpoint = cfg["base_url"] or PRESETS[provider].base_url or "не задан"
        has_key = bool(self.storage.get_key(user_id, provider))
        text = f"Провайдер: <b>{html.escape(PRESETS[provider].title)}</b>\nМодель: <code>{html.escape(model)}</code>\nEndpoint: <code>{html.escape(endpoint)}</code>\nAPI-ключ: {'✅' if has_key else '❌'}"
        await self._send(session, chat_id, text)

    async def _chat(self, session: aiohttp.ClientSession, chat_id: int, user_id: int, text: str) -> None:
        cfg = self.storage.settings(user_id)
        provider = str(cfg["provider"])
        api_key = self.storage.get_key(user_id, provider)
        if not api_key:
            await self._send(session, chat_id, f"Сначала добавьте ключ: <code>/setkey {provider} ВАШ_КЛЮЧ</code>")
            return
        model = cfg["model"] or PRESETS[provider].default_model
        endpoint = cfg["base_url"] or PRESETS[provider].base_url
        if not model or not endpoint:
            await self._send(session, chat_id, "Для custom задайте /model и /endpoint.")
            return
        history = self.storage.history(user_id)
        messages = [{"role": "system", "content": str(cfg["system_prompt"])}] + history + [{"role": "user", "content": text}]
        await self._call(session, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
        try:
            reply = await ask(session, provider, api_key, str(model), messages, str(endpoint))
        except ProviderError as exc:
            await self._send(session, chat_id, f"Ошибка провайдера: <code>{html.escape(str(exc))}</code>")
            return
        history.extend([{"role": "user", "content": text}, {"role": "assistant", "content": reply}])
        self.storage.save_history(user_id, history)
        for chunk in _chunks(reply):
            await self._send(session, chat_id, html.escape(chunk))

    async def _send(self, session: aiohttp.ClientSession, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        await self._call(session, "sendMessage", payload)

    async def _call(self, session: aiohttp.ClientSession, method: str, payload: dict[str, Any]) -> Any:
        async with session.post(f"{self.api}/{method}", json=payload) as response:
            data = await response.json(content_type=None)
            if not data.get("ok"):
                raise RuntimeError(f"Telegram API error: {data.get('description', data)}")
            return data["result"]


def _chunks(text: str, size: int = 3900) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(TelegramBot(settings).run())

