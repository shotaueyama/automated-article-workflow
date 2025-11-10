#!/usr/bin/env python3
"""Alternative research tool using GPT-4o-search-preview + report generation for material.md."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import List, Dict, Any

from openai import OpenAI
from openai import OpenAIError

ARTICLES_ROOT = Path("articles")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Research with GPT-4o-search-preview, then save output to articles/<n>/material.md."
    )
    parser.add_argument("query", help="Research topic or question to investigate.")
    parser.add_argument(
        "--search-model",
        default=os.environ.get("PRIMARY_SEARCH_MODEL", "gpt-4o-search-preview"),
        help="OpenAI search model to use (default: %(default)s).",
    )
    parser.add_argument(
        "--report-model",
        default=os.environ.get("PRIMARY_RESEARCH_MODEL", "gpt-5-mini"),
        help="Model for report generation (default: %(default)s).",
    )
    parser.add_argument(
        "--strategy-model",
        default=os.environ.get("PRIMARY_STRATEGY_MODEL", "gpt-5-mini"),
        help="Model for research strategy planning (default: %(default)s).",
    )
    parser.add_argument(
        "--fallback-model",
        default=os.environ.get("FALLBACK_RESEARCH_MODEL", "gpt-5-nano"),
        help="Fallback model when primary models fail (default: %(default)s).",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=12,
        help="Maximum number of search queries to perform (default: %(default)s).",
    )
    parser.add_argument(
        "--depth",
        choices=["basic", "detailed", "comprehensive"],
        default="comprehensive",
        help="Research depth level (default: %(default)s).",
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


def get_next_section_strategy(client: OpenAI, topic: str, current_report: str, strategy_model: str, fallback_model: str, section_count: int) -> Dict[str, Any]:
    """現在のレポート内容を踏まえて、次に調査すべきセクションを戦略的に決定"""
    
    system_prompt = f"""あなたは戦略コンサルタントです。これまでに作成されたレポート内容を分析し、さらに価値を高めるために次に調査すべきセクションを1つ戦略的に決定してください。

## 分析要件：
1. 現在のレポートの強み・弱みを評価
2. 読者にとって最も価値の高い次のセクションを特定
3. 既存内容との重複を避け、新しい価値を追加
4. 論理的な流れと一貫性を考慮

## 出力形式（JSON）：
{{
  "should_continue": true/false,
  "analysis": "現在のレポートの評価と次のセクションの必要性（150字程度）",
  "next_section": {{
    "section_title": "次のセクション名",
    "description": "このセクションの目的と価値（100-150字）",
    "key_questions": ["調査すべき具体的な質問1", "質問2", "質問3"],
    "expected_insights": "期待される価値・洞察（50-80字）",
    "priority": "high/medium/low"
  }}
}}

## 継続判断基準：
- 既に十分包括的: should_continue = false
- まだ重要な価値を追加可能: should_continue = true
- セクション数が{section_count}以上: 継続を慎重に判断

