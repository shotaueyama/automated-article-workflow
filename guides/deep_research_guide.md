# AI記事リサーチツール：DeepResearch + フォールバック機能（AIエージェント対応）

`tools/deep_research_collect.py` は OpenAI の `o4-mini-deep-research` モデルを呼び出し、調査結果を `articles/<連番>/material.md` にまとめる CLI です。DeepResearch が利用できない場合は、自動的に `search_research_collect.py` にフォールバックして段階的リサーチを実行します。人間のオペレーターだけでなく、他の AI エージェントでも同じ手順で実行できます。

---

## 1. 事前準備

1. **仮想環境を有効化**
   ```bash
   source .venv/bin/activate
   ```
2. **APIキーを読み込む**（`.env.local` に既に保存済み）
   ```bash
   set -a; source .env.local; set +a
   ```
3. **依存関係**: `pip install -r requirements.txt` 済みを前提（`openai`, `beautifulsoup4` など）。

> AIエージェントはこの 3 行を順番に実行してからツールを呼び出せば OK です。

---

## 2. 実行コマンド

```bash
python tools/deep_research_collect.py "調べたいテーマや質問" --effort medium
```

**メインオプション**：
- `--model` … 既定は `o4-mini-deep-research`。別モデルが必要なら指定。
- `--effort` … 現状 `medium` のみ対応（`high` はエラーになる）。
- `--web-search` … 互換性のため残していますが、現行モデルでは無視されます。

**フォールバック用代替ツール**（DeepResearch利用不可時に自動実行）：
```bash
python tools/search_research_collect.py "調べたいテーマや質問" --search-model gpt-4o-search-preview --report-model gpt-5-mini
```

---

## 3. 処理フロー

### A. DeepResearch利用時（メインフロー）
1. OpenAI Responses API に DeepResearch リクエスト（`web_search_preview` ツール付き）を送信。
2. レスポンス本文から `output_text` / `summary_text` を抽出し、Markdown サマリを整形。
3. `articles/` を走査して次の連番フォルダ（例: `articles/3/`）を作成。
4. `material.md` に以下を保存:
   - クエリ内容、生成日時、使用モデル、推論レベル
   - サマリ本文（引用リンク付き）
   - 応答 JSON (`response.model_dump()`) のフルログ

### B. フォールバック時（段階的リサーチ）
1. DeepResearch API エラー発生時、自動的に `search_research_collect.py` を呼び出し。
2. GPT-5-mini が戦略的セクション計画を立案。
3. GPT-4o-search-preview が各セクションを順次リサーチ。
4. GPT-5-mini が統合レポートを生成（10セクション反復）。
5. 同様に `articles/<連番>/material.md` に保存（タイムスタンプ付きログ含む）。

---

## 4. 他AIエージェント向けTips

- **コマンド再利用**: テーマ文言だけ差し替えて繰り返し実行する。連番フォルダは自動で増えるため競合しにくい。
- **成果物の受け渡し**: 実行後は `articles/<最新番号>/material.md` を読み込んで次のタスク（HTML生成、WordPress投稿など）へ渡す。
- **長時間ジョブ**: DeepResearch は 5～10 分、フォールバック時は 15～20 分かかる場合があるため、待機／再試行ロジックを組み込むと安定。
- **プログレス監視**: フォールバック時は詳細なタイムスタンプ付きログが出力されるため、進捗状況を把握しやすい。
- **品質保証**: フォールバック機能により、DeepResearch が利用不可でも同等品質のリサーチが保証される。

---

## 5. トラブルシューティング

| 症状 | 対処 |
| --- | --- |
| `OPENAI_API_KEY is not set.` | `.env.local` を読み込んでいない。上記ステップ2を実行。 |
| `reasoning.effort` のエラー | `--effort medium` 以外を指定していないか確認。 |
| `tools` に関するエラー | 最新版の `tools/deep_research_collect.py` を使っているか確認（`web_search_preview` 付与済みか）。 |
| `material.md` にJSONだけが出る | モデルが文章を返さなかったケース。プロンプトを具体化して再実行。 |
| DeepResearch API エラー | 自動フォールバックが動作。「Falling back to search-based research...」メッセージを確認。 |
| フォールバック実行中にエラー | `search_research_collect.py` のログを確認。GPT-5-miniまたはGPT-4o-search-previewのAPI制限の可能性。 |
| 生成時間が長い | フォールバック時は正常（10セクション反復のため）。途中停止する場合はタイムアウト設定を確認。 |

---

## 6. ワークフロー統合

**完全な記事生成パイプライン**：
1. **リサーチ**: `deep_research_collect.py` でmaterial.md生成
2. **HTML生成**: `generate_html_from_material.py` でWordPress用記事作成
3. **画像生成**: `generate_image.py` でセクション画像を自動生成
4. **レイアウト改善**: `improve_html_layout.py` でHTML最適化
5. **WordPress投稿**: `upload_to_wordpress.py` で自動投稿

**応用例**：
- 連番ではなく任意フォルダに出力したい場合は `next_article_dir` のロジックを変更。
- 複数テーマをまとめて走らせるなら、シェルスクリプトやタスクランナーでコマンドをループ実行。
- サーバー環境では `workflow_server.py` でWeb APIとして実行可能。

## 7. モデル仕様と制限事項

**DeepResearch (o4-mini-deep-research)**：
- 深度のあるリサーチが可能、引用リンク付き
- API制限や利用制限により使えない場合がある

**フォールバック (GPT-5-mini + GPT-4o-search-preview)**：
- 戦略的段階リサーチで高品質を保証
- 実行時間は長いが安定性が高い
- 各セクション詳細ログで透明性確保

このガイドに従えば、人間・AIを問わず統一手順で高品質なAI記事生成が運用できます。必要に応じてガイドを更新し、組織内で共有してください。
