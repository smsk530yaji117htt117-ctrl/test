# -*- coding: utf-8 -*-
"""
しくみ1（継続監査）: audit_scan の検出ルールのテスト。
純関数（内容ルール／横断ルール／整形）をネットワーク・git なしで検証する。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools"))

import audit_scan as a


# ── 内容ルール ───────────────────────────────────────────────────────────────
def test_urlopen_without_timeout_flagged():
    f = a.scan_urlopen_timeout("x.py", "with urllib.request.urlopen(req) as r:\n    pass\n")
    assert len(f) == 1
    assert f[0].rule == "urlopen-timeout" and f[0].severity == "high"
    assert f[0].line == 1


def test_urlopen_with_timeout_ok():
    assert a.scan_urlopen_timeout("x.py", "urlopen(req, timeout=30)\n") == []


def test_urlopen_timeout_multiline_call_ok():
    text = "resp = urlopen(\n    req,\n    timeout=30,\n)\n"
    assert a.scan_urlopen_timeout("x.py", text) == []


def test_env_subscript_flagged_but_get_ok():
    bad = a.scan_env_subscript("x.py", 'k = os.environ["API_KEY"]\n')
    assert len(bad) == 1 and bad[0].rule == "env-subscript"
    assert a.scan_env_subscript("x.py", 'k = os.environ.get("API_KEY", "")\n') == []


def test_todo_markers():
    f = a.scan_todo_markers("x.py", "# TODO fix\n# FIXME later\nx = 1  # ok\n")
    assert {x.line for x in f} == {1, 2}
    assert all(x.rule == "todo-marker" for x in f)


# ── 横断ルール ───────────────────────────────────────────────────────────────
def test_untested_module_detection():
    impl = ["foo.py", "bar.py"]
    tests = ["import foo\n\ndef test_foo(): ..."]  # bar はどこからも import されない
    f = a.find_untested_modules(impl, tests)
    flagged = {x.file for x in f}
    assert "bar.py" in flagged
    assert "foo.py" not in flagged


def test_dead_func_detection():
    files = {
        "m.py": "def used():\n    return 1\n\ndef caller():\n    return used()\n\ndef orphan():\n    return 2\n",
    }
    f = a.find_possible_dead_funcs(files)
    names = {x.message.split("'")[1] for x in f}
    assert "orphan" in names    # 定義のみ・1回出現 → dead 候補
    assert "used" not in names  # caller から参照されている → 非 dead


def test_dead_func_ignores_main():
    files = {"m.py": "def main():\n    return 1\n"}
    assert a.find_possible_dead_funcs(files) == []


# ── 整形 ────────────────────────────────────────────────────────────────────
def test_render_markdown_empty():
    assert "検出なし" in a.render_markdown([], "test")


def test_render_markdown_table():
    out = a.render_markdown([a.Finding("x.py", 3, "high", "urlopen-timeout", "msg")], "test")
    assert "x.py:3" in out and "high" in out and "| severity |" in out


# ── 自己適用: スキャナ自身をかけても落ちない（スモーク） ─────────────────────────
def test_collect_findings_smoke():
    root = os.path.dirname(os.path.dirname(__file__))
    findings = a.collect_findings(root)
    assert isinstance(findings, list)
    # Finding dataclass の形を保っている
    for f in findings[:5]:
        assert hasattr(f, "rule") and hasattr(f, "severity")
