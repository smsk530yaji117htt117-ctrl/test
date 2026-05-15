# Quickstart — 30分で収益化スタート

完全自動運用までの最短手順です。所要時間: **約30分**（1回のみ）。

---

## ステップ 1: mainにマージ（2分）

GitHubで PR を作成してマージ:

1. https://github.com/smsk530yaji117htt117-ctrl/test/pull/new/claude/automated-income-system-w6zSi
2. **Create pull request** をクリック
3. **Merge pull request** をクリック

> これで GitHub Actions の日次cronが動き出します（毎日 00:15 UTC）。

---

## ステップ 2: GitHub Secrets を設定（5分・任意だが推奨）

https://github.com/smsk530yaji117htt117-ctrl/test/settings/secrets/actions

| Secret 名 | 値 | 効果 |
|----------|-----|------|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/ で発行 | AI日本語要約が有効化 → 単価2-3倍 |
| `TECH_PULSE_WEBHOOK_URL` | Slack/Discord の Incoming Webhook URL | キーワード急上昇を自動通知 |

未設定でも動きます。後から追加可能。

---

## ステップ 3: 初回データ収集を手動トリガ（1分）

https://github.com/smsk530yaji117htt117-ctrl/test/actions/workflows/collect.yml

1. **Run workflow** → **Run workflow** をクリック
2. 1〜2分待つ
3. Actions タブで緑のチェックマークを確認

これで `data/latest.json` が生成され、9ソースから本物のデータが入ります。

---

## ステップ 4: Vercel デプロイ（10分）

1. https://vercel.com/new にアクセス（GitHubでサインアップ）
2. このリポジトリを **Import**
3. **Framework Preset:** Other（変更なし）
4. **Environment Variables** に1つ追加:
   - Name: `RAPIDAPI_PROXY_SECRET`
   - Value: ターミナルで `openssl rand -hex 32` を実行した出力
   - **この値はメモする**（ステップ5で使う）
5. **Deploy** をクリック
6. 完了後、`https://<your-app>.vercel.app/health` を開いて `{"ok":true}` を確認
7. **`/dashboard` も開いて動作確認**

---

## ステップ 5: RapidAPI で出品（12分）

1. https://rapidapi.com/provider/add-new-api にアクセス（無料サインアップ）
2. **基本情報:**
   - Name: `Tech Pulse API`
   - Category: `Data`
   - Description: `Daily aggregated tech trends from 9 public sources with AI summaries.`
3. **Base URL:** `https://<your-vercel-app>.vercel.app`
4. **Endpoints の一括登録（推奨）:**
   - **OpenAPI ファイル**: このリポジトリの `docs/openapi.json` をダウンロードしてアップロード
   - 17エンドポイントが自動登録される
5. **Security → Secret Header:**
   - Header name: `X-RapidAPI-Proxy-Secret`
   - Value: ステップ4でメモした値
6. **Pricing プラン:**
   - **Basic (Free):** 100 calls/month — 集客用
   - **Pro:** $9.99/month, 10,000 calls — メイン課金
   - **Ultra:** $49/month, 100,000 calls — 大口向け
7. **Payout 設定:** PayPalまたはStripeを登録
8. **Make API Public** で公開

---

## 動作確認

ローカルから実際にAPIを叩いてみる:

```bash
# RapidAPIダッシュボードでAPIキーをコピーしてから:
curl -H "X-RapidAPI-Key: YOUR_KEY" \
     -H "X-RapidAPI-Host: tech-pulse-api.p.rapidapi.com" \
     https://tech-pulse-api.p.rapidapi.com/v1/pulse/trending
```

レスポンスにキーワード一覧が返れば**収益化スタート**。

---

## 完全自動運用フロー（設定後）

```
00:15 UTC ──┐
            ├─→ GitHub Actions: 9ソース収集 + AI要約 + webhook送信
            ├─→ data/latest.json を自動コミット
            └─→ Vercel: 自動再デプロイ

ユーザー ──→ RapidAPI ──認証/課金──→ Vercel API ──→ data/latest.json
                                              ↓
                                         JSON返却
                                              ↓
RapidAPI ──月次集金──→ あなたの PayPal/Stripe
```

あなたの月次作業: **RapidAPIダッシュボードで売上確認のみ**

---

## 集客（任意・継続）

API を見つけてもらうための施策:

- **Zenn / Qiita / dev.to** で「Tech Pulse APIを公開した」記事
- **Twitter/X**: `#buildinpublic` で告知
- **Reddit** `r/SideProject`、`r/webdev` で紹介
- **RapidAPI内SEO**: タイトルにキーワード、サンプルコードを充実

---

## トラブルシューティング

| 症状 | 確認箇所 |
|------|---------|
| Actions が動かない | リポジトリ Settings → Actions → 有効化 |
| /health が 503 | Vercel ビルドログ確認 |
| `/v1/pulse/*` が 401 | RAPIDAPI_PROXY_SECRET の値がVercelとRapidAPIで一致しているか |
| AI要約が出ない | `ANTHROPIC_API_KEY` が Secrets に入っているか |
| dashboard が空 | 初回 cron 待ち or workflow を手動実行 |
