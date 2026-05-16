# Personal OS Consensus

Claude・Gemini・OpenAIの3社に同じ質問を投げ、統合分析をNotionに自動保存するシステムです。

---

## システムの全体像

矢嶋さんが重要な判断をする際に、NotionのAI Consensus Logに質問を書くだけで、
3社のAIが並列に回答し、Claudeが統合分析を生成してNotionに書き戻します。

---

## 質問を投入する方法

1. Notionで「AI Consensus Log」データベースを開く
   - 場所: 個人OSハブ → AI Consensus Log
2. 「+ 新規」をクリックして新しい行を追加
3. 以下を入力：
   - **Question**（必須）: 聞きたいことを自由に入力
   - **Status**: `Pending` を選択
   - **Category**: 投資 / キャリア / 健康 / システム設計 / その他 から選択

---

## ローカルで実行する方法

ターミナル（コマンドプロンプト）を開いて以下を実行：

```
cd %USERPROFILE%\Documents\personal_os_consensus
venv\Scripts\activate
python consensus.py
```

実行すると Status=Pending の質問がすべて処理されます。

---

## 結果の確認方法

- Notionの「AI Consensus Log」を開く
- Status が **Complete** になった行をクリック
- **Claude_Response** / **Gemini_Response** / **GPT_Response**: 各社の回答
- **Synthesis**: Claudeによる統合分析（最重要）
- **Tags**: 信頼度タグ（確定 / 推測 / 未確認）

---

## 後日 Outcome 列に結果を記入する方法

判断から数週間後、実際の結果が出たら：

1. 該当行を開く
2. **Outcome** 列に「結果どうだったか」を自由記述
3. **Accuracy_Claude / Accuracy_Gemini / Accuracy_GPT** に 1〜5 で評価入力
4. **Status** を `Reviewed` に変更

→ これが蓄積されると「どのAIが当たりやすいか」が可視化されます。

---

## クラウド実行への切り替え方法

Render.comにデプロイすると、Pendingの質問が10分ごとに自動処理されます。
手順は [deploy_guide.md](./deploy_guide.md) を参照してください。

---

## トラブルシューティング

| エラー | 対処法 |
|--------|--------|
| `ANTHROPIC_API_KEY が未設定` | `.env` に `ANTHROPIC_API_KEY=sk-ant-...` を追加 |
| `NOTION_TOKEN が未設定` | `.env` に `NOTION_TOKEN=ntn_...` を追加 |
| `[APIエラー：取得できませんでした]` | APIキーの有効期限・残高を確認 |
| `cp932 codec エラー` | `run_script.bat` 経由で実行（chcp 65001が適用される）|
| `body.children.length > 2000` | consensus.py の `_truncate()` が自動対応済み |

エラーが解消しない場合は Claude.ai にエラー文をそのまま貼り付けてください。
