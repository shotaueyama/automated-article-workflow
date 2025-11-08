#!/usr/bin/env python3
"""
WordPressブロックエディタ向けHTML記事レイアウト改善ツール

GPT-5-miniを使用してHTML記事をWordPressブロックエディタ（Gutenberg）で
正しく表示されるように最適化する：
- WordPressブロック互換の段落分割
- ブロックエディタ対応の見出し階層構造
- 標準HTMLタグによるシンプルなレイアウト
- ブロックエディタでレイアウト崩れしない構造
- リストや強調の適切な配置
"""

import sys
import argparse
import re
from pathlib import Path
from openai import OpenAI
import os


def log_info(message: str):
    """情報ログを出力"""
    print(f"[INFO] improve_html: {message}")


def log_error(message: str):
    """エラーログを出力"""
    print(f"[ERROR] improve_html: {message}")


def fix_broken_html_tags(html_content: str) -> str:
    """
    破損したHTMLタグを自動修正する
    
    Args:
        html_content (str): 修正対象のHTML内容
        
    Returns:
        str: 修正されたHTML内容
    """
    # 破損したstrongタグを修正 (例: </strong、 -> </strong>、)
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
        # まず破損したHTMLタグを修正
        log_info("破損したHTMLタグを修正中...")
        html_content = fix_broken_html_tags(html_content)
        
        client = OpenAI(api_key=api_key)
        log_info("HTMLレイアウト改善を開始...")
        
        system_prompt = """あなたはWordPressブロックエディタ（Gutenberg）専門の日本語記事レイアウト専門家です。

提供されたHTML記事をWordPressのブロックエディタで正しく表示されるように改善してください：

1. **段落の最適化（WordPressブロック対応）**
   - 長い段落を適切な長さに分割（1段落150-200文字目安）
   - 各段落は明確な<p>タグで区切る
   - 段落間の論理的な流れを維持

2. **見出し構造の最適化**
   - h1は記事タイトル用なので使用しない
   - h2を主要セクション、h3をサブセクションとして使用
   - 見出しの階層を論理的に構成（h2→h3→h4の順序を守る）

3. **リストの適切な使用**
   - 箇条書きは<ul><li>で構成
   - 番号付きリストは<ol><li>で構成
   - リスト内の各項目は簡潔にまとめる

4. **強調とフォーマット**
   - 重要な部分は<strong>で強調
   - 軽い強調は<em>を使用
   - 引用は<blockquote>を使用

5. **WordPressブロック互換性**
   - divタグやspanタグは最小限に抑制
   - section、article、header、main、figureタグは除去
   - 複雑なCSSクラスは使用しない
   - p、h2、h3、h4、ul、ol、li、img、strong、emのみ使用

**重要な制約事項：**
- 記事の内容・意味・情報は一切変更しない
- 画像タグ（<img>）は絶対に削除・変更しない（ただしalt属性の##記号は除去）
- 画像の順序や配置は維持する
- 元の文章の表現や言い回しは保持する
- section、article、header、main、figure、nav等の構造タグは完全に除去
- WordPressブロックエディタで認識される最小限のタグのみ使用
- 極めてシンプルなフラットな構造にする
- 画像のalt属性から不要な##記号を除去してクリーンにする
- 破損したHTMLタグ（例：<strong>text</strong、）を自動修正する

改善されたHTMLのみを返してください。説明やコメントは不要です。"""

        user_prompt = f"""以下のHTML記事をWordPressブロックエディタで正しく表示されるように改善してください：

{html_content}

**改善ポイント：**
- WordPressブロックエディタ専用の極めてシンプルな構造に変換
- section、article、header、main、figure等の構造タグを完全除去
- p、h2、h3、h4、img、strong、em、ul、ol、li、blockquoteのみ使用
- 段落は適切な長さで<p>タグで明確に分割
- 見出し階層を整理（h2→h3→h4の順序）
- フラットで最小限のHTML構造
- 画像のalt属性から不要な##記号を除去
- 破損したHTMLタグの自動修正（例：<strong>text</strong、 → <strong>text</strong>）

記事の内容・意味・画像は絶対に変更せず、構造最適化とHTMLタグ修正のみ行ってください。"""

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
        
        # 最終的に再度HTMLタグ修正を実行
        log_info("最終HTMLタグ修正を実行中...")
        improved_html = fix_broken_html_tags(improved_html)
            
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