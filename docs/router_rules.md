# router_rules — 会議（AI合議）→ 次工程ルーティング規則

PersonalOS 1.3-β。`consensus.py` が出力する Synthesis（8セクション構造）の
**タイプ判定**から **next_route** を決め、`meeting_result_processor.py` が
次工程へ自動接続するための規則を定義する。

## Synthesis 出力フォーマット（確定版）

| セクション | 内容 |
|---|---|
| 結論 | 1〜2文 |
| 根拠 | 3点以内 |
| リスク | 2点以内 |
| 推奨アクション | 1〜3件 |
| タイプ判定 | `primary: dev_task \| doc_task \| decision \| research`（1つ）／`secondary:` 0個以上 |
| 推奨成果物 | primary 型に応じた成果物 |
| Human Review Required | `true` / `false`（→ docs/HUMAN_REVIEW_REQUIRED_POLICY.md） |
| Next Route | `create_handoff \| create_doc \| no_action \| research_more`（1つ） |

## 型 → next_route

| primary 型 | next_route | 動作 |
|---|---|---|
| `dev_task` | `create_handoff` | Handoff 起票。Execution Mode: Claude Code / Codex |
| `doc_task` | `create_doc` | 別ループ（非同期）。**`consensus.py` の合議ループに入れない** |
| `decision` | `no_action` | 起票せず人間に判断提示。`Handoff Reason=人間判断` で Draft も可 |
| `research` | `research_more` | Task 先頭に「深掘り:」、Execution Mode: Deep Research で起票 |

## 複合（dev_task + doc_task）

`primary` と `secondary` を合わせて `{dev_task, doc_task}` を含む場合は複合とみなす。

- **親1 + 子2** を起票する。
- 実行順は **doc → dev**（ドキュメントを先に固めてから実装に着手）。
- 親は取りまとめ（`Handoff Reason=複合タスク取りまとめ`）。

```
親（複合・取りまとめ）
├─ 子1: doc_task  → create_doc   （先）
└─ 子2: dev_task  → create_handoff（後）
```

## 起票と実行（executor）の分離

- **起票は常に自動でよい。** gate は実行（executor 投入・PR merge）側に置く。
- `human_review_required=true` の行は起票のみ行い、**executor へ投入しない**。
- `decision`（no_action）は起票せず、人間に判断材料を提示する。
- `doc_task` 単独は別ループ（非同期）で処理し、合議ループからは起票しない。
  （複合の子としての doc_task は親に紐づけて起票する。）

## 実装メモ

- 解析: `meeting_result_processor.parse_synthesis()`
- ルート計画: `meeting_result_processor.plan_actions()`
- 起票実行: `relay/create_handoff_page.create_handoff_page()`（`dry_run` 対応）
- 合議からの接続: `consensus.route_synthesis_result()`
  - 既定は **dry-run（ログのみ）**。`ENABLE_MEETING_ROUTING=1` で実起票に切り替え。
  - 例外は握りつぶし、合議ループ本体は止めない。
