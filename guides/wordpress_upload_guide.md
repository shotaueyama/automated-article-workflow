# WordPress投稿アップロード手順

この記事では、`tools/upload_to_wordpress.py` を使って Markdown 記事とローカル画像を WordPress（https://link-village.com）へ新規投稿としてアップロードする方法をまとめます。REST API + アプリパスワード（Basic認証）で動作します。

## 1. 事前準備

1. `.venv` を有効化し、依存関係をインストール済みであること  
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. `.env.local` に以下の環境変数を設定  
   ```bash
   WP_USERNAME=info@quon.ink
   WP_APP_PASSWORD="61EI wbZP LWwb Fa61 amPk HWV7"
   WP_BASE_URL=https://link-village.com/wp-json/wp/v2
   OPENAI_API_KEY=sk-proj-...
   ```
   → `set -a; source .env.local; set +a` で読み込む。  
   **重要**: 現在は更新されたアプリパスワードを使用してください。
3. 投稿カテゴリが WordPress 上に存在すること（今回: `QUON COLLEGE > ブログ`）。

## 2. コマンドの実行

```bash
# 手動実行の場合
python tools/upload_to_wordpress.py \
  --markdown articles/1/article.md \
  --status draft \
  --category-name ブログ \
  --parent-category "QUON COLLEGE"

# ワークフロー監視UIから自動実行
# http://localhost:8080 の記事生成機能を使用すると自動的に投稿されます
```

- `--status` を `publish` にすると即公開。安全のため `draft` がデフォルト。
- `--markdown` には任意の記事を指定可能。
- スクリプトは Markdown の H1 からタイトルを取得し、本文側からはその H1 行を自動的に取り除きます（ブロックエディタに見出しを重複させないため）。本文は Gutenberg ブロック（段落・見出し・リスト・画像ブロック）形式で投稿されます。画像は `generated-images` 配下のファイルを順番にアップロードします。
- `--skip-title` を付けると WordPress 側に既に入力済みのタイトルを上書きしません。

## 3. 新しいワークフロー統合

**自動ワークフロー（推奨）:**
1. **記事生成**: ディープリサーチ → 記事生成 → 画像生成 → HTML変換 → WordPress投稿
2. **再生成機能**: material.mdまたはarticle.mdから部分的に再実行可能
3. **リアルタイム監視**: WebSocket経由で進行状況をリアルタイム表示
4. **自動画像多様化**: AIによる重複チェック付きプロンプト生成

**手動スクリプトの処理内容:**
1. Markdown を HTML に変換（Python Markdown + 拡張機能使用）。
2. ローカル画像（例: `images/...png`）をすべて検出し、WordPress の `/media` エンドポイントへアップロード。
3. 取得した `source_url` に HTML 内のパスを置換。
4. 指定カテゴリ（`QUON COLLEGE` とその子カテゴリ `ブログ`）の ID を REST API で取得し、新規投稿を `/posts` に作成。本文は Gutenberg ブロック形式に変換され、両方のカテゴリにチェックが入るよう送信します。

**ワークフロー監視UIの場合:**
- リアルタイムログでWordPress投稿の進行状況を確認
- 成功時は投稿URLがログに表示
- 失敗時はGPT分析で原因を特定可能

**手動実行の場合:**
```
Uploaded images/20241108-example.png -> https://link-village.com/wp-content/uploads/...
Created post ID 1234 at https://link-village.com/?p=1234
```
のようなログが表示されます。

## 4. よくあるエラー

| 症状 | 対処 |
| --- | --- |
| `401 Unauthorized` | `.env.local`の`WP_USERNAME` / `WP_APP_PASSWORD` が正しいか、アプリパスワードが有効か確認。環境変数が正しく読み込まれているか確認。 |
| `Category 'ブログ' ... not found` | WordPress 側に該当カテゴリが存在するか、親カテゴリが一致しているか確認。 |
| `Image path not found` | Markdown の画像パス（`images/...png`）が実在するかを確認。画像生成ステップが正常完了しているか確認。 |
| `WordPress API error (4xx/5xx)` | 応答本文を確認して追加フィールドや権限を調整。ワークフロー監視UIのGPT分析機能を使用して詳細分析。 |
| ワークフロー監視UIから投稿に失敗 | `.env.local`の環境変数設定を確認。サーバー再起動後に再試行。リアルタイムログで詳細エラーを確認。 |
| HTML変換でフォーマットが崩れる | markdown拡張機能（extra, codehilite, toc）が正しく動作しているか確認。article.htmlファイルでプレビュー確認。 |

## 5. 現在利用可能な機能

**ワークフロー監視UI（http://localhost:8080）:**
- ✨ **記事生成開始**: テーマ入力から完全自動化
- 📁 **記事再生成**: material.mdから記事生成を再開
- 🎨 **画像生成再開**: article.mdから画像生成を再開
- 📊 **リアルタイムログ**: WebSocket経由で進行状況監視
- 🤖 **GPT分析**: 失敗時の原因分析
- 📝 **実行履歴**: 過去のワークフロー結果一覧

**記事品質の改善:**
- 自然な文章生成（リスト使用最小化）
- AI画像プロンプト多様化（重複チェック付き）
- 16:9アスペクト比画像（1536x1024）
- HTML変換とプレビュー機能
- 3200-3800文字の文字数保証

**拡張予定:**
- 複数記事の一括アップロード
- 既存投稿の更新機能
- カスタマイズ可能な投稿設定
- 画像生成スタイルの詳細設定

ワークフロー監視UIを使用することで、手動操作なしで高品質な記事をWordPressに自動投稿できます。
