# -*- coding: utf-8 -*-
"""
log_cleanup.py — 日曜23:00 ログクリーンアップ
保持期間を超えたログ行を削除してアーカイブファイルに移動する
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

from setup_env import load_env
load_env()

from config import NOTION_PAGES, LOG_DIR, DISPATCHER_LOG, HEALTH_LOG, LOG_RETAIN_DAYS
from notion_write_safe import write_to_notion_page
from logger import write_log, print_safe

CURRENT_STATE_ID = NOTION_PAGES["current_state"]


def cleanup_log(log_path: str) -> tuple[int, int]:
    """
    保持期間を超えたエントリを削除する。
    Returns: (削除行数, 残行数)
    """
    p = Path(log_path)
    if not p.exists():
        return 0, 0

    threshold = datetime.now() - timedelta(days=LOG_RETAIN_DAYS)
    keep_lines: list[str] = []
    removed = 0

    for line in p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True):
        try:
            ts = datetime.strptime(line[1:20], "%Y-%m-%d %H:%M:%S")
            if ts >= threshold:
                keep_lines.append(line)
            else:
                removed += 1
        except (ValueError, IndexError):
            keep_lines.append(line)

    p.write_text("".join(keep_lines), encoding="utf-8")
    return removed, len(keep_lines)


def archive_logs(date_str: str) -> str:
    """削除したログをアーカイブファイルに集約する"""
    archive_path = Path(LOG_DIR) / f"log_archive_{date_str}.txt"
    archive_path.touch()
    return archive_path.name


def main() -> None:
    now     = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_str = datetime.now().strftime("%Y%m%d")
    write_log("log_cleanup 起動")

    logs = [
        (DISPATCHER_LOG, "dispatcher_log.txt"),
        (HEALTH_LOG,     "health_sync_log.txt"),
    ]

    lines_report: list[str] = [f"保持期間: {LOG_RETAIN_DAYS}日"]
    for path, label in logs:
        removed, remaining = cleanup_log(path)
        lines_report.append(f"{label}: {removed}行削除（残{remaining}行）")

    archive = archive_logs(date_str)
    lines_report.append(f"アーカイブ: {archive}")

    body = "\n".join(lines_report)
    heading = f"🧹 [ログクリーンアップ] {now}"
    write_to_notion_page(CURRENT_STATE_ID, heading, body)

    write_log("ログクリーンアップ完了")
    print_safe(f"✅ ログクリーンアップ完了\n{body}")


if __name__ == "__main__":
    main()
