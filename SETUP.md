# Tech Pulse API — セットアップ手順

このAPIで収益化するために、あなたが一度だけ行う作業をまとめています。
コードはすべて自動で動きます。あなたの作業は**初回のみ約30分**です。

---

## 全体像

```
GitHub Actions (毎日 00:15 UTC)
   ↓ 公開APIから収集
data/latest.json (Gitに自動コミット)
   ↓ Vercelが自動デプロイ
https://tech-pulse-api.vercel.app
   ↓ RapidAPIマーケットプレイスで販売
   ↓ ユーザーが課金 → RapidAPIが集金 → あなたに送金
```

運用後の手間: **ほぼゼロ**（月1回ダッシュボードを見るだけ）

---

## ステップ 1: GitHub Actions を有効化（5分）

1. このリポジトリの **Actions** タブを開く
2. ワークフローを有効化
3. `Daily Collect` を手動実行（`workflow_dispatch`）して動作確認

成功すると `data/daily/YYYY-MM-DD.json` と `data/latest.json` がコミットされます。

---

## ステップ 2: Vercel にデプロイ（10分）

1. https://vercel.com にGitHubアカウントでサインアップ（無料）
2. このリポジトリを **Import**
3. **Framework Preset:** Other / **Build Command:** 空 / **Output Directory:** 空
4. 環境変数を追加:
   - `RAPIDAPI_PROXY_SECRET` = 任意の長い文字列（例: `openssl rand -hex 32` の出力）
5. Deploy

完了すると `https://<your-app>.vercel.app/health` で `{"ok": true}` が返ります。
GitHub に push されるたびに自動再デプロイ。

---

## ステップ 3: RapidAPI に出品（15分）

1. https://rapidapi.com/provider にサインアップ（無料）
2. **Add New API** を選択
3. 入力内容:
   - **Name:** Tech Pulse API
   - **Category:** Data
   - **Base URL:** `https://<your-app>.vercel.app`
   - **Description:** Daily aggregated tech trends from Hacker News, GitHub Trending, and Reddit.
4. **Settings → Security** で、RapidAPIが送ってくる `X-RapidAPI-Proxy-Secret` を
   Vercelに設定したものと同じ値にする（これでRapidAPI経由のみアクセス可能になる）
5. **Endpoints** を登録:
   - `GET /v1/pulse/latest`
   - `GET /v1/pulse/hackernews?limit=20`
   - `GET /v1/pulse/github?language=Python`
   - `GET /v1/pulse/reddit/{subreddit}`
   - `GET /v1/pulse/archive/{date}`
6. **Pricing プラン** を設定（推奨）:
   - **Basic (Free):** 100コール/月 — 集客用
   - **Pro:** $9.99/月 — 10,000コール
   - **Ultra:** $49/月 — 100,000コール
7. 支払い情報（PayPal または Stripe）を登録

---

## ステップ 4: 集客（任意・継続）

リスティングしただけでは見つかりません。少しの初動が必要です:

- **dev.to / Qiita / Zenn** に「Tech Pulse APIを公開した」記事を書く
- **Twitter/X** で告知（#buildinpublic）
- **Reddit r/SideProject** で紹介
- **RapidAPI内のSEO**: タイトル・タグ・サンプルコードを充実させる

---

## 収益試算（保守的）

| シナリオ | Pro契約数 | 月収 |
|---------|----------|------|
| 立ち上げ期 | 0〜2 | $0〜$20 |
| 軌道後 | 5〜10 | $50〜$100 |
| ヒット時 | 30+ | $300+ |

データの差別化（独自スクレイピング、AI要約追加）で単価を上げられます。

---

## 拡張アイデア（将来）

1. **AI要約レイヤー** — Claude APIで各記事に200字要約を付与（単価アップ）
2. **トレンド分析エンドポイント** — `/v1/trending/keywords?days=7`
3. **日本語ソース追加** — はてブ、Qiitaトレンド
4. **Webhook配信** — 「特定キーワードが浮上したら通知」

これらは私が追加実装できます。「拡張○○を入れて」と言ってください。
