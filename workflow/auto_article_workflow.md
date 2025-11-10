# 自動記事執筆ワークフロー（2025年最新版）

## 🚀 統合ワークフロー（推奨）

### Web UI経由での完全自動実行

```bash
# サーバー起動
source .venv/bin/activate
set -a && source .env.local && set +a
python -m uvicorn workflow_server:app --host 127.0.0.1 --port 3000 &
python workflow_monitor.py --api-base http://127.0.0.1:3000 --port 8080
```

1. **ブラウザで http://127.0.0.1:8080 を開く**
2. **テーマを入力して「実行」ボタンをクリック**
3. **自動で以下が順次実行される**：
   - リサーチ（DeepResearch + フォールバック）
   - HTML記事生成・レビュー
   - 画像生成（各セクション）
   - WordPress投稿

### コマンドライン統合実行

```bash
python run_workflow.py --theme "調べたいテーマ" --effort medium --status draft --category-name ブログ
```

---

## 🔧 個別ツール実行（手動制御）

### 1. **情報収集** – `tools/deep_research_collect.py`

```bash
source .venv/bin/activate
set -a && source .env.local && set +a
python tools/deep_research_collect.py "調べたいテーマ" --effort medium
```

**特徴**:
- **メイン**: o4-mini-deep-research モデル使用
- **フォールバック**: 自動的に search_research_collect.py に切り替え
- **出力**: `articles/<連番>/material.md`（詳細なリサーチ結果）

### 2. **HTML記事生成** – `tools/generate_html_from_material.py`

```bash
python tools/generate_html_from_material.py \
  --material articles/<連番>/material.md \
  --output articles/<連番>/article.html \
  --model gpt-5-mini-2025-08-07
```

**特徴**:
- **GPT-5-mini**による3200-3800文字の日本語記事
- **WordPress最適化**：ブロックエディタ完全対応
- **自動レビュー機能**：品質チェック・修正
- **出力**: `articles/<連番>/article.html` + レビューレポート

### 3. **画像生成** – `tools/generate_image.py`

```bash
python tools/generate_image.py "見出しテキスト" \
  --size 1792x1024 \
  --quality standard \
  --output-dir articles/<連番>/images \
  --filename "20251109123456-section"
```

**特徴**:
- **DALL-E 3**による高品質画像生成
- **自動見出し抽出**：HTMLからh2タグを検出
- **出力**: `articles/<連番>/images/*.png`
- **注意**: 現在は手動でHTMLに画像タグを挿入する必要あり

### 4. **WordPress投稿** – `tools/upload_to_wordpress.py`

```bash
python tools/upload_to_wordpress.py \
  --html articles/<連番>/article.html \
  --status draft \
  --category-name ブログ \
  --parent-category "QUON COLLEGE"
```

**特徴**:
- **画像自動アップロード**：記事内の画像を一括処理
- **WordPress REST API**：ブロックエディタ形式で投稿
- **アイキャッチ自動設定**：最初の画像をアイキャッチに

---

## 📁 ファイル構成（実際の出力）

```
articles/8/                    # 自動生成される連番フォルダ
├── material.md               # リサーチ結果（詳細）
├── article.html             # WordPress投稿用HTML記事
├── article_review.md        # 自動品質レビューレポート
└── images/                  # 生成画像フォルダ
    ├── 20251109030842-section.png
    ├── 20251109030911-section.png
    └── ... （各セクション画像）
```

---

## ⚡ 再開・部分実行機能

### 画像生成から再開

```bash
python run_workflow.py --resume-from-images articles/8
```

### 記事生成から再開

```bash
python run_workflow.py --resume-from-article articles/8 --status publish
```

---

## 🎯 モデル仕様とフォールバック

### リサーチ段階
- **メイン**: o4-mini-deep-research（深度リサーチ、引用付き）
- **フォールバック**: GPT-5-mini戦略 + GPT-4o-search-preview検索（10セクション反復）

### 記事生成段階
- **記事生成**: gpt-5-mini-2025-08-07
- **レビュー**: gpt-5-mini-2025-08-07（品質チェック・修正）

### 画像生成段階
- **画像**: dall-e-3（1792x1024、standard品質）

---

## 🛠️ 実行時の重要なポイント

### 環境設定
```bash
# 必須：毎回実行前に環境変数を読み込み
source .venv/bin/activate
set -a && source .env.local && set +a
```

### タイムアウト設定
- **リサーチ**: 5-20分（フォールバック時は長時間）
- **記事生成**: 2-5分
- **画像生成**: 5-15分（画像数による）
- **WordPress投稿**: 1-3分

### エラー時の対処
- **DeepResearch失敗**: 自動フォールバックで継続
- **文字数不足**: 自動拡充機能で調整
- **画像生成停止**: 個別に `generate_image.py` 実行
- **WordPress 404**: エンドポイント修正済み（自動解決）

---

## 📊 コスト管理

| 段階 | 使用モデル | 推定コスト/記事 |
| --- | --- | --- |
| リサーチ | o4-mini-deep-research | $0.10-0.30 |
| 記事生成 | gpt-5-mini | $0.02-0.05 |
| 画像生成 | dall-e-3 (6枚) | $0.48 |
| **合計** | - | **$0.60-0.83** |

---

## 🔄 プロンプトカスタマイズ

記事の出力スタイルを変更したい場合は以下を編集：

- **記事生成プロンプト**: `tools/generate_html_from_material.py` (81-127行目)
- **リサーチ指示**: `tools/deep_research_collect.py` または `tools/search_research_collect.py`
- **画像生成**: `tools/generate_image.py`

---

## ✅ 成功事例と実績

- **記事8**: 「デザイナーがAI時代に『人間らしさ』で差をつける方法」
  - リサーチ: 10セクション段階的調査
  - 記事: 3500文字、レビュー済み
  - 画像: 8枚生成・アップロード成功
  - WordPress: 正常投稿（ID: 7194）

この統合ワークフローにより、テーマ入力から WordPress 投稿まで **完全自動化** が実現されています。