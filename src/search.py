"""Google検索を使った企業ページ探索モジュール

企業HPのURLが不明な場合や、追加の社員インタビュー記事を探す場合に使用する。
Google Custom Search APIを利用。
"""

import logging
import os

logger = logging.getLogger(__name__)

# Google APIが利用可能かチェック
try:
    from googleapiclient.discovery import build as google_build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False


def search_google(query: str, num_results: int = 5) -> list[dict]:
    """Google Custom Search APIで検索

    Args:
        query: 検索クエリ
        num_results: 取得件数（最大10）

    Returns:
        list[dict]: [{"title": str, "url": str, "snippet": str}, ...]
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    cse_id = os.environ.get("GOOGLE_CSE_ID", "")

    if not api_key or not cse_id:
        logger.warning(
            "Google API未設定。環境変数 GOOGLE_API_KEY, GOOGLE_CSE_ID を設定してください。"
        )
        return []

    if not GOOGLE_API_AVAILABLE:
        logger.warning("google-api-python-client がインストールされていません。")
        return []

    try:
        service = google_build("customsearch", "v1", developerKey=api_key)
        res = service.cse().list(q=query, cx=cse_id, num=num_results).execute()
        items = res.get("items", [])
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
            for item in items
        ]
    except Exception as e:
        logger.error("Google検索エラー: %s", e)
        return []


def search_employee_interviews(company_name: str) -> list[dict]:
    """企業名で社員インタビュー記事を検索"""
    queries = [
        f'{company_name} 社員インタビュー',
        f'{company_name} 先輩社員 紹介',
        f'{company_name} 採用 社員の声',
    ]
    results = []
    seen_urls = set()
    for q in queries:
        for item in search_google(q):
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                results.append(item)
    return results


def search_company_website(company_name: str) -> str | None:
    """企業名から公式サイトURLを検索で特定"""
    results = search_google(f"{company_name} 公式サイト", num_results=3)
    if results:
        return results[0]["url"]
    return None


def search_recruiter_info(company_name: str) -> list[dict]:
    """企業名で採用担当者情報を検索"""
    queries = [
        f'{company_name} 採用担当者',
        f'{company_name} 人事部 採用',
    ]
    results = []
    seen_urls = set()
    for q in queries:
        for item in search_google(q):
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                results.append(item)
    return results
