#!/usr/bin/env python3
"""
HTML記事の読みやすさとレイアウトを改善するツール

GPT-5-miniを使用してHTML記事を分析し、以下の改善を行う：
- 段落の適切な分割
- 読みやすい行間調整
- 不自然なレイアウトの修正
- 見出しの階層構造最適化
- リストや引用の適切な配置
"""

import sys
import argparse
from pathlib import Path
from openai import OpenAI
import os


def log_info(message: str):
    """情報ログを出力"""
    print(f"[INFO] improve_html: {message}")


def log_error(message: str):
    """エラーログを出力"""
    print(f"[ERROR] improve_html: {message}")


def improve_html_layout(html_content: str) -> str:
    """
    GPT-5-miniを使用してHTML記事のレイアウトと読みやすさを改善
    
    Args:
        html_content (str): 改善対象のHTML内容
        
    Returns:
        str: 改善されたHTML内容
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log_error("OPENAI_API_KEY environment variable not set")
        return html_content
    
    try:
        client = OpenAI(api_key=api_key)
        log_info("HTMLレイアウト改善を開始...")
        
        system_prompt = """あなたは日本語記事のHTMLレイアウト専門家です。
        
提供されたHTML記事を以下の観点で改善してください：

1. **段落の適切な分割**
   - 長すぎる段落を読みやすい長さに分割
   - 論理的な区切りで段落を分ける
   - 適切な<p>タグの使用

2. **読みやすいレイアウト**
   - 見出し（h1, h2, h3）の階層構造を整理
   - リスト項目の適切な配置
   - 重要な部分の強調（<strong>、<em>）

3. **自然な文章構造**
   - 文章の流れを改善
   - 接続詞の適切な使用
   - 読者にとって分かりやすい構成

4. **HTML品質向上**
   - 適切なHTMLタグの使用
   - セマンティックな構造
   - アクセシビリティの考慮

**重要な注意事項：**
- 記事の内容や意味を変更しないこと
- 画像タグ（<img>）は絶対に削除・変更しないこと
- 元の情報を保持すること
- HTMLとして有効な構造を維持すること

改善されたHTMLのみを返してください。説明は不要です。"""

        user_prompt = f"""以下のHTML記事を読みやすく、自然なレイアウトに改善してください：

{html_content}

記事の内容は変更せず、レイアウトと読みやすさのみを改善してください。"""

        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_completion_tokens=16000
        )
        
        improved_html = response.choices[0].message.content.strip()
        log_info("HTMLレイアウト改善が完了しました")
        
        # HTMLが適切に返されているかチェック
        if not improved_html or len(improved_html) < 100:
            log_error("改善されたHTMLが短すぎます。元のHTMLを返します")
            return html_content
            
        return improved_html
        
    except Exception as e:
        log_error(f"HTMLレイアウト改善中にエラーが発生: {str(e)}")
        return html_content


def main():
    parser = argparse.ArgumentParser(description="HTML記事のレイアウトと読みやすさを改善")
    parser.add_argument("--input", "-i", required=True, help="入力HTMLファイルのパス")
    parser.add_argument("--output", "-o", help="出力HTMLファイルのパス（指定しない場合は入力ファイルを上書き）")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        log_error(f"入力ファイルが見つかりません: {input_path}")
        sys.exit(1)
    
    try:
        # HTMLファイルを読み込み
        log_info(f"HTMLファイルを読み込み: {input_path}")
        with open(input_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # HTMLレイアウトを改善
        improved_html = improve_html_layout(html_content)
        
        # 出力ファイルパスを決定
        output_path = Path(args.output) if args.output else input_path
        
        # 改善されたHTMLを保存
        log_info(f"改善されたHTMLを保存: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(improved_html)
        
        log_info("HTML改善処理が完了しました")
        
    except Exception as e:
        log_error(f"処理中にエラーが発生: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()