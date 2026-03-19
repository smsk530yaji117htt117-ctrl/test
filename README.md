# 企業HP社員情報自動収集ツール

対象企業のWebサイトから先輩社員紹介・インタビュー・採用担当者情報を自動収集するツール。

## セットアップ

```bash
pip install -r requirements.txt
```

## 使い方

### 1. 入力CSVの準備

`data/input/` に企業一覧CSVを配置する。形式:

```csv
tdb_code,company_name,website_url,industry
270012345,株式会社サンプル商事,https://www.example.co.jp,商社
```

- `company_name` (必須): 企業名
- `website_url` (推奨): 企業HP URL
- `tdb_code` (任意): TDBコード
- `industry` (任意): 業種

### 2. 実行

```bash
# 基本実行
python main.py --input data/input/companies.csv

# 出力ファイルにプレフィックスを付ける
python main.py --input data/input/companies.csv --output-prefix 2026Q1

# Google検索APIも併用（URL未設定企業の自動検索 + 追加記事収集）
python main.py --input data/input/companies.csv --use-google-search

# 処理企業数を制限（テスト用）
python main.py --input data/input/companies.csv --max-companies 5
```

### 3. 出力

`data/output/` に以下のファイルが生成される:

| ファイル | 内容 |
|---------|------|
| `summary_*.csv` | 企業ごとの収集概要（ページ数等） |
| `employees_*.csv` | 社員紹介情報（人名・部署・役職・概要） |
| `recruiters_*.csv` | 採用担当者情報（メール・電話・概要） |
| `full_results_*.json` | 全データ（詳細参照用） |

## 処理フロー

```
企業一覧CSV
  ↓
企業HPトップページ取得
  ↓
採用ページリンクを探索（recruit, 採用, saiyo 等のキーワード）
  ↓
社員紹介・インタビューページを探索（先輩社員, 社員インタビュー 等）
  ↓
ページ本文から情報抽出（人名・部署・役職を正規表現で検出）
  ↓
採用担当者ページを探索（採用担当, 人事部 等）
  ↓
連絡先情報を抽出（メール・電話番号）
  ↓
CSV/JSON出力
```

## Google Custom Search API（オプション）

追加検索機能を使う場合、以下の環境変数を設定:

```bash
export GOOGLE_API_KEY="your-api-key"
export GOOGLE_CSE_ID="your-cse-id"
```

## 設定変更

`src/config.py` で以下を調整可能:

- `REQUEST_DELAY`: リクエスト間隔（デフォルト2秒）
- `MAX_PAGES_PER_COMPANY`: 1社あたりの最大探索ページ数
- `EMPLOYEE_PAGE_KEYWORDS`: 社員紹介ページ検出キーワード
- `RECRUITER_PAGE_KEYWORDS`: 採用担当者ページ検出キーワード

## 注意事項

- robots.txt を遵守し、過度なアクセスは避けてください
- リクエスト間隔は `REQUEST_DELAY` で制御されます（デフォルト2秒）
- 収集した個人情報の取り扱いには十分ご注意ください
