# Drive画像 read_file_content 検証レポート

**調査日**: 2026-06-15  
**実施**: Dispatcher Routine (Claude Code)  
**対象 Handoff**: [健康OS自動化②(調査)](https://app.notion.com/p/3805ae2b8d6a81e4a319ce33b5e87624)

---

## 結論

**NO — 自律 Routine による進捗写真の有用な下読みは現時点では不可能**

`read_file_content` は JPEG/PNG 画像に対して空文字列を返す。NL 記述は提供されない。  
現行の「週1で人がチャットに貼る」手作業は、当面の最小必要工数として確定。

---

## 検証内容

### テスト対象

Google Drive 内の JPEG ファイル 2件を使用:

| ファイル ID | サイズ | MIME |
|---|---|---|
| `1JWmshIBccN3Q2MSLBazULy-4_EAqLgdn` | 117,331 bytes | image/jpeg |
| `1w-BunuFSybzjhcWSVAP4HTke533bIA_R` | 455,709 bytes | image/jpeg |

### テスト 1: `read_file_content`

```
入力: fileId = "1JWmshIBccN3Q2MSLBazULy-4_EAqLgdn"
出力: {"fileContent": ""}

入力: fileId = "1w-BunuFSybzjhcWSVAP4HTke533bIA_R"
出力: {"fileContent": ""}
```

**結果**: 両ファイルともに空文字列。NL 記述なし。  
ツールの対応 MIME タイプに `image/jpeg` と `image/png` が列挙されているにも関わらず、実際のコンテンツは空。

### テスト 2: `get_file_metadata`（contentSnippet 確認）

```
contentSnippet: ""
```

**結果**: メタデータの contentSnippet も空。テキスト抽出不可。

---

## 各方式の評価

| 方式 | 実測結果 | 使用可否 |
|---|---|---|
| `read_file_content` (NL記述) | 空文字列を返す | ❌ 不可 |
| `contentSnippet` (メタデータ) | 空 | ❌ 不可 |
| Drive サムネイル取得 | 未実装（MCP に取得ツールなし） | ❌ 不可 |
| `download_file_content` (base64) | 技術的には取得可能だが、Routine が Vision 解析を持たない | △ 要 Vision API |

---

## 推奨事項

1. **現状確定**: 「週1で人がチャットに貼る」方式を最小手作業として運用継続
2. **将来拡張の条件**: Vision API（Google Cloud Vision または Claude Vision）を Routine に統合できれば自動化可能。ただし追加コスト・実装工数あり
3. **代替案**: 定量的な数値データ（体重ログ等）であれば Drive のスプレッドシートとして保存し、`read_file_content` で読み取れる可能性が高い

---

## 窓口 Claude の事前推論との照合

2026-06-15 の窓口 Claude による事前推論:
> read_file_content は第三者的な汎用NL記述を返すため、(a) 私の臨床的所見の再現にならず、(b) 週次のデルタ比較もできない見込み

**実測の結果**: そもそも NL 記述が返らない（空文字列）。事前推論よりも制約が厳しい状況であることを確認。
