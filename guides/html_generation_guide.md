# HTML記事生成ガイド（WordPress最適化対応）

`tools/generate_html_from_material.py` は リサーチ素材（material.md）からWordPress投稿用のHTML記事を生成するツールです。GPT-5-miniを使用して3000-4000文字の日本語記事を生成し、自動レビュー・修正機能も備えています。

---

## 1. システム概要

### 1.1 役割と位置づけ

| 処理段階 | 入力 | 出力 | 備考 |
| --- | --- | --- | --- |
| リサーチ | テーマ/質問 | `material.md` | `deep_research_collect.py` |
| **HTML生成** | `material.md` | `article.html` | **このツール** |
| 画像生成 | `article.html` | 画像ファイル | `generate_image.py` |
| WordPress投稿 | `article.html` + 画像 | WordPress投稿 | `upload_to_wordpress.py` |

### 1.2 主要機能

- **GPT-5-mini記事生成**: リサーチ素材を読みやすい記事形式に変換
- **文字数自動調整**: 3000-4000文字の範囲内に自動調整
- **WordPress最適化**: ブロックエディタ完全対応のHTML構造
- **自動レビュー機能**: 生成後の品質チェックと修正
- **HTMLタグ修復**: 破損したタグの自動修正

---

## 2. 基本的な使用方法

### 2.1 事前準備

```bash
# 仮想環境を有効化
source .venv/bin/activate

# API キーを読み込み
set -a && source .env.local && set +a
```

### 2.2 基本実行コマンド

```bash
python tools/generate_html_from_material.py \
  --material articles/8/material.md \
  --output articles/8/article.html \
  --model gpt-5-mini-2025-08-07
```

### 2.3 デフォルトパスでの実行

```bash
# デフォルト設定で実行（articles/material.md → articles/generated_article.html）
python tools/generate_html_from_material.py
```

---

## 3. 技術仕様

### 3.1 文字数制御

```python
MIN_CHAR_COUNT = 3000  # 最小文字数
MAX_CHAR_COUNT = 4000  # 最大文字数
MAX_ATTEMPTS = 5       # 最大リトライ回数
```

**文字数カウント方式**:
- HTMLタグを除去してからカウント
- 日本語文字（ひらがな・カタカナ・漢字・数字・英字・記号）が対象
- スペースと改行は除外

### 3.2 HTML構造要件

**使用可能タグ**:
- `h1`, `h2`, `h3`, `h4`: 見出し（h1は必須）
- `p`: 段落（150-200文字目安で分割）
- `strong`, `em`: 強調
- `ul`, `ol`, `li`: リスト（必要最小限）

**使用禁止タグ**:
- `blockquote`: WordPressブロック互換性問題
- `section`, `article`, `header`, `main`, `figure`, `div`: 複雑な構造
- `img`: 画像は別途自動生成されるため

### 3.3 WordPress最適化

```html
<!-- 正しい構造例 -->
<h1>記事タイトル（必須、WordPress抽出用）</h1>
<p>導入段落...</p>
<h2>主要セクション</h2>
<p>内容段落...</p>
<h3>サブセクション</h3>
<p>詳細説明...</p>
```

---

## 4. 自動品質制御システム

### 4.1 文字数調整フロー

```python
def generate_html_article_with_retry(material: str, model: str) -> str:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        html_content = generate_article_with_openai(material, model)
        char_count = count_japanese_chars(html_content)
        
        if MIN_CHAR_COUNT <= char_count <= MAX_CHAR_COUNT:
            return html_content  # 適切な文字数
        elif char_count < MIN_CHAR_COUNT:
            # 文字数不足時は拡充処理
            improved_html = improve_article_length(html_content, 3500, model)
            return improved_html
        # 文字数過多時は再生成
```

### 4.2 HTMLタグ修復機能

```python
def fix_broken_html_tags(html_content: str) -> str:
    # 破損したstrongタグを修正
    html_content = re.sub(r'</strong、', '</strong>、', html_content)
    html_content = re.sub(r'</strong。', '</strong>。', html_content)
    
    # 破損したemタグを修正
    html_content = re.sub(r'</em、', '</em>、', html_content)
    html_content = re.sub(r'</em。', '</em>。', html_content)
    
    # 見出しタグの修正
    html_content = re.sub(r'</h([1-6])、', r'</h\1>、', html_content)
    return html_content
```

### 4.3 自動レビュー・修正機能

```python
def review_html_article(html_content: str, model: str) -> tuple[List[str], str]:
    """HTMLコンテンツをレビューし、問題点と修正版を返す"""
    # GPT-5-miniによる自動レビュー
    # 問題点の検出と修正版HTMLを生成
    # JSON形式で結果を返す
```

**レビュー観点**:
- 文章の自然性と読みやすさ
- 断定的すぎる表現の緩和
- 法令・規制への言及の正確性
- HTML構造の最適性
- WordPress互換性

---

## 5. 出力ファイル構成

### 5.1 生成されるファイル

```
articles/8/
├── material.md           # 入力: リサーチ素材
├── article.html         # 出力: メインHTML記事
└── article_review.md    # 出力: レビューレポート
```

