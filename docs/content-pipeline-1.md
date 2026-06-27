# コンテンツ自動蓄積パイプライン① — テーマ補充 → note草稿 → GitHub保存

元キット: `routine_content_pipeline_kit.md`（v2／Claude Code 渡し用）

## 目的（Goal）

ルーティンが「新テーマを考える → 記事の草稿を書く → GitHub に保存する」を全部無人で回す。
矢嶋さんの手は運用中ゼロ（出したくないテーマに任意で「却下」を付けるだけ）。
週一でたまった草稿から Chrome 用プロンプトでまとめて手動公開する。

## 成果物（このPRに含まれるもの）

| ファイル | 役割 |
|---|---|
| `content/themes.md` | テーマ台帳（5列テーブル: テーマ名 / 種類 / 出所 / レビュー / 進捗） |
| `content/pipeline.py` | 生成・補充ルーティンの決定論パート（stdlib のみ） |
| `content/drafts/` | 草稿の保存先（`YYYY-MM-DD-slug.md`、1ファイル1記事） |
| `tests/test_content_pipeline.py` | 純粋ロジック＋driver のユニットテスト（ネットワーク非依存） |
| `docs/content-pipeline-1.md` | 本書（設計・検証手順・有効化手順） |

`python3 -m unittest discover -s tests` → 既存と合わせて **43 passed / 0 failed**。

## 役割分担（cloud-robust 方式）

記事本文・新テーマの生成（LLM）と GitHub への commit は **Cloud Routine 側のコネクタ**が行う。
`content/pipeline.py` はそれを安全に・ぶれなく回すための**決定論パート**だけを担う:

- 記事生成の対象選択（`select_next`: レビュー≠却下 かつ 進捗=未着手）
- 草稿ファイル名 `YYYY-MM-DD-slug.md` の確定（`draft_filename`・JST 日付）
- 記事生成／テーマ生成プロンプトの組み立て（`render_generation_prompt` / `render_theme_prompt`）
- 台帳の進捗更新（`mark_done`）と新テーマ追記（`append_themes`・自動/未確認/未着手）

既存の `health/*.py` と同じく **標準ライブラリのみ・秘匿情報を扱わない・失敗は静かに無視せず
非ゼロ終了・`--dry-run` 対応**。

## 台帳の形式（`content/themes.md`）

5 列の Markdown テーブル。

| テーマ名 | 種類 | 出所 | レビュー | 進捗 |
|---|---|---|---|---|
| 例 | 設計思想 | 手動 | 採用 | 未着手 |

- **出所**: `手動` / `自動`（補充ルーティンが足したもの）
- **レビュー**: `採用` / `未確認` / `却下`
- **進捗**: `未着手` / `草稿済み`
- テーマ名は台帳内で一意（重複は parse 時に拒否）。

## 暴走を止める仕組み（採用/却下フラグ）

- 自動生成テーマは `未確認` で入る。記事生成は `未確認` も対象にするので、放置でも回り続ける。
- 週次公開時、矢嶋さんは出したくないテーマに `却下` を付けるだけ。記事生成は **却下を必ずスキップ**する。
- 手動追加テーマを `採用` にすれば確実に記事化される。

## 保存先とブランチ運用（governance）

- 草稿・台帳は専用ブランチ `content-drafts`（main ではない）の `content/` に置く。
- main への直 push はしない。草稿はドラフトブランチに置くだけで merge は不要。
- 本 PR（コード・台帳・本書）は作業ブランチ `claude/new-session-mw1isf` → **ドラフト PR**。
  `themes.md` はルーティンが読み書きする正本なので、有効化時に `content-drafts` 側へ seed する。

## ★ Step 1：GitHub 書き込みの最小検証（作り込む前に必ず／Rule 4）

1. ダミー内容（`test draft` の1行）を `content/drafts/_verify.md` として
   `content-drafts` ブランチに commit するだけのルーティンを1回実行。
