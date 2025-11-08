# WordPress投稿アップロード手順

この記事では、`tools/upload_to_wordpress.py` を使って HTML記事（またはMarkdown記事）とローカル画像を WordPress（https://link-village.com）へ新規投稿としてアップロードする方法をまとめます。REST API + アプリパスワード（Basic認証）で動作します。

## 1. 事前準備

1. `.venv` を有効化し、依存関係をインストール済みであること  
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. `.env.local` に以下の環境変数を設定  
   ```bash
   WP_USERNAME=info@quon.ink
   WP_APP_PASSWORD="hvgL fsSP C3gs nQs9 8jGD gknJ"
   WP_BASE_URL=https://link-village.com/wp-json/wp/v2
   OPENAI_API_KEY=sk-proj-...
   ```
   → `set -a; source .env.local; set +a` で読み込む。
3. 投稿カテゴリが WordPress 上に存在すること（今回: `QUON COLLEGE > ブログ`）。

## 2. コマンドの実行

```bash
# HTMLファイルのアップロード（推奨）
python tools/upload_to_wordpress.py \
  --html articles/2/article.html \
  --status publish \
  --category-name ブログ \
  --parent-category "QUON COLLEGE"

# Markdownファイルのアップロード（従来方式）
python tools/upload_to_wordpress.py \
  --markdown articles/1/article.md \
  --status draft \
  --category-name ブログ \
  --parent-category "QUON COLLEGE"

# ワークフロー監視UIから自動実行
# http://localhost:8080 の記事生成機能を使用すると自動的に投稿されます
```

### 重要な仕様変更

- **HTMLファイル対応**: `--html` オプションでHTMLファイルを直接アップロード可能
- **h1タグ自動除去**: HTMLコンテンツからh1タグを自動除去し、WordPressタイトル欄のみに設定
- **アイキャッチ画像自動設定**: 最初の画像を自動的にアイキャッチ画像として設定
- **`--status` を `publish` にすると即公開。安全のため `draft` がデフォルト
- **`--skip-title` を付けると WordPress 側に既に入力済みのタイトルを上書きしません

## 3. 新しいワークフロー統合

**自動HTML生成ワークフロー（推奨）:**
1. **記事生成**: ディープリサーチ → 直接HTML生成（h1タグ付き） → GPT-5 miniレビュー → 画像生成 → WordPress投稿
2. **再生成機能**: material.mdまたはarticle.htmlから部分的に再実行可能
3. **リアルタイム監視**: WebSocket経由で進行状況をリアルタイム表示
4. **自動画像多様化**: AIによる重複チェック付きプロンプト生成
5. **品質保証**: レビュー機能による記事品質チェックとレポート生成

**手動スクリプトの処理内容:**

### HTMLファイルの場合
1. HTMLからh1タグを抽出してタイトルとして使用
2. HTMLコンテンツからh1タグを除去（WordPressタイトル欄と重複を避けるため）
3. ローカル画像（例: `images/...png`）をすべて検出し、WordPress の `/media` エンドポイントへアップロード
4. 最初の画像を自動的にアイキャッチ画像として設定
5. 取得した `source_url` に HTML 内のパスを置換
6. 指定カテゴリ（`QUON COLLEGE` とその子カテゴリ `ブログ`）の ID を REST API で取得
7. 新規投稿を `/posts` に作成（Gutenbergブロック形式で投稿）

### Markdownファイルの場合（従来方式）
1. Markdown を HTML に変換（Python Markdown + 拡張機能使用）
2. Markdown の H1 からタイトルを取得し、本文側からはその H1 行を自動的に取り除く
3. 既存の `article.html` ファイルがある場合は優先的に使用
4. 以下、HTMLファイルと同様の処理

**ワークフロー監視UIの場合:**
- リアルタイムログでWordPress投稿の進行状況を確認
- 成功時は投稿URLがログに表示
- 失敗時はGPT分析で原因を特定可能

