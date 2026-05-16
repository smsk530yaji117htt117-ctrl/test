@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
echo.
echo ===================================================
echo  Personal OS Consensus セットアップ開始
echo ===================================================
echo.

:: ── 1. Gitクローン（初回のみ） ──────────────────────────────
if not exist "consensus.py" (
    echo [1/5] リポジトリをクローン中...
    git clone https://github.com/smsk530yaji117htt117-ctrl/test .
    if errorlevel 1 (
        echo ERROR: クローンに失敗しました。GitHubへの接続を確認してください。
        pause & exit /b 1
    )
    echo      完了
) else (
    echo [1/5] ファイルが既に存在します。クローンをスキップします。
    git pull origin claude/notion-api-setup-BQGwN 2>nul || git pull origin main 2>nul
)

:: ── 2. 仮想環境の作成 ──────────────────────────────────────
echo.
echo [2/5] Python仮想環境を作成中...
if not exist "venv\" (
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Pythonが見つかりません。https://python.org からインストールしてください。
        pause & exit /b 1
    )
    echo      完了
) else (
    echo      既存のvenvを使用します
)

:: ── 3. ライブラリインストール ───────────────────────────────
echo.
echo [3/5] ライブラリをインストール中（初回は数分かかります）...
call venv\Scripts\activate
pip install -q -r requirements.txt
if errorlevel 1 (
    echo ERROR: インストールに失敗しました。
    pause & exit /b 1
)
echo      完了

:: ── 4. APIキーの入力と .env ファイルの作成 ──────────────────
echo.
echo [4/5] APIキーを入力してください（貼り付けてEnter）
echo.
set /p ANTHROPIC_API_KEY="Anthropic APIキー（sk-ant-）: "
set /p OPENAI_API_KEY="OpenAI APIキー  （sk-proj-）: "
set /p GEMINI_API_KEY="Gemini APIキー  （AIza）   : "
set /p NOTION_TOKEN="Notion Token    （ntn_）   : "

(
    echo ANTHROPIC_API_KEY=%ANTHROPIC_API_KEY%
    echo OPENAI_API_KEY=%OPENAI_API_KEY%
    echo GEMINI_API_KEY=%GEMINI_API_KEY%
    echo NOTION_TOKEN=%NOTION_TOKEN%
    echo NOTION_DATABASE_ID=7cb72b048ffa427f808010bd8213d563
    echo RENDER_DEPLOY=false
) > .env
echo      .envファイルを作成しました

:: ── 5. 動作テスト ──────────────────────────────────────────
echo.
echo [5/5] consensus.py を実行中...
echo      （NotionのPending行を処理します）
echo.
python consensus.py

echo.
echo ===================================================
echo  セットアップ完了！
echo  次回以降は以下のコマンドだけで実行できます：
echo.
echo    venv\Scripts\activate
echo    python consensus.py
echo ===================================================
echo.
pause
