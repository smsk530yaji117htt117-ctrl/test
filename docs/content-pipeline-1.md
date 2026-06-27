# コンテンツ自動蓄積パイプライン① — テーマ在庫 → note草稿 → GitHub保存

元キット: `routine_content_pipeline_kit.md`（Claude Code 渡し用）

## 目的（Goal）

日中ルーティンが「テーマ在庫から1件取得 → note向け草稿を生成 → GitHub に markdown で保存」を
無人で回す。手は運用中ゼロ。週一でたまった草稿から Chrome 用プロンプトでまとめて手動公開する。

## 成果物（このPRに含まれるもの）

| ファイル | 役割 |
|---|---|
| `content/themes.md` | テーマ在庫の正本（未着手/草稿済みを機械可読な書式で管理） |
| `content/pipeline.py` | 生成ルーティンの決定論パート（テーマ選択・草稿名・生成プロンプト・themes 更新）。stdlib のみ |
| `content/drafts/` | 草稿の保存先（`YYYY-MM-DD-slug.md`、1ファイル1記事） |
| `tests/test_content_pipeline.py` | 純粋ロジック＋driver のユニットテスト（ネットワーク非依存） |
| `docs/content-pipeline-1.md` | 本書（設計・検証手順・有効化手順） |

`python3 -m unittest discover -s tests` → 既存と合わせて **35 passed / 0 failed**。

## 役割分担（cloud-robust 方式）

記事本文の生成（LLM）と GitHub への commit は **Cloud Routine 側のコネクタ**が行う。
`content/pipeline.py` はそれを安全に回すための**決定論パート**だけを担う:

- 次に書く未着手テーマの選択（`select_next`）
- 草稿ファイル名 `YYYY-MM-DD-slug.md` の確定（`draft_filename`・JST 日付）
- キット本文そのままの生成プロンプト組み立て（`render_generation_prompt`）
- `themes.md` の該当行を「草稿済み」へ更新（`mark_done`・冪等）

既存の `health/*.py` と同じく **標準ライブラリのみ・秘匿情報を扱わない・失敗は静かに無視せず
非ゼロ終了・`--dry-run` 対応**。

## 保存先とブランチ運用（governance）

- 草稿は専用ブランチ `content-drafts`（main ではない）の `content/drafts/` に置く。
- main への直 push はしない。草稿はドラフトブランチに置くだけで merge は不要
  （公開時はそのブランチから読む）。
- 本 PR（コード・在庫・本書）は作業ブランチ `claude/new-session-mw1isf` → **ドラフト PR**。
  `themes.md` はルーティンが読み書きする正本なので、有効化時に `content-drafts` 側へ
  seed する（本 PR の `content/themes.md` がその初期版）。

## ★ Step 1：最小検証（作り込む前に必ず／Rule 4）

本実装の前提として、まず「ルーティンが実際に GitHub へ書けるか」だけを確認する。

1. ダミー内容（`test draft` の1行）を `content/drafts/_verify.md` として
   `content-drafts` ブランチに commit するだけのルーティンを1回実行。
2. commit 成功・repo にファイルが出れば合格。失敗ならログ確認
   （コネクタ接続・権限・ブランチ・パス）。
3. 合格してから Step 2（生成ルーティン）を有効化する。未検証のまま生成は回さない。

## Step 2：生成ルーティンの動き

スケジュール（既存の日中枠 09/13/17 JST に相乗り、または専用枠1つ。1回1記事）で、
ルーティンは以下を行う。`pipeline.py` の出力をそのまま使うと決定論部分がぶれない。

1. `python3 -m content.pipeline --mode plan` 相当で**次の未着手テーマと生成プロンプト**を得る。
   - 未着手が0件なら `[skip]`（対象0件 → 即終了。既存ルーティンの空振りガードと統一）。
2. 生成プロンプトで草稿本文を生成（LLM）。
3. 草稿を `content/drafts/YYYY-MM-DD-slug.md` として `content-drafts` に commit。
4. `themes.md` の該当行を「草稿済み」に更新（`｜draft: <ファイル名>` を追記）して commit
   （重複生成の防止＝冪等）。

参考: ローカル/橋側で本文ファイルがある場合は
`python3 -m content.pipeline --mode write --body-file draft.md` で
草稿書き出し＋themes 更新まで決定論的に実行できる（`--dry-run` で予定のみ確認可）。

## テーマ在庫の書式（`content/themes.md`）

    - [ ] <タイトル>｜種類: <種類>｜slug: <ascii-slug>

- `[ ]`=未着手 / `[x]`=草稿済み、`slug` は ascii・在庫内で一意（重複は parse 時に拒否）。
- 草稿済みにすると `｜draft: <ファイル名>` が追記される。
- 既出（#1 Cloud Routines 3連敗 / #2 線引き / 既出の3社合議）は重複回避のため在庫に含めない。

## 品質の前提

無人生成の草稿は、対話で詰めた記事ほどの完成度には届かない。週次の公開時が軽いレビュー点。
直したい草稿はその場で窓口 OS に指示すれば調整できる。

## 週次の公開（Chrome・手動のまま）

週一で `content/drafts/` のたまった草稿から出すものを選び、Chrome 用プロンプトで
「下書き作成 → 確認 → 手動公開」。**自動公開はしない**。Chrome プロンプトは公開のたびに
窓口 OS が完成本文を埋め込んで用意する。

## 動作確認（ローカル）

```bash
python3 -m unittest discover -s tests          # 自動テスト（35 passed）
python3 -m content.pipeline --mode plan        # 次の1件＋生成プロンプトを表示
python3 -m content.pipeline --mode write \
        --body-file draft.md --dry-run         # 書き出し予定の確認（非書き込み）
```

## ⚠️ 有効化に必要な手動操作（矢嶋さん承認後 / Claude Code 単独では不可）

本 PR は**コードと在庫と手順の追加のみ**。実 Routine 設定・スケジュール・公開には触れない。

1. Step 1 の最小検証ルーティンで `content-drafts` への commit を確認する。
2. `content/themes.md` を `content-drafts` ブランチへ seed する。
3. 生成ルーティンを日中枠に設定（1回1記事・空振りは即終了）。
4. 初回数回を観察し、草稿が `content/drafts/` に入り themes が草稿済みに更新されることを確認。

> merge・Routine 有効化は矢嶋さんの明示承認後に行うこと（自動マージ・自動公開禁止）。
