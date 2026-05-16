# Render.com クラウドデプロイ手順書

Personal OS Consensus をクラウドで10分ごとに自動実行するための手順です。

---

## 1. GitHubリポジトリの作成

1. https://github.com にアクセスしてログイン
2. 右上の「+」→「New repository」をクリック
3. Repository name: `personal-os-consensus`
4. Private（非公開）を選択
5. 「Create repository」をクリック
6. 表示されるコマンドをコピーして、ターミナルで実行：

```
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/あなたのID/personal-os-consensus.git
git push -u origin main
```

> ⚠️ `.env` はアップロードしない（.gitignoreで除外済み）

---

## 2. Render.comのアカウント作成

1. https://render.com にアクセス
2. 「Get Started for Free」をクリック
3. GitHubアカウントでサインアップ（推奨）

---

## 3. GitHubをRenderに連携してデプロイ

1. Renderダッシュボードで「New +」→「Cron Job」をクリック
2. 「Connect a repository」でGitHubのリポジトリを選択
3. 設定画面で以下を入力：
   - **Name**: personal-os-consensus
   - **Region**: Singapore（日本から近い）
   - **Branch**: main
   - **Build Command**: `pip install -r requirements.txt`
   - **Command**: `python consensus.py`
   - **Schedule**: `*/10 * * * *`（10分ごと）
4. 「Create Cron Job」をクリック

---

## 4. 環境変数をRenderに設定

デプロイ後、Renderの「Environment」タブで以下を手動入力：

| Key | Value |
|-----|-------|
| `ANTHROPIC_API_KEY` | sk-ant-... |
| `OPENAI_API_KEY` | sk-proj-... |
| `GEMINI_API_KEY` | AIza... |
| `NOTION_TOKEN` | ntn_... |
| `NOTION_DATABASE_ID` | 7cb72b048ffa427f808010bd8213d563 |
| `RENDER_DEPLOY` | true |

---

## 5. デプロイ後の動作確認

1. Notionの「AI Consensus Log」にStatus=Pendingの行を追加
2. Renderダッシュボードで「Manual Run」をクリック（初回テスト）
3. 「Logs」タブでエラーがないか確認
4. Notionでレコードが Complete になったら成功

---

## 6. ローカル実行との切り替え

`.env` の `RENDER_DEPLOY` の値で動作を切り替えられます：

```
RENDER_DEPLOY=false  # ローカル実行（デフォルト）
RENDER_DEPLOY=true   # クラウド実行
```
