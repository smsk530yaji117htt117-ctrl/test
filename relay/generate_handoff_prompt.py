# -*- coding: utf-8 -*-
"""
relay/generate_handoff_prompt.py — SynthesisDecision → Handoff spec（純関数）

会議の Synthesis 解析結果から、AI Handoff DB に起票するための「仕様（spec）」と
executor 向けプロンプト本文を生成する。Notion I/O は一切行わない（テスト容易）。

型ごとの方針（docs/router_rules.md）:
- dev_task  : Execution Mode = Claude Code   / Task Type = 実装       / Handoff Reason = 実装依頼
- doc_task  : Execution Mode = Claude Code   / Task Type = ドキュメント / Handoff Reason = ドキュメント作成
- research  : Execution Mode = Deep Research / Task Type = 調査       / Handoff Reason = 深掘り調査
             （Task 先頭に「深掘り: 」を付ける）
- decision  : 起票しない想定（no_action）。複合の親など必要時は Handoff Reason = 人間判断
- composite : 親タスク（dev_task+doc_task の取りまとめ。実行順 doc→dev）

human_review_required（docs/HUMAN_REVIEW_REQUIRED_POLICY.md）:
- true  → Status = Draft（保留。executor 投入しない・起票のみ）
- false → Status = Ready
"""

from __future__ import annotations

# 型 → (Task Type ラベル, Execution Mode, Handoff Reason, タイトル接頭辞)
_TYPE_PROFILE: dict[str, tuple[str, str, str, str]] = {
    "dev_task":  ("実装",       "Claude Code",   "実装依頼",        "[Auto/dev_task] "),
    "doc_task":  ("ドキュメント", "Claude Code",   "ドキュメント作成", "[Auto/doc_task] "),
    "research":  ("調査",       "Deep Research", "深掘り調査",      "深掘り: "),
    "decision":  ("意思決定",    "—",            "人間判断",        "[Auto/decision] "),
    "composite": ("実装",       "Claude Code",   "実装依頼",        "[Auto/複合] "),
}

_TITLE_MAX = 120


def _title_base(decision) -> str:
    """結論の先頭1行をタイトル素材にする。空なら推奨成果物で代替。"""
    src = (decision.conclusion or decision.deliverable or "会議結果").strip()
    first = src.splitlines()[0].strip() if src else "会議結果"
    return first or "会議結果"


def _status_for(human_review_required: bool) -> str:
    return "Draft" if human_review_required else "Ready"


def build_prompt_text(decision, *, task_type: str, role: str) -> str:
    """executor 向けのプロンプト本文（Notes へ格納する人間可読テキスト）を生成する。"""
    secondary = ", ".join(decision.secondary_types) if decision.secondary_types else "なし"
    lines = [
        f"## 自動起票（会議→Handoff 接続 / {task_type} / role={role}）",
        "",
        "### 結論",
        decision.conclusion or "（記載なし）",
        "",
        "### 根拠",
        decision.grounds or "（記載なし）",
        "",
        "### リスク",
        decision.risks or "（記載なし）",
        "",
        "### 推奨アクション",
        decision.recommended_actions or "（記載なし）",
        "",
        "### 推奨成果物",
        decision.deliverable or "（記載なし）",
        "",
        "### ルーティング",
        f"- primary: {decision.primary_type}",
        f"- secondary: {secondary}",
        f"- next_route: {decision.next_route}",
        f"- human_review_required: {str(decision.human_review_required).lower()}",
    ]
    return "\n".join(lines)


def build_handoff_spec(decision, *, task_type: str, role: str = "single") -> dict:
    """
    SynthesisDecision から Handoff 起票用 spec（dict）を生成する。

    返り値のキー:
      task_title / status / task_type_label / execution_mode / handoff_reason /
      human_review_required / role / primary_type / secondary_types / next_route /
      notes / source_url
    """
    profile = _TYPE_PROFILE.get(task_type, _TYPE_PROFILE["dev_task"])
    type_label, exec_mode, handoff_reason, title_prefix = profile

    base = _title_base(decision)
    if role == "parent":
        title = f"[Auto/複合・親] {base}（実行順 doc→dev）"
        handoff_reason = "複合タスク取りまとめ"
    else:
        title = f"{title_prefix}{base}"
    title = title[:_TITLE_MAX]

    return {
        "task_title": title,
        "status": _status_for(decision.human_review_required),
        "task_type_label": type_label,
        "execution_mode": exec_mode,
        "handoff_reason": handoff_reason,
        "human_review_required": decision.human_review_required,
        "role": role,
        "primary_type": decision.primary_type,
        "secondary_types": list(decision.secondary_types),
        "next_route": decision.next_route,
        "notes": build_prompt_text(decision, task_type=task_type, role=role),
        "source_url": "",
    }
