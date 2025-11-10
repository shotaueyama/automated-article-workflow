#!/usr/bin/env python3
"""Orchestrate the end-to-end article workflow described in workflow/auto_article_workflow.md."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

REPO_ROOT = Path(__file__).resolve().parent
LOG_DIR = REPO_ROOT / "logs" / "workflow_runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the automated article workflow.")
    parser.add_argument(
        "--theme",
        required=True,
        help="Research topic passed to deep_research_collect.py.",
    )
    parser.add_argument(
        "--effort",
        default="medium",
        choices=("medium",),
        help="Reasoning effort for DeepResearch (currently only medium is supported).",
    )
    parser.add_argument(
        "--status",
        default="draft",
        choices=("draft", "publish"),
        help="WordPress post status.",
    )
    parser.add_argument(
        "--category-name",
        default="ブログ",
        help="Child category name for WordPress upload.",
    )
    parser.add_argument(
        "--parent-category",
        default="QUON COLLEGE",
        help="Parent category name for WordPress upload.",
    )
    parser.add_argument(
        "--resume-from-material",
        type=int,
        metavar="ARTICLE_ID",
        help="Resume workflow from article generation using existing material.md in the specified article ID folder.",
    )
    parser.add_argument(
        "--resume-from-images",
        type=int,
        metavar="ARTICLE_ID",
        help="Resume workflow from image generation using existing article.md in the specified article ID folder.",
    )
    return parser.parse_args()


def list_article_ids() -> List[int]:
    articles_dir = REPO_ROOT / "articles"
    if not articles_dir.exists():
        return []
    ids = []
    for entry in articles_dir.iterdir():
        if entry.is_dir() and entry.name.isdigit():
            ids.append(int(entry.name))
    return sorted(ids)


def run_command(cmd: List[str], cwd: Path) -> Tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    return proc.returncode, proc.stdout, proc.stderr


def ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def write_log(log: Dict) -> None:
    ensure_log_dir()
    run_id = log["run_id"]
    path = LOG_DIR / f"{run_id}.json"
    path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = LOG_DIR / "latest.json"
    latest.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def log_step(log: Dict, name: str, status: str, detail: str = "", error: str | None = None) -> None:
    log.setdefault("steps", []).append(
        {
            "name": name,
            "status": status,
            "detail": detail,
            "error": error,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )
    write_log(log)


def fail_and_exit(log: Dict, name: str, detail: str, error: str) -> None:
    log_step(log, name, "failure", detail, error)
    print(f"[ERROR] {name}: {error}", file=sys.stderr)
    raise SystemExit(1)


def print_status(message: str, step: str = "INFO") -> None:
    """詳細なステータス情報を標準出力に出力"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {step}: {message}", file=sys.stdout, flush=True)


