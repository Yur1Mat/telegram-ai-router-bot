from __future__ import annotations

import sqlite3
from pathlib import Path


class Storage:
    def __init__(self, path: Path):
        self._db = sqlite3.connect(path)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                chat_id INTEGER PRIMARY KEY,
                first_name TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS scheduled_slots (
                slot_key TEXT PRIMARY KEY,
                message_id INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS deliveries (
                slot_key TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                delivered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (slot_key, chat_id)
            );
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            );
            INSERT OR IGNORE INTO state(key, value) VALUES ('next_message_id', 0);
            """
        )
        self._db.commit()

    def subscribe(self, chat_id: int, first_name: str = "") -> None:
        self._db.execute(
            """INSERT INTO subscriptions(chat_id, first_name, active)
               VALUES (?, ?, 1)
               ON CONFLICT(chat_id) DO UPDATE SET first_name=excluded.first_name, active=1""",
            (chat_id, first_name),
        )
        self._db.commit()

    def unsubscribe(self, chat_id: int) -> None:
        self._db.execute("UPDATE subscriptions SET active=0 WHERE chat_id=?", (chat_id,))
        self._db.commit()

    def is_subscribed(self, chat_id: int) -> bool:
        row = self._db.execute(
            "SELECT active FROM subscriptions WHERE chat_id=?", (chat_id,)
        ).fetchone()
        return bool(row and row[0])

    def subscribers(self) -> list[int]:
        return [
            row[0]
            for row in self._db.execute(
                "SELECT chat_id FROM subscriptions WHERE active=1 ORDER BY chat_id"
            )
        ]

    def message_for_slot(self, slot_key: str, catalog_size: int) -> int:
        row = self._db.execute(
            "SELECT message_id FROM scheduled_slots WHERE slot_key=?", (slot_key,)
        ).fetchone()
        if row:
            return int(row[0])

        with self._db:
            next_id = int(
                self._db.execute(
                    "SELECT value FROM state WHERE key='next_message_id'"
                ).fetchone()[0]
            )
            self._db.execute(
                "INSERT INTO scheduled_slots(slot_key, message_id) VALUES (?, ?)",
                (slot_key, next_id),
            )
            self._db.execute(
                "UPDATE state SET value=? WHERE key='next_message_id'",
                ((next_id + 1) % catalog_size,),
            )
        return next_id

    def delivered(self, slot_key: str, chat_id: int) -> bool:
        return self._db.execute(
            "SELECT 1 FROM deliveries WHERE slot_key=? AND chat_id=?", (slot_key, chat_id)
        ).fetchone() is not None

    def mark_delivered(self, slot_key: str, chat_id: int) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO deliveries(slot_key, chat_id) VALUES (?, ?)",
            (slot_key, chat_id),
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()
