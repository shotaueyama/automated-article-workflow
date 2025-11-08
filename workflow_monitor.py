#!/usr/bin/env python3
"""Simple HTTP server to inspect workflow run logs in the browser."""
from __future__ import annotations

import argparse
import json
import os
from functools import partial
import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

REPO_ROOT = Path(__file__).resolve().parent
LOG_ROOT = REPO_ROOT / "logs"
api_base = "http://localhost:9000"

INDEX_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Workflow Monitor</title>
  <style>
    :root {
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --surface: #ffffff;
      --surface-2: #f8fafc;
      --surface-3: #f1f5f9;
      --text: #1e293b;
      --text-muted: #64748b;
      --border: #e2e8f0;
      --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
      --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
      --radius: 0.75rem;
      --radius-sm: 0.5rem;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: #f8fafc;
      min-height: 100vh;
      color: var(--text);
      line-height: 1.6;
    }

    .container {
      max-width: 1000px;
      margin: 0 auto;
      padding: 2rem 1.5rem;
    }

    h1 {
      font-size: 2.25rem;
      font-weight: 700;
      color: var(--text);
      text-align: center;
      margin-bottom: 3rem;
    }

    .main-grid {
      display: flex;
      flex-direction: column;
      gap: 2rem;
    }

    .card {
      background: var(--surface);
      border-radius: var(--radius);
      box-shadow: var(--shadow-lg);
      padding: 2rem;
      border: 1px solid var(--border);
    }

    .card-header {
      margin-bottom: 2rem;
    }

    .card-title {
      font-size: 1.25rem;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 0.5rem;
    }

    .input-group {
      margin-bottom: 1rem;
    }

    .input-group label {
      display: block;
      font-size: 0.875rem;
      font-weight: 500;
      color: var(--text);
      margin-bottom: 0.5rem;
    }

    .input {
      width: 100%;
      padding: 1.25rem 1.5rem;
      border: 2px solid var(--border);
      border-radius: var(--radius-sm);
      font-size: 1.125rem;
      transition: border-color 0.15s ease;
      background: var(--surface);
    }

    .input:focus {
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgb(59 130 246 / 0.1);
    }

    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 1rem 2rem;
      font-size: 1rem;
      font-weight: 600;
      border-radius: var(--radius-sm);
      border: none;
      cursor: pointer;
      transition: all 0.15s ease;
      text-decoration: none;
      margin-top: 0.5rem;
    }

    .btn-primary {
      background: var(--primary);
      color: white;
    }

    .btn-primary:hover {
      background: var(--primary-hover);
      transform: translateY(-1px);
    }

    .btn-sm {
      padding: 0.5rem 1rem;
      font-size: 0.8rem;
    }

    .btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      transform: none !important;
    }

    .status {
      display: inline-flex;
      align-items: center;
      padding: 0.25rem 0.75rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .status-running {
      background: rgb(251 191 36 / 0.1);
      color: #92400e;
      border: 1px solid rgb(251 191 36 / 0.2);
    }

    .status-success {
      background: rgb(16 185 129 / 0.1);
      color: #065f46;
      border: 1px solid rgb(16 185 129 / 0.2);
    }

    .status-failure {
      background: rgb(239 68 68 / 0.1);
      color: #991b1b;
      border: 1px solid rgb(239 68 68 / 0.2);
    }

    .status-message {
      margin-top: 0.75rem;
      padding: 0.75rem;
      border-radius: var(--radius-sm);
      font-size: 0.875rem;
      background: var(--surface-3);
      border-left: 4px solid var(--primary);
    }

    .runs-section {
      margin-top: 3rem;
    }

    .run-card {
      background: var(--surface);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 1.25rem;
      margin-bottom: 1rem;
      border: 1px solid var(--border);
      transition: transform 0.15s ease, box-shadow 0.15s ease;
    }

    .run-card:hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-lg);
    }

    .run-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 1rem;
    }

    .run-title {
      font-size: 1.125rem;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 0.25rem;
    }

    .run-meta {
      font-size: 0.875rem;
      color: var(--text-muted);
      margin-bottom: 0.75rem;
    }

    .run-times {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1rem;
      font-size: 0.875rem;
      color: var(--text-muted);
    }

    .terminal {
      background: #1e293b;
      color: #e2e8f0;
      padding: 1.5rem;
      border-radius: var(--radius-sm);
      font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
      font-size: 0.9rem;
      line-height: 1.6;
      height: 500px;
      overflow-y: auto;
      border: 1px solid #374151;
    }

    .terminal-line {
      margin-bottom: 0.25rem;
      white-space: pre-wrap;
    }

    .analysis-output {
      background: var(--surface-2);
      padding: 1.5rem;
      border-radius: var(--radius-sm);
      font-size: 0.95rem;
      line-height: 1.7;
      white-space: pre-wrap;
      border: 1px solid var(--border);
      min-height: 400px;
    }

    .empty-state {
      text-align: center;
      padding: 3rem 1rem;
      color: var(--text-muted);
    }

    .empty-state-icon {
      font-size: 3rem;
      margin-bottom: 1rem;
      opacity: 0.5;
    }

    .material-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 1rem;
      margin-bottom: 0.75rem;
      transition: all 0.15s ease;
    }

    .material-card:hover {
      border-color: var(--primary);
      box-shadow: var(--shadow);
    }

    .material-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.5rem;
    }

    .material-id {
      font-weight: 600;
      font-size: 1.1rem;
      color: var(--primary);
    }

    .material-preview {
      font-size: 0.875rem;
      color: var(--text-muted);
      line-height: 1.4;
      margin-bottom: 0.75rem;
      max-height: 3.5rem;
      overflow: hidden;
      border-left: 3px solid var(--border);
      padding-left: 0.75rem;
    }

    .article-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 1rem;
      margin-bottom: 0.75rem;
      transition: all 0.15s ease;
    }

    .article-card:hover {
      border-color: var(--primary);
      box-shadow: var(--shadow);
    }

    .article-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.5rem;
    }

    .article-id {
      font-weight: 600;
      font-size: 1.1rem;
      color: var(--primary);
    }

    .article-title {
      font-size: 1rem;
      font-weight: 500;
      color: var(--text);
      margin-bottom: 0.5rem;
    }

    .article-preview {
      font-size: 0.875rem;
      color: var(--text-muted);
      line-height: 1.4;
      margin-bottom: 0.75rem;
      max-height: 3.5rem;
      overflow: hidden;
      border-left: 3px solid var(--border);
      padding-left: 0.75rem;
    }

    .btn-warning {
      background: var(--warning);
      color: white;
    }

    .btn-warning:hover {
      background: #d97706;
      transform: translateY(-1px);
    }

    @media (max-width: 768px) {
      .container { padding: 1rem; }
      h1 { font-size: 2rem; margin-bottom: 2rem; }
      .card { padding: 1.5rem; }
      .input { padding: 1rem 1.25rem; font-size: 1rem; }
      .btn { padding: 0.875rem 1.5rem; font-size: 0.95rem; }
      .terminal { height: 400px; padding: 1.25rem; }
      .analysis-output { min-height: 300px; padding: 1.25rem; }
      .run-header { flex-direction: column; gap: 0.75rem; }
      .run-times { grid-template-columns: 1fr; gap: 0.5rem; }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>🚀 Workflow Monitor</h1>
    
    <div class="main-grid">
      <div class="card">
        <div class="card-header">
          <h2 class="card-title">✨ 記事生成を開始</h2>
        </div>
        <div class="input-group">
          <label for="theme-input">テーマ</label>
          <input 
            type="text" 
            id="theme-input" 
            class="input"
            placeholder="例: 生成AIで月5万円を稼ぐリアルステップ"
          >
        </div>
        <button id="start-workflow-btn" class="btn btn-primary">
          記事生成開始
        </button>
        <div id="start-workflow-status"></div>
      </div>
      
      <div class="card">
        <div class="card-header">
          <h2 class="card-title">📁 記事再生成</h2>
        </div>
        <div id="materials-section">
          <p style="margin-bottom: 1rem; color: var(--text-muted);">
            material.md のみ存在するフォルダから記事生成を再開できます
          </p>
          <div id="materials-list">
            <div style="text-align: center; padding: 1rem;">読み込み中...</div>
          </div>
        </div>
      </div>
      
      <div class="card">
        <div class="card-header">
          <h2 class="card-title">🎨 画像生成再開</h2>
        </div>
        <div id="completed-articles-section">
          <p style="margin-bottom: 1rem; color: var(--text-muted);">
            article.html（優先）またはarticle.md が存在するフォルダから画像生成を再開できます
          </p>
          <div id="completed-articles-list">
            <div style="text-align: center; padding: 1rem;">読み込み中...</div>
          </div>
        </div>
      </div>
      
      <div class="card">
        <div class="card-header">
          <h2 class="card-title">📊 リアルタイムログ</h2>
        </div>
        <div id="log-output" class="terminal"></div>
      </div>
      
      <div class="card">
        <div class="card-header">
          <h2 class="card-title">🤖 GPT 分析</h2>
        </div>
        <div id="analysis-output" class="analysis-output">
          失敗した実行の「分析する」ボタンを押すと結果が表示されます。
        </div>
      </div>
    </div>
    
    <div class="runs-section">
      <div class="card">
        <div class="card-header">
          <h2 class="card-title">📝 実行履歴</h2>
        </div>
        <div id="runs">ロード中...</div>
      </div>
    </div>
  </div>
  <script>
    const apiBase = "/api";

    let lastRunsData = null;
    
    async function fetchRuns() {
      try {
        const res = await fetch(apiBase + "/runs");
        if (!res.ok) throw new Error("Failed to fetch runs");
        const data = await res.json();
        
        // データが変更された場合のみレンダリング
        const dataStr = JSON.stringify(data);
        if (lastRunsData !== dataStr) {
          renderRuns(data);
          lastRunsData = dataStr;
        }
      } catch (err) {
        document.getElementById("runs").innerText = "取得に失敗しました。workflow_server.py が動作中か確認してください。";
      }
    }

    function renderRuns(runs) {
      const container = document.getElementById("runs");
      
      // 実行中のワークフローがあるかチェック
      const runningWorkflow = runs.find(run => run.status === 'running');
      if (!runningWorkflow && logStreamActive) {
        // 実行中のワークフローがなくなったらログ配信を停止
        stopLogStream();
      }
      
      if (runs.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">📝</div>
            <p>まだ実行ログがありません。</p>
          </div>
        `;
        return;
      }
      
      // DocumentFragment を使用してパフォーマンスを向上
      const fragment = document.createDocumentFragment();
      
      for (const run of runs) {
        const card = document.createElement("div");
        card.className = "run-card";
        const statusClass = "status-" + run.status;
        
        // エスケープ処理を追加
        const escapeHtml = (text) => {
          const div = document.createElement('div');
          div.textContent = text;
          return div.innerHTML;
        };
        
        card.innerHTML = `
          <div class="run-header">
            <div>
              <h3 class="run-title">${escapeHtml(run.run_id)}</h3>
              <div class="run-meta">テーマ: ${escapeHtml(run.request?.theme ?? "N/A")} • 記事ID: ${run.article_id ?? "-"}</div>
            </div>
            <span class="status ${statusClass}">${escapeHtml(run.status ?? "running")}</span>
          </div>
          <div class="run-times">
            <div><strong>開始:</strong> ${escapeHtml(run.started_at ?? "-")}</div>
            <div><strong>終了:</strong> ${escapeHtml(run.finished_at ?? "-")}</div>
          </div>
          <div style="margin-top: 1rem;">
            <button 
              onclick="requestAnalysis('${escapeHtml(run.run_id)}')" 
              class="btn btn-sm ${run.status === 'failure' ? 'btn-primary' : ''}" 
              ${run.status === 'failure' ? '' : 'disabled'}>
              🔍 分析する
            </button>
          </div>
        `;
        fragment.appendChild(card);
      }
      
      // 一度にDOMに挿入
      container.innerHTML = "";
      container.appendChild(fragment);
    }

    let logStreamActive = false;
    let currentWebSocket = null;

    function connectLogStream() {
      if (!logStreamActive) return;
      
      const logBox = document.getElementById("log-output");
      
      // 実行中のワークフローを取得
      function getRunningWorkflow() {
        return fetch(apiBase + "/runs")
          .then(res => res.json())
          .then(runs => runs.find(run => run.status === 'running'))
          .catch(() => null);
      }
      
      async function connectToWorkflowLogs() {
        if (!logStreamActive) return;
        
        const runningWorkflow = await getRunningWorkflow();
        if (!runningWorkflow) {
          if (logStreamActive) {
            setTimeout(connectLogStream, 2000);
          }
          return;
        }
        
        const wsUrl = (location.protocol === "https:" ? "wss://" : "ws://") + 
                      "127.0.0.1:3000" + "/workflow/logs/" + runningWorkflow.run_id;
        const ws = new WebSocket(wsUrl);
        currentWebSocket = ws;
        
        ws.onopen = () => {
          const entry = document.createElement("div");
          entry.className = "terminal-line";
          entry.style.color = "#10b981";
          entry.textContent = `✅ ワークフローログに接続しました (Run ID: ${runningWorkflow.run_id})`;
          logBox.appendChild(entry);
          logBox.scrollTop = logBox.scrollHeight;
        };
        
        let messageBuffer = [];
        let bufferTimeout;
        
        ws.onmessage = (event) => {
          messageBuffer.push(event.data);
          
          // バッファをクリアするタイマーを設定/リセット
          clearTimeout(bufferTimeout);
          bufferTimeout = setTimeout(() => {
            flushMessageBuffer();
          }, 100); // 100msごとにバッファを処理
        };
        
        function flushMessageBuffer() {
          if (messageBuffer.length === 0) return;
          
          const fragment = document.createDocumentFragment();
          const timestamp = new Date().toLocaleTimeString();
          
          for (const data of messageBuffer) {
            const entry = document.createElement("div");
            entry.className = "terminal-line";
            
            try {
              const jsonData = JSON.parse(data);
              if (jsonData.error) {
                entry.style.color = "#ef4444";
                entry.textContent = `${timestamp} ❌ エラー: ${jsonData.error}`;
              } else {
                entry.textContent = `${timestamp} ${data}`;
              }
            } catch (e) {
              // プレーンテキストの場合
              if (data.includes("ERROR") || data.includes("Failed")) {
                entry.style.color = "#ef4444";
              } else if (data.includes("SUCCESS") || data.includes("Completed")) {
                entry.style.color = "#10b981";
              } else if (data.includes("OpenAI") || data.includes("API")) {
                entry.style.color = "#3b82f6";
              }
              entry.textContent = `${timestamp} ${data}`;
            }
            
            fragment.appendChild(entry);
          }
          
          logBox.appendChild(fragment);
          logBox.scrollTop = logBox.scrollHeight;
          
          // 効率的な行数制限
          const children = logBox.children;
          if (children.length > 150) {
            const removeCount = children.length - 150;
            for (let i = 0; i < removeCount; i++) {
              logBox.removeChild(children[0]);
            }
          }
          
          messageBuffer = [];
        }
        
        ws.onclose = () => {
          if (logStreamActive) {
            setTimeout(connectLogStream, 2000);
          }
        };
        
        ws.onerror = (error) => {
          const entry = document.createElement("div");
          entry.className = "terminal-line";
          entry.style.color = "#ef4444";
          entry.textContent = "❌ WebSocket接続エラーが発生しました";
          logBox.appendChild(entry);
        };
      }
      
      connectToWorkflowLogs();
    }

    function startLogStream() {
      logStreamActive = true;
      const logBox = document.getElementById("log-output");
      logBox.innerHTML = "";
      const entry = document.createElement("div");
      entry.className = "terminal-line";
      entry.style.color = "#10b981";
      entry.textContent = "🔄 ワークフローログ配信を開始します...";
      logBox.appendChild(entry);
      connectLogStream();
    }

    function stopLogStream() {
      logStreamActive = false;
      if (currentWebSocket) {
        currentWebSocket.close();
        currentWebSocket = null;
      }
      const logBox = document.getElementById("log-output");
      const entry = document.createElement("div");
      entry.className = "terminal-line";
      entry.style.color = "#64748b";
      entry.textContent = "⏸️ ワークフローログ配信を停止しました";
      logBox.appendChild(entry);
    }

    fetchRuns();
    fetchMaterials();
    fetchCompletedArticles();
    // パフォーマンス向上のため30秒間隔に変更
    setInterval(fetchRuns, 30000);
    
    // 初期状態でログ配信停止メッセージを表示
    const logBox = document.getElementById("log-output");
    const entry = document.createElement("div");
    entry.className = "terminal-line";
    entry.style.color = "#64748b";
    entry.textContent = "📊 ワークフロー実行時にリアルタイムログが表示されます";
    logBox.appendChild(entry);

    document.getElementById("start-workflow-btn").addEventListener("click", startWorkflow);

    async function fetchMaterials() {
      try {
        const res = await fetch(apiBase + "/articles/materials");
        if (!res.ok) throw new Error("Failed to fetch materials");
        const materials = await res.json();
        renderMaterials(materials);
      } catch (err) {
        document.getElementById("materials-list").innerHTML = 
          '<div style="color: var(--danger); text-align: center; padding: 1rem;">マテリアル取得に失敗しました</div>';
      }
    }

    async function fetchCompletedArticles() {
      try {
        const res = await fetch(apiBase + "/articles/completed");
        if (!res.ok) throw new Error("Failed to fetch completed articles");
        const articles = await res.json();
        renderCompletedArticles(articles);
      } catch (err) {
        document.getElementById("completed-articles-list").innerHTML = 
          '<div style="color: var(--danger); text-align: center; padding: 1rem;">完成記事取得に失敗しました</div>';
      }
    }

    function renderMaterials(materials) {
      const container = document.getElementById("materials-list");
      
      if (materials.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">📁</div>
            <p>material.mdのみ存在するフォルダはありません</p>
          </div>
        `;
        return;
      }

      const fragment = document.createDocumentFragment();
      
      for (const material of materials) {
        const card = document.createElement("div");
        card.className = "material-card";
        
        const escapeHtml = (text) => {
          const div = document.createElement('div');
          div.textContent = text;
          return div.innerHTML;
        };
        
        card.innerHTML = `
          <div class="material-header">
            <span class="material-id">記事 ${material.article_id}</span>
            <button 
              onclick="resumeWorkflow(${material.article_id})" 
              class="btn btn-sm btn-primary">
              🔄 再生成
            </button>
          </div>
          <div class="material-preview">${escapeHtml(material.material_preview)}</div>
        `;
        fragment.appendChild(card);
      }
      
      container.innerHTML = "";
      container.appendChild(fragment);
    }

    function renderCompletedArticles(articles) {
      const container = document.getElementById("completed-articles-list");
      
      if (articles.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">🎨</div>
            <p>article.mdが存在するフォルダはありません</p>
          </div>
        `;
        return;
      }

      const fragment = document.createDocumentFragment();
      
      for (const article of articles) {
        const card = document.createElement("div");
        card.className = "article-card";
        
        const escapeHtml = (text) => {
          const div = document.createElement('div');
          div.textContent = text;
          return div.innerHTML;
        };
        
        card.innerHTML = `
          <div class="article-header">
            <span class="article-id">記事 ${article.article_id}</span>
            <button 
              onclick="resumeFromImages(${article.article_id})" 
              class="btn btn-sm btn-warning">
              🎨 画像生成再開
            </button>
          </div>
          <div class="article-title">${escapeHtml(article.title)}</div>
          <div class="article-preview">${escapeHtml(article.article_preview)}</div>
        `;
        fragment.appendChild(card);
      }
      
      container.innerHTML = "";
      container.appendChild(fragment);
    }

    async function resumeWorkflow(articleId) {
      const statusBox = document.getElementById("start-workflow-status");
      
      try {
        statusBox.innerHTML = '<div class="status-message">🔄 記事再生成を開始中...</div>';
        
        const res = await fetch(`${apiBase}/workflow/resume`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ article_id: articleId }),
        });
        
        if (!res.ok) {
          const errorText = await res.text();
          throw new Error(`記事再生成に失敗しました: ${errorText}`);
        }
        
        const data = await res.json();
        statusBox.innerHTML = `
          <div class="status-message" style="border-left-color: var(--success);">
            ✅ 記事再生成開始: Run ID ${data.run_id}<br>
            📁 記事ID: ${data.article_id}<br>
            📝 テーマ: ${data.theme}
          </div>
        `;
        
        // 実行履歴を更新
        setTimeout(fetchRuns, 1000);
        
        // ログ配信を開始
        startLogStream();
        
      } catch (err) {
        statusBox.innerHTML = `
          <div class="status-message" style="border-left-color: var(--danger);">
            ❌ 記事再生成に失敗: ${err.message}
          </div>
        `;
      }
    }

    async function resumeFromImages(articleId) {
      const statusBox = document.getElementById("start-workflow-status");
      
      try {
        statusBox.innerHTML = '<div class="status-message">🎨 画像生成再開を開始中...</div>';
        
        const res = await fetch(`${apiBase}/workflow/resume-images`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ article_id: articleId }),
        });
        
        if (!res.ok) {
          const errorText = await res.text();
          throw new Error(`画像生成再開に失敗しました: ${errorText}`);
        }
        
        const data = await res.json();
        statusBox.innerHTML = `
          <div class="status-message" style="border-left-color: var(--warning);">
            ✅ 画像生成再開: Run ID ${data.run_id}<br>
            📁 記事ID: ${data.article_id}<br>
            📝 タイトル: ${data.title}
          </div>
        `;
        
        // 実行履歴を更新
        setTimeout(fetchRuns, 1000);
        
        // ログ配信を開始
        startLogStream();
        
      } catch (err) {
        statusBox.innerHTML = `
          <div class="status-message" style="border-left-color: var(--danger);">
            ❌ 画像生成再開に失敗: ${err.message}
          </div>
        `;
      }
    }

    async function startWorkflow() {
      const statusBox = document.getElementById("start-workflow-status");
      const button = document.getElementById("start-workflow-btn");
      const theme = (document.getElementById("theme-input").value || "").trim();
      
      if (!theme) {
        statusBox.innerHTML = '<div class="status-message" style="border-left-color: var(--danger);">⚠️ テーマを入力してください。</div>';
        console.log("[workflow] テーマ未入力のためリクエストを送信しませんでした");
        return;
      }
      
      button.disabled = true;
      button.textContent = "送信中...";
      statusBox.innerHTML = '<div class="status-message">📤 実行リクエスト送信中...</div>';
      console.log("[workflow] 実行リクエスト送信開始", { theme });
      
      try {
        const res = await fetch(`${apiBase}/workflow/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ theme }),
        });
        if (!res.ok) {
          const errorText = await res.text();
          console.error("[workflow] APIエラー", res.status, errorText);
          throw new Error("APIエラー");
        }
        const data = await res.json();
        statusBox.innerHTML = `<div class="status-message" style="border-left-color: var(--success);">✅ 実行開始: Run ID ${data.run_id}</div>`;
        console.log("[workflow] 実行開始", data);
        document.getElementById("theme-input").value = "";
        setTimeout(fetchRuns, 1000);
        
        // ログ配信を開始
        startLogStream();
      } catch (err) {
        statusBox.innerHTML = `<div class="status-message" style="border-left-color: var(--danger);">❌ 実行に失敗しました: ${err.message}</div>`;
        console.error("[workflow] 実行に失敗しました", err);
      } finally {
        button.disabled = false;
        button.textContent = "記事生成開始";
      }
    }

    async function requestAnalysis(runId) {
      const output = document.getElementById("analysis-output");
      output.innerHTML = '<div style="text-align: center; padding: 2rem; color: var(--text-muted);">🔄 分析中...</div>';
      
      try {
        const res = await fetch(`${apiBase}/runs/${runId}/analysis`, { method: "POST" });
        if (!res.ok) throw new Error("分析APIに失敗しました");
        const data = await res.json();
        output.innerHTML = `
          <div style="margin-bottom: 0.75rem; padding: 0.5rem; background: var(--surface-3); border-radius: var(--radius-sm); font-weight: 600;">
            🤖 Run ID: ${runId} の分析結果
          </div>
          <div>${data.analysis.replace(/\\n/g, '<br>')}</div>
        `;
      } catch (err) {
        output.innerHTML = `<div style="color: var(--danger); text-align: center; padding: 2rem;">❌ 分析に失敗しました: ${err.message}</div>`;
      }
    }
  </script>
