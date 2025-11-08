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

    stdout_task = asyncio.create_task(_stream_reader(process.stdout, run_id, "stdout"))
    stderr_task = asyncio.create_task(_stream_reader(process.stderr, run_id, "stderr"))
    await process.wait()
    await stdout_task
    await stderr_task

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

    stdout_task = asyncio.create_task(_stream_reader(process.stdout, run_id, "stdout"))
    stderr_task = asyncio.create_task(_stream_reader(process.stderr, run_id, "stderr"))
    await process.wait()
    await stdout_task
    await stderr_task

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

    stdout_task = asyncio.create_task(_stream_reader(process.stdout, run_id, "stdout"))
    stderr_task = asyncio.create_task(_stream_reader(process.stderr, run_id, "stderr"))
    await process.wait()
    await stdout_task
    await stderr_task

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


@app.get("/articles/completed")
async def list_completed_articles():
    """article.mdが存在するフォルダを一覧取得（画像生成から再開用）"""
    articles_root = REPO_ROOT / "articles"
    if not articles_root.exists():
        return []
    
    completed_articles = []
    for folder in articles_root.iterdir():
        if not folder.is_dir() or not folder.name.isdigit():
            continue
            
        article_path = folder / "article.md"
        
        # article.mdが存在する場合
        if article_path.exists():
            try:
                article_content = article_path.read_text(encoding="utf-8")
                # 最初の見出しをタイトルとして抽出
                lines = article_content.split('\n')
                title = "記事タイトル未設定"
                for line in lines:
                    if line.startswith('# '):
                        title = line[2:].strip()
                        break
                    elif line.startswith('## '):
                        title = line[3:].strip()
                        break
                
                preview = article_content[:200] + "..." if len(article_content) > 200 else article_content
                
                completed_articles.append({
                    "article_id": int(folder.name),
                    "folder_name": folder.name,
                    "title": title,
                    "article_preview": preview,
                    "article_path": str(article_path.relative_to(REPO_ROOT))
                })
            except Exception:
                completed_articles.append({
                    "article_id": int(folder.name),
                    "folder_name": folder.name,
                    "title": "記事タイトル読み込みエラー",
                    "article_preview": "プレビューを読み込めませんでした",
                    "article_path": str(article_path.relative_to(REPO_ROOT))
                })
    
    # article_id順にソート
    completed_articles.sort(key=lambda x: x["article_id"], reverse=True)
    return completed_articles


@app.get("/articles/materials")
async def list_material_only_folders():
    """material.mdのみ存在するフォルダを一覧取得"""
    articles_root = REPO_ROOT / "articles"
    if not articles_root.exists():
        return []
    
    material_only_folders = []
    for folder in articles_root.iterdir():
        if not folder.is_dir() or not folder.name.isdigit():
            continue
            
        material_path = folder / "material.md"
        article_path = folder / "article.md"
        
        # material.mdが存在し、article.mdが存在しない場合
        if material_path.exists() and not article_path.exists():
            # material.mdの一部を読み取ってプレビューとして使用
            try:
                material_content = material_path.read_text(encoding="utf-8")
                preview = material_content[:200] + "..." if len(material_content) > 200 else material_content
                
                material_only_folders.append({
                    "article_id": int(folder.name),
                    "folder_name": folder.name,
                    "material_preview": preview,
                    "material_path": str(material_path.relative_to(REPO_ROOT))
                })
            except Exception:
                material_only_folders.append({
                    "article_id": int(folder.name),
                    "folder_name": folder.name,
                    "material_preview": "プレビューを読み込めませんでした",
                    "material_path": str(material_path.relative_to(REPO_ROOT))
                })
    
    # article_id順にソート
    material_only_folders.sort(key=lambda x: x["article_id"])
    return material_only_folders


@app.post("/workflow/resume-images")
async def resume_workflow_from_images(request: dict):
    """article.mdから画像生成を再開"""
    article_id = request.get("article_id")
    if not article_id:
        raise HTTPException(status_code=400, detail="article_id is required")
    
    article_folder = REPO_ROOT / "articles" / str(article_id)
    article_path = article_folder / "article.md"
    
    if not article_path.exists():
        raise HTTPException(status_code=404, detail=f"article.md not found in article {article_id}")
    
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
