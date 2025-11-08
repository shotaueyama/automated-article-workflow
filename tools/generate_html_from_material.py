#!/usr/bin/env python3
"""Generate a WordPress-optimized HTML article (3000-4000 Japanese characters) from material.md."""
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
DEFAULT_OUTPUT_PATH = Path("articles/generated_article.html")
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
            "3000-4000 character Japanese HTML article optimized for WordPress."
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
        help=f"Output HTML file (default: {DEFAULT_OUTPUT_PATH}).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"ChatGPT model name (default: {DEFAULT_MODEL}).",
    )
    return parser.parse_args()


def count_japanese_chars(text: str) -> int:
    """日本語文字数をカウント（ひらがな・カタカナ・漢字・数字・英字・記号等）"""
    # HTML タグを除去してから文字数カウント
    import re
    clean_text = re.sub(r'<[^>]+>', '', text)
    return len(clean_text.replace(" ", "").replace("\n", ""))


def generate_article_with_openai(material: str, model: str) -> str:
    """OpenAI API を使って記事を生成"""
    
    if OpenAI is None:
        raise SystemExit("OpenAI library is not available.")
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY environment variable not set.")
    
    client = OpenAI(api_key=api_key)
    
    system_prompt = """あなたは、WordPressブロックエディタ向けの日本語記事を直接HTML形式で生成する専門ライターです。

以下の制約に従って、WordPressブロックエディタで完璧に表示される高品質なHTML記事を生成してください：

【WordPressブロック対応HTML構造】
- p、h2、h3、h4、img、strong、em、ul、ol、liタグのみ使用
- section、article、header、main、figure、div、blockquoteタグは一切使用禁止
- 極めてシンプルでフラットなHTML構造

【記事品質要件】
- 必ず3200〜3800文字（理想は3500文字）の日本語記事
- 人間らしいブログ調で体験談や感情を織り交ぜた自然な文章
- 適度に口語表現を使い、親しみやすさを心がける
- 機械的なリストや箇条書きを最小限に抑制
- 流れるような文章で情報を伝える物語調のスタイル

【HTML構造ルール】
- 記事は必ずh1タグで始まる（記事タイトル用、WordPressアップロード時に抽出される）
- 見出し階層：h1（記事タイトル）→ h2（主要セクション）→ h3（サブセクション）→ h4
- 段落は150-200文字目安で適切に分割
- 画像タグ使用禁止（画像は後で自動生成・挿入されるため、imgタグは含めない）
- 強調は<strong>、軽い強調は<em>を使用
- リストが必要な場合のみ<ul><li>を使用
- blockquoteタグは使用禁止（WordPressブロックエディタ互換性のため）

【重要な注意事項】
- HTMLのみを出力（説明や前置きは不要）
- 文字数は3200文字未満にならないよう十分な内容で構成
- 各セクションは具体例や詳細説明を豊富に含む
- 読者が自然に理解できる構成"""

    user_prompt = f"""以下のリサーチメモを踏まえて、WordPressブロックエディタ向けの日本語HTML記事を生成してください。

【重要な要求】
- **必ずh1タグでタイトルから開始する**（WordPressアップロード時に抽出されます）
- **必ず3200〜3800文字（理想は3500文字）**の日本語HTML記事
- **blockquoteタグは使用禁止**（WordPress互換性問題のため）
- **imgタグのsrcにはプレースホルダーURL禁止**（example.com等は使用不可）
- WordPressブロックエディタで完璧に表示されるシンプルな構造
- 人間らしい自然な文章（機械的なリストは最小限）
- 体験談や感情を織り交ぜた読みやすい記事

=== リサーチメモ ===
{material}

必ずh1タグで始まる、WordPressブロックエディタ向けの最適化されたHTMLのみを出力してください。"""

    try:
        print(f"[INFO] Generating HTML article with {model}...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_completion_tokens=MAX_OUTPUT_TOKENS,
        )
        
        html_content = response.choices[0].message.content.strip()
        print(f"[INFO] Generated HTML content: {len(html_content)} characters")
        
        return html_content
        
    except OpenAIError as e:
        print(f"[ERROR] OpenAI API error: {e}")
        raise SystemExit(f"Failed to generate article: {e}")


