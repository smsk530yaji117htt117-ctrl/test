"""content.pipeline の純粋ロジック＋driver に対するユニットテスト（ネットワーク非依存）。"""
import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from content import pipeline as cp  # noqa: E402

# 6列テーブル。最後の行は slug 空欄（フォールバック確認用）。
SAMPLE = (
    "# テーマ台帳\n"
    "| テーマ名 | 種類 | 出所 | レビュー | 進捗 | slug |\n"
    "|---|---|---|---|---|---|\n"
    "| Notionを外部記憶にしてAIを育てる | 第二の脳 | 手動 | 採用 | 未着手 | notion-external-memory |\n"
    "| 却下されたやつ | ノウハウ | 自動 | 却下 | 未着手 | rejected-one |\n"
    "| 既に書いたやつ | ノウハウ | 手動 | 採用 | 草稿済み | already-done |\n"
    "| 未確認の自動テーマ | 設計思想 | 自動 | 未確認 | 未着手 |  |\n"
)


class TestPureLogic(unittest.TestCase):
    def test_jst_today_uses_utc_plus_9(self):
        now = dt.datetime(2026, 6, 26, 23, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(cp.jst_today(now), dt.date(2026, 6, 27))

    def test_slugify_ascii(self):
        self.assertEqual(cp.slugify("Hello World_Foo"), "hello-world-foo")

    def test_slugify_japanese_is_stable_hash(self):
        a = cp.slugify("日本語のみ")
        b = cp.slugify("日本語のみ")
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("theme-"))
        self.assertNotEqual(cp.slugify("別のタイトル"), a)

    def test_parse_themes_extracts_six_columns(self):
        themes = cp.parse_themes(SAMPLE)
        self.assertEqual(len(themes), 4)
        t = themes[0]
        self.assertEqual(t.title, "Notionを外部記憶にしてAIを育てる")
        self.assertEqual(t.kind, "第二の脳")
        self.assertEqual(t.source, "手動")
        self.assertEqual(t.review, "採用")
        self.assertEqual(t.progress, "未着手")
        self.assertEqual(t.slug, "notion-external-memory")
        # 空欄 slug の行は slug == ""。
        self.assertEqual(themes[3].slug, "")

    def test_parse_themes_rejects_duplicate_title(self):
        dup = SAMPLE + "| Notionを外部記憶にしてAIを育てる | x | 手動 | 採用 | 未着手 | s |\n"
        with self.assertRaises(cp.PipelineError):
            cp.parse_themes(dup)

    def test_parse_themes_rejects_wrong_column_count(self):
        bad = SAMPLE + "| 足りない | 列 | だけ |\n"  # 旧5列も6列でないので拒否される
        with self.assertRaises(cp.PipelineError):
            cp.parse_themes(bad)

    def test_resolve_slug_prefers_column(self):
        theme = cp.parse_themes(SAMPLE)[0]
        self.assertEqual(cp.resolve_slug(theme), "notion-external-memory")

    def test_resolve_slug_falls_back_when_blank(self):
        theme = cp.parse_themes(SAMPLE)[3]  # slug 空欄の日本語タイトル
        resolved = cp.resolve_slug(theme)
        self.assertTrue(resolved.startswith("theme-"))
        self.assertEqual(resolved, cp.slugify(theme.title))

    def test_select_next_skips_rejected_and_done(self):
        nxt = cp.select_next(cp.parse_themes(SAMPLE))
        self.assertEqual(nxt.title, "Notionを外部記憶にしてAIを育てる")

    def test_select_next_includes_unconfirmed_auto(self):
        text = SAMPLE.replace(
            "| Notionを外部記憶にしてAIを育てる | 第二の脳 | 手動 | 採用 | 未着手 | notion-external-memory |",
            "| Notionを外部記憶にしてAIを育てる | 第二の脳 | 手動 | 採用 | 草稿済み | notion-external-memory |")
        nxt = cp.select_next(cp.parse_themes(text))
        self.assertEqual(nxt.title, "未確認の自動テーマ")

    def test_select_next_none_when_only_rejected_or_done(self):
        text = (
            "| テーマ名 | 種類 | 出所 | レビュー | 進捗 | slug |\n"
            "|---|---|---|---|---|---|\n"
            "| a | k | 自動 | 却下 | 未着手 | a |\n"
            "| b | k | 手動 | 採用 | 草稿済み | b |\n"
        )
        self.assertIsNone(cp.select_next(cp.parse_themes(text)))

    def test_draft_filename(self):
        self.assertEqual(
            cp.draft_filename(dt.date(2026, 6, 27), "abc"), "2026-06-27-abc.md")

    def test_render_generation_prompt_injects_theme(self):
        theme = cp.parse_themes(SAMPLE)[0]
        prompt = cp.render_generation_prompt(theme)
        self.assertIn("Notionを外部記憶にしてAIを育てる", prompt)
        self.assertIn("第二の脳", prompt)
        self.assertIn("1800〜2200字", prompt)

    def test_render_theme_prompt_embeds_existing(self):
        prompt = cp.render_theme_prompt(cp.parse_themes(SAMPLE), ["2026-06-01-x.md"])
        self.assertIn("Notionを外部記憶にしてAIを育てる", prompt)
        self.assertIn("2026-06-01-x.md", prompt)
        self.assertIn("除外リスト", prompt)

    def test_mark_done_flips_progress_and_keeps_slug(self):
        themes = cp.parse_themes(SAMPLE)
        updated = cp.mark_done(SAMPLE, themes[0])
        reparsed = {t.title: t for t in cp.parse_themes(updated)}
        done = reparsed["Notionを外部記憶にしてAIを育てる"]
        self.assertEqual(done.progress, "草稿済み")
        self.assertEqual(done.review, "採用")
        self.assertEqual(done.slug, "notion-external-memory")  # slug 列を保つ
        self.assertEqual(reparsed["未確認の自動テーマ"].progress, "未着手")

    def test_mark_done_idempotent(self):
        themes = cp.parse_themes(SAMPLE)
        once = cp.mark_done(SAMPLE, themes[0])
        twice = cp.mark_done(once, cp.parse_themes(once)[0])
        self.assertEqual(once, twice)

    def test_parse_theme_lines_handles_separators_and_bullets(self):
        text = (
            "- 失敗から学ぶデプロイ設計／失敗談\n"
            "2. 計測してから直す習慣 / 再現ノウハウ\n"
            "空行や雑音\n"
        )
        out = cp.parse_theme_lines(text)
        self.assertEqual(out[0], ("失敗から学ぶデプロイ設計", "失敗談"))
        self.assertEqual(out[1], ("計測してから直す習慣", "再現ノウハウ"))
        self.assertEqual(len(out), 2)

    def test_append_themes_adds_auto_unconfirmed_todo_with_blank_slug(self):
        new_text, added = cp.append_themes(SAMPLE, [("新テーマA", "設計思想")])
        self.assertEqual(added, 1)
        themes = {t.title: t for t in cp.parse_themes(new_text)}
        self.assertIn("新テーマA", themes)
        self.assertEqual(themes["新テーマA"].source, "自動")
        self.assertEqual(themes["新テーマA"].review, "未確認")
        self.assertEqual(themes["新テーマA"].progress, "未着手")
        self.assertEqual(themes["新テーマA"].slug, "")  # 自動補充は slug 空欄

    def test_append_themes_dedupes_existing_and_within_batch(self):
        new_text, added = cp.append_themes(SAMPLE, [
            ("却下されたやつ", "ノウハウ"),   # 既存 → 除外
            ("新テーマA", "設計思想"),
            ("新テーマA", "設計思想"),         # バッチ内重複 → 1回だけ
        ])
        self.assertEqual(added, 1)
        self.assertEqual(len(cp.parse_themes(new_text)), len(cp.parse_themes(SAMPLE)) + 1)


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
        self.assertEqual(
            cp.run(self.themes_path, self.drafts, mode="plan",
                   today=dt.date(2026, 6, 27)), 0)

    def test_empty_guard_when_no_eligible(self):
        with open(self.themes_path, "w", encoding="utf-8") as f:
            f.write(
                "| テーマ名 | 種類 | 出所 | レビュー | 進捗 | slug |\n"
                "|---|---|---|---|---|---|\n"
                "| a | k | 自動 | 却下 | 未着手 | a |\n")
        self.assertEqual(
            cp.run(self.themes_path, self.drafts, mode="plan",
                   today=dt.date(2026, 6, 27)), 0)

    def test_write_uses_slug_column_in_filename_and_marks_done(self):
        body_path = os.path.join(self.tmp.name, "body.md")
        with open(body_path, "w", encoding="utf-8") as f:
            f.write("# タイトル\n本文\n")
        rc = cp.run(self.themes_path, self.drafts, mode="write",
                    body_file=body_path, today=dt.date(2026, 6, 27))
        self.assertEqual(rc, 0)
        # slug 列が優先され、ファイル名が人手可読になる。
        self.assertTrue(os.path.exists(
            os.path.join(self.drafts, "2026-06-27-notion-external-memory.md")))
        # 進捗が更新され、次の select は別テーマ（未確認の自動テーマ）。
        with open(self.themes_path, encoding="utf-8") as f:
            nxt = cp.select_next(cp.parse_themes(f.read()))
        self.assertEqual(nxt.title, "未確認の自動テーマ")

    def test_write_dry_run_writes_nothing(self):
        body_path = os.path.join(self.tmp.name, "body.md")
        with open(body_path, "w", encoding="utf-8") as f:
            f.write("# x\n本文\n")
        before = open(self.themes_path, encoding="utf-8").read()
        rc = cp.run(self.themes_path, self.drafts, mode="write",
                    body_file=body_path, today=dt.date(2026, 6, 27), dry_run=True)
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.isdir(self.drafts))
        self.assertEqual(open(self.themes_path, encoding="utf-8").read(), before)

    def test_themes_plan_returns_zero(self):
        self.assertEqual(
            cp.run(self.themes_path, self.drafts, mode="themes-plan"), 0)

    def test_themes_add_appends_rows(self):
        tf = os.path.join(self.tmp.name, "new.md")
        with open(tf, "w", encoding="utf-8") as f:
            f.write("新テーマX／失敗談\n新テーマY／設計思想\n")
        rc = cp.run(self.themes_path, self.drafts, mode="themes-add",
                    themes_file=tf)
        self.assertEqual(rc, 0)
        titles = {t.title for t in cp.parse_themes(
            open(self.themes_path, encoding="utf-8").read())}
        self.assertIn("新テーマX", titles)
        self.assertIn("新テーマY", titles)

    def test_themes_add_dry_run_writes_nothing(self):
        tf = os.path.join(self.tmp.name, "new.md")
        with open(tf, "w", encoding="utf-8") as f:
            f.write("新テーマX／失敗談\n")
        before = open(self.themes_path, encoding="utf-8").read()
        rc = cp.run(self.themes_path, self.drafts, mode="themes-add",
                    themes_file=tf, dry_run=True)
        self.assertEqual(rc, 0)
        self.assertEqual(open(self.themes_path, encoding="utf-8").read(), before)

    def test_themes_add_requires_file(self):
        with self.assertRaises(cp.PipelineError):
            cp.run(self.themes_path, self.drafts, mode="themes-add")

    def test_main_returns_nonzero_on_error(self):
        self.assertEqual(
            cp.main(["--themes", os.path.join(self.tmp.name, "missing.md")]), 2)


if __name__ == "__main__":
    unittest.main()
