"""設定ファイル"""

# Google Custom Search API設定（利用する場合）
GOOGLE_API_KEY = ""  # 環境変数 GOOGLE_API_KEY で上書き可能
GOOGLE_CSE_ID = ""   # 環境変数 GOOGLE_CSE_ID で上書き可能

# スクレイピング設定
REQUEST_TIMEOUT = 15  # 秒
REQUEST_DELAY = 2.0   # リクエスト間の待機秒数（サーバー負荷軽減）
MAX_PAGES_PER_COMPANY = 20  # 1社あたり最大探索ページ数
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 採用ページ探索用キーワード
CAREER_PATH_KEYWORDS = [
    "recruit", "careers", "saiyo", "jinji",
    "採用", "リクルート", "新卒", "中途",
]

# 社員紹介ページ探索用キーワード
EMPLOYEE_PAGE_KEYWORDS = [
    "先輩社員", "社員紹介", "社員インタビュー",
    "人を知る", "働く人", "スタッフ紹介",
    "社員の声", "メンバー紹介", "仲間を知る",
    "people", "interview", "staff", "member",
    "voice", "story", "stories",
]

# 採用担当者ページ探索用キーワード
RECRUITER_PAGE_KEYWORDS = [
    "採用担当", "人事担当", "リクルーター",
    "採用チーム", "人事部", "採用メッセージ",
    "recruiter", "hiring", "hr team",
]

# 出力ディレクトリ
OUTPUT_DIR = "data/output"
INPUT_DIR = "data/input"
