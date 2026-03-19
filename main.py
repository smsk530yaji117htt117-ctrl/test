#!/usr/bin/env python3
"""企業HP社員情報自動収集ツール

使い方:
    python main.py                              # デフォルトのサンプルCSVを使用
    python main.py --input data/input/my_companies.csv
    python main.py --input data/input/my_companies.csv --output-prefix project1
    python main.py --use-google-search           # Google検索APIも併用

入力CSVの形式:
    tdb_code,company_name,website_url,industry
    270012345,株式会社サンプル商事,https://www.example.co.jp,商社
"""

import argparse
import logging
import sys

import pandas as pd

from src.config import INPUT_DIR
from src.exporter import export_results
from src.scraper import CompanyScraper
from src.search import search_company_website, search_employee_interviews

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraping.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def load_companies(csv_path: str) -> pd.DataFrame:
    """企業一覧CSVを読み込む"""
    df = pd.read_csv(csv_path, dtype=str)
    required_cols = {"company_name"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"CSVに必須カラムがありません: {required_cols - set(df.columns)}")
    return df


def main():
    parser = argparse.ArgumentParser(description="企業HP社員情報自動収集ツール")
    parser.add_argument(
        "--input", "-i",
        default=f"{INPUT_DIR}/companies_sample.csv",
        help="企業一覧CSVファイルのパス",
    )
    parser.add_argument(
        "--output-prefix", "-o",
        default="",
        help="出力ファイル名のプレフィックス",
    )
    parser.add_argument(
        "--use-google-search",
        action="store_true",
        help="Google Custom Search APIを使って追加検索を行う",
    )
    parser.add_argument(
        "--max-companies", "-n",
        type=int,
        default=0,
        help="処理する企業数の上限（0=全件）",
    )
    args = parser.parse_args()

    logger.info("企業一覧を読み込み: %s", args.input)
    df = load_companies(args.input)

    if args.max_companies > 0:
        df = df.head(args.max_companies)

    logger.info("対象企業数: %d社", len(df))

    scraper = CompanyScraper()
    all_results = []

    for idx, row in df.iterrows():
        company_name = row["company_name"]
        website_url = row.get("website_url", "")

        # URLが未設定の場合、Google検索で探す
        if (not website_url or pd.isna(website_url)) and args.use_google_search:
            logger.info("URLが未設定のため検索: %s", company_name)
            website_url = search_company_website(company_name) or ""

        if not website_url or pd.isna(website_url):
            logger.warning("URL不明のためスキップ: %s", company_name)
            continue

        # HPスクレイピング
        result = scraper.scrape_company(company_name, website_url)

        # Google検索で追加のインタビュー記事を探す
        if args.use_google_search:
            search_results = search_employee_interviews(company_name)
            result["google_search_results"] = search_results

        result["tdb_code"] = row.get("tdb_code", "")
        result["industry"] = row.get("industry", "")
        all_results.append(result)

        logger.info(
            "[%d/%d] %s 完了 - 社員紹介: %d件, 採用担当: %d件",
            idx + 1, len(df), company_name,
            len(result["employee_pages"]),
            len(result["recruiter_pages"]),
        )

    # 結果を出力
    output_files = export_results(all_results, args.output_prefix)
    logger.info("=== 全処理完了 ===")
    logger.info("出力ファイル:")
    for key, path in output_files.items():
        if path:
            logger.info("  %s: %s", key, path)


if __name__ == "__main__":
    main()
