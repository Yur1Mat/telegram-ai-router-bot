from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp


@dataclass(frozen=True)
class ProviderPreset:
    title: str
    base_url: str
    default_model: str
    protocol: str


PRESETS: dict[str, ProviderPreset] = {
    "openai": ProviderPreset("OpenAI", "https://api.openai.com/v1", "gpt-5.6-luna", "responses"),
    "anthropic": ProviderPreset("Claude (Anthropic)", "https://api.anthropic.com/v1", "claude-sonnet-5", "anthropic"),
    "deepseek": ProviderPreset("DeepSeek", "https://api.deepseek.com", "deepseek-v4-flash", "chat"),
    "custom": ProviderPreset("Custom API", "", "", "chat"),
}


class ProviderError(RuntimeError):
    pass


async def ask(
    session: aiohttp.ClientSession,
    provider: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    base_url: str | None = None,
) -> str:
    preset = PRESETS[provider]
    url = (base_url or preset.base_url).rstrip("/")
    if preset.protocol == "responses":
        payload: dict[str, Any] = {"model": model, "input": messages, "store": False}
        data = await _post(session, f"{url}/responses", payload, {"Authorization": f"Bearer {api_key}"})
        text = data.get("output_text")
        if text:
            return text
        parts = [c.get("text", "") for item in data.get("output", []) for c in item.get("content", []) if c.get("type") == "output_text"]
        return "".join(parts) or _missing_text(data)
    if preset.protocol == "anthropic":
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        body = {
            "model": model,
            "max_tokens": 4096,
            "messages": [m for m in messages if m["role"] != "system"],
        }
        if system:
            body["system"] = system
        data = await _post(
            session,
            f"{url}/messages",
            body,
            {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        )
        return "".join(c.get("text", "") for c in data.get("content", []) if c.get("type") == "text") or _missing_text(data)
    data = await _post(
        session,
        f"{url}/chat/completions",
        {"model": model, "messages": messages},
        {"Authorization": f"Bearer {api_key}"},
    )
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("API returned no text") from exc


async def _post(session: aiohttp.ClientSession, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    try:
        async with session.post(url, json=payload, headers=headers) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                detail = data.get("error", data) if isinstance(data, dict) else data
                raise ProviderError(f"API error {response.status}: {str(detail)[:500]}")
            if not isinstance(data, dict):
                raise ProviderError("API returned an invalid response")
            return data
    except aiohttp.ClientError as exc:
        raise ProviderError(f"Network error: {exc}") from exc


def _missing_text(_: dict[str, Any]) -> str:
    raise ProviderError("API returned no text")
