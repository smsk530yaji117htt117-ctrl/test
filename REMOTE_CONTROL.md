# Claude Code Remote Control

Claude Code の Remote Control 機能を使うと、ローカルで実行中のセッションにスマートフォンやブラウザからリモート接続できます。

## 概要

- Claude Code はローカルマシン上で動作し続け、クラウドには移行しません
- マシンは Anthropic API に対して HTTPS 接続でポーリングし、リモートデバイスからの指示を受け取ります
- すべての通信は TLS で暗号化されます

## 使い方

### セッションの開始

ターミナルで以下を実行:

```bash
claude remote-control
```

または、Claude Code セッション内で:

```
/remote-control
```

カスタム名を付ける場合:

```bash
claude remote-control "My Project"
```

### 接続方法

コマンド実行後、URL と QR コードが表示されます。

- ブラウザで URL を開く
- スマートフォンで QR コードをスキャン
- claude.ai/code または Claude モバイルアプリからセッション名で検索

### 全セッションで有効化

Claude Code 内で `/config` を実行し、**Enable Remote Control for all sessions** を有効にします。

## 要件

- Pro、Max、Team、または Enterprise プラン
- `/login` でログイン済みであること
- プロジェクトディレクトリで `claude` を一度実行してワークスペース信頼ダイアログを承認済みであること
- API キーは非対応

## 主な機能

- **ローカル環境をリモートで利用**: ファイルシステム、MCP サーバー、ツール、プロジェクト設定がそのまま使える
- **複数デバイスで同時作業**: ターミナル、ブラウザ、スマートフォンで会話が同期される
- **中断に強い**: ネットワーク切断やスリープから復帰時に自動再接続

## 制限事項

- 1 セッションにつきリモート接続は 1 つまで
- ターミナルウィンドウを閉じるとセッション終了
- 長時間のネットワーク切断（10 分以上）でタイムアウト

## Remote Control vs Claude Code on the Web

| 項目 | Remote Control | Claude Code on the Web |
|------|---------------|----------------------|
| 実行場所 | ローカルマシン | Anthropic クラウド |
| ツール・MCP | 利用可能 | 制限あり |
| 用途 | フル開発環境のリモート利用 | ローカル設定なしの簡易タスク |
