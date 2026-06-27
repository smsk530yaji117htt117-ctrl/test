# テーマ在庫（コンテンツ自動蓄積パイプライン）

生成ルーティンはこのファイルを正本として「未着手」のテーマを1件選び、
草稿を生成したら該当行を「草稿済み」に更新する（重複生成の防止＝冪等）。

書式（1行1テーマ・機械可読）:

    - [ ] <タイトル>｜種類: <種類>｜slug: <ascii-slug>

- `[ ]` = 未着手 / `[x]` = 草稿済み
- `slug` は草稿ファイル名 `YYYY-MM-DD-<slug>.md` に使う（ascii 必須・重複不可）
- 草稿済みにすると `｜draft: <ファイル名>` が自動で追記される（追跡用）

<!-- THEMES:BEGIN 行を編集してよいのはこのブロック内のみ -->
- [ ] Notionを外部記憶にしてAIを育てる｜種類: 第二の脳｜slug: notion-second-brain
- [ ] 承認ゲート設計：AIの暴走をどう止めるか｜種類: 設計思想｜slug: approval-gate-design
- [ ] スマホをポストに封印する習慣設計｜種類: 横展開｜slug: phone-in-mailbox-habit
- [ ] 投資OS：感情を排除しルールで売買する｜種類: ビフォーアフター｜slug: investment-os-rules
- [ ] 3社合議エンジンを月1〜2ドルで常駐させた構築記｜種類: インフラ｜slug: three-model-consensus-infra
- [ ] AIに記憶を持たせる：引き継ぎ書＋ログ運用｜種類: ノウハウ｜slug: ai-memory-handoff-log
- [ ] 「面倒だといじらなくなる」を設計に組み込む｜種類: 設計思想｜slug: friction-aware-design
- [ ] 減量OS：計量弁当とストレス評価の仕組み化｜種類: 横展開｜slug: diet-os-measured-bento
<!-- THEMES:END -->

> 既出（別チャットで作成済み・公開待ち。重複させない）: #1 Cloud Routines 3連敗 /
> #2 線引き / 既出の3社合議。これらは在庫に含めない。
