#!/usr/bin/env python3
"""コンテンツ自動蓄積パイプライン — 生成／補充ルーティンの決定論パート。

役割（cloud-robust 方式）:
  このスクリプトは「どのテーマを次に書くか／草稿ファイル名／生成プロンプト／
  themes.md（台帳）の更新後テキスト」を**決定論的に**算出する planner。
  記事本文・新テーマの生成（LLM）と GitHub への commit は Cloud Routine 側の
  コネクタが行う（docs/content-pipeline-1.md）。本体は標準ライブラリのみ・
  外部依存なし・秘匿情報を扱わない。

設計方針（既存の health/*.py と統一）:
- 標準ライブラリのみ（外部 SDK なし）。
- 「対象0件なら即終了」ガード（対象テーマが無ければ何もせず return 0）。
- 冪等: 草稿済みは再生成しない／既存草稿は上書きしない／補充は重複名を足さない。
- 失敗時は静かに無視せず stderr へ出して非ゼロ終了する。
- `--dry-run` で書き込みなしに予定を確認できる。

themes.md は 6 列の Markdown テーブル:
  | テーマ名 | 種類 | 出所 | レビュー | 進捗 | slug |
- 出所:   手動 / 自動
- レビュー: 採用 / 未確認 / 却下（却下は記事生成で必ずスキップ＝暴走の停止）
- 進捗:   未着手 / 草稿済み
- slug:   草稿ファイル名用の英小文字ハイフン識別子。空欄ならタイトル由来へフォールバック

モード:
  plan        : 記事生成の次の1件（レビュー≠却下 かつ 進捗=未着手）と生成プロンプトを出力
  write       : --body-file の本文で草稿を書き出し、進捗を「草稿済み」に更新
  themes-plan : テーマ補充の生成プロンプト（既存テーマ・既存草稿名を埋め込み）を出力
  themes-add  : --themes-file の「テーマ名／種類」行を台帳へ追記（自動/未確認/未着手・重複名は除外）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
import re
import sys
from typing import NamedTuple

# JST 固定（コンテンツ枠は JST スケジュール）。stdlib のみで UTC+9 を作る。
JST = _dt.timezone(_dt.timedelta(hours=9))

# レビュー／進捗／出所の語彙。
SOURCE_MANUAL = "手動"
SOURCE_AUTO = "自動"
REVIEW_ADOPTED = "採用"
REVIEW_UNCONFIRMED = "未確認"
REVIEW_REJECTED = "却下"
PROGRESS_TODO = "未着手"
PROGRESS_DONE = "草稿済み"

# kit の「記事生成プロンプト」をそのまま定数化。
GENERATION_PROMPT_TEMPLATE = """あなたはnote記事の草稿を書く。以下のテーマで日本語のnote記事を1本書く。
制約：
- 文字数 1800〜2200字。
- 構成：リード（3〜4行で結論と引きを先出し）→ 見出し3〜5個（## ）→ まとめ → 最後にX誘導の1文。
- スマホ前提。2〜3文ごとに改行。箇条書きは適宜。
- 失敗談・具体例・再現できる学びを優先し、一般論は避ける。
- 一人称、思想型・設計型のトーン。
- 数値や事実は、確証がなければ「一例」と明記する（捏造しない）。
出力：markdown本文のみ（先頭の # がタイトル）。
テーマ：{title}／種類：{kind}"""

# kit の「テーマ生成プロンプト」。{themes}/{drafts} に既存一覧を差し込む。
THEME_PROMPT_TEMPLATE = """PersonalOS（AIと会話するだけで仕事・投資・減量・開発の判断をまわす個人OS）の開発知見から、note向けの新テーマを5件出す。
条件：
- 既存テーマ・既存草稿・下の除外リストと重複しないこと。
- 種類は 失敗談／再現ノウハウ／設計思想／ビフォーアフター のいずれか。
- 固有の実体験に紐づくこと。一般論・汎用ツール紹介は除外。
出力：1行1テーマで「テーマ名／種類」のみ、5件。
除外リスト（既に作成/公開済み・再生成しない）：3社AI合議で意思決定、Cloud Routines 3連敗→動く根拠ルール、AIに任せる/人間が判断を残す線引き。

既存テーマ（themes.md）:
{themes}

