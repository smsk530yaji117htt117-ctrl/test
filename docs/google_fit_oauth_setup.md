# Google Fit 同期: トークン失効(invalid_grant)の修復手順

対象: `google_fit_sync.py` (Render Cron, 毎日 07:00 JST)
作成日: 2026-05-30

## 背景 / 根本原因

`google_fit_sync.py` が 5/21 以降 `invalid_grant: Token has been expired or
revoked.` を返し続け、Google Fit → Notion 50_Daily の同期が停止している。

- 最後に成功したのが 5/14、最初の失効が 5/21 で **約 7 日後**。
- これは **OAuth 同意画面が「テスト(Testing)」状態のときに発行される
  refresh token が 7 日で失効する** という Google の仕様と一致する。

したがって恒久対策は **OAuth 同意画面を「本番(In production)」に公開する**
こと。そのうえで refresh token を取り直す。

> ⚠️ すべての手順で、取得した **token / client_secret を Notion・PR・チャット・
> ログに貼らない** こと。値は Render の環境変数とローカルの一時ファイルだけで扱う。

---

## 全体の流れ

1. 【手動 / 矢嶋さん】OAuth 同意画面をテスト → 本番に公開する (7 日失効の恒久対策)
2. 【手動 / 矢嶋さん】ローカル PC で `google_fit_reauth.py` を実行し、新しい
   refresh token を取得する
3. 【手動 / 矢嶋さん】Render の環境変数 `GOOGLE_FIT_REFRESH_TOKEN` を更新する
4. 【検証】`python google_fit_sync.py --dry-run` で 1 日分の体重・歩数が取得でき、
   HTTP 200 になることを確認する

> 1〜3 は本人の Google アカウント / Render ダッシュボード操作が必須のため、
> Claude Code では実行できない。以下の手順を本人が実施すること。

---

## 手順 1: OAuth 同意画面を本番公開する (恒久対策)

1. [Google Cloud Console](https://console.cloud.google.com/) を開き、
   Google Fit 連携で使っているプロジェクトを選択する。
2. 左メニュー **API とサービス → OAuth 同意画面** (APIs & Services → OAuth
   consent screen) を開く。
3. User type が **External(外部)** になっていることを確認する。
4. 「公開ステータス(Publishing status)」が **テスト(Testing)** になっている
   はずなので、**「アプリを公開(PUBLISH APP)」** を押し、ステータスを
   **本番(In production)** に変更する。
5. 確認ダイアログで実行する。

### スコープと「未確認のアプリ」警告について

- 本スクリプトのスコープは `fitness.body.read` と `fitness.activity.read`
  (機密 / sensitive スコープ)。
- **本番公開するだけで「テスト状態の 7 日失効」は解消される**
  (refresh token が長期間有効になる)。
- 機密スコープは「Google による確認(verification)」を求められることがあるが、
  確認は主に「未確認のアプリ」警告を消すためのもの。**個人利用(アプリ作成者
  本人のアカウント)** であれば、認証時に
  「詳細 → (安全でないページ)へ移動」から続行すれば利用できる。
- まずは本番公開 + 本人アカウントでの続行で復旧する。第三者にも使わせる予定が
  あるときだけ verification を検討する。

---

## 手順 2: 新しい refresh token を取得する (ローカル PC)

> Render / CI では実行しない。ブラウザ認証が必要なためローカル PC で 1 回だけ。

```bash
# 1. 依存をインストール
pip install google-auth-oauthlib

# 2. Desktop App クライアントの値を一時的に環境変数へ (本人のローカルのみ)
export GOOGLE_FIT_CLIENT_ID='（Desktop App クライアント ID）'
export GOOGLE_FIT_CLIENT_SECRET='（Desktop App クライアント シークレット）'

# 3. 再認証ヘルパを実行
python google_fit_reauth.py
```

- ブラウザが開くので、対象の Google アカウントでログインし、Fit データへの
  アクセスを許可する。
- 成功すると `.secrets/google_fit_refresh_token.txt` に新しい refresh token が
  保存される (`.gitignore` 済み・権限 600)。**token 値は画面には表示されない。**

> クライアント ID / シークレットが手元に無い場合は、Google Cloud Console →
> API とサービス → 認証情報(Credentials) → 対象の OAuth 2.0 クライアント
> (種別: デスクトップ アプリ) から確認できる。

---

## 手順 3: Render の環境変数を更新する

1. [Render ダッシュボード](https://dashboard.render.com/) → 対象サービス →
   **Environment** を開く。
2. `GOOGLE_FIT_REFRESH_TOKEN` の値を、`.secrets/google_fit_refresh_token.txt`
   の中身で置き換える (ファイルを開いてコピー&ペースト)。
3. 必要なら `GOOGLE_FIT_CLIENT_ID` / `GOOGLE_FIT_CLIENT_SECRET` /
   `NOTION_API_KEY` / `NOTION_50_DAILY_DB_ID` も設定済みか確認する。
4. 保存すると再デプロイされる。
5. 確認後、ローカルの `.secrets/google_fit_refresh_token.txt` を **削除** する。

---

## 手順 4: 検証 (1 日分の取得で HTTP 200 を確認)

Render の環境変数更新後、手動で最小検証を実行する。

```bash
# Notion へは書き込まず、Google Fit からの取得のみ確認する
python google_fit_sync.py --dry-run

# 特定の日付を指定したい場合
python google_fit_sync.py --dry-run --date 2026-05-30
```

### 期待される出力 (Expected Output a)

```
... INFO google_fit_sync: access token を更新しました (HTTP 200)。
... INFO google_fit_sync: 取得結果 2026-05-30: weight=<値> steps=<値> calories=<値>
... INFO google_fit_sync: dry-run のため Notion へは書き込みません。取得は成功です (HTTP 200)。
{"date": "2026-05-30", "weight": <値>, "steps": <値>, "calories": <値>}
```

- `invalid_grant` が出なくなり、`access token を更新しました (HTTP 200)` と
  体重・歩数が表示されれば復旧成功。
- 問題なければ `--dry-run` を外して本同期 (`python google_fit_sync.py`) を実行、
  または翌 07:00 JST の cron 実行を待つ。

### まだ `invalid_grant` が出る場合

- 手順 1 (本番公開) が反映されていない、または手順 2 を本番公開 **前** に
  実行した可能性がある。本番公開を確認のうえ、手順 2 からやり直す。
- スクリプトは refresh token 失効時に **終了コード 2** を返し、再認証が必要で
  ある旨をログに出す (秘匿情報は出力しない)。

---

## 秘匿情報の取り扱い (厳守)

- token / client_secret / api_key を **リポジトリ・PR・Notion・チャット・ログ**
  に出力・貼り付けしない。
- 値は Render の環境変数と、ローカルの `.secrets/`(gitignore 済み) のみで扱う。
- 検証が済んだらローカルの token ファイルを削除する。
