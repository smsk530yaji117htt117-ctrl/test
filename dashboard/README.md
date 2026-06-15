# 📊 PersonalOS 読み取り専用ダッシュボード (MVP)

Notion の PersonalOS 系 DB を **サーバ側で読み取り**、モバイル幅の軽量 HTML で
一覧表示する read-only ダッシュボードです。**Notion へは一切書き込みません。**

- Python + [FastAPI](https://fastapi.tiangolo.com/) + Notion 公式 SDK（`notion-client`）
- `GET /` がその場で Notion を `databases.query` して HTML を返す（キャッシュなし）
- **セクション単位でエラーを隔離** — 1つの DB 取得が失敗しても、他のセクションと
  ページ全体は表示される

## 表示セクション

| # | セクション | DB | 表示ロジック |
|---|---|---|---|
| 1 | 📈 習慣トラッカー | `4f57bc5a…` | `状態=進行中` を取得。`自動化度` が 4/5 の習慣を **🎓卒業候補** として強調 |
| 2 | 🧺 生活在庫・消耗品 | `53390db1…` | `推定残り日数`(formula) ≤ `アラート閾値日数` を **🛒補充** としてマーク |
| 3 | 🧹 定期家事 | `304f28c0…` | `次回まで日数`(formula) ≤ 2 を **🧹今日明日**。`天気依存` は **☀️** マーク |
| 4 | 🍳 料理・献立プール | `e3a221c9…` | `前回から日数`(formula) 降順 **top5** を **🍳献立候補** |
| 5 | 🤝 AI Handoff | `f9172334…` | `Status=Draft` の **件数 ＋ 上位5件**（更新日 降順） |

> formula 列（推定残り日数 / 次回まで日数 / 前回から日数）は **そのまま読み取り**ます。

## セットアップ

### 1. 依存をインストール

```bash
cd dashboard
python -m venv .venv && source .venv/bin/activate   # 任意
pip install -r requirements.txt
```

### 2. NOTION_TOKEN を設定

このダッシュボードは **環境変数 `NOTION_TOKEN`** を使います（リポジトリ全体と同じ変数名）。

```bash
cp .env.example .env
# .env を編集して NOTION_TOKEN=ntn_... を設定
```

- `.env` は `.gitignore` 済みで **コミットされません**。トークンはコミット禁止です。
- トークンの Notion インテグレーションを、上記5つの DB に **「接続（Connections）」** して
  おく必要があります（共有されていない DB はそのセクションだけエラー表示になります）。

`.env` から自動で環境変数を読みたい場合は、起動時に読み込んでください（下記）。

### 3. 起動

```bash
# .env を読み込んでから uvicorn を起動（python-dotenv 利用時）
set -a && source .env && set +a
uvicorn app:app --reload
```

`--reload` なしの素の起動:

```bash
NOTION_TOKEN=ntn_... uvicorn app:app --host 0.0.0.0 --port 8000
```

ブラウザ / スマホで <http://127.0.0.1:8000/> を開きます。
死活確認は <http://127.0.0.1:8000/healthz>（`ok` を返すだけ・Notion 非アクセス）。

## 仕様・制約

- **read-only**: `databases.query` のみ。ページ作成・更新・削除は一切しません。
- **秘匿情報**: トークンは環境変数のみ。エラー表示時も `ntn_***` 等にマスクします。
- Notion API バージョンはリポジトリの他コードと同じ `2022-06-28` を使用。
- 閾値・件数は `notion_reader.py` 上部の定数（`CHORE_DUE_DAYS` / `MEAL_TOP_N` /
  `HANDOFF_TOP_N` / `STOCK_DEFAULT_THRESHOLD`）で調整できます。

## テスト

純粋な変換ロジック（プロパティ抽出・閾値判定・並び替え）はネットワークなしで検証できます。

```bash
cd dashboard
python -m pytest tests -q
```