def improve_article_length(html_content: str, target_chars: int, model: str) -> str:
    """記事の文字数が不足している場合、内容を拡充"""
    
    if OpenAI is None:
        return html_content
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return html_content
    
    client = OpenAI(api_key=api_key)
    
    current_chars = count_japanese_chars(html_content)
    
    system_prompt = f"""あなたは記事の内容拡充専門家です。
    
提供されたHTML記事を{target_chars}文字に拡充してください：

【拡充ルール】
- 既存の内容の意味や構造は変更しない
- 具体例、詳細説明、体験談を追加して自然に文字数を増やす
- WordPressブロックエディタ対応のシンプルなHTML構造を維持
- p、h2、h3、h4、img、strong、em、ul、ol、liタグのみ使用
- 機械的なリストではなく、流れるような文章で拡充

現在{current_chars}文字から{target_chars}文字に拡充してください。"""

    user_prompt = f"""以下のHTML記事を{target_chars}文字に拡充してください：

{html_content}

既存の内容を活かしつつ、具体例や詳細説明を追加して自然に文字数を増やしてください。"""

    try:
        print(f"[INFO] Improving article length from {current_chars} to {target_chars} characters...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_completion_tokens=MAX_OUTPUT_TOKENS,
        )
        
        improved_html = response.choices[0].message.content.strip()
        print(f"[INFO] Improved article length: {count_japanese_chars(improved_html)} characters")
        
        return improved_html
        
    except OpenAIError as e:
        print(f"[ERROR] Failed to improve article length: {e}")
        return html_content


def fix_broken_html_tags(html_content: str) -> str:
    """破損したHTMLタグを自動修正する"""
    import re
    
    # 破損したstrongタグを修正
    html_content = re.sub(r'</strong、', '</strong>、', html_content)
    html_content = re.sub(r'</strong。', '</strong>。', html_content)
    html_content = re.sub(r'</strong！', '</strong>！', html_content)
    html_content = re.sub(r'</strong？', '</strong>？', html_content)
    
    # 破損したemタグを修正
    html_content = re.sub(r'</em、', '</em>、', html_content)
    html_content = re.sub(r'</em。', '</em>。', html_content)
    html_content = re.sub(r'</em！', '</em>！', html_content)
    html_content = re.sub(r'</em？', '</em>？', html_content)
    
    # その他の一般的な破損パターン
    html_content = re.sub(r'</h([1-6])、', r'</h\1>、', html_content)
    html_content = re.sub(r'</h([1-6])。', r'</h\1>。', html_content)
    
    return html_content


def review_html_article(html_content: str, model: str) -> tuple[List[str], str]:
    """HTMLコンテンツをレビューし、問題点と修正版を返す"""
    
    if OpenAI is None:
        print("[WARNING] OpenAI package not available, skipping review")
        return [], html_content
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[WARNING] OPENAI_API_KEY not set, skipping review")
        return [], html_content
    
    client = OpenAI(api_key=api_key)
    
    system_prompt = """あなたは日本語のHTML記事編集者です。WordPressブロックエディタ向けのHTML記事の品質をチェックし、問題点を指摘して改善版を提供します。

【レビュー観点】
- 文章の自然性と読みやすさ
- 数値や事例の信頼性（個別事例か一般的傾向かの明記）
- 断定的すぎる表現の緩和
- 具体例や前提条件の明記
- 法令や規制への言及の正確性
- 機密情報・個人情報の取り扱い注意喚起
- AIの幻覚（hallucination）や出典不明確性の警告
- 専門家相談の推奨
- HTML構造の最適性（WordPressブロック対応）

【重要：HTML構造について】
- 記事は必ずh1タグで始まること（WordPressタイトル抽出のため）
- 既存のh1タグがある場合は必ず保持すること
- h1タグがない場合は適切なタイトルのh1タグを追加すること
- 見出しの階層構造（h1→h2→h3）を適切に維持すること
- blockquoteタグは使用禁止（WordPressブロック互換性問題のため）
- imgタグ内のsrcにはプレースホルダーURL（example.com等）は使用禁止
- 実際の画像ファイルパスを使用するか、画像は別途自動生成される場合は省略

【出力形式】
必ずJSON形式で以下の2フィールドのみを含めてください：
- "issues": 問題点のリスト（文字列配列）
- "revised_html": 修正されたHTML（文字列、必ずh1タグで開始）"""

    user_prompt = f"""以下のHTML記事をレビューし、問題点を列挙して修正版を提示してください：

{html_content}

問題点と修正版をJSON形式で返してください。HTMLの構造は維持し、WordPressブロックエディタ対応を保ってください。"""

    try:
        print(f"[INFO] Reviewing HTML article with {model}...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_completion_tokens=MAX_OUTPUT_TOKENS,
        )
        
        review_text = response.choices[0].message.content.strip()
        print(f"[INFO] Review completed: {len(review_text)} characters")
        
        # JSONパース
        try:
            data = json.loads(review_text)
            issues = data.get("issues", [])
            revised_html = data.get("revised_html", html_content)
            
            if not isinstance(issues, list):
                issues = []
            if not isinstance(revised_html, str):
                revised_html = html_content
                
            print(f"[INFO] Found {len(issues)} issues for review")
            return issues, revised_html
            
        except json.JSONDecodeError as e:
            print(f"[WARNING] Failed to parse review JSON: {e}")
            return [], html_content
        
    except Exception as e:
        print(f"[ERROR] Review failed: {e}")
        return [], html_content


