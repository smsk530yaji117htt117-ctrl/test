"""収集結果をCSV/JSONに出力するモジュール"""

import json
import logging
import os
from datetime import datetime

import pandas as pd

from src.config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def export_results(all_results: list[dict], output_prefix: str = ""):
    """全企業の収集結果をCSVとJSONに出力

    Args:
        all_results: scraper.scrape_company()の戻り値のリスト
        output_prefix: 出力ファイル名のプレフィックス
    """
    ensure_output_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{output_prefix}_" if output_prefix else ""

    # --- 社員情報CSV ---
    employee_rows = []
    for company_data in all_results:
        for emp in company_data.get("employee_pages", []):
            employee_rows.append({
                "企業名": company_data["company_name"],
                "企業URL": company_data["website_url"],
                "ページURL": emp["url"],
                "ページタイトル": emp["page_title"],
                "検出された人名": " / ".join(emp.get("names", [])),
                "部署": " / ".join(emp.get("departments", [])),
                "役職": " / ".join(emp.get("positions", [])),
                "コンテンツ概要": emp.get("content_summary", ""),
            })

    if employee_rows:
        emp_df = pd.DataFrame(employee_rows)
        emp_path = os.path.join(OUTPUT_DIR, f"{prefix}employees_{timestamp}.csv")
        emp_df.to_csv(emp_path, index=False, encoding="utf-8-sig")
        logger.info("社員情報CSV出力: %s (%d件)", emp_path, len(employee_rows))

    # --- 採用担当者情報CSV ---
    recruiter_rows = []
    for company_data in all_results:
        for rec in company_data.get("recruiter_pages", []):
            recruiter_rows.append({
                "企業名": company_data["company_name"],
                "企業URL": company_data["website_url"],
                "ページURL": rec["url"],
                "ページタイトル": rec["page_title"],
                "メールアドレス": " / ".join(rec.get("emails", [])),
                "電話番号": " / ".join(rec.get("phones", [])),
                "コンテンツ概要": rec.get("content_summary", ""),
            })

    if recruiter_rows:
        rec_df = pd.DataFrame(recruiter_rows)
        rec_path = os.path.join(OUTPUT_DIR, f"{prefix}recruiters_{timestamp}.csv")
        rec_df.to_csv(rec_path, index=False, encoding="utf-8-sig")
        logger.info("採用担当者CSV出力: %s (%d件)", rec_path, len(recruiter_rows))

    # --- サマリーCSV（企業ごとの概要）---
    summary_rows = []
    for company_data in all_results:
        summary_rows.append({
            "企業名": company_data["company_name"],
            "企業URL": company_data["website_url"],
            "採用ページ数": len(company_data.get("career_pages", [])),
            "社員紹介ページ数": len(company_data.get("employee_pages", [])),
            "採用担当者ページ数": len(company_data.get("recruiter_pages", [])),
        })

    summary_df = pd.DataFrame(summary_rows)
    summary_path = os.path.join(OUTPUT_DIR, f"{prefix}summary_{timestamp}.csv")
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    logger.info("サマリーCSV出力: %s", summary_path)

    # --- 全データJSON（詳細参照用）---
    json_path = os.path.join(OUTPUT_DIR, f"{prefix}full_results_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    logger.info("JSON出力: %s", json_path)

    return {
        "summary_csv": summary_path,
        "employee_csv": emp_path if employee_rows else None,
        "recruiter_csv": rec_path if recruiter_rows else None,
        "full_json": json_path,
    }
