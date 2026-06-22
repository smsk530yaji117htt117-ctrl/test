# ⑥ 会議→Handoff live化 カナリア観測チェックリスト

[decisions/06-meeting-routing-live.md](decisions/06-meeting-routing-live.md) の「条件付き Go（カナリア）」を
実地で安全に回すための観測手順。**有効化（`ENABLE_MEETING_ROUTING` の設定）は人間・承認後**。本書は手順のみ。

## 前提（コード側の守り）
- 既定は dry-run（`ENABLE_MEETING_ROUTING` 未設定＝起票しない）。`consensus.route_synthesis_result` は
  例外を握りつぶし、合議ループを止めない。
- 二重起票防止: 同一 synthesis（＋source_url）の sha256 指紋で in-process dedup（PR #25）。
  さらに `try_claim_page`（Status ロック）が**別 run の重複**を防ぐ多層防御。
- 本番不変条件は `tests/test_routing_live_safety.py` で固定済み:
  壊れ/空 Synthesis は誤起票ゼロ ／ decision・unknown は no_action ／ **HRR=true は live でも Draft**
  ／ 同一 run の二重起票なし。

## カナリア手順
1. **1日だけ** Render で `ENABLE_MEETING_ROUTING=1` を設定（他の env・cron は触らない）。
2. その日の 3社合議結果（AI Consensus Log の Complete 行）について観測:
   - 新規 Handoff が**妥当な型**で起票されたか（dev_task→Handoff / doc_task→別ループ / decision→no_action / research→深掘り）。
   - **重複起票が無い**か（同一 synthesis から2件以上の親が立っていないか）。
   - **HRR=true の項目が Draft** になっているか（Ready で自動消化されていないか）。
   - 想定外の大量起票が無いか。
3. 問題なし → 常用へ。問題あり → 即 `ENABLE_MEETING_ROUTING` を false/未設定へ（ロールバック）。

## ロールバック
- `ENABLE_MEETING_ROUTING` を未設定/false に戻すと即 dry-run。誤起票分は Handoff を Archived/削除で回収（スキーマ不変）。

## 別途検討（永続 dedup の強化・要承認）
- in-process dedup は **同一 run 内のみ**有効。cross-run は `try_claim_page` が守るが、より強い保証が要るなら
  AI Consensus Log の**既存プロパティ `Handoff起票済み`（checkbox）**を live 時に立てる/参照する設計が候補。
  - これは**本番への書き込み挙動の追加**（スキーマ変更ではない＝既存プロパティ）だが、live 化の一部として
    人間承認後に実装する。本チェックリストでは提案のみ。
