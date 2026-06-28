---
title: "📋 PC作業手順 — Phase 1.3-α セットアップ"
source_notion_id: 36a5ae2b8d6a816c86bec4016e976f00
archived: 2026-06-28
status: 完了
---

# 📋 PC作業手順 — Phase 1.3-α セットアップ

> ✅ **この手順は 2026-05-24 に完了済みです。**
> Phase 1.3-α は動作確認完了、Dispatcher と PR Status Sync は稼働中。
> 本ページは履歴として保持しています。

*作成: 2026-05-24 / 窓口OS (Claude) 作成*

このページをPC で開きながら、上から順に進めてください。所要時間: **60〜90分**。

**前提**: Phase 1.2 セットアップが完了していること。まだなら先に [📋 PC作業手順 — Phase 1.2 セットアップ](2026-05-24_pc-setup-phase-1.2.md) を済ませる。

---

## ⏱ 全体マップ

```
ステップ1: GitHub Personal Access Token (PAT) 発行   (10分)
   ↓
ステップ2: GitHub main ブランチ保護設定              (5分)
   ↓
ステップ3: PersonalOS Dispatcher Routine 作成        (15分)
   ↓
ステップ4: PersonalOS PR Status Sync Routine 作成    (15分)
   ↓
ステップ5: ダミー Handoff で動作確認                  (15-30分)
   ↓
完了 ✅
```

---

## 🔹 ステップ 1: GitHub Personal Access Token (PAT) 発行

Cloud Routine が GitHub にアクセスするための鍵を作ります。

