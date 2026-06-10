# PROGRESS — 新A1: Render橋（通知ハブ＋発火リレー）

指示書: Notion「📦 新A1 指示書: Render橋」/ 作業ブランチ: `claude/bridge-a1` / PR base: `claude/notion-api-setup-BQGwN`

## 絶対制約（自己チェック用）
- [x] `consensus.py` は 1 バイトも変更しない / import しない（subprocess 起動のみ）
- [x] 既存 Notion DB のスキーマ変更なし（書き込みは Bridge Queue 行 + ダイジェストページcoメントのみ）
- [x] main ブランチへ push しない / PR base は `claude/notion-api-setup-BQGwN`
- [x] シークレット（キー/トークン/Webhook URL）をコード・ログ・PR に出さない（env 参照 + ログマスク）
- [x] 要求範囲を超える機能追加・抽象化をしない

## Phase 0 — リポジトリ調査（完了）
- Notion 認証 env 名: `NOTION_TOKEN`（`notion_utils.py` で確認）。Notion-Version `2022-06-28`。
- HTTP は stdlib `urllib`（`notion_utils.py` 準拠）。橋も urllib のみで実装 → 追加ランタイム依存なし。
- 既存依存（requirements.txt）: anthropic / openai / google-genai / notion-client / python-dotenv。
- Render: `render.yaml` の startCommand は `python consensus.py`。**変更しない**（マージ後に矢嶋さんが `python main.py` へ変更）。
- pytest は requirements 未記載（dev のみ）。既存 `tests/test_consensus.py` は anthropic 等が必要で本環境では収集不可 → 新規テストは独立ファイルで実行。
- ブランチ `claude/bridge-a1` を `origin/claude/notion-api-setup-BQGwN` から作成済み。

## 設計判断
- HTTP は全て stdlib `urllib`。Notion 呼び出しは共通補助 `bridge_notion.py` に集約（Comments / Queue の読み書き）。
- notify のフォールバック: `NOTIFY_ROUTES`（既定 `discord,slack,notion`）順に試行、最初の成功で終了。`notion` は常に終端として末尾に保証付与。
- notion 終端が 401/403（権限不足）の場合は Bridge Queue に結果行を書いて終端とし、Result に権限不足の事実を記録。
- dedupe: notify は直近30分の Done 行 Result から `dedupe_key=<key>` を照会。dedupe_key 指定の送信成功時に Queue へ marker 付き Done 行を残し永続化（プロセス毎回終了のため Queue 照会で実現）。
- マスク: 既知パターン（sk-ant-/sk-proj-/AIza/ntn_/Bearer/Slack・Discord webhook URL）+ 機微 env 値の動的置換。
- main.py: `subprocess.run([sys.executable, "consensus.py"])` → 終了コードに関わらず `bridge.run()`。consensus は import しない。

## Phase 進捗
- [x] Phase 0: 調査 / ブランチ作成 / PROGRESS 初期化
- [x] Phase 1: `notify.py` + tests
- [x] Phase 2: `bridge.py` + tests
- [x] Phase 3: `main.py` ラッパー + SELFTEST + tests
- [x] Phase 4: `docs/bridge.md` + PR 作成

## 未解決の質問 / 既知の制限
- fire の二重発火: 処理途中クラッシュ時に次回再試行で稀に二重 POST。v1 では既知の制限（対策未実装、docs に明記）。
- §6 確認事項「API発火された Routine 実行が15回/日上限に算入されるか」は窓口OS担当（本セッション外）。
- 外部到達（Discord/Slack/Notion/Anthropic）の実テストは Render 環境と条件が異なるため本セッションでは mock のみ。実到達は マージ後 SELFTEST レポートで確認。
- `NOTIFY_ROUTES` 既定値の確定は SELFTEST レポート後に窓口OSが行う。
</content>
</invoke>
