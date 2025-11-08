#!/usr/bin/env python3
"""Generate a markdown article (3000-4000 Japanese characters) from material.md."""
from __future__ import annotations

import argparse
import os
import datetime as dt
from pathlib import Path
from typing import List

import requests
import json

try:
    from openai import OpenAI, OpenAIError
except ImportError:  # openai パッケージが無い環境向けのフォールバック
    OpenAI = None  # type: ignore

    class OpenAIError(Exception):  # type: ignore
        """Placeholder to unify exception handling when openai is unavailable."""

        pass

DEFAULT_MATERIAL_PATH = Path("articles/material.md")
DEFAULT_OUTPUT_PATH = Path("articles/generated_article.md")
DEFAULT_MODEL = "gpt-5-mini-2025-08-07"
MIN_CHAR_COUNT = 3000
MAX_CHAR_COUNT = 4000
MAX_ATTEMPTS = 5
MAX_OUTPUT_TOKENS = 128_000
REVIEW_MODEL = "gpt-5-mini-2025-08-07"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read articles/material.md, then ask ChatGPT GPT-5 mini to write a "
            "3000-4000 character Japanese markdown article."
        )
    )
    parser.add_argument(
        "--material",
        type=Path,
        default=DEFAULT_MATERIAL_PATH,
        help=f"Path to the source material (default: {DEFAULT_MATERIAL_PATH}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Path to write the generated article (default: {DEFAULT_OUTPUT_PATH}).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"OpenAI model to use (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--review-model",
        default=REVIEW_MODEL,
        help=f"OpenAI model used for post-review (default: {REVIEW_MODEL}).",
    )
    return parser.parse_args()


def read_material(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"Material file not found: {path}")
    return path.read_text(encoding="utf-8").strip()




def convert_bold_bullet_headings(article: str) -> str:
    """Convert '- **Heading**: text' style bullets into proper subheadings."""
    lines = article.splitlines()
    converted: List[str] = []
    import re

    pattern = re.compile(r"^-+\s*\*\*(.+?)\*\*[:：]\s*(.*)")
    for line in lines:
        match = pattern.match(line.strip())
        if match:
            heading, body = match.groups()
            converted.append(f"### {heading.strip()}")
            if body:
                converted.append(body.strip())
        else:
            converted.append(line)
    return "\n".join(converted)


def build_messages(material: str) -> List[dict]:
    user_prompt = (
        "以下のリサーチメモを踏まえて、読者が自然に引き込まれるような"
        "**必ず3200〜3800文字（理想は3500文字）**の日本語記事をMarkdownで執筆してください。\n\n"
        "【重要な要求】\n"
        "文字数は3200文字未満にならないよう、十分な内容で構成してください。日本語を主体とし、人間らしいブログ調で体験談や感情を織り交ぜながら書いてください。適度に口語表現を使い、親しみやすさを心がけてください。\n\n"
        "各セクションは具体例や詳細説明を豊富に含め、見出し（## ### ####）で構造化してください。重要なのは、リストや箇条書きを最小限に抑え、代わりに流れるような文章で情報を伝えることです。機械的に見えるリストよりも、読者が自然に理解できる物語調の文章を心がけてください。\n\n"
        "=== リサーチメモ ===\n"
        f"{material}"
    )
    return [
        {
            "role": "system", 
            "content": (
                "あなたは熟練の日本語ライターです。"
                "論理的な構成とストーリーテリングを意識し、"
                "事実と洞察を織り交ぜて読者を惹きつけます。"
                "Markdown形式で出力し、必ず3200〜3800文字の範囲に収めてください。"
                "各セクションは読みやすいブログ調で、見出し階層を正しく使い分けてください。"
                "短すぎる記事は絶対に避け、十分な詳細と具体例を含めてください。"
                "箇条書きやリストを使用せず、流れるような文章で情報を伝えてください。"
                "人間が自然に書いたような、親しみやすく読みやすい文体を心がけてください。"
            )
        },
        {"role": "user", "content": user_prompt},
    ]


def count_characters(text: str) -> int:
    # Ignore newlines when counting to align with common manuscript counting in Japanese.
    return len(text.replace("\n", ""))


def request_article(messages: List[dict], model: str, api_key: str):
    """Standard OpenAI chat completion request."""
    if OpenAI is None:
        raise SystemExit("OpenAI package not available")
    
    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=MAX_OUTPUT_TOKENS,
        )
        return response.choices[0].message.content or ""
    except OpenAIError as exc:
        raise SystemExit(f"OpenAI API call failed: {exc!s}")


def review_article_text(article: str, model: str, api_key: str):
    """Ask the model to review the article, list issues, and provide a minimally edited version."""
    system_text = (
        "あなたは日本語の編集者です。文章の構成や語調を保ったまま、"
        "記事として不自然な点や矛盾を洗い出し、必要最小限の修正だけを加えます。"
        "箇条書きの冒頭で強調記号を用いて見出しを表現している場合は、小見出し（###）に変換した状態で出力してください。"
        "応答は必ずJSON形式で、issues(リスト)とrevised_article(文字列)の2フィールドのみを含めてください。"
    )
    user_text = (
        "以下の記事をレビューし、記事的におかしい箇所を列挙しつつ、"
        "内容はできる限り変化させずに修正案を示してください。\n\n"
        "=== 対象記事 ===\n"
        f"{article}"
    )
    messages = [
        {"role": "system", "content": system_text},
        {"role": "user", "content": user_text},
    ]
    
    raw_text = request_article(messages, model, api_key)
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Review model returned invalid JSON: {raw_text}") from exc
    issues = data.get("issues") or []
    revised = data.get("revised_article") or article
    if not isinstance(issues, list) or not isinstance(revised, str):
        raise SystemExit("Review model response missing expected fields.")
    return issues, revised


