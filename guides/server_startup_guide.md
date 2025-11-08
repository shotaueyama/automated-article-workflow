# サーバー起動マニュアル（監視UI＋ワークフローAPI）

この記事では、自動記事生成ワークフロー（`run_workflow.py`）と監視UIを正常に稼働させるための手順をまとめます。ポート利用制限がある環境を想定し、設定済みの組み合わせ（API 3000番、監視UI 8080番）で説明します。

---

## 1. 前提

- 仮想環境 `.venv` が作成済みで、`pip install -r requirements.txt` を終えていること。
- `.env.local` で `OPENAI_API_KEY`、`WP_USERNAME` など必要な環境変数を設定済み。
- `logs/` ディレクトリに書き込み可能（サーバーログを出力します）。

---

## 2. APIサーバ（workflow_server）を起動

1. ターミナルでリポジトリのルートへ移動:
   ```bash
   cd /Users/shotaueyama/Desktop/gendocs
   ```
2. 仮想環境を有効化し、環境変数をロード:
   ```bash
   source .venv/bin/activate
   set -a && source .env.local && set +a
   ```
3. `uvicorn` で `workflow_server` を起動（ポート 3000）:
   ```bash
   python -m uvicorn workflow_server:app --host 127.0.0.1 --port 3000
   ```
   - 起動ログは `logs/workflow_server.log` に保存されます（FastAPI + OpenAI + WordPress連携のAPI）。
   - **重要**: `.env.local` から環境変数（OPENAI_API_KEY、WordPress認証情報）を自動読み込みします。
   - もしポートが使用できない場合は、環境で許可されている別のポートに変えて再実行してください。

> バックグラウンド起動したい場合は `nohup ... &` などを利用し、PID を控えておくと便利です。

---

## 3. 監視UI（workflow_monitor）を起動

1. 別ターミナルを開き、同じく仮想環境をアクティブ化:
   ```bash
   cd /Users/shotaueyama/Desktop/gendocs
   source .venv/bin/activate
   ```
2. `workflow_monitor.py` を API 基本URL 3000番、表示ポート 8080番で起動:
   ```bash
   python workflow_monitor.py --api-base http://127.0.0.1:3000 --port 8080
   ```
   - 監視UIのログは `logs/workflow_monitor.log` に保存されます。
   - `http://localhost:8080` にアクセスすると、リアルタイムログ・履歴・GPT分析ボタン付きの監視画面が表示されます。
   - ポートが許可されていない場合は、利用可能な番号に変更してください（例: 8081、8082 など）。

---

## 4. 停止方法

- フォアグラウンドで起動している場合は `Ctrl+C`。
- バックグラウンドで起動した場合は、起動時に控えた PID を `kill <PID>` で停止。PID が取れない環境では、ログを確認しながら該当プロセスを終了させてください。

---

## 5. トラブルシューティング

| 症状 | 対処 |
| --- | --- |
| `error while attempting to bind ... operation not permitted` | 該当ポートが使用不可。別ポートを選択するか、/etc/hostsなどの制約を確認。 |
| ブラウザから `ERR_CONNECTION_REFUSED` | サーバープロセスが起動していないか、別ポートで待ち受けている。ログや `nohup` 出力をチェック。 |
| GPT分析ボタンでエラー | `workflow_server.py` が OpenAI へアクセスできる状態か（APIキー設定、ネットワーク許可）を確認。 |
| WordPress へ投稿できない | `tools/upload_to_wordpress.py` のログを参照。カテゴリID、認証情報、API権限が正しいか確認。`.env.local`のWordPress設定を確認。 |
| リアルタイムログが表示されない | WebSocket接続の問題。ワークフロー実行中のみログ配信されます。ブラウザのコンソールでエラーを確認。 |
| 画像生成で類似画像が生成される | AI重複チェック機能が動作中。OpenAI APIキーが正しく設定されているか確認。 |
| HTML変換に失敗する | markdownライブラリが不足。`pip install markdown`で再インストール。 |

---

## 6. 実行順序まとめ

```bash
# ターミナル1: APIサーバー起動
cd /Users/shotaueyama/Desktop/gendocs
source .venv/bin/activate
set -a && source .env.local && set +a
python -m uvicorn workflow_server:app --host 127.0.0.1 --port 3000

# ターミナル2: 監視UI起動
cd /Users/shotaueyama/Desktop/gendocs
source .venv/bin/activate
python workflow_monitor.py --api-base http://127.0.0.1:3000 --port 8080
```

これで `http://localhost:8080` の監視画面からワークフローをチェックし、`http://127.0.0.1:3000` の API へリクエストを送る準備が整います。以下の機能が利用可能です：

**新機能（最新版）:**
- ✨ **記事生成開始**: テーマ入力から自動ワークフロー実行
- 📁 **記事再生成**: material.mdから記事生成を再開
- 🎨 **画像生成再開**: article.mdから画像生成を再開
- 📊 **リアルタイムログ**: WebSocket経由でワークフロー進行状況を監視
- 🤖 **GPT分析**: 失敗したワークフローの原因分析
- 📝 **実行履歴**: 過去のワークフロー実行結果を一覧表示

**ワークフロー構成:**
1. ディープリサーチ (material.md生成)
2. 記事生成 (article.md生成) - 自然な文章、リスト最小化
3. 画像生成 (AIプロンプト + 重複チェック) - 16:9、多様性重視
4. HTML変換 (article.html生成) - プレビュー用
5. WordPress投稿 (自動アップロード)

---

不具合が発生した場合は `logs/workflow_server.log` / `logs/workflow_monitor.log` を確認し、エラーメッセージに従ってポート変更や権限の調整を行ってください。
