---
title: "📦 新A1 指示書: Render橋（通知ハブ＋Routine発火リレー）12h自律実装"
source_notion_id: 37b5ae2b8d6a8153ad94d22bd192c4f0
archived: 2026-06-28
status: 完了
---

# 📦 新A1 指示書: Render橋（通知ハブ＋Routine発火リレー）12h自律実装

*作成: 2026-06-10 / 作成者: 窓口OS (Claude) / 実行者: Claude Code 単独クラウドセッション（Fable 5 / effort=high 想定）/ 関連Handoff: AI Handoff DB「新A1: Render橋」*

---

# 0. 最初にやること
1. このページを最後まで読む
2. 作業ブランチ直下に `PROGRESS.md` を作成し、フェーズごとの進捗・判断・未解決の質問を追記しながら進める（セッション断絶時の再開点）
3. 不明点があっても推測で仕様を拡張しない。確実な部分だけ実装し、質問は `PROGRESS.md` と PR description に明記する

# 1. ミッション
Render上で `consensus.py` と同居して10分毎に動く「橋（bridge）」を実装し、PR提出まで完遂する。橋の機能は2つ:
- **通知ハブ**: `notify()` 抽象化レイヤー。Discord / Slack / Email / Notion へフォールバック付きで通知を配送する
- **発火リレー**: Notion「Bridge Queue」DB の Pending 行を読み、Claude Code Routines のAPIトリガーへ HTTP POST して即時起動する

これによりPersonalOSは「定時ポーリング待ち」から「承認後すぐ実行」へ移行し、通知問題も同じ橋で解決する。

# 2. 絶対制約（違反したら失敗扱い）
- `consensus.py` は1バイトも変更しない。import もしない（読解は可、起動は subprocess のみ）
- 既存Notion DBのスキーマ変更禁止。Notionへの書き込み対象は Bridge Queue DB の行と、ダイジェストページへのコメントのみ
- main ブランチへの push 禁止
- PR の base は `claude/notion-api-setup-BQGwN`（本番ブランチ。**mainではない**）
- マージしない。PR作成・`PROGRESS.md`記録まで（Handoff DBの更新は窓口OS側が担当）
- APIキー・トークン・Webhook URL をコード・PR・ログに書かない。環境変数参照のみ、ログ出力時はマスクする
- 要求範囲を超える機能追加・リファクタ・抽象化をしない

# 3. 確定アーキテクチャ（窓口OS決定済み・変更不可）

## 3-1. 配置
現Renderサービス personal-os-consensus（cron 10分毎、Start Command: `python consensus.py`）に対し、以下を新規納品する:
- `main.py`: ① `subprocess.run([sys.executable, "consensus.py"])` を実行 → ② その終了コードに関わらず bridge 処理を実行するラッパー。マージ後に矢嶋さんが Start Command を `python main.py` に変更する
- `bridge.py` / `notify.py` /（必要なら共通の Notion クライアント補助）/ `tests/` / `docs/bridge.md`
- 依存追加が必要なら requirements に最小限で追記（既存依存を Phase 0 で確認）

## 3-2. Bridge Queue DB（窓口OSが作成済み）
- Database ID: `ffad28a9f7b648cb8efdff4c47dda4cb`
- Data Source ID: `8cc53d3d-cf72-4697-84c4-6373498c4d89`
- スキーマ: Name(title) / Action(select: fire, notify) / Target(text) / Payload(text) / Status(select: Pending, Done, Error) / Result(text) / Requested At(created_time)
- bridge は毎実行で Status=Pending を全件取得し、Requested At の古い順に処理。処理後すみやかに Status と Result を更新する
- 処理途中のクラッシュ→次回再試行のため、fire の二重発火が稀に起こり得る。v1ではこれを既知の制限として docs に明記する（対策実装はしない）

## 3-3. notify() インターフェース（確定済み・変更不可）
```python
res = notify(text, source, level="info", title=None, dedupe_key=None, force_route=None)
# -> NotifyResult(ok: bool, route: str | None, attempts: list[tuple[route, ok, err]])
```
- 経路優先順は環境変数 `NOTIFY_ROUTES`（既定 `"discord,slack,notion"`）。対応する env が未設定の経路はスキップ
- **終端は常に notion**: ダイジェストページ（ID: `36a5ae2b8d6a81ee8b46e86c7941058f`）へ Notion Comments API でコメント作成。level=error の時のみ user_id `173d872b-594c-81b4-af4a-000262688c71` をメンションに含める
- コメント作成が権限不足（403等）の場合は、Bridge Queue への結果行書き込みを終端とし、Result に権限不足の事実を記録
- `dedupe_key` 指定時: Bridge Queue の直近30分の Done 行の Result に同一 dedupe_key の記録があれば送信しない（プロセスは毎回終了するため、永続dedupeはQueue照会で行う）
- `notify()` は例外を外に投げない（通知失敗で呼び出し元を落とさない）
- Action=notify の Queue 行は Payload を text として notify() に流す。Target に経路名があれば force_route として扱い、空なら通常フォールバック

