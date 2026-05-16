# -*- coding: utf-8 -*-
"""
ログ書き込みユーティリティ
- ファイルロック競合を避けるためファイルへの書き込みを分離
- Windows cp932 エンコードエラーを回避
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from config import LOG_DIR, DISPATCHER_LOG


def _ensure_log_dir() -> None:
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)


def write_log(message: str, log_file: str = DISPATCHER_LOG) -> None:
    """タイムスタンプ付きでログファイルに追記する"""
    _ensure_log_dir()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}\n"
    try:
        with open(log_file, "a", encoding="utf-8", errors="replace") as f:
            f.write(line)
    except Exception:
        pass  # ログ書き込み失敗は握りつぶす（本処理を止めない）


def print_safe(message: str) -> None:
    """絵文字・日本語を含む文字列を安全に標準出力する"""
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", errors="replace").decode())


def get_recent_errors(log_file: str, hours: int = 24) -> list[str]:
    """指定ファイルから直近 N 時間以内のエラー行を返す"""
    from datetime import timedelta
    threshold = datetime.now() - timedelta(hours=hours)
    errors: list[str] = []
    p = Path(log_file)
    if not p.exists():
        return errors
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if "エラー" not in line and "ERROR" not in line and "error" not in line:
            continue
        try:
            ts_str = line[1:20]
            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            if ts >= threshold:
                errors.append(line)
        except ValueError:
            pass
    return errors
