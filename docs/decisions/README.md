# 決定パッケージ一覧（人間判断待ちの前裁き）

改善エンジンのしくみ3。code-only で潰せない（戦略・インフラ・スキーマ・Render）項目を、
矢嶋さんが**選ぶだけ**にするため前裁きしたもの。テンプレ: [../decision-package-template.md](../decision-package-template.md)。

| # | 決める問い | 推奨 | 依存 | 影響(Render/スキーマ/挙動) |
|---|---|---|---|---|
| [⑤](05-branch-divergence.md) | canonical ブランチの確定＋health/移植 | 本番系を正本化 | なし（④の前提） | 確認のみ / なし / なし |
| [④](04-weight-zero-input.md) | 体重手入力ゼロ化（健康OS自動化①有効化） | 有効化（Render Cron） | ⑤＋OAuth | あり / なし / あり |
| [⑥](06-meeting-routing-live.md) | 会議→Handoff 自動起票の live 化 | 条件付きGo（カナリア） | Render env | あり / なし / あり |

## 進め方の推奨順
1. **⑤** を決める（他の置き場・deploy 元が定まる）。
2. **④** … ⑤確定後に health/ 移植 PR（エージェント）＋ OAuth/Render（人間）。
3. **⑥** … 独立。カナリア用テスト PR（エージェント）＋ Render env 1日 live（人間）。

各項目とも、エージェントが代行できるのは **PR 作成まで**。Render/OAuth/スキーマ/実 live 切替は人間。
