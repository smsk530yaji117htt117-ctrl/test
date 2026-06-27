#!/usr/bin/env python3
"""コンテンツ自動蓄積パイプライン — 生成ルーティンの決定論パート。

役割（cloud-robust 方式）:
  このスクリプトは「どのテーマを次に書くか／草稿ファイル名／生成プロンプト／
  themes.md の更新後テキスト」を**決定論的に**算出する planner。記事本文の生成
  （LLM）と GitHub への commit は Cloud Routine 側のコネクタが行う(docs参照)。
  本体は標準ライブラリのみ・外部依存なし・秘匿情報を扱わない。

設計方針（既存の health/*.py と統一）:
- 標準ライブラリのみ（外部 SDK なし）。
- 「対象0件なら即終了」ガード（未着手テーマが無ければ何もせず return 0）。
- 冪等: 草稿済みテーマは再生成しない（themes.md の `[x]` で判定）。
- 失敗時は静かに無視せず stderr へ出して非ゼロ終了する。
- `--dry-run` で書き込みなしに「次に生成する1件」と生成プロンプトを確認できる。

実行モード:
  plan  (既定): 次のテーマを選び、生成プロンプトと草稿パスを出力する。
  write       : `--body-file` の本文で草稿を書き出し、themes.md を草稿済みに更新する。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import sys
from typing import NamedTuple

# JST 固定（コンテンツ枠は JST スケジュール）。stdlib のみで UTC+9 を作る。
JST = _dt.timezone(_dt.timedelta(hours=9))

THEME_LINE_RE = re.compile(
    r"^- \[(?P<done>[ xX])\]\s*(?P<title>.+?)"
    r"｜種類:\s*(?P<kind>.+?)"
    r"｜slug:\s*(?P<slug>[a-z0-9][a-z0-9-]*)"
    r"(?:｜draft:\s*(?P<draft>\S+))?\s*$"
)

# kit の「生成プロンプト（ルーティンに埋め込む本文）」をそのまま定数化。
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


class PipelineError(Exception):
    """回復不能なエラー（呼び出し側で非ゼロ終了に変換する）。"""


class Theme(NamedTuple):
    title: str
    kind: str
    slug: str
    done: bool
    draft: str | None
    line_no: int  # themes.md 内の0始まり行番号


# ----------------------------- 純粋ロジック ----------------------------- #

def jst_today(now: _dt.datetime | None = None) -> _dt.date:
    """JST の今日の日付。テストでは now を注入する。"""
    now = now or _dt.datetime.now(JST)
    return now.astimezone(JST).date()


def slugify(text: str) -> str:
    """ascii slug を正規化する。日本語など ascii 外は明示 slug が必要なので拒否。"""
    s = text.strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if not s:
        raise PipelineError(f"ascii slug を生成できません: {text!r}（明示 slug が必要）")
    return s


def parse_themes(text: str) -> list[Theme]:
    """themes.md 本文からテーマ行を抽出する。slug 重複は冪等性を壊すので拒否。"""
    themes: list[Theme] = []
    seen_slugs: set[str] = set()
    for i, line in enumerate(text.splitlines()):
        m = THEME_LINE_RE.match(line)
        if not m:
            continue
        slug = m.group("slug")
        if slug in seen_slugs:
            raise PipelineError(f"slug が重複しています: {slug}")
        seen_slugs.add(slug)
        themes.append(Theme(
            title=m.group("title").strip(),
            kind=m.group("kind").strip(),
            slug=slug,
            done=m.group("done").lower() == "x",
            draft=m.group("draft"),
            line_no=i,
        ))
    return themes


def select_next(themes: list[Theme]) -> Theme | None:
    """先頭から最初の未着手テーマを返す。全て草稿済みなら None。"""
    for t in themes:
        if not t.done:
            return t
    return None


def draft_filename(date: _dt.date, slug: str) -> str:
    """草稿ファイル名 YYYY-MM-DD-slug.md。"""
    return f"{date.isoformat()}-{slug}.md"


def render_generation_prompt(theme: Theme) -> str:
    """kit の生成プロンプトにテーマ名・種類を埋め込む。"""
    return GENERATION_PROMPT_TEMPLATE.format(title=theme.title, kind=theme.kind)


def mark_done(text: str, theme: Theme, draft_name: str) -> str:
    """themes.md 本文の該当行を草稿済み `[x]` に更新し draft 名を追記する。

    既に草稿済みなら変更しない（冪等）。
    """
    lines = text.splitlines(keepends=True)
    if not 0 <= theme.line_no < len(lines):
        raise PipelineError("テーマ行番号が範囲外です（themes.md が変化した可能性）")
    new_line = (
        f"- [x] {theme.title}｜種類: {theme.kind}｜slug: {theme.slug}"
        f"｜draft: {draft_name}"
    )
    # 元行の改行を保つ。
    eol = "\n" if lines[theme.line_no].endswith("\n") else ""
    lines[theme.line_no] = new_line + eol
    return "".join(lines)


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


def run(themes_path: str, drafts_dir: str, mode: str = "plan",
        body_file: str | None = None, today: _dt.date | None = None,
        dry_run: bool = False) -> int:
    today = today or jst_today()
    themes = parse_themes(_read(themes_path))
    theme = select_next(themes)

    # 「対象0件なら即終了」ガード（既存ルーティンと統一）。
    if theme is None:
        print("[skip] 未着手のテーマがありません（対象0件 → 即終了）")
        return 0

    fname = draft_filename(today, theme.slug)
    draft_path = os.path.join(drafts_dir, fname)
    prompt = render_generation_prompt(theme)

    if mode == "plan":
        print(f"[plan] 次のテーマ: {theme.title}（種類: {theme.kind}）")
        print(f"[plan] 草稿パス: {draft_path}")
        print("[plan] 生成プロンプト ↓↓↓")
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
            print(f"[dry-run] themes.md を草稿済みに更新予定: {theme.slug}")
            return 0
        os.makedirs(drafts_dir, exist_ok=True)
        _write(draft_path, body + "\n")
        _write(themes_path, mark_done(_read(themes_path), theme, fname))
        print(f"[ok] 草稿を書き出し themes を更新しました: {draft_path}")
        return 0

    raise PipelineError(f"不明なモード: {mode}")


def main(argv: list[str] | None = None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="コンテンツ自動蓄積パイプライン planner")
    parser.add_argument("--themes", default=os.path.join(here, "themes.md"),
                        help="テーマ在庫ファイル（既定: content/themes.md）")
    parser.add_argument("--drafts-dir", default=os.path.join(here, "drafts"),
                        help="草稿出力ディレクトリ（既定: content/drafts）")
    parser.add_argument("--mode", choices=["plan", "write"], default="plan",
                        help="plan=次の1件と生成プロンプト / write=本文を書き出し")
    parser.add_argument("--body-file", help="write モードで使う生成本文ファイル")
    parser.add_argument("--dry-run", action="store_true",
                        help="write モードで書き込まず予定のみ表示")
    args = parser.parse_args(argv)
    try:
        return run(args.themes, args.drafts_dir, mode=args.mode,
                   body_file=args.body_file, dry_run=args.dry_run)
    except PipelineError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
