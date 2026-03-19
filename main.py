#!/usr/bin/env python3
"""企業HP社員情報自動収集ツール

使い方:
    python main.py                              # デフォルトのサンプルCSVを使用
    python main.py --input data/input/my_companies.csv
    python main.py --input data/input/my_companies.csv --output-prefix project1
    python main.py --use-google-search           # Google検索APIも併用

入力CSVの形式:
    NO,対応日,対応者,TDB,会社名,業種,案件番号,規模
    1,11月11日,,10009645,伊藤組土建株式会社,一般土木建築工事業,◯ 320,①
"""

import argparse
import logging
import re
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


# 日本語カラム名 → 内部カラム名のマッピング
COLUMN_MAP = {
    "会社名": "company_name",
    "TDB": "tdb_code",
    "業種": "industry",
    # 英語カラム名もそのまま受け付ける
    "company_name": "company_name",
    "tdb_code": "tdb_code",
    "website_url": "website_url",
    "industry": "industry",
}


def _fix_tdb_code(val: str) -> str:
    """Excelの指数表記（4E+08等）を整数文字列に戻す"""
    if not val or pd.isna(val):
        return ""
    val = val.strip()
    if re.match(r'^[\d.]+[Ee][+\-]?\d+$', val):
        try:
            return str(int(float(val)))
        except (ValueError, OverflowError):
            return val
    return val


def load_companies(csv_path: str) -> pd.DataFrame:
    """企業一覧CSVを読み込む（日本語・英語カラム名の両方に対応）"""
    df = pd.read_csv(csv_path, dtype=str)

    # カラム名をマッピング
    rename = {col: COLUMN_MAP[col] for col in df.columns if col in COLUMN_MAP}
    df = df.rename(columns=rename)

    if "company_name" not in df.columns:
        raise ValueError(
            f"CSVに企業名カラムがありません。'会社名' または 'company_name' が必要です。"
            f" 検出されたカラム: {list(df.columns)}"
        )

    # TDBコードの指数表記を修正
    if "tdb_code" in df.columns:
        df["tdb_code"] = df["tdb_code"].apply(_fix_tdb_code)

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

        # HPがある場合はスクレイピング、なくてもGoogle検索のみで進められる
        if website_url and not pd.isna(website_url):
            result = scraper.scrape_company(company_name, website_url)
        else:
            logger.info("URL不明のためHP探索スキップ、外部検索のみ実行: %s", company_name)
            result = {
                "company_name": company_name,
                "website_url": "",
                "career_pages": [],
                "employee_pages": [],
                "external_pages": [],
                "recruiter_pages": [],
            }

        # Google検索で外部インタビュー記事を網羅的に探す
        if args.use_google_search:
            search_results = search_employee_interviews(company_name)
            result["google_search_results"] = search_results

            # 検索結果のURLを実際にスクレイピングして情報抽出
            external_pages = []
            scraped_urls = {p["url"] for p in result["employee_pages"]}
            for sr in search_results:
                if sr["url"] in scraped_urls:
                    continue
                scraped_urls.add(sr["url"])
                logger.info("外部ページスクレイピング: %s", sr["url"])
                ext_info = scraper.scrape_external_page(sr["url"])
                if ext_info:
                    external_pages.append(ext_info)
            result["external_pages"] = external_pages
            logger.info(
                "%s: 外部サイトから %d 件の社員情報を取得",
                company_name, len(external_pages),
            )

        result["tdb_code"] = row.get("tdb_code", "")
        result["industry"] = row.get("industry", "")
        all_results.append(result)

        total_employee = len(result["employee_pages"]) + len(result.get("external_pages", []))
        logger.info(
            "[%d/%d] %s 完了 - HP社員紹介: %d件, 外部記事: %d件, 採用担当: %d件",
            idx + 1, len(df), company_name,
            len(result["employee_pages"]),
            len(result.get("external_pages", [])),
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
