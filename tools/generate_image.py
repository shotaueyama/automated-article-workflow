#!/usr/bin/env python3
"""Simple CLI for generating images with OpenAI's ChatGPT image API."""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    from openai import OpenAI
    from openai import OpenAIError
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "The openai package is required. Install it via `pip install openai`."
    ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an image by calling ChatGPT's image (DALL·E) API."
    )
    parser.add_argument(
        "prompt",
        help="Text that describes the image you would like ChatGPT to create.",
    )
    parser.add_argument(
        "--model",
        default="dall-e-3",
        help="Image model to use. Defaults to %(default)s.",
    )
    parser.add_argument(
        "--size",
        default="1792x1024",
        help="Image size accepted by the API, e.g. 1024x1024, 1792x1024, or 1024x1792.",
    )
    parser.add_argument(
        "--quality",
        choices=("standard", "high"),
        default="standard",
        help="Image quality. `high` yields better results but costs more.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory where the PNG will be written. Defaults to auto-detected article images folder.",
    )
    parser.add_argument(
        "--filename",
        help="Optional custom filename (without directory). `.png` will be appended.",
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=3,
        help="Number of retry attempts for content policy violations. Defaults to %(default)s.",
    )
    return parser.parse_args()


def sanitize_prompt_for_safety(prompt: str, client: OpenAI) -> str:
    """プロンプトを安全性チェック用に修正"""
    safety_prompt = f"""以下の画像生成プロンプトをOpenAIのコンテンツポリシーに準拠するよう安全に修正してください。
    
元のプロンプト: {prompt}

修正要件:
- 暴力的、性的、不適切な表現を削除または置換
- 政治的、宗教的に中立な表現に変更
- ビジネス用途として適切な内容に調整
- 可愛い3Dアニメーションスタイルを保持（rounded features, cute characters, bright colors）
- 具体的で建設的な視覚的要素を保持

修正されたプロンプトのみを出力してください:"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは画像生成プロンプトの安全性を確保する専門家です。"},
                {"role": "user", "content": safety_prompt}
            ],
            max_completion_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Warning: Failed to sanitize prompt: {e}", file=sys.stderr)
        # フォールバック: 基本的な単語置換
        safe_prompt = prompt.replace("暴力", "力強い").replace("戦争", "競争").replace("血", "赤色")
        return safe_prompt


def generate_image_with_retry(client: OpenAI, prompt: str, args, max_attempts: int) -> tuple[bool, any]:
    """コンテンツポリシー違反時に自動リトライする画像生成"""
    current_prompt = prompt
    
    for attempt in range(max_attempts):
        try:
            print(f"[Attempt {attempt + 1}/{max_attempts}] Generating image with prompt: {current_prompt[:100]}...")
            
            response = client.images.generate(
                model=args.model,
                prompt=current_prompt,
                size=args.size,
                quality=args.quality,
                n=1,
                response_format="b64_json"
            )
            return True, response
            
        except OpenAIError as exc:
            error_message = str(exc)
            print(f"[Attempt {attempt + 1}] Failed: {error_message}", file=sys.stderr)
            
            # コンテンツポリシー違反の場合
            if "content_policy_violation" in error_message or "safety system" in error_message:
                if attempt < max_attempts - 1:
                    print(f"[Attempt {attempt + 1}] Content policy violation detected, modifying prompt...", file=sys.stderr)
                    current_prompt = sanitize_prompt_for_safety(current_prompt, client)
                    print(f"[Attempt {attempt + 1}] Modified prompt: {current_prompt[:100]}...", file=sys.stderr)
                    continue
                else:
                    print(f"[Final attempt failed] Content policy violation could not be resolved", file=sys.stderr)
                    return False, exc
            else:
                # その他のエラーの場合は即座に終了
                return False, exc
    
    return False, Exception("Max retry attempts exceeded")


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Set the OPENAI_API_KEY environment variable first.", file=sys.stderr)
        return 1

    client = OpenAI(api_key=api_key)
    
    # リトライ機能付きで画像生成
    success, result = generate_image_with_retry(client, args.prompt, args, args.retry_attempts)
    
    if not success:
        print(f"Image generation failed after {args.retry_attempts} attempts: {result}", file=sys.stderr)
        return 1
    
    response = result

    if not response.data:
        print("Image generation returned no results.", file=sys.stderr)
        return 1

    # b64_jsonが利用できない場合のフォールバック処理
    image_data = response.data[0]
    image_b64 = None
    image_bytes = None
    
    if hasattr(image_data, 'b64_json') and image_data.b64_json:
        image_b64 = image_data.b64_json
    elif hasattr(image_data, 'url'):
        # URLから画像をダウンロード
        import requests
        try:
            img_response = requests.get(image_data.url, timeout=30)
            img_response.raise_for_status()
            image_bytes = img_response.content
        except Exception as e:
            print(f"Failed to download image from URL: {e}", file=sys.stderr)
            return 1
    else:
        print("API response did not contain image data.", file=sys.stderr)
        return 1

    output_dir = determine_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.filename:
        filename = args.filename
    else:
        timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        sanitized = "".join(
            c for c in args.prompt.lower() if c.isalnum() or c in ("-", "_")
        )
        sanitized = sanitized[:32] or "image"
        filename = f"{timestamp}-{sanitized}"
    output_path = output_dir / f"{filename}.png"

    # 画像データを保存
    if image_b64:
        output_path.write_bytes(base64.b64decode(image_b64))
    else:
        output_path.write_bytes(image_bytes)
    
    print(f"Image saved to {output_path}")
    return 0


def determine_output_dir(cli_output: str | None) -> Path:
    if cli_output:
        return Path(cli_output).expanduser()

    cwd = Path.cwd().resolve()
    articles_dir = cwd
    while articles_dir != articles_dir.parent:
        if articles_dir.name.isdigit() and articles_dir.parent.name == "articles":
            return articles_dir / "images"
        articles_dir = articles_dir.parent

    # If not in an article directory, use current directory
    return Path.cwd() / "images"


if __name__ == "__main__":
    raise SystemExit(main())