2. commit 成功・repo にファイルが出れば合格。失敗ならログ確認
   （コネクタ接続・権限・ブランチ・パス）。
3. 合格してから Step 2 / Step 3 を有効化する。未検証のまま生成は回さない。
   （Step 3 も本稼働前に「台帳に1行追記できるか」を1回だけ確認する。）

## Step 2：記事生成ルーティン（日中枠・1回1記事）

1. `python3 -m content.pipeline --mode plan` 相当で**次の対象テーマと記事生成プロンプト**を得る。
   - 対象 = レビュー≠却下 かつ 進捗=未着手。0件なら `[skip]`（対象0件 → 即終了）。
2. 記事生成プロンプトで草稿本文を生成（LLM）。
3. 草稿を `content/drafts/YYYY-MM-DD-slug.md` として `content-drafts` に commit。
4. 台帳の該当行の進捗を「草稿済み」に更新（重複防止）して commit。

ローカル/橋側で本文ファイルがあるときは
`python3 -m content.pipeline --mode write --body-file draft.md` で
草稿書き出し＋進捗更新まで決定論的に実行できる（`--dry-run` で予定のみ）。

## Step 3：テーマ自動補充ルーティン（週1・記事生成とは別枠）

1. `python3 -m content.pipeline --mode themes-plan` で、既存テーマ・既存草稿名・除外リストを
   埋め込んだ**テーマ生成プロンプト**を得る。
2. プロンプトで重複しない新テーマを5件生成（LLM）。出力は「テーマ名／種類」1行1件。
3. その出力を `python3 -m content.pipeline --mode themes-add --themes-file out.md` に渡すと、
   台帳末尾へ「出所=自動／レビュー=未確認／進捗=未着手」で追記する（既存名・バッチ内重複は除外）。

## slug について

`slug` は草稿ファイル名 `YYYY-MM-DD-slug.md` に使う。タイトルの ascii 成分から生成し、
ascii 成分が無い（日本語のみの）場合はタイトル由来の**安定ハッシュ** `theme-xxxxxxxx` に退避する
（決定論的で一意。草稿は手動公開のためファイル名の可読性は重視しない）。

## 動作確認（ローカル）

```bash
python3 -m unittest discover -s tests              # 自動テスト（43 passed）
python3 -m content.pipeline --mode plan            # 記事生成: 次の1件＋プロンプト
python3 -m content.pipeline --mode themes-plan     # 補充: テーマ生成プロンプト
python3 -m content.pipeline --mode themes-add \
        --themes-file out.md --dry-run             # 補充: 追記予定の確認（非書き込み）
```

## 品質の前提

無人生成の草稿は、対話で詰めた記事ほどの完成度には届かない。週次の公開時が軽いレビュー点
（出す草稿の選別＋却下フラグ）。直したい草稿はその場で窓口 OS に指示すれば調整できる。

## 週次の公開（Chrome・手動のまま）

週一で `content/drafts/` のたまった草稿から出すものを選び、Chrome 用プロンプトで
「下書き作成 → 確認 → 手動公開」。**自動公開はしない**。Chrome プロンプトは公開のたびに
窓口 OS が完成本文を埋め込んで用意する。

## ⚠️ 有効化に必要な手動操作（矢嶋さん承認後 / Claude Code 単独では不可）

本 PR は**コードと台帳と手順の追加のみ**。実 Routine 設定・スケジュール・公開には触れない。

1. Step 1 の最小検証で `content-drafts` への commit を確認する。
2. `content/themes.md` を `content-drafts` ブランチへ seed する。
3. 記事生成ルーティンを日中枠（1回1記事・対象0件は即終了）、補充ルーティンを週1で設定する。
4. 初回数回を観察し、草稿が `content/drafts/` に入り台帳の進捗・追記が正しく回ることを確認。

> merge・Routine 有効化は矢嶋さんの明示承認後に行うこと（自動マージ・自動公開禁止）。