def print_api_log(action: str, details: str) -> None:
    """OpenAI API関連のログを出力"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] OpenAI API {action}: {details}", file=sys.stdout, flush=True)


def generate_image_prompt(heading: str, previous_prompts: List[str] = None) -> str:
    """見出しから画像プロンプトを生成し、重複をチェックする"""
    if OpenAI is None:
        return generate_fallback_prompt(heading)
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return generate_fallback_prompt(heading)
    
    client = OpenAI(api_key=api_key)
    previous_prompts = previous_prompts or []
    
    # プロンプト生成
    system_prompt = (
        "You are an expert at creating diverse, professional image prompts for DALL-E 3 in cute 3D animation style. "
        "Create unique, visually distinct prompts that avoid repetition. "
        "Each prompt should be in English, featuring: "
        "- Simple, minimalist 3D scenes with few objects "
        "- 3D rendered characters with rounded, cute features and large expressive eyes "
        "- Clean, uncluttered compositions with plenty of white space "
        "- Soft, bouncy textures and smooth plastic-like surfaces "
        "- Bright, saturated colors with warm ambient lighting "
        "- Cartoon-style proportions but professional business context "
        "- Cheerful, friendly atmosphere similar to animated movies "
        "- 16:9 aspect ratio, no text overlay "
        "Focus on simplicity and clarity with minimal objects per scene."
    )
    
    user_prompt = f"Create a unique image prompt for the heading: '{heading}'. Keep it simple and minimalist with few objects. Include keywords like 'cute 3D characters', 'clean composition', 'minimal objects', 'plenty of white space', 'simple background' to achieve a clean, uncluttered look."
    
    if previous_prompts:
        user_prompt += f"\n\nAvoid similarity to these previous prompts:\n{chr(10).join(previous_prompts)}"
        user_prompt += "\n\nMake sure the new prompt has different: composition, color scheme, lighting, objects, and overall visual style."
    
    try:
        print_api_log("REQUEST", f"プロンプト生成: {heading[:30]}...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_completion_tokens=200
        )
        
        generated_prompt = response.choices[0].message.content.strip()
        print_api_log("SUCCESS", f"プロンプト生成完了: {generated_prompt[:50]}...")
        
        # 重複チェック
        if previous_prompts and is_prompt_similar(generated_prompt, previous_prompts, client):
            print_api_log("WARNING", "プロンプト重複検出、再生成中...")
            # 再生成
            retry_prompt = user_prompt + "\n\nThe previous attempt was too similar. Create something completely different with unique visual elements."
            retry_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": retry_prompt}
                ],
                max_completion_tokens=200
            )
            generated_prompt = retry_response.choices[0].message.content.strip()
            print_api_log("SUCCESS", f"再生成プロンプト: {generated_prompt[:50]}...")
        
        return generated_prompt
        
    except Exception as e:
        print_api_log("FAILED", f"プロンプト生成エラー: {str(e)}")
        return generate_fallback_prompt(heading)


def is_prompt_similar(new_prompt: str, previous_prompts: List[str], client: OpenAI) -> bool:
    """プロンプトの類似性をチェック"""
    if not previous_prompts:
        return False
    
    try:
        comparison_prompt = (
            f"Compare this new image prompt with the previous ones and determine if they are too similar:\n\n"
            f"New prompt: {new_prompt}\n\n"
            f"Previous prompts:\n{chr(10).join(previous_prompts)}\n\n"
            f"Answer with 'YES' if they are too similar (same objects, composition, or visual style), "
            f"or 'NO' if they are sufficiently different. Only respond with YES or NO."
        )
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": comparison_prompt}
            ],
            max_completion_tokens=10
        )
        
        result = response.choices[0].message.content.strip().upper()
        return result == "YES"
        
    except Exception:
        return False


def generate_fallback_prompt(heading: str) -> str:
    """フォールバック用のプロンプト生成（シンプル可愛い3Dアニメーションスタイル）"""
    base_style = ", simple minimalist cute 3D rendered animation style, few objects, clean composition, rounded characters, large expressive eyes, soft textures, bright colors, warm lighting, plenty of white space, no text overlay"
    
    if "AI" in heading or "人工知能" in heading:
        return f"Simple AI workspace with one computer and a friendly robot character{base_style}"
    elif "フリーランス" in heading or "働き方" in heading:
        return f"Clean home office with one laptop and a cute character working{base_style}"
    elif "自動化" in heading or "効率" in heading:
        return f"Simple automation scene with gears and one friendly robot{base_style}"
    elif "収益" in heading or "収入" in heading or "稼" in heading:
        return f"Clean business growth scene with simple chart and happy character{base_style}"
    elif "ツール" in heading or "アプリ" in heading:
        return f"Minimalist workspace with one screen showing simple app interface{base_style}"
    elif "学習" in heading or "スキル" in heading:
        return f"Simple learning scene with book, laptop and cute student character{base_style}"
    elif "マーケティング" in heading:
        return f"Clean marketing workspace with simple analytics chart{base_style}"
    elif "クライアント" in heading or "顧客" in heading:
        return f"Simple meeting scene with two friendly characters shaking hands{base_style}"
    elif "時間" in heading or "管理" in heading:
        return f"Minimalist time management with one clock and organized desk{base_style}"
    else:
        return f"Simple business scene with friendly character and minimal objects{base_style}"


def step_deep_research(args: argparse.Namespace, log: Dict) -> int:
    print_status("🔍 STEP 1: ディープリサーチを開始", "RESEARCH")
    print_status(f"📚 テーマ調査中: {args.theme}")
    
    before_ids = set(list_article_ids())
    cmd = [
        sys.executable,
        "tools/deep_research_collect.py",
        args.theme,
        "--effort",
        args.effort,
    ]
    
    print_api_log("REQUEST", "OpenAI o4-mini-deep-researchでリサーチ処理を開始")
    code, stdout, stderr = run_command(cmd, REPO_ROOT)
    detail = stdout.strip()
    
    if code != 0:
        print_api_log("FAILED", f"リサーチ処理エラー: {stderr.strip()}")
        fail_and_exit(log, "deep_research", detail, stderr.strip() or "Deep research failed.")
        
    after_ids = set(list_article_ids())
    new_ids = sorted(after_ids - before_ids)
    if not new_ids:
        print_status("❌ 新規記事が作成されませんでした", "ERROR")
        fail_and_exit(log, "deep_research", detail, "No new article directory was created.")
        
    article_id = new_ids[-1]
    log["article_id"] = article_id
    print_api_log("SUCCESS", f"リサーチ完了 - 記事ID: {article_id}")
    print_status(f"✅ STEP 1完了: 記事ID {article_id} でマテリアル作成", "RESEARCH")
    log_step(log, "deep_research", "success", f"articles/{article_id}/material.md")
    return article_id


def step_generate_article(article_id: int, log: Dict) -> None:
    print_status("✍️ STEP 2: HTML記事生成・レビューを開始", "GENERATE")
    print_status(f"📄 記事ID {article_id} のHTML記事を直接生成中（GPT-5 mini レビュー付き）")
    
    material_path = REPO_ROOT / "articles" / str(article_id) / "material.md"
    output_path = REPO_ROOT / "articles" / str(article_id) / "article.html"
    cmd = [
        sys.executable,
        "tools/generate_html_from_material.py",
        "--material",
        str(material_path),
        "--output",
        str(output_path),
    ]
    
    print_api_log("REQUEST", "OpenAI GPT-5 miniでHTML記事生成処理を開始")
    code, stdout, stderr = run_command(cmd, REPO_ROOT)
    
    if code != 0:
        print_api_log("FAILED", f"HTML記事生成エラー: {stderr.strip()}")
        fail_and_exit(
            log,
            "generate_article",
            stdout.strip(),
            stderr.strip() or "HTML article generation failed.",
        )
    
    print_api_log("SUCCESS", f"HTML記事生成・レビュー完了 - 出力: {output_path.name}")
    print_status(f"✅ STEP 2完了: HTML記事を {output_path.name} に生成（レビュー済み）", "GENERATE")
    log_step(log, "generate_article", "success", str(output_path.relative_to(REPO_ROOT)))


def extract_headings(article_path: Path) -> List[str]:
    headings: List[str] = []
    content = article_path.read_text(encoding="utf-8")
    
    # HTMLファイルの場合はHTMLタグから見出しを抽出
    if article_path.suffix == ".html":
        import re
        h2_matches = re.findall(r'<h2>(.*?)</h2>', content)
        for heading in h2_matches:
            headings.append(f"## {heading}")
    else:
        # Markdownファイルの場合は従来の方法
        for line in content.splitlines():
            line = line.rstrip()
            if line.startswith("## "):
                headings.append(line.strip())
    
    return headings


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "section"


def insert_image_html(article_path: Path, heading: str, relative_path: str) -> None:
    content = article_path.read_text(encoding="utf-8")
    
    if article_path.suffix == ".html":
        # HTMLファイルの場合
        import re
        # 見出しタグを探してその後に画像タグを挿入
        pattern = f'<h2>{re.escape(heading.replace("## ", ""))}</h2>'
        if re.search(pattern, content):
            # 既に画像が挿入されているかチェック
            next_image_pattern = f'{pattern}\\s*<img[^>]*src="{re.escape(relative_path)}"'
            if not re.search(next_image_pattern, content):
                alt_text = f"{heading.replace('## ', '')}のイメージ"
                image_tag = f'<img src="{relative_path}" alt="{alt_text}" />'
                replacement = f'<h2>{heading.replace("## ", "")}</h2>\n{image_tag}'
                content = re.sub(pattern, replacement, content, count=1)
                article_path.write_text(content, encoding="utf-8")
    else:
        # Markdownファイルの場合（従来の方法）
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            if line.strip() == heading.strip():
                insert_idx = idx + 1
                while insert_idx < len(lines) and lines[insert_idx].strip() == "":
                    insert_idx += 1
                if insert_idx < len(lines) and lines[insert_idx].lstrip().startswith("!"):
                    return
                snippet = [
                    "",
                    f"![{heading}のイメージ]({relative_path})",
                    "",
                ]
                lines[idx + 1 : idx + 1] = snippet
                article_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return


def step_generate_images(article_id: int, log: Dict) -> None:
    print_status("🎨 STEP 3: 画像生成を開始", "IMAGES")
    print_status(f"🖼️ 記事ID {article_id} の画像を生成中")
    
    # HTMLファイルを優先的に使用
    article_path = REPO_ROOT / "articles" / str(article_id) / "article.html"
    if not article_path.exists():
        # HTMLファイルが存在しない場合はMarkdownファイルを使用
        article_path = REPO_ROOT / "articles" / str(article_id) / "article.md"
        if not article_path.exists():
            fail_and_exit(log, "generate_images", "", f"Neither article.html nor article.md found for article {article_id}.")

    headings = extract_headings(article_path)
    if not headings:
        print_status("ℹ️ 見出しが見つかりませんでした。画像生成をスキップ", "IMAGES")
        log_step(log, "generate_images", "success", "No headings found for image generation.")
        return

    print_status(f"📝 {len(headings)}個の見出しに対して画像を生成します")
    created_files: List[str] = []
    generated_prompts: List[str] = []  # 生成済みプロンプトを記録

    images_dir = article_path.parent / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # 既存の画像数をチェック
    existing_images = list(images_dir.glob("*.png"))
    print_status(f"📁 既存画像: {len(existing_images)}個, 必要: {len(headings)}個")

    for i, heading in enumerate(headings, 1):
        # 既存の画像が十分にある場合はスキップ
        if len(existing_images) >= i:
            print_status(f"⏭️  画像 {i}/{len(headings)}: {heading[:30]}... (既存画像使用)")
            continue
            
        slug = slugify(heading)
        filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{slug}"
        image_path = images_dir / f"{filename}.png"
        
        # AIを使って多様なプロンプトを生成（重複チェック付き）
        prompt = generate_image_prompt(heading, generated_prompts)
        generated_prompts.append(prompt)
        
        print_status(f"🎨 画像 {i}/{len(headings)}: {heading[:30]}...")
        print_status(f"📝 プロンプト: {prompt[:60]}...")
        
        cmd = [
            sys.executable,
            "tools/generate_image.py",
            prompt,
            "--output-dir",
            str(image_path.parent.relative_to(REPO_ROOT)),
            "--filename",
            filename,
            "--retry-attempts",
            "3",
        ]
        
        print_api_log("REQUEST", f"DALL-E 3で画像生成: {heading[:20]}...")
        code, stdout, stderr = run_command(cmd, REPO_ROOT)
        
        if code != 0 or not image_path.exists():
            print_api_log("FAILED", f"画像生成エラー: {stderr.strip()}")
            fail_and_exit(
                log,
                "generate_images",
                stdout.strip(),
                stderr.strip() or f"Image generation failed for heading: {heading}",
            )
            
        print_api_log("SUCCESS", f"画像生成完了: {filename}.png")
        relative_path = Path("images") / image_path.name
        insert_image_html(article_path, heading, str(relative_path))
        created_files.append(str(image_path.relative_to(REPO_ROOT)))

    print_status(f"✅ STEP 3完了: {len(created_files)}個の画像を生成", "IMAGES")
    detail = "\n".join(created_files)
    log_step(log, "generate_images", "success", detail or "Images already existed.")




def step_upload(article_id: int, args: argparse.Namespace, log: Dict) -> None:
    print_status("🌐 STEP 4: WordPressアップロードを開始", "UPLOAD")
    print_status(f"📤 記事ID {article_id} をWordPressに投稿中")
    
    # HTMLファイルを優先的に使用
    html_path = REPO_ROOT / "articles" / str(article_id) / "article.html"
    if html_path.exists():
        print_status(f"📋 HTMLファイルを使用: {html_path.name}")
        cmd = [
            sys.executable,
            "tools/upload_to_wordpress.py",
            "--html",
            str(html_path),
            "--status",
            args.status,
            "--category-name",
            args.category_name,
            "--parent-category",
            args.parent_category,
        ]
    else:
        # HTMLファイルが存在しない場合はMarkdownファイルを使用
        article_path = REPO_ROOT / "articles" / str(article_id) / "article.md"
        if not article_path.exists():
            fail_and_exit(log, "upload_wordpress", "", f"Neither article.html nor article.md found for article {article_id}.")
        
        print_status(f"📋 Markdownファイルを使用: {article_path.name}")
        cmd = [
            sys.executable,
            "tools/upload_to_wordpress.py",
            "--markdown",
            str(article_path),
            "--status",
            args.status,
            "--category-name",
            args.category_name,
            "--parent-category",
            args.parent_category,
        ]
        
    print_status(f"📋 設定: status={args.status}, category={args.category_name}")
    
    print_api_log("REQUEST", f"WordPress APIで投稿開始 (status: {args.status})")
    code, stdout, stderr = run_command(cmd, REPO_ROOT)
    
    if code != 0:
        print_api_log("FAILED", f"WordPressアップロードエラー: {stderr.strip()}")
        fail_and_exit(
            log,
            "upload_wordpress",
            stdout.strip(),
            stderr.strip() or "WordPress upload failed.",
        )
    
    print_api_log("SUCCESS", f"WordPress投稿完了")
    print_status("✅ STEP 4完了: WordPressに正常に投稿されました", "UPLOAD")
    log_step(log, "upload_wordpress", "success", stdout.strip())


def main() -> None:
    args = parse_args()
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    
    # 画像生成からの再開モード
    if args.resume_from_images:
        article_id = args.resume_from_images
        
        # HTMLファイルを優先的にチェック
        html_path = REPO_ROOT / "articles" / str(article_id) / "article.html"
        md_path = REPO_ROOT / "articles" / str(article_id) / "article.md"
        
        if html_path.exists():
            article_path = html_path
        elif md_path.exists():
            article_path = md_path
        else:
            raise SystemExit(f"Neither article.html nor article.md found for article {article_id}")
        
        log: Dict = {
            "run_id": run_id,
            "theme": args.theme,
            "article_id": article_id,
            "steps": [],
            "resume_mode": "images",
        }
        write_log(log)
        
        print_status(f"🎨 ワークフロー再開: Run ID {run_id}", "RESUME")
        print_status(f"📄 記事ID {article_id} から画像生成を再開")
        print_status(f"📝 テーマ: {args.theme}")
        print_status(f"⚙️  設定: effort={args.effort}, status={args.status}, category={args.category_name}")
        
        # 既存のarticle.mdから画像生成を開始
        step_generate_images(article_id, log)
        step_upload(article_id, args, log)
        
        print_status(f"✅ 画像生成ワークフロー完了: 記事ID {article_id}", "RESUME")
        print(f"Image generation workflow completed for article {article_id}. Log: {LOG_DIR / (run_id + '.json')}")
        
    # 再開モードの場合
    elif args.resume_from_material:
        article_id = args.resume_from_material
        material_path = REPO_ROOT / "articles" / str(article_id) / "material.md"
        
        if not material_path.exists():
            raise SystemExit(f"Material file not found: {material_path}")
        
        log: Dict = {
            "run_id": run_id,
            "theme": args.theme,
            "article_id": article_id,
            "steps": [],
            "resume_mode": True,
        }
        write_log(log)
        
        print_status(f"🔄 ワークフロー再開: Run ID {run_id}", "RESUME")
        print_status(f"📁 記事ID {article_id} から記事生成を再開")
        print_status(f"📝 テーマ: {args.theme}")
        print_status(f"⚙️  設定: effort={args.effort}, status={args.status}, category={args.category_name}")
        
        # 既存のmaterial.mdから記事生成を開始
        step_generate_article(article_id, log)
        step_generate_images(article_id, log)
        step_upload(article_id, args, log)
        
        print_status(f"✅ 再開ワークフロー完了: 記事ID {article_id}", "RESUME")
        print(f"Resume workflow completed for article {article_id}. Log: {LOG_DIR / (run_id + '.json')}")
        
    else:
        # 通常モード
        log: Dict = {
            "run_id": run_id,
            "theme": args.theme,
            "article_id": None,
            "steps": [],
        }
        write_log(log)
        
        print_status(f"🚀 ワークフロー開始: Run ID {run_id}", "START")
        print_status(f"📝 テーマ: {args.theme}")
        print_status(f"⚙️  設定: effort={args.effort}, status={args.status}, category={args.category_name}")

        article_id = step_deep_research(args, log)
        step_generate_article(article_id, log)
        step_generate_images(article_id, log)
        step_upload(article_id, args, log)

        print_status(f"✅ ワークフロー完了: 記事ID {article_id}", "COMPLETE")
        print(f"Workflow completed for article {article_id}. Log: {LOG_DIR / (run_id + '.json')}")


if __name__ == "__main__":
    main()
