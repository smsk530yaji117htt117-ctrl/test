# Render.com デプロイ手順書

Personal OS Consensus をクラウドで10分ごとに自動実行するための手順です。

---

## Step 1: Render.comアカウント作成

1. https://render.com を開く
2. 「Get Started for Free」をクリック
3. GitHubアカウントでサインアップ

---

## Step 2: GitHubリポジトリを接続

1. Render.comにログイン後、「New +」→「Cron Job」を選択
2. 「Connect a repository」でGitHubを接続
3. リポジトリ「smsk530yaji117htt117-ctrl/test」を選択

---

## Step 3: Cron Jobの設定

以下の値を入力して設定する：

| 項目 | 値 |
|---|---|
| Name | personal-os-consensus |
| Branch | claude/notion-api-setup-BQGwN |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python consensus.py` |
| Schedule | `*/10 * * * *`（10分ごと） |

---

## Step 4: 環境変数を設定

「Environment」タブで以下を1つずつ追加する。
値は `.env` ファイルから確認して手動入力すること。

| Key | 値の例 |
|---|---|
| `ANTHROPIC_API_KEY` | sk-ant-... |
| `OPENAI_API_KEY` | sk-proj-... |
| `GEMINI_API_KEY` | AIza... |
| `NOTION_TOKEN` | ntn_... |
| `NOTION_DATABASE_ID` | 7cb72b048ffa427f808010bd8213d563 |

> ⚠️ `.env` ファイルは絶対にGitHubにアップロードしないこと（.gitignoreで除外済み）

---

## Step 5: デプロイ実行

1. 「Create Cron Job」をクリック
2. ログタブでエラーがないか確認
3. 以下のログが出れば正常：

```
処理待ちの質問はありません。
```

---

## Step 6: 動作確認

1. Notionの「AI Consensus Log」にStatus=Pendingの行を1件作成
2. Renderダッシュボードで「Manual Run」をクリック（手動でテスト実行）
3. ログタブで以下が表示されれば成功：

```
処理待ち: 1件
▶ Status → Running
▶ 3社に並列問い合わせ中...
▶ 統合分析を生成中...
▶ Notionに書き戻し完了 → Status: Complete
✅ 完了しました（1件処理）
```

4. Notionで対象行のStatusが「Complete」になっていることを確認

10分ごとの自動実行が始まると、Renderダッシュボードの「Next Run」で次回実行時刻が確認できる。
過去の実行結果は「History」タブで一覧確認できる。
