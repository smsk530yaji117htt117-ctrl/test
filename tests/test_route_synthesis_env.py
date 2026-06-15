# -*- coding: utf-8 -*-
"""
consensus.route_synthesis_result の env / 例外ハンドリングのテスト（requirement 2）

検証項目:
- ENABLE_MEETING_ROUTING 未設定時は dry-run を維持する（実起票しない既定）。
- 真値が設定されたときだけ dry_run=False（起票実行）になる。
- ルーティングで例外が起きても合議ループへ伝播させない（再送出しない）が、
  握りつぶさず必ず記録（ログ出力）する。記録時に API キーはマスクする。

ルーティング本体（route_meeting_result）は monkeypatch で差し替え、
consensus.py 本体の挙動（既定 dry-run・例外で合議を止めない）だけを検証する。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import consensus
import meeting_result_processor as mrp
from meeting_result_processor import RoutingResult, SynthesisDecision

_SAMPLE = (
    "### 結論\n結論\n### タイプ判定\nprimary: dev_task\nsecondary: なし\n"
    "### Human Review Required\nfalse\n### Next Route\ncreate_handoff\n"
)


def _capturing_route(captured):
    """route_meeting_result の代役。dry_run 等を捕捉し、最小の RoutingResult を返す。"""
    def fake(text, *, source_url="", dry_run=True, **kwargs):
        captured["dry_run"] = dry_run
        captured["source_url"] = source_url
        captured["text"] = text
        return RoutingResult(
            decision=SynthesisDecision(primary_type="dev_task"),
            actions=[],
            dry_run=dry_run,
        )
    return fake


# ── env: 未設定なら dry-run 維持 ──────────────────────────────────────────────

def test_dry_run_maintained_when_env_unset(monkeypatch):
    monkeypatch.delenv("ENABLE_MEETING_ROUTING", raising=False)
    captured = {}
    monkeypatch.setattr(mrp, "route_meeting_result", _capturing_route(captured))

    consensus.route_synthesis_result(_SAMPLE, source_page_id="abc123def456")

    assert captured["dry_run"] is True
    # source_page_id から Notion URL が組み立てられて渡る
    assert captured["source_url"].endswith("abc123def456")


def test_dry_run_maintained_when_env_falsey(monkeypatch):
    # 0 / false / 空 などは偽 → dry-run 維持
    for val in ("", "0", "false", "no", "off"):
        monkeypatch.setenv("ENABLE_MEETING_ROUTING", val)
        captured = {}
        monkeypatch.setattr(mrp, "route_meeting_result", _capturing_route(captured))
        consensus.route_synthesis_result(_SAMPLE)
        assert captured["dry_run"] is True, f"value={val!r} で dry-run が解除された"


def test_live_when_env_truthy(monkeypatch):
    # 1 / true / yes / on は真 → 起票実行（dry_run=False）
    for val in ("1", "true", "yes", "on", "TRUE", " On "):
        monkeypatch.setenv("ENABLE_MEETING_ROUTING", val)
        captured = {}
        monkeypatch.setattr(mrp, "route_meeting_result", _capturing_route(captured))
        consensus.route_synthesis_result(_SAMPLE)
        assert captured["dry_run"] is False, f"value={val!r} で起票実行にならない"


# ── 例外: 握りつぶさず記録、ただし合議ループは止めない ────────────────────────

def test_exception_is_recorded_and_not_raised(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise RuntimeError("ルート計画に失敗しました")

    monkeypatch.setattr(mrp, "route_meeting_result", boom)

    # 例外は呼び出し側へ伝播しない（合議ループを止めない）
    consensus.route_synthesis_result(_SAMPLE, source_page_id="abc")

    out = capsys.readouterr().out
    # 握りつぶさず記録されている（ログに skip と例外内容が残る）
    assert "ルーティングskip" in out
    assert "ルート計画に失敗しました" in out


def test_exception_record_masks_secrets(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise RuntimeError("認証失敗 token=sk-ant-abcDEF123456")

    monkeypatch.setattr(mrp, "route_meeting_result", boom)
    consensus.route_synthesis_result(_SAMPLE)

    out = capsys.readouterr().out
    # 記録はするが API キーは生で出さない（マスク済み）
    assert "sk-ant-abcDEF123456" not in out
    assert "sk-ant-***" in out


def test_env_truthy_helper():
    # _env_truthy の真偽判定（境界）
    assert consensus._env_truthy("1") is True
    assert consensus._env_truthy("true") is True
    assert consensus._env_truthy(" On ") is True
    assert consensus._env_truthy(None) is False
    assert consensus._env_truthy("0") is False
    assert consensus._env_truthy("maybe") is False