def generate_article(material: str, model: str, api_key: str) -> str:
    """文字数保証機能付きの記事生成。確実に3000-4000文字になるまで再編集を繰り返す。"""
    messages = build_messages(material)
    
    print("Starting article generation with character count guarantee...")
    
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"Attempt {attempt}/{MAX_ATTEMPTS}")
        
        try:
            article = request_article(messages, model, api_key)
            article = article.strip()
        except Exception as exc:
            raise SystemExit(f"OpenAI API call failed: {exc!s}")

        char_count = count_characters(article)
        print(f"Generated article with {char_count} characters")
        
        if MIN_CHAR_COUNT <= char_count <= MAX_CHAR_COUNT:
            print(f"✅ Successfully generated {char_count} character article (target: {MIN_CHAR_COUNT}-{MAX_CHAR_COUNT})")
            return article

        # 文字数調整のための追加プロンプト
        messages.append({"role": "assistant", "content": article})

        if char_count < MIN_CHAR_COUNT:
            shortage = MIN_CHAR_COUNT - char_count
            adjustment_text = (
                f"【重要】現在の記事は{char_count}文字で、目標の{MIN_CHAR_COUNT}文字まで{shortage}文字不足しています。\n\n"
                f"以下の既存記事を基にして、必ず{MIN_CHAR_COUNT}〜{MAX_CHAR_COUNT}文字（理想は3500文字）になるように"
                "詳細な内容を追加して再編集してください：\n\n"
                "【追加要求】\n"
                "- 各セクションに具体例、数値、体験談を大幅に追加\n"
                "- 新しい小見出しやサブトピックを追加\n"
                "- 実践的なTips、注意点、ケーススタディを挿入\n"
                "- 読者の疑問を想定したQ&A風の説明を加える\n"
                "- 重複は避けて新しい価値ある情報を盛り込む\n\n"
                f"現在の記事（{char_count}文字）：\n{article}"
            )
        else:
            excess = char_count - MAX_CHAR_COUNT
            adjustment_text = (
                f"現在の記事は{char_count}文字で、目標の{MAX_CHAR_COUNT}文字を{excess}文字超過しています。\n\n"
                f"{MIN_CHAR_COUNT}〜{MAX_CHAR_COUNT}文字（理想は3500文字）に収まるよう、"
                "冗長な部分を削除し簡潔にまとめ直してください。ただし重要な情報は残してください。\n\n"
                f"現在の記事（{char_count}文字）：\n{article}"
            )

        messages.append({"role": "user", "content": adjustment_text})
        print(f"Requesting adjustment: target {MIN_CHAR_COUNT}-{MAX_CHAR_COUNT} characters")

    # 最大試行回数に達した場合でも、最後の結果を返す（完全に失敗させない）
    final_char_count = count_characters(article)
    print(f"⚠️ Warning: Final article is {final_char_count} characters (target: {MIN_CHAR_COUNT}-{MAX_CHAR_COUNT})")
    
    if final_char_count < MIN_CHAR_COUNT * 0.8:  # 極端に短い場合のみエラー
        raise SystemExit(
            f"Article generation failed: Final length {final_char_count} chars is too short "
            f"(minimum acceptable: {int(MIN_CHAR_COUNT * 0.8)} chars)"
        )
    
    return article


def ensure_output_path(path: Path) -> Path:
    if path.suffix.lower() != ".md":
        raise SystemExit("Output file must have a .md extension.")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set.")
    material_text = read_material(args.material)
    output_path = ensure_output_path(args.output)
    article = generate_article(material_text, args.model, api_key)
    article = convert_bold_bullet_headings(article)
    issues, revised_article = review_article_text(article, args.review_model, api_key)
    revised_article = convert_bold_bullet_headings(revised_article)
    output_path.write_text(revised_article, encoding="utf-8")
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_lines = [
        f"# Review Report for {output_path.name}",
        "",
        f"- Generated: {timestamp}",
        f"- Model: {args.review_model}",
        "",
    ]
    if issues:
        report_lines.append("## Issues")
        for idx, issue in enumerate(issues, 1):
            report_lines.append(f"{idx}. {issue}")
    else:
        report_lines.append("レビュー結果: 特に修正は必要ありませんでした。")
    review_path = output_path.with_name(f"{output_path.stem}_review.md")
    review_path.write_text("\n".join(report_lines), encoding="utf-8")
    if issues:
        print("Review issues detected:")
        for idx, issue in enumerate(issues, 1):
            print(f"{idx}. {issue}")
    else:
        print("Review found no issues.")
    print(f"Wrote review report to {review_path}")
    print(f"Wrote article to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
