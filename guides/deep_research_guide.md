# DeepResearch 情報収集ツール（AIエージェント対応）

`tools/deep_research_collect.py` は OpenAI の `o3-deep-research` モデルを呼び出し、調査結果を `articles/<連番>/material.md` にまとめる CLI です。人間のオペレーターだけでなく、他の AI エージェントでも同じ手順で実行できます。

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

- `--model` … 既定は `o3-deep-research`。別モデルが必要なら指定。
- `--effort` … 現状 `medium` のみ対応（`high` はエラーになる）。
- `--web-search` … 互換性のため残していますが、現行モデルでは無視されます。

---

## 3. 処理フロー

1. OpenAI Responses API に DeepResearch リクエスト（`web_search_preview` ツール付き）を送信。
2. レスポンス本文から `output_text` / `summary_text` を抽出し、Markdown サマリを整形。
3. `articles/` を走査して次の連番フォルダ（例: `articles/3/`）を作成。
4. `material.md` に以下を保存:
   - クエリ内容、生成日時、使用モデル、推論レベル
   - サマリ本文（引用リンク付き）
   - 応答 JSON (`response.model_dump()`) のフルログ

---

## 4. 他AIエージェント向けTips

- **コマンド再利用**: テーマ文言だけ差し替えて繰り返し実行する。連番フォルダは自動で増えるため競合しにくい。
- **成果物の受け渡し**: 実行後は `articles/<最新番号>/material.md` を読み込んで次のタスク（構成案作成、WordPress投稿など）へ渡す。
- **長時間ジョブ**: DeepResearch は 5～10 分かかる場合があるため、待機／再試行ロジックを組み込むと安定。

---

## 5. トラブルシューティング

| 症状 | 対処 |
| --- | --- |
| `OPENAI_API_KEY is not set.` | `.env.local` を読み込んでいない。上記ステップ2を実行。 |
| `reasoning.effort` のエラー | `--effort medium` 以外を指定していないか確認。 |
| `tools` に関するエラー | 最新版の `tools/deep_research_collect.py` を使っているか確認（`web_search_preview` 付与済みか）。 |
| `material.md` にJSONだけが出る | モデルが文章を返さなかったケース。プロンプトを具体化して再実行。 |

---

## 6. 応用

- 連番ではなく任意フォルダに出力したい場合は `next_article_dir` のロジックを変更。
- 生成後、自動で要約や構成案に落とし込みたい場合は、`material.md` を読み取る別スクリプト（例: `tools/summarize_material.py`）を用意。
- 複数テーマをまとめて走らせるなら、シェルスクリプトやタスクランナーでコマンドをループ実行。

このガイドに従えば、人間・AIを問わず DeepResearch 呼び出しを統一手順で運用できます。必要に応じてガイドを更新し、組織内で共有してください。