### 5.2 レビューレポート例

```markdown
# Review Report for article.html

- Generated: 2025-11-09 12:30:45
- Model: gpt-5-mini-2025-08-07

## Issues
1. 一部の表現が断定的すぎるため、「〜の場合があります」等の表現に修正しました
2. 個別事例であることを明記し、一般化しすぎないよう注意喚起を追加しました
3. 専門家相談の推奨文言を追加しました
```

---

## 6. プロンプト設計

### 6.1 システムプロンプト（重要部分）

```
あなたは、WordPressブロックエディタ向けの日本語記事を直接HTML形式で生成する専門ライターです。

【WordPressブロック対応HTML構造】
- p、h2、h3、h4、img、strong、em、ul、ol、liタグのみ使用
- section、article、header、main、figure、div、blockquoteタグは一切使用禁止
- 極めてシンプルでフラットなHTML構造

【記事品質要件】
- 必ず3200〜3800文字（理想は3500文字）の日本語記事
- 人間らしいブログ調で体験談や感情を織り交ぜた自然な文章
- 機械的なリストや箇条書きを最小限に抑制
```

### 6.2 ユーザープロンプト構造

```python
user_prompt = f"""以下のリサーチメモを踏まえて、WordPressブロックエディタ向けの日本語HTML記事を生成してください。

【重要な要求】
- **必ずh1タグでタイトルから開始する**
- **必ず3200〜3800文字の日本語HTML記事**
- **blockquoteタグは使用禁止**
- 人間らしい自然な文章（機械的なリストは最小限）

=== リサーチメモ ===
{material}
"""
```

---

## 7. ワークフロー統合

### 7.1 統合ワークフローでの使用

```python
# run_workflow.py での呼び出し例
def step_generate_article(article_id: int, log: Dict) -> None:
    input_path = REPO_ROOT / "articles" / str(article_id) / "material.md"
    output_path = REPO_ROOT / "articles" / str(article_id) / "article.html"
    
    cmd = [
        "python", "tools/generate_html_from_material.py",
        "--material", str(input_path),
        "--output", str(output_path),
        "--model", "gpt-5-mini-2025-08-07"
    ]
```

### 7.2 Web API経由での実行

```bash
# workflow_server.py 経由
curl -X POST http://127.0.0.1:3000/workflow/generate-article \
  -H "Content-Type: application/json" \
  -d '{"article_id": 8}'
```

---

## 8. エラーハンドリング

### 8.1 一般的なエラー

| エラー | 原因 | 対処 |
| --- | --- | --- |
| `OPENAI_API_KEY not set` | API key未設定 | `.env.local`読み込み確認 |
| `Material file not found` | 入力ファイルなし | `material.md`のパス確認 |
| `Material file is empty` | 空のファイル | リサーチ工程の確認 |
| `Failed to generate article` | API制限/エラー | 時間を置いて再実行 |
| `Reached maximum attempts` | 文字数条件未達 | プロンプト調整が必要 |

### 8.2 文字数制御の失敗

```python
# 最大試行回数に達した場合の処理
if attempt >= MAX_ATTEMPTS:
    print(f"[WARNING] Reached maximum attempts, returning last result")
    return fix_broken_html_tags(html_content)
```

**対処法**:
1. `material.md`の内容量を確認（少なすぎる/多すぎる）
2. プロンプトの調整
3. モデルの変更（gpt-4o等）

---

## 9. カスタマイズ

### 9.1 文字数範囲の調整

```python
# ファイル先頭の定数を変更
MIN_CHAR_COUNT = 2500  # 最小文字数
MAX_CHAR_COUNT = 4500  # 最大文字数
```

### 9.2 モデルの変更

```bash
# GPT-4oを使用する場合
python tools/generate_html_from_material.py \
  --model gpt-4o \
  --material articles/8/material.md
```

### 9.3 出力ディレクトリの変更

```bash
# カスタムパスで出力
python tools/generate_html_from_material.py \
  --material custom/research.md \
  --output custom/final_article.html
```

---

## 10. 品質管理とベストプラクティス

### 10.1 品質確保

- **レビューログ確認**: `article_review.md`で問題点をチェック
- **文字数確認**: 3200-3800文字の範囲内であることを確認
- **HTML構造**: WordPressプレビューで表示崩れがないか確認
- **コンテンツ品質**: 自然な文章で読みやすいか確認

### 10.2 効率的な運用

```bash
# バッチ処理例（複数記事の一括生成）
for i in {1..5}; do
  python tools/generate_html_from_material.py \
    --material articles/$i/material.md \
    --output articles/$i/article.html
done
```

### 10.3 コスト管理

- **GPT-5-mini料金**: 約$0.01-0.03/記事（3500文字）
- **レビュー込み**: 約$0.02-0.05/記事（生成+レビューの合計）
- **月間予算**: 100記事で約$2-5

---

このガイドは`tools/generate_html_from_material.py`の完全な使用方法を説明しており、リサーチ素材からWordPress対応の高品質HTML記事を自動生成するワークフローを提供します。