# Render橋（bridge）— 通知ハブ + 発火リレー 運用ドキュメント

`consensus.py` と同居して Render の cron（10分毎）で動く「橋」。2つの機能を持つ。

- **通知ハブ** (`notify.py`): フォールバック付きで Discord / Slack / Email / Notion へ通知を配送する `notify()` 抽象化レイヤー。
- **発火リレー** (`bridge.py`): Notion「Bridge Queue」DB の Pending 行を読み、Claude Code Routines の API トリガーへ HTTP POST して即時起動する。

## 構成ファイル

| ファイル | 役割 |
|---|---|
| `main.py` | Render 用ラッパー。`subprocess` で `consensus.py` を起動 → 終了コードに関わらず `bridge.run()` を実行 |
| `bridge.py` | Bridge Queue のポーリング、fire / notify ディスパッチ、SELFTEST |
| `notify.py` | `notify()` 通知ハブ（経路フォールバック / dedupe / マスク） |
| `bridge_notion.py` | Notion / HTTP 補助（Comments API、Queue 行の読み書き、汎用 JSON POST） |
| `tests/` | 全経路 mock のユニットテスト |

`consensus.py` は一切変更しない。`main.py` から **subprocess 起動のみ**で呼び出す（import しない）。
HTTP は全て標準ライブラリ `urllib` を使用し、追加のランタイム依存はない。

## 処理フロー（毎実行）

1. `BRIDGE_SELFTEST=1` のとき、冒頭で SELFTEST（後述）を実行。
2. Bridge Queue DB から `Status=Pending` を `Requested At`（created_time）昇順で全件取得。
3. 各行を処理し、終了後すみやかに `Status` と `Result` を更新。
   - `Action=fire`: `Target`=ルーチンキー、`Payload`=POST する text。
   - `Action=notify`: `Payload` を text として `notify()` へ。`Target` に経路名があれば `force_route`、空なら通常フォールバック。

## 通知ハブ `notify()`

```python
res = notify(text, source, level="info", title=None, dedupe_key=None, force_route=None)
# -> NotifyResult(ok: bool, route: str | None, attempts: list[tuple[route, ok, err]])
```

- 経路優先順は `NOTIFY_ROUTES`（既定 `discord,slack,notion`）。対応 env が未設定の経路はスキップ。
- **終端は常に notion**: ダイジェストページへ Notion Comments API でコメント作成。`level=error` の時のみ指定ユーザーをメンション。
- notion コメントが権限不足（401/403）の場合は、Bridge Queue への結果行書き込みを終端とし、Result に権限不足の事実を記録。
- `dedupe_key` 指定時: Bridge Queue の直近30分の `Done` 行 Result に同一 `dedupe_key=<key>` があれば送信しない。送信成功時は marker 付き Done 行を Queue に残して永続化する（プロセスは毎回終了するため Queue 照会で dedupe を実現）。
- `notify()` は例外を外に投げない（通知失敗で呼び出し元を落とさない）。

| 経路 | 実装 | 環境変数 |
|---|---|---|
| discord | Webhook POST `{"content": ...}` | `DISCORD_WEBHOOK_URL` |
| slack | Webhook POST `{"text": ...}` | `SLACK_WEBHOOK_URL` |
| email | HTTP API プロバイダ想定のスタブ（env 未設定なら常にスキップ） | `EMAIL_API_URL` / `EMAIL_API_KEY` / `EMAIL_TO` |
| notion | Comments API（終端・必須） | `NOTION_TOKEN`（`consensus.py` と共通） |

## 発火リレー（fire）

`Action=fire` の行を Claude Code Routines の API トリガーへ POST する。

- 送信先は `ROUTINE_FIRE_URL_<KEY>` / `ROUTINE_FIRE_TOKEN_<KEY>`（KEY=`Target` 値）。未設定の KEY は `Status=Error` / `Result="env未設定"`。
- リクエスト（公式: https://code.claude.com/docs/en/routines ）:

```
POST {ROUTINE_FIRE_URL_<KEY>}
Authorization: Bearer {ROUTINE_FIRE_TOKEN_<KEY>}
anthropic-beta: experimental-cc-routine-2026-04-01
anthropic-version: 2023-06-01
Content-Type: application/json

{"text": "<Payload>"}
```

- 成功時はレスポンスの `claude_code_session_url` を Result に記録し `Done`。失敗は `Error` + マスク済みエラー。

## SELFTEST（到達可否レポート）

`BRIDGE_SELFTEST=1` のとき bridge 実行の冒頭で実施する。

1. 全経路に1件ずつテスト通知。
2. 設定済みの全 fire キー（`ROUTINE_FIRE_URL_*`）へ `text="selftest"` を POST。
3. 結果（経路ごとの ok / エラー要約）を Bridge Queue に1行（`Action=notify`, `Name="SELFTEST結果 <日時>"`, `Status=Done`, `Result`=詳細）として書き、あわせてダイジェストページへコメント。

これがマージ後の「Render 実環境での到達可否レポート」になる。

## 環境変数一覧

| 変数 | 用途 | 必須 |
|---|---|---|
| `NOTION_TOKEN` | Notion API（既存・`consensus.py` と共通） | はい |
| `NOTIFY_ROUTES` | 通知経路の優先順（既定 `discord,slack,notion`） | いいえ |
| `DISCORD_WEBHOOK_URL` | Discord 通知 | いいえ |
| `SLACK_WEBHOOK_URL` | Slack 通知 | いいえ |
| `EMAIL_API_URL` / `EMAIL_API_KEY` / `EMAIL_TO` | Email 通知（スタブ） | いいえ |
| `ROUTINE_FIRE_URL_<KEY>` / `ROUTINE_FIRE_TOKEN_<KEY>` | fire 送信先（KEY=Target 値、例 `PR_SYNC`） | fire を使う場合 |
| `BRIDGE_SELFTEST` | `1` で起動時に SELFTEST を実行 | いいえ |

> シークレット（キー / トークン / Webhook URL）はコード・ログに出さない。env 参照のみで、ログ出力時はマスクする。

## マージ後の手順（実行: 矢嶋さん + 窓口OS）

1. **矢嶋さん**: https://claude.ai/code/routines で「PersonalOS PR Status Sync」に API トリガーを追加し、URL とトークンを取得（トークンは一度しか表示されない）。
2. **矢嶋さん**: Render Dashboard で env 登録（`ROUTINE_FIRE_URL_PR_SYNC` / `ROUTINE_FIRE_TOKEN_PR_SYNC`、保有していれば各 Webhook URL）+ Start Command を `python main.py` に変更 + `BRIDGE_SELFTEST=1` を設定。
3. **自動**: 次回 cron 実行で SELFTEST が走り、ダイジェストに到達可否レポートが届く。
4. **窓口OS**: レポートを確認し `NOTIFY_ROUTES` 既定値を確定 → 矢嶋さんが `BRIDGE_SELFTEST` を削除。
5. **確認事項**: API 発火された Routine 実行が 15回/日上限に算入されるかを Routines 画面で確認し、制約リストへ追記（窓口OS 担当）。

## 既知の制限（v1）

- **fire の二重発火**: 処理途中のクラッシュ → 次回再試行のため、fire の二重発火が稀に起こり得る。v1 ではこれを既知の制限とし、対策は実装しない。
- 外部到達（Discord / Slack / Notion / Anthropic）の実テストは Render 環境と条件が異なるため、本リポジトリのテストは mock のみ。実到達はマージ後の SELFTEST レポートで確認する。
