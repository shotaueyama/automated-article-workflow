# 自動記事執筆ワークフロー

## フロー概要

1. **情報収集** – `tools/deep_research_collect.py`
   ```bash
   source .venv/bin/activate
   set -a; source .env.local; set +a
   python tools/deep_research_collect.py "調べたいテーマ" --effort medium
   ```
   - 出力: `articles/<連番>/material.md`

2. **記事執筆** – `tools/generate_article_from_material.py`
   ```bash
   python tools/generate_article_from_material.py --article-id <連番> --material articles/<連番>/material.md --output articles/<連番>/article.md
   ```
   - 出力: `articles/<連番>/article.md`

3. **章ごとの画像生成** – `tools/generate_image.py`
   - 各章タイトルをプロンプトにして画像生成:
     ```bash
     python tools/generate_image.py "第1章タイトルの要約" --output-dir generated-images
     ```
   - 生成したファイルを `articles/<連番>/article.md` の該当見出し直下に Markdown で貼り付け:
     ```markdown
     ![第1章のイメージ](../../generated-images/20251108-xxxx-chapter1.png)
     ```

4. **WordPress へアップロード** – `tools/upload_to_wordpress.py`
   ```bash
   python tools/upload_to_wordpress.py \
     --markdown articles/<連番>/article.md \
     --status draft \
     --category-name ブログ \
     --parent-category "QUON COLLEGE"
   ```
   - 画像アップロード・Gutenbergブロック化・カテゴリ設定を自動実行。

## 補足

- 連番フォルダ (`articles/1`, `articles/2` …) は `deep_research_collect.py` が自動で作成。
- 画像ファイルは英小文字＋意味のあるファイル名にしておくと `article.md` への挿入が容易。
- WordPress 投稿はデフォルトでドラフト。公開したい場合は `--status publish` に変更。

この手順を順番に実行することで、情報収集から WordPress への投稿までを一気通貫で自動化できます。
