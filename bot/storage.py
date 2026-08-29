from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class Storage:
    def __init__(self, path: Path, encryption_key: str):
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._cipher = Fernet(encryption_key.encode())
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER PRIMARY KEY,
                provider TEXT NOT NULL DEFAULT 'openai',
                model TEXT,
                base_url TEXT,
                system_prompt TEXT NOT NULL DEFAULT 'You are a helpful assistant.'
            );
            CREATE TABLE IF NOT EXISTS secrets (
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                api_key BLOB NOT NULL,
                PRIMARY KEY (user_id, provider)
            );
            CREATE TABLE IF NOT EXISTS history (
                user_id INTEGER PRIMARY KEY,
                messages TEXT NOT NULL DEFAULT '[]'
            );
            """
        )

    def settings(self, user_id: int) -> dict[str, str | None]:
        self._db.execute("INSERT OR IGNORE INTO settings(user_id) VALUES (?)", (user_id,))
        self._db.commit()
        return dict(self._db.execute("SELECT provider, model, base_url, system_prompt FROM settings WHERE user_id=?", (user_id,)).fetchone())

    def update(self, user_id: int, **values: str | None) -> None:
        allowed = {"provider", "model", "base_url", "system_prompt"}
        if not values or not set(values) <= allowed:
            raise ValueError("Invalid settings")
        self.settings(user_id)
        assignments = ", ".join(f"{key}=?" for key in values)
        self._db.execute(f"UPDATE settings SET {assignments} WHERE user_id=?", (*values.values(), user_id))
        self._db.commit()

    def set_key(self, user_id: int, provider: str, api_key: str) -> None:
        encrypted = self._cipher.encrypt(api_key.encode())
        self._db.execute("INSERT OR REPLACE INTO secrets VALUES (?, ?, ?)", (user_id, provider, encrypted))
        self._db.commit()

    def get_key(self, user_id: int, provider: str) -> str | None:
        row = self._db.execute("SELECT api_key FROM secrets WHERE user_id=? AND provider=?", (user_id, provider)).fetchone()
        if not row:
            return None
        try:
            return self._cipher.decrypt(row[0]).decode()
        except InvalidToken as exc:
            raise RuntimeError("ENCRYPTION_KEY does not match the database") from exc

    def history(self, user_id: int) -> list[dict[str, str]]:
        row = self._db.execute("SELECT messages FROM history WHERE user_id=?", (user_id,)).fetchone()
        return json.loads(row[0]) if row else []

    def save_history(self, user_id: int, messages: list[dict[str, str]]) -> None:
        self._db.execute("INSERT OR REPLACE INTO history VALUES (?, ?)", (user_id, json.dumps(messages[-20:], ensure_ascii=False)))
        self._db.commit()

    def clear_history(self, user_id: int) -> None:
        self._db.execute("DELETE FROM history WHERE user_id=?", (user_id,))
        self._db.commit()

    def close(self) -> None:
        self._db.close()
