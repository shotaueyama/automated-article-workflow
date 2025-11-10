#!/usr/bin/env python3
"""HTMLファイルから不足している画像のみを生成するツール"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="HTMLファイルから不足している画像のみを生成"
    )
    parser.add_argument(
        "article_id",
        type=int,
        help="記事ID（articles/{article_id}/article.htmlを対象）"
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=3,
        help="画像生成のリトライ回数. Defaults to %(default)s.",
    )
    return parser.parse_args()


def extract_h2_headings(html_content: str) -> List[str]:
    """HTMLからh2見出しを抽出"""
    pattern = r'<h2>(.*?)</h2>'
    matches = re.findall(pattern, html_content)
    return matches


def find_existing_images(images_dir: Path) -> List[str]:
    """既存の画像ファイル名リストを取得"""
    if not images_dir.exists():
        return []
    return [img.name for img in images_dir.glob("*.png")]


def generate_filename_from_heading(heading: str, index: int) -> str:
    """見出しからファイル名を生成"""
    import datetime as dt
    
    timestamp = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    
    # 見出しをファイル名用にサニタイズ
    if "AI" in heading or "エージェント" in heading:
        suffix = "ai"
    elif any(word in heading for word in ["業務", "仕事", "実践", "方法", "チェック"]):
        suffix = "section"
    else:
        suffix = "section"
    
    return f"{timestamp}-{suffix}"


def generate_image_prompt(heading: str) -> str:
    """見出しから画像生成プロンプトを作成"""
    if OpenAI is None:
        return f"Business illustration representing: {heading}"
    
    # OpenAI APIを使ってより適切なプロンプトを生成
    import os
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return f"Business illustration representing: {heading}"
    
    client = OpenAI(api_key=api_key)
    
    prompt = f"""以下の見出しに最適な画像生成プロンプトを作成してください：
    
見出し: {heading}

要件:
- ビジネス記事にふさわしいプロフェッショナルな画像
- シンプルでミニマルな可愛い3D rendered animation style
- 少ないオブジェクトでクリーンな構成、余白を多く
- 丸みを帯びたキャラクター、大きな表情豊かな目
- 柔らかいテクスチャ、明るく彩度の高い色彩
- 楽しげで親しみやすい雰囲気、カートゥン的なプロポーション
- 日本のビジネス環境に適した内容
- 120文字以内の英語プロンプト

プロンプトのみを出力してください:"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたはビジネス記事用の3Dアニメーション風画像生成プロンプト作成専門家です。現代的な3Dアニメーション映画のようなスタイルでプロンプトを作成します。"},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=200,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Warning: Failed to generate custom prompt: {e}", file=sys.stderr)
        return f"Modern business illustration representing {heading}"


def check_image_needed(heading: str, images_dir: Path, heading_index: int) -> Tuple[bool, str]:
    """見出しに対応する画像が必要かチェック"""
    filename_base = generate_filename_from_heading(heading, heading_index)
    expected_patterns = [
        f"*-ai.png",
        f"*-section.png",
        f"{filename_base}.png"
    ]
    
    existing_images = find_existing_images(images_dir)
    
    # 既存画像がある場合はスキップ
    if len(existing_images) > heading_index:
        print(f"[SKIP] {heading[:30]}... (既存画像あり)")
        return False, ""
    
    return True, filename_base


def main() -> int:
    args = parse_args()
    
    article_dir = REPO_ROOT / "articles" / str(args.article_id)
    html_path = article_dir / "article.html"
    images_dir = article_dir / "images"
    
    if not html_path.exists():
        print(f"Error: {html_path} not found", file=sys.stderr)
        return 1
    
    # HTMLからh2見出しを抽出
    html_content = html_path.read_text(encoding="utf-8")
    headings = extract_h2_headings(html_content)
    
    if not headings:
        print("No h2 headings found in HTML", file=sys.stderr)
        return 1
    
    print(f"Found {len(headings)} h2 headings in article {args.article_id}")
    
    # 画像ディレクトリの確認
    images_dir.mkdir(parents=True, exist_ok=True)
    existing_images = find_existing_images(images_dir)
    print(f"Existing images: {len(existing_images)}")
    
    missing_count = 0
    
    # 各見出しについて画像生成の必要性をチェック
    for i, heading in enumerate(headings):
        needs_image, filename_base = check_image_needed(heading, images_dir, i)
        
        if not needs_image:
            continue
        
        missing_count += 1
        print(f"\n[GENERATE] {heading[:50]}...")
        
        # プロンプト生成
        prompt = generate_image_prompt(heading)
        print(f"Prompt: {prompt[:80]}...")
        
        # 画像生成コマンド実行
        cmd = [
            sys.executable,
            str(REPO_ROOT / "tools" / "generate_image.py"),
            prompt,
            "--output-dir",
            str(images_dir),
            "--filename",
            filename_base,
            "--retry-attempts",
            str(args.retry_attempts),
        ]
        
        import subprocess
        try:
            result = subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                print(f"✅ Generated: {filename_base}.png")
            else:
                print(f"❌ Failed to generate image for: {heading}")
                print(f"Error: {result.stderr}")
                return 1
                
        except subprocess.TimeoutExpired:
            print(f"❌ Timeout generating image for: {heading}")
            return 1
        except Exception as e:
            print(f"❌ Error generating image for: {heading}: {e}")
            return 1
    
    if missing_count == 0:
        print("\n✅ All images already exist. No generation needed.")
    else:
        print(f"\n✅ Successfully generated {missing_count} missing images for article {args.article_id}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())