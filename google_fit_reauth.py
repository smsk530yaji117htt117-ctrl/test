#!/usr/bin/env python3
"""Google Fit refresh token 再取得ヘルパ (ワンタイム / ローカル実行専用).

refresh token が失効 (invalid_grant) した際に、矢嶋さん本人のローカル PC で
1 回だけ実行し、新しい refresh token を取得するための補助スクリプト。

⚠️ このスクリプトは Render / CI では実行しない。ブラウザでの Google 認証
   (本人のアカウント操作) が必須のため、ローカル PC でのみ実行すること。

セキュリティ
------------
- client_id / client_secret は環境変数から読む (ハードコードしない)。
- 取得した refresh token は **標準出力に出さない**。
  ローカルの gitignore 済みファイル (.secrets/google_fit_refresh_token.txt) に
  パーミッション 600 で保存する。
- 保存ファイルを開いて Render の環境変数 GOOGLE_FIT_REFRESH_TOKEN に貼り付け、
  **貼り付け後はローカルのファイルを削除** すること。
- 取得した token を Notion / PR / チャット / ログへ貼らないこと。

事前準備
--------
1. 恒久対策として OAuth 同意画面を「本番(In production)」に変更しておく
   (docs/google_fit_oauth_setup.md 参照)。テストのままだと再び 7 日で失効する。
2. 依存をインストール:  pip install google-auth-oauthlib
3. 環境変数を一時的に設定 (本人のローカルのみ):
       export GOOGLE_FIT_CLIENT_ID=...        # Desktop App クライアントの値
       export GOOGLE_FIT_CLIENT_SECRET=...

実行
----
    python google_fit_reauth.py

完了後、表示される手順に従って Render の環境変数を更新する。
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

# Google Fit に必要な読み取りスコープ (sync 側と一致させること)
SCOPES = [
    "https://www.googleapis.com/auth/fitness.body.read",
    "https://www.googleapis.com/auth/fitness.activity.read",
]

OUTPUT_DIR = Path(".secrets")
OUTPUT_FILE = OUTPUT_DIR / "google_fit_refresh_token.txt"


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(
            f"エラー: 環境変数 {name} が未設定です。\n"
            "Desktop App クライアントの値を一時的に export してから再実行してください。",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def _save_token(refresh_token: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(refresh_token, encoding="utf-8")
    # 所有者のみ読み書き可 (600)
    try:
        OUTPUT_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass  # Windows 等で chmod 不可でも続行
    return OUTPUT_FILE


def main() -> int:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "google-auth-oauthlib が未インストールです。\n"
            "  pip install google-auth-oauthlib\n"
            "を実行してから再度お試しください。",
            file=sys.stderr,
        )
        return 1

    client_id = _require_env("GOOGLE_FIT_CLIENT_ID")
    client_secret = _require_env("GOOGLE_FIT_CLIENT_SECRET")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    # offline + consent を指定して必ず refresh token を発行させる。
    creds = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )

    if not creds.refresh_token:
        print(
            "refresh token を取得できませんでした。\n"
            "Google アカウントのアプリ連携から既存の許可を一度解除し、"
            "再度実行してください (prompt=consent で再発行されます)。",
            file=sys.stderr,
        )
        return 1

    path = _save_token(creds.refresh_token)

    # token 値そのものは出力しない。長さのみ表示して取得成功を示す。
    print("✅ 新しい refresh token を取得しました。")
    print(f"   保存先: {path}  (.gitignore 済み / 権限 600)")
    print(f"   token 長: {len(creds.refresh_token)} 文字 (値は表示しません)")
    print()
    print("次の手順:")
    print("  1. Render ダッシュボード → 対象サービス → Environment を開く")
    print("  2. GOOGLE_FIT_REFRESH_TOKEN の値を、上記ファイルの中身で置き換える")
    print("     (ファイルを開いてコピー&ペースト)")
    print("  3. 保存して再デプロイ → cron 実行を待つ、または手動で")
    print("     python google_fit_sync.py --dry-run を実行して HTTP 200 を確認")
    print(f"  4. 確認できたらローカルの {path} を削除する")
    print()
    print("⚠️ token を Notion / PR / チャット / ログへ貼らないこと。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
