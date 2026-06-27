"""content.pipeline の純粋ロジック＋driver に対するユニットテスト（ネットワーク非依存）。"""
import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from content import pipeline as cp  # noqa: E402

SAMPLE = (
    "# テーマ在庫\n"
    "- [ ] Notionを外部記憶にしてAIを育てる｜種類: 第二の脳｜slug: notion-second-brain\n"
    "- [x] 既に書いたやつ｜種類: ノウハウ｜slug: already-done｜draft: 2026-06-01-already-done.md\n"
    "- [ ] 承認ゲート設計｜種類: 設計思想｜slug: approval-gate-design\n"
)


class TestPureLogic(unittest.TestCase):
    def test_jst_today_uses_utc_plus_9(self):
        # UTC 2026-06-26 23:00 は JST では 2026-06-27。
        now = dt.datetime(2026, 6, 26, 23, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(cp.jst_today(now), dt.date(2026, 6, 27))

    def test_slugify_basic(self):
        self.assertEqual(cp.slugify("Hello World_Foo"), "hello-world-foo")
        self.assertEqual(cp.slugify("  A--B  "), "a-b")

    def test_slugify_rejects_non_ascii(self):
        with self.assertRaises(cp.PipelineError):
            cp.slugify("日本語のみ")

    def test_parse_themes_extracts_fields(self):
        themes = cp.parse_themes(SAMPLE)
        self.assertEqual(len(themes), 3)
        self.assertEqual(themes[0].title, "Notionを外部記憶にしてAIを育てる")
        self.assertEqual(themes[0].kind, "第二の脳")
        self.assertEqual(themes[0].slug, "notion-second-brain")
        self.assertFalse(themes[0].done)
        self.assertTrue(themes[1].done)
        self.assertEqual(themes[1].draft, "2026-06-01-already-done.md")

    def test_parse_themes_rejects_duplicate_slug(self):
        dup = SAMPLE + "- [ ] かぶり｜種類: x｜slug: notion-second-brain\n"
        with self.assertRaises(cp.PipelineError):
            cp.parse_themes(dup)

    def test_select_next_skips_done(self):
        themes = cp.parse_themes(SAMPLE)
        nxt = cp.select_next(themes)
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt.slug, "notion-second-brain")

    def test_select_next_returns_none_when_all_done(self):
        text = "- [x] a｜種類: k｜slug: a｜draft: d.md\n"
        self.assertIsNone(cp.select_next(cp.parse_themes(text)))

    def test_draft_filename(self):
        self.assertEqual(
            cp.draft_filename(dt.date(2026, 6, 27), "notion-second-brain"),
            "2026-06-27-notion-second-brain.md",
        )

    def test_render_generation_prompt_injects_theme(self):
        theme = cp.parse_themes(SAMPLE)[0]
        prompt = cp.render_generation_prompt(theme)
        self.assertIn("Notionを外部記憶にしてAIを育てる", prompt)
        self.assertIn("第二の脳", prompt)
        self.assertIn("1800〜2200字", prompt)

    def test_mark_done_flips_only_target_line(self):
        themes = cp.parse_themes(SAMPLE)
        target = themes[0]
        updated = cp.mark_done(SAMPLE, target, "2026-06-27-notion-second-brain.md")
        reparsed = {t.slug: t for t in cp.parse_themes(updated)}
        self.assertTrue(reparsed["notion-second-brain"].done)
        self.assertEqual(reparsed["notion-second-brain"].draft,
                         "2026-06-27-notion-second-brain.md")
        # 他の行は不変。
        self.assertFalse(reparsed["approval-gate-design"].done)

    def test_mark_done_is_idempotent(self):
        themes = cp.parse_themes(SAMPLE)
        once = cp.mark_done(SAMPLE, themes[0], "d.md")
        # 2回目は再パースした done 行に対しては select されないため、
        # mark_done を同じ行に再適用しても結果は安定する。
        twice = cp.mark_done(once, cp.parse_themes(once)[0], "d.md")
        self.assertEqual(once, twice)


class TestDriver(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.themes_path = os.path.join(self.tmp.name, "themes.md")
        self.drafts = os.path.join(self.tmp.name, "drafts")
        with open(self.themes_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_mode_returns_zero(self):
        rc = cp.run(self.themes_path, self.drafts, mode="plan",
                    today=dt.date(2026, 6, 27))
        self.assertEqual(rc, 0)

    def test_empty_guard_when_all_done(self):
        with open(self.themes_path, "w", encoding="utf-8") as f:
            f.write("- [x] a｜種類: k｜slug: a｜draft: d.md\n")
        rc = cp.run(self.themes_path, self.drafts, mode="plan",
                    today=dt.date(2026, 6, 27))
        self.assertEqual(rc, 0)

    def test_write_mode_creates_draft_and_updates_themes(self):
        body_path = os.path.join(self.tmp.name, "body.md")
        with open(body_path, "w", encoding="utf-8") as f:
            f.write("# タイトル\n本文\n")
        rc = cp.run(self.themes_path, self.drafts, mode="write",
                    body_file=body_path, today=dt.date(2026, 6, 27))
        self.assertEqual(rc, 0)
        draft = os.path.join(self.drafts, "2026-06-27-notion-second-brain.md")
        self.assertTrue(os.path.exists(draft))
        # themes.md が草稿済みに更新されている → 次の select は別テーマ。
        with open(self.themes_path, encoding="utf-8") as f:
            nxt = cp.select_next(cp.parse_themes(f.read()))
        self.assertEqual(nxt.slug, "approval-gate-design")

    def test_write_mode_dry_run_writes_nothing(self):
        body_path = os.path.join(self.tmp.name, "body.md")
        with open(body_path, "w", encoding="utf-8") as f:
            f.write("# x\n本文\n")
        rc = cp.run(self.themes_path, self.drafts, mode="write",
                    body_file=body_path, today=dt.date(2026, 6, 27), dry_run=True)
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(
            os.path.join(self.drafts, "2026-06-27-notion-second-brain.md")))

    def test_write_mode_idempotent_when_draft_exists(self):
        os.makedirs(self.drafts, exist_ok=True)
        existing = os.path.join(self.drafts, "2026-06-27-notion-second-brain.md")
        with open(existing, "w", encoding="utf-8") as f:
            f.write("既存\n")
        body_path = os.path.join(self.tmp.name, "body.md")
        with open(body_path, "w", encoding="utf-8") as f:
            f.write("新規\n")
        rc = cp.run(self.themes_path, self.drafts, mode="write",
                    body_file=body_path, today=dt.date(2026, 6, 27))
        self.assertEqual(rc, 0)
        with open(existing, encoding="utf-8") as f:
            self.assertEqual(f.read(), "既存\n")  # 上書きしない

    def test_write_mode_errors_without_body_file(self):
        with self.assertRaises(cp.PipelineError):
            cp.run(self.themes_path, self.drafts, mode="write",
                   today=dt.date(2026, 6, 27))

    def test_main_returns_nonzero_on_error(self):
        rc = cp.main(["--themes", os.path.join(self.tmp.name, "missing.md")])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