def generate_html_article_with_retry(material: str, model: str) -> str:
    """記事生成を行い、文字数が条件を満たすまでリトライ"""
    
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"[INFO] Article generation attempt {attempt}/{MAX_ATTEMPTS}")
        
        html_content = generate_article_with_openai(material, model)
        
        # HTMLタグ修正
        html_content = fix_broken_html_tags(html_content)
        
        # 文字数チェック
        char_count = count_japanese_chars(html_content)
        print(f"[INFO] Generated article length: {char_count} characters")
        
        if MIN_CHAR_COUNT <= char_count <= MAX_CHAR_COUNT:
            print(f"[SUCCESS] Article meets character requirements ({char_count} chars)")
            return html_content
        elif char_count < MIN_CHAR_COUNT:
            print(f"[INFO] Article too short ({char_count} chars), attempting to expand...")
            # 文字数不足の場合は拡充を試みる
            improved_html = improve_article_length(html_content, 3500, model)
            improved_char_count = count_japanese_chars(improved_html)
            
            if MIN_CHAR_COUNT <= improved_char_count <= MAX_CHAR_COUNT:
                print(f"[SUCCESS] Improved article meets requirements ({improved_char_count} chars)")
                return fix_broken_html_tags(improved_html)
            else:
                print(f"[WARNING] Improvement failed, continuing to next attempt...")
        else:
            print(f"[WARNING] Article too long ({char_count} chars), retrying...")
    
    # 最大試行回数に達した場合、最後の結果を返す
    print(f"[WARNING] Reached maximum attempts, returning last result")
    return fix_broken_html_tags(html_content)


def main() -> None:
    args = parse_args()
    
    # Input validation
    if not args.material.exists():
        print(f"[ERROR] Material file not found: {args.material}")
        raise SystemExit(1)
    
    # Read material
    print(f"[INFO] Reading material from: {args.material}")
    try:
        material = args.material.read_text(encoding="utf-8")
        print(f"[INFO] Material loaded: {len(material)} characters")
    except Exception as e:
        print(f"[ERROR] Failed to read material: {e}")
        raise SystemExit(1)
    
    if not material.strip():
        print("[ERROR] Material file is empty")
        raise SystemExit(1)
    
    # Create output directory if needed
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate HTML article
    try:
        html_content = generate_html_article_with_retry(material, args.model)
        
        # Review the generated article
        print(f"[INFO] Starting article review...")
        issues, revised_html = review_html_article(html_content, REVIEW_MODEL)
        
        # Use revised version if available and different
        final_html = revised_html if revised_html != html_content else html_content
        if revised_html != html_content:
            print(f"[INFO] Article was revised based on review feedback")
        else:
            print(f"[INFO] No revisions needed or review skipped")
        
        # Write the HTML file
        print(f"[INFO] Writing HTML article to: {args.output}")
        args.output.write_text(final_html, encoding="utf-8")
        
        # Generate review report
        timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_lines = [
            f"# Review Report for {args.output.name}",
            "",
            f"- Generated: {timestamp}",
            f"- Model: {REVIEW_MODEL}",
            "",
            "## Issues"
        ]
        
        if issues:
            for idx, issue in enumerate(issues, 1):
                report_lines.append(f"{idx}. {issue}")
        else:
            report_lines.append("レビュー結果: 特に修正は必要ありませんでした。")
        
        review_path = args.output.with_name(f"{args.output.stem}_review.md")
        review_path.write_text("\n".join(report_lines), encoding="utf-8")
        
        final_char_count = count_japanese_chars(final_html)
        print(f"[SUCCESS] HTML article generated successfully!")
        print(f"[INFO] Final character count: {final_char_count}")
        print(f"[INFO] Output file: {args.output}")
        
        # Display review results
        if issues:
            print(f"[INFO] Review found {len(issues)} issues:")
            for idx, issue in enumerate(issues, 1):
                print(f"  {idx}. {issue}")
        else:
            print("[INFO] Review found no issues")
        print(f"[INFO] Review report: {review_path}")
        
    except Exception as e:
        print(f"[ERROR] Failed to generate HTML article: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()