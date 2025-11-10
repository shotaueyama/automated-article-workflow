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
# Get model settings from environment variables with fallbacks
DEFAULT_MODEL = os.environ.get("PRIMARY_MODEL", "gpt-5-mini-2025-08-07")
FALLBACK_MODEL = os.environ.get("FALLBACK_MODEL", "gpt-5-nano")
REVIEW_MODEL = os.environ.get("PRIMARY_REVIEW_MODEL", "gpt-5-mini-2025-08-07")
REVIEW_FALLBACK_MODEL = os.environ.get("FALLBACK_REVIEW_MODEL", "gpt-5-nano")

MIN_CHAR_COUNT = 3500
MAX_CHAR_COUNT = 4500
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


def count_japanese_chars(text: str) -> int:
    """日本語文字数をカウント（ひらがな・カタカナ・漢字・数字・英字・記号等）"""
    # HTML タグを除去してから文字数カウント
    import re
    clean_text = re.sub(r'<[^>]+>', '', text)
    return len(clean_text.replace(" ", "").replace("\n", ""))


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


def generate_outline_from_material(material: str, model: str) -> str:
    """material.mdから5つのh2見出しを生成"""
    
    if OpenAI is None:
        raise SystemExit("OpenAI library is not available.")
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY environment variable not set.")
    
    client = OpenAI(api_key=api_key)
    
    system_prompt = """あなたは記事構成の専門家です。リサーチメモを基に、読者にとって有益で論理的な流れの5つの見出しを作成してください。

【見出し作成の要件】
- material.mdの内容を全体的に把握し、重要なポイントを網羅
- 読者の関心を引く魅力的で具体的な見出し
- 論理的な順序で配置（導入→詳細→実践→応用→まとめの流れ）
- 専門用語は避け、わかりやすい表現を使用
- 各見出しは30文字以内で簡潔に

【出力形式】
JSON形式で以下のように出力してください：
{
  "h2_headings": [
    "見出し1",
    "見出し2", 
    "見出し3",
    "見出し4",
    "見出し5"
  ]
}"""

    user_prompt = f"""以下のリサーチメモを分析し、5つのh2見出しを作成してください。

=== リサーチメモ ===
{material}

上記の内容を基に、読者が理解しやすい順序で5つのh2見出しをJSON形式で出力してください。"""

    try:
        print(f"[INFO] Generating outline with {model}...")
        response = try_model_with_fallback(
            client=client,
            model=model,
            fallback_model=FALLBACK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_completion_tokens=1000,
        )
        
        outline_json = response.choices[0].message.content.strip()
        print(f"[INFO] Generated outline: {len(outline_json)} characters")
        
        return outline_json
        
    except Exception as e:
        print(f"[ERROR] Failed to generate outline: {e}")
        raise SystemExit(f"Failed to generate outline: {e}")


