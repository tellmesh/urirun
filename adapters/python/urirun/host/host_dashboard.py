# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Small host dashboard for planfile tasks, nodes and urirun activity."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import socket
import ssl
import subprocess
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse


_SERVICE_LOCK = threading.Lock()
_SERVICE_SERVERS: dict[str, ThreadingHTTPServer] = {}
_SERVICE_THREADS: dict[str, threading.Thread] = {}


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>urirun host</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8fa;
      --surface: #ffffff;
      --ink: #111827;
      --muted: #64748b;
      --line: #d9dee7;
      --accent: #0f766e;
      --warn: #b45309;
      --bad: #b91c1c;
      --good: #15803d;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 5;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      min-height: 64px;
      padding: 12px 20px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.94);
      backdrop-filter: blur(10px);
    }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: 20px; font-weight: 750; letter-spacing: 0; }
    h2 { font-size: 16px; font-weight: 700; }
    .subtle { color: var(--muted); }
    .toolbar, .tabs, .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    button, select, input, textarea {
      font: inherit;
      border: 1px solid var(--line);
      background: var(--surface);
      color: var(--ink);
      border-radius: 6px;
    }
    button {
      min-height: 36px;
      padding: 0 12px;
      cursor: pointer;
    }
    button.primary { background: var(--accent); border-color: var(--accent); color: white; }
    button.danger { color: var(--bad); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    select, input { min-height: 36px; padding: 0 10px; }
    textarea {
      width: 100%;
      min-height: 108px;
      padding: 10px 12px;
      resize: vertical;
    }
    main {
      width: min(1440px, 100%);
      margin: 0 auto;
      padding: 18px 20px 84px;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(5, minmax(120px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .metric {
      min-height: 76px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
    }
    .metric strong { display: block; font-size: 24px; line-height: 1.1; }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(320px, .75fr);
      gap: 14px;
      align-items: start;
    }
    .panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      overflow: hidden;
    }
    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
    }
    .panel-body { padding: 12px 14px; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; min-width: 760px; }
    th, td { padding: 9px 8px; border-bottom: 1px solid #eef1f6; text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; }
    .status, .pill {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 0 8px;
      border-radius: 999px;
      background: #eef2f7;
      color: #334155;
      white-space: nowrap;
    }
    .status.done, .pill.up { background: #dcfce7; color: var(--good); }
    .status.blocked, .status.failed, .pill.down { background: #fee2e2; color: var(--bad); }
    .status.in_progress, .pill.running { background: #fef3c7; color: var(--warn); }
    .stack { display: grid; gap: 14px; }
    .list { display: grid; gap: 8px; }
    .chat-form { display: grid; gap: 10px; }
    .chat-options, .node-options {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .check {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 30px;
      color: var(--muted);
    }
    .check input { min-height: 0; }
    .chat-result {
      display: grid;
      gap: 8px;
      max-height: 620px;
      overflow: auto;
    }
    .message {
      display: grid;
      gap: 8px;
      padding: 10px;
      border: 1px solid #eef1f6;
      border-radius: 8px;
      background: #fbfcfe;
    }
    .message.user { background: #ecfeff; border-color: #bae6fd; }
    .message.system { background: #f8fafc; }
    .message-head { display: flex; justify-content: space-between; gap: 10px; align-items: center; }
    .attachments {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 8px;
    }
    .attachment {
      display: grid;
      gap: 6px;
      padding: 8px;
      border: 1px solid #eef1f6;
      border-radius: 8px;
      background: #fff;
    }
    .attachment img {
      width: 100%;
      max-height: 220px;
      object-fit: contain;
      border: 1px solid #eef1f6;
      border-radius: 6px;
      background: #f8fafc;
    }
    .attachment.attachment-qr {
      max-width: 380px;
    }
    .attachment.attachment-qr img {
      max-height: 340px;
      image-rendering: pixelated;
    }
    pre {
      margin: 0;
      padding: 10px;
      border: 1px solid #eef1f6;
      border-radius: 6px;
      background: #f8fafc;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .item {
      display: grid;
      gap: 4px;
      padding: 10px;
      border: 1px solid #eef1f6;
      border-radius: 8px;
      background: #fbfcfe;
    }
    .mono {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    .bottom-nav {
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 6;
      display: none;
      grid-template-columns: repeat(5, 1fr);
      border-top: 1px solid var(--line);
      background: var(--surface);
    }
    .bottom-nav button {
      border: 0;
      border-radius: 0;
      min-height: 56px;
      border-right: 1px solid var(--line);
    }
    .hidden { display: none !important; }
    @media (max-width: 920px) {
      .topbar { align-items: flex-start; flex-direction: column; }
      main { padding: 14px 12px 76px; }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .grid { grid-template-columns: 1fr; }
      .desktop-tabs { display: none; }
      .bottom-nav { display: grid; }
      table { min-width: 680px; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div>
      <h1>urirun host</h1>
      <p class="subtle" id="contextLine">Loading...</p>
    </div>
    <div class="toolbar">
      <div class="tabs desktop-tabs">
        <button data-view="overview">Overview</button>
        <button data-view="chat">Chat</button>
        <button data-view="tasks">Tasks</button>
        <button data-view="nodes">Nodes</button>
        <button data-view="activity">Activity</button>
      </div>
      <button id="scannerBtn" type="button">Phone Scanner</button>
      <button class="primary" id="refreshBtn">Refresh</button>
    </div>
  </header>
  <main>
    <section class="metrics" id="metrics"></section>
    <section class="grid">
      <div class="stack">
        <article class="panel view-block" data-section="chat">
          <div class="panel-head">
            <div>
              <h2>Node Chat</h2>
              <p class="subtle">Natural language to URI flow across selected nodes.</p>
            </div>
            <span class="pill" id="chatMode">dry-run</span>
          </div>
          <div class="panel-body">
            <form class="chat-form" id="chatForm">
              <textarea id="chatPrompt" placeholder="np. sprawdz health i procesy na wszystkich node'ach"></textarea>
              <div>
                <div class="subtle">Target nodes</div>
                <div class="node-options" id="chatNodeList"></div>
              </div>
              <div class="chat-options">
                <label class="check"><input type="checkbox" id="chatExecute"> Execute URI operations</label>
                <label class="check"><input type="checkbox" id="chatNoLlm"> Heuristic planner only</label>
                <button class="primary" type="submit" id="chatAskBtn">Run</button>
              </div>
            </form>
          </div>
        </article>
        <article class="panel view-block" data-section="chat">
          <div class="panel-head"><h2>Chat Result</h2><span class="subtle" id="chatStatus">idle</span></div>
          <div class="panel-body"><div class="chat-result" id="chatResult"></div></div>
        </article>
        <article class="panel view-block" data-section="tasks">
          <div class="panel-head">
            <h2>Tasks</h2>
            <div class="toolbar">
              <select id="sprintFilter">
                <option value="current">current</option>
                <option value="all">all</option>
              </select>
              <select id="queueFilter">
                <option value="">all queues</option>
                <option value="implementation">implementation</option>
                <option value="daily">daily</option>
                <option value="review">review</option>
                <option value="default">default</option>
              </select>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Queue</th><th>Priority</th><th>Actions</th></tr></thead>
              <tbody id="tasksBody"></tbody>
            </table>
          </div>
        </article>
        <article class="panel view-block" data-section="nodes">
          <div class="panel-head"><h2>Nodes</h2><span class="subtle" id="nodeCount"></span></div>
          <div class="panel-body"><div class="list" id="nodesList"></div></div>
        </article>
        <article class="panel view-block" data-section="nodes">
          <div class="panel-head"><h2>URI Processes</h2><span class="subtle" id="routeCount"></span></div>
          <div class="panel-body"><div class="list" id="routesList"></div></div>
        </article>
      </div>
      <aside class="stack">
        <article class="panel view-block" data-section="activity">
          <div class="panel-head"><h2>Checks</h2></div>
          <div class="panel-body"><div class="list" id="checksList"></div></div>
        </article>
        <article class="panel view-block" data-section="activity">
          <div class="panel-head"><h2>Logs</h2></div>
          <div class="panel-body"><div class="list" id="logsList"></div></div>
        </article>
        <article class="panel view-block" data-section="activity">
          <div class="panel-head"><h2>Artifacts</h2></div>
          <div class="panel-body"><div class="list" id="artifactsList"></div></div>
        </article>
      </aside>
    </section>
  </main>
  <nav class="bottom-nav">
    <button data-view="overview">Overview</button>
    <button data-view="chat">Chat</button>
    <button data-view="tasks">Tasks</button>
    <button data-view="nodes">Nodes</button>
    <button data-view="activity">Activity</button>
  </nav>
  <script>
    const params = new URLSearchParams(window.location.search);
    const initialView = params.get('view') || 'overview';
    const state = { summary: null, tasks: [], view: initialView, chatMessages: [] };
    const $ = (id) => document.getElementById(id);

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      });
      const data = await response.json();
      if (!response.ok || data.ok === false) throw new Error(data.error || response.statusText);
      return data;
    }

    function text(value, fallback = '') {
      return value === undefined || value === null || value === '' ? fallback : String(value);
    }

    function esc(value) {
      return text(value).replace(/[&<>"']/g, (ch) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[ch]));
    }

    function metric(label, value, note) {
      return `<div class="metric"><strong>${text(value, 0)}</strong><span>${label}</span><p class="subtle">${text(note)}</p></div>`;
    }

    function empty(label) {
      return `<div class="item subtle">${label}</div>`;
    }

    function renderMetrics(summary) {
      const counts = summary.taskCounts || {};
      $('metrics').innerHTML = [
        metric('open tasks', counts.open || 0, 'planfile'),
        metric('running', counts.in_progress || 0, 'in progress'),
        metric('blocked', counts.blocked || 0, 'needs operator'),
        metric('nodes online', summary.nodesOnline || 0, `${summary.nodeCount || 0} configured`),
        metric('URI processes', summary.routeCount || 0, 'mesh routes'),
      ].join('');
    }

    function renderTasks(tasks) {
      $('tasksBody').innerHTML = tasks.map((ticket) => {
        const exec = ticket.execution || {};
        return `<tr>
          <td class="mono">${ticket.id}</td>
          <td><strong>${ticket.name}</strong><div class="subtle">${text(ticket.description).slice(0, 120)}</div></td>
          <td><span class="status ${ticket.status}">${ticket.status}</span><div class="subtle">${text(exec.state)}</div></td>
          <td>${text(exec.queue, 'default')}</td>
          <td>${text(ticket.priority, 'normal')}</td>
          <td><div class="actions">
            <button data-action="start" data-id="${ticket.id}">Start</button>
            <button data-action="complete" data-id="${ticket.id}">Done</button>
            <button class="danger" data-action="block" data-id="${ticket.id}">Block</button>
          </div></td>
        </tr>`;
      }).join('') || `<tr><td colspan="6">${empty('No tasks')}</td></tr>`;
    }

    function renderNodes(nodes) {
      $('nodeCount').textContent = `${nodes.length} configured`;
      $('nodesList').innerHTML = nodes.map((node) => `<div class="item">
        <div><strong>${node.name}</strong> <span class="pill ${node.reachable ? 'up' : 'down'}">${node.reachable ? 'up' : 'down'}</span></div>
        <div class="mono">${node.url}</div>
        <div class="subtle">${(node.routes || []).length} routes${node.error ? ` · ${node.error}` : ''}</div>
      </div>`).join('') || empty('No nodes configured');
    }

    function renderChatNodes(nodes) {
      $('chatNodeList').innerHTML = nodes.map((node) => `<label class="check">
        <input type="checkbox" name="chatNode" value="${esc(node.name)}" ${node.reachable ? '' : 'disabled'}>
        ${esc(node.name)} <span class="pill ${node.reachable ? 'up' : 'down'}">${node.reachable ? 'up' : 'down'}</span>
      </label>`).join('') || '<span class="subtle">No nodes configured</span>';
    }

    function renderRoutes(routes) {
      $('routeCount').textContent = `${routes.length} routes`;
      $('routesList').innerHTML = routes.slice(0, 30).map((route) => `<div class="item">
        <div class="mono">${route.uri}</div>
        <div class="subtle">${text(route.node)} · ${text(route.kind)} · ${text(route.adapter)}</div>
      </div>`).join('') || empty('No routes discovered');
    }

    function renderChecks(items) {
      $('checksList').innerHTML = items.map((item) => `<div class="item">
        <div><strong>${item.subject}</strong> <span class="status ${item.status}">${item.status}</span></div>
        <div class="mono">${item.check_uri}</div>
        <div class="subtle">${item.created_at}</div>
      </div>`).join('') || empty('No checks recorded');
    }

    function renderLogs(items) {
      $('logsList').innerHTML = items.map((item) => `<div class="item">
        <div><strong>${item.event}</strong> <span class="pill">${item.stream}</span></div>
        ${item.detail ? `<details><summary>URI / JSON</summary><pre>${esc(JSON.stringify(item.detail, null, 2))}</pre></details>` : ''}
        <div class="subtle">${item.created_at}</div>
      </div>`).join('') || empty('No logs recorded');
    }

    function artifactPreview(item) {
      const path = item && item.path ? String(item.path) : '';
      if (!/\.(png|jpe?g|webp|gif)$/i.test(path)) return '';
      return `<img src="/api/file?path=${encodeURIComponent(path)}" alt="${esc(basename(path))}" loading="lazy">`;
    }

    function renderArtifacts(items) {
      $('artifactsList').innerHTML = items.map((item) => `<div class="item">
        <div><strong>${item.kind}</strong></div>
        ${artifactPreview(item)}
        <div class="mono">${item.uri}</div>
        <div class="subtle">${text(item.path)} ${item.created_at || ''}</div>
        ${item.meta ? `<details><summary>metadata</summary><pre>${esc(JSON.stringify(item.meta, null, 2))}</pre></details>` : ''}
      </div>`).join('') || empty('No artifacts recorded');
    }

    function basename(path) {
      return text(path).split('/').filter(Boolean).pop() || text(path);
    }

    function renderAttachment(att) {
      const meta = att.meta || {};
      const ocr = meta.ocr || {};
      const qrClass = att.kind === 'qr-code' ? ' attachment-qr' : '';
      const preview = att.previewUrl
        ? `<img src="${esc(att.previewUrl)}" alt="${esc(basename(att.path))}" loading="lazy">`
        : `<div class="subtle">preview unavailable</div>`;
      const ocrLine = ocr.ok
        ? `<div class="subtle">OCR ${esc(ocr.backend || '')}: ${esc(text(ocr.text).slice(0, 160))}</div>`
        : (ocr.error ? `<div class="subtle">OCR: ${esc(ocr.error)}</div>` : '');
      return `<div class="attachment${qrClass}">
        ${preview}
        <div class="mono">${esc(basename(att.path))}</div>
        <div class="subtle">${esc(att.kind || 'file')} ${meta.width && meta.height ? `· ${meta.width}x${meta.height}` : ''}</div>
        ${ocrLine}
        <details><summary>metadata</summary><pre>${esc(JSON.stringify(att, null, 2))}</pre></details>
      </div>`;
    }

    function renderChatMessage(message) {
      const detail = message.detail || {};
      const timeline = detail.timeline || [];
      const lines = timeline.map((step) => `${step.ok ? 'ok' : 'fail'} · ${step.target || ''} · ${step.uri}`).join('\n');
      const attachments = message.attachments || [];
      const role = message.role || 'system';
      return `<div class="message ${esc(role)}">
        <div class="message-head">
          <strong>${esc(role)}</strong>
          <span class="subtle">${esc(message.created_at || '')}</span>
        </div>
        <div>${esc(message.content || '')}</div>
        ${lines ? `<pre>${esc(lines)}</pre>` : ''}
        ${attachments.length ? `<div class="attachments">${attachments.map(renderAttachment).join('')}</div>` : ''}
        ${Object.keys(detail).length ? `<details><summary>URI / JSON</summary><pre>${esc(JSON.stringify(detail, null, 2))}</pre></details>` : ''}
      </div>`;
    }

    function renderChatHistory() {
      const seenQr = new Set();
      const visible = [...state.chatMessages].reverse().filter((message) => {
        const uri = message.detail && message.detail.uri;
        if (uri && uri.startsWith('dashboard://host/qr/')) {
          if (seenQr.has(uri)) return false;
          seenQr.add(uri);
        }
        return true;
      }).reverse();
      $('chatResult').innerHTML = visible.map(renderChatMessage).join('') || empty('No chat messages yet');
    }

    async function loadChatHistory() {
      const history = await api('/api/chat/history?limit=80');
      state.chatMessages = history.messages || [];
      renderChatHistory();
    }

    function applyView(view) {
      state.view = view;
      document.querySelectorAll('.view-block').forEach((block) => {
        block.classList.toggle('hidden', view !== 'overview' && block.dataset.section !== view);
      });
    }

    async function load() {
      const sprint = $('sprintFilter').value;
      const queue = $('queueFilter').value;
      const [summary, tasks] = await Promise.all([
        api('/api/summary'),
        api(`/api/tasks?sprint=${encodeURIComponent(sprint)}&queue=${encodeURIComponent(queue)}`),
      ]);
      state.summary = summary;
      state.tasks = tasks.tickets || [];
      $('contextLine').textContent = `${summary.project} · ${summary.db}`;
      renderMetrics(summary);
      renderTasks(state.tasks);
      renderNodes(summary.nodes || []);
      renderChatNodes(summary.nodes || []);
      renderRoutes(summary.routes || []);
      renderChecks(summary.checks || []);
      renderLogs(summary.logs || []);
      renderArtifacts(summary.artifacts || []);
      await loadChatHistory();
      applyView(state.view);
    }

    async function taskAction(id, action) {
      const body = action === 'complete'
        ? { note: 'Completed from urirun host dashboard' }
        : action === 'block'
          ? { reason: 'Blocked from urirun host dashboard' }
          : {};
      await api(`/api/tasks/${encodeURIComponent(id)}/${action}`, { method: 'POST', body: JSON.stringify(body) });
      await load();
    }

    async function askChat(event) {
      event.preventDefault();
      const prompt = $('chatPrompt').value.trim();
      if (!prompt) return;
      const nodes = [...document.querySelectorAll('input[name="chatNode"]:checked')].map((item) => item.value);
      const execute = $('chatExecute').checked;
      $('chatMode').textContent = execute ? 'execute' : 'dry-run';
      $('chatStatus').textContent = 'running...';
      $('chatAskBtn').disabled = true;
      try {
        const result = await api('/api/chat/ask', {
          method: 'POST',
          body: JSON.stringify({
            prompt,
            nodes,
            execute,
            no_llm: $('chatNoLlm').checked,
          }),
        });
        await loadChatHistory();
        $('chatStatus').textContent = result.ok ? 'ok' : 'failed';
      } catch (error) {
        $('chatStatus').textContent = error.message;
        state.chatMessages.push({ role: 'system', content: error.message, detail: { prompt, execute, error: error.message }, attachments: [] });
        renderChatHistory();
      } finally {
        $('chatAskBtn').disabled = false;
      }
    }

    document.addEventListener('click', (event) => {
      const action = event.target.dataset.action;
      const id = event.target.dataset.id;
      const view = event.target.dataset.view;
      if (action && id) taskAction(id, action).catch((error) => alert(error.message));
      if (view) applyView(view);
    });
    $('refreshBtn').addEventListener('click', () => load().catch((error) => alert(error.message)));
    $('scannerBtn').addEventListener('click', () => window.open('/scanner', '_blank'));
    $('sprintFilter').addEventListener('change', () => load().catch((error) => alert(error.message)));
    $('queueFilter').addEventListener('change', () => load().catch((error) => alert(error.message)));
    $('chatForm').addEventListener('submit', askChat);
    $('chatExecute').addEventListener('change', () => {
      $('chatMode').textContent = $('chatExecute').checked ? 'execute' : 'dry-run';
    });
    renderChatHistory();
    setInterval(() => loadChatHistory().catch(() => {}), 4000);
    load().catch((error) => {
      $('contextLine').textContent = error.message;
    });
  </script>
</body>
</html>
"""


SCANNER_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>urirun phone scanner</title>
  <style>
    :root { color-scheme: dark; --bg:#0b0f14; --panel:#111827; --ink:#f8fafc; --muted:#94a3b8; --line:#334155; --accent:#14b8a6; --bad:#f87171; }
    * { box-sizing: border-box; }
    body { margin:0; font:15px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--ink); }
    header { padding:12px 14px; border-bottom:1px solid var(--line); display:flex; justify-content:space-between; gap:10px; align-items:center; }
    h1 { margin:0; font-size:18px; }
    main { display:grid; gap:12px; padding:12px; }
    video, canvas { width:100%; max-height:72vh; object-fit:contain; background:#000; border:1px solid var(--line); border-radius:8px; }
    .controls { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
    button, select, input { min-height:44px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--ink); font:inherit; padding:0 12px; }
    button.primary { background:var(--accent); border-color:var(--accent); color:#042f2e; font-weight:700; }
    button:disabled { opacity:.55; }
    .status { color:var(--muted); overflow-wrap:anywhere; }
    .error { color:var(--bad); }
  </style>
</head>
<body>
  <header>
    <h1>urirun phone scanner</h1>
    <span class="status" id="state">idle</span>
  </header>
  <main>
    <video id="video" autoplay playsinline muted></video>
    <canvas id="canvas" hidden></canvas>
    <div class="controls">
      <button class="primary" id="start">Start camera</button>
      <button class="primary" id="capture" disabled>Scan now</button>
      <select id="quality">
        <option value="0.92">JPEG 92%</option>
        <option value="0.82">JPEG 82%</option>
        <option value="0.70">JPEG 70%</option>
      </select>
      <label><input type="checkbox" id="auto"> auto every 5s</label>
    </div>
    <p class="status">Use this page from the phone on the same LAN. Mobile browsers usually require HTTPS or a trusted local exception for camera access.</p>
  </main>
  <script>
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const state = document.getElementById('state');
    const startBtn = document.getElementById('start');
    const captureBtn = document.getElementById('capture');
    const auto = document.getElementById('auto');
    let stream = null;
    let timer = null;

    function setState(text, error=false) {
      state.textContent = text;
      state.className = error ? 'status error' : 'status';
    }

    async function announce(event, extra={}) {
      try {
        await fetch('/api/scanner/session', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            event,
            href: location.href,
            width: window.innerWidth,
            height: window.innerHeight,
            userAgent: navigator.userAgent,
            at: new Date().toISOString(),
            ...extra
          })
        });
      } catch (_) {}
    }

    async function startCamera() {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 2560 },
          height: { ideal: 1440 }
        }
      });
      video.srcObject = stream;
      captureBtn.disabled = false;
      setState('camera ready');
      await announce('camera-started', {tracks: stream.getVideoTracks().map((track) => track.label)});
    }

    async function capture() {
      if (!stream) return;
      const w = video.videoWidth || 1920;
      const h = video.videoHeight || 1080;
      canvas.width = w;
      canvas.height = h;
      canvas.getContext('2d').drawImage(video, 0, 0, w, h);
      const quality = Number(document.getElementById('quality').value || '0.92');
      const image = canvas.toDataURL('image/jpeg', quality);
      setState(`uploading ${w}x${h}...`);
      const response = await fetch('/api/scanner/capture', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          source: 'phone',
          image,
          width: w,
          height: h,
          userAgent: navigator.userAgent,
          capturedAt: new Date().toISOString()
        })
      });
      const data = await response.json();
      if (!response.ok || data.ok === false) throw new Error(data.error || response.statusText);
      setState(`saved ${data.artifact && data.artifact.path ? data.artifact.path : data.uri}`);
    }

    announce('open');
    startBtn.addEventListener('click', () => startCamera().catch((err) => setState(err.message, true)));
    captureBtn.addEventListener('click', () => capture().catch((err) => setState(err.message, true)));
    auto.addEventListener('change', () => {
      clearInterval(timer);
      timer = auto.checked ? setInterval(() => capture().catch((err) => setState(err.message, true)), 5000) : null;
    });
  </script>
</body>
</html>
"""


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler: BaseHTTPRequestHandler, html: str = INDEX_HTML) -> None:
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8") or "{}")


def _file_response(handler: BaseHTTPRequestHandler, path: str, project: str) -> None:
    source = Path(path).expanduser().resolve()
    allowed_roots = [
        Path(project).expanduser().resolve(),
        Path("~/.urirun").expanduser().resolve(),
        Path(os.environ.get("URIRUN_ARTIFACT_DIR", "~/.urirun/artifacts")).expanduser().resolve(),
    ]
    if not any(source == root or source.is_relative_to(root) for root in allowed_roots):
        _json_response(handler, 403, {"ok": False, "error": "file is outside dashboard preview roots"})
        return
    if not source.is_file():
        _json_response(handler, 404, {"ok": False, "error": "file not found"})
        return
    mime = mimetypes.guess_type(str(source))[0] or "application/octet-stream"
    body = source.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _preview_url(path: str, project: str) -> str | None:
    try:
        source = Path(path).expanduser().resolve()
        roots = [
            Path(project).expanduser().resolve(),
            Path("~/.urirun").expanduser().resolve(),
            Path(os.environ.get("URIRUN_ARTIFACT_DIR", "~/.urirun/artifacts")).expanduser().resolve(),
        ]
        if source.is_file() and any(source == root or source.is_relative_to(root) for root in roots):
            return f"/api/file?path={quote(str(source))}"
    except Exception:  # noqa: BLE001
        return None
    return None


def _is_image_path(path: str) -> bool:
    return Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _collect_attachments(value: Any, project: str, *, limit: int = 24) -> list[dict]:
    """Find screenshot/photo/OCR artifacts in a URI result tree for chat rendering."""
    attachments: list[dict] = []
    seen: set[str] = set()

    def add(path: str, *, kind: str = "file", meta: dict | None = None, uri: str = "") -> None:
        if not path or path in seen or len(attachments) >= limit:
            return
        seen.add(path)
        item = {
            "kind": "image" if _is_image_path(path) else kind,
            "path": path,
            "uri": uri,
            "meta": meta or {},
        }
        preview = _preview_url(path, project)
        if preview:
            item["previewUrl"] = preview
        attachments.append(item)

    def walk(node: Any, hint: str = "") -> None:
        if len(attachments) >= limit:
            return
        if isinstance(node, dict):
            if node.get("artifactPath"):
                add(str(node["artifactPath"]), kind="artifact", meta=node, uri=str(node.get("uri") or ""))
            if node.get("path") and any(word in hint.lower() for word in ("photo", "image", "screenshot", "artifact", "scan")):
                add(str(node["path"]), kind=hint or "file", meta=node, uri=str(node.get("uri") or ""))
            if node.get("cropPath"):
                add(str(node["cropPath"]), kind="crop", meta=node)
            for key in ("photo", "screenshot", "image", "object", "inspection"):
                child = node.get(key)
                if isinstance(child, dict):
                    walk(child, key)
                elif isinstance(child, str) and ("/" in child or "\\" in child):
                    add(child, kind=key)
            for key, child in node.items():
                if key in {"bytes_b64", "base64", "data"}:
                    continue
                walk(child, str(key))
        elif isinstance(node, list):
            for item in node:
                walk(item, hint)

    walk(value)
    return attachments


def _chat_message(role: str, content: str, *, detail: dict | None = None, attachments: list[dict] | None = None) -> dict:
    return {
        "role": role,
        "content": content,
        "detail": detail or {},
        "attachments": attachments or [],
    }


def _add_chat_message(db: str | None, message: dict) -> dict | None:
    try:
        return _host_db().add_log(db, "chat", "message", message)
    except Exception:  # noqa: BLE001
        return None


def chat_history(db: str | None, project: str, limit: int = 80) -> dict:
    host_db = _host_db()
    fetch_limit = max(limit * 4, limit)
    logs = list(reversed(host_db.recent_logs(db, stream="chat", limit=fetch_limit)))
    messages = []
    for item in logs:
        if item.get("event") != "message":
            continue
        detail = item.get("detail") or {}
        msg = dict(detail)
        msg.setdefault("created_at", item.get("created_at"))
        msg.setdefault("id", item.get("id"))
        messages.append(msg)
    return {"ok": True, "messages": messages[-limit:]}


def _local_image_ocr(path: str) -> dict:
    if not shutil_which("tesseract"):
        return {"ok": False, "backend": "none", "error": "tesseract is not installed on host"}
    import subprocess

    proc = subprocess.run(["tesseract", path, "stdout", "-l", "eng+pol"],
                          capture_output=True, text=True, timeout=90, check=False)
    if proc.returncode != 0:
        proc = subprocess.run(["tesseract", path, "stdout"],
                              capture_output=True, text=True, timeout=90, check=False)
    if proc.returncode != 0:
        return {"ok": False, "backend": "tesseract", "error": (proc.stderr or "").strip()}
    text = proc.stdout.strip()
    return {"ok": True, "backend": "tesseract", "text": text, "chars": len(text)}


def shutil_which(binary: str) -> str | None:
    import shutil
    return shutil.which(binary)


def _lan_host() -> str:
    configured = os.environ.get("URIRUN_DASHBOARD_PUBLIC_HOST")
    if configured:
        return configured
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        host = sock.getsockname()[0]
        if host and not host.startswith("127."):
            return host
    except OSError:
        pass
    finally:
        sock.close()
    try:
        host = socket.gethostbyname(socket.gethostname())
        if host and not host.startswith("127."):
            return host
    except OSError:
        pass
    return "127.0.0.1"


def _url_host(host: str) -> str:
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def _public_base_url(scheme: str, host: str, port: int) -> str:
    explicit = os.environ.get("URIRUN_DASHBOARD_PUBLIC_URL")
    if explicit:
        return explicit.rstrip("/")
    bind_host = (host or "127.0.0.1").strip("[]")
    if bind_host in {"", "0.0.0.0", "::"}:
        public_host = _lan_host()
    else:
        public_host = bind_host
    return f"{scheme}://{_url_host(public_host)}:{port}"


def _write_qr_png(url: str, path: Path) -> None:
    import qrcode

    path.parent.mkdir(parents=True, exist_ok=True)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    image.save(path)


def startup_phone_qr(project: str, db: str | None, *, scheme: str, host: str, port: int,
                     qr_url: str | None = None, content_prefix: str = "Phone scanner QR ready") -> dict:
    base_url = _public_base_url(scheme, host, port)
    scanner_url = (qr_url or os.environ.get("URIRUN_DASHBOARD_QR_URL") or f"{base_url}/scanner").strip()
    digest = hashlib.sha256(scanner_url.encode("utf-8")).hexdigest()
    root = Path(os.environ.get("URIRUN_DASHBOARD_QR_DIR", "~/.urirun/host-dashboard/qr")).expanduser()
    path = root / f"phone-scanner-{digest[:12]}.png"
    bind_host = (host or "").strip("[]")
    reachable_from_phone = bind_host not in {"127.0.0.1", "localhost", "::1"}
    secure_camera_context = scanner_url.startswith("https://") or scanner_url.startswith("http://127.0.0.1") or scanner_url.startswith("http://localhost")
    meta = {
        "url": scanner_url,
        "dashboardUrl": f"{base_url}/",
        "scannerUrl": scanner_url,
        "bindHost": host,
        "port": port,
        "scheme": scheme,
        "reachableFromPhone": reachable_from_phone,
        "secureCameraContext": secure_camera_context,
    }
    uri = f"dashboard://host/qr/{digest[:16]}"
    attachment = None
    try:
        _write_qr_png(scanner_url, path)
        artifact = _host_db().register_artifact(db, "dashboard-qr", uri, str(path), meta)
        attachment = {
            "kind": "qr-code",
            "path": str(path),
            "uri": uri,
            "previewUrl": _preview_url(str(path), project),
            "meta": meta,
        }
    except Exception as exc:  # noqa: BLE001 - QR is helpful, not required for serving.
        artifact = {"kind": "dashboard-qr", "uri": uri, "path": None, "meta": {**meta, "error": str(exc)}}

    content = f"{content_prefix}: {scanner_url}"
    if not reachable_from_phone:
        content += " (dashboard is bound to loopback; use --host 0.0.0.0 for phone access)"
    elif not secure_camera_context:
        content += " (phone camera usually needs HTTPS)"
    message = _chat_message(
        "system",
        content,
        detail={"uri": uri, "url": scanner_url, "artifact": artifact, "metadata": meta},
        attachments=[attachment] if attachment else [],
    )
    _add_chat_message(db, message)
    return {"ok": True, "uri": uri, "url": scanner_url, "artifact": artifact, "message": message}


def _ensure_tls_cert(cert: str, key: str) -> tuple[str, str]:
    cert_path = Path(cert).expanduser()
    key_path = Path(key).expanduser()
    if cert_path.is_file() and key_path.is_file():
        return str(cert_path), str(key_path)
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key_path),
            "-out", str(cert_path),
            "-days", "365",
            "-subj", "/CN=urirun-dashboard.local",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return str(cert_path), str(key_path)


def _probe_scanner_url(url: str, timeout: float = 1.5) -> bool:
    import urllib.request

    try:
        context = ssl._create_unverified_context() if url.startswith("https://") else None
        with urllib.request.urlopen(url, timeout=timeout, context=context) as response:
            return 200 <= int(response.status) < 500
    except Exception:  # noqa: BLE001
        return False


def _nl_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _is_phone_scanner_prompt(prompt: str) -> bool:
    text = _nl_text(prompt)
    scanner_terms = (
        "skaner", "scanner", "skan", "scan", "kamera", "camera", "telefon", "phone", "mobile", "mobil",
        "webrtc", "qr", "qrcode", "paragon", "rachunek",
    )
    service_terms = ("aplikac", "uslug", "service", "stron", "narzedz", "interfejs")
    start_terms = (
        "uruchom", "wystart", "stworz", "utworz", "start", "create", "open", "wlacz", "odpal", "daj",
        "pokaz", "link", "adres", "ip", "qr",
    )
    wants_scanner = any(word in text for word in scanner_terms)
    wants_service = any(word in text for word in service_terms)
    wants_start = any(word in text for word in start_terms)
    mobile_context = any(word in text for word in ("telefon", "phone", "mobile", "mobil", "webrtc", "kamera", "camera", "qr", "skaner", "scanner"))
    return wants_start and (wants_scanner or (wants_service and mobile_context))


def ensure_phone_scanner_service(
    project: str,
    db: str | None,
    config: str | None = None,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
    *,
    host: str | None = None,
    port: int | None = None,
    tls_cert: str | None = None,
    tls_key: str | None = None,
) -> dict:
    bind_host = host or os.environ.get("URIRUN_PHONE_SCANNER_HOST", "0.0.0.0")
    scanner_port = int(port or os.environ.get("URIRUN_PHONE_SCANNER_PORT", "8196"))
    cert = tls_cert or os.environ.get("URIRUN_PHONE_SCANNER_TLS_CERT", "~/.urirun/certs/urirun-dashboard.crt")
    key = tls_key or os.environ.get("URIRUN_PHONE_SCANNER_TLS_KEY", "~/.urirun/certs/urirun-dashboard.key")
    cert, key = _ensure_tls_cert(cert, key)
    scanner_url = f"https://{_url_host(_lan_host())}:{scanner_port}/scanner"
    service_id = f"https://{bind_host}:{scanner_port}"

    with _SERVICE_LOCK:
        server = _SERVICE_SERVERS.get(service_id)
        thread = _SERVICE_THREADS.get(service_id)
        if server is not None and thread is not None and thread.is_alive():
            status = "already-running"
        elif _probe_scanner_url(scanner_url):
            status = "external-running"
        else:
            server = serve(
                project=project,
                db=db,
                config=config,
                host=bind_host,
                port=scanner_port,
                node_urls=node_urls,
                token=token,
                identity=identity,
                tls_cert=cert,
                tls_key=key,
                startup_qr=False,
            )
            thread = threading.Thread(target=server.serve_forever, name=f"urirun-phone-scanner-{scanner_port}", daemon=True)
            thread.start()
            _SERVICE_SERVERS[service_id] = server
            _SERVICE_THREADS[service_id] = thread
            status = "started"

    qr = startup_phone_qr(
        project,
        db,
        scheme="https",
        host=bind_host,
        port=scanner_port,
        qr_url=scanner_url,
        content_prefix="Phone scanner service ready",
    )
    meta = {
        "status": status,
        "service": "phone-scanner",
        "url": scanner_url,
        "bindHost": bind_host,
        "hostIp": _lan_host(),
        "port": scanner_port,
        "tlsCert": cert,
    }
    try:
        _host_db().add_log(db, "service", "phone-scanner", meta)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, **meta, "qr": qr, "message": qr.get("message")}


def _auto_crop_receipt(path: Path) -> dict:
    try:
        from PIL import Image, ImageOps
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"pillow unavailable: {exc}"}

    try:
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"image decode failed: {exc}"}

    width, height = image.size
    if width < 80 or height < 80:
        return {"ok": False, "reason": "image too small", "width": width, "height": height}

    max_side = 900
    scale = min(1.0, max_side / max(width, height))
    analysis = image.resize((max(1, int(width * scale)), max(1, int(height * scale)))) if scale < 1.0 else image
    aw, ah = analysis.size
    pixels = analysis.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(ah):
        for x in range(aw):
            r, g, b = pixels[x, y]
            hi = max(r, g, b)
            lo = min(r, g, b)
            lum = (299 * r + 587 * g + 114 * b) // 1000
            sat = hi - lo
            if (lum >= 150 and sat <= 70) or lum >= 215:
                xs.append(x)
                ys.append(y)

    coverage = len(xs) / float(aw * ah)
    if coverage < 0.035:
        return {"ok": False, "reason": "not enough receipt-like pixels", "coverage": round(coverage, 4)}

    xs.sort()
    ys.sort()

    def quantile(values: list[int], q: float) -> int:
        return values[min(len(values) - 1, max(0, int(len(values) * q)))]

    left = quantile(xs, 0.01)
    right = quantile(xs, 0.99)
    top = quantile(ys, 0.01)
    bottom = quantile(ys, 0.99)
    bw = max(1, right - left + 1)
    bh = max(1, bottom - top + 1)
    bbox_area = (bw * bh) / float(aw * ah)
    if bbox_area < 0.08:
        return {"ok": False, "reason": "detected region too small", "coverage": round(coverage, 4), "bboxArea": round(bbox_area, 4)}
    if bbox_area > 0.96:
        return {"ok": False, "reason": "receipt already fills frame", "coverage": round(coverage, 4), "bboxArea": round(bbox_area, 4)}

    pad_x = max(4, int(bw * 0.035))
    pad_y = max(4, int(bh * 0.035))
    left = max(0, left - pad_x)
    top = max(0, top - pad_y)
    right = min(aw - 1, right + pad_x)
    bottom = min(ah - 1, bottom + pad_y)

    inv_scale = 1.0 / scale
    box = (
        max(0, int(left * inv_scale)),
        max(0, int(top * inv_scale)),
        min(width, int((right + 1) * inv_scale)),
        min(height, int((bottom + 1) * inv_scale)),
    )
    if box[2] - box[0] < 50 or box[3] - box[1] < 50:
        return {"ok": False, "reason": "crop too small", "box": list(box)}
    if box[0] <= 3 and box[1] <= 3 and box[2] >= width - 3 and box[3] >= height - 3:
        return {"ok": False, "reason": "crop equals original", "box": list(box)}

    crop = image.crop(box)
    crop_path = path.with_name(f"{path.stem}-receipt-crop.jpg")
    crop.save(crop_path, format="JPEG", quality=94, optimize=True)
    return {
        "ok": True,
        "path": str(crop_path),
        "box": list(box),
        "coverage": round(coverage, 4),
        "bboxArea": round(bbox_area, 4),
        "originalWidth": width,
        "originalHeight": height,
        "width": crop.size[0],
        "height": crop.size[1],
    }


def scanner_capture(project: str, db: str | None, payload: dict) -> dict:
    raw_image = str(payload.get("image") or "")
    match = re.match(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", raw_image, re.S)
    if not match:
        raise ValueError("image must be a data:image/*;base64 payload")
    mime, encoded = match.group(1), match.group(2)
    raw = base64.b64decode(encoded.encode("ascii"), validate=False)
    digest = hashlib.sha256(raw).hexdigest()
    ext = ".jpg" if mime in {"image/jpeg", "image/jpg"} else ".png" if mime == "image/png" else ".bin"
    root = Path(os.environ.get("URIRUN_SCANNER_DIR", "~/.urirun/host-dashboard/scans")).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    name = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-phone-scan-{digest[:12]}{ext}"
    path = root / name
    path.write_bytes(raw)
    crop = _auto_crop_receipt(path)
    display_path = Path(crop["path"]) if crop.get("ok") and crop.get("path") else path
    ocr = _local_image_ocr(str(display_path))
    meta = {
        "source": payload.get("source") or "phone",
        "width": payload.get("width"),
        "height": payload.get("height"),
        "mime": mime,
        "sha256": digest,
        "bytes": len(raw),
        "originalPath": str(path),
        "displayPath": str(display_path),
        "crop": crop,
        "capturedAt": payload.get("capturedAt"),
        "userAgent": payload.get("userAgent", ""),
        "ocr": ocr,
    }
    uri = f"scanner://host/capture/{digest[:16]}"
    artifact = _host_db().register_artifact(db, "camera-scan", uri, str(display_path), meta)
    attachment = {
        "kind": "receipt-crop" if crop.get("ok") else "image",
        "path": str(display_path),
        "uri": uri,
        "previewUrl": _preview_url(str(display_path), project),
        "meta": meta,
    }
    content = "Phone scan saved"
    if crop.get("ok"):
        content += " (cropped to receipt)"
    if ocr.get("ok") and ocr.get("text"):
        content += f": {str(ocr.get('text'))[:180]}"
    elif ocr.get("error"):
        content += f" (OCR: {ocr.get('error')})"
    message = _chat_message("system", content, detail={"artifact": artifact, "uri": uri, "ocr": ocr}, attachments=[attachment])
    _add_chat_message(db, message)
    return {"ok": True, "uri": uri, "artifact": artifact, "ocr": ocr, "message": message}


def scanner_session(db: str | None, payload: dict) -> dict:
    event = str(payload.get("event") or "open")
    fingerprint = json.dumps({
        "event": event,
        "userAgent": payload.get("userAgent", ""),
        "href": payload.get("href", ""),
        "at": payload.get("at", ""),
    }, sort_keys=True)
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    uri = f"scanner://host/session/{digest[:16]}"
    detail = {
        "uri": uri,
        "event": event,
        "href": payload.get("href"),
        "width": payload.get("width"),
        "height": payload.get("height"),
        "userAgent": payload.get("userAgent", ""),
        "at": payload.get("at"),
        "tracks": payload.get("tracks") or [],
    }
    label = "Phone scanner opened" if event == "open" else "Phone scanner camera started" if event == "camera-started" else f"Phone scanner {event}"
    message = _chat_message("system", label, detail=detail)
    _add_chat_message(db, message)
    return {"ok": True, "uri": uri, "message": message}


def _first(query: dict[str, list[str]], name: str, default: str | None = None) -> str | None:
    values = query.get(name)
    return values[0] if values else default


def _host_db():
    from urirun import host_db

    return host_db


def _mesh():
    from urirun import mesh

    return mesh


def _planfile_adapter():
    from urirun import planfile_adapter

    return planfile_adapter


def _host_config(config: str | None, node_urls: list[str] | None = None) -> dict:
    mesh = _mesh()
    loaded = mesh.load_host_config(config)
    return mesh.config_with_transient_node_urls(loaded, node_urls or [])


def _safe_tickets(project: str, sprint: str = "current", status: str | None = None, queue: str | None = None) -> tuple[list[dict], str | None]:
    try:
        return _planfile_adapter().list_tickets(project, sprint=sprint, status=status, queue=queue), None
    except Exception as exc:  # noqa: BLE001 - dashboard should stay up while optional stores are missing.
        return [], str(exc)


def _task_counts(tickets: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ticket in tickets:
        status = str(ticket.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def summary(project: str, db: str | None, config: str | None, node_urls: list[str] | None = None) -> dict:
    tickets, task_error = _safe_tickets(project, sprint="all")
    host_db = _host_db()
    mesh = _mesh()
    try:
        discovered = mesh.discover_mesh(_host_config(config, node_urls))
    except Exception as exc:  # noqa: BLE001
        discovered = {"nodes": [], "routes": [], "serviceMap": {}, "error": str(exc)}
    checks = host_db.recent_checks(db, limit=10)
    artifacts = host_db.list_artifacts(db, limit=10)
    logs = host_db.recent_logs(db, limit=10)
    nodes = discovered.get("nodes") or []
    routes = discovered.get("routes") or []
    return {
        "ok": True,
        "project": str(Path(project).expanduser().resolve()),
        "db": str(host_db.db_path(db)),
        "config": str(mesh.host_config_path(config)),
        "taskError": task_error,
        "taskCounts": _task_counts(tickets),
        "ticketCount": len(tickets),
        "nodeCount": len(nodes),
        "nodesOnline": len([node for node in nodes if node.get("reachable")]),
        "routeCount": len(routes),
        "nodes": nodes,
        "routes": routes,
        "checks": checks,
        "artifacts": artifacts,
        "logs": logs,
    }


def _compact_chat_result(result: dict, payload: dict) -> dict:
    if payload.get("inline_artifacts") or payload.get("inlineArtifacts"):
        return result
    from urirun.node._artifacts import materialize_base64_artifacts

    compacted, artifacts = materialize_base64_artifacts(
        result,
        artifact_dir=payload.get("artifact_dir") or payload.get("artifactDir"),
        hint="host-chat",
    )
    if artifacts:
        compacted = dict(compacted)
        compacted["artifacts"] = artifacts
    return compacted


def chat_ask(project: str, db: str | None, config: str | None, payload: dict, node_urls: list[str] | None = None,
             token: str | None = None, identity: str | None = None) -> dict:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    selected_nodes = [str(item).strip() for item in (payload.get("nodes") or []) if str(item).strip()]
    execute = bool(payload.get("execute"))
    no_llm = bool(payload.get("no_llm") or payload.get("noLlm"))
    _add_chat_message(db, _chat_message(
        "user",
        prompt,
        detail={"execute": execute, "selectedNodes": selected_nodes, "noLlm": no_llm},
    ))
    if _is_phone_scanner_prompt(prompt):
        service = ensure_phone_scanner_service(
            project,
            db,
            config=config,
            node_urls=node_urls,
            token=token,
            identity=identity,
        )
        result = {
            "ok": bool(service.get("ok")),
            "prompt": prompt,
            "execute": True,
            "selectedNodes": selected_nodes,
            "generator": {"provider": "host-dashboard", "intent": "phone-scanner-service"},
            "flow": {
                "task": {"id": "phone-scanner-service", "title": "Start phone scanner service"},
                "steps": [{"id": "start-phone-scanner", "uri": "dashboard://host/phone-scanner/command/start", "payload": {}}],
            },
            "timeline": [{
                "id": "start-phone-scanner",
                "uri": "dashboard://host/phone-scanner/command/start",
                "target": "host",
                "ok": bool(service.get("ok")),
                "status": service.get("status"),
            }],
            "results": {"phone-scanner-service": service},
            "attachments": ((service.get("message") or {}).get("attachments") or []),
        }
        try:
            _host_db().add_log(
                db,
                "chat",
                "ask",
                {
                    "prompt": prompt,
                    "execute": True,
                    "ok": result.get("ok"),
                    "selectedNodes": selected_nodes,
                    "generator": result.get("generator"),
                    "timeline": result.get("timeline") or [],
                },
            )
        except Exception:
            pass
        return result
    mesh = _mesh()
    old_token = os.environ.get("URIRUN_RUN_TOKEN")
    old_identity = os.environ.get("URIRUN_RUN_IDENTITY")
    if token:
        os.environ["URIRUN_RUN_TOKEN"] = token
        os.environ.pop("URIRUN_RUN_IDENTITY", None)
    elif identity:
        os.environ["URIRUN_RUN_IDENTITY"] = os.path.expanduser(identity)
        os.environ.pop("URIRUN_RUN_TOKEN", None)
    try:
        discovered = mesh.discover_mesh(_host_config(config, node_urls))
        flow, generator = mesh.make_flow(prompt, discovered, selected_nodes=selected_nodes, use_llm=not no_llm)
        registry = mesh.registry_from_routes(discovered.get("routes") or [])
        execution = mesh.execute_flow(flow, discovered, registry, execute=execute)
    finally:
        if old_token is None:
            os.environ.pop("URIRUN_RUN_TOKEN", None)
        else:
            os.environ["URIRUN_RUN_TOKEN"] = old_token
        if old_identity is None:
            os.environ.pop("URIRUN_RUN_IDENTITY", None)
        else:
            os.environ["URIRUN_RUN_IDENTITY"] = old_identity
    result = {
        "ok": bool(execution.get("ok")),
        "prompt": prompt,
        "execute": execute,
        "selectedNodes": selected_nodes,
        "generator": generator,
        "nodeCount": len(discovered.get("nodes") or []),
        "routeCount": len(discovered.get("routes") or []),
        "flow": flow,
        **execution,
    }
    result = _compact_chat_result(result, payload)
    attachments = _collect_attachments(result, project)
    result["attachments"] = attachments
    timeline = result.get("timeline") or []
    status = "ok" if result.get("ok") else "failed"
    content = f"{status}: {len(timeline)} URI step(s)"
    if attachments:
        content += f", {len(attachments)} attachment(s)"
    _add_chat_message(db, _chat_message(
        "system",
        content,
        detail={
            "prompt": prompt,
            "execute": execute,
            "ok": result.get("ok"),
            "generator": generator,
            "flow": flow,
            "timeline": timeline,
            "results": result.get("results") or {},
            "error": result.get("error"),
        },
        attachments=attachments,
    ))
    try:
        _host_db().add_log(
            db,
            "chat",
            "ask",
            {
                "prompt": prompt,
                "execute": execute,
                "ok": result.get("ok"),
                "selectedNodes": selected_nodes,
                "generator": generator,
                "timeline": result.get("timeline") or [],
            },
        )
    except Exception:
        pass
    return result


def task_action(project: str, ticket_id: str, action: str, payload: dict) -> dict:
    planfile_adapter = _planfile_adapter()
    if action == "start":
        ticket = planfile_adapter.start_ticket(project, ticket_id, assigned_to=payload.get("assigned_to"))
    elif action == "complete":
        ticket = planfile_adapter.complete_ticket(project, ticket_id, note=payload.get("note"), result=payload.get("result"), artifacts=payload.get("artifacts"))
    elif action == "block":
        ticket = planfile_adapter.update_ticket(project, ticket_id, {"status": "blocked", "description": str(payload.get("reason") or "Blocked from dashboard")})
    elif action == "ready":
        ticket = planfile_adapter.ready_ticket(project, ticket_id, note=payload.get("note"))
    elif action == "fail":
        ticket = planfile_adapter.fail_ticket(project, ticket_id, str(payload.get("error") or "failed from dashboard"))
    else:
        raise ValueError(f"unsupported task action: {action}")
    return {"ok": True, "ticket": ticket}


def _dashboard_api_response(path: str, project: str, db: str | None, config: str | None, query: dict, node_urls: list[str] | None = None) -> tuple[int, dict]:
    """Resolve a dashboard /api/* path to an (HTTP status, JSON payload) pair."""
    if path == "/api/summary":
        return 200, summary(project, db, config, node_urls=node_urls)
    if path == "/api/tasks":
        tickets, error = _safe_tickets(
            project,
            sprint=str(_first(query, "sprint", "current")),
            status=_first(query, "status"),
            queue=_first(query, "queue") or None,
        )
        return 200, {"ok": error is None, "tickets": tickets, "error": error}
    if path in {"/api/nodes", "/api/routes"}:
        mesh = _mesh()
        discovered = mesh.discover_mesh(_host_config(config, node_urls))
        key = "nodes" if path == "/api/nodes" else "routes"
        return 200, {"ok": True, key: discovered.get(key) or []}
    if path == "/api/checks":
        host_db = _host_db()
        return 200, {"ok": True, "checks": host_db.recent_checks(db, subject=_first(query, "subject"), limit=int(_first(query, "limit", "20") or 20))}
    if path == "/api/logs":
        host_db = _host_db()
        return 200, {"ok": True, "logs": host_db.recent_logs(db, stream=_first(query, "stream"), limit=int(_first(query, "limit", "20") or 20))}
    if path == "/api/artifacts":
        host_db = _host_db()
        return 200, {"ok": True, "artifacts": host_db.list_artifacts(db, kind=_first(query, "kind"), limit=int(_first(query, "limit", "20") or 20))}
    if path == "/api/chat/history":
        return 200, chat_history(db, project, limit=int(_first(query, "limit", "80") or 80))
    return 404, {"ok": False, "error": "not found"}


def create_handler(
    project: str,
    db: str | None = None,
    config: str | None = None,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
):
    class Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            _json_response(self, 200, {"ok": True})

        def do_GET(self):
            parsed = urlparse(self.path)
            try:
                if parsed.path in {"/", "/index.html"}:
                    _html_response(self)
                    return
                if parsed.path == "/scanner":
                    _html_response(self, SCANNER_HTML)
                    return
                if parsed.path == "/api/file":
                    path = _first(parse_qs(parsed.query), "path")
                    if not path:
                        _json_response(self, 400, {"ok": False, "error": "path is required"})
                        return
                    _file_response(self, unquote(path), project)
                    return
                status, payload = _dashboard_api_response(parsed.path, project, db, config, parse_qs(parsed.query), node_urls=node_urls)
                _json_response(self, status, payload)
            except Exception as exc:  # noqa: BLE001
                _json_response(self, 500, {"ok": False, "error": str(exc)})

        def do_POST(self):
            parsed = urlparse(self.path)
            parts = [part for part in parsed.path.split("/") if part]
            try:
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "tasks":
                    payload = _read_json(self)
                    _json_response(self, 200, task_action(project, parts[2], parts[3], payload))
                    return
                if parsed.path == "/api/chat/ask":
                    payload = _read_json(self)
                    _json_response(self, 200, chat_ask(project, db, config, payload, node_urls=node_urls,
                                                       token=token, identity=identity))
                    return
                if parsed.path == "/api/scanner/capture":
                    payload = _read_json(self)
                    _json_response(self, 200, scanner_capture(project, db, payload))
                    return
                if parsed.path == "/api/scanner/session":
                    payload = _read_json(self)
                    _json_response(self, 200, scanner_session(db, payload))
                    return
                _json_response(self, 404, {"ok": False, "error": "not found"})
            except Exception as exc:  # noqa: BLE001
                _json_response(self, 400, {"ok": False, "error": str(exc)})

        def log_message(self, fmt, *args: Any):
            return

    return Handler


def serve(
    project: str = ".",
    db: str | None = None,
    config: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8194,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
    tls_cert: str | None = None,
    tls_key: str | None = None,
    startup_qr: bool = False,
    qr_url: str | None = None,
) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), create_handler(project, db=db, config=config, node_urls=node_urls,
                                                             token=token, identity=identity))
    scheme = "http"
    if tls_cert and tls_key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(os.path.expanduser(tls_cert), os.path.expanduser(tls_key))
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    qr = startup_phone_qr(project, db, scheme=scheme, host=host, port=server.server_address[1], qr_url=qr_url) if startup_qr else None
    print(json.dumps({
        "event": "urirun.host_dashboard.started",
        "url": f"{scheme}://{host}:{server.server_address[1]}/",
        "qrUrl": qr.get("url") if qr else None,
        "project": str(Path(project).resolve()),
    }), flush=True)
    return server


def command(args) -> int:
    if args.dashboard_command == "serve":
        host = args.host or "127.0.0.1"
        port = int(args.port or 8194)
        startup_qr = bool(getattr(args, "startup_qr", False)) and not bool(getattr(args, "no_startup_qr", False))
        server = serve(project=args.project, db=args.db, config=args.config, host=host, port=port,
                       node_urls=getattr(args, "node_url", None),
                       token=getattr(args, "token", None) or os.environ.get("URIRUN_NODE_TOKEN"),
                       identity=getattr(args, "identity", None),
                       tls_cert=getattr(args, "tls_cert", None),
                       tls_key=getattr(args, "tls_key", None),
                       startup_qr=startup_qr,
                       qr_url=getattr(args, "qr_url", None))
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return 130
        return 0
    if args.dashboard_command == "url":
        host = args.host or "127.0.0.1"
        port = int(args.port or 8194)
        print(f"http://{host}:{port}/")
        return 0
    return 1


def default_host() -> str:
    return socket.gethostbyname(socket.gethostname())