</body>
</html>
"""


class LogBroadcaster:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def register(self, ws: WebSocket) -> None:
        await ws.accept()
        self.connections.add(ws)

    def unregister(self, ws: WebSocket) -> None:
        self.connections.discard(ws)

    async def broadcast(self, message: str) -> None:
        stale = []
        for ws in self.connections:
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.unregister(ws)


log_broadcaster = LogBroadcaster()
app = FastAPI()
monitor_logger = logging.getLogger("workflow_monitor")


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(INDEX_HTML)


@app.get("/api/runs")
async def api_runs():
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get(f"{api_base}/workflow/runs")
        res.raise_for_status()
        return res.json()


@app.post("/api/workflow/run")
async def api_workflow_run(request: dict):
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.post(f"{api_base}/workflow/run", json=request)
        res.raise_for_status()
        return res.json()


@app.get("/api/articles/completed")
async def api_completed():
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get(f"{api_base}/articles/completed")
        res.raise_for_status()
        return res.json()


@app.get("/api/articles/materials")
async def api_materials():
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get(f"{api_base}/articles/materials")
        res.raise_for_status()
        return res.json()


@app.post("/api/workflow/resume")
async def api_workflow_resume(request: dict):
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.post(f"{api_base}/workflow/resume", json=request)
        res.raise_for_status()
        return res.json()


@app.post("/api/workflow/resume-images")
async def api_workflow_resume_images(request: dict):
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.post(f"{api_base}/workflow/resume-images", json=request)
        res.raise_for_status()
        return res.json()


@app.post("/api/runs/{run_id}/analysis")
async def api_analysis(run_id: str):
    import httpx
    from fastapi import HTTPException

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            res = await client.post(f"{api_base}/workflow/runs/{run_id}/analysis")
            res.raise_for_status()
            return res.json()
        except httpx.TimeoutException:
            monitor_logger.error(f"Analysis request timed out for run {run_id}")
            raise HTTPException(
                status_code=504, 
                detail="Analysis request timed out. The analysis process may still be running in the background."
            )
        except httpx.HTTPStatusError as e:
            monitor_logger.error(f"Analysis request failed: {e.response.status_code} {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code, 
                detail=f"Analysis failed: {e.response.text}"
            )
        except Exception as e:
            monitor_logger.error(f"Unexpected error during analysis: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Unexpected error: {str(e)}"
            )


@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket):
    await log_broadcaster.register(ws)
    try:
        while True:
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        log_broadcaster.unregister(ws)
        monitor_logger.info("WebSocket disconnected")


async def tail_latest_log() -> None:
    import httpx

    async with httpx.AsyncClient() as client:
        while True:
            try:
                res = await client.get(f"{api_base}/workflow/runs")
                res.raise_for_status()
                runs = res.json()
                for run in runs:
                    message = json.dumps(run, ensure_ascii=False)
                    await log_broadcaster.broadcast(message)
            except Exception:
                pass
            await asyncio.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser(description="Workflow monitor with WebSocket log stream.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--api-base", default="http://localhost:9000")
    args = parser.parse_args()

    global api_base
    api_base = args.api_base.rstrip("/")

    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    log_file = LOG_ROOT / "workflow_monitor.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    monitor_logger.info(
        "Starting workflow monitor on %s:%d (API base %s)", args.host, args.port, api_base
    )

    loop = asyncio.get_event_loop()
    loop.create_task(tail_latest_log())
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