現在のレポートを分析し、最適な次のステップを決定してください。"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            # より明確なプロンプトでJSONを強制
            enhanced_prompt = f"""{system_prompt}

## 重要: 必ずJSON形式で出力してください
以下の厳密なJSON形式で回答してください。他の文字は一切含めないでください：

{{
  "should_continue": true,
  "analysis": "現在のレポートの評価と次のセクションの必要性",
  "next_section": {{
    "section_title": "次のセクション名",
    "description": "このセクションの目的と価値",
    "key_questions": ["質問1", "質問2", "質問3"],
    "expected_insights": "期待される価値",
    "priority": "high"
  }}
}}"""

            response = try_model_with_fallback(
                client=client,
                model=strategy_model,
                fallback_model=fallback_model,
                messages=[
                    {"role": "system", "content": enhanced_prompt},
                    {"role": "user", "content": f"トピック: {topic}\n\n現在のレポート内容:\n{current_report}\n\n上記を分析して、次に追加すべきセクションをJSON形式で提案してください。"}
                ],
                max_completion_tokens=3000,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content.strip()
            print(f"Raw JSON response (attempt {attempt + 1}): {content}")
            
            import json as json_lib
            strategy = json_lib.loads(content)
            
            # 必要なフィールドの存在確認
            if not all(key in strategy for key in ["should_continue", "analysis"]):
                raise ValueError("Missing required fields in JSON response")
            
            return strategy
            
        except Exception as e:
            print(f"Strategy planning attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                # 最後の試行も失敗した場合は終了
                print("All retry attempts failed. Stopping research.")
                return {
                    "should_continue": False,
                    "analysis": f"戦略プランニングが{max_retries}回失敗したため終了します",
                    "next_section": None
                }
            print(f"Retrying... ({attempt + 1}/{max_retries})")
            
    # ここには到達しないはずですが、安全のため
    return {
        "should_continue": False,
        "analysis": "予期しないエラーが発生しました",
        "next_section": None
    }


def analyze_topic_and_create_research_plan(client: OpenAI, topic: str, strategy_model: str, max_sections: int = 8) -> Dict[str, Any]:
    """GPT-5-miniでトピックを分析し、包括的な調査計画を作成"""
    
    system_prompt = f"""あなたは戦略コンサルタントです。与えられたトピックについて、極めて包括的で価値の高い調査レポートを作成するための最適なリサーチ戦略を設計してください。

## 分析要件：
1. トピックの本質的な価値と重要性を分析
2. 対象読者のニーズと知りたい情報を特定
3. 調査すべき核心的な領域を体系的に整理
4. 各領域で取得すべき具体的情報を明確化

## 出力形式：
以下のJSON形式で{max_sections}つのリサーチセクションを設計してください：

{{
  "topic_analysis": "トピックの重要性と価値の分析（200字程度）",
  "target_audience": "想定読者とそのニーズ（100字程度）", 
  "research_sections": [
    {{
      "section_title": "セクション名",
      "description": "このセクションの目的と調査内容（100-150字）",
      "key_questions": ["調査すべき具体的な質問1", "質問2", "質問3"],
      "expected_insights": "期待される洞察・価値（50-80字）"
    }}
  ]
}}

## 品質基準：
- 各セクションは異なる視点・価値を提供する
- 実用的で actionable な情報取得を重視
- 最新性と具体性のバランスを考慮
- 専門性と一般理解性を両立"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            # JSON形式を明確に指定
            enhanced_prompt = f"""{system_prompt}

## 重要: 必ずJSON形式で出力してください
以下の厳密なJSON形式で回答してください：

{{
  "topic_analysis": "トピックの重要性と価値の分析",
  "target_audience": "想定読者とそのニーズ",
  "research_sections": [
    {{
      "section_title": "セクション名",
      "description": "このセクションの目的と調査内容",
      "key_questions": ["質問1", "質問2", "質問3"],
      "expected_insights": "期待される洞察・価値"
    }}
  ]
}}"""

            response = try_model_with_fallback(
                client=client,
                model=strategy_model,
                fallback_model=fallback_model,
                messages=[
                    {"role": "system", "content": enhanced_prompt},
                    {"role": "user", "content": f"以下のトピックについて、包括的で価値の高いリサーチ戦略を設計してください：\n\n{topic}"}
                ],
                max_completion_tokens=3000,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content.strip()
            print(f"Raw initial plan JSON: {content}")
            
            import json as json_lib
            plan = json_lib.loads(content)
            
            # 必要なフィールドの存在確認
            if not all(key in plan for key in ["topic_analysis", "target_audience"]):
                raise ValueError("Missing required fields in initial plan JSON")
            
            return plan
            
        except Exception as e:
            print(f"Initial strategy planning attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                print("All retry attempts for initial planning failed. Using minimal plan.")
                return {
                    "topic_analysis": f"{topic}について基本的な調査を実施します。",
                    "target_audience": "一般的な学習者・実践者",
                    "research_sections": []
                }
            print(f"Retrying initial planning... ({attempt + 1}/{max_retries})")


def generate_search_queries(client: OpenAI, topic: str, search_model: str, max_queries: int = 12, depth: str = "comprehensive") -> List[str]:
    """トピックから包括的な検索クエリを生成"""
    
    # 深度に応じて調査カテゴリを決定
    if depth == "basic":
        categories = ["基本情報", "実践方法", "事例"]
        queries_per_category = max_queries // 3
    elif depth == "detailed":
        categories = ["基本情報", "実践方法", "事例", "最新動向", "課題・注意点"]
        queries_per_category = max_queries // 5
    else:  # comprehensive
        categories = [
            "基本情報・定義", "実践的手法・戦略", "成功事例・ケーススタディ", 
            "最新動向・市場分析", "必要スキル・ツール", "収入・価格設定",
            "課題・リスク・注意点", "専門知識・テクニック"
        ]
        queries_per_category = max(1, max_queries // len(categories))
    
    system_prompt = f"""あなたは戦略的リサーチの専門家です。
与えられたトピックについて、以下のカテゴリごとに具体的で効果的な検索クエリを生成してください。

カテゴリ: {', '.join(categories)}

各カテゴリにつき{queries_per_category}個程度のクエリを生成し、全体で{max_queries}個以内にしてください。

要件:
1. 各クエリは具体的で実用的な情報が得られるものにする
2. 検索エンジンで効果的に検索できる自然な日本語にする
3. 異なる観点・深度でカバーする
4. 最新の情報や具体的な数値・事例が含まれるようなクエリにする
5. 実践者が本当に知りたい詳細な情報を取得できるようにする

出力形式:
各カテゴリの見出しなしで、検索クエリのみを1行ずつ出力してください。"""

    try:
        response = try_model_with_fallback(
            client=client,
            model=search_model,
            fallback_model=fallback_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"トピック: {topic}"}
            ],
            max_completion_tokens=800
        )
        
        queries_text = response.choices[0].message.content.strip()
        queries = [q.strip() for q in queries_text.split('\n') if q.strip()]
        
        # 最大数に制限
        return queries[:max_queries]
        
    except Exception as e:
        print(f"Search query generation failed: {e}")
        # フォールバック: 基本的なクエリを生成
        return [
            topic,
            f"{topic} とは",
            f"{topic} 最新情報"
        ][:max_queries]


def perform_section_research(client: OpenAI, section_info: Dict[str, Any], search_model: str) -> Dict[str, Any]:
    """リサーチプランの各セクションに対して専門的な調査を実行"""
    
    section_title = section_info["section_title"]
    description = section_info["description"]
    key_questions = section_info["key_questions"]
    
    # キーションを結合して包括的な検索クエリを作成
    combined_query = f"{section_title}: {description}\n調査項目: {', '.join(key_questions)}"
    
    system_prompt = f"""あなたは専門リサーチャーです。指定されたセクションについて、検索機能を使って極めて詳細で価値の高い調査を行ってください。

## セクション情報：
- **タイトル**: {section_title}
- **目的**: {description}
- **調査項目**: {', '.join(key_questions)}

## 調査要件：
1. **最新情報の重視**: 2024-2025年の最新データ・トレンドを優先
2. **データ収集**: 具体的な数値、統計、事例を豊富に含める
3. **専門性**: 業界の専門知識と実践的洞察を提供
4. **実用性**: 読者が実際に活用できる actionable な情報
5. **信頼性**: 信頼できるソースからの情報を重視

## 出力形式：
- セクションタイトルで始める
- サブセクションを適切に構造化
- 箇条書きや表を活用して読みやすく
- 重要な情報はボールド(**文字**)で強調
- 具体例や数値データを豊富に含める
- 3000-5000文字程度の詳細な内容

極めて価値の高い専門的な調査レポートを作成してください。"""

    try:
        response = try_model_with_fallback(
            client=client,
            model=search_model,
            fallback_model=fallback_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"以下について極めて詳細に調査してください:\n\n{combined_query}"}
            ],
            max_completion_tokens=8000
        )
        
        return {
            "section_title": section_title,
            "content": response.choices[0].message.content.strip(),
            "success": True,
            "model": search_model,
            "query_info": section_info
        }
        
    except Exception as e:
        print(f"Section research failed for '{section_title}': {e}")
        return {
            "section_title": section_title,
            "content": f"調査に失敗しました: {str(e)}",
            "success": False,
            "error": str(e),
            "query_info": section_info
        }


def perform_search_research(client: OpenAI, query: str, search_model: str) -> Dict[str, Any]:
    """検索機能付きモデルで調査を実行"""
    system_prompt = """あなたは専門的なリサーチャーです。与えられたクエリについて、検索機能を使って最新の情報を収集し、極めて詳細で包括的な調査結果を提供してください。

## 必須調査観点（全て詳細に調べること）:
1. **基本情報**: 定義、歴史、背景、概要
2. **詳細分析**: 仕組み、プロセス、技術的側面
3. **最新動向**: 2024年以降の最新情報、トレンド、変化
4. **具体例・事例**: 成功事例、失敗事例、ケーススタディ
5. **実践方法**: 具体的な手順、ツール、リソース
6. **数値・データ**: 統計、市場規模、収益、効果測定
7. **専門知識**: 上級者向け技術、プロフェッショナルな見解
8. **課題・リスク**: 問題点、注意事項、対処法
9. **将来展望**: 予測、展望、発展可能性
10. **関連情報**: 関連分野、競合、代替手段

## 調査要件:
- 必ず最新の検索結果を活用する
- 各観点で1000文字以上の詳細な説明を提供
- 具体的な数値、事例、引用を含める
- 専門用語は詳しく説明する
- 実践的で actionable な情報を重視する

極めて詳細で価値の高い調査結果を提供してください。"""

    try:
        response = try_model_with_fallback(
            client=client,
            model=search_model,
            fallback_model=fallback_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"以下について極めて詳細に調査してください（上記の10の観点全てを網羅し、実用的で最新の情報を提供してください）: {query}"}
            ],
            max_completion_tokens=8000
        )
        
        return {
            "query": query,
            "content": response.choices[0].message.content.strip(),
            "success": True,
            "model": search_model
        }
        
    except Exception as e:
        print(f"Search research failed for query '{query}': {e}")
        return {
            "query": query,
            "content": f"検索調査に失敗しました: {str(e)}",
            "success": False,
            "error": str(e)
        }


def add_section_to_report(client: OpenAI, topic: str, current_report: str, section_info: Dict[str, Any], section_content: str, report_model: str) -> str:
    """現在のレポートに新しいセクションを統合して追記"""
    
    system_prompt = f"""あなたは専門レポートライターです。既存のレポートに新しいセクションを論理的に統合し、より価値の高いレポートに発展させてください。

## タスク：
1. 新しいセクション内容を既存レポートに適切に統合
2. 論理的な構成と流れを維持
3. 重複を避け、相乗効果を生む内容配置
4. 専門性と読みやすさのバランス

## セクション情報：
- **タイトル**: {section_info.get('section_title', 'Unknown')}
- **目的**: {section_info.get('description', 'N/A')}
- **期待価値**: {section_info.get('expected_insights', 'N/A')}

## 出力要件：
- 既存のレポート構造を尊重
- 新しいセクションを最適な位置に配置
- セクション間の論理的なつながりを明確化
- マークダウン形式で美しく構造化
- 全体の一貫性と専門性を向上

既存レポートを発展させて、より包括的で価値の高い内容にしてください。"""

    try:
        response = try_model_with_fallback(
            client=client,
            model=report_model,
            fallback_model=fallback_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user", 
                    "content": f"既存レポート:\n\n{current_report}\n\n---\n\n新しいセクション ({section_info.get('section_title', 'Unknown')}):\n\n{section_content}\n\n---\n\n上記を統合して、'{topic}'についてのより包括的なレポートを作成してください。"
                }
            ],
            max_completion_tokens=20000
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Section integration failed: {e}")
        # フォールバック: 単純に追記
        return f"{current_report}\n\n---\n\n## {section_info.get('section_title', 'New Section')}\n\n{section_content}"


def initialize_report(client: OpenAI, topic: str, research_plan: Dict[str, Any], report_model: str) -> str:
    """初期レポート（トピック分析とイントロダクション）を生成"""
    
    topic_analysis = research_plan.get("topic_analysis", "")
    target_audience = research_plan.get("target_audience", "")
    
    system_prompt = f"""あなたは専門レポートライターです。トピック分析に基づいて、高品質なレポートの導入部分を作成してください。

## レポート要件：
1. **タイトルとエグゼクティブサマリー** (300-400字)
2. **トピック分析と背景** (200-300字)
3. **対象読者とレポートの価値** (150-200字)
4. **レポート構成の概要** (100-150字)

## 品質基準：
- 専門的かつ分かりやすい表現
- 読者の期待値を適切に設定
- 後続セクションへの自然な導入
- マークダウン形式で美しく構造化

段階的に発展する高品質レポートの基盤を作成してください。"""

    try:
        response = try_model_with_fallback(
            client=client,
            model=report_model,
            fallback_model=fallback_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user", 
                    "content": f"トピック: {topic}\n\n分析: {topic_analysis}\n\n対象読者: {target_audience}\n\n上記に基づいて、高品質レポートの導入部分を作成してください。"
                }
            ],
            max_completion_tokens=3000
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Report initialization failed: {e}")
        return f"# {topic}\n\n## 概要\n{topic_analysis}\n\n## 対象読者\n{target_audience}"


def generate_strategic_comprehensive_report(client: OpenAI, topic: str, research_plan: Dict[str, Any], section_results: List[Dict[str, Any]], report_model: str) -> str:
    """GPT-5-miniで戦略的で包括的なレポートを生成"""
    
    # 成功した調査結果のみを使用
    successful_results = [r for r in section_results if r.get("success", False)]
    
    if not successful_results:
        return f"# {topic}\n\n調査結果の取得に失敗しました。手動での情報収集が必要です。"
    
    # トピック分析情報を取得
    topic_analysis = research_plan.get("topic_analysis", "")
    target_audience = research_plan.get("target_audience", "")
    
    # セクション別の調査結果を構造化
    sections_content = "\n\n---\n\n".join([
        f"## {result['section_title']}\n\n{result['content']}"
        for result in successful_results
    ])
    
    system_prompt = f"""あなたは専門レポートライターです。以下のセクション別調査結果を統合して、極めて高品質で実用的な包括レポートを作成してください。

## トピック背景：
- **分析**: {topic_analysis}
- **読者**: {target_audience}

## レポート要件：
1. **エグゼクティブサマリー**: 重要ポイントの簡潔な要約（300-400字）
2. **目次**: 各セクションの概要
3. **詳細セクション**: 提供された各セクションを統合・最適化
4. **実践的な行動指針**: 具体的なネクストステップ（300-500字）
5. **まとめと将来展望**: 総括と今後の展望（200-300字）

## 品質基準：
- 情報の重複を避け、価値ある内容のみを統合
- 各セクション間の論理的なつながりを明確にする
- 読者が実際に活用できる actionable な情報を重視
- 専門性を保ちながら分かりやすい表現を使用
- マークダウン形式で美しく構造化
- 総文字数15,000-20,000文字の詳細レポート

極めて価値の高い、専門的で実用的なレポートを作成してください。"""

    try:
        response = try_model_with_fallback(
            client=client,
            model=report_model,
            fallback_model=fallback_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user", 
                    "content": f"以下のセクション別調査結果を統合して、'{topic}'についての最高品質の包括レポートを作成してください:\n\n{sections_content}"
                }
            ],
            max_completion_tokens=20000
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Strategic report generation failed: {e}")
        # フォールバック: セクション別結果をそのまま統合
        fallback_report = f"# {topic}\n\n"
        fallback_report += f"## 分析概要\n{topic_analysis}\n\n" if topic_analysis else ""
        fallback_report += f"## 対象読者\n{target_audience}\n\n" if target_audience else ""
        fallback_report += sections_content
        fallback_report += f"\n\n*注: 統合レポート生成中にエラーが発生: {str(e)}*"
        return fallback_report


def generate_comprehensive_report(client: OpenAI, topic: str, research_results: List[Dict[str, Any]], report_model: str) -> str:
    """複数の調査結果から包括的なレポートを生成"""
    
    # 成功した調査結果のみを使用
    successful_results = [r for r in research_results if r.get("success", False)]
    
    if not successful_results:
        return f"# {topic}\n\n調査結果の取得に失敗しました。手動での情報収集が必要です。"
    
    # 調査結果をテキストとして結合
    combined_research = "\n\n---\n\n".join([
        f"## 調査クエリ: {result['query']}\n\n{result['content']}"
        for result in successful_results
    ])
    
    system_prompt = """あなたは専門的なレポートライターです。複数の調査結果を統合して、極めて包括的で実用的なマークダウン形式のレポートを作成してください。

## 必須レポート構成（全セクション詳細化）:
1. **エグゼクティブサマリー** (重要ポイントの要約)
2. **基本情報と定義** (詳細な概要、歴史的背景)
3. **最新動向と市場分析** (2024年以降のトレンド、統計データ)
4. **詳細メソッドと技術解説** (具体的手法、プロセス、技術的側面)
5. **実践ガイド** (ステップバイステップの実行方法)
6. **成功事例とケーススタディ** (具体的な成功例、数値結果)
7. **必要なスキルとツール** (要求される能力、推奨ツール)
8. **収益性と価格設定** (収入の可能性、市場価格)
9. **課題とリスク管理** (問題点、対策、注意事項)
10. **専門知識と上級テクニック** (プロフェッショナル向け情報)
11. **将来展望と発展可能性** (予測、成長性)
12. **実践的リソースと次のステップ** (役立つリンク、行動計画)

## 品質要件:
- 各セクション500-800文字の詳細な説明
- 具体的な数値、データ、事例を豊富に含める
- 実践的で actionable な情報を優先
- 専門用語には丁寧な解説を付与
- 論理的で読みやすい構造
- 重複を避け、各セクションで異なる価値を提供
- 日本語で自然かつプロフェッショナルな文章
- 総文字数8000-12000文字の極めて詳細なレポート

従来の3倍以上の情報量と価値を持つ、専門性の高いレポートを作成してください。"""

    try:
        response = try_model_with_fallback(
            client=client,
            model=report_model,
            fallback_model=fallback_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user", 
                    "content": f"以下の調査結果を統合して、'{topic}'についての包括的なレポートを作成してください:\n\n{combined_research}"
                }
            ],
            max_completion_tokens=16000
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Report generation failed: {e}")
        # フォールバック: 調査結果をそのまま構造化
        fallback_report = f"# {topic}\n\n"
        fallback_report += "## 調査結果\n\n"
        fallback_report += combined_research
        fallback_report += f"\n\n*注: レポート統合中にエラーが発生しました: {str(e)}*"
        return fallback_report


def main() -> int:
    args = parse_args()
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Set the OPENAI_API_KEY environment variable first.", file=sys.stderr)
        return 1

    client = OpenAI(api_key=api_key)
    
    try:
        # 新しい記事ディレクトリを作成
        article_dir = next_article_dir(ARTICLES_ROOT)
        article_id = int(article_dir.name)
        
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] Starting strategic iterative research for: {args.query}")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] Article directory: {article_dir}")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 🧠 Using Iterative: GPT-5-mini strategy → GPT-4o-search → GPT-5-mini report → repeat")
        
        # 1. 初期戦略とレポート基盤を作成
        print(f"\n[{dt.datetime.now().strftime('%H:%M:%S')}] 🔍 Phase 1: Initial Research Planning & Report Foundation (GPT-5-mini)...")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 📡 OpenAI API REQUEST: GPT-5-mini で初期戦略プラン生成開始")
        
        initial_plan = analyze_topic_and_create_research_plan(client, args.query, args.strategy_model, max_sections=3)
        
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] ✅ 初期戦略プラン生成完了")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 📋 Initial Strategy Created:")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}]   Topic Analysis: {initial_plan.get('topic_analysis', 'N/A')[:100]}...")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}]   Target Audience: {initial_plan.get('target_audience', 'N/A')}")
        
        # レポート基盤を初期化
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 📡 OpenAI API REQUEST: GPT-5-mini でレポート基盤生成開始")
        current_report = initialize_report(client, args.query, initial_plan, args.report_model)
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] ✅ レポート基盤生成完了")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 📄 Report foundation created: {len(current_report)} characters")
        
        # 2. 段階的なセクション追加ループ
        print(f"\n[{dt.datetime.now().strftime('%H:%M:%S')}] 🔄 Phase 2: Iterative Section Development...")
        section_count = 0
        max_iterations = 10
        all_sections = []
        
        for iteration in range(1, max_iterations + 1):
            print(f"\n[{dt.datetime.now().strftime('%H:%M:%S')}] === Iteration {iteration} ===")
            
            # 2a. 次のセクション戦略を決定
            print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 🔍 Strategy: Determining next section...")
            print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 📡 OpenAI API REQUEST: GPT-5-mini でセクション戦略分析開始")
            strategy = get_next_section_strategy(client, args.query, current_report, args.strategy_model, args.fallback_model, section_count)
            
            if not strategy.get("should_continue", False):
                print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] ✅ Strategy decided to stop: {strategy.get('analysis', 'Complete')}")
                break
            
            next_section = strategy.get("next_section")
            if not next_section:
                print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] ❌ No valid next section provided")
                break
                
            section_title = next_section.get("section_title", f"Section {iteration}")
            print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] ✅ セクション戦略決定完了")
            print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 📋 Next section: {section_title}")
            print(f"[{dt.datetime.now().strftime('%H:%M:%S')}]    Priority: {next_section.get('priority', 'unknown')}")
            print(f"[{dt.datetime.now().strftime('%H:%M:%S')}]    Description: {next_section.get('description', 'N/A')[:100]}...")
            
            # 2b. セクションを調査
            print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 🔎 Research: {section_title}...")
            print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 📡 OpenAI API REQUEST: GPT-4o-search-preview で詳細調査開始")
            section_result = perform_section_research(client, next_section, args.search_model)
            
            if section_result["success"]:
                print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] ✅ Research success: {len(section_result['content'])} characters")
                
                # 2c. レポートに統合
                print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 📝 Integration: Adding to report...")
                print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 📡 OpenAI API REQUEST: GPT-5-mini でレポート統合開始")
                current_report = add_section_to_report(
                    client, args.query, current_report, next_section, 
                    section_result["content"], args.report_model
                )
                print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] ✅ Integration success: {len(current_report)} total characters")
                print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 📈 Progress: セクション {section_count + 1} 完了（累積 {len(current_report)} 文字）")
                
                section_count += 1
                all_sections.append({
                    "iteration": iteration,
                    "section_info": next_section,
                    "research_result": section_result,
                    "report_length": len(current_report)
                })
            else:
                print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] ❌ Research failed: {section_result.get('error', 'Unknown error')}")
                print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 🔄 Continuing to next iteration...")
                # 失敗した場合は続行
        
        final_report = current_report
        print(f"\n[{dt.datetime.now().strftime('%H:%M:%S')}] 🎉 Iterative research completed after {section_count} sections!")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 📊 Final report length: {len(final_report)} characters")
        
        # 4. material.mdに保存
        material_file = article_dir / "material.md"
        
        # メタデータを追加
        metadata = {
            "timestamp": dt.datetime.utcnow().isoformat() + "Z",
            "query": args.query,
            "strategy_model": args.strategy_model,
            "search_model": args.search_model,
            "report_model": args.report_model,
            "fallback_model": args.fallback_model,
            "initial_plan": initial_plan,
            "successful_sections": section_count,
            "total_iterations": len(all_sections),
            "section_details": all_sections,
            "architecture": "Iterative: GPT-5-mini strategy → GPT-4o-search → GPT-5-mini report → repeat"
        }
        
        full_content = f"""# {args.query}

## Research Metadata
- Timestamp: {metadata["timestamp"]}
- Architecture: {metadata["architecture"]}
- Strategy Model: {args.strategy_model}
- Search Model: {args.search_model}
- Report Model: {args.report_model}
- Successful Sections: {metadata["successful_sections"]}
- Total Iterations: {metadata["total_iterations"]}
- Method: Iterative strategic research

---

{final_report}

---

## Research Process
Iterative Development:
{chr(10).join([f"- Iteration {section['iteration']}: {section['section_info'].get('section_title', 'Unknown')} ({section['report_length']} chars total)" for section in all_sections])}

Research metadata:
```json
{json.dumps(metadata, ensure_ascii=False, indent=2)}
```
"""
        
        material_file.write_text(full_content, encoding="utf-8")
        
        print(f"\n[{dt.datetime.now().strftime('%H:%M:%S')}] ✅ Iterative Strategic Research completed successfully!")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 📁 Article ID: {article_id}")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 📝 Material saved: {material_file}")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 📊 Report length: {len(final_report)} characters")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 🔍 Successful sections: {metadata['successful_sections']}")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 🔄 Total iterations: {metadata['total_iterations']}")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 🧠 Architecture: {metadata['architecture']}")
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] 🎯 Process Summary:")
        for section in all_sections:
            print(f"[{dt.datetime.now().strftime('%H:%M:%S')}]   - Section {section['iteration']}: {section['section_info'].get('section_title', 'Unknown')} → {section['report_length']} chars")
        
        return 0
        
    except Exception as e:
        print(f"Research failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import sys
    raise SystemExit(main())