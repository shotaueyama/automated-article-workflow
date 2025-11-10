#!/usr/bin/env python3
"""HTTP API to trigger and monitor run_workflow.py executions."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

try:
    from openai import OpenAI, OpenAIError
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore
    OpenAIError = Exception  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent
LOG_ROOT = REPO_ROOT / "logs"
RUNS: Dict[str, Dict] = {}
PROCESSES: Dict[str, asyncio.subprocess.Process] = {}
app = FastAPI(title="GENDOCS Workflow API", version="1.1.0")


def setup_logging() -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    log_file = LOG_ROOT / "workflow_server.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


setup_logging()
logger = logging.getLogger(__name__)


class WorkflowRequest(BaseModel):
    theme: str = Field(..., description="Research theme passed to deep_research_collect.py.")
    effort: str = Field("medium", description="Reasoning effort (currently medium only).")
    status: str = Field("draft", description="WordPress post status.")
    category_name: str = Field("ブログ", description="Child category name.")
    parent_category: str = Field("QUON COLLEGE", description="Parent category name.")


class RunResponse(BaseModel):
    run_id: str
    status: str


def get_openai_client() -> OpenAI:
    if OpenAI is None:
        raise HTTPException(status_code=500, detail="openai package not installed.")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set.")
    return OpenAI(api_key=api_key)



async def _stream_reader(stream: asyncio.StreamReader, run_id: str, prefix: str) -> None:
    while True:
        line = await stream.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="ignore").rstrip()
        RUNS[run_id]["logs"].append(f"{prefix}: {text}")


async def _run_workflow_subprocess(run_id: str, req: WorkflowRequest) -> None:
    logger.info("Starting workflow run %s with theme: %s", run_id, req.theme)
    RUNS[run_id] = {
        "status": "running",
        "started_at": datetime.utcnow().isoformat() + "Z",
        "logs": [],
        "request": req.dict(),
    }
    cmd = [
        sys.executable,
        "run_workflow.py",
        "--theme",
        req.theme,
        "--effort",
        req.effort,
        "--status",
        req.status,
        "--category-name",
        req.category_name,
        "--parent-category",
        req.parent_category,
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )

    # プロセス参照を保存
    PROCESSES[run_id] = process

    stdout_task = asyncio.create_task(_stream_reader(process.stdout, run_id, "stdout"))
    stderr_task = asyncio.create_task(_stream_reader(process.stderr, run_id, "stderr"))
    await process.wait()
    await stdout_task
    await stderr_task

    # プロセス参照を削除
    if run_id in PROCESSES:
        del PROCESSES[run_id]

    RUNS[run_id]["finished_at"] = datetime.utcnow().isoformat() + "Z"
    if process.returncode == 0:
        RUNS[run_id]["status"] = "success"
        logger.info("Workflow run %s finished successfully.", run_id)
    else:
        RUNS[run_id]["status"] = "failure"
        logger.error("Workflow run %s failed. See logs for details.", run_id)


async def _resume_workflow_from_images(run_id: str, req: WorkflowRequest, article_id: int) -> None:
    """article.mdから画像生成を再開する専用関数"""
    logger.info("Resuming workflow run %s from images for article %s", run_id, article_id)
    RUNS[run_id] = {
        "status": "running",
        "started_at": datetime.utcnow().isoformat() + "Z",
        "logs": [],
        "request": req.dict(),
        "article_id": article_id,
    }
    
    # 画像生成から開始するための専用スクリプト実行
    cmd = [
        sys.executable,
        "run_workflow.py",
        "--theme", 
        req.theme,
        "--effort",
        req.effort,
        "--status",
        req.status,
        "--category-name", 
        req.category_name,
        "--parent-category",
        req.parent_category,
        "--resume-from-images",  # 画像生成から再開フラグ
        str(article_id),  # 記事ID
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )

    # プロセス参照を保存
    PROCESSES[run_id] = process

    stdout_task = asyncio.create_task(_stream_reader(process.stdout, run_id, "stdout"))
    stderr_task = asyncio.create_task(_stream_reader(process.stderr, run_id, "stderr"))
    await process.wait()
    await stdout_task
    await stderr_task

    # プロセス参照を削除
    if run_id in PROCESSES:
        del PROCESSES[run_id]

    RUNS[run_id]["finished_at"] = datetime.utcnow().isoformat() + "Z"
    if process.returncode == 0:
        RUNS[run_id]["status"] = "success"
        logger.info("Resume workflow from images run %s finished successfully.", run_id)
    else:
        RUNS[run_id]["status"] = "failure"
        logger.error("Resume workflow from images run %s failed. See logs for details.", run_id)


async def _resume_workflow_from_material(run_id: str, req: WorkflowRequest, article_id: int) -> None:
    """material.mdから記事生成を再開する専用関数"""
    logger.info("Resuming workflow run %s from material for article %s", run_id, article_id)
    RUNS[run_id] = {
        "status": "running",
        "started_at": datetime.utcnow().isoformat() + "Z",
        "logs": [],
        "request": req.dict(),
        "article_id": article_id,
    }
    
    # 記事生成から開始するための専用スクリプト実行
    cmd = [
        sys.executable,
        "run_workflow.py",
        "--theme", 
        req.theme,
        "--effort",
        req.effort,
        "--status",
        req.status,
        "--category-name", 
        req.category_name,
        "--parent-category",
        req.parent_category,
        "--resume-from-material",  # 再開フラグ
        str(article_id),  # 記事ID
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )

    # プロセス参照を保存
    PROCESSES[run_id] = process

    stdout_task = asyncio.create_task(_stream_reader(process.stdout, run_id, "stdout"))
    stderr_task = asyncio.create_task(_stream_reader(process.stderr, run_id, "stderr"))
    await process.wait()
    await stdout_task
    await stderr_task

    # プロセス参照を削除
    if run_id in PROCESSES:
        del PROCESSES[run_id]

    RUNS[run_id]["finished_at"] = datetime.utcnow().isoformat() + "Z"
    if process.returncode == 0:
        RUNS[run_id]["status"] = "success"
        logger.info("Resume workflow run %s finished successfully.", run_id)
    else:
        RUNS[run_id]["status"] = "failure"
        logger.error("Resume workflow run %s failed. See logs for details.", run_id)


@app.post("/workflow/run", response_model=RunResponse)
async def trigger_workflow(req: WorkflowRequest):
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    asyncio.create_task(_run_workflow_subprocess(run_id, req))
    return RunResponse(run_id=run_id, status="running")


@app.get("/workflow/runs")
async def list_runs():
    return [
        {"run_id": run_id, **info}
        for run_id, info in sorted(RUNS.items(), key=lambda item: item[1]["started_at"], reverse=True)
    ]


@app.get("/workflow/runs/{run_id}")
async def get_run(run_id: str):
    info = RUNS.get(run_id)
    if not info:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, **info}


@app.post("/workflow/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    """実行中のワークフローをキャンセル"""
    info = RUNS.get(run_id)
    if not info:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if info.get("status") != "running":
        raise HTTPException(status_code=400, detail="Run is not running")
    
    # プロセスが存在する場合は強制終了
    process = PROCESSES.get(run_id)
    if process:
        try:
            process.terminate()
            # 数秒待ってもまだ生きている場合は強制kill
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
            
            # プロセス参照を削除
            if run_id in PROCESSES:
                del PROCESSES[run_id]
            
            # ステータスを更新
            RUNS[run_id]["status"] = "cancelled"
            RUNS[run_id]["finished_at"] = datetime.utcnow().isoformat() + "Z"
            RUNS[run_id]["logs"].append("stdout: [CANCELLED] Workflow was cancelled by user")
            
            logger.info("Workflow run %s was cancelled", run_id)
            return {"run_id": run_id, "status": "cancelled"}
            
        except Exception as e:
            logger.error("Failed to cancel workflow run %s: %s", run_id, e)
            raise HTTPException(status_code=500, detail=f"Failed to cancel run: {e}")
    else:
        # プロセス参照がない場合でもステータスを更新
        RUNS[run_id]["status"] = "cancelled"
        RUNS[run_id]["finished_at"] = datetime.utcnow().isoformat() + "Z"
        RUNS[run_id]["logs"].append("stdout: [CANCELLED] Workflow was cancelled (no process found)")
        return {"run_id": run_id, "status": "cancelled"}


@app.post("/workflow/runs/{run_id}/analysis")
async def analyze_run(run_id: str):
    info = RUNS.get(run_id)
    if not info:
        raise HTTPException(status_code=404, detail="Run not found")
    logs_text = "\n".join(info.get("logs", [])) or "ログは記録されていません。"
    summary = json.dumps(
        {
            "run_id": run_id,
            "status": info.get("status"),
            "request": info.get("request"),
            "steps": info.get("steps"),
        },
        ensure_ascii=False,
        indent=2,
    )
    prompt = (
        "以下は自動記事生成ワークフローの実行ログです。問題点や改善策を日本語で簡潔にまとめ、"
        "必要があれば再実行手順も提案してください。\n\n"
        f"=== 実行サマリ ===\n{summary}\n\n=== 生ログ ===\n{logs_text}"
    )
    client = get_openai_client()
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "あなたはワークフロー監視のSREです。原因分析と再発防止策を簡潔に述べます。",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                max_completion_tokens=1000,
            ),
        )
    except OpenAIError as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {exc}")
    analysis = response.choices[0].message.content or "分析結果を取得できませんでした。"
    return {"run_id": run_id, "analysis": analysis}


@app.get("/articles")
async def list_articles():
    """全記事の状態を統合した一覧を取得（テーブル表示用）"""
    articles_root = REPO_ROOT / "articles"
    if not articles_root.exists():
        return []
    
    articles = []
    for folder in articles_root.iterdir():
        if not folder.is_dir() or not folder.name.isdigit():
            continue
            
        article_id = int(folder.name)
        material_path = folder / "material.md"
        html_path = folder / "article.html"
        md_path = folder / "article.md"
        images_dir = folder / "images"
        
        # ファイル存在確認
        has_material = material_path.exists()
        has_html = html_path.exists()
        has_md = md_path.exists()
        has_images = images_dir.exists() and len(list(images_dir.glob("*.png"))) > 0
        
        # タイトル抽出
        title = None
        try:
            if has_html:
                # HTMLファイルからタイトル抽出
                import re
                content = html_path.read_text(encoding="utf-8")
                h1_match = re.search(r'<h1>(.*?)</h1>', content)
                if h1_match:
                    title = h1_match.group(1).strip()
            elif has_md:
                # Markdownファイルからタイトル抽出
                content = md_path.read_text(encoding="utf-8")
                lines = content.split('\n')
                for line in lines:
                    if line.startswith('# '):
                        title = line[2:].strip()
                        break
            elif has_material:
                # material.mdから推測（先頭行を使用）
                content = material_path.read_text(encoding="utf-8")
                lines = content.split('\n')
                for line in lines:
                    if line.strip() and not line.startswith('#'):
                        title = line.strip()[:50] + "..." if len(line.strip()) > 50 else line.strip()
                        break
        except Exception:
            pass
        
        # 日付取得（最初に見つかったファイルの作成日時）
        date_created = None
        try:
            for path in [html_path, md_path, material_path]:
                if path.exists():
                    import datetime
                    date_created = datetime.datetime.fromtimestamp(path.stat().st_ctime).strftime("%Y-%m-%d %H:%M")
                    break
        except Exception:
            pass
        
        articles.append({
            "article_id": article_id,
            "title": title or f"記事 {article_id}",
            "has_material": has_material,
            "has_html": has_html,
            "has_md": has_md,
            "has_images": has_images,
            "date_created": date_created
        })
    
    # article_id順にソート（降順）
    articles.sort(key=lambda x: x["article_id"], reverse=True)
    return articles


@app.post("/workflow/resume-images")
async def resume_workflow_from_images(request: dict):
    """article.html（優先）またはarticle.mdから画像生成を再開"""
    article_id = request.get("article_id")
    if not article_id:
        raise HTTPException(status_code=400, detail="article_id is required")
    
    article_folder = REPO_ROOT / "articles" / str(article_id)
    
    # HTMLファイルを優先的にチェック
    html_path = article_folder / "article.html"
    md_path = article_folder / "article.md"
    
    article_path = None
    if html_path.exists():
        article_path = html_path
    elif md_path.exists():
        article_path = md_path
    
    if not article_path:
        raise HTTPException(status_code=404, detail=f"Neither article.html nor article.md found in article {article_id}")
    
    # 新しいrun_idを生成
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    
    # article.mdの内容からタイトルを抽出
    try:
        article_content = article_path.read_text(encoding="utf-8")
        lines = article_content.split('\n')
        title = f"記事 {article_id} の画像生成"
        for line in lines:
            if line.startswith('# '):
                title = line[2:].strip()
                break
            elif line.startswith('## '):
                title = line[3:].strip()
                break
    except Exception:
        title = f"記事 {article_id} の画像生成"
    
    # ワークフローを画像生成ステップから開始
    workflow_request = WorkflowRequest(
        theme=title,
        effort="medium",
        status="draft", 
        category_name="ブログ",
        parent_category="QUON COLLEGE"
    )
    
    asyncio.create_task(_resume_workflow_from_images(run_id, workflow_request, article_id))
    return {"run_id": run_id, "status": "running", "article_id": article_id, "title": title}


@app.post("/workflow/resume")
async def resume_workflow_from_material(request: dict):
    """material.mdから記事生成を再開"""
    article_id = request.get("article_id")
    if not article_id:
        raise HTTPException(status_code=400, detail="article_id is required")
    
    article_folder = REPO_ROOT / "articles" / str(article_id)
    material_path = article_folder / "material.md"
    
    if not material_path.exists():
        raise HTTPException(status_code=404, detail=f"material.md not found in article {article_id}")
    
    # 新しいrun_idを生成
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    
    # material.mdの内容からテーマを抽出（最初の行をテーマとして使用）
    try:
        material_content = material_path.read_text(encoding="utf-8")
        theme = material_content.split('\n')[0].strip()
        if theme.startswith('# '):
            theme = theme[2:].strip()
        elif len(theme) > 100:
            theme = theme[:100] + "..."
    except Exception:
        theme = f"記事 {article_id} の再生成"
    
    # ワークフローを記事生成ステップから開始
    workflow_request = WorkflowRequest(
        theme=theme,
        effort="medium",
        status="draft", 
        category_name="ブログ",
        parent_category="QUON COLLEGE"
    )
    
    asyncio.create_task(_resume_workflow_from_material(run_id, workflow_request, article_id))
    return {"run_id": run_id, "status": "running", "article_id": article_id, "theme": theme}


@app.get("/")
async def root():
    return {"message": "GENDOCS Workflow API is running."}


@app.websocket("/workflow/logs/{run_id}")
async def workflow_logs_ws(ws: WebSocket, run_id: str):
    await ws.accept()
    try:
        last_index = 0
        while True:
            info = RUNS.get(run_id)
            if not info:
                await ws.send_text(json.dumps({"error": "Run not found"}, ensure_ascii=False))
                await asyncio.sleep(2)
                continue
            logs = info.get("logs", [])
            if last_index < len(logs):
                for entry in logs[last_index:]:
                    await ws.send_text(entry)
                last_index = len(logs)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


def main() -> None:
    import uvicorn

    uvicorn.run("workflow_server:app", host="0.0.0.0", port=9000, reload=False)


if __name__ == "__main__":
    main()
