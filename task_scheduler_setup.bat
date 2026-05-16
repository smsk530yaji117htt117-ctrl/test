@echo off
chcp 65001 >nul
:: Windows タスクスケジューラへの自動登録スクリプト
:: 管理者権限で実行すること

set DIR=%~dp0
set PY=%DIR%run_script.bat

echo タスクスケジューラに登録します...

:: 朝7:00 システムヘルスチェック
schtasks /create /tn "PersonalOS_HealthCheck" /tr "\"%PY%\" system_health_check.py" /sc daily /st 07:00 /f

:: 朝7:30 投資日次レポート
schtasks /create /tn "PersonalOS_InvestReport" /tr "\"%PY%\" daily_investment_report.py" /sc daily /st 07:30 /f

:: 朝8:00 朝ディスパッチャ
schtasks /create /tn "PersonalOS_DispatcherAM" /tr "\"%PY%\" dispatcher.py" /sc daily /st 08:00 /f

:: 15:30 ポジションチェック
schtasks /create /tn "PersonalOS_PositionCheck" /tr "\"%PY%\" position_check.py" /sc daily /st 15:30 /f

:: 夜22:00 夜ディスパッチャ
schtasks /create /tn "PersonalOS_DispatcherPM" /tr "\"%PY%\" dispatcher.py" /sc daily /st 22:00 /f

:: 日曜21:00 週次レビュー
schtasks /create /tn "PersonalOS_WeeklyReview" /tr "\"%PY%\" weekly_review.py" /sc weekly /d SUN /st 21:00 /f

:: 日曜23:00 ログクリーンアップ
schtasks /create /tn "PersonalOS_LogCleanup" /tr "\"%PY%\" log_cleanup.py" /sc weekly /d SUN /st 23:00 /f

echo.
echo 登録完了。以下のタスクが追加されました：
schtasks /query /fo LIST /tn "PersonalOS_*" 2>nul | findstr "タスク名"
echo.
pause