def generate_article_with_openai(material: str, model: str) -> str:
    """material.mdを基に目次を作成してから記事を生成"""
    
    if OpenAI is None:
        raise SystemExit("OpenAI library is not available.")
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY environment variable not set.")
    
    client = OpenAI(api_key=api_key)
    
    # まず目次を生成
    outline_json = generate_outline_from_material(material, model)
    
    # JSONをパース
    try:
        import json
        outline_data = json.loads(outline_json)
        h2_headings = outline_data.get("h2_headings", [])
        if len(h2_headings) != 5:
            print(f"[WARNING] Expected 5 headings, got {len(h2_headings)}. Using generated headings as-is.")
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse outline JSON: {e}")
        h2_headings = [
            "基本的な概要と重要性",
            "具体的な方法とアプローチ",
            "実践的なステップとコツ",
            "よくある問題と解決策",
            "今後の展望とまとめ"
        ]
        print("[INFO] Using fallback headings")
    
    print(f"[INFO] Generated headings: {h2_headings}")
    
    # 生成された見出しを文字列形式に変換
    headings_text = "\n".join([f"- {heading}" for heading in h2_headings])
    
    system_prompt = """あなたは、WordPressブロックエディタ向けの日本語記事を直接HTML形式で生成する専門ライターです。

以下の制約に従って、WordPressブロックエディタで完璧に表示される高品質なHTML記事を生成してください：

【WordPressブロック対応HTML構造】
- p、h2、h3、h4、img、strong、em、ul、ol、liタグのみ使用
- section、article、header、main、figure、div、blockquoteタグは一切使用禁止
- 極めてシンプルでフラットなHTML構造

【記事品質要件】
- **🚨絶対要求: 3500文字以上4500文字以内の日本語記事（HTMLタグ除く純粋な文字数）**
- **単なる説明文は避け、人間味のある面白い文章を心がける**
- **体験談、失敗談、驚きのエピソード、意外な発見を積極的に盛り込む**
- **読者が「へぇ〜！」「そうなんだ！」と思わず声に出したくなるような内容**
- 適度に口語表現を使い、まるで友達と話しているような親しみやすさ
- 機械的なリストや箇条書きを最小限に抑制し、ストーリー性を重視
- 流れるような文章で情報を伝える物語調のスタイル
- **読者の感情に訴えかける表現（共感、驚き、興味、好奇心）を多用**
- **具体的な例え話や比喩を使って複雑な内容をわかりやすく**
- 専門用語はなるべく使わず、高校3年生の理解度でもわかるように書いてください
- 専門用語を入れる場合は、身近な例えで説明を簡潔に入れてください

【HTML構造ルール】
- 記事は必ずh1タグで始まる（記事タイトル用、WordPressアップロード時に抽出される）
- **h1タグの直後に導入文（前書き）を必ず配置**し、その後に最初のh2見出しを配置
- 見出し階層：h1（記事タイトル）→ 導入文（p タグ） → h2（主要セクション）→ h3（サブセクション）→ h4
- 段落は150-200文字目安で適切に分割
- **h2は最大5つまで利用可能(最大5つのセクションで構成)**
- 画像タグ使用禁止（画像は後で自動生成・挿入されるため、imgタグは含めない）
- 強調は<strong>、軽い強調は<em>を使用
- リストが必要な場合のみ<ul><li>を使用
- blockquoteタグは使用禁止（WordPressブロックエディタ互換性のため）

【重要な注意事項】
- HTMLのみを出力（説明や前置きは不要）
- **🚨文字数は絶対に3500文字以上になるよう十分な内容で構成（短い記事は絶対不可）**
- **文字数計算: HTMLタグを除いた純粋な日本語テキストで3500-4500文字**
- 各セクションは具体例や詳細説明を豊富に含む
- 専門用語はなるべく使わず、高校3年生の理解度でもわかるように書いてください
- 専門用語を入れる場合は、専門用語の説明を簡潔に入れてください
- 読者が自然に理解できる構成"""

    user_prompt = f"""以下のリサーチメモと指定された見出し構成を踏まえて、WordPressブロックエディタ向けの日本語HTML記事を生成してください。

【重要な要求】
- **必ずh1タグでタイトルから開始する**（WordPressアップロード時に抽出されます）
- **以下の5つのh2見出しのみを使用して記事を構成する（これ以上のh2見出しは絶対に追加しない）**：
{headings_text}
- **重要: h2見出しは上記の5つのみ使用し、追加のh2見出しは一切作成しないでください**
- **🚨絶対要求: 3500文字以上4500文字以内の日本語HTML記事（HTMLタグを除く純粋な日本語文字数で計算）**
- **各h2セクション最低700文字、導入文最低300文字で構成すること**
- **リサーチメモを重視**して、各h2セクションの内容を充実させてください
- **もしリサーチメモにデータと出典がある場合は確実に出典**を載せてください
- **単なる説明文は絶対に避け、読者が思わず最後まで読みたくなる面白いコンテンツに**
- **「なるほど！」「知らなかった！」「面白い！」と感じる要素を各セクションに必ず含める**
- **リアルな体験談、具体的なエピソード、意外な事実を積極的に活用**
- **読者が親近感を持てるような身近な例えや比喩を多用**
- **専門用語はなるべく使わず、高校3年生の理解度でもわかるように**書いてください
- **blockquoteタグは使用禁止**（WordPress互換性問題のため）
- **imgタグのsrcにはプレースホルダーURL禁止**（example.com等は使用不可）
- WordPressブロックエディタで完璧に表示されるシンプルな構造
- 人間らしい自然な文章（機械的なリストは最小限）
- 読者が感情移入できるストーリー性のある記事

【記事構成指示】
1. h1タグでメインタイトルを設定
2. **h1の直後に、最初のh2見出しの前に、必ず導入文（前書き）を300-500文字程度で配置する**
   - 記事全体の概要や読者への問いかけ
   - 「この記事では〜」「〜について解説します」のような形式
   - 読者の興味を引く導入として機能させる
3. 上記の5つのh2見出しを順番に使用
4. 各h2セクションでは、リサーチメモの該当部分を参考に**ストーリー性のある面白い内容**で詳しく説明
5. **🚨絶対要求: 各セクション最低700文字以上**で充実した内容にする（短いセクションは絶対に不可）
6. **各セクションに必ず「驚き」「発見」「共感」のいずれかの要素を含める**
7. **読者が「続きを読みたい」と思うような文章構成にする**

=== リサーチメモ ===
{material}

必ずh1タグで始まり、指定された5つのh2見出しを使用した、WordPressブロックエディタ向けの最適化されたHTMLのみを出力してください。"""

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