### 1-1. GitHub の Token 発行画面を開く
- ブラウザで [https://github.com/settings/tokens](https://github.com/settings/tokens) を開く
- 右上の「**Generate new token**」→「**Generate new token (classic)**」をクリック
- パスワード再入力を求められたら入力

### 1-2. Token の設定

| 項目 | 入力値 |
|---|---|
| Note (名前) | `Claude Cloud Routine - PersonalOS Dispatcher` |
| Expiration | `90 days`（90日後に更新が必要、長期希望なら `1 year`） |
| Scopes | **repo** にチェック（read/write 全部） |
|  | **workflow** にチェック（任意、GitHub Actions 操作する場合） |

### 1-3. Token を生成して保存
- 一番下の「**Generate token**」をクリック
- **表示された token を必ずコピー**（この画面を閉じると二度と見られない）
- 一時的に安全な場所に保管（パスワードマネージャー推奨）
- 例: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### 1-4. PAT を Claude Code Desktop に登録
- Claude Code Desktop を開く
- 設定（Settings）→ 環境変数 または Secrets セクションを開く
- 新規追加:
	- 名前: `GITHUB_PAT`
	- 値: 1-3でコピーした token
- 保存

**注**: Claude Code Desktop の UI 名称は変わる可能性あり。「環境変数」「Secrets」「Tokens」など類似の項目を探す。見つからない場合は、Cloud Routine 内で直接設定する案内があるはず（ステップ3で対応）。

✅ **PAT が登録できたら次へ**

---

## 🔹 ステップ 2: GitHub main ブランチ保護設定

AI が暴走しても main ブランチが壊れないようにする安全弁です。

### 2-1. 対象 repo を開く
- ブラウザで [https://github.com/smsk530yaji117htt117-ctrl/test](https://github.com/smsk530yaji117htt117-ctrl/test) を開く
- （個人OS 関連の repo。違ったら実際の personal_os_consensus repo へ）

### 2-2. ブランチ保護ルールの追加
- repo の「**Settings**」タブをクリック
- 左サイドバー「**Branches**」をクリック
- 「**Branch protection rules**」セクションの「**Add rule**」または「**Add branch protection rule**」をクリック

### 2-3. ルール内容

| 項目 | 設定 |
|---|---|
| Branch name pattern | `main` |
| Require a pull request before merging | **✓ チェック** |
| Require approvals | ✗ チェックしない（矢嶋さんソロ運用のため） |
| Restrict deletions | **✓ チェック** |
| Block force pushes | **✓ チェック** |
| Allow force pushes (誰か) | ✗ チェックしない |

### 2-4. 保存
- 一番下の「**Create**」または「**Save changes**」をクリック
- ルール一覧に `main` のルールが追加されたことを確認

✅ **保護ルールが有効になったら次へ**

---

## 🔹 ステップ 3: PersonalOS Dispatcher Routine 作成

Ready タスクを自動実装して PR を作る Routine です。

### 3-1. 新規 Routine 作成画面を開く
- Claude Code Desktop の左サイドバー「**Routines**」をクリック
- 右上の「**+ New Routine**」→「**Remote**」を選択

### 3-2. 基本設定

| 項目 | 入力値 |
|---|---|
| 名前 | `PersonalOS Dispatcher` |
| トリガー | `平日 13:00 JST`（月〜金） |
| コネクター | **Notion** ・ **GitHub**（GitHub コネクターを追加。PAT を要求されたらステップ1で発行した token を貼り付け） |

### 3-3. 指示欄に下のプロンプトを貼り付け

```
あなたは PersonalOS の Dispatcher 担当です。Notion AI Handoff DB から Ready タスクを1件取得し、GitHub repo で実装して PR を作る役割です。

【データソース】
- AI Handoff DB ID: f91723343d1b4fed91127cda97adbe59
- ダイジェストページ ID: 36a5ae2b8d6a81ee8b46e86c7941058f
- GitHub repo: smsk530yaji117htt117-ctrl/test
- 矢嶋勇輝 user_id: 173d872b-594c-81b4-af4a-000262688c71

【手順】

1. AI Handoff DB から以下条件の行を取得:
   - Status = Ready
   - Task名が「深掘り:」または「深掘り：」で始まらない
   - 最大1件、Priority High → Medium → Low の順、同 Priority 内では古い順

2. 対象が0件なら「Dispatcher 対象なし」と出力して終了

3. 該当 Handoff の以下フィールドを取得:
   - Task / Goal / Current State / Next Action / Do Not Touch / Risks / Notes / Repository
   - Repository が未指定なら smsk530yaji117htt117-ctrl/test を使う

4. GitHub repo を clone:
   - origin の main を最新化
   - feature ブランチ名: feature/handoff-[Handoff ID の最初の8文字]
   - feature ブランチを作成して切り替え

5. Acceptance Criteria に従って実装:
   - Notes の Acceptance Criteria を読み取り、満たすコードを書く
   - 既存のコーディングスタイルに従う
   - 必要ならテスト追加

6. Do Not Touch 違反チェック:
   - git diff の中に Do Not Touch リスト内のキーワード（.env, APIキー, Notion スキーマ等）があれば実行を中断
   - 該当 Handoff の Status を Blocked に変更、Notes に違反内容を追記
   - ダイジェストに「Blocked: Do Not Touch 違反」とコメント投稿して終了

7. diff が500行を超える場合も中断（肥大化リスク）:
   - Status を Blocked に変更
   - Notes に「diff が500行超で中断、要スコープ縮小」と追記
   - ダイジェストに通知して終了

8. PR を作成:
   - タイトル: [Handoff] {Task}
   - 本文に Goal / Acceptance Criteria のチェックリスト / 変更ファイル一覧 / Handoff ページへのリンクを含める

9. 該当 Handoff の以下を更新:
   - Status を Handed Off に
   - Updated 日付を今日に
   - Notes に追記（既存内容は保持、追記のみ）:
     ## Dispatcher 実行 [YYYY-MM-DD HH:MM]
     PR URL: [URL]
     変更ファイル数: [数]
     追加行数: +[数]
     削除行数: -[数]
     diff サマリ: [3-5行で要約]

10. ダイジェストページ（ID: 36a5ae2b8d6a81ee8b46e86c7941058f）にコメント投稿:
    冒頭に user mention（user_id: 173d872b-594c-81b4-af4a-000262688c71）を入れ、その後に:

    🛠️ Dispatcher 実行結果 [今日の日付]

    実装完了: 1件
    - Task: [Task名]
    - PR: [URL]
    - 変更: [ファイル数]ファイル / +[追加]/-[削除]行

    「○○のPRを見せて」または「マージして」と窓口OSへ

11. 「Dispatcher 実行完了」と出力

【絶対禁止】
- Notion スキーマの変更
- AI Handoff DB 以外への書き込み
- 元 Handoff の Task / Goal / Current State の上書き（Notes 追記のみ）
- API キー、トークン、認証情報の表示・出力
- main ブランチへの直 push
- PR を自分でマージする（マージは PR Status Sync Routine の担当、かつ人間承認後のみ）
- Do Not Touch リスト内の変更
- 「深掘り:」プレフィックス付きタスクの処理（Deep Research Routine の担当）

【エラー時】
- GitHub 認証エラーなら停止、Notion に「GitHub 認証エラー」と記録
- repo clone 失敗なら停止
- 実装が見通せない場合、Status を Error に変更、エラー詳細を Notes に記録
- 同 Handoff の Attempt Count が3以上なら Blocked にして停止

【文言ルール】
- 「未対応」「対応してください」を使わない
- 「実装完了」「PR レビュー待ち」「Do Not Touch 違反」「diff 肥大化」を使う
```

### 3-4. 保存
- 右上の「**保存**」または「**Save**」をクリック
- 一覧に「PersonalOS Dispatcher」が増えたことを確認

✅ **増えたら次へ**

---

## 🔹 ステップ 4: PersonalOS PR Status Sync Routine 作成

人間判断（Approved / Needs Fix / Rejected）を GitHub 操作に反映する事務処理 Routine です。

### 4-1. 新規 Routine 作成
- 「**+ New Routine**」→「**Remote**」を選択

### 4-2. 基本設定

| 項目 | 入力値 |
|---|---|
| 名前 | `PersonalOS PR Status Sync` |
| トリガー | `30分おき`（平日 09:00-21:00 JST、可能なら時間帯指定） |
| コネクター | **Notion** ・ **GitHub** |

**注**: 「30分おき + 時間帯指定」が UI で設定できない場合は、毎時 00分と30分の cron 風指定で代替（例: `0,30 9-21 * * 1-5`）。設定 UI で迷ったら一旦「毎時0分」で作って動かしてみる。

### 4-3. 指示欄に下のプロンプトを貼り付け

```
あなたは PersonalOS の PR Status Sync 担当です。Notion で矢嶋さん（人間）が判断した PR Status（Approved / Needs Fix / Rejected）を GitHub 操作に反映する事務処理担当です。マージしてよいかを Routine 自身が判断することはありません。

【データソース】
- AI Handoff DB ID: f91723343d1b4fed91127cda97adbe59
- ダイジェストページ ID: 36a5ae2b8d6a81ee8b46e86c7941058f
- GitHub repo: smsk530yaji117htt117-ctrl/test
- 矢嶋勇輝 user_id: 173d872b-594c-81b4-af4a-000262688c71

【手順】

1. AI Handoff DB から Status が以下のいずれかの行を取得:
   - Approved
   - Needs Fix
   - Rejected

2. 対象が0件なら「PR Status Sync 対象なし」と出力して終了

3. 各行について、Notes フィールドから「PR URL: 」の行を探して PR URL を取得
   - 見つからなければスキップ、その行の Notes に「PR URL 不明、人間確認要」と追記し Status を Blocked に

4. Status ごとに以下を実行:

   【Approved の場合】（矢嶋さんが「マージして」と指示済み）
   - GitHub API で PR を squash merge
   - Handoff の Status を Done に変更
   - Completed 日付を今日に
   - Notes に追記:
     ## Merge 完了 [YYYY-MM-DD HH:MM]
     マージ済み、main に統合

   【Needs Fix の場合】（矢嶋さんが「直して」と指示済み）
   - PR は閉じない（再実装で更新される）
   - Handoff の Status を Ready に戻す（Dispatcher が再実装する）
   - Notes に追記:
     ## 再実装依頼 [YYYY-MM-DD HH:MM]
     PR: [URL] に対する再実装を Dispatcher へ
     矢嶋さんの指示: [Notes の最新指示を引用]
   - Attempt Count を +1

   【Rejected の場合】（矢嶋さんが「却下」と指示済み）
   - GitHub API で PR をクローズ
   - feature ブランチを削除
   - Handoff の Status を Archived に変更
   - Notes に追記:
     ## 却下 [YYYY-MM-DD HH:MM]
     PR クローズ、ブランチ削除

5. 処理した件数を集計

6. ダイジェストページ（ID: 36a5ae2b8d6a81ee8b46e86c7941058f）にコメント投稿（処理が0件なら投稿しない）:
   冒頭に user mention（user_id: 173d872b-594c-81b4-af4a-000262688c71）を入れ、その後に:

   🔄 PR Status Sync [今日の日付 HH:MM]

   マージ完了: [件数]件
   - [Task名]

   再実装依頼: [件数]件
   - [Task名]

   却下: [件数]件
   - [Task名]

7. 「PR Status Sync 実行完了」と出力

【絶対禁止】
- Routine 自身がマージ可否を判断すること（人間判断 Status を実行するだけ）
- Status が Approved / Needs Fix / Rejected 以外の行への操作
- Notion スキーマの変更
- API キー、トークン、認証情報の表示
- main ブランチへの直 push

【エラー時】
- GitHub API エラーなら該当行はスキップ、次へ
- PR URL が見つからない場合、Notes に「PR URL 不明、人間確認要」と追記し Status を Blocked に
- 部分失敗でも完了分は処理

【文言ルール】
- 「未対応」「対応してください」を使わない
- 「マージ完了」「再実装依頼」「却下」「PR クローズ」を使う
```

### 4-4. 保存
- 「**保存**」をクリック → 一覧に「PersonalOS PR Status Sync」が増えたことを確認

✅ **増えたら次へ**

---

## 🔹 ステップ 5: ダミー Handoff で動作確認

本物のタスクを流す前に、ダミーで一連の流れをテストします。

### 5-1. ダミー Handoff を起票（窓口OSに依頼）
- Claude チャット（窓口OS = 私）に以下を送る:

```
ダミーで Dispatcher を試したい。「personal_os_consensus の README に『2026-05-24 PersonalOS Dispatcher 初回テスト』という1行を追記する」というタスクを Ready で起票して。
```

→ 私が AI Handoff DB に Ready で起票します。

### 5-2. Dispatcher Routine を手動実行
- Claude Code Desktop に戻る
- 「PersonalOS Dispatcher」を開く
- 右上の「**今すぐ実行**」または「**Run Now**」をクリック
- 実行ログを観察

### 5-3. 結果を確認
4つチェック:
- [ ] **GitHub で PR が作成された**
	- [https://github.com/smsk530yaji117htt117-ctrl/test/pulls](https://github.com/smsk530yaji117htt117-ctrl/test/pulls) を開く
	- feature ブランチからの PR が1件できているはず
	- 中身: README に1行追加されているか
- [ ] **Handoff の Status が Handed Off になっている**
	- Notion の AI Handoff DB を開く
	- ダミー Handoff の Status を確認
- [ ] **Handoff の Notes に PR URL が記録されている**
	- Notion の Notes を確認、Dispatcher 実行ログがあるか
- [ ] **ダイジェストページにコメント通知が来ている**
	- スマホで通知を確認、または Notion でコメント確認

全部 ✅ なら **Dispatcher は動いている**。

### 5-4. PR Status Sync をテスト
- Claude チャット（窓口OS = 私）に以下を送る:

```
さっきのダミーPR、マージしていいよ。
```

→ 私が Notion の該当 Handoff の Status を Approved に変更します。
- Claude Code Desktop で「PersonalOS PR Status Sync」を開く
- 「**今すぐ実行**」をクリック
- 結果を確認:
	- [ ] PR が main にマージされた
	- [ ] Handoff の Status が Done になった
	- [ ] Notes に Merge 完了が記録されている
	- [ ] ダイジェストに通知コメント

全部 ✅ なら **PR Status Sync も動いている**。

✅ **両方確認できたら Phase 1.3-α は完成**

---

## 完了後にやること

### 完了報告
- Claude チャット（窓口OS）に「**Phase 1.3-α 動作確認完了**」と送信
- 私が:
	- Phase 1.3 の Status を Handed Off → In Progress（慣らし運用中）に
	- ダッシュボードを更新

### 慣らし運用開始（1〜2週間）
- 小規模タスク（50-200行）を Claude チャットで依頼
- 私が Handoff を起票 → Ready に
- 自動 or 手動で Dispatcher 実行 → PR 作成 → スマホ通知
- PR の中身を私に要約させて、「マージ」「直して」「却下」の判断
- 5-10件こなして「楽」と感じたら Phase 1.3-β に進む

### 次のセッション（Phase 1.3-β）
- Cloud Routine から OpenAI / Gemini API が呼べるか検証（B1 判定）
- 結果に応じて3社レビュー Routine を作成
- 詳細は慣らし完了後に手順書を作成

---

## ❓ うまくいかなかった時

### A. GitHub コネクターが Claude Code Desktop に無い / 設定方法がわからない
→ スクショを撮って私（Claude チャット）に送ってください。代替手段を提案します。場合により、Routine プロンプト内で PAT を直接渡す方式（少しセキュリティ的に弱い）に切り替え可能。

### B. PR が作成されない / Routine がエラー
→ Routine の実行ログをコピーして私に送る。エラーメッセージから原因を切り分けます。

### C. Do Not Touch 違反検知が動かない（誤検知 or 検知漏れ）
→ 慣らし期間中に挙動を観察。問題があればプロンプトの Do Not Touch チェックロジックを改良。

### D. PR が肥大化（500行超）
→ Routine の安全弁が作動し、Blocked になる設計。プロンプト通り動いていれば問題なし。

### E. その他
→ Claude チャットに「○○でつまってる」と送ってください。

---

## 補足: なぜ「PR Status Sync」という名前なのか

以前は「PR Merge Routine」という名前を検討していましたが、これは「AI が勝手にマージする」誤解を招くため変更しました。

**役割の本質**: Routine は判断しない。**人間（矢嶋さん）が窓口OSで判断した結果**（Notion Status の変更）を GitHub 操作に反映する事務処理係。
- マージするか否か → 人間判断
- マージのボタンを押す動作 → Routine が代行（=Status Sync）

この分離が安全弁になっています。
