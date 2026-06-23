# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Small host dashboard for planfile tasks, nodes and urirun activity."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import mimetypes
import os
import re
import socket
import ssl
import subprocess
import textwrap
import threading
import time
import unicodedata
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse


_SERVICE_LOCK = threading.Lock()
_SERVICE_SERVERS: dict[str, ThreadingHTTPServer] = {}
_SERVICE_THREADS: dict[str, threading.Thread] = {}
_DOCUMENT_INDEX_LOCK = threading.Lock()
_SCANNER_BEST_LOCK = threading.Lock()
_SCANNER_BEST_SESSIONS: dict[str, dict] = {}
_PAGE_ACTION_LOCK = threading.Lock()
_PAGE_ACTION_QUEUES: dict[str, list[dict]] = {}


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
    button.active { border-color: var(--accent); box-shadow: inset 0 -2px 0 var(--accent); color: var(--accent); }
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
    .attachment iframe {
      width: 100%;
      height: 220px;
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
    body.chat-fullscreen { overflow: hidden; }
    body.chat-fullscreen .topbar,
    body.chat-fullscreen .metrics,
    body.chat-fullscreen aside,
    body.chat-fullscreen .bottom-nav { display: none; }
    body.chat-fullscreen main {
      width: 100%;
      height: 100vh;
      padding: 10px;
    }
    body.chat-fullscreen .grid {
      height: 100%;
      display: block;
    }
    body.chat-fullscreen .grid > .stack {
      height: 100%;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      gap: 10px;
    }
    body.chat-fullscreen .view-block[data-section="chat"] {
      min-height: 0;
    }
    body.chat-fullscreen .view-block[data-section="chat"]:not(:nth-of-type(-n+2)) {
      display: none !important;
    }
    body.chat-fullscreen .chat-result {
      max-height: none;
      height: calc(100vh - 286px);
    }
    body.chat-fullscreen textarea {
      min-height: 86px;
    }
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
      <span class="pill" id="activeTabPill">overview</span>
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
            <div class="actions">
              <span class="pill" id="chatMode">dry-run</span>
              <button id="chatFullscreenBtn" type="button">Full screen</button>
            </div>
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
    const VALID_VIEWS = new Set(['overview', 'chat', 'tasks', 'nodes', 'activity']);
    const params = new URLSearchParams(window.location.search);
    const initialView = VALID_VIEWS.has(params.get('view')) ? params.get('view') : (VALID_VIEWS.has(params.get('tab')) ? params.get('tab') : 'overview');
    const initialChatFull = params.get('chat') === 'full' || params.get('fullscreen') === 'chat';
    const state = { summary: null, tasks: [], view: initialView, chatMessages: [], chatFullscreen: initialChatFull };
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

    function setParam(search, key, value) {
      if (value === undefined || value === null || value === '') search.delete(key);
      else search.set(key, String(value));
    }

    function currentControlState() {
      return {
        sprint: $('sprintFilter') ? $('sprintFilter').value : '',
        queue: $('queueFilter') ? $('queueFilter').value : '',
        execute: $('chatExecute') && $('chatExecute').checked ? '1' : '',
        no_llm: $('chatNoLlm') && $('chatNoLlm').checked ? '1' : ''
      };
    }

    function renderUrlState() {
      $('activeTabPill').textContent = `tab:${state.view}${state.chatFullscreen ? ' · full' : ''}`;
      document.querySelectorAll('[data-view]').forEach((button) => {
        button.classList.toggle('active', button.dataset.view === state.view);
      });
    }

    function writeUrlState(changes = {}, options = {}) {
      const search = new URLSearchParams(window.location.search);
      const controls = currentControlState();
      setParam(search, 'view', state.view);
      setParam(search, 'tab', state.view);
      setParam(search, 'chat', state.view === 'chat' ? (state.chatFullscreen ? 'full' : 'panel') : '');
      setParam(search, 'sprint', controls.sprint && controls.sprint !== 'current' ? controls.sprint : '');
      setParam(search, 'queue', controls.queue || '');
      setParam(search, 'execute', controls.execute);
      setParam(search, 'no_llm', controls.no_llm);
      Object.entries(changes).forEach(([key, value]) => setParam(search, key, value));
      const query = search.toString();
      const nextUrl = `${window.location.pathname}${query ? '?' + query : ''}${window.location.hash}`;
      const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      if (nextUrl !== currentUrl) {
        const method = options.replace ? 'replaceState' : 'pushState';
        window.history[method]({ view: state.view, chatFullscreen: state.chatFullscreen }, '', nextUrl);
      }
      renderUrlState();
    }

    function applyControlsFromUrl() {
      const search = new URLSearchParams(window.location.search);
      if ($('sprintFilter') && search.get('sprint')) $('sprintFilter').value = search.get('sprint');
      if ($('queueFilter') && search.has('queue')) $('queueFilter').value = search.get('queue') || '';
      if ($('chatExecute')) {
        $('chatExecute').checked = search.get('execute') === '1';
        $('chatMode').textContent = $('chatExecute').checked ? 'execute' : 'dry-run';
      }
      if ($('chatNoLlm')) $('chatNoLlm').checked = search.get('no_llm') === '1';
    }

    function setChatFullscreen(enabled, options = {}) {
      state.chatFullscreen = !!enabled;
      document.body.classList.toggle('chat-fullscreen', state.chatFullscreen);
      $('chatFullscreenBtn').textContent = state.chatFullscreen ? 'Exit full screen' : 'Full screen';
      if (state.chatFullscreen && state.view !== 'chat') {
        state.view = 'chat';
      }
      renderUrlState();
      if (!options.silent) {
        writeUrlState({ action: state.chatFullscreen ? 'chat:fullscreen' : 'chat:panel' });
      }
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
      const isPdf = /\.pdf$/i.test(text(att.path));
      const preview = att.previewUrl
        ? (isPdf
          ? `<iframe src="${esc(att.previewUrl)}" title="${esc(basename(att.path))}" loading="lazy"></iframe>`
          : `<img src="${esc(att.previewUrl)}" alt="${esc(basename(att.path))}" loading="lazy">`)
        : `<div class="subtle">preview unavailable</div>`;
      const download = att.previewUrl ? `<a href="${esc(att.previewUrl)}" download>download</a>` : '';
      const ocrLine = ocr.ok
        ? `<div class="subtle">OCR ${esc(ocr.backend || '')}: ${esc(text(ocr.text).slice(0, 160))}</div>`
        : (ocr.error ? `<div class="subtle">OCR: ${esc(ocr.error)}</div>` : '');
      return `<div class="attachment${qrClass}">
        ${preview}
        <div class="mono">${esc(basename(att.path))}</div>
        <div class="subtle">${esc(att.kind || 'file')} ${meta.width && meta.height ? `· ${meta.width}x${meta.height}` : ''}</div>
        ${download}
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
      if (!VALID_VIEWS.has(view)) view = 'overview';
      state.view = view;
      document.querySelectorAll('.view-block').forEach((block) => {
        block.classList.toggle('hidden', view !== 'overview' && block.dataset.section !== view);
      });
      renderUrlState();
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
      writeUrlState({ action: `task:${action}`, item: id });
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
      state.view = 'chat';
      writeUrlState({ action: 'chat:run', prompt_len: prompt.length, nodes: nodes.join(',') });
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
      if (view) {
        applyView(view);
        writeUrlState({ action: `tab:${view}` });
      }
    });
    $('refreshBtn').addEventListener('click', () => {
      writeUrlState({ action: 'refresh' });
      load().catch((error) => alert(error.message));
    });
    $('scannerBtn').addEventListener('click', () => {
      writeUrlState({ action: 'open:scanner' });
      window.open('/scanner', '_blank');
    });
    $('chatFullscreenBtn').addEventListener('click', () => setChatFullscreen(!state.chatFullscreen));
    $('sprintFilter').addEventListener('change', () => {
      writeUrlState({ action: 'filter:sprint' }, { replace: true });
      load().catch((error) => alert(error.message));
    });
    $('queueFilter').addEventListener('change', () => {
      writeUrlState({ action: 'filter:queue' }, { replace: true });
      load().catch((error) => alert(error.message));
    });
    $('chatForm').addEventListener('submit', askChat);
    $('chatExecute').addEventListener('change', () => {
      $('chatMode').textContent = $('chatExecute').checked ? 'execute' : 'dry-run';
      state.view = 'chat';
      writeUrlState({ action: 'chat:mode' }, { replace: true });
    });
    $('chatNoLlm').addEventListener('change', () => {
      state.view = 'chat';
      writeUrlState({ action: 'chat:planner' }, { replace: true });
    });
    window.addEventListener('popstate', () => {
      const search = new URLSearchParams(window.location.search);
      const nextView = VALID_VIEWS.has(search.get('view')) ? search.get('view') : (VALID_VIEWS.has(search.get('tab')) ? search.get('tab') : 'overview');
      state.view = nextView;
      applyControlsFromUrl();
      setChatFullscreen(search.get('chat') === 'full' || search.get('fullscreen') === 'chat', { silent: true });
      applyView(state.view);
      load().catch((error) => { $('contextLine').textContent = error.message; });
    });
    applyControlsFromUrl();
    setChatFullscreen(state.chatFullscreen, { silent: true });
    applyView(state.view);
    writeUrlState({ action: params.get('action') || 'load' }, { replace: true });
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
    button.remote-click { outline:3px solid #fde68a; outline-offset:2px; }
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
      <button id="torch" disabled>Light off</button>
      <button class="primary" id="capture" disabled>Scan now</button>
      <button class="primary" id="best" disabled>Best PDF</button>
      <select id="bestCount">
        <option value="6">6 frames · 1s</option>
        <option value="4">4 frames · 1s</option>
        <option value="8">8 frames · 1s</option>
      </select>
      <select id="quality">
        <option value="0.92">JPEG 92%</option>
        <option value="0.82">JPEG 82%</option>
        <option value="0.70">JPEG 70%</option>
      </select>
      <label><input type="checkbox" id="startBest" checked> best after start</label>
      <label><input type="checkbox" id="auto"> auto every 1s</label>
    </div>
    <p class="status">Use this page from the phone on the same LAN. Mobile browsers usually require HTTPS or a trusted local exception for camera access.</p>
  </main>
  <script src="/assets/urirun.js"
          data-site="urirun-phone-scanner"
          data-endpoint="/api/uri/event"
          data-action-endpoint="/api/uri/invoke"
          data-load="0"
          data-clicks="0"
          data-forms="0"
          data-spa="0"
          data-debug="1"></script>
  <script>
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const state = document.getElementById('state');
    const startBtn = document.getElementById('start');
    const torchBtn = document.getElementById('torch');
    const captureBtn = document.getElementById('capture');
    const bestBtn = document.getElementById('best');
    const startBest = document.getElementById('startBest');
    const auto = document.getElementById('auto');
    let stream = null;
    let timer = null;
    let bestRunning = false;
    let torchOn = false;
    let startCameraPromise = null;
    let startCameraClickPromise = null;
    let torchClickPromise = null;

    function setState(text, error=false) {
      state.textContent = text;
      state.className = error ? 'status error' : 'status';
    }

    function invokeURI(uri, payload={}) {
      if (window.urirun && typeof window.urirun.invoke === 'function') {
        return window.urirun.invoke(uri, payload);
      }
      return fetch('/api/uri/invoke', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({uri, payload})
      }).then((response) => response.json());
    }

    async function announce(event, extra={}) {
      try {
        await invokeURI('scanner://host/session/command/log', {
          event,
          href: location.href,
          width: window.innerWidth,
          height: window.innerHeight,
          userAgent: navigator.userAgent,
          at: new Date().toISOString(),
          ...extra
        });
      } catch (_) {}
    }

    async function startCamera(options={}) {
      if (stream && stream.getVideoTracks && stream.getVideoTracks().some((track) => track.readyState === 'live')) {
        await waitForVideoReady();
        refreshTorchButton();
        return cameraStatus();
      }
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 2560 },
          height: { ideal: 1440 }
        }
      });
      video.srcObject = stream;
      if (video.play) await video.play().catch(() => {});
      await waitForVideoReady();
      captureBtn.disabled = false;
      bestBtn.disabled = false;
      refreshTorchButton();
      setState('camera ready');
      await announce('camera-started', {tracks: stream.getVideoTracks().map((track) => track.label)});
      const shouldStartBest = Object.prototype.hasOwnProperty.call(options || {}, 'startBest') ? !!options.startBest : startBest.checked;
      if (shouldStartBest) {
        setTimeout(() => bestPdf().catch((err) => setState(err.message, true)), 350);
      }
      return cameraStatus();
    }

    function runStartCamera(options={}) {
      if (!startCameraPromise) {
        startCameraPromise = startCamera(options).finally(() => {
          startCameraPromise = null;
        });
      }
      return startCameraPromise;
    }

    function beginStartCamera(options={}) {
      const promise = runStartCamera(options);
      startCameraClickPromise = promise;
      promise.finally(() => {
        if (startCameraClickPromise === promise) startCameraClickPromise = null;
      });
      return promise;
    }

    function dispatchRemoteButtonClick(button) {
      button.classList.add('remote-click');
      const makeEvent = (name) => new Event(name, {bubbles: true, cancelable: true});
      try {
        button.dispatchEvent(makeEvent('pointerdown'));
        button.dispatchEvent(makeEvent('mousedown'));
        button.dispatchEvent(makeEvent('pointerup'));
        button.dispatchEvent(makeEvent('mouseup'));
        button.click();
      } finally {
        setTimeout(() => button.classList.remove('remote-click'), 450);
      }
    }

    async function clickStartCameraButton(payload={}) {
      if (Object.prototype.hasOwnProperty.call(payload || {}, 'startBest')) {
        startBest.checked = !!payload.startBest;
      }
      setState('URI click Start camera');
      dispatchRemoteButtonClick(startBtn);
      const status = await (startCameraClickPromise || beginStartCamera(payload || {}));
      return {ok: true, clicked: true, button: 'Start camera', uri: 'scanner://page/ui/button/start-camera/command/click', status};
    }

    function cameraTrack() {
      return stream && stream.getVideoTracks ? stream.getVideoTracks()[0] : null;
    }

    function torchInfo() {
      const track = cameraTrack();
      let supported = false;
      let settings = {};
      if (track) {
        try {
          const capabilities = track.getCapabilities ? track.getCapabilities() : {};
          supported = !!(capabilities && Object.prototype.hasOwnProperty.call(capabilities, 'torch'));
        } catch (_) {}
        try {
          settings = track.getSettings ? track.getSettings() : {};
        } catch (_) {}
      }
      return {
        supported,
        enabled: torchOn,
        ready: !!track,
        label: track ? track.label : '',
        settings: {torch: Object.prototype.hasOwnProperty.call(settings, 'torch') ? settings.torch : null}
      };
    }

    function refreshTorchButton() {
      const info = torchInfo();
      torchBtn.disabled = !info.supported;
      torchBtn.textContent = torchOn ? 'Light on' : 'Light off';
      torchBtn.className = torchOn ? 'primary' : '';
      return info;
    }

    async function setTorch(enabled=true) {
      if (!stream) {
        await runStartCamera({startBest: false});
      }
      const track = cameraTrack();
      if (!track) throw new Error('camera stream not ready');
      const capabilities = track.getCapabilities ? track.getCapabilities() : {};
      if (track.getCapabilities && !Object.prototype.hasOwnProperty.call(capabilities || {}, 'torch')) {
        refreshTorchButton();
        throw new Error('torch not supported by this browser/camera');
      }
      await track.applyConstraints({advanced: [{torch: !!enabled}]});
      torchOn = !!enabled;
      const info = refreshTorchButton();
      setState(torchOn ? 'light on' : 'light off');
      await announce('torch-changed', {enabled: torchOn, supported: info.supported});
      return {ok: true, uri: 'scanner://page/camera/command/torch', enabled: torchOn, torch: info, status: cameraStatus()};
    }

    async function clickTorchButton(payload={}) {
      if (!stream) {
        await runStartCamera({startBest: false});
      }
      const info = refreshTorchButton();
      if (!info.supported) throw new Error('torch not supported by this browser/camera');
      if (Object.prototype.hasOwnProperty.call(payload || {}, 'enabled')) {
        torchBtn.dataset.nextTorch = payload.enabled ? '1' : '0';
      }
      setState('URI click Light');
      dispatchRemoteButtonClick(torchBtn);
      const result = await (torchClickPromise || setTorch(Object.prototype.hasOwnProperty.call(payload || {}, 'enabled') ? !!payload.enabled : !torchOn));
      return {ok: true, clicked: true, button: 'Light', uri: 'scanner://page/ui/button/torch/command/click', result, status: cameraStatus()};
    }

    function sleep(ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    }

    function waitForVideoReady(timeout=3000) {
      if (video.videoWidth && video.videoHeight) return Promise.resolve();
      return new Promise((resolve) => {
        let done = false;
        const finish = () => {
          if (done) return;
          done = true;
          video.removeEventListener('loadedmetadata', finish);
          video.removeEventListener('canplay', finish);
          resolve();
        };
        video.addEventListener('loadedmetadata', finish);
        video.addEventListener('canplay', finish);
        setTimeout(finish, timeout);
      });
    }

    async function sendFrame(options={}) {
      if (!stream) return;
      await waitForVideoReady();
      const w = video.videoWidth || 1920;
      const h = video.videoHeight || 1080;
      canvas.width = w;
      canvas.height = h;
      canvas.getContext('2d').drawImage(video, 0, 0, w, h);
      const quality = Number(document.getElementById('quality').value || '0.92');
      const image = canvas.toDataURL('image/jpeg', quality);
      return invokeURI('scanner://host/capture/command/run', {
        source: 'phone',
        image,
        width: w,
        height: h,
        userAgent: navigator.userAgent,
        capturedAt: new Date().toISOString(),
        ...options
      });
    }

    async function capture(options={}) {
      const w = video.videoWidth || 1920;
      const h = video.videoHeight || 1080;
      setState(`uploading ${w}x${h}...`);
      const data = await sendFrame({archive: true, ...options});
      if (!data || data.ok === false) throw new Error((data && data.error) || 'scan failed');
      setState(`saved ${data.artifact && data.artifact.path ? data.artifact.path : data.uri}`);
      return data;
    }

    async function bestPdf(options={}) {
      if (!stream || bestRunning) return;
      bestRunning = true;
      bestBtn.disabled = true;
      captureBtn.disabled = true;
      const total = Number(options.count || document.getElementById('bestCount').value || '6');
      const seriesId = `best-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      try {
        let best = null;
        for (let frame = 1; frame <= total; frame += 1) {
          setState(`frame ${frame}/${total}...`);
          const data = await sendFrame({
            archive: false,
            mode: 'best-candidate',
            seriesId,
            frameIndex: frame,
            frameCount: total
          });
          if (!data || data.ok === false) throw new Error((data && data.error) || 'candidate scan failed');
          best = data.series && data.series.best ? data.series.best : data.candidate;
          const score = best && best.quality ? Number(best.quality.score || 0).toFixed(1) : '0.0';
          setState(`frame ${frame}/${total}, best score ${score}`);
          if (frame < total) await sleep(1000);
        }
        const finalData = await invokeURI('scanner://host/best/command/finish', {seriesId, minScore: options.minScore || 45});
        if (!finalData || finalData.ok === false) throw new Error((finalData && finalData.error) || 'best scan failed');
        setState(`saved best ${finalData.document && finalData.document.path ? finalData.document.path : finalData.uri}`);
        return finalData;
      } finally {
        bestRunning = false;
        bestBtn.disabled = !stream;
        captureBtn.disabled = !stream;
      }
    }

    function cameraStatus() {
      const track = cameraTrack();
      return {
        ok: true,
        uri: 'scanner://page/camera/query/status',
        ready: !!stream,
        runningBest: bestRunning,
        width: video.videoWidth || 0,
        height: video.videoHeight || 0,
        torch: torchInfo(),
        track: track ? {label: track.label, readyState: track.readyState, enabled: track.enabled} : null,
        localActions: window.urirun && window.urirun.listActions ? window.urirun.listActions() : []
      };
    }

    function registerCameraActions() {
      if (!window.urirun || typeof window.urirun.registerAction !== 'function') return;
      window.urirun.registerAction('scanner://page/ui/button/start-camera/command/click', (payload) => clickStartCameraButton(payload || {}), {
        label: 'Click Start camera button', layer: 'page', kind: 'command', sideEffects: ['dom-click', 'camera-permission', 'media-stream']
      });
      window.urirun.registerAction('scanner://page/camera/command/start', (payload) => runStartCamera(payload || {}), {
        label: 'Start camera', layer: 'page', kind: 'command', sideEffects: ['camera-permission', 'media-stream']
      });
      window.urirun.registerAction('scanner://page/ui/button/torch/command/click', (payload) => clickTorchButton(payload || {}), {
        label: 'Click Light button', layer: 'page', kind: 'command', sideEffects: ['dom-click', 'camera-torch']
      });
      window.urirun.registerAction('scanner://page/camera/command/torch', (payload) => setTorch(!payload || !Object.prototype.hasOwnProperty.call(payload, 'enabled') ? true : !!payload.enabled), {
        label: 'Set camera light/torch', layer: 'page', kind: 'command', sideEffects: ['camera-torch']
      });
      window.urirun.registerAction('scanner://page/camera/command/scan', (payload) => capture(payload || {}), {
        label: 'Scan current frame', layer: 'page', kind: 'command', sideEffects: ['network', 'document-write']
      });
      window.urirun.registerAction('scanner://page/camera/command/best-pdf', (payload) => bestPdf(payload || {}), {
        label: 'Capture best PDF', layer: 'page', kind: 'command', sideEffects: ['camera-read', 'network', 'document-write']
      });
      window.urirun.registerAction('scanner://page/camera/query/status', () => cameraStatus(), {
        label: 'Camera page status', layer: 'page', kind: 'query', sideEffects: []
      });
      window.urirun.registerAction('scanner://page/actions/query/list', () => ({ok: true, actions: window.urirun.listActions()}), {
        label: 'List page actions', layer: 'page', kind: 'query', sideEffects: []
      });
      window.urirun.track('scanner_actions_ready', { count: window.urirun.listActions().length });
    }

    async function sendActionResult(action, result, error) {
      try {
        await fetch('/api/page/actions/result', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            id: action.id,
            target: action.target || 'scanner',
            uri: action.uri,
            ok: !error && (!result || result.ok !== false),
            error: error ? String(error.message || error) : '',
            result: result || null,
            at: new Date().toISOString()
          })
        });
      } catch (_) {}
    }

    async function pollPageActions() {
      if (!window.urirun || typeof window.urirun.invoke !== 'function') return;
      let data = null;
      try {
        const response = await fetch('/api/page/actions/poll?target=scanner&limit=4', {cache: 'no-store'});
        data = await response.json();
      } catch (_) {
        return;
      }
      const actions = data && Array.isArray(data.actions) ? data.actions : [];
      for (const action of actions) {
        try {
          setState(`URI ${action.uri}`);
          const result = await window.urirun.invoke(action.uri, action.payload || {}, {mode: action.mode || 'execute', localOnly: true});
          await sendActionResult(action, result, null);
        } catch (err) {
          setState(err.message || String(err), true);
          await sendActionResult(action, null, err);
        }
      }
    }

    announce('open');
    registerCameraActions();
    setInterval(() => pollPageActions().catch(() => {}), 1000);
    startBtn.addEventListener('click', () => beginStartCamera().catch((err) => setState(err.message, true)));
    torchBtn.addEventListener('click', () => {
      const requested = Object.prototype.hasOwnProperty.call(torchBtn.dataset, 'nextTorch') ? torchBtn.dataset.nextTorch === '1' : !torchOn;
      delete torchBtn.dataset.nextTorch;
      const promise = setTorch(requested).catch((err) => setState(err.message, true));
      torchClickPromise = promise;
      promise.finally(() => {
        if (torchClickPromise === promise) torchClickPromise = null;
      });
    });
    captureBtn.addEventListener('click', () => capture().catch((err) => setState(err.message, true)));
    bestBtn.addEventListener('click', () => bestPdf().catch((err) => {
      bestRunning = false;
      bestBtn.disabled = !stream;
      captureBtn.disabled = !stream;
      setState(err.message, true);
    }));
    auto.addEventListener('change', () => {
      clearInterval(timer);
      timer = auto.checked ? setInterval(() => {
        if (!bestRunning) bestPdf().catch((err) => setState(err.message, true));
      }, 1000) : null;
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


def _asset_response(handler: BaseHTTPRequestHandler, body: bytes, content_type: str) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _js_sdk_response(handler: BaseHTTPRequestHandler, project: str) -> None:
    configured = os.environ.get("URIRUN_JS_SDK")
    roots = []
    if configured:
        roots.append(Path(configured).expanduser())
    project_path = Path(project).expanduser().resolve()
    roots.extend([
        project_path.parent / "js-urirun-com" / "urirun.js",
        project_path.parent / "js-urirun-com" / "src" / "urirun.js",
        Path("/home/tom/github/if-uri/js-urirun-com/urirun.js"),
        Path("/home/tom/github/if-uri/js-urirun-com/src/urirun.js"),
    ])
    for source in roots:
        try:
            resolved = source.expanduser().resolve()
            if resolved.is_file():
                _asset_response(handler, resolved.read_bytes(), "application/javascript; charset=utf-8")
                return
        except Exception:  # noqa: BLE001
            continue
    _json_response(handler, 404, {"ok": False, "error": "urirun JS SDK not found"})


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


def _document_archive_root() -> Path:
    return Path(os.environ.get("URIRUN_DOCUMENT_DIR", "~/.urirun/documents")).expanduser().resolve()


def _document_index_path() -> Path:
    configured = os.environ.get("URIRUN_DOCUMENT_INDEX")
    return Path(configured).expanduser().resolve() if configured else _document_archive_root() / "index.json"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).expanduser().resolve().open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_document_text(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    folded = re.sub(r"[^a-zA-Z0-9.,:/@+\- ]+", " ", folded.lower())
    return re.sub(r"\s+", " ", folded).strip()


def _load_document_index() -> dict:
    path = _document_index_path()
    if not path.is_file():
        return {"version": 1, "documents": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"version": 1, "documents": []}
    if not isinstance(data, dict):
        return {"version": 1, "documents": []}
    docs = data.get("documents")
    if not isinstance(docs, list):
        data["documents"] = []
    data.setdefault("version", 1)
    return data


def _save_document_index(index: dict) -> None:
    path = _document_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    index["updatedAt"] = _utc_now()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _docid_for_file(path: str | Path, ocr_text: str) -> dict:
    docid_error = ""
    docid_log = ""
    try:
        import contextlib
        from docid import get_document_id  # type: ignore

        log_buffer = io.StringIO()
        with contextlib.redirect_stdout(log_buffer), contextlib.redirect_stderr(log_buffer):
            value = str(get_document_id(str(Path(path).expanduser().resolve())) or "").strip()
        docid_log = log_buffer.getvalue().strip()
        if value:
            result = {"id": value, "provider": "docid", "source": "get_document_id"}
            if docid_log:
                result["docidLog"] = docid_log[:240]
            return result
    except Exception as exc:  # noqa: BLE001
        docid_error = str(exc)

    normalized = _normalized_document_text(ocr_text)
    if len(normalized) >= 24:
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        source = "ocr-text"
    else:
        digest = _file_sha256(path)
        source = "file-sha256"
    result = {"id": f"LOCAL-DOC-{digest[:16].upper()}", "provider": "local-fallback", "source": source}
    if docid_error:
        result["docidError"] = docid_error[:240]
    if docid_log:
        result["docidLog"] = docid_log[:240]
    return result


def _parse_document_date(text: str, fallback: str | None = None) -> str:
    candidates: list[date] = []
    for year, month, day in re.findall(r"\b(20\d{2})[-./](\d{1,2})[-./](\d{1,2})\b", text):
        try:
            candidates.append(date(int(year), int(month), int(day)))
        except ValueError:
            pass
    for day, month, year in re.findall(r"\b(\d{1,2})[-./](\d{1,2})[-./](20\d{2})\b", text):
        try:
            candidates.append(date(int(year), int(month), int(day)))
        except ValueError:
            pass
    if candidates:
        return min(candidates).isoformat()
    if fallback:
        match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", fallback)
        if match:
            return match.group(1)
    return time.strftime("%Y-%m-%d", time.gmtime())


def _parse_amount(text: str) -> dict:
    amount_re = re.compile(r"(?<!\d)(\d{1,3}(?:[ \u00a0]?\d{3})*(?:[,.]\d{2})|\d+[,.]\d{2})(?!\d)")
    keyword_re = re.compile(r"(razem|suma|do zaplaty|do zapłaty|naleznosc|należność|total|kwota|brutto)", re.I)
    date_context_re = re.compile(r"\b(data|date|godzina|hour|czas|time)\b", re.I)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    matches: list[tuple[int, float, str]] = []
    for idx, line in enumerate(lines):
        has_amount_keyword = bool(keyword_re.search(line))
        if date_context_re.search(line) and not has_amount_keyword:
            continue
        for raw in amount_re.findall(line):
            normalized = raw.replace("\u00a0", "").replace(" ", "").replace(",", ".")
            try:
                value = float(normalized)
            except ValueError:
                continue
            score = 10 if has_amount_keyword else 0
            matches.append((score + idx, value, raw))
    if not matches:
        return {"amount": "", "currency": ""}
    best = max(matches, key=lambda item: (item[0], item[1]))
    return {"amount": f"{best[1]:.2f}", "currency": "PLN"}


def _document_type(text: str) -> str:
    lower = text.lower()
    if "paragon" in lower or "fiskal" in lower or "receipt" in lower:
        return "paragon"
    if "faktura" in lower or "invoice" in lower or ("nip" in lower and "vat" in lower):
        return "faktura"
    if "rachunek" in lower or "bill" in lower:
        return "rachunek"
    payment_terms = ("contactless", "terminal", "karta", "kart", "obciazyc", "obciążyć", "eplatnosci", "epłatności")
    if any(term in lower for term in payment_terms):
        return "potwierdzenie"
    return "dokument"


def _parse_contractor(text: str) -> str:
    ignored = re.compile(
        r"^(faktura|paragon|rachunek|invoice|receipt|nip|vat|data|date|razem|suma|total|do zap|sprzedawca|nabywca|lp\.?|ilosc|ilość|cena|kwota)\b",
        re.I,
    )
    candidates: list[tuple[int, str]] = []
    for idx, raw in enumerate(text.splitlines()[:30]):
        line = re.sub(r"\s+", " ", raw.strip(" \t:-")).strip()
        if len(line) < 3 or len(line) > 70 or ignored.search(line):
            continue
        if not re.search(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]", line):
            continue
        digit_ratio = sum(ch.isdigit() for ch in line) / max(1, len(line))
        if digit_ratio > 0.35:
            continue
        score = 100 - idx
        if re.search(r"\b(sp\.?|s\.a\.|s\.c\.|ltd|gmbh|inc|allegro|amazon|google|openai|microsoft|apple)\b", line, re.I):
            score += 30
        if line.upper() == line and len(line) >= 5:
            score += 8
        candidates.append((score, line))
    if not candidates:
        return "kontrahent-nieznany"
    return max(candidates, key=lambda item: item[0])[1]


def _extract_document_metadata(ocr_text: str, *, captured_at: str | None = None) -> dict:
    amount = _parse_amount(ocr_text)
    return {
        "type": _document_type(ocr_text),
        "date": _parse_document_date(ocr_text, captured_at),
        "contractor": _parse_contractor(ocr_text),
        "amount": amount["amount"],
        "currency": amount["currency"],
    }


def _filename_part(value: str, *, default: str, max_len: int = 48) -> str:
    folded = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    folded = re.sub(r"[^A-Za-z0-9._+-]+", "-", folded).strip(".-_").lower()
    folded = re.sub(r"-{2,}", "-", folded)
    return (folded or default)[:max_len].strip(".-_") or default


def _canonical_document_filename(meta: dict) -> str:
    doc_type = _filename_part(str(meta.get("type") or ""), default="dokument", max_len=18)
    doc_date = _filename_part(str(meta.get("date") or ""), default=time.strftime("%Y-%m-%d", time.gmtime()), max_len=10)
    contractor = _filename_part(str(meta.get("contractor") or ""), default="kontrahent-nieznany", max_len=42)
    amount = str(meta.get("amount") or "").strip()
    currency = str(meta.get("currency") or "").strip().upper()
    amount_part = f"{amount}-{currency}" if amount and currency else amount or "kwota-nieznana"
    amount_part = _filename_part(amount_part, default="kwota-nieznana", max_len=24)
    return f"{doc_type}_{doc_date}_{contractor}_{amount_part}.pdf"


def _pdf_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return text


def _pdf_stream(data: bytes) -> bytes:
    return b"<< /Length " + str(len(data)).encode("ascii") + b" >>\nstream\n" + data + b"\nendstream"


def _write_document_pdf(image_path: str | Path, pdf_path: str | Path, *, metadata: dict, ocr_text: str) -> None:
    from PIL import Image, ImageOps

    source = Path(image_path).expanduser().resolve()
    target = Path(pdf_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image_bytes = io.BytesIO()
        image.save(image_bytes, format="JPEG", quality=92, optimize=True)
        jpeg = image_bytes.getvalue()
        image_width, image_height = image.size

    page_width = 595.0
    page_height = 842.0
    margin = 36.0
    scale = min((page_width - margin * 2) / image_width, (page_height - margin * 2) / image_height)
    draw_width = image_width * scale
    draw_height = image_height * scale
    draw_x = (page_width - draw_width) / 2.0
    draw_y = (page_height - draw_height) / 2.0
    image_content = f"q {draw_width:.2f} 0 0 {draw_height:.2f} {draw_x:.2f} {draw_y:.2f} cm /Im0 Do Q".encode("ascii")

    header_lines = [
        f"Document ID: {metadata.get('docId', '')}",
        f"Type: {metadata.get('type', '')}",
        f"Date: {metadata.get('date', '')}",
        f"Contractor: {metadata.get('contractor', '')}",
        f"Amount: {metadata.get('amount', '')} {metadata.get('currency', '')}".strip(),
        f"Source: {metadata.get('sourcePath', '')}",
        "",
        "OCR text:",
    ]
    text_lines = header_lines
    for paragraph in (ocr_text or "").splitlines():
        if not paragraph.strip():
            text_lines.append("")
            continue
        text_lines.extend(textwrap.wrap(paragraph.strip(), width=92) or [""])
    text_lines = text_lines[:66]
    ops = ["BT /F1 10 Tf 12 TL 44 792 Td"]
    for line in text_lines:
        ops.append(f"({_pdf_text(line)}) Tj T*")
    ops.append("ET")
    text_content = "\n".join(ops).encode("ascii", "ignore")

    info = (
        f"<< /Title ({_pdf_text(target.stem)}) "
        f"/Creator ({_pdf_text('urirun host dashboard')}) "
        f"/Subject ({_pdf_text(metadata.get('docId', ''))}) "
        f"/Keywords ({_pdf_text('urirun,ocr,document,' + str(metadata.get('type', '')))}) >>"
    ).encode("ascii", "ignore")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 7 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /XObject << /Im0 5 0 R >> >> /Contents 4 0 R >>",
        _pdf_stream(image_content),
        (
            b"<< /Type /XObject /Subtype /Image /Width "
            + str(image_width).encode("ascii")
            + b" /Height "
            + str(image_height).encode("ascii")
            + b" /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length "
            + str(len(jpeg)).encode("ascii")
            + b" >>\nstream\n"
            + jpeg
            + b"\nendstream"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 6 0 R >> >> /Contents 8 0 R >>",
        _pdf_stream(text_content),
        info,
    ]

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for idx, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 9 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    target.write_bytes(bytes(pdf))


def _unique_document_path(directory: Path, filename: str, doc_id: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    suffix = _filename_part(doc_id[-10:], default="doc", max_len=12)
    alternative = directory / f"{candidate.stem}_{suffix}{candidate.suffix}"
    counter = 2
    while alternative.exists():
        alternative = directory / f"{candidate.stem}_{suffix}-{counter}{candidate.suffix}"
        counter += 1
    return alternative


def _existing_document(index: dict, *, doc_id: str, source_sha256: str, text_sha256: str) -> dict | None:
    for item in index.get("documents", []):
        if not isinstance(item, dict):
            continue
        same_doc = item.get("docId") == doc_id
        same_source = bool(source_sha256 and item.get("sourceSha256") == source_sha256)
        same_text = bool(text_sha256 and item.get("textSha256") == text_sha256)
        if same_doc or same_source or same_text:
            path = item.get("pdfPath") or item.get("path")
            if path and Path(path).expanduser().is_file():
                return item
    return None


def _archive_scanned_document(
    *,
    display_path: Path,
    original_path: Path,
    ocr: dict,
    crop: dict,
    source_sha256: str,
    captured_at: str | None,
) -> dict:
    ocr_text = str(ocr.get("text") or "")
    extracted = _extract_document_metadata(ocr_text, captured_at=captured_at)
    docid_info = _docid_for_file(display_path, ocr_text)
    doc_id = str(docid_info["id"])
    normalized_text = _normalized_document_text(ocr_text)
    text_sha256 = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest() if normalized_text else ""
    month = str(extracted["date"])[:7] if re.match(r"^20\d{2}-\d{2}", str(extracted.get("date", ""))) else time.strftime("%Y-%m", time.gmtime())
    root = _document_archive_root()
    archive_dir = root / month
    filename = _canonical_document_filename(extracted)

    with _DOCUMENT_INDEX_LOCK:
        index = _load_document_index()
        duplicate = _existing_document(index, doc_id=doc_id, source_sha256=source_sha256, text_sha256=text_sha256)
        if duplicate:
            return {
                "ok": True,
                "duplicate": True,
                "docId": doc_id,
                "docIdProvider": docid_info.get("provider"),
                "path": duplicate.get("pdfPath") or duplicate.get("path"),
                "jsonPath": duplicate.get("jsonPath"),
                "duplicateOf": duplicate.get("docId"),
                "metadata": extracted,
                "indexPath": str(_document_index_path()),
            }

        archive_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = _unique_document_path(archive_dir, filename, doc_id)
        json_path = pdf_path.with_suffix(".json")
        pdf_meta = {
            **extracted,
            "docId": doc_id,
            "sourcePath": str(original_path),
            "cropPath": str(display_path),
        }
        _write_document_pdf(display_path, pdf_path, metadata=pdf_meta, ocr_text=ocr_text)
        entry = {
            "docId": doc_id,
            "docIdProvider": docid_info.get("provider"),
            "docIdSource": docid_info.get("source"),
            "docIdError": docid_info.get("docidError"),
            "docIdLog": docid_info.get("docidLog"),
            "uri": f"document://host/{quote(doc_id, safe='')}",
            "pdfPath": str(pdf_path),
            "jsonPath": str(json_path),
            "originalPath": str(original_path),
            "cropPath": str(display_path),
            "sourceSha256": source_sha256,
            "textSha256": text_sha256,
            "ocrBackend": ocr.get("backend"),
            "ocrChars": ocr.get("chars"),
            "crop": crop,
            "createdAt": _utc_now(),
            **extracted,
        }
        json_path.write_text(
            json.dumps({**entry, "ocr": ocr, "text": ocr_text}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        docs = [item for item in index.get("documents", []) if isinstance(item, dict) and item.get("docId") != doc_id]
        docs.append(entry)
        index["documents"] = docs
        _save_document_index(index)
    return {
        "ok": True,
        "duplicate": False,
        "docId": doc_id,
        "docIdProvider": docid_info.get("provider"),
        "path": str(pdf_path),
        "jsonPath": str(json_path),
        "uri": entry["uri"],
        "metadata": extracted,
        "indexPath": str(_document_index_path()),
    }


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
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.translate(str.maketrans({"ł": "l", "ß": "ss"}))


def _is_phone_scanner_prompt(prompt: str) -> bool:
    text = _nl_text(prompt)
    scanner_terms = (
        "skaner", "scanner", "skan", "scan", "kamera", "camera", "telefon", "phone", "mobile", "mobil",
        "webrtc", "qr", "qrcode", "paragon", "rachunek", "latark", "swiatl", "torch", "flash",
    )
    service_terms = ("aplikac", "uslug", "service", "stron", "narzedz", "interfejs")
    start_terms = (
        "uruchom", "wystart", "stworz", "utworz", "start", "create", "open", "wlacz", "odpal", "daj",
        "pokaz", "link", "adres", "ip", "qr", "wylacz", "zgas", "disable", "off",
    )
    wants_scanner = any(word in text for word in scanner_terms)
    wants_service = any(word in text for word in service_terms)
    wants_start = any(word in text for word in start_terms)
    mobile_context = any(word in text for word in ("telefon", "phone", "mobile", "mobil", "webrtc", "kamera", "camera", "qr", "skaner", "scanner", "latark", "swiatl", "torch", "flash"))
    return wants_start and (wants_scanner or (wants_service and mobile_context))


def _is_camera_start_prompt(prompt: str) -> bool:
    text = _nl_text(prompt)
    camera_terms = ("kamer", "camera", "webcam", "aparat", "obiektyw")
    start_terms = ("wlacz", "uruchom", "start", "odpal", "otworz", "aktywow", "enable")
    return any(word in text for word in camera_terms) and any(word in text for word in start_terms)


def _torch_enabled_from_prompt(prompt: str) -> bool | None:
    text = _nl_text(prompt)
    torch_terms = ("latark", "swiatl", "oswietl", "lampa", "led", "torch", "flash")
    if not any(word in text for word in torch_terms):
        return None
    off_terms = ("wylacz", "zgas", "off", "disable", "stop")
    on_terms = ("wlacz", "uruchom", "start", "odpal", "zaswiec", "on", "enable")
    if any(word in text for word in off_terms):
        return False
    if any(word in text for word in on_terms):
        return True
    return True


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
        from urirun_connector_smart_crop import detect_document_crop
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"smart-crop connector unavailable: {exc}", "originalPath": str(path)}
    return detect_document_crop(path, output_path=path.with_name(f"{path.stem}-receipt-crop.jpg"))


def _bounded(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _frame_visual_metrics(path: str | Path) -> dict:
    try:
        from PIL import Image, ImageOps

        with Image.open(Path(path).expanduser().resolve()) as opened:
            image = ImageOps.exif_transpose(opened).convert("L")
            scale = min(1.0, 420 / max(image.size))
            if scale < 1.0:
                image = image.resize((max(1, int(image.size[0] * scale)), max(1, int(image.size[1] * scale))))
            width, height = image.size
            pixels = list(image.tobytes())
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "sharpness": 0.0, "contrast": 0.0, "brightness": 0.0}
    if not pixels:
        return {"ok": False, "error": "empty image", "sharpness": 0.0, "contrast": 0.0, "brightness": 0.0}
    mean = sum(pixels) / len(pixels)
    variance = sum((value - mean) ** 2 for value in pixels) / len(pixels)
    contrast = variance ** 0.5
    diffs = []
    stride = max(1, width // 160)
    for y in range(0, height - 1, stride):
        row = y * width
        next_row = (y + 1) * width
        for x in range(0, width - 1, stride):
            idx = row + x
            diffs.append(abs(pixels[idx] - pixels[idx + 1]))
            diffs.append(abs(pixels[idx] - pixels[next_row + x]))
    sharpness = sum(diffs) / max(1, len(diffs))
    brightness_score = _bounded(1.0 - abs(mean - 190.0) / 190.0)
    return {
        "ok": True,
        "width": width,
        "height": height,
        "brightness": round(mean, 3),
        "brightnessScore": round(brightness_score, 4),
        "contrast": round(contrast, 3),
        "contrastScore": round(_bounded(contrast / 72.0), 4),
        "sharpness": round(sharpness, 3),
        "sharpnessScore": round(_bounded(sharpness / 18.0), 4),
    }


def _document_frame_quality(crop: dict, ocr: dict, metadata: dict, display_path: str | Path) -> dict:
    visual = _frame_visual_metrics(display_path)
    score = 0.0
    reasons: list[str] = []
    if crop.get("ok"):
        score += 42.0
        reasons.append("crop")
        bbox_area = float(crop.get("bboxArea") or 0.0)
        if bbox_area:
            score += 18.0 * _bounded(1.0 - abs(bbox_area - 0.42) / 0.42)
        width = int(crop.get("width") or crop.get("cropWidth") or 0)
        height = int(crop.get("height") or crop.get("cropHeight") or 0)
        if min(width, height) >= 220 and max(width, height) >= 420:
            score += 12.0
            reasons.append("size")
        orientation = crop.get("orientation") if isinstance(crop.get("orientation"), dict) else {}
        if orientation.get("enabled") and int(orientation.get("height") or height) >= int(orientation.get("width") or width):
            score += 5.0
            reasons.append("portrait")
    else:
        score -= 20.0

    doc_type = str(metadata.get("type") or "dokument")
    if doc_type in {"paragon", "faktura"}:
        score += 32.0
        reasons.append(doc_type)
    elif doc_type in {"rachunek", "potwierdzenie"}:
        score += 20.0
        reasons.append(doc_type)
    elif doc_type != "dokument":
        score += 10.0

    if metadata.get("date"):
        score += 8.0
        reasons.append("date")
    if metadata.get("amount"):
        score += 10.0
        reasons.append("amount")

    chars = int(ocr.get("chars") or len(str(ocr.get("text") or "")))
    if ocr.get("ok") and chars:
        score += min(36.0, chars / 4.0)
        reasons.append("ocr")

    if visual.get("ok"):
        score += 18.0 * float(visual.get("sharpnessScore") or 0.0)
        score += 10.0 * float(visual.get("contrastScore") or 0.0)
        score += 7.0 * float(visual.get("brightnessScore") or 0.0)
        reasons.append("visual")

    document_like = bool(crop.get("ok") and (doc_type in {"paragon", "faktura", "rachunek", "potwierdzenie"} or chars >= 36))
    return {
        "score": round(max(0.0, score), 3),
        "documentLike": document_like,
        "reasons": reasons,
        "visual": visual,
    }


def _public_scanner_candidate(candidate: dict) -> dict:
    ocr = candidate.get("ocr") if isinstance(candidate.get("ocr"), dict) else {}
    return {
        "seriesId": candidate.get("seriesId"),
        "frameIndex": candidate.get("frameIndex"),
        "uri": candidate.get("uri"),
        "path": candidate.get("displayPath"),
        "originalPath": candidate.get("originalPath"),
        "sha256": candidate.get("sha256"),
        "quality": candidate.get("quality"),
        "detectedDocument": candidate.get("detectedDocument"),
        "crop": candidate.get("crop"),
        "ocr": {key: value for key, value in ocr.items() if key != "text"},
    }


def _scanner_best_update(series_id: str, candidate: dict) -> dict:
    with _SCANNER_BEST_LOCK:
        series = _SCANNER_BEST_SESSIONS.setdefault(series_id, {"createdAt": _utc_now(), "candidates": []})
        series["updatedAt"] = _utc_now()
        series["candidates"].append(candidate)
        series["candidates"] = series["candidates"][-24:]
        best = max(series["candidates"], key=lambda item: float((item.get("quality") or {}).get("score") or 0.0))
        series["best"] = best
        return {
            "seriesId": series_id,
            "count": len(series["candidates"]),
            "best": _public_scanner_candidate(best),
        }


def _scanner_best_take(series_id: str, *, clear: bool = True) -> dict | None:
    with _SCANNER_BEST_LOCK:
        series = _SCANNER_BEST_SESSIONS.get(series_id)
        if not series:
            return None
        if clear:
            _SCANNER_BEST_SESSIONS.pop(series_id, None)
        return dict(series)


def _register_scanner_result(
    project: str,
    db: str | None,
    *,
    uri: str,
    display_path: Path,
    original_path: Path,
    meta: dict,
    crop: dict,
    ocr: dict,
    document: dict,
    content_prefix: str,
) -> dict:
    artifact = _host_db().register_artifact(db, "camera-scan", uri, str(display_path), meta)
    attachments = [{
        "kind": "receipt-crop" if crop.get("ok") else "image",
        "path": str(display_path),
        "uri": uri,
        "previewUrl": _preview_url(str(display_path), project),
        "meta": meta,
    }]
    document_artifact = None
    if document.get("ok") and document.get("path"):
        document_uri = str(document.get("uri") or f"document://host/{quote(str(document.get('docId') or meta.get('sha256') or ''), safe='')}")
        document_meta = {
            "document": document,
            "ocr": {key: value for key, value in ocr.items() if key != "text"},
            "sourceCaptureUri": uri,
            "sourceImage": str(original_path),
            "displayImage": str(display_path),
        }
        document_artifact = _host_db().register_artifact(db, "document-pdf", document_uri, str(document["path"]), document_meta)
        attachments.append({
            "kind": "document-pdf",
            "path": str(document["path"]),
            "uri": document_uri,
            "previewUrl": _preview_url(str(document["path"]), project),
            "meta": document_meta,
        })
    content = content_prefix
    if crop.get("ok"):
        content += " (cropped to receipt)"
    if document.get("ok") and document.get("path"):
        content += " -> document PDF"
        if document.get("duplicate"):
            content += " (duplicate)"
    if ocr.get("ok") and ocr.get("text"):
        content += f": {str(ocr.get('text'))[:180]}"
    elif ocr.get("error"):
        content += f" (OCR: {ocr.get('error')})"
    message = _chat_message(
        "system",
        content,
        detail={"artifact": artifact, "documentArtifact": document_artifact, "uri": uri, "ocr": ocr, "document": document},
        attachments=attachments,
    )
    _add_chat_message(db, message)
    return {"artifact": artifact, "documentArtifact": document_artifact, "message": message}


def scanner_capture(project: str, db: str | None, payload: dict) -> dict:
    mode = str(payload.get("mode") or "").lower()
    archive = not (payload.get("archive") is False or mode in {"candidate", "best-candidate", "analyze", "analysis"})
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
    detected_document = _extract_document_metadata(str(ocr.get("text") or ""), captured_at=payload.get("capturedAt"))
    quality = _document_frame_quality(crop, ocr, detected_document, display_path)
    document = {"ok": False, "reason": "analysis-only", "metadata": detected_document}
    if archive:
        try:
            document = _archive_scanned_document(
                display_path=display_path,
                original_path=path,
                ocr=ocr,
                crop=crop,
                source_sha256=digest,
                captured_at=payload.get("capturedAt"),
            )
        except Exception as exc:  # noqa: BLE001
            document = {"ok": False, "error": str(exc), "metadata": detected_document}
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
        "detectedDocument": detected_document,
        "quality": quality,
        "document": document,
    }
    uri = f"scanner://host/capture/{digest[:16]}"
    if not archive:
        candidate = {
            "seriesId": str(payload.get("seriesId") or ""),
            "frameIndex": payload.get("frameIndex"),
            "uri": uri,
            "mime": mime,
            "sha256": digest,
            "bytes": len(raw),
            "originalPath": str(path),
            "displayPath": str(display_path),
            "crop": crop,
            "ocr": ocr,
            "detectedDocument": detected_document,
            "quality": quality,
            "capturedAt": payload.get("capturedAt"),
            "userAgent": payload.get("userAgent", ""),
            "width": payload.get("width"),
            "height": payload.get("height"),
        }
        series = None
        if candidate["seriesId"]:
            series = _scanner_best_update(candidate["seriesId"], candidate)
        return {
            "ok": True,
            "uri": uri,
            "candidate": _public_scanner_candidate(candidate),
            "series": series,
            "ocr": ocr,
            "crop": crop,
            "quality": quality,
            "detectedDocument": detected_document,
        }

    registered = _register_scanner_result(
        project,
        db,
        uri=uri,
        display_path=display_path,
        original_path=path,
        meta=meta,
        crop=crop,
        ocr=ocr,
        document=document,
        content_prefix="Phone scan saved",
    )
    return {
        "ok": True,
        "uri": uri,
        "artifact": registered["artifact"],
        "documentArtifact": registered["documentArtifact"],
        "ocr": ocr,
        "detectedDocument": detected_document,
        "quality": quality,
        "document": document,
        "message": registered["message"],
    }


def scanner_best_finish(project: str, db: str | None, payload: dict) -> dict:
    series_id = str(payload.get("seriesId") or "").strip()
    if not series_id:
        raise ValueError("seriesId is required")
    series = _scanner_best_take(series_id, clear=payload.get("clear", True) is not False)
    if not series:
        return {"ok": False, "error": "scanner best series not found", "seriesId": series_id}
    best = series.get("best")
    if not isinstance(best, dict):
        candidates = [item for item in series.get("candidates", []) if isinstance(item, dict)]
        best = max(candidates, key=lambda item: float((item.get("quality") or {}).get("score") or 0.0)) if candidates else None
    if not isinstance(best, dict):
        return {"ok": False, "error": "scanner best series has no candidates", "seriesId": series_id}
    quality = best.get("quality") if isinstance(best.get("quality"), dict) else {}
    min_score = float(payload.get("minScore") if payload.get("minScore") is not None else 45.0)
    if not payload.get("force") and (float(quality.get("score") or 0.0) < min_score or not quality.get("documentLike")):
        return {
            "ok": False,
            "error": "no reliable receipt or invoice candidate found",
            "seriesId": series_id,
            "best": _public_scanner_candidate(best),
            "minScore": min_score,
        }

    original_path = Path(str(best.get("originalPath") or "")).expanduser().resolve()
    display_path = Path(str(best.get("displayPath") or "")).expanduser().resolve()
    if not original_path.is_file() or not display_path.is_file():
        return {"ok": False, "error": "best candidate file is missing", "seriesId": series_id, "best": _public_scanner_candidate(best)}
    crop = best.get("crop") if isinstance(best.get("crop"), dict) else {}
    ocr = best.get("ocr") if isinstance(best.get("ocr"), dict) else {}
    digest = str(best.get("sha256") or _file_sha256(original_path))
    try:
        document = _archive_scanned_document(
            display_path=display_path,
            original_path=original_path,
            ocr=ocr,
            crop=crop,
            source_sha256=digest,
            captured_at=str(best.get("capturedAt") or ""),
        )
    except Exception as exc:  # noqa: BLE001
        document = {"ok": False, "error": str(exc), "metadata": best.get("detectedDocument") or {}}
    uri = str(best.get("uri") or f"scanner://host/capture/{digest[:16]}")
    meta = {
        "source": "phone-best",
        "seriesId": series_id,
        "frameIndex": best.get("frameIndex"),
        "candidateCount": len(series.get("candidates", []) or []),
        "width": best.get("width"),
        "height": best.get("height"),
        "mime": best.get("mime"),
        "sha256": digest,
        "bytes": best.get("bytes"),
        "originalPath": str(original_path),
        "displayPath": str(display_path),
        "crop": crop,
        "capturedAt": best.get("capturedAt"),
        "userAgent": best.get("userAgent", ""),
        "ocr": ocr,
        "detectedDocument": best.get("detectedDocument") or {},
        "quality": quality,
        "document": document,
    }
    registered = _register_scanner_result(
        project,
        db,
        uri=uri,
        display_path=display_path,
        original_path=original_path,
        meta=meta,
        crop=crop,
        ocr=ocr,
        document=document,
        content_prefix="Best phone scan saved",
    )
    return {
        "ok": True,
        "seriesId": series_id,
        "best": _public_scanner_candidate(best),
        "uri": uri,
        "artifact": registered["artifact"],
        "documentArtifact": registered["documentArtifact"],
        "ocr": ocr,
        "detectedDocument": best.get("detectedDocument") or {},
        "quality": quality,
        "document": document,
        "message": registered["message"],
    }


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


def uri_event(db: str | None, query: dict[str, list[str]]) -> dict:
    event = _first(query, "e", "event") or "event"
    detail = {
        "site": _first(query, "s", ""),
        "event": event,
        "path": _first(query, "p", ""),
        "url": _first(query, "u", ""),
        "referrer": _first(query, "r", ""),
        "label": _first(query, "l", ""),
        "value": _first(query, "v", ""),
        "raw": {key: values[0] if len(values) == 1 else values for key, values in query.items()},
    }
    try:
        _host_db().add_log(db, "uri-js", event, detail)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "event": event}


def page_action_enqueue(
    db: str | None,
    *,
    target: str,
    uri: str,
    payload: dict | None = None,
    mode: str = "execute",
    source: str = "host",
) -> dict:
    target = (target or "scanner").strip() or "scanner"
    action_id = hashlib.sha256(f"{time.time_ns()}:{target}:{uri}".encode("utf-8")).hexdigest()[:16]
    item = {
        "id": action_id,
        "target": target,
        "uri": uri,
        "payload": payload or {},
        "mode": _uri_mode(mode),
        "source": source,
        "createdAt": _utc_now(),
    }
    with _PAGE_ACTION_LOCK:
        queue = _PAGE_ACTION_QUEUES.setdefault(target, [])
        queue.append(item)
        _PAGE_ACTION_QUEUES[target] = queue[-50:]
    try:
        _host_db().add_log(db, "page-action", "queued", item)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "queued": True, "target": target, "action": item}


def page_action_poll(target: str = "scanner", limit: int = 4) -> dict:
    target = (target or "scanner").strip() or "scanner"
    limit = max(1, min(20, int(limit or 4)))
    with _PAGE_ACTION_LOCK:
        queue = _PAGE_ACTION_QUEUES.get(target, [])
        actions = queue[:limit]
        _PAGE_ACTION_QUEUES[target] = queue[limit:]
    return {"ok": True, "target": target, "actions": actions, "count": len(actions)}


def page_action_result(db: str | None, payload: dict) -> dict:
    detail = {
        "id": payload.get("id"),
        "target": payload.get("target") or "scanner",
        "uri": payload.get("uri"),
        "ok": payload.get("ok"),
        "error": payload.get("error"),
        "result": payload.get("result"),
        "at": payload.get("at") or _utc_now(),
    }
    try:
        _host_db().add_log(db, "page-action", "result", detail)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "result": detail}


def _uri_action_catalog() -> list[dict]:
    return [
        {
            "uri": "scanner://page/ui/button/start-camera/command/click",
            "layer": "page",
            "kind": "command",
            "label": "Click the Start camera button in the scanner page",
            "sideEffects": ["dom-click", "camera-permission", "media-stream"],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://page/camera/command/start",
            "layer": "page",
            "kind": "command",
            "label": "Start browser camera stream",
            "sideEffects": ["camera-permission", "media-stream"],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://page/ui/button/torch/command/click",
            "layer": "page",
            "kind": "command",
            "label": "Click the camera light button in the scanner page",
            "sideEffects": ["dom-click", "camera-torch"],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://page/camera/command/torch",
            "layer": "page",
            "kind": "command",
            "label": "Set browser camera light/torch",
            "sideEffects": ["camera-torch"],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://page/camera/command/scan",
            "layer": "page",
            "kind": "command",
            "label": "Capture one frame and send it to host",
            "sideEffects": ["camera-read", "network", "document-write"],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://page/camera/command/best-pdf",
            "layer": "page",
            "kind": "command",
            "label": "Capture a burst and archive the best PDF",
            "sideEffects": ["camera-read", "network", "document-write"],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://page/camera/query/status",
            "layer": "page",
            "kind": "query",
            "label": "Inspect camera page state",
            "sideEffects": [],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://host/capture/command/run",
            "layer": "host",
            "kind": "command",
            "label": "Analyze or archive a scanner frame",
            "sideEffects": ["file-write", "ocr", "optional-document-write"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "scanner://host/best/command/finish",
            "layer": "host",
            "kind": "command",
            "label": "Archive the best frame from a scanner series",
            "sideEffects": ["file-write", "document-write", "chat-message"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "scanner://host/session/command/log",
            "layer": "host",
            "kind": "command",
            "label": "Log scanner page/session event",
            "sideEffects": ["chat-message"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "scanner://host/actions/query/list",
            "layer": "host",
            "kind": "query",
            "label": "List scanner URI actions across layers",
            "sideEffects": [],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/phone-scanner/command/start",
            "layer": "dashboard",
            "kind": "command",
            "label": "Start phone scanner service and QR message",
            "sideEffects": ["service-start", "chat-message", "qr-artifact"],
            "where": "host dashboard /api/uri/invoke",
        },
    ]


def _uri_action_lookup(uri: str) -> dict | None:
    for item in _uri_action_catalog():
        if item["uri"] == uri:
            return item
    aliases = {
        "scanner://host/capture": "scanner://host/capture/command/run",
        "scanner://host/best/finish": "scanner://host/best/command/finish",
        "scanner://host/session": "scanner://host/session/command/log",
        "scanner://page/start-button": "scanner://page/ui/button/start-camera/command/click",
        "scanner://page/torch": "scanner://page/camera/command/torch",
        "scanner://page/torch-button": "scanner://page/ui/button/torch/command/click",
        "dashboard://host/actions/query/list": "scanner://host/actions/query/list",
    }
    target = aliases.get(uri)
    if target:
        return _uri_action_lookup(target)
    return None


def _uri_mode(value: Any) -> str:
    mode = str(value or "execute").strip().lower()
    if mode in {"execute", "exec", "run"}:
        return "execute"
    return "dry-run"


def _uri_simulated_result(uri: str, mode: str, action_payload: dict, action: dict | None) -> dict:
    return {
        "ok": True,
        "uri": uri,
        "invokedUri": uri,
        "mode": mode,
        "simulated": True,
        "dryRun": True,
        "action": action or {"uri": uri},
        "payload": action_payload,
        "wouldRun": {
            "uri": uri,
            "layer": (action or {}).get("layer"),
            "kind": (action or {}).get("kind"),
            "sideEffects": (action or {}).get("sideEffects", []),
        },
    }


def uri_invoke(
    project: str,
    db: str | None,
    config: str | None,
    payload: dict,
    *,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
) -> dict:
    uri = str(payload.get("uri") or "").strip()
    action_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    mode = _uri_mode(payload.get("mode") or payload.get("runMode") or action_payload.get("mode"))
    if not uri:
        raise ValueError("uri is required")
    action = _uri_action_lookup(uri)

    if uri in {"scanner://host/actions/query/list", "dashboard://host/actions/query/list"}:
        return {"ok": True, "mode": mode, "actions": _uri_action_catalog(), "invokedUri": uri}

    if mode != "execute":
        return _uri_simulated_result(uri, mode, action_payload, action)

    if action and action.get("layer") == "page":
        source = str(payload.get("source") or action_payload.get("source") or "").strip().lower()
        if source in {"page", "scanner-page"}:
            raise ValueError(f"page URI action must be handled locally by the scanner page: {uri}")
        return page_action_enqueue(
            db,
            target=str(action_payload.get("target") or "scanner"),
            uri=uri,
            payload=action_payload,
            mode=mode,
            source=str(payload.get("source") or "uri-invoke"),
        )

    if uri in {"scanner://host/capture/command/run", "scanner://host/capture"}:
        result = scanner_capture(project, db, action_payload)
    elif uri in {"scanner://host/best/command/finish", "scanner://host/best/finish"}:
        result = scanner_best_finish(project, db, action_payload)
    elif uri in {"scanner://host/session/command/log", "scanner://host/session"}:
        result = scanner_session(db, action_payload)
    elif uri == "dashboard://host/phone-scanner/command/start":
        result = ensure_phone_scanner_service(
            project,
            db,
            config,
            node_urls=node_urls,
            token=token,
            identity=identity,
        )
    else:
        raise ValueError(f"unsupported URI action: {uri}")

    if isinstance(result, dict):
        result.setdefault("invokedUri", uri)
        return result
    return {"ok": True, "invokedUri": uri, "result": result}


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
        queued_camera = None
        queued_torch = None
        camera_click_uri = "scanner://page/ui/button/start-camera/command/click"
        torch_click_uri = "scanner://page/ui/button/torch/command/click"
        torch_enabled = _torch_enabled_from_prompt(prompt)
        if _is_camera_start_prompt(prompt) or torch_enabled is not None:
            queued_camera = page_action_enqueue(
                db,
                target="scanner",
                uri=camera_click_uri,
                payload={"target": "scanner", "startBest": torch_enabled is None},
                mode="execute",
                source="chat",
            )
            camera_message = _chat_message(
                "system",
                "Camera start queued for the open scanner page. Open the scanner URL and accept the browser camera permission if prompted.",
                detail={
                    "uri": camera_click_uri,
                    "queued": queued_camera,
                    "scannerUrl": service.get("url"),
                },
            )
            _add_chat_message(db, camera_message)
        if torch_enabled is not None:
            queued_torch = page_action_enqueue(
                db,
                target="scanner",
                uri=torch_click_uri,
                payload={"target": "scanner", "enabled": bool(torch_enabled)},
                mode="execute",
                source="chat",
            )
            torch_message = _chat_message(
                "system",
                f"Camera light {'on' if torch_enabled else 'off'} queued for the open scanner page.",
                detail={
                    "uri": torch_click_uri,
                    "enabled": bool(torch_enabled),
                    "queued": queued_torch,
                    "scannerUrl": service.get("url"),
                },
            )
            _add_chat_message(db, torch_message)
        result = {
            "ok": bool(service.get("ok")),
            "prompt": prompt,
            "execute": True,
            "selectedNodes": selected_nodes,
            "generator": {"provider": "host-dashboard", "intent": "phone-scanner-service"},
            "flow": {
                "task": {"id": "phone-scanner-service", "title": "Start phone scanner service"},
                "steps": [
                    {"id": "start-phone-scanner", "uri": "dashboard://host/phone-scanner/command/start", "payload": {}},
                    *([{
                        "id": "queue-camera-start",
                        "uri": camera_click_uri,
                        "payload": {"target": "scanner", "startBest": torch_enabled is None},
                    }] if queued_camera else []),
                    *([{
                        "id": "queue-camera-light",
                        "uri": torch_click_uri,
                        "payload": {"target": "scanner", "enabled": bool(torch_enabled)},
                    }] if queued_torch else []),
                ],
            },
            "timeline": [
                {
                    "id": "start-phone-scanner",
                    "uri": "dashboard://host/phone-scanner/command/start",
                    "target": "host",
                    "ok": bool(service.get("ok")),
                    "status": service.get("status"),
                },
                *([{
                    "id": "queue-camera-start",
                    "uri": camera_click_uri,
                    "target": "scanner-page",
                    "ok": bool(queued_camera.get("ok")),
                    "status": "queued",
                }] if queued_camera else []),
                *([{
                    "id": "queue-camera-light",
                    "uri": torch_click_uri,
                    "target": "scanner-page",
                    "ok": bool(queued_torch.get("ok")),
                    "status": "queued",
                }] if queued_torch else []),
            ],
            "results": {
                "phone-scanner-service": service,
                **({"camera-start": queued_camera} if queued_camera else {}),
                **({"camera-torch": queued_torch} if queued_torch else {}),
            },
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
                if parsed.path == "/assets/urirun.js":
                    _js_sdk_response(self, project)
                    return
                if parsed.path == "/api/uri/event":
                    _json_response(self, 200, uri_event(db, parse_qs(parsed.query)))
                    return
                if parsed.path == "/api/page/actions/poll":
                    query = parse_qs(parsed.query)
                    _json_response(
                        self,
                        200,
                        page_action_poll(_first(query, "target", "scanner") or "scanner", int(_first(query, "limit", "4") or 4)),
                    )
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
                if parsed.path == "/api/uri/invoke":
                    payload = _read_json(self)
                    if not payload.get("source"):
                        ref_path = urlparse(self.headers.get("Referer", "") or "").path
                        if ref_path == "/scanner":
                            payload["source"] = "scanner-page"
                    _json_response(
                        self,
                        200,
                        uri_invoke(project, db, config, payload, node_urls=node_urls, token=token, identity=identity),
                    )
                    return
                if parsed.path == "/api/page/actions/result":
                    payload = _read_json(self)
                    _json_response(self, 200, page_action_result(db, payload))
                    return
                if parsed.path == "/api/scanner/capture":
                    payload = _read_json(self)
                    _json_response(self, 200, scanner_capture(project, db, payload))
                    return
                if parsed.path == "/api/scanner/best/finish":
                    payload = _read_json(self)
                    _json_response(self, 200, scanner_best_finish(project, db, payload))
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