既存草稿（ファイル名一覧）:
{drafts}"""

ALLOWED_KINDS_AUTO = {"失敗談", "再現ノウハウ", "設計思想", "ビフォーアフター"}


class PipelineError(Exception):
    """回復不能なエラー（呼び出し側で非ゼロ終了に変換する）。"""


class Theme(NamedTuple):
    title: str
    kind: str
    source: str
    review: str
    progress: str
    slug: str  # 草稿ファイル名用。空欄ならタイトル由来へフォールバック
    line_no: int  # themes.md 内の0始まり行番号（テーブル行のみ）


# ----------------------------- 純粋ロジック ----------------------------- #

def jst_today(now: _dt.datetime | None = None) -> _dt.date:
    """JST の今日の日付。テストでは now を注入する。"""
    now = now or _dt.datetime.now(JST)
    return now.astimezone(JST).date()


def slugify(title: str) -> str:
    """草稿ファイル名用の ascii slug。日本語など ascii 化できない場合は安定ハッシュ。"""
    s = title.strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if s:
        return s
    # ascii 成分が無いタイトル（日本語のみ）はタイトル由来の安定ハッシュに退避。
    digest = hashlib.sha1(title.strip().encode("utf-8")).hexdigest()[:8]
    return f"theme-{digest}"


def resolve_slug(theme: Theme) -> str:
    """ファイル名用 slug。台帳の slug 列を優先し、空欄のみタイトル由来へフォールバック。"""
    explicit = theme.slug.strip()
    return explicit if explicit else slugify(theme.title)


def _is_table_row(line: str) -> bool:
    """データ行（ヘッダ・区切り行・非テーブル行を除く）か判定する。"""
    st = line.strip()
    if not st.startswith("|"):
        return False
    if "テーマ名" in st and "種類" in st:  # ヘッダ
        return False
    if set(st) <= set("|-: "):  # 区切り行 |---|---|
        return False
    return True


def _cells(line: str) -> list[str]:
    """`| a | b |` を ['a','b'] に。両端の空セルを落とす。"""
    parts = [c.strip() for c in line.strip().strip("|").split("|")]
    return parts


def parse_themes(text: str) -> list[Theme]:
    """themes.md のテーブル行を Theme に変換する。タイトル重複は重複防止を壊すので拒否。"""
    themes: list[Theme] = []
    seen: set[str] = set()
    for i, line in enumerate(text.splitlines()):
        if not _is_table_row(line):
            continue
        cells = _cells(line)
        if len(cells) != 6:
            raise PipelineError(f"テーブル行の列数が6ではありません（行{i}）: {line!r}")
        title, kind, source, review, progress, slug = cells
        if title in seen:
            raise PipelineError(f"テーマ名が重複しています: {title}")
        seen.add(title)
        themes.append(Theme(title, kind, source, review, progress, slug, i))
    return themes


def select_next(themes: list[Theme]) -> Theme | None:
    """記事生成の対象: レビュー≠却下 かつ 進捗=未着手 の先頭行。無ければ None。"""
    for t in themes:
        if t.review != REVIEW_REJECTED and t.progress == PROGRESS_TODO:
            return t
    return None


def draft_filename(date: _dt.date, slug: str) -> str:
    """草稿ファイル名 YYYY-MM-DD-slug.md。"""
    return f"{date.isoformat()}-{slug}.md"


def render_generation_prompt(theme: Theme) -> str:
    """記事生成プロンプトにテーマ名・種類を埋め込む。"""
    return GENERATION_PROMPT_TEMPLATE.format(title=theme.title, kind=theme.kind)


def render_theme_prompt(themes: list[Theme], draft_filenames: list[str]) -> str:
    """テーマ補充プロンプトに既存テーマ・既存草稿名を埋め込む。"""
    themes_block = "\n".join(f"- {t.title}／{t.kind}" for t in themes) or "（なし）"
    drafts_block = "\n".join(f"- {n}" for n in sorted(draft_filenames)) or "（なし）"
    return THEME_PROMPT_TEMPLATE.format(themes=themes_block, drafts=drafts_block)


def _row(title: str, kind: str, source: str, review: str, progress: str,
         slug: str) -> str:
    return f"| {title} | {kind} | {source} | {review} | {progress} | {slug} |"


def mark_done(text: str, theme: Theme) -> str:
    """該当行の進捗を「草稿済み」に更新する。既に草稿済みなら不変（冪等）。slug 列は保つ。"""
    lines = text.splitlines(keepends=True)
    if not 0 <= theme.line_no < len(lines):
        raise PipelineError("テーマ行番号が範囲外です（themes.md が変化した可能性）")
    eol = "\n" if lines[theme.line_no].endswith("\n") else ""
    lines[theme.line_no] = _row(
        theme.title, theme.kind, theme.source, theme.review, PROGRESS_DONE,
        theme.slug) + eol
    return "".join(lines)


def parse_theme_lines(text: str) -> list[tuple[str, str]]:
    """LLM 出力「テーマ名／種類」を (title, kind) のリストに。全角／半角スラッシュ両対応。"""
    out: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("-・*0123456789.)　 ").strip()
        if not line:
            continue
        parts = re.split(r"[／/]", line, maxsplit=1)
        if len(parts) != 2:
            continue
        title, kind = parts[0].strip(), parts[1].strip()
        if title and kind:
            out.append((title, kind))
    return out


def append_themes(text: str, new_themes: list[tuple[str, str]]) -> tuple[str, int]:
    """新テーマを「自動/未確認/未着手」で台帳末尾（最後のテーブル行の直後）に追記する。

    既存タイトル・追記内での重複は除外（冪等）。戻り値 = (新テキスト, 追記件数)。
    """
    existing = parse_themes(text)
    seen = {t.title for t in existing}
    if not existing:
        raise PipelineError("テーブル行が見つかりません（themes.md の形式を確認）")
    rows: list[str] = []
    for title, kind in new_themes:
        if title in seen:
            continue
        seen.add(title)
        # 自動補充は slug 空欄（ファイル名生成時にタイトル由来へフォールバック）。
        rows.append(_row(title, kind, SOURCE_AUTO, REVIEW_UNCONFIRMED, PROGRESS_TODO, ""))
    if not rows:
        return text, 0
    lines = text.splitlines(keepends=True)
    insert_at = existing[-1].line_no  # 最後のテーブル行
    has_eol = lines[insert_at].endswith("\n")
    block = ("" if has_eol else "\n") + "".join(r + "\n" for r in rows)
    lines[insert_at] = lines[insert_at] + block
    return "".join(lines), len(rows)


# ----------------------------- IO / driver ----------------------------- #

def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise PipelineError(f"読み込み失敗: {path}: {e}") from None


def _write(path: str, content: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        raise PipelineError(f"書き込み失敗: {path}: {e}") from None


def _list_drafts(drafts_dir: str) -> list[str]:
    try:
        return [n for n in os.listdir(drafts_dir)
                if n.endswith(".md") and not n.startswith("_")]
    except FileNotFoundError:
        return []


def run(themes_path: str, drafts_dir: str, mode: str = "plan",
        body_file: str | None = None, themes_file: str | None = None,
        today: _dt.date | None = None, dry_run: bool = False) -> int:
    today = today or jst_today()
    themes = parse_themes(_read(themes_path))

    # ---- テーマ補充（Step 3）----
    if mode == "themes-plan":
        print("[themes-plan] テーマ補充プロンプト ↓↓↓")
        print(render_theme_prompt(themes, _list_drafts(drafts_dir)))
        return 0

    if mode == "themes-add":
        if not themes_file:
            raise PipelineError("themes-add モードには --themes-file が必要です")
        candidates = parse_theme_lines(_read(themes_file))
        if not candidates:
            raise PipelineError("追記候補テーマを1件も解釈できませんでした")
        new_text, added = append_themes(_read(themes_path), candidates)
        if added == 0:
            print("[skip] 追記すべき新テーマがありません（全て重複）")
            return 0
        if dry_run:
            print(f"[dry-run] {added}件を台帳へ追記予定（自動/未確認/未着手）")
            return 0
        _write(themes_path, new_text)
        print(f"[ok] {added}件を台帳へ追記しました（自動/未確認/未着手）")
        return 0

    # ---- 記事生成（Step 2）----
    theme = select_next(themes)
    if theme is None:
        print("[skip] 対象テーマがありません（レビュー≠却下 かつ 未着手 が0件 → 即終了）")
        return 0

    fname = draft_filename(today, resolve_slug(theme))
    draft_path = os.path.join(drafts_dir, fname)
    prompt = render_generation_prompt(theme)

    if mode == "plan":
        print(f"[plan] 次のテーマ: {theme.title}（種類: {theme.kind} / レビュー: {theme.review}）")
        print(f"[plan] 草稿パス: {draft_path}")
        print("[plan] 記事生成プロンプト ↓↓↓")
        print(prompt)
        return 0

    if mode == "write":
        if not body_file:
            raise PipelineError("write モードには --body-file が必要です")
        body = _read(body_file).strip()
        if not body:
            raise PipelineError("生成本文が空です（草稿を書き出しません）")
        if os.path.exists(draft_path):
            print(f"[skip] 既に存在します（冪等）: {draft_path}")
            return 0
        if dry_run:
            print(f"[dry-run] 書き出し予定: {draft_path}（{len(body)}字）")
            print(f"[dry-run] 進捗を草稿済みに更新予定: {theme.title}")
            return 0
        os.makedirs(drafts_dir, exist_ok=True)
        _write(draft_path, body + "\n")
        _write(themes_path, mark_done(_read(themes_path), theme))
        print(f"[ok] 草稿を書き出し進捗を更新しました: {draft_path}")
        return 0

    raise PipelineError(f"不明なモード: {mode}")


def main(argv: list[str] | None = None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="コンテンツ自動蓄積パイプライン planner")
    parser.add_argument("--themes", default=os.path.join(here, "themes.md"),
                        help="テーマ台帳ファイル（既定: content/themes.md）")
    parser.add_argument("--drafts-dir", default=os.path.join(here, "drafts"),
                        help="草稿ディレクトリ（既定: content/drafts）")
    parser.add_argument("--mode",
                        choices=["plan", "write", "themes-plan", "themes-add"],
                        default="plan",
                        help="plan/write=記事生成 / themes-plan/themes-add=テーマ補充")
    parser.add_argument("--body-file", help="write モードで使う記事本文ファイル")
    parser.add_argument("--themes-file",
                        help="themes-add モードで使う「テーマ名／種類」行ファイル")
    parser.add_argument("--dry-run", action="store_true",
                        help="書き込まず予定のみ表示")
    args = parser.parse_args(argv)
    try:
        return run(args.themes, args.drafts_dir, mode=args.mode,
                   body_file=args.body_file, themes_file=args.themes_file,
                   dry_run=args.dry_run)
    except PipelineError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
