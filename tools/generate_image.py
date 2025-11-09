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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Set the OPENAI_API_KEY environment variable first.", file=sys.stderr)
        return 1

    client = OpenAI(api_key=api_key)
    try:
        response = client.images.generate(
            model=args.model,
            prompt=args.prompt,
            size=args.size,
            quality=args.quality,
            n=1,
            response_format="b64_json"  # 明示的にbase64形式を要求
        )
    except OpenAIError as exc:
        print(f"Image generation failed: {exc}", file=sys.stderr)
        return 1

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
