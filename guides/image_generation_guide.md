# AI画像生成ガイド（DALL-E 3 統合ワークフロー）

OpenAI の DALL-E 3 を使用した自動画像生成システムです。記事の見出しから自動的に多様な画像を生成し、HTMLに埋め込む統合ワークフローを提供します。

---

## 1. システム構成と責務

| パス | 役割 |
| --- | --- |
| `run_workflow.py` | メインワークフローエンジン。`step_generate_images()` で画像生成を統合実行。 |
| `articles/<n>/images/` | 記事ごとの画像フォルダ。自動生成された画像がここに保存される。 |
| `articles/<n>/article.html` | HTMLファイル。見出しから画像生成対象を抽出し、生成後に画像パスを挿入。 |
| `tools/generate_image.py` | 単体画像生成CLI（レガシー）。現在はワークフロー統合版を使用。 |
| `.env.local` | `OPENAI_API_KEY` などの機密情報を格納。Git管理対象外。 |
| `workflow_monitor.py` | Web UI (http://localhost:8080) でリアルタイム画像生成進捗を監視。 |

> **重要**: `generated-images/` ディレクトリは廃止されました。すべて記事フォルダ内の `images/` に統一されています。

---

## 2. 自動画像生成ワークフロー（推奨）

### 2.1 ワークフロー監視UI経由（完全自動）

```bash
# サーバー起動
source .venv/bin/activate
set -a && source .env.local && set +a
python -m uvicorn workflow_server:app --host 127.0.0.1 --port 3000 &
python workflow_monitor.py --api-base http://127.0.0.1:3000 --port 8080
```

1. ブラウザで http://localhost:8080 を開く
2. 記事生成フローを実行、または既存記事の「画像生成再開」を選択
3. 自動的にHTML見出しから画像生成対象を抽出
4. DALL-E 3で多様な画像を生成（重複チェック付き）
5. HTMLファイルに画像パスを自動挿入

### 2.2 手動ワークフロー実行

```python
# Pythonスクリプトから直接呼び出し
import sys
sys.path.append('.')
from run_workflow import step_generate_images
from datetime import datetime

log = {
    'run_id': f'manual_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
    'steps': []
}

# 記事ID 2 の画像生成を実行
step_generate_images(2, log)
```

---

## 3. 技術仕様

### 3.1 DALL-E 3 設定

- **モデル**: `dall-e-3`
- **画像サイズ**: `1536x1024` (16:9アスペクト比)
- **品質**: `standard` (コストと品質のバランス)
- **プロンプト言語**: 英語必須（日本語は文字化けするため自動翻訳）

### 3.2 プロンプト生成システム

画像生成は2段階で実行：

1. **プロンプト生成**: ChatGPT（GPT-5 mini）が日本語見出しから英語プロンプトを生成
2. **重複チェック**: 既存プロンプトとの類似性を確認、必要に応じて再生成
3. **画像生成**: DALL-E 3で最終プロンプトから画像を生成

### 3.3 プロンプト生成例

**入力見出し**: "月5万円を実現する収益構造の骨組み（考え方の例）"

**生成プロンプト**: "A serene home office setting in the late afternoon, featuring three distinct revenue stream visualization boards on easels, displaying charts and diagrams that represent multiple income sources flowing together, with warm natural lighting and a professional yet approachable atmosphere"

---

## 4. ファイル命名規則

```
articles/2/images/20251108163048-5.png
                  ^^^^^^^^^^^^^^ ^
                  日時スタンプ    |
                              連番またはキーワード
```

- **形式**: `YYYYMMDDHHMMSS-{identifier}.png`
- **自動埋め込み**: HTMLファイルの対応する見出し直後に `<img>` タグを挿入

---

## 5. HTML統合システム

### 5.1 見出し抽出

```python
def extract_headings(article_path: Path) -> List[str]:
    """HTMLまたはMarkdownから見出しを抽出"""
    content = article_path.read_text()
    if article_path.suffix == '.html':
        # HTML: h2, h3, h4タグから抽出
        soup = BeautifulSoup(content, 'html.parser')
        headings = [tag.get_text().strip() for tag in soup.find_all(['h2', 'h3', 'h4'])]
    else:
        # Markdown: ##, ###, ####から抽出  
        headings = [line.strip('#').strip() for line in content.split('\n') 
                   if line.startswith('##') and not line.startswith('#####')]
    return headings
```

### 5.2 画像自動挿入

生成された画像は対応する見出し直後に自動挿入：

```html
<h2>月5万円を実現する収益構造の骨組み（考え方の例）</h2>
<img src="images/20251108163048-5.png" alt="月5万円を実現する収益構造の骨組み（考え方の例）のイメージ" />
<p>重要なのは「複数の小さな収入源を組み合わせること」です...</p>
```

---

## 6. リアルタイム監視

ワークフロー監視UI（http://localhost:8080）で以下の情報をリアルタイム表示：

```
[00:29:33] IMAGES: 🎨 STEP 3: 画像生成を開始
[00:29:33] INFO: 🖼️ 記事ID 2 の画像を生成中
[00:29:33] INFO: 📝 6個の見出しに対して画像を生成します
[00:29:33] OpenAI API REQUEST: プロンプト生成: ## トレンドの実感：今なぜチャンスなのか...
[00:29:36] OpenAI API SUCCESS: プロンプト生成完了: **Prompt:** A dynamic urban landscape at dawn, sho...
[00:29:36] INFO: 🎨 画像 1/6: ## トレンドの実感：今なぜチャンスなのか...
[00:29:36] OpenAI API REQUEST: DALL-E 3で画像生成: ## トレンドの実感：今なぜチャンスなの...
[00:30:48] OpenAI API SUCCESS: 画像生成完了: 20251108162933-section.png
[00:37:57] IMAGES: ✅ STEP 3完了: 6個の画像を生成
```

---

## 7. プロンプト多様化システム

### 7.1 重複チェック機能

```python
def check_prompt_similarity(new_prompt: str, existing_prompts: List[str]) -> bool:
    """プロンプトの類似性をチェック（簡易版）"""
    for existing in existing_prompts:
        if calculate_similarity(new_prompt, existing) > 0.7:
            return True  # 類似度が高い
    return False
```

### 7.2 多様化戦略

- **シーン設定**: オフィス、カフェ、自然、都市など多様な背景
- **視点変更**: 俯瞰、クローズアップ、横からのアングル
- **時間帯**: 朝、昼、夜、夕方で雰囲気を変更
- **スタイル**: 写実的、イラスト調、インフォグラフィック

---

## 8. エラーハンドリング

### 8.1 一般的なエラー

| エラー | 原因 | 対処 |
| --- | --- | --- |
| `DALL-E 3 API error: invalid size` | 非対応サイズ指定 | `1536x1024`, `1024x1536`, `1024x1024`のみ使用 |
| `Japanese text may cause garbling` | 日本語プロンプト | 英語プロンプト自動生成で対応済み |
| `No headings found` | 見出しなしファイル | HTMLにh2-h4タグ、Markdownに##以降が必要 |
| `OpenAI API rate limit` | API制限到達 | 1分待機後リトライ、または後時間帯に実行 |

### 8.2 リトライ機能

```python
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        # 画像生成実行
        break
    except OpenAIError as e:
        if attempt < MAX_RETRIES - 1:
            print(f"[WARNING] Retry {attempt + 1}/{MAX_RETRIES}: {e}")
            time.sleep(30)  # 30秒待機
        else:
            print(f"[ERROR] Max retries reached: {e}")
            raise
```

---

## 9. 手動実行（レガシー対応）

```bash
# 単体画像生成（開発・デバッグ用）
python tools/generate_image.py "A serene office workspace at sunset" \
  --size 1536x1024 \
  --output-dir articles/2/images \
  --filename manual-test
```

> **注意**: 手動実行は開発用途のみ。本番環境では統合ワークフローを使用してください。

---

## 10. 運用ベストプラクティス

### 10.1 品質管理

- **プレビュー確認**: 生成後はHTMLファイルをブラウザで確認
- **Alt属性**: 見出しテキストから自動生成（SEO対応）
- **ファイルサイズ**: PNGで約500KB-2MB（品質とサイズのバランス）

### 10.2 コスト管理

- **DALL-E 3料金**: `1536x1024`で$0.080/枚
- **6枚生成**: 約$0.48/記事
- **月間予算**: 100記事で約$48

### 10.3 著作権・利用規約

- **商用利用**: OpenAI利用規約に従い商用利用可能
- **帰属表示**: 不要（OpenAI生成画像）
- **編集自由**: 生成後の編集・加工は自由

---

## 11. 今後の拡張予定

- **スタイル指定**: 記事ごとに画像スタイルを指定可能に
- **一括再生成**: 既存記事の画像を一括で再生成
- **カスタムプロンプト**: ユーザー定義のプロンプトテンプレート
- **画像圧縮**: WebP変換による高速化とサイズ削減

---

このガイドは統合ワークフローの画像生成システムを説明しており、手動操作を最小限に抑えた自動化環境を提供します。ワークフロー監視UIを使用することで、記事作成から画像生成、WordPress投稿まで完全自動化が可能です。