【最重要レビュー観点】
- **単なる説明文になっていないか（最重要）**
- **読者が「面白い！」「へぇ〜！」と感じる要素があるか**
- **人間味のある親しみやすい文章になっているか**
- **体験談、エピソード、意外な事実が含まれているか**
- **読者の感情に訴えかける表現があるか（共感、驚き、興味、好奇心）**
- **具体的な例え話や比喩で説明されているか**
- **まるで友達と話しているような自然さがあるか**
- **読者が最後まで読みたくなる魅力的な内容か**

【基本品質観点】
- 文章の自然性と読みやすさ
- 数値や事例の信頼性（個別事例か一般的傾向かの明記）
- もしリサーチメモにデータの出典がある場合は確実に出典を載せる
- 断定的すぎる表現の緩和
- 具体例や前提条件の明記
- 法令や規制への言及の正確性
- 専門用語をなるべく使わない
- リサーチメモを重視して書く
- 高校3年生の理解度でもわかるように書く
- 専門用語を入れる場合は、専門用語の説明を簡潔に入れる
- HTML構造の最適性（WordPressブロック対応）
- 文章内容に対するブログの範囲内でのレイアウト的読みやすさ

【重要：HTML構造について】
- 記事は必ずh1タグで始まること（WordPressタイトル抽出のため）
- 既存のh1タグがある場合は必ず保持すること
- h1タグがない場合は適切なタイトルのh1タグを追加すること
- 見出しの階層構造（h1→h2→h3）を適切に維持すること
- **h2見出しは最大5つまでに制限する（追加のh2見出しは絶対に作成しない）**
- **既存のh2見出しの数を変更してはいけない（5つ以下の場合は現状維持）**
- blockquoteタグは使用禁止（WordPressブロック互換性問題のため）
- imgタグ内のsrcにはプレースホルダーURL（example.com等）は使用禁止
- 実際の画像ファイルパスを使用するか、画像は別途自動生成される場合は省略

【出力形式】
必ずJSON形式で以下の2フィールドのみを含めてください：
- "issues": 問題点のリスト（文字列配列）
- "revised_html": 修正されたHTML（文字列、必ずh1タグで開始）"""

    user_prompt = f"""以下のHTML記事をレビューし、問題点を列挙して修正版を提示してください：

{html_content}

【レビューで特に厳しくチェックしてください】
1. **h1タイトルの直後に導入文（前書き）があるか（なければ追加）**
2. **単なる説明的な文章になっていないか**
3. **読者が「つまらない」と感じる箇所はないか**
4. **人間味や親しみやすさが足りない部分はないか**
5. **体験談やエピソード、驚きの要素が不足していないか**
6. **読者の感情に響く表現が使われているか**
7. **友達に話すような自然な口調になっているか**
8. **読者が「続きを読みたい」と思える魅力があるか**
9. **h2見出しの数が5つを超えていないか（超えている場合は削除・統合で5つ以下に調整）**

問題点と修正版をJSON形式で返してください。**h2見出しは絶対に5つ以下に保ち**、HTMLの構造は維持し、WordPressブロックエディタ対応を保ってください。"""

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
            target_chars = max(3700, MIN_CHAR_COUNT + 200)  # 最低3700文字目標
            improved_html = improve_article_length(html_content, target_chars, model)
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