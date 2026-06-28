---
title: "📋 B4監査レポート（削る対象の特定）2026-06-11"
source_notion_id: 37c5ae2b8d6a8126b5facee9a3ab5e36
archived: 2026-06-28
status: 完了
---

# 📋 B4監査レポート（削る対象の特定）2026-06-11

*監査日: 2026-06-11 / 実施: 窓口OS（リポジトリ実物clone＋Notion痕跡調査）/ 目的: 削る対象の特定*

# 1. 実行面マップ（現状）

| 実行面 | 状態 | 中身 |
|---|---|---|
| Render | 稼働中 | `main.py` → `consensus.py`(591行) + bridge系3本。10分毎 |
| Cloud Routines | 稼働中7本 | PR Status Sync / Dispatcher / DR深夜・昼 / 指示処理 / 朝・夕ダイジェスト |
| ThinkPad Task Scheduler | **2026-05-20朝停止（実証）** | 旧dispatcher・投資日次・ポジション・健全性・週次/月次・ログ掃除 |
| Termux (Pixel 7) | 所在不明・リポジ外 | `google_fit_sync.py`（invalid_grantで停止中。.env.exampleにGOOGLE_FIT_*残香） |

停止の根拠: 週次レビュー最終生成 2026-05-17(日) 21:01 JST、以降3回の日曜未生成。50_Daily最終更新 2026-05-20 07:00 JST（健全性チェックの時刻）。Render化(5/22)と整合。

# 2. 削除確定（17件）
- 旧実行系7: `dispatcher.py` / `daily_investment_report.py` / `position_check.py` / `system_health_check.py` / `weekly_review.py` / `monthly_review.py` / `log_cleanup.py`
- 旧基盤5: `ai_client.py` / `config.py` / `logger.py` / `notion_write_safe.py` / `setup_env.py`
- bat 4: `load_env.bat` / `quick_start_win.bat` / `run_script.bat` / `task_scheduler_setup.bat`
- 旧ドキュメント1: `window_os_prompt.md`
- 注: `notion_utils.py` は `consensus.py` 依存のため残す。git履歴で復元可能

# 3. 本番系修正3点
1. `main.py`: subprocessにtimeout=480追加（consensusハング時も橋を実行）
2. render.yaml: startCommandを `python main.py` に修正（実態との乖離解消）
3. README: 実行面マップと「本番ブランチ＝claude/notion-api-setup-BQGwN（mainではない）」を明記（F4再発防止）

# 4. ブランチ負債
22本中19本が掃除候補（実験系12＋feature残骸6＋master）。個別リストを矢嶋さん承認後に削除（別タスク）。mainへの本番統合はリスク不釣り合いのため見送り、README明記で代替。

# 5. Notion側の発見
- **Current Stateフリーズの原因仮説確定**: 旧システムの日次追記（7:00＋15:30）による肥大。肥大は5/20で停止済み。対処は「軽量な新Current Stateを再作成→旧ページアーカイブ」（別タスク）
- AI Consensus LogのTags残置: スキーマ変更禁止のため放置で可

# 6. 推奨着手順
1. 掃除PR（削除17件＋修正3点）← 起票済み。マージ承認時にBridge Queue fireの初実運用検証を兼ねる
2. ブランチ掃除（リスト承認制）
3. Current State軽量再作成
4. Termux google_fitの復旧or廃止判断
