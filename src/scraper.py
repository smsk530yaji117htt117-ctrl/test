"""企業HPスクレイピングモジュール

対象企業のWebサイトから以下の情報を自動収集する:
- 先輩社員紹介ページ
- 優秀社員インタビュー
- 採用担当者情報
"""

import logging
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.config import (
    CAREER_PATH_KEYWORDS,
    EMPLOYEE_PAGE_KEYWORDS,
    MAX_PAGES_PER_COMPANY,
    RECRUITER_PAGE_KEYWORDS,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


class CompanyScraper:
    """企業HPから社員情報を収集するスクレイパー"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "ja,en;q=0.9",
        })

    def _get_page(self, url: str) -> BeautifulSoup | None:
        """URLからページを取得してパースする"""
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as e:
            logger.warning("ページ取得失敗: %s - %s", url, e)
            return None

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        """ページ内の全リンクをテキスト付きで抽出"""
        links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            absolute_url = urljoin(base_url, href)
            # 同一ドメインのみ対象
            if urlparse(absolute_url).netloc != urlparse(base_url).netloc:
                continue
            text = a_tag.get_text(strip=True)
            links.append({"url": absolute_url, "text": text})
        return links

    def _matches_keywords(self, text: str, url: str, keywords: list[str]) -> bool:
        """テキストまたはURLがキーワードにマッチするか判定"""
        combined = (text + " " + url).lower()
        return any(kw.lower() in combined for kw in keywords)

    def find_career_pages(self, base_url: str) -> list[str]:
        """企業HPのトップから採用関連ページのURLを探索"""
        logger.info("採用ページ探索: %s", base_url)
        soup = self._get_page(base_url)
        if not soup:
            return []

        career_urls = []
        links = self._extract_links(soup, base_url)
        for link in links:
            if self._matches_keywords(link["text"], link["url"], CAREER_PATH_KEYWORDS):
                career_urls.append(link["url"])

        # 重複除去
        return list(dict.fromkeys(career_urls))

    def find_employee_pages(self, career_urls: list[str], base_url: str) -> list[str]:
        """採用ページ群から社員紹介・インタビューページを探索"""
        logger.info("社員紹介ページ探索中...")
        employee_urls = []
        visited = set()
        pages_checked = 0

        # トップページも含める
        urls_to_check = [base_url] + career_urls

        for page_url in urls_to_check:
            if page_url in visited or pages_checked >= MAX_PAGES_PER_COMPANY:
                continue
            visited.add(page_url)
            pages_checked += 1

            time.sleep(REQUEST_DELAY)
            soup = self._get_page(page_url)
            if not soup:
                continue

            links = self._extract_links(soup, page_url)
            for link in links:
                if self._matches_keywords(link["text"], link["url"], EMPLOYEE_PAGE_KEYWORDS):
                    if link["url"] not in visited:
                        employee_urls.append(link["url"])

        return list(dict.fromkeys(employee_urls))

    def find_recruiter_pages(self, career_urls: list[str], base_url: str) -> list[str]:
        """採用担当者情報のページを探索"""
        logger.info("採用担当者ページ探索中...")
        recruiter_urls = []
        visited = set()

        urls_to_check = [base_url] + career_urls
        for page_url in urls_to_check[:10]:
            if page_url in visited:
                continue
            visited.add(page_url)

            time.sleep(REQUEST_DELAY)
            soup = self._get_page(page_url)
            if not soup:
                continue

            links = self._extract_links(soup, page_url)
            for link in links:
                if self._matches_keywords(link["text"], link["url"], RECRUITER_PAGE_KEYWORDS):
                    if link["url"] not in visited:
                        recruiter_urls.append(link["url"])

        return list(dict.fromkeys(recruiter_urls))

    def extract_employee_info(self, url: str) -> dict | None:
        """社員紹介ページから情報を抽出

        Returns:
            dict: {
                "url": str,
                "page_title": str,
                "names": list[str],       # 検出された人名
                "departments": list[str],  # 部署名
                "positions": list[str],    # 役職
                "content_summary": str,    # ページ本文の先頭500文字
            }
        """
        time.sleep(REQUEST_DELAY)
        soup = self._get_page(url)
        if not soup:
            return None

        title = soup.title.get_text(strip=True) if soup.title else ""

        # メインコンテンツ抽出
        # よくあるメインコンテンツ領域を優先
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_=re.compile(r"content|main|entry|interview", re.I))
            or soup.body
        )
        if not main_content:
            return None

        text = main_content.get_text(separator="\n", strip=True)

        # 人名パターン（日本語氏名）
        name_pattern = re.compile(
            r"[一-龥ぁ-んァ-ヶ]{1,4}\s?[一-龥ぁ-んァ-ヶ]{1,4}\s*(?:さん|氏|様)?"
        )
        # 部署パターン
        dept_pattern = re.compile(
            r"[一-龥ぁ-んァ-ヶA-Za-z\s]{2,20}(?:部|課|室|グループ|チーム|事業部|センター)"
        )
        # 役職パターン
        position_pattern = re.compile(
            r"(?:部長|課長|係長|主任|マネージャー|リーダー|ディレクター|"
            r"エンジニア|デザイナー|プランナー|コンサルタント|アナリスト|"
            r"担当|スペシャリスト|エキスパート|アドバイザー)"
        )

        names = list(dict.fromkeys(name_pattern.findall(text)[:10]))
        departments = list(dict.fromkeys(dept_pattern.findall(text)[:10]))
        positions = list(dict.fromkeys(position_pattern.findall(text)[:10]))

        return {
            "url": url,
            "page_title": title,
            "names": names,
            "departments": departments,
            "positions": positions,
            "content_summary": text[:500],
        }

    def extract_recruiter_info(self, url: str) -> dict | None:
        """採用担当者ページから情報を抽出"""
        time.sleep(REQUEST_DELAY)
        soup = self._get_page(url)
        if not soup:
            return None

        title = soup.title.get_text(strip=True) if soup.title else ""
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_=re.compile(r"content|main|entry", re.I))
            or soup.body
        )
        if not main_content:
            return None

        text = main_content.get_text(separator="\n", strip=True)

        # メールアドレス抽出
        emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        # 電話番号抽出
        phones = re.findall(r"(?:0\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{3,4})", text)

        return {
            "url": url,
            "page_title": title,
            "emails": list(dict.fromkeys(emails)),
            "phones": list(dict.fromkeys(phones)),
            "content_summary": text[:500],
        }

    def scrape_company(self, company_name: str, website_url: str) -> dict:
        """1社分の情報を収集するメインメソッド

        Returns:
            dict: {
                "company_name": str,
                "website_url": str,
                "career_pages": list[str],
                "employee_pages": list[dict],
                "recruiter_pages": list[dict],
            }
        """
        logger.info("=== %s のスクレイピング開始 ===", company_name)

        result = {
            "company_name": company_name,
            "website_url": website_url,
            "career_pages": [],
            "employee_pages": [],
            "recruiter_pages": [],
        }

        # Step 1: 採用ページを探す
        career_urls = self.find_career_pages(website_url)
        result["career_pages"] = career_urls
        logger.info("採用ページ %d 件発見", len(career_urls))

        # Step 2: 社員紹介ページを探す
        employee_urls = self.find_employee_pages(career_urls, website_url)
        logger.info("社員紹介ページ %d 件発見", len(employee_urls))

        # Step 3: 社員情報を抽出
        for emp_url in employee_urls[:MAX_PAGES_PER_COMPANY]:
            info = self.extract_employee_info(emp_url)
            if info:
                result["employee_pages"].append(info)

        # Step 4: 採用担当者ページを探す
        recruiter_urls = self.find_recruiter_pages(career_urls, website_url)
        logger.info("採用担当者ページ %d 件発見", len(recruiter_urls))

        # Step 5: 採用担当者情報を抽出
        for rec_url in recruiter_urls[:5]:
            info = self.extract_recruiter_info(rec_url)
            if info:
                result["recruiter_pages"].append(info)

        logger.info("=== %s のスクレイピング完了 ===", company_name)
        return result
