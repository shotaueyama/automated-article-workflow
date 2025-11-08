# 自動記事生成ワークフロー

AI駆動型の記事生成、画像作成、WordPress自動投稿システム

## 機能

✨ **完全自動化ワークフロー**
- ディープリサーチからWordPress投稿まで一貫した処理
- OpenAI GPT-5 mini + DALL-E 3を活用した高品質コンテンツ生成
- GPT-5 mini自動レビュー機能による品質向上
- リアルタイム進行状況監視

📊 **監視・管理機能**
- WebSocket経由のリアルタイムログ配信
- 実行履歴の可視化
- GPT分析による失敗原因の自動特定

🎨 **画像生成**
- 16:9アスペクト比での多様な画像生成
- AI重複チェック機能付きプロンプト生成
- 見出しに応じた自動画像作成

📝 **記事品質**
- 自然な日本語文章生成（3200-3800文字保証）
- リスト使用最小化、人間らしい表現
- 直接HTML生成によるWordPress最適化
- GPT-5 mini自動レビューによる品質向上と修正

🔄 **再実行機能**
- material.mdからの記事再生成
- article.html（優先）またはarticle.mdからの画像生成再開
- ワークフロー中断時の柔軟な再開

🚀 **WordPress統合**
- REST API経由の自動投稿
- カテゴリ設定、画像アップロード対応
- ドラフト/公開状態の選択可能

## セットアップ

1. **依存関係のインストール**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **環境変数の設定**
   `.env.local`ファイルを作成：
   ```bash
   OPENAI_API_KEY=your_openai_api_key
   WP_USERNAME=your_wordpress_username
   WP_APP_PASSWORD=your_wordpress_app_password
   WP_BASE_URL=https://your-site.com/wp-json/wp/v2
   ```

3. **サーバーの起動**
   ```bash
   # ターミナル1: APIサーバー
   source .venv/bin/activate
   set -a && source .env.local && set +a
   python -m uvicorn workflow_server:app --host 127.0.0.1 --port 3000

   # ターミナル2: 監視UI
   source .venv/bin/activate
   python workflow_monitor.py --api-base http://127.0.0.1:3000 --port 8080
   ```

4. **アクセス**
   - 監視UI: http://localhost:8080
   - API: http://localhost:3000

## 使い方

### 基本的なワークフロー
1. 監視UIでテーマを入力
2. 「記事生成開始」をクリック
3. リアルタイムログで進行状況を確認
4. 完了後、WordPressで記事を確認

### 再実行機能
- **記事再生成**: material.mdから記事作成を再開
- **画像生成再開**: article.html（優先）またはarticle.mdから画像生成を再開

### 手動実行
```bash
# 記事生成
python run_workflow.py --theme "あなたのテーマ"

# 画像生成から再開
python run_workflow.py --resume-from-images articles/1
```

## ファイル構成

```
├── workflow_server.py      # メインAPIサーバー
├── workflow_monitor.py     # 監視UI
├── run_workflow.py         # ワークフロー実行エンジン
├── tools/
│   ├── generate_html_from_material.py      # HTML記事生成（レビュー付き）
│   ├── generate_image.py                   # 画像生成
│   └── upload_to_wordpress.py              # WordPress投稿
├── guides/                 # 詳細ガイド
│   ├── server_startup_guide.md
│   └── wordpress_upload_guide.md
└── logs/                   # 実行ログ
```

## ワークフロー詳細

1. **ディープリサーチ** - OpenAI o3-deep-researchによるテーマ調査（material.md生成）
2. **HTML記事生成** - GPT-5 mini による自然な日本語記事作成（article.html生成）
3. **品質レビュー** - GPT-5 mini による記事の自動レビュー・修正
4. **画像生成** - DALL-E 3による多様な画像作成と記事への自動挿入
5. **WordPress投稿** - 自動アップロードと投稿

## トラブルシューティング

詳細は以下のガイドを参照：
- [サーバー起動ガイド](guides/server_startup_guide.md)
- [WordPress投稿ガイド](guides/wordpress_upload_guide.md)

## 要件

- Python 3.8+
- OpenAI API キー
- WordPress REST API アクセス権限

## ライセンス

MIT License