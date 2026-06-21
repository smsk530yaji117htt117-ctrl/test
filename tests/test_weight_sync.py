"""weight_sync の純粋ロジックに対するユニットテスト（ネットワーク非依存）。"""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from health import weight_sync as ws  # noqa: E402


class TestPureLogic(unittest.TestCase):
    def test_iso_week_key_format(self):
        self.assertEqual(ws.iso_week_key(dt.date(2026, 6, 15)), "2026-W25")

    def test_compute_bmi(self):
        self.assertEqual(ws.compute_bmi(95.0, 170.0), 32.9)
        self.assertEqual(ws.compute_bmi(70.0, 170.0), 24.2)

    def test_compute_bmi_rejects_bad_height(self):
        with self.assertRaises(ws.SyncError):
            ws.compute_bmi(70.0, 0)

    def test_parse_googlefit_weight_latest_point(self):
        resp = {
            "bucket": [
                {"dataset": [{"point": [
                    {"endTimeNanos": "100", "value": [{"fpVal": 95.0}]},
                    {"endTimeNanos": "200", "value": [{"fpVal": 94.2}]},
                ]}]}
            ]
        }
        self.assertEqual(ws.parse_googlefit_weight(resp), 94.2)

    def test_parse_googlefit_weight_raises_when_empty(self):
        with self.assertRaises(ws.SyncError):
            ws.parse_googlefit_weight({"bucket": []})

    def test_already_synced_detects_marker(self):
        line = ws.build_weekly_line(dt.date(2026, 6, 15), "2026-W25", 94.2, 170.0, 32.6)
        self.assertTrue(ws.already_synced_this_week([line], "2026-W25"))

    def test_already_synced_false_for_other_week(self):
        line = ws.build_weekly_line(dt.date(2026, 6, 15), "2026-W25", 94.2, 170.0, 32.6)
        self.assertFalse(ws.already_synced_this_week([line], "2026-W26"))

    def test_build_weekly_line_contains_week_key(self):
        line = ws.build_weekly_line(dt.date(2026, 6, 15), "2026-W25", 94.2, 170.0, 32.6)
        self.assertIn("2026-W25", line)
        self.assertIn("BMI 32.6", line)

    def test_build_append_children_shape(self):
        payload = ws.build_append_children("hello")
        block = payload["children"][0]
        self.assertEqual(block["type"], "paragraph")
        self.assertEqual(
            block["paragraph"]["rich_text"][0]["text"]["content"], "hello"
        )


class TestRunGuards(unittest.TestCase):
    def test_run_errors_without_env(self):
        # 必須 env が無い状態では SyncError（静かに無視しない）。
        saved = {k: os.environ.pop(k, None) for k in (
            "GOOGLE_FIT_CLIENT_ID", "GOOGLE_FIT_CLIENT_SECRET",
            "GOOGLE_FIT_REFRESH_TOKEN", "NOTION_TOKEN")}
        try:
            with self.assertRaises(ws.SyncError):
                ws.run(dry_run=True, today=dt.date(2026, 6, 15))
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_main_returns_nonzero_on_error(self):
        saved = {k: os.environ.pop(k, None) for k in (
            "GOOGLE_FIT_CLIENT_ID", "GOOGLE_FIT_CLIENT_SECRET",
            "GOOGLE_FIT_REFRESH_TOKEN", "NOTION_TOKEN")}
        try:
            self.assertEqual(ws.main(["--dry-run"]), 2)
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
