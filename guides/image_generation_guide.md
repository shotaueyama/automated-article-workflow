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
- **画像サイズ**: `1792x1024` (16:9アスペクト比)
- **品質**: `standard` (コストと品質のバランス)
- **プロンプト言語**: 英語必須（日本語は文字化けするため自動翻訳）

### 3.2 プロンプト生成システム

画像生成はコマンドラインツールで実行：

1. **見出し抽出**: `run_workflow.py` の `extract_headings()` でHTML/Markdownからh2タグを抽出
2. **コマンド実行**: `tools/generate_image.py` を各見出しごとに呼び出し
3. **画像生成**: DALL-E 3で直接日本語見出しから画像を生成
4. **ファイル保存**: `articles/<id>/images/` にタイムスタンプ付きで保存

### 3.3 プロンプト生成例

**入力見出し**: "月5万円を実現する収益構造の骨組み（考え方の例）"

**実行コマンド**: 
```bash
python tools/generate_image.py "## 月5万円を実現する収益構造の骨組み（考え方の例）" \
  --output-dir articles/2/images \
  --filename "20251108163048-5"
```

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

### 5.1 見出し抽出（実装版）

```python
def extract_headings(article_path: Path) -> List[str]:
    """HTMLまたはMarkdownから見出しを抽出"""
    headings: List[str] = []
    content = article_path.read_text(encoding="utf-8")
    
    # HTMLファイルの場合はHTMLタグから見出しを抽出
    if article_path.suffix == ".html":
        import re
        h2_matches = re.findall(r'<h2>(.*?)</h2>', content)
        for heading in h2_matches:
            headings.append(f"## {heading}")
    else:
        # Markdownファイルの場合は従来の方法
        for line in content.splitlines():
            line = line.rstrip()
            if line.startswith("## "):
                headings.append(line.strip())
    return headings
```

### 5.2 画像自動挿入（手動適用）

現在の実装では、画像生成後に手動でHTMLに挿入する必要があります：

```html
<h2>月5万円を実現する収益構造の骨組み（考え方の例）</h2>
<img src="images/20251108163048-5.png" alt="月5万円を実現する収益構造の骨組み（考え方の例）のイメージ" />
<p>重要なのは「複数の小さな収入源を組み合わせること」です...</p>
```

> **注意**: 自動挿入機能は未実装。現在は手動で`<img>`タグを追加する必要があります。

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

## 7. 画像生成コマンドラインオプション

### 7.1 基本オプション

```bash
python tools/generate_image.py "見出しテキスト" \
  --model dall-e-3 \
  --size 1792x1024 \
  --quality standard \
  --output-dir articles/2/images \
  --filename "ファイル名"
```

### 7.2 サイズオプション

- **1792x1024**: 横長（16:9アスペクト比）
- **1024x1792**: 縦長（9:16アスペクト比）
- **1024x1024**: 正方形（1:1アスペクト比）

### 7.3 品質設定

- **standard**: 標準品質（コスト効率重視）
- **high**: 高品質（高額だが高精細）

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
python tools/generate_image.py "見出しテキスト" \
  --size 1792x1024 \
  --output-dir articles/2/images \
  --filename manual-test
```

> **注意**: 手動実行でも実用的に使用可能。統合ワークフローでは `step_generate_images()` がこのツールを内部的に呼び出します。

---

## 10. 運用ベストプラクティス

### 10.1 品質管理

- **プレビュー確認**: 生成後はHTMLファイルをブラウザで確認
- **Alt属性**: 見出しテキストから自動生成（SEO対応）
- **ファイルサイズ**: PNGで約500KB-2MB（品質とサイズのバランス）

### 10.2 コスト管理

- **DALL-E 3料金**: `1792x1024`で$0.080/枚（standard品質）
- **6枚生成**: 約$0.48/記事
- **月間予算**: 100記事で約$48

### 10.3 著作権・利用規約

- **商用利用**: OpenAI利用規約に従い商用利用可能
- **帰属表示**: 不要（OpenAI生成画像）
- **編集自由**: 生成後の編集・加工は自由

---

## 11. 現在の制限と今後の改善点

### 現在の制限
- **手動挿入**: 生成後の画像をHTMLに手動で挿入する必要がある
- **h2のみ対応**: h3, h4などのサブ見出しは現在非対応
- **プロンプト多様化**: 重複チェックなどの高度な機能は未実装

### 今後の改善予定
- **自動挿入**: HTMLに画像を自動挿入する機能
- **サブ見出し対応**: h3, h4タグからも画像生成
- **プロンプト高度化**: コンテキストを考慮した多様なプロンプト生成
- **画像圧縮**: WebP変換による高速化とサイズ削減

---

このガイドは統合ワークフローの画像生成システムを説明しており、手動操作を最小限に抑えた自動化環境を提供します。ワークフロー監視UIを使用することで、記事作成から画像生成、WordPress投稿まで完全自動化が可能です。