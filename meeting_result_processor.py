# -*- coding: utf-8 -*-
"""
meeting_result_processor.py — 会議（AI合議）結果 → Handoff 自動接続

consensus.py が出力した Synthesis テキスト（8セクション構造）を解析し、
型判定ルーティング規則（docs/router_rules.md）に従って次工程へ振り分ける。

依存は標準ライブラリのみ。実際の Notion 起票は relay/create_handoff_page.py
に委譲する（このモジュールは「解析＋ルート決定＋オーケストレーション」に集中）。

ルート規則（docs/router_rules.md）:
- dev_task  → create_handoff   （Handoff 起票 / Execution Mode: Claude Code）
- doc_task  → create_doc       （別ループ・非同期。合議ループには入れない）
- decision  → no_action        （起票せず人間に判断提示。Handoff Reason=人間判断）
- research  → research_more    （Task 先頭に「深掘り:」/ Execution Mode: Deep Research）
- dev_task + doc_task 複合 → 親1 + 子2（実行順 doc→dev）

human_review_required（docs/HUMAN_REVIEW_REQUIRED_POLICY.md）:
- 起票は常に自動でよい。gate は実行（executor 投入・PR merge）側。
- true → Status=Draft（保留）。false → Status=Ready。
- 曖昧・未記載は安全側に倒して true。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Callable

from relay.generate_handoff_prompt import build_handoff_spec

# ─── ルート規則（型 → next_route）────────────────────────────────────────────
ROUTER_RULES: dict[str, str] = {
    "dev_task": "create_handoff",
    "doc_task": "create_doc",
    "decision": "no_action",
    "research": "research_more",
}
VALID_TYPES = tuple(ROUTER_RULES.keys())
VALID_ROUTES = ("create_handoff", "create_doc", "no_action", "research_more")

# Next Route に複数候補が混在したとき（LLM がメニューを丸写し / 両論併記した等）に
# 適用する「決定的な優先順位」。VALID_ROUTES のタプル宣言順（＝偶発的な順序）に
# 判定が引きずられる順序バイアスを排し、入力中のトークン出現順にも依存させない。
# 安全側（起票しない・可逆＝人手判断や別ループ）を上位に固定する。
_ROUTE_PRIORITY = ("no_action", "create_doc", "research_more", "create_handoff")

# 曖昧・未記載時の human_review_required 既定値（安全側 = true）
DEFAULT_HUMAN_REVIEW_REQUIRED = True

# 起票を伴うルート（no_action / research_more の扱いは下記参照）
#   create_handoff … Handoff DB に起票
#   create_doc     … 別ループ（合議ループに入れない）。複合の子としてのみ起票
#   research_more  … 深掘り Handoff として起票
#   no_action      … 起票しない（人間へ判断提示）
_ROUTES_THAT_CREATE = {"create_handoff", "research_more"}

# 二重起票防止（idempotency）の既定登録簿。
#   同一 synthesis（＋起票元 source_url）から会議/Handoff を二重に起票しないための
#   プロセス内ガード。consensus.py 側の Status ベースの重複防止フラグ
#   （try_claim_page = 楽観ロック）を補完する多層防御として働く。
#   呼び出し側／テストは route_meeting_result(..., dedup_store=...) で任意の集合を
#   注入でき、その場合この既定登録簿は使わない。
_SEEN_FINGERPRINTS: set[str] = set()


def _synthesis_fingerprint(text: str, source_url: str = "") -> str:
    """synthesis 本文＋起票元から二重起票判定用の安定指紋（sha256）を作る。

    空白のゆらぎ（末尾改行・連続スペース等）は吸収し、同一内容を同一指紋に寄せる。
    """
    normalized = "\n".join((text or "").split())
    payload = f"{source_url}\x00{normalized}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def reset_dedup_registry() -> None:
    """プロセス内の二重起票防止登録簿をクリアする（テスト／運用リセット用）。"""
    _SEEN_FINGERPRINTS.clear()


def _join_note(existing: str, addition: str) -> str:
    return f"{existing} / {addition}" if existing else addition


# ════════════════════════════════════════════════════════════════════════
# データ構造
# ════════════════════════════════════════════════════════════════════════

@dataclass
class SynthesisDecision:
    """Synthesis テキストを解析した結果。"""
    conclusion: str = ""
    grounds: str = ""
    risks: str = ""
    recommended_actions: str = ""
    deliverable: str = ""
    primary_type: str = "unknown"
    secondary_types: list[str] = field(default_factory=list)
    human_review_required: bool = DEFAULT_HUMAN_REVIEW_REQUIRED
    next_route: str = "no_action"
    raw: str = ""


@dataclass
class HandoffAction:
    """1件のルーティング動作。"""
    route: str                 # create_handoff | create_doc | no_action | research_more
    task_type: str             # dev_task | doc_task | decision | research | composite
    role: str = "single"       # single | parent | child
    spec: dict | None = None   # 起票内容（generate_handoff_prompt の戻り値）。no_action は None
    created: dict | None = None # 起票結果（dry-run 時は payload、実起票時は Notion 応答）
    note: str = ""             # 補足（no_action の人間提示文など）
    skipped: bool = False      # 二重起票防止ガードで起票を見送った場合 True


@dataclass
class RoutingResult:
    decision: SynthesisDecision
    actions: list[HandoffAction] = field(default_factory=list)
    dry_run: bool = True


# ════════════════════════════════════════════════════════════════════════
# 1. 解析
# ════════════════════════════════════════════════════════════════════════

_HEADING_RE = re.compile(r"^#{1,6}\s*(.+?)\s*$")


def _split_sections(text: str) -> dict[str, str]:
    """`### 見出し` 区切りで本文を辞書化する（見出し名 → 本文）。"""
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        m = _HEADING_RE.match(line.strip()) if line.strip().startswith("#") else None
        if m:
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = m.group(1).strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def _get(sections: dict[str, str], *names: str) -> str:
    """見出し名のゆらぎを吸収して本文を取り出す。"""
    for name in names:
        for key, val in sections.items():
            if key.lower() == name.lower():
                return val
    return ""


def _normalize_type(token: str) -> str:
    """型トークンを正規化（全角・別名を吸収）。不明は 'unknown'。"""
    t = token.strip().lower().replace("　", "").replace(" ", "")
    aliases = {
        "dev": "dev_task", "devtask": "dev_task", "dev_task": "dev_task", "実装": "dev_task",
        "doc": "doc_task", "doctask": "doc_task", "doc_task": "doc_task",
        "ドキュメント": "doc_task", "document": "doc_task",
        "decision": "decision", "意思決定": "decision", "判断": "decision",
        "research": "research", "調査": "research", "深掘り": "research",
        "discussion": "decision",  # 旧語彙の救済（discussion → decision 扱い）
    }
    return aliases.get(t, t if t in ROUTER_RULES else "unknown")


def _parse_types(type_section: str) -> tuple[str, list[str]]:
    """タイプ判定セクションから primary / secondary を抽出する。"""
    primary = "unknown"
    secondary: list[str] = []
    for line in type_section.splitlines():
        low = line.lower()
        if "primary" in low or "プライマリ" in line:
            primary = _normalize_type(_after_colon(line))
        elif "secondary" in low or "セカンダリ" in line:
            for tok in _split_list(_after_colon(line)):
                norm = _normalize_type(tok)
                if norm in ROUTER_RULES and norm != primary and norm not in secondary:
                    secondary.append(norm)
    # primary が取れない場合、本文中の最初の有効な型を採用
    if primary == "unknown":
        for tok in re.split(r"[\s,、/|]+", type_section):
            norm = _normalize_type(tok)
            if norm in ROUTER_RULES:
                primary = norm
                break
    return primary, secondary


def _after_colon(line: str) -> str:
    """`primary: dev_task` の `:` / `：` 以降を返す。"""
    for sep in (":", "："):
        if sep in line:
            return line.split(sep, 1)[1]
    return line


def _split_list(text: str) -> list[str]:
    parts = re.split(r"[,、/|]+", text)
    out = []
    for p in parts:
        p = p.strip()
        if p and p not in {"なし", "none", "-", "—"}:
            out.append(p)
    return out


def _parse_bool(text: str, *, default: bool) -> bool:
    """true/false を抽出（全角・日本語のゆらぎ込み）。曖昧なら default。"""
    low = text.strip().lower()
    if not low:
        return default
    if re.search(r"\btrue\b|^true|要|必要|はい|yes", low):
        return True
    if re.search(r"\bfalse\b|^false|不要|いいえ|no", low):
        return False
    return default


def _parse_route(text: str, primary_type: str) -> str:
    """Next Route セクションから enum ルートを決定的に1つ選ぶ。

    判定は「入力トークンの出現順」にも「VALID_ROUTES の宣言順」にも依存させない:
      1. 有効ルートがちょうど1つだけ現れた → それを採用（LLM の明示指定を尊重）。
      2. 複数現れた（メニュー丸写し／両論併記などで曖昧）→ 明示した優先順位
         _ROUTE_PRIORITY（安全側を上位）で決定する。
      3. 1つも現れない → 型→ルートの正準マッピング ROUTER_RULES で導出する。

    旧実装は VALID_ROUTES のタプル順で先頭一致を返していたため、宣言順という
    偶発的なバイアスに判定が引きずられていた。本実装はそれを明示順位に固定する。
    """
    low = (text or "").lower()
    present = [route for route in VALID_ROUTES if route in low]
    distinct = list(dict.fromkeys(present))
    if len(distinct) == 1:
        return distinct[0]
    if distinct:
        for route in _ROUTE_PRIORITY:
            if route in distinct:
                return route
    return ROUTER_RULES.get(primary_type, "no_action")


def parse_synthesis(text: str) -> SynthesisDecision:
    """Synthesis テキスト（8セクション）を SynthesisDecision に解析する。"""
    sections = _split_sections(text or "")
    type_section = _get(sections, "タイプ判定", "type", "type judgment")
    primary, secondary = _parse_types(type_section)
    hrr = _parse_bool(
        _get(sections, "Human Review Required", "human_review_required", "ヒューマンレビュー"),
        default=DEFAULT_HUMAN_REVIEW_REQUIRED,
    )
    next_route = _parse_route(_get(sections, "Next Route", "next_route", "次のルート"), primary)
    return SynthesisDecision(
        conclusion=_get(sections, "結論", "conclusion"),
        grounds=_get(sections, "根拠", "grounds"),
        risks=_get(sections, "リスク", "risks"),
        recommended_actions=_get(sections, "推奨アクション", "recommended actions"),
        deliverable=_get(sections, "推奨成果物", "deliverable"),
        primary_type=primary,
        secondary_types=secondary,
        human_review_required=hrr,
        next_route=next_route,
        raw=text or "",
    )


# ════════════════════════════════════════════════════════════════════════
# 2. ルーティング
# ════════════════════════════════════════════════════════════════════════

def _is_composite(decision: SynthesisDecision) -> bool:
    """dev_task + doc_task の複合か判定する。"""
    types = {decision.primary_type, *decision.secondary_types}
    return {"dev_task", "doc_task"} <= types


def plan_actions(decision: SynthesisDecision) -> list[HandoffAction]:
    """
    SynthesisDecision から実行すべき HandoffAction 群を構築する（起票はまだしない）。

    複合（dev_task+doc_task）の場合は 親1 + 子2（実行順 doc→dev）を返す。
    """
    # ── 複合: 親1 + 子2（doc → dev の順）─────────────────────────────
    if _is_composite(decision):
        parent_spec = build_handoff_spec(decision, task_type="composite", role="parent")
        doc_spec = build_handoff_spec(decision, task_type="doc_task", role="child")
        dev_spec = build_handoff_spec(decision, task_type="dev_task", role="child")
        return [
            HandoffAction("create_handoff", "composite", "parent", spec=parent_spec),
            HandoffAction("create_doc", "doc_task", "child", spec=doc_spec),
            HandoffAction("create_handoff", "dev_task", "child", spec=dev_spec),
        ]

    # ── 単一型 ───────────────────────────────────────────────────────
    ptype = decision.primary_type
    route = decision.next_route or ROUTER_RULES.get(ptype, "no_action")

    if route == "no_action" or ptype == "decision":
        # 起票せず人間に判断提示
        return [HandoffAction(
            "no_action", ptype if ptype in VALID_TYPES else "decision", "single",
            spec=None,
            note=decision.conclusion or "（判断材料を人間に提示）",
        )]

    if route == "create_doc" or ptype == "doc_task":
        # doc_task は合議ループに入れない＝別ループ。単独時はここで起票しない。
        return [HandoffAction(
            "create_doc", "doc_task", "single",
            spec=build_handoff_spec(decision, task_type="doc_task", role="single"),
            note="doc_task は別ループ（非同期）で処理。合議ループでは起票しない。",
        )]

    # research → research_more（深掘り Handoff）
    if route == "research_more" or ptype == "research":
        return [HandoffAction(
            "research_more", "research", "single",
            spec=build_handoff_spec(decision, task_type="research", role="single"),
        )]

    # dev_task → create_handoff
    return [HandoffAction(
        "create_handoff", "dev_task", "single",
        spec=build_handoff_spec(decision, task_type="dev_task", role="single"),
    )]


def route_meeting_result(
    text: str,
    *,
    source_url: str = "",
    dry_run: bool = True,
    handoff_creator: Callable[..., dict] | None = None,
    dedup_store: set[str] | None = None,
) -> RoutingResult:
    """
    Synthesis テキストを解析し、ルート規則に従って起票（または起票計画）を行う。

    - dry_run=True（既定）: Notion へ書き込まず、起票予定 payload を action.created に格納。
    - dry_run=False: 起票を伴うルートで handoff_creator を呼び出す。
      handoff_creator 省略時は relay.create_handoff_page.create_handoff_page を使用。
    - doc_task 単独（create_doc）は別ループ扱いのため、ここでは起票しない（計画のみ）。
    - no_action は起票しない（人間へ判断提示）。

    二重起票防止ガード:
    - 同一 synthesis（＋起票元 source_url）から会議/Handoff を二重に起票しない。
      既に起票済みの組み合わせなら、起票を伴うアクションは handoff_creator を呼ばず
      skip（action.skipped=True / created=None）にする。
    - 判定キーは _synthesis_fingerprint（本文＋source_url の sha256）。登録簿は
      既定で本モジュールのプロセス内集合 _SEEN_FINGERPRINTS（consensus.py の Status
      ベース重複防止＝try_claim_page を補完する多層防御）。dedup_store を渡せば
      呼び出し側・テストが任意の登録簿を注入できる。
    """
    decision = parse_synthesis(text)
    actions = plan_actions(decision)

    if handoff_creator is None:
        from relay.create_handoff_page import create_handoff_page as handoff_creator  # noqa: E501

    store = _SEEN_FINGERPRINTS if dedup_store is None else dedup_store
    fingerprint = _synthesis_fingerprint(text, source_url)
    already_filed = fingerprint in store
    filed_now = False

    for action in actions:
        action.spec = _attach_source(action.spec, source_url)
        # 複合の create_doc 子は「別ループだが親に紐づく子」として起票する。
        # 単独 doc_task（role=single）は別ループ扱いで合議側からは起票しない。
        is_standalone_doc = action.route == "create_doc" and action.role == "single"
        should_create = (
            action.route in _ROUTES_THAT_CREATE
            or (action.route == "create_doc" and action.role == "child")
        )
        if not should_create or is_standalone_doc or action.spec is None:
            continue
        if already_filed:
            # 二重起票防止: 同一 synthesis から起票済み → 起票せず skip
            action.skipped = True
            action.note = _join_note(
                action.note, "二重起票防止: 同一synthesis結果から起票済みのためskip"
            )
            continue
        action.created = handoff_creator(action.spec, dry_run=dry_run)
        filed_now = True

    if filed_now:
        store.add(fingerprint)

    return RoutingResult(decision=decision, actions=actions, dry_run=dry_run)


def _attach_source(spec: dict | None, source_url: str) -> dict | None:
    if spec is None or not source_url:
        return spec
    spec = dict(spec)
    spec["source_url"] = source_url
    return spec
