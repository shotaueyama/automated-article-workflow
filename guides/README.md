# Local ChatGPT Image Generation

This repository now includes a lightweight CLI that calls OpenAI's ChatGPT image API (DALL·E via `gpt-image-1`). You can run it directly from Cursor or any local terminal to create PNGs without visiting the browser.

## 1. Prerequisites

- Python 3.9+.
- An OpenAI API key with image-generation access.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Export your key before using the script:

```bash
export OPENAI_API_KEY="sk-..."
# optional: export OPENAI_BASE_URL="https://api.openai.com/v1"
```

## 2. Generate an image from the terminal

```bash
python tools/generate_image.py "a sumi-e style owl reading a book"
# >> Image saved to generated-images/20240201-123456-a-sumi-e-style-owl.png
```

Flags:

- `--model gpt-image-1` (default) – swap for other compatible models when available.
- `--size 1024x1024` – use OpenAI-supported sizes such as `1792x1024`.
- `--quality high` – switch to `standard` to reduce cost.
- `--output-dir generated-images` – override to control where files land.
- `--filename my_concept` – set an exact filename (without extension).

If the API key is missing or OpenAI returns an error, the CLI prints a descriptive message and exits with code `1`.

## 3. Hook it into Cursor

1. Open **Cursor → Settings → Features → Custom Commands → Add Command**.
2. Set any name you like (e.g., `Generate Image with ChatGPT`).
3. Command: `python tools/generate_image.py "{{text}}" --output-dir generated-images`.
4. Input source: `Selected Text` so highlighted text becomes the prompt (or `Command Palette Input` for manual entry).
5. Save. Now highlight text in the editor, press `Cmd+Shift+P`, run your command, and Cursor executes the script locally. The PNG file path is echoed back in the terminal pane.

You can add variations (different sizes/models) by creating extra commands that call the script with alternative flags.

---

## 使い方（日本語）

1. **Python仮想環境と依存関係の準備**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **OpenAI APIキーの設定**

   ```bash
   export OPENAI_API_KEY="sk-..."  # OpenAIの管理画面から取得したキーを設定
   # (必要なら) export OPENAI_BASE_URL="https://api.openai.com/v1"
   ```

3. **画像を生成**

   ```bash
   python tools/generate_image.py "墨絵風のフクロウが本を読むイラスト"
   ```

   実行すると `generated-images/` 以下にPNGファイルが保存され、パスが表示されます。  
   主なオプション:

   - `--model gpt-image-1` : 使用モデル（今後別モデルが追加されたら切り替え可）
   - `--size 1792x1024` : 出力解像度
   - `--quality standard` : 品質（`high`の方が高品質・高コスト）
   - `--output-dir my-images` : 保存先フォルダ
   - `--filename hero_visual` : ファイル名を指定

4. **Cursorで直接呼び出す場合**

   1. Cursorの設定 → Features → Custom Commands → Add Command を開く
   2. コマンド名を入力（例: `ChatGPTで画像生成`）
   3. Command欄に `python tools/generate_image.py "{{text}}" --output-dir generated-images`
   4. Input sourceは `Selected Text` を選ぶと、選択した文章がプロンプトになる
   5. 保存後、エディタでテキストを選択 → `Cmd+Shift+P` → 作成したコマンドを実行すると、ローカルで画像が生成される
