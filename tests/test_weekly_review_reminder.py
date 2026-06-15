"""weekly_review_reminder の純粋ロジックに対するユニットテスト。"""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from health import weekly_review_reminder as wr  # noqa: E402


class TestReminder(unittest.TestCase):
    def test_build_reminder_comment_starts_with_mention(self):
        payload = wr.build_reminder_comment("user-123")
        first = payload["rich_text"][0]
        self.assertEqual(first["type"], "mention")
        self.assertEqual(first["mention"]["user"]["id"], "user-123")
        self.assertEqual(payload["rich_text"][1]["type"], "text")

    def test_is_target_window_sunday_21(self):
        # 2026-06-14 は日曜。21時台のみ True。
        self.assertTrue(wr.is_target_window(dt.datetime(2026, 6, 14, 21, 0)))
        self.assertFalse(wr.is_target_window(dt.datetime(2026, 6, 14, 20, 59)))
        self.assertFalse(wr.is_target_window(dt.datetime(2026, 6, 15, 21, 0)))  # 月曜

    def test_now_jst_offset(self):
        utc = dt.datetime(2026, 6, 14, 12, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(wr.now_jst(utc).hour, 21)  # 12:00 UTC = 21:00 JST
        self.assertTrue(wr.is_target_window(wr.now_jst(utc)))

    def test_run_skips_outside_window(self):
        # 月曜 11:32 UTC → 日曜21時ではない → skip(0)、副作用なし。
        utc = dt.datetime(2026, 6, 15, 11, 32, tzinfo=dt.timezone.utc)
        self.assertEqual(wr.run(dry_run=True, now_utc=utc), 0)

    def test_run_dry_run_in_window(self):
        utc = dt.datetime(2026, 6, 14, 12, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(wr.run(dry_run=True, now_utc=utc), 0)

    def test_run_errors_without_token_when_forced(self):
        saved = os.environ.pop("NOTION_TOKEN", None)
        try:
            with self.assertRaises(wr.ReminderError):
                wr.run(dry_run=False, force=True)
        finally:
            if saved is not None:
                os.environ["NOTION_TOKEN"] = saved


if __name__ == "__main__":
    unittest.main()
