# -*- coding: utf-8 -*-
"""
環境変数セットアップスクリプト
.env ファイルから環境変数を読み込み、動作確認を行う
"""

import os
import sys
from pathlib import Path


def load_env(env_path: str = ".env") -> dict[str, str]:
    """
    .env ファイルを読み込んで環境変数に設定する
    Windows の cp932/utf-8 混在環境に対応
    """
    loaded: dict[str, str] = {}
    p = Path(env_path)
    if not p.exists():
        print(f"⚠️  {env_path} が見つかりません。.env.example を参考に作成してください。")
        return loaded

    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
        loaded[key] = value
    return loaded


def check_env() -> bool:
    """必須環境変数の存在確認"""
    required = ["NOTION_TOKEN"]
    optional = ["ANTHROPIC_API_KEY"]
    ok = True

    for key in required:
        val = os.environ.get(key, "")
        if val:
            print(f"✅ {key}: 設定済み ({val[:8]}...)")
        else:
            print(f"❌ {key}: 未設定 [必須]")
            ok = False

    for key in optional:
        val = os.environ.get(key, "")
        if val:
            print(f"✅ {key}: 設定済み ({val[:8]}...)")
        else:
            print(f"⚠️  {key}: 未設定 [オプション]")

    return ok


if __name__ == "__main__":
    # Windows環境でのUTF-8出力
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass

    print("=== 環境変数チェック ===")
    loaded = load_env()
    if loaded:
        print(f"  .env から {len(loaded)} 件読み込み\n")
    else:
        print()

    ok = check_env()

    if ok:
        print("\n✅ 環境変数OK。Notion APIを使用できます。")
        print("   python notion_client.py  で接続テストを実行できます。")
    else:
        print("\n❌ 必須の環境変数が不足しています。.env ファイルを作成してください。")
        sys.exit(1)
