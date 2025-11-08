# ChatGPT画像生成ガイド（AIエージェント向け詳細版）

OpenAI の ChatGPT 画像 API（`gpt-image-1`）をローカルから呼び出すための運用手順です。人間のオペレーターだけでなく、他の AI エージェントが自動タスクとして呼び出しても破綻しないよう、前提とコマンド体系を明示しています。

---

## 1. リポジトリ構造と責務

| パス | 役割 |
| --- | --- |
| `tools/generate_image.py` | 画像生成のCLI本体。OpenAI SDKを直接呼び出し、PNGを出力。 |
| `generated-images/` | 既定の出力先（記事フォルダ外で実行した場合に使用）。 |
| `articles/<n>/images/` | 記事ごとの画像フォルダ。`articles/<n>/` 直下でコマンドを実行すると自動的にこちらへ保存される。 |
| `.env.local` | `OPENAI_API_KEY` などの機密情報を格納。Git管理対象外。 |
| `guides/image_generation_guide.md` | 本ドキュメント。AIエージェントへのハンドブックとして利用。 |

> **メモ**: 追加の自動処理（例：画像リサイズやメタデータ書き込み）を行う場合は `tools/` 配下にスクリプトを増やし、ここに追記してください。

---

## 2. 初期セットアップ

### 2.1 ヒト/エージェント共通コマンド

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2.2 APIキー管理

1. `.env.local` に以下の形式で保存  
   `OPENAI_API_KEY=sk-proj-xxxx`
2. 新しいシェルやエージェントプロセスで必ず読み込む  
   ```bash
   set -a
   source .env.local
   set +a
   ```
3. 複数キーを切り替える場合は `.env.local` を都度編集するか、`OPENAI_API_KEY=... python ...` のように一時指定してください。

---

## 3. 画像生成コマンドの使い方

### 3.1 基本

```bash
python tools/generate_image.py "夕焼けの海辺でノートPCを開くソロ起業家のイラスト"
```

成功するとターミナルに `Image saved to ...` が表示されます（記事フォルダ内なら `articles/<n>/images/`、それ以外なら `generated-images/` になります）。

### 3.2 オプション一覧

| オプション | 用途 | 備考 |
| --- | --- | --- |
| `--model` | 使用モデル。デフォルト `gpt-image-1` | ほかの画像モデルが開放された場合に切り替え。 |
| `--size` | 解像度指定 | OpenAIのサポート値は `1024x1024 / 1024x1536 / 1536x1024 / auto`。16:9が必要な場合は`sips`等で後処理。 |
| `--quality` | `standard` or `high` | `high` は高品質・高コスト。 |
| `--output-dir` | 出力フォルダ | `articles/<n>/` 内で実行した場合は自動で `articles/<n>/images/` を使用。その他は `generated-images/`。 |
| `--filename` | ファイル名（拡張子なし） | チームで命名規則を決めると追跡が楽。 |

### 3.3 後処理例（16:9クロップ）

```bash
sips -c 864 1536 generated-images/sample.png \
  --out generated-images/sample-16x9.png
```

AIエージェントから呼ぶ場合は、生成後に `sips` や `convert` を続けて実行するタスクを定義してください。

---

## 4. プロンプト設計ガイド

- **文脈→スタイル→構図→光源** の順で書くと安定。  
  例: `リアルな写真風：一人起業家とメカニカルなロボットAIが机を挟んで議論する16:9シーン。暖色のオフィスライト。`
- 日本語/英語どちらも可。生成結果を共有したいエージェント向けに、プロンプトと出力パスをログへ残すことを推奨。
- 「ロボットは無表情」「chibiスタイル」など人間以外の表現は具体的な形容を入れる。

---

## 5. Cursor からの呼び出し

1. Cursor → Settings → Features → Custom Commands → Add Command  
2. Name: `ChatGPTで画像生成（ローカル）` など自由  
3. Command:  
   ```
   python tools/generate_image.py "{{text}}" --output-dir generated-images
   ```
   （記事フォルダ内で呼び出す場合は `--output-dir` を省略すれば自動的に `images/` 配下に保存）
4. Input Source: `Selected Text`（または `Command Palette Input`）  
5. 実行結果は Cursor のターミナルペインに表示。必要なら post-processing コマンドを追加で実行できます。

> **エージェント実装メモ**: Cursor の Custom Command を呼び出す AI からは、プロンプト文字列を選択範囲に書き出してからコマンド発火、完了後に `generated-images/` もしくは `articles/<n>/images/` を参照して Markdown に差し込む、という手順が再現可能です。

---

## 6. 自動化／他AIエージェント向けTips

| タスク | 推奨フロー |
| --- | --- |
| バッチ生成 | プロンプトリストを持つテキストをループし、`python tools/generate_image.py "$(cat prompt.txt)" --filename ...` を順番に実行。 |
| 失敗時のリトライ | スクリプトは終了コード `1` で失敗を返すので、AIエージェントは `if [ $? -ne 0 ]; then ...` で再実行/通知を実装。 |
| ログ出力 | `tee -a logs/image_generation.log` を併用するとプロンプトと結果パスを永続化できる。 |
| 別ユーザー環境 | `.venv` と `.env.local` をコピーし、`pip install -r requirements.txt` を再実行するだけで再現可能。 |

---

## 7. トラブルシューティング

- **403: organization must be verified**  
  OpenAI ダッシュボードで組織の Verify が必要。完了後 15 分ほど待機。自動エージェントはエラー文をそのままユーザーへ報告する。
- **Invalid size**  
  OpenAI が許可していない解像度を指定している。`--size` はサポート値のみ使用し、16:9は後処理で対応。
- **APIキー未設定**  
  エラー文 `Set the OPENAI_API_KEY environment variable first.` が出たら `.env.local` を読み込んでいない。自動スクリプトの冒頭に `set -a; source .env.local; set +a` を必ず入れる。
- **依存関係エラー**  
  `.venv` を削除→再作成し、`pip install -r requirements.txt` を再実行。ネットワーク制限がある場合はプロキシ設定を確認。

---

## 8. 運用上のベストプラクティス

- 生成後は記事やメモに **相対パス** (`../../generated-images/...`) で貼り、ファイル名は英小文字＋意味のある単語で統一。
- 大量生成する場合はコスト監視のため、`tqdm` のような進捗ログを活用するか、1タスクごとに OpenAI の Usage API を照会する。
- 画像を差し替えた場合は、旧ファイルも保持して比較できるよう `generated-images/` に残しておく（不要ならアーカイブしても構いませんが Git には含めないこと）。

---

これで人間とAIエージェントの双方が `generate_image.py` を安全かつ再現性高く利用できます。新しいワークフローを追加した際は本ガイドを更新し、ナレッジを共有してください。
