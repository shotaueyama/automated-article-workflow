#!/usr/bin/env python3
"""Generate a WordPress-optimized HTML article (3000-4000 Japanese characters) from material.md."""
from __future__ import annotations

import argparse
import os
import datetime as dt
from pathlib import Path
from typing import List
import re

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
# Get model settings from environment variables with fallbacks
DEFAULT_MODEL = os.environ.get("PRIMARY_MODEL", "gpt-5-mini-2025-08-07")
FALLBACK_MODEL = os.environ.get("FALLBACK_MODEL", "gpt-5-nano")
REVIEW_MODEL = os.environ.get("PRIMARY_REVIEW_MODEL", "gpt-5-mini-2025-08-07")
REVIEW_FALLBACK_MODEL = os.environ.get("FALLBACK_REVIEW_MODEL", "gpt-5-nano")

MIN_CHAR_COUNT = 3000
MAX_CHAR_COUNT = 4000
MAX_ATTEMPTS = 5
MAX_OUTPUT_TOKENS = 128_000


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


def read_material(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"Material file not found: {path}")
    return path.read_text(encoding="utf-8").strip()






def extract_title_from_material(material: str) -> str:
    """リサーチメモから最初の#タイトルを抽出"""
    lines = material.split('\n')
    for line in lines:
        if line.startswith('# ') and 'Research Notes' not in line:
            # '# ' を除去してタイトル部分のみを取得
            title = line.strip('# ').strip()
            # ' – ' でリサーチメモタイトルを分割して前半を取得
            if ' – ' in title:
                return title.split(' – ')[0].strip()
            return title
    return "記事タイトル"  # デフォルト


def try_model_with_fallback(client, model: str, fallback_model: str, messages: list, **kwargs) -> any:
    """モデル使用を試行し、失敗時にフォールバックモデルを使用"""
    try:
        print(f"[INFO] Attempting to use model: {model}")
        return client.chat.completions.create(model=model, messages=messages, **kwargs)
    except Exception as e:
        error_str = str(e).lower()
        # より幅幅いエラーパターンでフォールバックをトリガー
        should_fallback = any([
            "model" in error_str,
            "not found" in error_str, 
            "unavailable" in error_str,
            "permission" in error_str,
            "quota" in error_str,  # クォータ超過
            "insufficient_quota" in error_str,
            "rate_limit" in error_str,
            "429" in error_str  # HTTP 429 Too Many Requests
        ])
        
        if should_fallback:
            print(f"[WARNING] Model {model} failed: {e}")
            print(f"[INFO] Falling back to model: {fallback_model}")
            try:
                return client.chat.completions.create(model=fallback_model, messages=messages, **kwargs)
            except Exception as fallback_e:
                print(f"[ERROR] Fallback model {fallback_model} also failed: {fallback_e}")
                raise fallback_e
        else:
            raise e


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
- h1、p、h2、h3、h4、img、strong、em、ul、ol、li、blockquoteタグのみ使用
- section、article、header、main、figure、divタグは一切使用禁止
- 極めてシンプルでフラットなHTML構造

【記事品質要件】
- 必ず3200〜3800文字（理想は3500文字）の日本語記事
- 人間らしいブログ調で体験談や感情を織り交ぜた自然な文章
- 適度に口語表現を使い、親しみやすさを心がける
- 機械的なリストや箇条書きを最小限に抑制
- 流れるような文章で情報を伝える物語調のスタイル

【HTML構造ルール】
- 記事冒頭は必ずh1タグでメインタイトルを配置
- 見出し階層：h1（メインタイトル）→ h2（主要セクション）→ h3（サブセクション）→ h4
- 段落は150-200文字目安で適切に分割
- 画像は段落間に適切に配置
- 強調は<strong>、軽い強調は<em>を使用
- リストが必要な場合のみ<ul><li>を使用

【重要な注意事項】
- HTMLのみを出力（説明や前置きは不要）
- 文字数は3200文字未満にならないよう十分な内容で構成
- 各セクションは具体例や詳細説明を豊富に含む
- 読者が自然に理解できる構成"""

    # リサーチメモからタイトルを抽出
    article_title = extract_title_from_material(material)
    
    user_prompt = f"""以下のリサーチメモを踏まえて、WordPressブロックエディタ向けの日本語HTML記事を生成してください。

【重要な要求】
- **必ず3200〜3800文字（理想は3500文字）**の日本語HTML記事
- WordPressブロックエディタで完璧に表示されるシンプルな構造
- 人間らしい自然な文章（機械的なリストは最小限）
- 体験談や感情を織り交ぜた読みやすい記事
- **記事の冒頭に「<h1>{article_title}</h1>」を必ず配置**

