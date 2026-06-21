# -*- coding: utf-8 -*-
"""
audit_scan — コード差分から監査項目を再生成する静的スキャナ（LLM不要・決定論的）。

改善エンジンの「燃料の自動補充」（しくみ1）。既存の read-only 監査
（research/code_audit.md）で繰り返し挙がった負債パターンを機械的に検出し、
監査項目を再生成する。差分モード（--since <ref>）で変更ファイルだけを監査でき、
Dispatcher 等から「変更検知→監査差分追記」に組み込める（ルーチン化は人間承認後）。

検出ルール:
  A urlopen-timeout : urlopen(...) に timeout= が無い（hot path のソケットハング）
  B env-subscript   : os.environ[...] の直接添字（未設定で KeyError / fail-fast 不整合）
  C todo-marker     : TODO / FIXME / HACK / XXX
  D untested-module : tests/ から import されていない実装モジュール（テスト欠落）
  E dead-func       : 定義以外にリポジトリ全体で参照されない関数（dead code 候補）

使い方:
  python tools/audit_scan.py                  # リポジトリ全体を監査して Markdown 出力
  python tools/audit_scan.py --since <gitref>  # 変更ファイルのみ（差分監査）
  python tools/audit_scan.py --format json     # JSON 出力
  python tools/audit_scan.py --fail-on high     # 指定 severity 以上があれば exit 1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict

SEVERITY_ORDER = {"low": 0, "med": 1, "high": 2}


@dataclass
class Finding:
    file: str
    line: int
    severity: str
    rule: str
    message: str


# ── 純関数: 1ファイルの内容に対する検出 ──────────────────────────────────────────

def _arg_string_after(text: str, open_paren_idx: int) -> str:
    """open_paren_idx は '(' の位置。対応する ')' までの引数文字列を返す。"""
    depth = 0
    out = []
    for ch in text[open_paren_idx:]:
        out.append(ch)
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                break
    return "".join(out)


def scan_urlopen_timeout(path: str, text: str) -> list[Finding]:
    findings = []
    for m in re.finditer(r"urlopen\s*\(", text):
        paren = text.index("(", m.start())
        args = _arg_string_after(text, paren)
        if "timeout" not in args:
            line = text.count("\n", 0, m.start()) + 1
            findings.append(Finding(path, line, "high", "urlopen-timeout",
                                    "urlopen に timeout= が無い（ソケットハングで処理枠を食い潰す）"))
    return findings


def scan_env_subscript(path: str, text: str) -> list[Finding]:
    findings = []
    for m in re.finditer(r"os\.environ\[", text):
        line = text.count("\n", 0, m.start()) + 1
        findings.append(Finding(path, line, "med", "env-subscript",
                                "os.environ[...] 直接添字（未設定で KeyError／.get + 明示エラー推奨）"))
    return findings


def scan_todo_markers(path: str, text: str) -> list[Finding]:
    findings = []
    for m in re.finditer(r"\b(TODO|FIXME|HACK|XXX)\b", text):
        line = text.count("\n", 0, m.start()) + 1
        findings.append(Finding(path, line, "low", "todo-marker",
                                f"{m.group(1)} マーカー（未完の作業）"))
    return findings


CONTENT_RULES = [scan_urlopen_timeout, scan_env_subscript, scan_todo_markers]


def scan_text(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for rule in CONTENT_RULES:
        findings.extend(rule(path, text))
    return findings


# ── 純関数: リポジトリ横断の検出 ─────────────────────────────────────────────────

def find_untested_modules(impl_files: list[str], test_texts: list[str]) -> list[Finding]:
    """tests/ のどこからも import されていない実装モジュールを検出する。"""
    findings = []
    joined = "\n".join(test_texts)
    for path in impl_files:
        mod = os.path.basename(path)[:-3]  # strip .py
        if mod in {"__init__"}:
            continue
        if not re.search(rf"\b{re.escape(mod)}\b", joined):
            findings.append(Finding(path, 0, "med", "untested-module",
                                    f"モジュール '{mod}' を import するテストが tests/ に見当たらない"))
    return findings


def find_possible_dead_funcs(files_text: dict[str, str]) -> list[Finding]:
    """定義以外にリポジトリ全体で参照されない関数（dead code 候補）。

    保守的に: 当該名がリポジトリ全体で1回（=定義のみ）しか出現しないトップレベル関数。
    main / 公開エントリ等の誤検出を避けるため除外名を設ける。
    """
    ignore = {"main"}
    all_text = "\n".join(files_text.values())
    findings = []
    for path, text in files_text.items():
        for m in re.finditer(r"^def\s+([A-Za-z_]\w*)\s*\(", text, re.MULTILINE):
            name = m.group(1)
            if name in ignore or name.startswith("__"):
                continue
            if len(re.findall(rf"\b{re.escape(name)}\b", all_text)) <= 1:
                line = text.count("\n", 0, m.start()) + 1
                findings.append(Finding(path, line, "low", "dead-func",
                                        f"関数 '{name}' は定義以外で参照されていない（dead code 候補）"))
    return findings


# ── ファイル収集 / git ───────────────────────────────────────────────────────────

def list_py_files(root: str) -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in {"venv", ".venv", ".git", "__pycache__", "node_modules"}]
        for fn in filenames:
            if fn.endswith(".py"):
                out.append(os.path.relpath(os.path.join(dirpath, fn), root).replace("\\", "/"))
    return sorted(out)


def changed_py_files(root: str, since_ref: str) -> list[str]:
    res = subprocess.run(["git", "diff", "--name-only", f"{since_ref}...HEAD"],
                         cwd=root, capture_output=True, text=True)
    files = [f.strip() for f in res.stdout.splitlines() if f.strip().endswith(".py")]
    return [f for f in files if os.path.exists(os.path.join(root, f))]


def is_test_file(path: str) -> bool:
    return "/test" in f"/{path}" or path.startswith("tests/") or "/tests/" in path


# ── オーケストレーション ─────────────────────────────────────────────────────────

def collect_findings(root: str, since_ref: str | None = None) -> list[Finding]:
    all_py = list_py_files(root)
    targets = changed_py_files(root, since_ref) if since_ref else all_py

    files_text: dict[str, str] = {}
    for path in all_py:
        try:
            files_text[path] = open(os.path.join(root, path), encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            files_text[path] = ""

    findings: list[Finding] = []
    # 内容ルールは対象（差分 or 全体）に適用
    for path in targets:
        findings.extend(scan_text(path, files_text.get(path, "")))

    # 横断ルールは常にリポジトリ全体で評価（差分でも全体整合を見る）
    impl_files = [p for p in all_py if not is_test_file(p)]
    test_texts = [t for p, t in files_text.items() if is_test_file(p)]
    findings.extend(find_untested_modules(impl_files, test_texts))
    findings.extend(find_possible_dead_funcs({p: files_text[p] for p in impl_files}))

    findings.sort(key=lambda f: (-SEVERITY_ORDER.get(f.severity, 0), f.file, f.line))
    return findings


def render_markdown(findings: list[Finding], scope: str) -> str:
    lines = [f"# 監査スキャン結果（{scope}）", ""]
    if not findings:
        lines.append("検出なし。")
        return "\n".join(lines)
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    summary = " / ".join(f"{s}: {counts.get(s, 0)}" for s in ("high", "med", "low"))
    lines += [f"合計 {len(findings)} 件（{summary}）", "",
              "| severity | rule | file:line | message |",
              "|---|---|---|---|"]
    for f in findings:
        loc = f"{f.file}:{f.line}" if f.line else f.file
        lines.append(f"| {f.severity} | {f.rule} | {loc} | {f.message} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="静的監査スキャナ（差分対応）")
    parser.add_argument("--since", help="この git ref からの変更ファイルのみ内容監査する")
    parser.add_argument("--root", default=os.getcwd(), help="リポジトリルート")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--fail-on", choices=["low", "med", "high"],
                        help="指定 severity 以上の検出で exit 1")
    args = parser.parse_args(argv)

    findings = collect_findings(args.root, args.since)
    scope = f"差分: {args.since}...HEAD" if args.since else "リポジトリ全体"

    if args.format == "json":
        print(json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2))
    else:
        print(render_markdown(findings, scope))

    if args.fail_on:
        threshold = SEVERITY_ORDER[args.fail_on]
        if any(SEVERITY_ORDER.get(f.severity, 0) >= threshold for f in findings):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