**手動実行の場合:**
```
Set as featured image: images/20251108162933-section.png
Uploaded images/20251108162933-section.png -> https://link-village.com/wp-content/uploads/...
Created post ID 7055 at https://link-village.com/生成aiで月5万円を目指す：...
Featured image set: media ID 7052
```
のようなログが表示されます。

## 4. よくあるエラー

| 症状 | 対処 |
| --- | --- |
| `401 Unauthorized` | `.env.local`の`WP_USERNAME` / `WP_APP_PASSWORD` が正しいか確認。現在のパスワード: `"hvgL fsSP C3gs nQs9 8jGD gknJ"` |
| `Category 'ブログ' ... not found` | WordPress 側に該当カテゴリが存在するか、親カテゴリが一致しているか確認 |
| `Image path not found` | HTML/Markdownの画像パス（`images/...png`）が実在するかを確認。画像生成ステップが正常完了しているか確認 |
| `WordPress API error (4xx/5xx)` | 応答本文を確認して追加フィールドや権限を調整。ワークフロー監視UIのGPT分析機能を使用 |
| `unrecognized arguments: --html` | 古いバージョンのスクリプト。最新版で `--html` オプションが利用可能 |
| `No H1 or H2 title found in HTML` | HTMLファイルにh1またはh2タグが存在しない。記事生成ツールで適切なHTMLを生成してください |

## 5. 現在利用可能な機能

**ワークフロー監視UI（http://localhost:8080）:**
- ✨ **記事生成開始**: テーマ入力から完全自動化（直接HTML生成）
- 📁 **記事再生成**: material.mdから記事生成を再開
- 🎨 **画像生成再開**: article.htmlから画像生成を再開
- 📊 **リアルタイムログ**: WebSocket経由で進行状況監視
- 🤖 **GPT分析**: 失敗時の原因分析
- 📝 **実行履歴**: 過去のワークフロー結果一覧

**記事品質の改善:**
- **直接HTML生成**: Markdown→HTML変換を省略し、最初からWordPress最適化HTML生成
- **GPT-5 miniレビュー**: 記事生成後の品質チェックと改善提案
- **h1タグ適切処理**: タイトル抽出後、コンテンツからh1除去で重複回避
- **アイキャッチ画像自動設定**: 最初の画像を自動的にアイキャッチに設定
- **自然な文章生成**: リスト使用最小化、人間らしい文章調
- **AI画像プロンプト多様化**: 重複チェック付きプロンプト生成
- **16:9アスペクト比画像**: 1536x1024サイズで統一
- **3200-3800文字の文字数保証**: 文字数不足時の自動拡充機能
- **レビューレポート生成**: `article_review.md`で改善点を文書化

**技術的改善:**
- **WordPressブロックエディタ最適化**: section/article/headerタグ除去
- **画像alt属性クリーニング**: 不要な記号自動除去
- **破損HTMLタグ自動修正**: 正規表現による自動修正
- **環境変数適切設定**: 最新の認証情報対応

**拡張予定:**
- 複数記事の一括アップロード
- 既存投稿の更新機能  
- カスタマイズ可能な投稿設定
- 画像生成スタイルの詳細設定

## 6. 推奨ワークフロー

**完全自動化（推奨）:**
1. ワークフロー監視UI（http://localhost:8080）でテーマ入力
2. 自動でHTML記事生成 → レビュー → 画像生成 → WordPress投稿
3. アイキャッチ画像自動設定、h1タグ適切処理
4. 公開URLの確認

**手動実行:**
```bash
# 最新のHTMLワークフローを使用
python tools/upload_to_wordpress.py --html articles/[ID]/article.html --status publish
```

ワークフロー監視UIを使用することで、手動操作なしで高品質な記事をWordPressに自動投稿できます。h1タグの重複やアイキャッチ画像の手動設定も不要になり、より効率的な記事投稿が可能です。