=== リサーチメモ ===
{material}

WordPressブロックエディタ向けの最適化されたHTMLのみを出力してください。
記事の最初は必ず「<h1>{article_title}</h1>」から始めてください。"""

    try:
        print(f"[INFO] Generating HTML article with {model}...")
        response = try_model_with_fallback(
            client=client,
            model=model,
            fallback_model=FALLBACK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_completion_tokens=MAX_OUTPUT_TOKENS,
        )
        
        html_content = response.choices[0].message.content.strip()
        print(f"[INFO] Generated HTML content: {len(html_content)} characters")
        
        return html_content
        
    except Exception as e:
        print(f"[ERROR] Failed to generate article: {e}")
        raise SystemExit(f"Failed to generate article: {e}")


def count_japanese_chars(text: str) -> int:
    """日本語文字数をカウント（ひらがな・カタカナ・漢字・数字・英字・記号等）"""
    # HTML タグを除去してから文字数カウント
    clean_text = re.sub(r'<[^>]+>', '', text)
    return len(clean_text.replace(" ", "").replace("\n", ""))




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
- p、h2、h3、h4、img、strong、em、ul、ol、li、blockquoteタグのみ使用
- 機械的なリストではなく、流れるような文章で拡充

現在{current_chars}文字から{target_chars}文字に拡充してください。"""

    user_prompt = f"""以下のHTML記事を{target_chars}文字に拡充してください：

{html_content}

既存の内容を活かしつつ、具体例や詳細説明を追加して自然に文字数を増やしてください。"""

    try:
        print(f"[INFO] Improving article length from {current_chars} to {target_chars} characters...")
        response = try_model_with_fallback(
            client=client,
            model=model,
            fallback_model=FALLBACK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_completion_tokens=MAX_OUTPUT_TOKENS,
        )
        
        improved_html = response.choices[0].message.content.strip()
        print(f"[INFO] Improved article length: {count_japanese_chars(improved_html)} characters")
        
        return improved_html
        
    except Exception as e:
        print(f"[ERROR] Failed to improve article length: {e}")
        return html_content


def fix_broken_html_tags(html_content: str) -> str:
    """破損したHTMLタグを自動修正する"""
    
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


def review_html_article(html_content: str, model: str) -> tuple[list[str], str]:
    """HTMLコンテンツをレビューし、問題点と修正版を返す"""
    
    if OpenAI is None:
        return [], html_content
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return [], html_content
    
    client = OpenAI(api_key=api_key)
    
    system_prompt = """あなたは日本語のHTML記事編集者です。WordPressブロックエディタ向けのHTML記事の品質をチェックし、問題点を指摘して改善版を提供します。

【レビュー観点】
- 文章の自然性と読みやすさ
- 数値や事例の信頼性（個別事例か一般的傾向かの明記）
- 断定的すぎる表現の緩和
- 具体例や前提条件の明記
- 法令や規制への言及の正確性
- HTML構造の最適性（WordPressブロック対応）

【出力形式】
必ずJSON形式で以下の2フィールドのみを含めてください：
- "issues": 問題点のリスト（文字列配列）
- "revised_html": 修正されたHTML（文字列）"""

    user_prompt = f"""以下のHTML記事をレビューし、問題点を列挙して修正版を提示してください：

{html_content}

問題点と修正版をJSON形式で返してください。HTMLの構造は維持し、WordPressブロックエディタ対応を保ってください。"""

    try:
        print(f"[INFO] Reviewing HTML article with {model}...")
        response = try_model_with_fallback(
            client=client,
            model=model,
            fallback_model=REVIEW_FALLBACK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_completion_tokens=MAX_OUTPUT_TOKENS,
        )
        
        review_text = response.choices[0].message.content.strip()
        print(f"[INFO] Review completed: {len(review_text)} characters")
        
        # JSONパース
        import json
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
        issues, revised_html = review_html_article(html_content, args.model)
        
        # Use revised version if available
        final_html = revised_html if revised_html != html_content else html_content
        final_html = fix_broken_html_tags(final_html)
        
        # Write the HTML file
        print(f"[INFO] Writing HTML article to: {args.output}")
        args.output.write_text(final_html, encoding="utf-8")
        
        # Generate review report
        timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_lines = [
            f"# Review Report for {args.output.name}",
            "",
            f"- Generated: {timestamp}",
            f"- Model: {args.model}",
            "",
        ]
        
        if issues:
            report_lines.append("## Issues")
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
        
        if issues:
            print(f"[INFO] Review issues detected: {len(issues)}")
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
