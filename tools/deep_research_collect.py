#!/usr/bin/env python3
"""Run OpenAI DeepResearch via API and store the findings in a new article folder."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import List

from openai import OpenAI
from openai import OpenAIError

ARTICLES_ROOT = Path("articles")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call OpenAI DeepResearch, then save output to articles/<n>/material.md."
    )
    parser.add_argument("query", help="Research topic or question to investigate.")
    parser.add_argument(
        "--model",
        default="o3-deep-research",
        help="OpenAI model to use (default: %(default)s).",
    )
    parser.add_argument(
        "--effort",
        default="medium",
        choices=("low", "medium", "high"),
        help="Reasoning effort level passed to the API.",
    )
    parser.add_argument(
        "--web-search",
        action="store_true",
        help="Deprecated flag (kept for compatibility; no effect if model does not support it).",
    )
    return parser.parse_args()


def next_article_dir(root: Path) -> Path:
    existing: List[int] = []
    if root.exists():
        for child in root.iterdir():
            if child.is_dir() and child.name.isdigit():
                existing.append(int(child.name))
    next_id = (max(existing) + 1) if existing else 1
    target = root / str(next_id)
    target.mkdir(parents=True, exist_ok=False)
    return target


def extract_text(response) -> str:
    """Concatenate human-readable text segments from the response output."""
    texts: List[str] = []
    for item in getattr(response, "output", []) or []:
        item_dict = item if isinstance(item, dict) else item.model_dump()
        if item_dict.get("type") != "message":
            continue
        for content in item_dict.get("content", []):
            content_type = content.get("type")
            if content_type in {"output_text", "summary_text"}:
                texts.append(content.get("text", ""))
    if not texts:
        texts.append(str(response))
    return "\n\n".join(texts)


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "input_text",
                    "text": "You are DeepResearch, a meticulous AI researcher. Cite sources where possible.",
                }
            ],
        },
        {"role": "user", "content": [{"type": "input_text", "text": args.query}]},
    ]
    request_kwargs = {
        "model": args.model,
        "reasoning": {"effort": args.effort},
        "tools": [{"type": "web_search_preview"}],
        "input": messages,
    }
    if args.web_search:
        print("Note: --web-search flag is currently ignored (model handles retrieval automatically).")

    try:
        response = client.responses.create(**request_kwargs)
    except OpenAIError as exc:
        raise SystemExit(f"DeepResearch API call failed: {exc!s}")

    text_output = extract_text(response)
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target_dir = next_article_dir(ARTICLES_ROOT)
    material_path = target_dir / "material.md"

    material = [
        f"# Research Notes – {args.query}",
        "",
        f"- Generated: {timestamp}",
        f"- Model: {args.model}",
        f"- Effort: {args.effort}",
        f"- Web search: {'enabled' if args.web_search else 'disabled'}",
        "",
        "## Summary",
        text_output.strip(),
        "",
        "## Raw Response",
        "```json",
        json.dumps(response.model_dump(), ensure_ascii=False, indent=2),
        "```",
    ]
    material_path.write_text("\n".join(material), encoding="utf-8")
    print(f"Wrote research output to {material_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
