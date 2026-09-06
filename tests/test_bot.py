import os
import tempfile
import unittest
from datetime import datetime, time
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from bot.app import next_scheduled_at
from bot.config import Settings, _parse_times
from bot.messages import MESSAGES
from bot.storage import Storage


class MessageTests(unittest.TestCase):
    def test_catalog_covers_three_years_at_two_messages_per_day(self):
        self.assertGreaterEqual(len(MESSAGES), 365 * 3 * 2)

    def test_messages_are_unique(self):
        self.assertEqual(len(MESSAGES), len(set(MESSAGES)))

    def test_requested_example_is_present(self):
        self.assertTrue(any("манной каши без единого комочка" in text for text in MESSAGES))


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.zone = ZoneInfo("Europe/Moscow")
        self.times = (time(9, 30), time(19, 30))

    def test_next_time_is_same_day(self):
        now = datetime(2026, 9, 6, 12, 0, tzinfo=self.zone)
        self.assertEqual(next_scheduled_at(now, self.times).hour, 19)

    def test_next_time_rolls_to_tomorrow(self):
        now = datetime(2026, 9, 6, 20, 0, tzinfo=self.zone)
        result = next_scheduled_at(now, self.times)
        self.assertEqual((result.day, result.hour, result.minute), (7, 9, 30))

    def test_time_parser(self):
        self.assertEqual(_parse_times("19:30,09:30"), self.times)


class StorageTests(unittest.TestCase):
    def test_subscription_and_delivery_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "test.db")
            store.subscribe(7, "Маша")
            self.assertEqual(store.subscribers(), [7])
            message_id = store.message_for_slot("2026-09-06T09:30", len(MESSAGES))
            self.assertEqual(message_id, 0)
            store.mark_delivered("2026-09-06T09:30", 7)
            self.assertTrue(store.delivered("2026-09-06T09:30", 7))
            store.unsubscribe(7)
            self.assertFalse(store.is_subscribed(7))
            store.close()

    def test_slot_keeps_same_message_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.db"
            store = Storage(path)
            first = store.message_for_slot("slot", len(MESSAGES))
            store.close()
            store = Storage(path)
            self.assertEqual(store.message_for_slot("slot", len(MESSAGES)), first)
            store.close()


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "token", "DATA_DIR": directory}, clear=True
        ):
            settings = Settings.from_env()
            self.assertEqual(settings.timezone.key, "Europe/Moscow")
            self.assertEqual(settings.send_times, (time(9, 30), time(19, 30)))


if __name__ == "__main__":
    unittest.main()
