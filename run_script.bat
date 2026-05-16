@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

call "%~dp0load_env.bat"

cd /d "%~dp0"
python "%~1" >> "%~dp0logs\run_log.txt" 2>&1
