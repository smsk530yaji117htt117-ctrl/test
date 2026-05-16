# -*- coding: utf-8 -*-
"""
personal_os_consensus — 全スクリプト共通設定
Notion ページ ID・モデル名・タイムアウト等をここで一元管理する
"""

# ─── Notion ページ ID ────────────────────────────────────────────────────────
NOTION_PAGES = {
    "hub":          "35b5ae2b-8d6a-814a-8dfb-f62143e725c0",  # 個人OSハブ
    "task_board":   "35b5ae2b-8d6a-8198-852d-dedbf8621eb5",  # Task Board
    "current_state":"35c5ae2b-8d6a-8130-b4c0-fce97037688d",  # Current State
    "daily":        "35b5ae2b-8d6a-819c-8540-d890c062a891",  # 50_Daily
    "work":         "35b5ae2b-8d6a-8144-b095-ebf30242228a",  # 10_Work
    "investment":   "35b5ae2b-8d6a-8179-9fcc-f6c396186fb7",  # 20_Investment
    "health":       "35b5ae2b-8d6a-8123-ade1-f642e64533e7",  # 30_Health
    "invest_os":    "35b5ae2b-8d6a-81a8-8356-cb19fa1bdc61",  # 投資OS v9.x
}

# ─── AI モデル ────────────────────────────────────────────────────────────────
CLAUDE_MODEL   = "claude-haiku-4-5-20251001"   # Haiku: 軽量タスク用
CLAUDE_MODEL_S = "claude-sonnet-4-6"           # Sonnet: 高品質タスク用
OPENAI_MODEL   = "gpt-4o-mini"                 # OpenAI: 汎用
GEMINI_MODEL   = "gemini-2.5-flash"            # Gemini: 情報収集・裏取り

# ─── ログ設定 ─────────────────────────────────────────────────────────────────
LOG_DIR           = "logs"
DISPATCHER_LOG    = f"{LOG_DIR}/dispatcher_log.txt"
HEALTH_LOG        = f"{LOG_DIR}/health_sync_log.txt"
LOG_RETAIN_DAYS   = 30

# ─── API タイムアウト（秒）────────────────────────────────────────────────────
API_TIMEOUT = 60
