"""Google検索を使った企業ページ探索モジュール

企業HPのURLが不明な場合や、追加の社員インタビュー記事を探す場合に使用する。
Google Custom Search APIを利用。
"""

import logging
import os

from src.config import EXTERNAL_INTERVIEW_SITES, EXTERNAL_SEARCH_QUERIES

logger = logging.getLogger(__name__)

GOOGLE_API_AVAILABLE = None  # 遅延チェック
_google_api_warned = False  # API未設定警告を1回だけ表示


def _get_google_build():
    """Google API clientを遅延ロードで取得"""
    global GOOGLE_API_AVAILABLE
    if GOOGLE_API_AVAILABLE is None:
        try:
            from googleapiclient.discovery import build  # noqa: F811
            GOOGLE_API_AVAILABLE = True
            return build
        except (ImportError, Exception):
            GOOGLE_API_AVAILABLE = False
            return None
    elif GOOGLE_API_AVAILABLE:
        from googleapiclient.discovery import build
        return build
    return None


def search_google(query: str, num_results: int = 10) -> list[dict]:
    """Google Custom Search APIで検索

    Args:
        query: 検索クエリ
        num_results: 取得件数（最大10）

    Returns:
        list[dict]: [{"title": str, "url": str, "snippet": str}, ...]
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    cse_id = os.environ.get("GOOGLE_CSE_ID", "")

    global _google_api_warned
    if not api_key or not cse_id:
        if not _google_api_warned:
            logger.warning(
                "Google API未設定。環境変数 GOOGLE_API_KEY, GOOGLE_CSE_ID を設定してください。"
            )
            _google_api_warned = True
        return []

    google_build = _get_google_build()
    if not google_build:
        logger.warning("google-api-python-client が利用できません。")
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


def _dedupe_results(results: list[dict]) -> list[dict]:
    """URL重複を除去"""
    seen = set()
    deduped = []
    for item in results:
        if item["url"] not in seen:
            seen.add(item["url"])
            deduped.append(item)
    return deduped


def search_employee_interviews(company_name: str) -> list[dict]:
    """企業名で社員インタビュー記事を網羅的に検索

    以下の3段階で検索を実施:
    1. 汎用クエリ（設定ファイルのテンプレート）
    2. 主要インタビューサイトへのsite:指定検索
    3. 追加の切り口（職種別・プロジェクト別等）
    """
    results = []

    # --- Phase 1: 設定ファイルのクエリテンプレートで検索 ---
    for query_template in EXTERNAL_SEARCH_QUERIES:
        query = query_template.format(company=company_name)
        results.extend(search_google(query))

    # --- Phase 2: 主要外部サイトにsite:指定で検索 ---
    # サイトを3つずつまとめてOR検索（API呼び出し回数を節約）
    batch_size = 3
    for i in range(0, len(EXTERNAL_INTERVIEW_SITES), batch_size):
        sites = EXTERNAL_INTERVIEW_SITES[i:i + batch_size]
        site_query = " OR ".join(f"site:{s}" for s in sites)
        query = f"{company_name} ({site_query})"
        results.extend(search_google(query))

    # --- Phase 3: 追加の切り口 ---
    extra_queries = [
        f'{company_name} エンジニア インタビュー',
        f'{company_name} 新卒 入社 体験',
        f'{company_name} 代表 メッセージ 社員',
        f'{company_name} プロジェクト 事例 社員',
    ]
    for q in extra_queries:
        results.extend(search_google(q))

    deduped = _dedupe_results(results)
    logger.info(
        "%s: 外部検索で %d 件の候補URL発見（重複除去後）",
        company_name, len(deduped),
    )
    return deduped


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
        f'{company_name} 採用 問い合わせ',
    ]
    results = []
    for q in queries:
        results.extend(search_google(q))
    return _dedupe_results(results)
