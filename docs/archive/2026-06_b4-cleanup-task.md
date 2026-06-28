---
title: "🧹 掃除タスク指示書: B4監査デッドコード削除＋小修正3点"
source_notion_id: 37c5ae2b8d6a815f8fe0fd9d4368f3aa
archived: 2026-06-28
status: 完了
---

# 🧹 掃除タスク指示書: B4監査デッドコード削除＋小修正3点

*作成: 2026-06-11 / 作成者: 窓口OS / 実行者: Claude Code（Dispatcher経由可・30分級）/ 根拠: B4監査レポート 2026-06-11*

# ミッション
B4監査でデッドコード確定したファイルの削除と、本番系の小修正3点を行いPRを提出する。

# 絶対制約
- `consensus.py` / `notion_utils.py` / `bridge.py` / `notify.py` / `bridge_notion.py` / `tests/` / `docs/bridge.md` は削除・改変禁止（`main.py`の下記修正のみ例外）
- PR baseは claude/notion-api-setup-BQGwN（main禁止）、headは新規ブランチ claude/cleanup-b4
- マージしない。PR作成まで
- 要求範囲外の機能追加・リファクタ禁止

# 作業内容

## A. 削除（17件・git rm）
`dispatcher.py` / `daily_investment_report.py` / `position_check.py` / `system_health_check.py` / `weekly_review.py` / `monthly_review.py` / `log_cleanup.py` / `ai_client.py` / `config.py` / `logger.py` / `notion_write_safe.py` / `setup_env.py` / `load_env.bat` / `quick_start_win.bat` / `run_script.bat` / `task_scheduler_setup.bat` / `window_os_prompt.md`

## B. 修正（3点）
1. `main.py`: `subprocess.run([sys.executable, "consensus.py"], cwd=HERE, timeout=480)` に変更し、TimeoutExpired を捕捉しても `bridge.run()` は必ず実行する構造を維持
2. render.yaml: `startCommand: python main.py` に修正
3. `README.md`: 冒頭に「実行面マップ」章を追加—— Render（`main.py`→consensus+bridge、10分毎）/ Cloud Routines 7本 / ThinkPad世代は2026-05-20停止・本コミットで削除 / **本番ブランチは claude/notion-api-setup-BQGwN（mainではない）** を明記

## C. 検証（PR descriptionに結果記載）
- `tests/test_consensus.py` が削除モジュール（config等）をimportしている場合は、テストファイルは削除せず必要最小限の修正のみ行い、修正内容をPR descriptionに明記
- `python -m pytest tests/` 全pass
- `python -c "import main, bridge, notify, bridge_notion"` 成功
- `consensus.py` / `notion_utils.py` の diff = 0行

# 補足
- diffは削除主体（約1,700行マイナス）。行数ガイドラインの例外として処理してよい（B4監査で削除確定済み、タスク起票は矢嶋さん承認済み 2026-06-11。マージは別途承認必要）
- 全ファイルはgit履歴に残るため復元可能