## 3-4. 発火リレー（fire）
- Action=fire の行: Target=ルーチンキー（例 `PR_SYNC`）、Payload=POST する text
- 送信先は環境変数 `ROUTINE_FIRE_URL_<KEY>` / `ROUTINE_FIRE_TOKEN_<KEY>`（KEY=Target値）。未設定の KEY は Status=Error、Result="env未設定" として処理
- リクエスト仕様（公式: [https://code.claude.com/docs/en/routines](https://code.claude.com/docs/en/routines) ）:
```
POST {ROUTINE_FIRE_URL_<KEY>}
Authorization: Bearer {ROUTINE_FIRE_TOKEN_<KEY>}
anthropic-beta: experimental-cc-routine-2026-04-01
anthropic-version: 2023-06-01
Content-Type: application/json

{"text": "<Payload>"}
```
- 成功時は response の `claude_code_session_url` を Result に記録し Done。失敗は Error + マスク済みエラーを記録
- 到達根拠: Render→api.anthropic.com は `consensus.py` のAPI呼び出しで到達実績あり

## 3-5. 通知経路の実装要件

| 経路 | 実装 | 環境変数 |
|---|---|---|
| discord | Webhook POST `{"content": ...}` | `DISCORD_WEBHOOK_URL` |
| slack | Webhook POST `{"text": ...}` | `SLACK_WEBHOOK_URL` |
| email | 送信抽象のスタブのみ（HTTP APIプロバイダ想定、env未設定なら常にスキップ） | `EMAIL_API_URL` / `EMAIL_API_KEY` / `EMAIL_TO` |
| notion | Comments API（終端・必須実装） | `consensus.py` が使う既存の Notion トークン変数を流用（Phase 0 で実名確認） |

## 3-6. SELFTEST（到達可否レポートの自動生成）
- 環境変数 `BRIDGE_SELFTEST=1` のとき、bridge 実行の冒頭で (a) 全経路に1件ずつテスト通知 (b) 設定済み全 fire キーへ text="selftest" を POST
- 結果（経路ごとの ok / エラー要約）を Bridge Queue に1行（Action=notify, Name="SELFTEST結果 \<日時\>", Status=Done, Result=詳細）として書き、あわせてダイジェストページへコメント
- これがマージ後の「Render実環境での到達可否レポート」になる。**Claude Code セッション環境からの外部到達テストは Render と条件が異なるため、本セッション内では実施不要**（テストは mock で行う）

# 4. 実装フェーズ
- **Phase 0**: リポジトリ調査。`consensus.py` の Notion 認証env名・依存・構成を把握（改変禁止）。`PROGRESS.md` 初期化。ブランチ `claude/bridge-a1` を `origin/claude/notion-api-setup-BQGwN` から作成
- **Phase 1**: `notify.py` + tests（全経路mock。フォールバック順序 / notion終端保証 / 例外封じ / dedupe / force_route）
- **Phase 2**: `bridge.py` + tests（Queueポーリング、fire、notifyディスパッチ、Status/Result更新）
- **Phase 3**: `main.py` ラッパー + SELFTEST + tests
- **Phase 4**: `docs/bridge.md`（運用手順・env一覧・マージ後手順・既知の制限）→ PR 作成

# 5. PR要件
- base: `claude/notion-api-setup-BQGwN` / head: `claude/bridge-a1`
- `consensus.py` の diff = 0 行であること
- description に: 実装サマリ / 環境変数一覧 / マージ後手順（§6の転記） / 未解決の質問 / 全テスト pass のログ

# 6. マージ後の手順（docs/bridge.md に転記。実行は矢嶋さんと窓口OS）
1. 矢嶋さん: [claude.ai/code/routines](https://claude.ai/code/routines) で「PersonalOS PR Status Sync」にAPIトリガーを追加し、URL とトークンを取得（トークンは一度しか表示されない）
2. 矢嶋さん: Render Dashboard で env 登録（`ROUTINE_FIRE_URL_PR_SYNC` / `ROUTINE_FIRE_TOKEN_PR_SYNC`、保有していれば各 Webhook URL）+ Start Command を `python main.py` に変更 + `BRIDGE_SELFTEST=1` を設定
3. 自動: 次回 cron 実行で SELFTEST が走り、ダイジェストに到達可否レポートが届く
4. 窓口OS: レポートを確認し `NOTIFY_ROUTES` 既定値を確定 → 矢嶋さんが `BRIDGE_SELFTEST` を削除
5. 確認事項: API発火された Routine 実行が15回/日上限に算入されるかを Routines 画面で確認し、制約リストへ追記（窓口OS担当）

# 7. 参考情報
- repo: `smsk530yaji117htt117-ctrl/test` / Render Service: personal-os-consensus（cron 10分毎）
- Routines 公式: [https://code.claude.com/docs/en/routines](https://code.claude.com/docs/en/routines)
- Notion Comments API: [https://developers.notion.com/reference/create-a-comment](https://developers.notion.com/reference/create-a-comment)
- 完了時: PR URL を `PROGRESS.md` 末尾に記録して終了。Handoff の Status 更新は窓口OS / PR Status Sync が行う
