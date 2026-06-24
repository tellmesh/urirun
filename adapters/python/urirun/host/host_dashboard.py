# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Small host dashboard for planfile tasks, nodes and urirun activity."""

from __future__ import annotations

import base64
import html
import hashlib
import io
import json
import mimetypes
import os
import re
import shlex
import socket
import ssl
import subprocess
import sys
import textwrap
import threading
import time
import unicodedata
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, parse_qsl, quote, unquote, urlencode, urlparse, urlsplit, urlunsplit


try:
    from docid.dedup import (
        FINGERPRINT_DISTINCT_FIELDS as _DOCID_FINGERPRINT_DISTINCT_FIELDS,
        VISUAL_NEAR_DISTANCE as _DOCID_VISUAL_NEAR_DISTANCE,
        VISUAL_STRONG_DISTANCE as _DOCID_VISUAL_STRONG_DISTANCE,
        business_key as _dedup_business_key,
        dhash_distance as _dedup_dhash_distance,
        document_id as _dedup_document_id,
        document_matches as _dedup_document_matches,
        fingerprint_match_count as _dedup_fingerprint_match_count,
        image_dhash as _dedup_image_dhash,
        image_phash as _dedup_image_phash,
        metadata_completeness as _dedup_metadata_completeness,
        normalize_text as _dedup_normalize_text,
        transaction_fingerprint as _dedup_transaction_fingerprint,
    )
    from docid.visual_fingerprint import FieldSource as _DocidFieldSource
    from docid.visual_fingerprint import merge_records as _docid_merge_records
except Exception as _DOCID_DEDUP_IMPORT_ERROR:  # noqa: BLE001
    _DOCID_FINGERPRINT_DISTINCT_FIELDS = ("number", "auth", "time", "card")
    _DOCID_VISUAL_NEAR_DISTANCE = 10
    _DOCID_VISUAL_STRONG_DISTANCE = 6
    _DocidFieldSource = None
    _dedup_business_key = None
    _dedup_dhash_distance = None
    _dedup_document_id = None
    _dedup_document_matches = None
    _dedup_fingerprint_match_count = None
    _dedup_image_dhash = None
    _dedup_image_phash = None
    _dedup_metadata_completeness = None
    _dedup_normalize_text = None
    _dedup_transaction_fingerprint = None
    _docid_merge_records = None
else:
    _DOCID_DEDUP_IMPORT_ERROR = None


_SERVICE_LOCK = threading.Lock()
_SERVICE_SERVERS: dict[str, ThreadingHTTPServer] = {}
_SERVICE_THREADS: dict[str, threading.Thread] = {}
_DOCUMENT_INDEX_LOCK = threading.Lock()
_SCANNER_BEST_LOCK = threading.Lock()
_SCANNER_BEST_SESSIONS: dict[str, dict] = {}
_SCANNER_LIVE_STREAMS: dict[str, dict] = {}
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
      color-scheme: dark;
      --bg: #11100f;
      --surface: #181716;
      --surface-2: #201f1d;
      --surface-3: #292724;
      --ink: #f4f1e9;
      --muted: #aaa49a;
      --line: #3c3934;
      --line-soft: #302d29;
      --accent: #2dd4bf;
      --accent-ink: #06221f;
      --warn: #fbbf24;
      --bad: #fb7185;
      --good: #34d399;
      --topbar: rgba(24, 23, 22, 0.94);
      --pill-bg: #25231f;
      --pill-ink: #ded8cc;
      --good-bg: rgba(52, 211, 153, .14);
      --bad-bg: rgba(251, 113, 133, .16);
      --warn-bg: rgba(251, 191, 36, .16);
      --user-bg: rgba(45, 212, 191, .10);
      --system-bg: #1c1b19;
      --code-bg: #151412;
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
      background: var(--topbar);
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
    button.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); font-weight: 700; }
    button.danger { color: var(--bad); }
    button.active { border-color: var(--accent); box-shadow: inset 0 -2px 0 var(--accent); color: var(--accent); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    ::placeholder { color: #7f786f; }
    a { color: var(--accent); }
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
    body[data-view="chat"] .grid {
      grid-template-columns: minmax(0, 1fr);
      min-height: calc(100vh - 210px);
    }
    body[data-view="chat"] .grid > .stack:first-of-type {
      grid-column: 1 / -1;
      min-height: inherit;
    }
    body[data-view="chat"] .grid > aside.stack {
      display: none;
    }
    body[data-view="chat"] .chat-panel {
      min-height: inherit;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
    }
    body[data-view="chat"] .chat-panel .panel-body,
    body[data-view="chat"] .chat-shell,
    body[data-view="chat"] .chat-main {
      min-height: 0;
      height: 100%;
    }
    body[data-view="chat"] .chat-result {
      max-height: none;
      min-height: 0;
    }
    .discovery-layout {
      grid-column: 1 / -1;
      display: grid;
      gap: 14px;
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
    th, td { padding: 9px 8px; border-bottom: 1px solid var(--line-soft); text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; }
    .status, .pill {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 0 8px;
      border-radius: 999px;
      background: var(--pill-bg);
      color: var(--pill-ink);
      white-space: nowrap;
    }
    .status.done, .pill.up { background: var(--good-bg); color: var(--good); }
    .status.blocked, .status.failed, .pill.down { background: var(--bad-bg); color: var(--bad); }
    .status.in_progress, .pill.running { background: var(--warn-bg); color: var(--warn); }
    .stack { display: grid; gap: 14px; }
    .list { display: grid; gap: 8px; }
    .chat-shell {
      display: grid;
      grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
      gap: 12px;
      min-height: 640px;
    }
    .contacts-panel {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      gap: 8px;
      min-height: 0;
      padding-right: 12px;
      border-right: 1px solid var(--line-soft);
    }
    .contact-list {
      display: grid;
      align-content: start;
      gap: 8px;
      overflow: auto;
      min-height: 0;
    }
    .contact-card {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 8px;
      align-items: start;
      padding: 9px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: var(--surface-2);
    }
	    .contact-card input { margin-top: 2px; min-height: 0; }
	    .contact-title { font-weight: 700; overflow-wrap: anywhere; }
	    .contact-meta { color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }
	    .contact-body { display: grid; gap: 5px; min-width: 0; }
	    .contact-actions {
	      display: flex;
	      flex-wrap: wrap;
	      gap: 6px;
	      padding-top: 2px;
	    }
	    .contact-actions button {
	      min-height: 30px;
	      padding: 0 9px;
	      font-size: 12px;
	    }
	    .chat-main {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      gap: 10px;
      min-width: 0;
      min-height: 0;
    }
    .chat-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .chat-form { display: grid; gap: 10px; }
    .chat-composer {
      display: grid;
      gap: 10px;
      padding-top: 10px;
      border-top: 1px solid var(--line-soft);
    }
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
      min-height: 360px;
      max-height: 620px;
      overflow: auto;
    }
    .stream-list {
      display: grid;
      gap: 8px;
    }
    .stream-card {
      display: grid;
      gap: 8px;
      padding: 10px;
      border: 1px solid rgba(45, 212, 191, .28);
      border-radius: 8px;
      background: rgba(45, 212, 191, .08);
    }
    .stream-head, .stream-meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .stream-frames {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(86px, 1fr));
      gap: 6px;
    }
    .stream-frame {
      display: grid;
      gap: 4px;
      min-width: 0;
      padding: 6px;
      border: 1px solid var(--line-soft);
      border-radius: 6px;
      background: var(--surface-2);
    }
    .stream-frame img {
      width: 100%;
      aspect-ratio: 4 / 3;
      object-fit: cover;
      border-radius: 4px;
      background: var(--code-bg);
    }
    .service-table-wrap {
      overflow: auto;
      border: 1px solid var(--line-soft);
      border-radius: 6px;
    }
    .service-table-wrap table {
      width: 100%;
      min-width: 0;
      border: 0;
      border-radius: 0;
    }
    .service-media {
      width: 100%;
      max-height: 520px;
      object-fit: contain;
      border: 1px solid var(--line-soft);
      border-radius: 6px;
      background: var(--code-bg);
    }
    .service-frame {
      width: 100%;
      height: min(68vh, 720px);
      border: 1px solid var(--line-soft);
      border-radius: 6px;
      background: var(--code-bg);
    }
    .service-form-preview {
      display: grid;
      gap: 8px;
      padding: 10px;
      border: 1px solid var(--line-soft);
      border-radius: 6px;
      background: var(--surface-2);
    }
    .service-graph {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
    }
    .artifact-layout, .widget-layout {
      grid-column: 1 / -1;
      display: grid;
      gap: 14px;
    }
    .artifact-file-grid {
      display: grid;
      gap: 8px;
      overflow: auto;
    }
    .artifact-file-row {
      display: grid;
      grid-template-columns: 32px 280px minmax(220px, 1fr) minmax(180px, .65fr) minmax(150px, .45fr);
      gap: 10px;
      align-items: start;
      min-width: 1060px;
      padding: 8px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: var(--surface-2);
    }
    .artifact-file-row.header {
      position: sticky;
      top: 0;
      z-index: 1;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      background: var(--surface-3);
    }
    .artifact-thumb {
      display: grid;
      place-items: center;
      width: 264px;
      height: 200px;
      overflow: hidden;
      border: 1px solid var(--line-soft);
      border-radius: 6px;
      background: var(--code-bg);
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }
    .artifact-thumb img {
      width: 100%;
      height: 100%;
      border: 0;
      object-fit: cover;
      background: var(--code-bg);
      pointer-events: none;
    }
    .artifact-thumb-pdf, .attachment-pdf-preview {
      align-content: center;
      gap: 8px;
      color: var(--text);
      background:
        linear-gradient(180deg, rgba(248, 250, 252, .08), rgba(15, 23, 42, .1)),
        var(--code-bg);
    }
    .artifact-thumb-pdf span, .attachment-pdf-preview span {
      font-size: 28px;
      font-weight: 800;
      letter-spacing: 0;
    }
    .artifact-thumb-pdf small, .attachment-pdf-preview small {
      color: var(--muted);
      text-transform: none;
    }
    .artifact-thumb-missing {
      color: var(--danger);
      border-style: dashed;
      text-transform: none;
    }
    .artifact-name {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }
    .artifact-actions {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      margin-top: 4px;
    }
    .artifact-meta-line {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      color: var(--muted);
    }
    .widget-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 12px;
      align-items: start;
    }
    .widget-card {
      display: grid;
      gap: 8px;
      min-width: 0;
      align-content: start;
    }
    .widget-card > .stream-head,
    .widget-card > .subtle,
    .widget-card > .artifact-actions {
      padding: 0 2px;
    }
    .widget-preview {
      display: grid;
      gap: 8px;
      max-height: 720px;
      overflow: auto;
    }
    .message {
      display: grid;
      gap: 8px;
      padding: 10px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: var(--system-bg);
    }
    .message.user { background: var(--user-bg); border-color: rgba(45, 212, 191, .32); }
    .message.system { background: var(--system-bg); }
    .message-head { display: flex; justify-content: space-between; gap: 10px; align-items: center; }
    .message-title { display: inline-flex; align-items: center; gap: 8px; min-width: 0; }
    .message-actions { display: inline-flex; align-items: center; gap: 8px; }
    .attachments {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 8px;
    }
    .attachment {
      display: grid;
      gap: 6px;
      padding: 8px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: var(--surface-2);
    }
    .attachment img {
      width: 100%;
      max-height: 420px;
      object-fit: contain;
      border: 1px solid var(--line-soft);
      border-radius: 6px;
      background: var(--code-bg);
    }
    .attachment iframe {
      width: 100%;
      height: 520px;
      border: 1px solid var(--line-soft);
      border-radius: 6px;
      background: var(--code-bg);
    }
    .attachment.attachment-pdf {
      grid-column: span 2;
    }
    .attachment-pdf-preview {
      display: grid;
      place-items: center;
      min-height: 260px;
      border: 1px solid var(--line-soft);
      border-radius: 6px;
    }
    .attachment.attachment-qr {
      max-width: 380px;
    }
    .attachment.attachment-qr img {
      max-height: 340px;
      image-rendering: pixelated;
    }
    @media (max-width: 760px) {
      .attachment.attachment-pdf { grid-column: auto; }
      .attachment iframe { height: 420px; }
    }
    pre {
      margin: 0;
      padding: 10px;
      border: 1px solid var(--line-soft);
      border-radius: 6px;
      background: var(--code-bg);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .item {
      display: grid;
      gap: 4px;
      padding: 10px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: var(--surface-2);
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
      grid-template-columns: repeat(8, 1fr);
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
    body.chat-fullscreen .grid { height: 100%; display: block; }
    body.chat-fullscreen .grid > .stack { height: 100%; display: block; }
    body.chat-fullscreen .chat-panel {
      height: 100%;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
    }
    body.chat-fullscreen .chat-panel .panel-body,
    body.chat-fullscreen .chat-shell,
    body.chat-fullscreen .chat-main { height: 100%; min-height: 0; }
    body.chat-fullscreen .chat-shell { min-height: 0; }
    body.chat-fullscreen .chat-result {
      max-height: none;
      min-height: 0;
    }
    body.chat-fullscreen textarea { min-height: 86px; }
    @media (max-width: 920px) {
      .topbar { align-items: flex-start; flex-direction: column; }
      main { padding: 14px 12px 76px; }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .grid { grid-template-columns: 1fr; }
      .chat-shell { grid-template-columns: 1fr; min-height: 0; }
      .contacts-panel { border-right: 0; border-bottom: 1px solid var(--line-soft); padding-right: 0; padding-bottom: 10px; }
      .contact-list { max-height: 260px; }
      .artifact-file-row {
        grid-template-columns: 32px 188px minmax(180px, 1fr) minmax(140px, .65fr) minmax(150px, .45fr);
        min-width: 850px;
      }
      .artifact-thumb { width: 180px; height: 136px; }
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
        <button data-view="discovery">Discovery</button>
        <button data-view="artifacts">Artifacts</button>
        <button data-view="widgets">Widgets</button>
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
      <section class="discovery-layout view-block" data-section="discovery">
        <article class="panel">
          <div class="panel-head"><h2>Discovery</h2><span class="subtle" id="discoveryCount"></span></div>
          <div class="panel-body"><div class="list" id="discoveryList"></div></div>
        </article>
        <article class="panel">
          <div class="panel-head"><h2>Discovered URI Routes</h2><span class="subtle" id="discoveryRouteCount"></span></div>
          <div class="panel-body"><div class="list" id="discoveryRoutesList"></div></div>
        </article>
      </section>
      <section class="artifact-layout view-block" data-section="artifacts">
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2>Artifacts</h2>
              <p class="subtle">File-style grid/table of generated documents, scans and previews.</p>
            </div>
            <div class="actions">
              <span class="subtle" id="artifactCount"></span>
              <span class="subtle" id="artifactSelectionSummary">0 selected</span>
              <button type="button" id="artifactSelectVisibleBtn">Select visible</button>
              <button type="button" id="artifactClearSelectionBtn">Clear</button>
              <button type="button" class="danger" id="artifactDeleteSelectedBtn">Delete selected</button>
              <button type="button" class="danger" id="artifactDeleteVisibleBtn">Delete visible</button>
              <button type="button" id="artifactDedupeRowsBtn">Dedupe rows</button>
              <button type="button" id="artifactCleanupOrphansBtn">Cleanup orphan JSON</button>
              <button type="button" id="documentReconcileBtn">Reconcile docs index</button>
              <button type="button" id="artifactCopyJsonBtn">Copy JSON</button>
              <button type="button" id="artifactRefreshBtn">Refresh files</button>
            </div>
          </div>
          <div class="panel-body"><div class="artifact-file-grid" id="artifactFileGrid"></div></div>
        </article>
      </section>
      <section class="widget-layout view-block" data-section="widgets">
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2>Widgets</h2>
              <p class="subtle">Dashboard service previews and live views exposed by URI services.</p>
            </div>
            <div class="actions">
              <span class="subtle" id="widgetCount"></span>
              <button type="button" id="widgetRefreshBtn">Refresh widgets</button>
            </div>
          </div>
          <div class="panel-body"><div class="widget-grid" id="widgetGrid"></div></div>
        </article>
      </section>
      <div class="stack">
        <article class="panel view-block chat-panel" data-section="chat">
          <div class="panel-head">
            <div>
              <h2>Chat Result</h2>
              <p class="subtle">Natural language to URI flow across host, nodes and services.</p>
            </div>
            <div class="actions">
              <span class="subtle" id="chatStatus">idle</span>
              <span class="pill" id="chatMode">dry-run</span>
              <button id="chatFullscreenBtn" type="button">Full screen</button>
            </div>
          </div>
          <div class="panel-body">
            <div class="chat-shell">
              <div class="contacts-panel">
                <div>
                  <h3>Contacts</h3>
                  <p class="subtle">Select one or more URI targets.</p>
                </div>
                <div class="contact-list" id="chatContactList"></div>
              </div>
              <div class="chat-main">
                <div class="chat-toolbar">
                  <div class="subtle" id="chatTargetSummary">urirun host</div>
                  <div class="actions">
                    <span class="subtle" id="chatSelectionSummary">0 selected</span>
                    <button type="button" id="chatScrollBottomBtn">Latest</button>
                    <button type="button" id="chatCopyVisibleBtn">Copy chat</button>
                    <button type="button" id="chatSelectVisibleBtn">Select visible</button>
                    <button type="button" id="chatClearSelectionBtn">Clear</button>
                    <button type="button" class="danger" id="chatDeleteSelectedBtn">Delete selected</button>
                    <button type="button" class="danger" id="chatDeleteVisibleBtn">Delete all visible</button>
                  </div>
                </div>
                <div class="stream-list" id="chatStreamList"></div>
                <div class="chat-result" id="chatResult"></div>
                <form class="chat-form chat-composer" id="chatForm">
                  <textarea id="chatPrompt" placeholder="Napisz komendę NL do wybranych kontaktów URI..."></textarea>
                  <div class="chat-options">
                    <label class="check"><input type="checkbox" id="chatExecute"> Execute URI operations</label>
                    <label class="check"><input type="checkbox" id="chatNoLlm"> Heuristic planner only</label>
                    <button class="primary" type="submit" id="chatAskBtn">Send</button>
                  </div>
                </form>
              </div>
            </div>
          </div>
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
    <button data-view="discovery">Discovery</button>
    <button data-view="artifacts">Artifacts</button>
    <button data-view="widgets">Widgets</button>
    <button data-view="tasks">Tasks</button>
    <button data-view="nodes">Nodes</button>
    <button data-view="activity">Activity</button>
  </nav>
  <script>
    const VALID_VIEWS = new Set(['overview', 'chat', 'discovery', 'artifacts', 'widgets', 'tasks', 'nodes', 'activity']);
    const params = new URLSearchParams(window.location.search);
    const initialView = VALID_VIEWS.has(params.get('view')) ? params.get('view') : (VALID_VIEWS.has(params.get('tab')) ? params.get('tab') : 'overview');
    const initialChatFull = params.get('chat') === 'full' || params.get('fullscreen') === 'chat';
    const initialTargets = (params.get('targets') || 'host').split(',').map((item) => item.trim()).filter(Boolean);
    const state = {
      summary: null,
      tasks: [],
      artifacts: [],
      artifactRenderKey: '',
      selectedArtifactIds: new Set(),
      view: initialView,
      chatMessages: [],
      chatRenderKey: '',
      serviceViews: [],
      widgetRender: null,
      visibleChatMessages: [],
      visibleChatMessageIds: [],
      selectedChatMessageIds: new Set(),
      chatFullscreen: initialChatFull,
      selectedTargets: initialTargets.length ? initialTargets : ['host']
    };
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

    function compactJson(value) {
      try {
        return JSON.stringify(value || null);
      } catch (error) {
        return String(value);
      }
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
        no_llm: $('chatNoLlm') && $('chatNoLlm').checked ? '1' : '',
        targets: state.selectedTargets.join(',')
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
      setParam(search, 'targets', controls.targets || 'host');
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
      const targets = (search.get('targets') || 'host').split(',').map((item) => item.trim()).filter(Boolean);
      state.selectedTargets = targets.length ? targets : ['host'];
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

	    function contactCard(contact) {
	      const checked = state.selectedTargets.includes(contact.id) ? 'checked' : '';
	      const disabled = contact.disabled ? 'disabled' : '';
	      const pillClass = contact.reachable === false ? 'down' : contact.status === 'running' || contact.reachable ? 'up' : '';
	      const isPhoneScanner = contact.id === 'service:phone-scanner';
	      const startUri = isPhoneScanner ? 'dashboard://host/phone-scanner/command/start' : '';
	      const restartUri = isPhoneScanner ? 'dashboard://host/service/phone-scanner/command/restart' : '';
	      const inputId = `chat-target-${String(contact.id || 'target').replace(/[^a-zA-Z0-9_-]/g, '-')}`;
	      const actions = [
	        startUri ? `<button type="button" data-contact-action="invoke-uri" data-uri="${esc(startUri)}" data-target="${esc(contact.id)}">Start</button>` : '',
	        restartUri ? `<button type="button" data-contact-action="invoke-uri" data-uri="${esc(restartUri)}" data-target="${esc(contact.id)}">Restart</button>` : '',
	        contact.url ? `<button type="button" data-contact-action="open-url" data-url="${esc(contact.url)}" data-target="${esc(contact.id)}">Open</button>` : '',
	      ].filter(Boolean).join('');
	      return `<div class="contact-card">
	        <input id="${esc(inputId)}" type="checkbox" name="chatTarget" value="${esc(contact.id)}" ${checked} ${disabled}>
	        <span class="contact-body">
	          <label class="contact-title" for="${esc(inputId)}">${esc(contact.label)}</label>
	          <span class="pill ${pillClass}">${esc(contact.status || contact.kind)}</span>
	          <span class="contact-meta">${esc(contact.url || contact.meta || '')}</span>
	          ${actions ? `<span class="contact-actions">${actions}</span>` : ''}
	        </span>
	      </div>`;
	    }

    function chatContacts(summary) {
      const nodes = summary.nodes || [];
      const services = summary.services || [];
      return [
        { id: 'host', kind: 'host', label: 'urirun host', status: 'local', reachable: true, url: summary.project || '' },
        ...nodes.map((node) => ({
          id: `node:${node.name}`,
          kind: 'node',
          label: `urirun node: ${node.name}`,
          status: node.reachable ? 'up' : 'down',
          reachable: !!node.reachable,
          disabled: !node.reachable,
          url: node.url || '',
        })),
	        ...services.map((service) => ({
	          id: service.id || `service:${service.name}`,
	          kind: 'service',
	          label: service.label || `urirun service: ${service.name}`,
	          status: service.status || (service.reachable ? 'running' : 'stopped'),
	          reachable: !!service.reachable,
	          url: service.url || '',
	          routes: service.routes || [],
	        })),
	      ];
	    }

    function selectedTargets() {
      const values = [...document.querySelectorAll('input[name="chatTarget"]:checked')].map((item) => item.value);
      return values.length ? values : ['host'];
    }

    function selectedNodeNames() {
      return state.selectedTargets
        .filter((target) => target.startsWith('node:'))
        .map((target) => target.slice('node:'.length))
        .filter(Boolean);
    }

    function updateTargetSummary() {
      $('chatTargetSummary').textContent = `to: ${state.selectedTargets.join(', ') || 'host'}`;
    }

    function renderChatContacts(summary) {
      if (!state.selectedTargets.length) state.selectedTargets = ['host'];
      $('chatContactList').innerHTML = chatContacts(summary).map(contactCard).join('') || empty('No contacts');
      updateTargetSummary();
    }

    function renderDiscovery(summary) {
      const contacts = chatContacts(summary);
      const routes = summary.routes || [];
      $('discoveryCount').textContent = `${contacts.length} contacts`;
      $('discoveryList').innerHTML = contacts.map((contact) => `<div class="item">
        <div><strong>${esc(contact.label)}</strong> <span class="pill ${contact.reachable === false ? 'down' : 'up'}">${esc(contact.status || contact.kind)}</span></div>
        <div class="mono">${esc(contact.id)}</div>
        <div class="subtle">${esc(contact.url || '')}</div>
        <div class="subtle">${esc(contact.kind || '')}</div>
      </div>`).join('') || empty('No contacts discovered');
      $('discoveryRouteCount').textContent = `${routes.length} routes`;
      $('discoveryRoutesList').innerHTML = routes.map((route) => `<div class="item">
        <div class="mono">${esc(route.uri)}</div>
        <div class="subtle">node:${esc(route.node || 'host')} · ${esc(route.kind || '')} · ${esc(route.adapter || '')}</div>
      </div>`).join('') || empty('No routes discovered');
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

    function filePreviewUrl(path) {
      return path ? `/api/file?path=${encodeURIComponent(path)}` : '';
    }

    function artifactFileUrl(item) {
      if (item && item.filePreviewUrl !== undefined) return text(item.filePreviewUrl);
      if (item && item.fileExists === false) return '';
      return filePreviewUrl(item && item.path ? String(item.path) : '');
    }

    function artifactVisualPath(item) {
      const path = item && item.path ? String(item.path) : '';
      const meta = item && item.meta ? item.meta : {};
      if (/\.pdf$/i.test(path)) {
        return text(meta.displayImage || meta.displayPath || meta.previewImage || meta.image || '');
      }
      return path;
    }

    function artifactVisualPreviewUrl(item) {
      if (item && item.previewUrl !== undefined) return text(item.previewUrl);
      if (item && item.previewExists === false) return '';
      return filePreviewUrl(artifactVisualPath(item));
    }

    function artifactPreview(item) {
      const path = artifactVisualPath(item);
      const url = artifactVisualPreviewUrl(item);
      if (!url || !/\.(png|jpe?g|webp|gif)$/i.test(path)) return '';
      return `<img src="${esc(url)}" alt="${esc(basename(path))}" loading="lazy">`;
    }

    function artifactThumb(item) {
      const path = item && item.path ? String(item.path) : '';
      const visualPath = artifactVisualPath(item);
      const url = artifactVisualPreviewUrl(item);
      const ext = (path.match(/\.([a-z0-9]+)$/i) || [,'file'])[1].toLowerCase();
      if (/\.pdf$/i.test(path)) {
        if (url && /\.(png|jpe?g|webp|gif)$/i.test(visualPath)) {
          return `<div class="artifact-thumb"><img src="${esc(url)}" alt="${esc(basename(visualPath))}" loading="lazy"></div>`;
        }
        return `<div class="artifact-thumb artifact-thumb-pdf"><span>PDF</span><small>${esc(basename(path))}</small></div>`;
      }
      if (!url) return path ? `<div class="artifact-thumb artifact-thumb-missing">missing<br>file</div>` : `<div class="artifact-thumb">uri</div>`;
      if (/\.(png|jpe?g|webp|gif)$/i.test(visualPath)) {
        return `<div class="artifact-thumb"><img src="${esc(url)}" alt="${esc(basename(visualPath))}" loading="lazy"></div>`;
      }
      return `<div class="artifact-thumb">${esc(ext)}</div>`;
    }

    function artifactMetaSummary(item) {
      const meta = item.meta || {};
      const doc = (meta.document && meta.document.metadata) || meta.detectedDocument || meta.metadata || {};
      const parts = [
        doc.type || meta.type,
        doc.date || meta.date,
        doc.contractor || doc.supplier || doc.category || meta.contractor,
        doc.amount || meta.amount,
      ].filter(Boolean);
      return parts.join(' · ');
    }

    function renderArtifactFileRow(item) {
      const id = text(item.id);
      const path = text(item.path);
      const name = basename(path || item.uri || item.id);
      const url = artifactFileUrl(item);
      const metaLine = artifactMetaSummary(item);
      const openLink = url ? `<a href="${esc(url)}" target="_blank" rel="noreferrer">open</a>` : '';
      const download = url ? `<a href="${esc(url)}" download>download</a>` : '';
      const missing = path && item.fileExists === false ? '<span class="pill down">missing file</span>' : '';
      const selected = id && state.selectedArtifactIds.has(id) ? 'checked' : '';
      const duplicateCount = Number(item.duplicateCount || 0);
      const duplicates = duplicateCount > 1 ? `<span class="pill">${duplicateCount} records</span>` : '';
      return `<div class="artifact-file-row">
        <div><input type="checkbox" name="artifactSelect" value="${esc(id)}" ${selected}></div>
        ${artifactThumb(item)}
        <div>
          <div class="artifact-name"><strong>${esc(name)}</strong><span class="pill">${esc(item.kind || 'artifact')}</span>${duplicates}${missing}</div>
          <div class="mono">${esc(path || item.uri || '')}</div>
          <div class="artifact-actions">${openLink}${download}</div>
        </div>
        <div>
          <div class="mono">${esc(item.uri || '')}</div>
          ${metaLine ? `<div class="artifact-meta-line">${esc(metaLine)}</div>` : ''}
        </div>
        <div>
          <div class="subtle">${esc(item.created_at || '')}</div>
          ${id ? `<button type="button" class="danger" data-artifact-delete="${esc(id)}">Delete</button>` : ''}
          ${item.meta ? `<details><summary>metadata</summary><pre>${esc(JSON.stringify(item.meta, null, 2))}</pre></details>` : ''}
        </div>
      </div>`;
    }

    function visibleArtifactIds() {
      return state.artifacts.map((item) => item && item.id).filter(Boolean);
    }

    function selectedVisibleArtifactIds() {
      const visible = new Set(visibleArtifactIds());
      return [...state.selectedArtifactIds].filter((id) => visible.has(id));
    }

    function artifactIdsForDelete(ids) {
      const selected = new Set((ids || []).filter(Boolean));
      const out = new Set(selected);
      (state.artifacts || []).forEach((item) => {
        if (!item || !selected.has(item.id)) return;
        (item.duplicateIds || []).forEach((id) => out.add(id));
      });
      return [...out];
    }

    function updateArtifactSelectionControls() {
      const visibleCount = visibleArtifactIds().length;
      const selectedCount = selectedVisibleArtifactIds().length;
      $('artifactSelectionSummary').textContent = `${selectedCount} selected / ${visibleCount} visible`;
      $('artifactDeleteSelectedBtn').disabled = selectedCount === 0;
      $('artifactDeleteVisibleBtn').disabled = visibleCount === 0;
      $('artifactSelectVisibleBtn').disabled = visibleCount === 0;
      $('artifactClearSelectionBtn').disabled = selectedCount === 0;
      $('artifactCopyJsonBtn').disabled = visibleCount === 0;
    }

    function renderArtifactFileGrid(items) {
      $('artifactCount').textContent = `${items.length} file(s)`;
      $('artifactFileGrid').innerHTML = items.length
        ? `<div class="artifact-file-row header">
            <div></div><div>Preview</div><div>File</div><div>URI / document</div><div>Created</div>
          </div>${items.map(renderArtifactFileRow).join('')}`
        : empty('No artifacts recorded');
      updateArtifactSelectionControls();
    }

    function artifactRenderSignature(items) {
      return compactJson({
        selected: [...state.selectedArtifactIds].sort(),
        items: (items || []).map((item) => [
          item.id, item.kind, item.uri, item.path, item.created_at,
          item.duplicateCount || 0, item.duplicateIds || [],
          item.meta || null,
        ]),
      });
    }

    function renderArtifacts(items=[], options={}) {
      state.artifacts = items || [];
      const renderKey = artifactRenderSignature(state.artifacts);
      if (!options.force && renderKey === state.artifactRenderKey) {
        updateArtifactSelectionControls();
        return;
      }
      state.artifactRenderKey = renderKey;
      renderArtifactFileGrid(state.artifacts);
      $('artifactsList').innerHTML = state.artifacts.map((item) => `<div class="item">
        <div><strong>${item.kind}</strong></div>
        ${artifactPreview(item)}
        <div class="mono">${item.uri}</div>
        <div class="subtle">${text(item.path)} ${item.created_at || ''}</div>
        ${item.meta ? `<details><summary>metadata</summary><pre>${esc(JSON.stringify(item.meta, null, 2))}</pre></details>` : ''}
      </div>`).join('') || empty('No artifacts recorded');
    }

    async function loadArtifacts() {
      const data = await api('/api/artifacts?limit=80');
      renderArtifacts(data.artifacts || []);
    }

    async function deleteArtifacts(ids) {
      const clean = [...new Set((ids || []).filter(Boolean))];
      if (!clean.length) return;
      const expanded = artifactIdsForDelete(clean);
      const result = await api('/api/artifacts/delete', {
        method: 'POST',
        body: JSON.stringify({ ids: expanded, deleteFiles: true }),
      });
      expanded.forEach((id) => state.selectedArtifactIds.delete(id));
      state.artifacts = state.artifacts.filter((item) => !expanded.includes(item.id));
      renderArtifacts(state.artifacts, { force: true });
      await loadArtifacts();
      writeUrlState({ action: 'artifacts:delete', deleted: result.deleted || 0 }, { replace: true });
    }

    async function cleanupArtifactOrphans() {
      const result = await api('/api/artifacts/cleanup-orphans', {
        method: 'POST',
        body: JSON.stringify({ deleteFiles: true }),
      });
      await loadArtifacts();
      writeUrlState({ action: 'artifacts:cleanup-orphans', deleted: result.filesDeleted || 0 }, { replace: true });
    }

    async function dedupeArtifactRows() {
      const result = await api('/api/artifacts/dedupe', {
        method: 'POST',
        body: JSON.stringify({ deleteRows: true }),
      });
      await loadArtifacts();
      writeUrlState({ action: 'artifacts:dedupe', deleted: result.deleted || 0 }, { replace: true });
    }

    async function reconcileDocumentsIndex() {
      const result = await api('/api/documents/reconcile', { method: 'POST', body: '{}' });
      await loadArtifacts();
      const pruned = result.prunedCount || 0;
      writeUrlState({ action: 'documents:reconcile', pruned }, { replace: true });
      alert(pruned ? `Pruned ${pruned} orphaned document(s) from the index.` : 'Index already consistent; nothing pruned.');
    }

    function artifactTableJsonRow(item) {
      const path = text(item.path);
      return {
        id: text(item.id),
        kind: text(item.kind),
        name: basename(path || item.uri || item.id),
        uri: text(item.uri),
        path,
        fileExists: item.fileExists === undefined ? null : Boolean(item.fileExists),
        previewExists: item.previewExists === undefined ? null : Boolean(item.previewExists),
        visualPath: text(item.visualPath),
        filePreviewUrl: text(item.filePreviewUrl),
        previewUrl: text(item.previewUrl),
        duplicateCount: Number(item.duplicateCount || 1),
        duplicateIds: item.duplicateIds || [],
        duplicateArtifactIds: item.duplicateArtifactIds || [],
        duplicateUris: item.duplicateUris || [],
        created_at: text(item.created_at),
        metadata: item.meta || {},
      };
    }

    async function copyArtifactsJson() {
      const rows = (state.artifacts || []).map(artifactTableJsonRow);
      if (!rows.length) return;
      const content = JSON.stringify({
        generatedAt: new Date().toISOString(),
        source: 'urirun-dashboard-artifacts',
        count: rows.length,
        artifacts: rows,
      }, null, 2);
      await copyTextToClipboard(content);
      window.__urirunLastCopiedArtifactsJson = content;
      writeUrlState({ action: 'artifacts:copy-json', copied: rows.length }, { replace: true });
    }

    function basename(path) {
      return text(path).split('/').filter(Boolean).pop() || text(path);
    }

    function attachmentVisualPreviewUrl(att) {
      const meta = att.meta || {};
      const displayPath = text(meta.displayImage || meta.displayPath || meta.previewImage || meta.image || '');
      return displayPath ? filePreviewUrl(displayPath) : '';
    }

    function isPdfAttachment(att) {
      return att && (att.kind === 'document-pdf' || /\.pdf$/i.test(text(att.path)));
    }

    function isScannerFrameAttachment(att) {
      if (!att) return false;
      const kind = text(att.kind);
      const uri = text(att.uri);
      return ['receipt-crop', 'image', 'camera-scan'].includes(kind) || uri.startsWith('scanner://host/capture/');
    }

    function messageAttachments(message) {
      const detail = message.detail || {};
      const document = detail.document || {};
      const attachments = messageAttachments(message);
      const hasPdf = attachments.some(isPdfAttachment);
      return attachments.filter((att) => {
        if (isPdfAttachment(att)) return true;
        if (hasPdf && isScannerFrameAttachment(att)) return false;
        if (isScannerFrameAttachment(att) && !(document.ok && document.path)) return false;
        return true;
      });
    }

    function renderAttachment(att) {
      const meta = att.meta || {};
      const ocr = meta.ocr || {};
      const isPdf = isPdfAttachment(att);
      const kindClass = att.kind === 'qr-code' ? ' attachment-qr' : isPdf ? ' attachment-pdf' : '';
      const visualUrl = isPdf ? attachmentVisualPreviewUrl(att) : text(att.previewUrl || '');
      const pdfUrl = isPdf ? text(att.previewUrl || '') : '';
      const preview = isPdf && pdfUrl
        ? `<iframe class="attachment-pdf-frame" src="${esc(pdfUrl)}" title="${esc(basename(att.path))}" loading="lazy"></iframe>`
        : (visualUrl
          ? `<img src="${esc(visualUrl)}" alt="${esc(basename(att.path))}" loading="lazy">`
          : (isPdf
            ? `<div class="attachment-pdf-preview"><span>PDF</span><small>${esc(basename(att.path))}</small></div>`
            : `<div class="subtle">preview unavailable</div>`));
      const open = att.previewUrl
        ? `<a href="${esc(att.previewUrl)}" target="_blank" rel="noreferrer">open</a>`
        : '';
      const download = att.previewUrl ? `<a href="${esc(att.previewUrl)}" download>download</a>` : '';
      const ocrLine = ocr.ok
        ? `<div class="subtle">OCR ${esc(ocr.backend || '')}: ${esc(text(ocr.text).slice(0, 160))}</div>`
        : (ocr.error ? `<div class="subtle">OCR: ${esc(ocr.error)}</div>` : '');
      return `<div class="attachment${kindClass}">
        ${preview}
        <div class="mono">${esc(basename(att.path))}</div>
        <div class="subtle">${esc(att.kind || 'file')} ${meta.width && meta.height ? `· ${meta.width}x${meta.height}` : ''}</div>
        <div class="artifact-actions">${open}${download}</div>
        ${ocrLine}
        <details><summary>metadata</summary><pre>${esc(JSON.stringify(att, null, 2))}</pre></details>
      </div>`;
    }

    function streamStatusClass(status) {
      if (status === 'accepted') return 'up';
      if (status === 'rejected' || status === 'failed') return 'down';
      return 'running';
    }

    function streamDocLabel(candidate) {
      const doc = candidate && candidate.detectedDocument ? candidate.detectedDocument : {};
      const parts = [doc.type, doc.date, doc.contractor || doc.supplier || doc.category, doc.amount].filter(Boolean);
      return parts.join(' · ') || 'document candidate';
    }

    function streamQualityLabel(candidate) {
      const quality = candidate && candidate.quality ? candidate.quality : {};
      const reasons = Array.isArray(quality.reasons) ? quality.reasons.filter(Boolean) : [];
      const crop = candidate && candidate.crop ? candidate.crop : {};
      const cropReason = quality.cropReason || crop.reason || '';
      return [...reasons, cropReason].filter(Boolean).join(' · ');
    }

    function renderStreamFrame(candidate) {
      const quality = candidate && candidate.quality ? candidate.quality : {};
      const score = Number(quality.score || 0).toFixed(1);
      const qualityLabel = streamQualityLabel(candidate);
      const previewUrl = candidate && (candidate.overlayPreviewUrl || candidate.previewUrl || '');
      const preview = previewUrl
        ? `<img src="${esc(previewUrl)}" alt="${esc(streamDocLabel(candidate))}" loading="lazy">`
        : '';
      return `<div class="stream-frame">
        ${preview}
        <div class="mono">#${esc(candidate && candidate.frameIndex || '')} · ${score}</div>
        <div class="subtle">${esc(streamDocLabel(candidate))}</div>
        ${qualityLabel ? `<div class="subtle">${esc(qualityLabel)}</div>` : ''}
        ${candidate && candidate.overlayPreviewUrl ? `<a href="${esc(candidate.overlayPreviewUrl)}" target="_blank" rel="noreferrer">overlay</a>` : ''}
      </div>`;
    }

    function renderScannerStream(stream, title='phone scanner stream') {
      const best = stream.best || {};
      const quality = best.quality || {};
      const document = stream.document || {};
      const status = stream.status || 'running';
      const accepted = status === 'accepted' && document.path;
      const bestScore = Number(quality.score || 0).toFixed(1);
      const bestQualityLabel = streamQualityLabel(best);
      const frames = stream.candidates || [];
      return `<div class="stream-card">
        <div class="stream-head">
          <strong>${esc(title)}</strong>
          <span class="pill ${streamStatusClass(status)}">${esc(status)}</span>
        </div>
        <div class="stream-meta">
          <span class="subtle">${esc(stream.seriesId || '')}</span>
          <span class="subtle">${esc(stream.updatedAt || '')}</span>
        </div>
        <div><strong>${esc(streamDocLabel(best))}</strong></div>
        <div class="subtle">${esc(stream.count || 0)} frame(s) · best score ${esc(bestScore)}${bestQualityLabel ? ` · ${esc(bestQualityLabel)}` : ''}${stream.error ? ` · ${esc(stream.error)}` : ''}</div>
        ${accepted ? `<div><a href="${esc(document.previewUrl || `/api/file?path=${encodeURIComponent(document.path)}`)}" download>${esc(basename(document.path))}</a></div>` : ''}
        ${frames.length ? `<div class="stream-frames">${frames.map(renderStreamFrame).join('')}</div>` : ''}
        <details><summary>URI / JSON</summary><pre>${esc(JSON.stringify(stream, null, 2))}</pre></details>
      </div>`;
    }

    function renderScannerArtifactFrame(item) {
      const label = [item.type, item.date, item.contractor || item.supplier || item.category, item.amount].filter(Boolean).join(' · ')
        || item.label || basename(item.path || item.uri || '');
      const preview = item.previewUrl
        ? `<img src="${esc(item.previewUrl)}" alt="${esc(label)}" loading="lazy">`
        : '';
      const href = item.filePreviewUrl || item.previewUrl || '';
      return `<div class="stream-frame">
        ${preview}
        <div class="mono">${esc(item.kind || 'artifact')}</div>
        <div class="subtle">${esc(label)}</div>
        ${href ? `<a href="${esc(href)}" target="_blank" rel="noreferrer">open</a>` : ''}
      </div>`;
    }

    function renderScannerStatusServiceView(view) {
      const data = view.data || {};
      const service = data.service || {};
      const camera = data.cameraStatus || {};
      const recent = Array.isArray(data.recentArtifacts) ? data.recentArtifacts : [];
      const ready = camera.ready ? 'ready' : (camera.ok === false ? 'error' : 'not ready');
      const track = camera.track || {};
      const body = `<div class="service-graph">
          <div class="item">
            <strong>service</strong>
            <div><span class="pill ${service.reachable ? 'up' : 'down'}">${esc(service.status || 'unknown')}</span></div>
            <div class="mono">${esc(service.url || '')}</div>
          </div>
          <div class="item">
            <strong>browser camera</strong>
            <div><span class="pill ${camera.ready ? 'up' : 'down'}">${esc(ready)}</span></div>
            <div class="subtle">${esc(camera.width || 0)}x${esc(camera.height || 0)} · ${esc(track.readyState || '')}</div>
            <div class="mono">${esc(track.label || camera.uri || '')}</div>
            ${camera.error ? `<div class="subtle">${esc(camera.error)}</div>` : ''}
          </div>
        </div>
        ${recent.length ? `<div class="stream-frames">${recent.map(renderScannerArtifactFrame).join('')}</div>` : '<div class="subtle">No scanner artifacts yet</div>'}`;
      return renderServiceViewShell(view, body);
    }

    function renderGenericServiceView(view) {
      const data = view.data || {};
      return `<div class="stream-card">
        <div class="stream-head">
          <strong>${esc(view.title || view.id || 'service view')}</strong>
          <span class="pill ${streamStatusClass(view.status || 'running')}">${esc(view.status || view.kind || 'live')}</span>
        </div>
        <div class="stream-meta">
          <span class="subtle">${esc(view.target || view.serviceId || '')}</span>
          <span class="subtle">${esc(view.updatedAt || '')}</span>
        </div>
        <details open><summary>service data</summary><pre>${esc(JSON.stringify(data, null, 2))}</pre></details>
      </div>`;
    }

    function renderTableServiceView(view) {
      const data = view.data || {};
      const rows = Array.isArray(data.rows) ? data.rows : [];
      const explicitColumns = Array.isArray(data.columns) ? data.columns : [];
      const columns = explicitColumns.length
        ? explicitColumns.map((column) => typeof column === 'string' ? column : column.key || column.name || column.label).filter(Boolean)
        : [...new Set(rows.flatMap((row) => Object.keys(row || {})))];
      const table = columns.length
        ? `<div class="service-table-wrap"><table>
            <thead><tr>${columns.map((column) => `<th>${esc(column)}</th>`).join('')}</tr></thead>
            <tbody>${rows.map((row) => `<tr>${columns.map((column) => `<td>${esc(text(row && row[column]))}</td>`).join('')}</tr>`).join('')}</tbody>
          </table></div>`
        : `<div class="subtle">no rows</div>`;
      return renderServiceViewShell(view, table);
    }

    function renderImageServiceView(view) {
      const data = view.data || {};
      const images = Array.isArray(data.images) ? data.images : [data.url || data.previewUrl || data.src].filter(Boolean);
      const body = images.length
        ? `<div class="stream-frames">${images.map((image) => {
            const item = typeof image === 'string' ? { url: image } : image;
            return `<div class="stream-frame">
              <img src="${esc(item.url || item.previewUrl || item.src || '')}" alt="${esc(item.label || view.title || 'service image')}" loading="lazy">
              ${item.label ? `<div class="subtle">${esc(item.label)}</div>` : ''}
            </div>`;
          }).join('')}</div>`
        : `<div class="subtle">no image</div>`;
      return renderServiceViewShell(view, body);
    }

    function renderVideoServiceView(view) {
      const data = view.data || {};
      const url = data.url || data.src || data.streamUrl;
      const body = url
        ? `<video class="service-media" src="${esc(url)}" controls muted playsinline></video>`
        : `<div class="subtle">no video stream</div>`;
      return renderServiceViewShell(view, body);
    }

    function renderIframeServiceView(view) {
      const data = view.data || {};
      const url = data.url || data.src || data.href;
      const body = url
        ? `<iframe class="service-frame" src="${esc(url)}" title="${esc(view.title || 'service page')}" loading="lazy"></iframe>`
        : `<div class="subtle">no page url</div>`;
      return renderServiceViewShell(view, body);
    }

    function renderFormServiceView(view) {
      const data = view.data || {};
      const fields = Array.isArray(data.fields) ? data.fields : [];
      const actionUri = data.actionUri || data.uri || view.actionUri || '';
      const body = `<form class="service-form-preview" data-service-form data-action-uri="${esc(actionUri)}">
        ${fields.map((field) => {
          const name = field.name || field.key || field.label || 'field';
          const type = field.type || 'text';
          const value = field.value || field.default || '';
          const checked = type === 'checkbox' && (field.checked || value === true || value === 'true') ? 'checked' : '';
          return `<label class="stack">
            <span class="subtle">${esc(field.label || name)}</span>
            <input type="${esc(type)}" name="${esc(name)}" value="${esc(value)}" ${checked} ${field.readonly ? 'readonly' : ''}>
          </label>`;
        }).join('') || '<div class="subtle">no fields</div>'}
        ${actionUri ? `<div class="mono">${esc(actionUri)}</div><button type="submit">Run URI</button>` : '<div class="subtle">no action URI</div>'}
      </form>`;
      return renderServiceViewShell(view, body);
    }

    function renderGraphServiceView(view) {
      const data = view.data || {};
      const nodes = Array.isArray(data.nodes) ? data.nodes : [];
      const edges = Array.isArray(data.edges) ? data.edges : [];
      const body = `<div class="service-graph">
        <div class="item"><strong>nodes</strong>${nodes.map((node) => `<div class="mono">${esc(node.id || node.name || JSON.stringify(node))}</div>`).join('') || '<div class="subtle">none</div>'}</div>
        <div class="item"><strong>edges</strong>${edges.map((edge) => `<div class="mono">${esc(edge.from || edge.source || '')} -> ${esc(edge.to || edge.target || '')}</div>`).join('') || '<div class="subtle">none</div>'}</div>
      </div>`;
      return renderServiceViewShell(view, body);
    }

    function renderServiceViewShell(view, body) {
      return `<div class="stream-card">
        <div class="stream-head">
          <strong>${esc(view.title || view.id || 'service view')}</strong>
          <span class="pill ${streamStatusClass(view.status || 'running')}">${esc(view.status || view.kind || 'live')}</span>
        </div>
        <div class="stream-meta">
          <span class="subtle">${esc(view.target || view.serviceId || '')}</span>
          <span class="subtle">${esc(view.updatedAt || '')}</span>
        </div>
        ${body}
        <details><summary>URI / JSON</summary><pre>${esc(JSON.stringify(view, null, 2))}</pre></details>
      </div>`;
    }

    function renderServiceView(view) {
      if (view.view === 'scanner-status') return renderScannerStatusServiceView(view);
      if (view.view === 'scanner-stream') {
        const streams = view.data && Array.isArray(view.data.streams) ? view.data.streams : [];
        return streams.map((stream) => renderScannerStream(stream, view.title || 'phone scanner stream')).join('');
      }
      if (view.view === 'table') return renderTableServiceView(view);
      if (view.view === 'image' || view.view === 'image-list') return renderImageServiceView(view);
      if (view.view === 'video') return renderVideoServiceView(view);
      if (view.view === 'iframe' || view.view === 'page' || view.view === 'web') return renderIframeServiceView(view);
      if (view.view === 'form') return renderFormServiceView(view);
      if (view.view === 'graph') return renderGraphServiceView(view);
      return renderGenericServiceView(view);
    }

    function serviceWidgetLinks(service, view) {
      const target = service.id || view.target || view.serviceId || '';
      const links = [];
      if (target) {
        links.push(`<a href="/services/view?target=${encodeURIComponent(target)}" target="_blank" rel="noreferrer">HTML widget</a>`);
        links.push(`<a href="/services/view.svg?target=${encodeURIComponent(target)}" target="_blank" rel="noreferrer">SVG</a>`);
      }
      if (service.url) links.push(`<a href="${esc(service.url)}" target="_blank" rel="noreferrer">open service</a>`);
      return links.length ? `<div class="artifact-actions">${links.join('')}</div>` : '';
    }

    function renderWidgetCard(service, view) {
      const safeView = view || {};
      const status = service.status || safeView.status || 'live';
      const target = service.id || safeView.target || safeView.serviceId || '';
      const fallbackView = service.url
        ? {title: `${service.name || target || 'service'} page`, target, status, view: 'page', data: {url: service.url}}
        : null;
      const preview = view
        ? renderServiceView(view)
        : (fallbackView ? renderIframeServiceView(fallbackView) : `<div class="stream-card"><div class="subtle">No live view published yet for this service.</div></div>`);
      return `<div class="widget-card">
        <div class="stream-head">
          <div>
            <strong>${esc(service.label || service.name || safeView.title || target || 'service')}</strong>
            <div class="mono">${esc(target)}</div>
          </div>
          <span class="pill ${status === 'running' || status === 'up' || status === 'live' ? 'up' : 'down'}">${esc(status)}</span>
        </div>
        <div class="subtle">${esc(service.url || service.bindUrl || safeView.updatedAt || '')}</div>
        ${serviceWidgetLinks(service, safeView)}
        <div class="widget-preview">${preview}</div>
      </div>`;
    }

    function renderWidgetDashboard() {
      const services = state.summary && Array.isArray(state.summary.services) ? state.summary.services : [];
      const views = state.serviceViews || [];
      const used = new Set();
      const cards = services.map((service) => {
        const view = views.find((item) => item.target === service.id || item.serviceId === service.id || item.serviceId === service.name || item.target === service.name);
        if (view) used.add(view.id || view.target || view.serviceId);
        return renderWidgetCard(service, view);
      });
      views.forEach((view) => {
        const key = view.id || view.target || view.serviceId;
        if (used.has(key)) return;
        cards.push(renderWidgetCard({id: view.target || view.serviceId, label: view.title || view.serviceId || view.target, status: view.status || view.kind || 'live'}, view));
      });
      $('widgetCount').textContent = `${cards.length} widget(s)`;
      $('widgetGrid').innerHTML = cards.join('') || empty('No services or widgets available');
    }

    function renderServiceViews() {
      const active = state.selectedTargets.length ? state.selectedTargets : ['host'];
      const visible = state.serviceViews.filter((view) => active.includes(view.target) || active.includes(view.serviceId));
      // Prefer the widget catalogue loaded over widget://host/bundle/query/js; fall back to the
      // inline renderers if that URI request hasn't resolved (or failed).
      const render = state.widgetRender || renderServiceView;
      $('chatStreamList').innerHTML = visible.map(render).join('');
      renderWidgetDashboard();
    }

    // Load the chat-stream widgets from the widget:// connector over a URI request, so the page
    // renders chatStreamList from the published catalogue instead of its inline copy. Best-effort:
    // any failure leaves state.widgetRender null and the inline renderers keep working.
    async function loadWidgetBundleViaUri() {
      try {
        const jsRes = await api('/api/uri/invoke', {
          method: 'POST',
          body: JSON.stringify({ uri: 'widget://host/bundle/query/js', mode: 'execute', payload: {}, source: 'widget-bundle' }),
        });
        const js = jsRes && jsRes.result && jsRes.result.js;
        if (js) {
          // The bundle is a single concatenated module (imports/exports stripped); evaluate it in
          // its own scope and hand back its renderServiceView.
          const factory = new Function(js + "\n;return (typeof renderServiceView === 'function') ? renderServiceView : null;");
          const fn = factory();
          if (typeof fn === 'function') state.widgetRender = fn;
        }
        const cssRes = await api('/api/uri/invoke', {
          method: 'POST',
          body: JSON.stringify({ uri: 'widget://host/bundle/query/css', mode: 'execute', payload: {}, source: 'widget-bundle' }),
        });
        const css = cssRes && cssRes.result && cssRes.result.css;
        if (css) {
          let styleEl = $('urirunWidgetCss');
          if (!styleEl) {
            styleEl = document.createElement('style');
            styleEl.id = 'urirunWidgetCss';
            document.head.appendChild(styleEl);
          }
          styleEl.textContent = css;
        }
        if (state.widgetRender) renderServiceViews();
      } catch (error) {
        // keep the inline renderers (state.widgetRender stays null)
        if (window.console) console.warn('widget bundle load failed, using inline renderers:', error.message);
      }
    }

    async function loadServiceViews() {
      const data = await api('/api/services/live?limit=8');
      state.serviceViews = data.views || [];
      renderServiceViews();
      renderChatHistory();
    }

    function renderChatMessage(message) {
      const detail = message.detail || {};
      const timeline = detail.timeline || [];
      const lines = timeline.map((step) => `${step.ok ? 'ok' : 'fail'} · ${step.target || ''} · ${step.uri}`).join('\n');
      const attachments = messageAttachments(message);
      const role = message.role || 'system';
      const selected = message.id && state.selectedChatMessageIds.has(message.id) ? 'checked' : '';
      const checkbox = message.id ? `<input type="checkbox" name="chatMessageSelect" value="${esc(message.id)}" ${selected}>` : '';
      const deleteButton = message.id ? `<button type="button" class="danger" data-chat-delete="${esc(message.id)}">Delete</button>` : '';
      return `<div class="message ${esc(role)}">
        <div class="message-head">
          <span class="message-title">${checkbox}<strong>${esc(role)}</strong></span>
          <span class="message-actions">
            <span class="subtle">${esc(message.created_at || '')}</span>
            ${deleteButton}
          </span>
        </div>
        <div>${esc(message.content || '')}</div>
        ${lines ? `<pre>${esc(lines)}</pre>` : ''}
        ${attachments.length ? `<div class="attachments">${attachments.map(renderAttachment).join('')}</div>` : ''}
        ${Object.keys(detail).length ? `<details><summary>URI / JSON</summary><pre>${esc(JSON.stringify(detail, null, 2))}</pre></details>` : ''}
      </div>`;
    }

    function addTargetsFromText(out, value) {
      const raw = text(value).toLowerCase();
      if (!raw) return;
      if (raw.includes('phone-scanner') || raw.includes('scanner://') || raw.includes('/scanner') || raw.includes('camera') || raw.includes('qr-code')) {
        out.add('service:phone-scanner');
      }
      if (raw.includes('dashboard://host') || raw.includes('host dashboard')) out.add('host');
      const uriNode = raw.match(/[a-z][a-z0-9+.-]*:\/\/([a-z0-9_.-]+)/);
      if (uriNode && uriNode[1] && !['host', 'local'].includes(uriNode[1])) out.add(`node:${uriNode[1]}`);
    }

    function messageTargets(message) {
      const out = new Set();
      const detail = message.detail || {};
      (detail.selectedTargets || []).forEach((target) => out.add(target));
      (detail.selectedNodes || []).forEach((node) => out.add(`node:${node}`));
      const timeline = detail.timeline || [];
      timeline.forEach((step) => {
        if (step.target === 'host') out.add('host');
        else if (step.target) out.add(`node:${step.target}`);
        addTargetsFromText(out, step.uri);
      });
      addTargetsFromText(out, detail.uri);
      addTargetsFromText(out, detail.scannerUrl);
      addTargetsFromText(out, detail.href);
      addTargetsFromText(out, message.content);
      (message.attachments || []).forEach((att) => {
        addTargetsFromText(out, att.uri);
        addTargetsFromText(out, att.path);
        addTargetsFromText(out, att.previewUrl);
        addTargetsFromText(out, att.kind);
      });
      if (!out.size && message.role === 'user') out.add('host');
      if (!out.size && /host|dashboard/i.test(JSON.stringify(detail))) out.add('host');
      return out;
    }

    function messageMatchesTargets(message) {
      const active = state.selectedTargets.length ? state.selectedTargets : ['host'];
      const targets = messageTargets(message);
      if (!targets.size) return active.includes('host');
      return active.some((target) => targets.has(target));
    }

    function isGroupedScannerEventMessage(message) {
      const scannerLiveVisible = state.serviceViews.some((view) => view.target === 'service:phone-scanner' || view.serviceId === 'service:phone-scanner');
      if (!state.selectedTargets.includes('service:phone-scanner') || !scannerLiveVisible) return false;
      const detail = message.detail || {};
      const event = String(detail.event || '');
      if (['open', 'camera-started', 'autonomous-start-requested', 'torch-changed'].includes(event)) return true;
      const content = String(message.content || '').toLowerCase();
      return content === 'phone scanner opened'
        || content === 'phone scanner camera started'
        || content === 'phone scanner autonomous-start-requested';
    }

    function selectedVisibleChatMessageIds() {
      return state.visibleChatMessageIds.filter((id) => state.selectedChatMessageIds.has(id));
    }

    function updateChatSelectionControls() {
      const visibleCount = state.visibleChatMessageIds.length;
      const selectedCount = selectedVisibleChatMessageIds().length;
      $('chatSelectionSummary').textContent = `${selectedCount} selected / ${visibleCount} visible`;
      $('chatCopyVisibleBtn').disabled = visibleCount === 0;
      $('chatDeleteSelectedBtn').disabled = selectedCount === 0;
      $('chatDeleteVisibleBtn').disabled = visibleCount === 0;
      $('chatSelectVisibleBtn').disabled = visibleCount === 0;
      $('chatClearSelectionBtn').disabled = selectedCount === 0;
    }

    function chatMessagePlainText(message) {
      const detail = message.detail || {};
      const timeline = detail.timeline || [];
      const attachments = message.attachments || [];
      const parts = [
        `[${message.created_at || ''}] ${message.role || 'system'}`,
        text(message.content || ''),
      ].filter(Boolean);
      if (timeline.length) {
        parts.push('URI timeline:');
        timeline.forEach((step) => {
          parts.push(`- ${step.ok ? 'ok' : 'fail'} ${step.target || ''} ${step.uri || ''}`.trim());
        });
      }
      if (attachments.length) {
        parts.push('Attachments:');
        attachments.forEach((att) => {
          parts.push(`- ${att.kind || 'file'} ${att.path || att.uri || att.previewUrl || ''}`.trim());
        });
      }
      return parts.join('\n');
    }

    async function copyTextToClipboard(value) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(value);
        return;
      }
      const textarea = document.createElement('textarea');
      textarea.value = value;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      textarea.remove();
    }

    async function copyVisibleChat() {
      const content = state.visibleChatMessages.map(chatMessagePlainText).join('\n\n---\n\n');
      if (!content) return;
      await copyTextToClipboard(content);
      window.__urirunLastCopiedChat = content;
      $('chatStatus').textContent = `copied ${state.visibleChatMessages.length}`;
      writeUrlState({ action: 'chat:copy', copied: state.visibleChatMessages.length }, { replace: true });
    }

    function chatRenderSignature(visible) {
      return compactJson({
        selected: [...state.selectedChatMessageIds].sort(),
        targets: state.selectedTargets,
        messages: (visible || []).map((message) => [
          message.id,
          message.role,
          message.created_at,
          message.content,
          messageAttachments(message).map((att) => [att.kind, att.path, att.previewUrl, att.uri, att.meta || null]),
          message.detail || null,
        ]),
      });
    }

    function renderChatHistory() {
      const seenQr = new Set();
      const resultEl = $('chatResult');
      const stickToBottom = resultEl.scrollTop + resultEl.clientHeight >= resultEl.scrollHeight - 32;
      const visible = [...state.chatMessages].reverse().filter((message) => {
        const uri = message.detail && message.detail.uri;
        if (uri && uri.startsWith('dashboard://host/qr/')) {
          if (seenQr.has(uri)) return false;
          seenQr.add(uri);
        }
        return true;
      }).reverse().filter(messageMatchesTargets).filter((message) => !isGroupedScannerEventMessage(message));
      state.visibleChatMessages = visible;
      state.visibleChatMessageIds = visible.map((message) => message.id).filter(Boolean);
      const renderKey = chatRenderSignature(visible);
      if (renderKey === state.chatRenderKey) {
        updateChatSelectionControls();
        return;
      }
      state.chatRenderKey = renderKey;
      resultEl.innerHTML = visible.map(renderChatMessage).join('') || empty('No chat messages yet');
      if (stickToBottom) resultEl.scrollTop = resultEl.scrollHeight;
      updateChatSelectionControls();
    }

    async function loadChatHistory() {
      const history = await api('/api/chat/history?limit=80');
      state.chatMessages = history.messages || [];
      renderChatHistory();
    }

    async function deleteChatMessages(ids) {
      const clean = [...new Set((ids || []).filter(Boolean))];
      if (!clean.length) return;
      const result = await api('/api/chat/messages/delete', {
        method: 'POST',
        body: JSON.stringify({ ids: clean }),
      });
      state.chatMessages = state.chatMessages.filter((message) => !clean.includes(message.id));
      clean.forEach((id) => state.selectedChatMessageIds.delete(id));
      renderChatHistory();
      $('chatStatus').textContent = `deleted ${result.deleted || 0}`;
      writeUrlState({ action: 'chat:delete', deleted: result.deleted || 0 }, { replace: true });
    }

	    async function submitServiceForm(form) {
	      const uri = form.dataset.actionUri || '';
	      if (!uri) return;
	      const payload = {};
      form.querySelectorAll('input, textarea, select').forEach((field) => {
        if (!field.name) return;
        if (field.type === 'checkbox') payload[field.name] = field.checked;
        else payload[field.name] = field.value;
      });
      $('chatStatus').textContent = 'running service URI...';
      await api('/api/uri/invoke', {
        method: 'POST',
        body: JSON.stringify({
          uri,
          payload,
          targets: state.selectedTargets,
          source: 'service-view',
        }),
      });
      await loadChatHistory();
      await loadServiceViews();
      $('chatStatus').textContent = 'ok';
	      writeUrlState({ action: 'service-form:submit', uri }, { replace: true });
	    }

	    async function contactAction(button) {
	      const action = button.dataset.contactAction || '';
	      if (action === 'open-url') {
	        const url = button.dataset.url || '';
	        if (url) window.open(url, '_blank', 'noopener');
	        writeUrlState({ action: 'contact:open', target: button.dataset.target || '' }, { replace: true });
	        return;
	      }
	      if (action !== 'invoke-uri') return;
	      const uri = button.dataset.uri || '';
	      if (!uri) return;
	      const target = button.dataset.target || 'host';
	      const previous = button.textContent;
	      button.disabled = true;
	      button.textContent = 'Starting...';
	      $('chatStatus').textContent = 'starting service...';
	      try {
	        await api('/api/uri/invoke', {
	          method: 'POST',
	          body: JSON.stringify({
	            uri,
	            mode: 'execute',
	            payload: {},
	            targets: [target],
	            source: 'contact-card',
	          }),
	        });
	        state.selectedTargets = [...new Set([...state.selectedTargets, target])];
	        await loadServiceViews();
	        await load();
	        $('chatStatus').textContent = 'service running';
	        writeUrlState({ action: 'contact:start', targets: state.selectedTargets.join(',') }, { replace: true });
	      } catch (error) {
	        button.disabled = false;
	        button.textContent = previous;
	        $('chatStatus').textContent = error.message;
	        throw error;
	      }
	    }

	    function applyView(view) {
	      if (!VALID_VIEWS.has(view)) view = 'overview';
	      state.view = view;
      document.body.dataset.view = view;
      document.querySelectorAll('.view-block').forEach((block) => {
        block.classList.toggle('hidden', view !== 'overview' && block.dataset.section !== view);
      });
      renderUrlState();
    }

    async function load() {
      const sprint = $('sprintFilter').value;
      const queue = $('queueFilter').value;
      const [summary, tasks, artifacts] = await Promise.all([
        api('/api/summary'),
        api(`/api/tasks?sprint=${encodeURIComponent(sprint)}&queue=${encodeURIComponent(queue)}`),
        api('/api/artifacts?limit=80'),
      ]);
      state.summary = summary;
      state.tasks = tasks.tickets || [];
      state.artifacts = artifacts.artifacts || summary.artifacts || [];
      $('contextLine').textContent = `${summary.project} · ${summary.db}`;
      renderMetrics(summary);
      renderTasks(state.tasks);
      renderNodes(summary.nodes || []);
      renderChatContacts(summary);
      renderDiscovery(summary);
      renderServiceViews();
      renderRoutes(summary.routes || []);
      renderChecks(summary.checks || []);
      renderLogs(summary.logs || []);
      renderArtifacts(state.artifacts);
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
      state.selectedTargets = selectedTargets();
      const nodes = selectedNodeNames();
      const execute = $('chatExecute').checked;
      state.view = 'chat';
      writeUrlState({ action: 'chat:run', prompt_len: prompt.length, nodes: nodes.join(','), targets: state.selectedTargets.join(',') });
      $('chatMode').textContent = execute ? 'execute' : 'dry-run';
      $('chatStatus').textContent = 'running...';
      $('chatAskBtn').disabled = true;
      try {
        const result = await api('/api/chat/ask', {
          method: 'POST',
          body: JSON.stringify({
            prompt,
            nodes,
            targets: state.selectedTargets,
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
	      const contactButton = event.target && event.target.closest ? event.target.closest('[data-contact-action]') : null;
	      if (contactButton) {
	        event.preventDefault();
	        event.stopPropagation();
	        contactAction(contactButton).catch((error) => alert(error.message));
	        return;
	      }
	      const deleteId = event.target.dataset.chatDelete;
	      if (deleteId) {
	        deleteChatMessages([deleteId]).catch((error) => alert(error.message));
        return;
      }
      const artifactDeleteId = event.target.dataset.artifactDelete;
      if (artifactDeleteId) {
        deleteArtifacts([artifactDeleteId]).catch((error) => alert(error.message));
        return;
      }
      const action = event.target.dataset.action;
      const id = event.target.dataset.id;
      const view = event.target.dataset.view;
      if (action && id) taskAction(id, action).catch((error) => alert(error.message));
      if (view) {
        applyView(view);
        writeUrlState({ action: `tab:${view}` });
      }
    });
    document.addEventListener('change', (event) => {
      if (event.target && event.target.name === 'chatTarget') {
        state.selectedTargets = selectedTargets();
        if (!state.selectedTargets.length) state.selectedTargets = ['host'];
        updateTargetSummary();
        renderChatHistory();
        renderServiceViews();
        writeUrlState({ action: 'contacts:select', targets: state.selectedTargets.join(',') }, { replace: true });
      }
      if (event.target && event.target.name === 'chatMessageSelect') {
        const id = event.target.value;
        if (event.target.checked) state.selectedChatMessageIds.add(id);
        else state.selectedChatMessageIds.delete(id);
        updateChatSelectionControls();
      }
      if (event.target && event.target.name === 'artifactSelect') {
        const id = event.target.value;
        if (event.target.checked) state.selectedArtifactIds.add(id);
        else state.selectedArtifactIds.delete(id);
        updateArtifactSelectionControls();
      }
    });
    document.addEventListener('submit', (event) => {
      const form = event.target && event.target.closest ? event.target.closest('[data-service-form]') : null;
      if (!form) return;
      event.preventDefault();
      submitServiceForm(form).catch((error) => {
        $('chatStatus').textContent = error.message;
        alert(error.message);
      });
    });
    $('refreshBtn').addEventListener('click', () => {
      writeUrlState({ action: 'refresh' });
      load().catch((error) => alert(error.message));
    });
    $('scannerBtn').addEventListener('click', () => {
      writeUrlState({ action: 'open:scanner' });
      window.open('/scanner', '_blank');
    });
    $('artifactRefreshBtn').addEventListener('click', () => {
      writeUrlState({ action: 'artifacts:refresh' }, { replace: true });
      loadArtifacts().catch((error) => alert(error.message));
    });
    $('artifactSelectVisibleBtn').addEventListener('click', () => {
      visibleArtifactIds().forEach((id) => state.selectedArtifactIds.add(id));
      renderArtifacts(state.artifacts);
      writeUrlState({ action: 'artifacts:select-visible' }, { replace: true });
    });
    $('artifactClearSelectionBtn').addEventListener('click', () => {
      visibleArtifactIds().forEach((id) => state.selectedArtifactIds.delete(id));
      renderArtifacts(state.artifacts);
      writeUrlState({ action: 'artifacts:clear-selection' }, { replace: true });
    });
    $('artifactDeleteSelectedBtn').addEventListener('click', () => {
      deleteArtifacts(selectedVisibleArtifactIds()).catch((error) => alert(error.message));
    });
    $('artifactDeleteVisibleBtn').addEventListener('click', () => {
      deleteArtifacts(visibleArtifactIds()).catch((error) => alert(error.message));
    });
    $('artifactDedupeRowsBtn').addEventListener('click', () => {
      dedupeArtifactRows().catch((error) => alert(error.message));
    });
    $('artifactCleanupOrphansBtn').addEventListener('click', () => {
      cleanupArtifactOrphans().catch((error) => alert(error.message));
    });
    $('documentReconcileBtn').addEventListener('click', () => {
      reconcileDocumentsIndex().catch((error) => alert(error.message));
    });
    $('artifactCopyJsonBtn').addEventListener('click', () => {
      copyArtifactsJson().catch((error) => alert(error.message));
    });
    $('widgetRefreshBtn').addEventListener('click', () => {
      writeUrlState({ action: 'widgets:refresh' }, { replace: true });
      loadServiceViews().catch((error) => alert(error.message));
    });
    $('chatFullscreenBtn').addEventListener('click', () => setChatFullscreen(!state.chatFullscreen));
    $('chatScrollBottomBtn').addEventListener('click', () => {
      $('chatResult').scrollTop = $('chatResult').scrollHeight;
      writeUrlState({ action: 'chat:latest' }, { replace: true });
    });
    $('chatCopyVisibleBtn').addEventListener('click', () => {
      copyVisibleChat().catch((error) => alert(error.message));
    });
    $('chatSelectVisibleBtn').addEventListener('click', () => {
      state.visibleChatMessageIds.forEach((id) => state.selectedChatMessageIds.add(id));
      renderChatHistory();
      writeUrlState({ action: 'chat:select-visible' }, { replace: true });
    });
    $('chatClearSelectionBtn').addEventListener('click', () => {
      state.visibleChatMessageIds.forEach((id) => state.selectedChatMessageIds.delete(id));
      renderChatHistory();
      writeUrlState({ action: 'chat:clear-selection' }, { replace: true });
    });
    $('chatDeleteSelectedBtn').addEventListener('click', () => {
      deleteChatMessages(selectedVisibleChatMessageIds()).catch((error) => alert(error.message));
    });
    $('chatDeleteVisibleBtn').addEventListener('click', () => {
      deleteChatMessages(state.visibleChatMessageIds).catch((error) => alert(error.message));
    });
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
    setInterval(() => loadServiceViews().catch(() => {}), 1000);
    setInterval(() => loadArtifacts().catch(() => {}), 4000);
    loadServiceViews().catch(() => {});
    loadWidgetBundleViaUri().catch(() => {});
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
    .field { display:grid; gap:4px; color:var(--muted); font-size:13px; }
    .inline-check { min-height:44px; display:flex; gap:8px; align-items:center; color:var(--muted); }
    .inline-check input { min-height:auto; }
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
        <option value="6">6 frames</option>
        <option value="4">4 frames</option>
        <option value="8">8 frames</option>
      </select>
      <select id="quality">
        <option value="0.92">JPEG 92%</option>
        <option value="0.82">JPEG 82%</option>
        <option value="0.70">JPEG 70%</option>
      </select>
      <label class="field">Scan interval (s)<input type="number" id="scanInterval" min="1" max="60" step="0.5" inputmode="decimal"></label>
      <label class="inline-check"><input type="checkbox" id="startBest" checked> best after start</label>
      <label class="inline-check"><input type="checkbox" id="auto"> <span id="autoIntervalLabel">auto every 3s</span></label>
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
    const bestCount = document.getElementById('bestCount');
    const quality = document.getElementById('quality');
    const scanInterval = document.getElementById('scanInterval');
    const autoIntervalLabel = document.getElementById('autoIntervalLabel');
    const startBest = document.getElementById('startBest');
    const auto = document.getElementById('auto');
    let stream = null;
    let timer = null;
    let bestRunning = false;
    let torchOn = false;
    let startCameraPromise = null;
    let startCameraClickPromise = null;
    let torchClickPromise = null;
    const scannerParams = new URLSearchParams(location.search);
    const DEFAULT_SCANNER_PARAMS = {
      autostart: '1',
      auto: '1',
      best: '1',
      count: '6',
      minScore: '45',
    };

    function applyDefaultScannerParams() {
      let changed = false;
      Object.entries(DEFAULT_SCANNER_PARAMS).forEach(([name, value]) => {
        if (!scannerParams.has(name)) {
          scannerParams.set(name, value);
          changed = true;
        }
      });
      if (!scannerParams.has('interval') && !scannerParams.has('scanInterval') && !scannerParams.has('intervalMs')) {
        scannerParams.set('interval', '3');
        changed = true;
      }
      if (!changed) return;
      const query = scannerParams.toString();
      history.replaceState(null, '', `${location.pathname}${query ? `?${query}` : ''}${location.hash || ''}`);
    }

    applyDefaultScannerParams();

    function truthyParam(name, fallback=false) {
      if (!scannerParams.has(name)) return fallback;
      const value = String(scannerParams.get(name) || '').toLowerCase();
      return !['0', 'false', 'no', 'off'].includes(value);
    }

    function numericParam(name, fallback) {
      const raw = Number(scannerParams.get(name));
      return Number.isFinite(raw) && raw > 0 ? raw : fallback;
    }

    function scanIntervalMs(options={}) {
      if (Object.prototype.hasOwnProperty.call(options || {}, 'interval')) {
        const seconds = Number(options.interval);
        if (Number.isFinite(seconds) && seconds > 0) return seconds * 1000;
      }
      if (Object.prototype.hasOwnProperty.call(options || {}, 'intervalSeconds')) {
        const seconds = Number(options.intervalSeconds);
        if (Number.isFinite(seconds) && seconds > 0) return seconds * 1000;
      }
      if (Object.prototype.hasOwnProperty.call(options || {}, 'intervalMs')) {
        const ms = Number(options.intervalMs);
        if (Number.isFinite(ms) && ms > 0) return ms;
      }
      if (scannerParams.has('interval')) return numericParam('interval', 3) * 1000;
      if (scannerParams.has('scanInterval')) return numericParam('scanInterval', 3) * 1000;
      return numericParam('intervalMs', 3000);
    }

    function writeScannerUrlState() {
      const query = scannerParams.toString();
      history.replaceState(null, '', `${location.pathname}${query ? `?${query}` : ''}${location.hash || ''}`);
    }

    function formatSeconds(value) {
      const rounded = Math.round(Number(value) * 10) / 10;
      return Number.isFinite(rounded) ? String(rounded).replace(/\.0$/, '') : '3';
    }

    function syncIntervalControl(options={}) {
      const seconds = formatSeconds(scanIntervalMs(options) / 1000);
      scanInterval.value = seconds;
      autoIntervalLabel.textContent = `auto every ${seconds}s`;
      return Number(seconds);
    }

    function updateIntervalFromControl() {
      const seconds = Number(scanInterval.value);
      if (!Number.isFinite(seconds) || seconds <= 0) {
        syncIntervalControl();
        return;
      }
      const normalized = formatSeconds(seconds);
      scannerParams.set('interval', normalized);
      scannerParams.delete('scanInterval');
      scannerParams.delete('intervalMs');
      writeScannerUrlState();
      syncIntervalControl();
      if (auto.checked) startAutoLoop();
      announce('interval-changed', {interval: Number(normalized)}).catch(() => {});
    }

    function setState(text, error=false) {
      state.textContent = text;
      state.className = error ? 'status error' : 'status';
    }

    // Audible/tactile confirmation that scan + OCR + identification finished.
    // 'ok' = new document saved, 'duplicate' = recognised as already archived,
    // 'superseded' = replaced a worse earlier scan, 'error' = processing failed.
    let feedbackAudioCtx = null;
    function feedbackEnabled() {
      return truthyParam('beep', true);
    }

    function unlockFeedbackAudio() {
      if (!feedbackEnabled()) return Promise.resolve(null);
      try {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) return Promise.resolve(null);
        feedbackAudioCtx = feedbackAudioCtx || new Ctx();
        const resume = feedbackAudioCtx.state === 'suspended'
          ? feedbackAudioCtx.resume().catch(() => null)
          : Promise.resolve(feedbackAudioCtx);
        return resume.then(() => feedbackAudioCtx);
      } catch (_e) {
        return Promise.resolve(null);
      }
    }

    function feedbackTone(kind) {
      if (!feedbackEnabled()) return;
      try {
        if (navigator.vibrate) {
          navigator.vibrate(kind === 'error' ? [120, 60, 120] : kind === 'duplicate' ? [40, 40, 40] : 30);
        }
      } catch (_e) {}
      unlockFeedbackAudio().then((ctx) => {
        if (!ctx) return;
        // Each tone: [frequencyHz, startOffsetSec, durationSec].
        const tones = kind === 'error'
          ? [[220, 0, 0.32]]
          : kind === 'duplicate'
            ? [[620, 0, 0.09], [620, 0.13, 0.09]]
            : kind === 'superseded'
              ? [[660, 0, 0.09], [990, 0.11, 0.16]]
              : [[880, 0, 0.12], [1320, 0.12, 0.16]];
        const now = ctx.currentTime;
        for (const [freq, at, dur] of tones) {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = 'sine';
          osc.frequency.value = freq;
          gain.gain.setValueAtTime(0.0001, now + at);
          gain.gain.exponentialRampToValueAtTime(0.25, now + at + 0.02);
          gain.gain.exponentialRampToValueAtTime(0.0001, now + at + dur);
          osc.connect(gain).connect(ctx.destination);
          osc.start(now + at);
          osc.stop(now + at + dur + 0.02);
        }
      }).catch(() => {});
    }

    function captureFeedbackKind(data) {
      const doc = (data && data.document) || {};
      if (doc.superseded || (data && data.superseded)) return 'superseded';
      if (doc.duplicate || (data && data.duplicate)) return 'duplicate';
      return 'ok';
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
      if (auto.checked) startAutoLoop();
      if (shouldStartBest) {
        setTimeout(() => bestPdf(options || {}).catch((err) => setState(err.message, true)), 350);
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
      try {
        const data = await sendFrame({archive: true, ...options});
        if (!data || data.ok === false) throw new Error((data && data.error) || 'scan failed');
        if (data.rejected) {
          const sc = data.quality && data.quality.score != null ? Number(data.quality.score).toFixed(0) : '?';
          const reasons = data.quality && Array.isArray(data.quality.reasons) ? data.quality.reasons.join(', ') : '';
          const why = data.reason || reasons || 'low quality scan';
          setState(`discarded — ${why} (score ${sc}, min ${data.minScore})`, true);
          feedbackTone('error');
          return data;
        }
        const kind = captureFeedbackKind(data);
        const label = kind === 'duplicate' ? 'already saved' : kind === 'superseded' ? 'updated' : 'saved';
        const savedArtifact = data.primaryArtifact || data.documentArtifact || data.artifact || {};
        setState(`${label} ${savedArtifact.path || data.uri}`);
        feedbackTone(kind);
        return data;
      } catch (err) {
        feedbackTone('error');
        throw err;
      }
    }

    async function bestPdf(options={}) {
      if (!stream || bestRunning) return;
      bestRunning = true;
      bestBtn.disabled = true;
      captureBtn.disabled = true;
      const total = Number(options.count || document.getElementById('bestCount').value || '6');
      const intervalMs = scanIntervalMs(options);
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
          if (frame < total) await sleep(intervalMs);
        }
        const minScore = Number(Object.prototype.hasOwnProperty.call(options || {}, 'minScore') ? options.minScore : numericParam('minScore', 45));
        const finalData = await invokeURI('scanner://host/best/command/finish', {seriesId, minScore});
        if (!finalData || finalData.ok === false) throw new Error((finalData && finalData.error) || 'best scan failed');
        const kind = captureFeedbackKind(finalData);
        const label = kind === 'duplicate' ? 'already saved' : kind === 'superseded' ? 'updated best' : 'saved best';
        setState(`${label} ${finalData.document && finalData.document.path ? finalData.document.path : finalData.uri}`);
        feedbackTone(kind);
        return finalData;
      } catch (err) {
        feedbackTone('error');
        throw err;
      } finally {
        bestRunning = false;
        bestBtn.disabled = !stream;
        captureBtn.disabled = !stream;
      }
    }

    function bestOptions(options={}) {
      return {
        count: Number(options.count || numericParam('count', Number(document.getElementById('bestCount').value || '6'))),
        minScore: Number(Object.prototype.hasOwnProperty.call(options || {}, 'minScore') ? options.minScore : numericParam('minScore', 45)),
        intervalMs: scanIntervalMs(options),
      };
    }

    function startAutoLoop(options={}) {
      clearInterval(timer);
      if (!auto.checked) return null;
      const run = () => {
        if (!stream || bestRunning) return;
        bestPdf(bestOptions(options)).catch((err) => setState(err.message, true));
      };
      timer = setInterval(run, scanIntervalMs(options));
      return timer;
    }

    async function beginAutonomousScanning(options={}) {
      auto.checked = Object.prototype.hasOwnProperty.call(options || {}, 'auto') ? !!options.auto : true;
      startBest.checked = Object.prototype.hasOwnProperty.call(options || {}, 'startBest') ? !!options.startBest : true;
      await announce('autonomous-start-requested', {auto: auto.checked, startBest: startBest.checked});
      const status = await runStartCamera({startBest: startBest.checked, ...bestOptions(options)});
      startAutoLoop(options);
      return {ok: true, uri: 'scanner://page/camera/command/autonomous', status, auto: auto.checked};
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
      window.urirun.registerAction('scanner://page/camera/command/autonomous', (payload) => beginAutonomousScanning(payload || {}), {
        label: 'Autonomous receipt/invoice scanning', layer: 'page', kind: 'command', sideEffects: ['camera-permission', 'camera-read', 'network', 'document-write']
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

    function actionTimeoutMs(action) {
      const payload = action && action.payload ? action.payload : {};
      const raw = Number(payload.timeoutMs || payload.timeout || action.timeoutMs || 0);
      if (Number.isFinite(raw) && raw >= 1000) return Math.min(raw, 120000);
      const uri = action && action.uri ? String(action.uri) : '';
      if (uri.includes('/camera/command/best-pdf') || uri.includes('/camera/command/autonomous')) return 60000;
      if (uri.includes('/camera/command/start') || uri.includes('/ui/button/start-camera/command/click')) return 20000;
      return 15000;
    }

    function withActionTimeout(promise, action) {
      const timeoutMs = actionTimeoutMs(action);
      const uri = action && action.uri ? action.uri : 'page action';
      let timeoutId = null;
      const timeout = new Promise((_, reject) => {
        timeoutId = setTimeout(() => {
          reject(new Error(`page action timed out after ${timeoutMs}ms: ${uri}; keep the scanner tab visible and accept camera permission if prompted`));
        }, timeoutMs);
      });
      return Promise.race([promise, timeout]).finally(() => {
        if (timeoutId) clearTimeout(timeoutId);
      });
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
          const result = await withActionTimeout(
            window.urirun.invoke(action.uri, action.payload || {}, {mode: action.mode || 'execute', localOnly: true}),
            action
          );
          await sendActionResult(action, result, null);
        } catch (err) {
          setState(err.message || String(err), true);
          await sendActionResult(action, null, err);
        }
      }
    }

    function applyInitialScannerOptions() {
      startBest.checked = truthyParam('best', startBest.checked);
      auto.checked = truthyParam('auto', auto.checked);
      const count = String(numericParam('count', Number(bestCount.value || '6')));
      if ([...bestCount.options].some((option) => option.value === count)) bestCount.value = count;
      const qualityValue = scannerParams.get('quality');
      if (qualityValue && [...quality.options].some((option) => option.value === qualityValue)) quality.value = qualityValue;
      syncIntervalControl();
    }

    applyInitialScannerOptions();
    announce('open', {autostart: truthyParam('autostart', false), auto: auto.checked, startBest: startBest.checked});
    registerCameraActions();
    setInterval(() => pollPageActions().catch(() => {}), 1000);
    window.addEventListener('pointerdown', unlockFeedbackAudio, {once: true, passive: true});
    window.addEventListener('touchstart', unlockFeedbackAudio, {once: true, passive: true});
    window.addEventListener('keydown', unlockFeedbackAudio, {once: true});
    startBtn.addEventListener('click', () => {
      unlockFeedbackAudio();
      beginStartCamera().catch((err) => {
        feedbackTone('error');
        setState(err.message, true);
      });
    });
    torchBtn.addEventListener('click', () => {
      const requested = Object.prototype.hasOwnProperty.call(torchBtn.dataset, 'nextTorch') ? torchBtn.dataset.nextTorch === '1' : !torchOn;
      delete torchBtn.dataset.nextTorch;
      const promise = setTorch(requested).catch((err) => setState(err.message, true));
      torchClickPromise = promise;
      promise.finally(() => {
        if (torchClickPromise === promise) torchClickPromise = null;
      });
    });
    captureBtn.addEventListener('click', () => {
      unlockFeedbackAudio();
      capture().catch((err) => setState(err.message, true));
    });
    bestBtn.addEventListener('click', () => {
      unlockFeedbackAudio();
      bestPdf().catch((err) => {
        bestRunning = false;
        bestBtn.disabled = !stream;
        captureBtn.disabled = !stream;
        setState(err.message, true);
      });
    });
    scanInterval.addEventListener('change', updateIntervalFromControl);
    scanInterval.addEventListener('blur', updateIntervalFromControl);
    auto.addEventListener('change', () => {
      if (auto.checked && !stream) {
        beginAutonomousScanning({auto: true, startBest: startBest.checked}).catch((err) => setState(err.message, true));
      } else {
        startAutoLoop();
      }
    });
    if (truthyParam('autostart', false)) {
      setTimeout(() => {
        beginAutonomousScanning({auto: auto.checked, startBest: startBest.checked}).catch((err) => {
          setState(`camera permission needed: ${err.message || err}`, true);
        });
      }, 350);
    }
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


def _service_view_from_query(project: str, query: dict[str, list[str]]) -> dict:
    target = _first(query, "target") or _first(query, "service") or "service:phone-scanner"
    view_id = _first(query, "id")
    data = service_live_views(project, limit=int(_first(query, "limit", "8") or 8))
    views = [item for item in data.get("views", []) if isinstance(item, dict)]
    if view_id:
        for view in views:
            if view.get("id") == view_id:
                return view
    for view in views:
        if view.get("target") == target or view.get("serviceId") == target:
            return view
    return {
        "id": view_id or f"{target}/live",
        "target": target,
        "serviceId": target,
        "title": target,
        "kind": "stream",
        "view": "json",
        "status": "stopped",
        "updatedAt": data.get("updatedAt") or _utc_now(),
        "data": {},
    }


def _service_widget_summary(view: dict) -> dict[str, str]:
    title = str(view.get("title") or view.get("id") or "service view")
    status = str(view.get("status") or "unknown")
    streams = ((view.get("data") or {}).get("streams") or []) if isinstance(view.get("data"), dict) else []
    if streams and isinstance(streams[0], dict):
        stream = streams[0]
        best = stream.get("best") if isinstance(stream.get("best"), dict) else {}
        doc = best.get("detectedDocument") if isinstance(best.get("detectedDocument"), dict) else {}
        parts = [doc.get("type"), doc.get("date"), doc.get("contractor") or doc.get("supplier") or doc.get("category"), doc.get("amount")]
        subtitle = " · ".join(str(part) for part in parts if part) or str(stream.get("seriesId") or "")
        detail = f"{stream.get('count') or 0} frame(s)"
        return {"title": title, "status": status, "subtitle": subtitle, "detail": detail}
    return {
        "title": title,
        "status": status,
        "subtitle": str(view.get("target") or view.get("serviceId") or ""),
        "detail": str(view.get("updatedAt") or ""),
    }


def _service_widget_html(project: str, query: dict[str, list[str]]) -> str:
    view = _service_view_from_query(project, query)
    target = str(view.get("target") or view.get("serviceId") or "service:phone-scanner")
    view_id = str(view.get("id") or "")
    refresh = int(view.get("refreshMs") or 1000)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(str(view.get("title") or "urirun service view"))}</title>
  <style>
    :root {{ color-scheme: dark; --bg:#11100f; --panel:#181716; --panel2:#201f1d; --ink:#f4f1e9; --muted:#aaa49a; --line:#3c3934; --accent:#2dd4bf; --good:#34d399; --bad:#fb7185; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; padding:12px; background:var(--bg); color:var(--ink); font:14px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    .widget {{ display:grid; gap:10px; min-height:100vh; }}
    .card {{ display:grid; gap:8px; padding:12px; border:1px solid rgba(45,212,191,.3); border-radius:8px; background:rgba(45,212,191,.08); }}
    .head,.meta {{ display:flex; align-items:center; justify-content:space-between; gap:8px; flex-wrap:wrap; }}
    .pill {{ display:inline-flex; min-height:24px; align-items:center; padding:2px 8px; border-radius:999px; background:#25231f; color:var(--muted); }}
    .pill.accepted,.pill.running {{ color:var(--good); background:rgba(52,211,153,.14); }}
    .pill.failed,.pill.rejected,.pill.stopped {{ color:var(--bad); background:rgba(251,113,133,.16); }}
    .frames {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(96px,1fr)); gap:8px; }}
    .frame {{ display:grid; gap:4px; padding:6px; border:1px solid var(--line); border-radius:6px; background:var(--panel2); }}
    img {{ width:100%; aspect-ratio:4/3; object-fit:cover; border-radius:4px; background:#151412; }}
    a {{ color:var(--accent); }}
    pre {{ margin:0; padding:10px; overflow:auto; border:1px solid var(--line); border-radius:6px; background:#151412; color:var(--ink); }}
    .muted {{ color:var(--muted); }}
  </style>
</head>
<body>
  <main class="widget">
    <section class="card" id="view">loading...</section>
  </main>
  <script>
    const target = {json.dumps(target)};
    const viewId = {json.dumps(view_id)};
    const refreshMs = Math.max(500, Number({json.dumps(refresh)}) || 1000);
    const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
    const basename = (path) => String(path || '').split('/').filter(Boolean).pop() || String(path || '');
    const docLabel = (candidate) => {{
      const doc = candidate && candidate.detectedDocument ? candidate.detectedDocument : {{}};
      return [doc.type, doc.date, doc.contractor || doc.supplier || doc.category, doc.amount].filter(Boolean).join(' · ') || 'document candidate';
    }};
    function pickView(data) {{
      const views = data.views || [];
      return views.find((view) => view.id === viewId) || views.find((view) => view.target === target || view.serviceId === target) || null;
    }}
    function renderScanner(view) {{
      const streams = view.data && Array.isArray(view.data.streams) ? view.data.streams : [];
      return streams.map((stream) => {{
        const best = stream.best || {{}};
        const document = stream.document || {{}};
        const status = stream.status || view.status || 'running';
        const frames = stream.candidates || [];
        const link = document.path ? `<a href="${{esc(document.previewUrl || `/api/file?path=${{encodeURIComponent(document.path)}}`)}}" download>${{esc(basename(document.path))}}</a>` : '';
        return `<section class="card">
          <div class="head"><strong>${{esc(view.title || 'service view')}}</strong><span class="pill ${{esc(status)}}">${{esc(status)}}</span></div>
          <div class="meta"><span class="muted">${{esc(stream.seriesId || view.target || '')}}</span><span class="muted">${{esc(stream.updatedAt || view.updatedAt || '')}}</span></div>
          <strong>${{esc(docLabel(best))}}</strong>
          <div class="muted">${{esc(stream.count || 0)}} frame(s)</div>
          ${{link}}
          ${{frames.length ? `<div class="frames">${{frames.map((frame) => `<div class="frame">${{frame.previewUrl ? `<img src="${{esc(frame.previewUrl)}}" alt="${{esc(docLabel(frame))}}">` : ''}}<span class="muted">${{esc(docLabel(frame))}}</span></div>`).join('')}}</div>` : ''}}
          <details><summary>URI / JSON</summary><pre>${{esc(JSON.stringify(stream, null, 2))}}</pre></details>
        </section>`;
      }}).join('') || '<section class="card">no stream</section>';
    }}
    function render(view) {{
      if (!view) return '<section class="card"><div class="head"><strong>service view</strong><span class="pill stopped">stopped</span></div><div class="muted">no live data</div></section>';
      if (view.view === 'scanner-stream') return renderScanner(view);
      return `<section class="card"><div class="head"><strong>${{esc(view.title || view.id || 'service view')}}</strong><span class="pill ${{esc(view.status || 'running')}}">${{esc(view.status || view.kind || 'live')}}</span></div><pre>${{esc(JSON.stringify(view, null, 2))}}</pre></section>`;
    }}
    async function load() {{
      const res = await fetch('/api/services/live?limit=8', {{ cache: 'no-store' }});
      const data = await res.json();
      document.getElementById('view').outerHTML = `<div id="view">${{render(pickView(data))}}</div>`;
    }}
    load().catch((error) => {{ document.getElementById('view').textContent = error.message; }});
    setInterval(() => load().catch(() => {{}}), refreshMs);
  </script>
</body>
</html>"""


def _service_widget_svg(project: str, query: dict[str, list[str]]) -> str:
    view = _service_view_from_query(project, query)
    summary = _service_widget_summary(view)
    width = max(320, min(1200, int(_first(query, "width", "720") or 720)))
    height = max(120, min(600, int(_first(query, "height", "180") or 180)))
    status = summary["status"]
    status_color = "#34d399" if status in {"accepted", "running"} else "#fb7185" if status in {"failed", "rejected", "stopped"} else "#aaa49a"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(summary['title'])}">
  <rect width="100%" height="100%" rx="8" fill="#11100f"/>
  <rect x="10" y="10" width="{width - 20}" height="{height - 20}" rx="8" fill="#13251f" stroke="#2dd4bf" stroke-opacity=".45"/>
  <text x="24" y="42" fill="#f4f1e9" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="18" font-weight="700">{html.escape(summary['title'])}</text>
  <rect x="{width - 130}" y="24" width="100" height="28" rx="14" fill="{status_color}" fill-opacity=".16"/>
  <text x="{width - 80}" y="43" text-anchor="middle" fill="{status_color}" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="13">{html.escape(status)}</text>
  <text x="24" y="78" fill="#f4f1e9" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="15">{html.escape(summary['subtitle'])}</text>
  <text x="24" y="108" fill="#aaa49a" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="13">{html.escape(summary['detail'])}</text>
  <text x="24" y="{height - 24}" fill="#aaa49a" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="11">{html.escape(str(view.get('id') or view.get('target') or ''))}</text>
</svg>"""


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


def _artifact_visual_path(artifact: dict) -> str:
    path = str(artifact.get("path") or "")
    meta = artifact.get("meta") if isinstance(artifact.get("meta"), dict) else {}
    if path.lower().endswith(".pdf"):
        return str(meta.get("displayImage") or meta.get("displayPath") or meta.get("previewImage") or meta.get("image") or "")
    return path


def _artifact_file_exists(path: str) -> bool:
    if not path:
        return False
    try:
        return Path(path).expanduser().resolve().is_file()
    except Exception:  # noqa: BLE001
        return False


def _public_artifact(artifact: dict, project: str) -> dict:
    path = str(artifact.get("path") or "")
    visual_path = _artifact_visual_path(artifact)
    file_preview = _preview_url(path, project) if path else None
    visual_preview = _preview_url(visual_path, project) if visual_path else None
    return {
        **artifact,
        "fileExists": _artifact_file_exists(path),
        "previewExists": _artifact_file_exists(visual_path),
        "visualPath": visual_path,
        "filePreviewUrl": file_preview or "",
        "previewUrl": visual_preview or "",
    }


def _public_artifacts(artifacts: list[dict], project: str) -> list[dict]:
    return [_public_artifact(artifact, project) for artifact in artifacts]


def _artifact_dedupe_key(item: dict) -> tuple[str, str]:
    path = str(item.get("path") or item.get("visualPath") or "")
    if path:
        try:
            return ("path", str(Path(path).expanduser().resolve()))
        except Exception:  # noqa: BLE001
            return ("path", str(Path(path).expanduser()))
    uri = str(item.get("uri") or item.get("id") or "")
    return ("uri", uri)


def _artifact_dedupe_rank(item: dict) -> tuple[int, int, str]:
    kind_rank = {
        "document-pdf": 0,
        "camera-scan": 1,
        "receipt-crop": 2,
        "dashboard-qr": 3,
    }
    missing_rank = 0 if item.get("fileExists") or item.get("previewExists") else 10
    return (missing_rank, kind_rank.get(str(item.get("kind") or ""), 5), str(item.get("created_at") or ""))


def _dedupe_public_artifacts(public: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = {}
    order: list[tuple[str, str]] = []
    for item in public:
        key = _artifact_dedupe_key(item)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)

    out: list[dict] = []
    for key in order:
        group = groups[key]
        if len(group) == 1:
            out.append(group[0])
            continue
        keep = sorted(group, key=_artifact_dedupe_rank)[0].copy()
        keep_id = str(keep.get("id") or "")
        duplicate_ids = [str(item.get("id")) for item in group if item.get("id") and str(item.get("id")) != keep_id]
        keep["duplicateCount"] = len(group)
        keep["duplicateIds"] = duplicate_ids
        keep["duplicateArtifactIds"] = [str(item.get("id")) for item in group if item.get("id")]
        keep["duplicateUris"] = [
            str(item.get("uri"))
            for item in group
            if item.get("uri") and str(item.get("uri")) != str(keep.get("uri") or "")
        ]
        out.append(keep)
    return out


def _visible_public_artifacts(
    artifacts: list[dict],
    project: str,
    *,
    include_missing: bool = False,
    include_duplicates: bool = False,
) -> list[dict]:
    public = _public_artifacts(artifacts, project)
    if not include_missing:
        public = [item for item in public if item.get("fileExists") or item.get("previewExists")]
    if include_duplicates:
        return public
    return _dedupe_public_artifacts(public)


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


def chat_delete_messages(db: str | None, payload: dict) -> dict:
    raw_ids = payload.get("ids")
    if raw_ids is None and payload.get("id"):
        raw_ids = [payload.get("id")]
    if not isinstance(raw_ids, list):
        raise ValueError("ids must be a list")
    ids = [str(item).strip() for item in raw_ids if str(item).strip()]
    deleted = _host_db().delete_logs(db, ids, stream="chat", event="message")
    return {"ok": True, "deleted": deleted, "ids": ids}


def _truthy_env(name: str, default: str = "0") -> bool:
    return str(os.environ.get(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def _local_image_ocr_tesseract(path: str) -> dict:
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


def _local_image_ocr(path: str, backend: str | None = None) -> dict:
    """OCR a scanned image for the phone-scanner pipeline.

    Prefers the urirun-connector-ocr ``auto`` cascade, whose first backend is PaddleOCR
    (PP-OCRv5/v6 det+rec with document orientation + dewarping). PaddleOCR reads Polish
    receipts on the *full frame* far more reliably than plain tesseract and does not lose
    the header/footer to an aggressive crop. Falls back to direct tesseract, then — when both
    paddle and tesseract come back empty — to a vision-LLM read (`_local_image_ocr_llm`), so a
    scan never yields empty text. Set ``URIRUN_SCANNER_OCR_BACKEND=tesseract`` to force the old
    path; ``URIRUN_SCANNER_OCR_LLM_FALLBACK=0`` to disable the LLM last resort.

    ``backend`` overrides the env default for one call. The live "best frame" loop scores
    transient candidates with the cheap ``tesseract`` backend and only pays for the full
    paddle read on the document it actually keeps (manual Scan, or the chosen best frame),
    so a 30s/frame OCR never piles up behind the ~3s capture interval.
    """
    backend = str(backend if backend is not None else os.environ.get("URIRUN_SCANNER_OCR_BACKEND", "auto")).strip().lower()
    if backend in {"", "tesseract"}:
        return _local_image_ocr_tesseract(path)
    try:
        from urirun_connector_ocr.core import image_text  # type: ignore
    except Exception as exc:  # noqa: BLE001
        result = _local_image_ocr_tesseract(path)
        result.setdefault("connectorError", f"urirun-connector-ocr unavailable: {exc}")
        return result
    try:
        envelope = image_text(image=path, backend=backend, lang="eng+pol", max_chars=20000)
    except Exception as exc:  # noqa: BLE001
        result = _local_image_ocr_tesseract(path)
        result.setdefault("connectorError", str(exc))
        return result
    if envelope.get("ok") and str(envelope.get("text") or "").strip():
        return {
            "ok": True,
            "backend": envelope.get("backend", backend),
            "text": str(envelope.get("text") or ""),
            "chars": envelope.get("chars") or len(str(envelope.get("text") or "")),
            "boxCount": envelope.get("box_count"),
            "docPreprocess": envelope.get("docPreprocess"),
        }
    # Connector found nothing usable; fall back to tesseract so a scan never silently fails.
    fallback = _local_image_ocr_tesseract(path)
    if fallback.get("ok") and str(fallback.get("text") or "").strip():
        return fallback
    # Last resort: read the image with a vision LLM. Covers the case where paddle is broken
    # AND tesseract is missing/blank — the scan still yields text instead of empty metadata.
    llm = _local_image_ocr_llm(path)
    if llm and llm.get("ok") and str(llm.get("text") or "").strip():
        return llm
    if not fallback.get("ok"):
        fallback.setdefault("connectorError", str(envelope.get("error") or "connector OCR returned no text"))
    return fallback


def _local_image_ocr_llm(path: str) -> dict | None:
    """OCR an image with a vision LLM — the final fallback when paddle and tesseract fail.

    Returns ``None`` when disabled (``URIRUN_SCANNER_OCR_LLM_FALLBACK=0``) or no vision
    model/key is configured, so it is always a safe last resort. Uses the same model
    resolution as the metadata extractor (``URIRUN_SCANNER_LLM_VISION_MODEL`` /
    ``URIRUN_SCANNER_LLM_MODEL`` / ``LLM_MODEL``).
    """
    if not _truthy_env("URIRUN_SCANNER_OCR_LLM_FALLBACK", "1"):
        return None
    if not (path and Path(str(path)).is_file()):
        return None
    model = _llm_model(vision=True)
    if not model:
        return None
    key_ref = _llm_api_key_ref()
    if model.startswith("openrouter/") and not key_ref:
        return None
    try:
        from urirun_connector_llm.core import complete  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    prompt = (
        "Przepisz CAŁY tekst z tego paragonu/faktury dokładnie tak jak widać, linia po linii. "
        "Zwróć wyłącznie tekst, bez komentarzy."
    )
    try:
        # The key is passed by reference and resolved inside the connector under a
        # deny-by-default allow-list — never copied into this process's environment.
        res = complete(prompt, model=model, image=str(path), api_key=key_ref, secret_allow=key_ref)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(res, dict) or not res.get("ok"):
        return None
    text = str(res.get("response") or "").strip()
    if not text:
        return None
    return {"ok": True, "backend": "llm-vision", "text": text, "chars": len(text), "model": model}


def _document_archive_root() -> Path:
    return Path(os.environ.get("URIRUN_DOCUMENT_DIR", "~/.urirun/documents")).expanduser().resolve()


def _document_index_path() -> Path:
    configured = os.environ.get("URIRUN_DOCUMENT_INDEX")
    return Path(configured).expanduser().resolve() if configured else _document_archive_root() / "index.json"


def _document_sync_default_dest_root() -> str:
    return os.environ.get("URIRUN_DOCUMENT_SYNC_DEST", "~/Downloads/urirun-scans")


def _document_sync_default_node() -> str:
    return os.environ.get("URIRUN_DOCUMENT_SYNC_NODE", "laptop")


def _scanned_id_log_path() -> Path:
    configured = os.environ.get("URIRUN_SCANNED_ID_LOG")
    return Path(configured).expanduser().resolve() if configured else _document_archive_root() / "scanned.id.jsonl"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).expanduser().resolve().open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _node_url_from_config(config: str | None, node_urls: list[str] | None, node: str) -> str | None:
    try:
        return str(_mesh().node_url(_host_config(config, node_urls), node)).rstrip("/")
    except (Exception, SystemExit):  # mesh.node_url exits for unknown nodes.
        return None


def _node_client(url: str, *, token: str | None = None, identity: str | None = None):
    from urirun.node.client import NodeClient

    return NodeClient(url, token=token, identity=identity)


def _run_node_uri(
    node_url: str,
    uri: str,
    payload: dict,
    *,
    token: str | None = None,
    identity: str | None = None,
    timeout: float = 120.0,
) -> dict:
    client = _node_client(node_url, token=token, identity=identity)
    envelope = client.run(uri, payload, timeout=timeout)
    value = client.value(envelope)
    value_ok = not isinstance(value, dict) or value.get("ok", True)
    return {
        "ok": bool(envelope.get("ok") and value_ok),
        "envelope": envelope,
        "value": value,
    }


def _document_archive_pdfs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        path for path in root.glob("*/*.pdf")
        if path.is_file() and path.parent.name != "no_invoice"
    )


def sync_documents_to_node(
    project: str,
    db: str | None,
    config: str | None,
    payload: dict,
    *,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
) -> dict:
    source_root = Path(payload.get("source_root") or payload.get("sourceRoot") or _document_archive_root()).expanduser().resolve()
    node = str(payload.get("node") or payload.get("targetNode") or _document_sync_default_node()).strip() or "laptop"
    node_url = str(payload.get("node_url") or payload.get("nodeUrl") or "").strip()
    if not node_url:
        node_url = _node_url_from_config(config, node_urls, node) or ""
    if not node_url:
        raise ValueError("node_url is required when the target node is not present in host config")
    node_url = node_url.rstrip("/")
    dest_root = str(payload.get("dest_root") or payload.get("destRoot") or _document_sync_default_dest_root()).rstrip("/")
    overwrite = bool(payload.get("overwrite", True))
    make_dirs = bool(payload.get("make_dirs", payload.get("makeDirs", True)))
    timeout = float(payload.get("timeout", 120.0) or 120.0)
    fs_target = str(payload.get("fs_target") or payload.get("fsTarget") or node).strip() or node
    fs_uri = f"fs://{fs_target}/file/command/write-b64"

    files = _document_archive_pdfs(source_root)
    results: list[dict] = []
    copied = 0
    failed = 0
    skipped = 0

    for source in files:
        rel = source.relative_to(source_root)
        dest_path = f"{dest_root}/{rel.as_posix()}"
        data = source.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        item = {
            "source": str(source),
            "relativePath": rel.as_posix(),
            "dest": dest_path,
            "bytes": len(data),
            "sha256": sha256,
        }
        try:
            run = _run_node_uri(
                node_url,
                fs_uri,
                {
                    "path": dest_path,
                    "bytes_b64": base64.b64encode(data).decode("ascii"),
                    "overwrite": overwrite,
                    "make_dirs": make_dirs,
                },
                token=token,
                identity=identity,
                timeout=timeout,
            )
            value = run.get("value") if isinstance(run.get("value"), dict) else {}
            remote_sha = value.get("sha256")
            ok = bool(run.get("ok") and value.get("ok", True) and remote_sha == sha256)
            item.update({
                "ok": ok,
                "remotePath": value.get("path"),
                "remoteSha256": remote_sha,
                "overwritten": value.get("overwritten"),
                "renamed": value.get("renamed"),
            })
            if ok:
                copied += 1
            else:
                failed += 1
                item["error"] = value.get("error") or "remote write failed or sha256 mismatch"
        except Exception as exc:  # noqa: BLE001 - report per-file transfer failures.
            failed += 1
            item.update({"ok": False, "error": str(exc)})
        results.append(item)

    report = {
        "ok": failed == 0,
        "uri": "document://host/archive/command/sync-to-node",
        "sourceRoot": str(source_root),
        "node": node,
        "nodeUrl": node_url,
        "fsUri": fs_uri,
        "destRoot": dest_root,
        "total": len(files),
        "copied": copied,
        "failed": failed,
        "skipped": skipped,
        "results": results,
        "updatedAt": _utc_now(),
    }
    try:
        _host_db().add_log(db, "document-sync", "sync-to-node", report)
    except Exception:
        pass

    status = "completed" if report["ok"] else "finished with errors"
    content = f"Document sync to {node} {status}: {copied}/{len(files)} PDFs -> {dest_root}"
    message = _chat_message(
        "system",
        content,
        detail={
            **report,
            "selectedTargets": ["host", f"node:{node}"],
        },
    )
    _add_chat_message(db, message)
    report["message"] = message
    return report


def _normalized_document_text(text: str) -> str:
    if _dedup_normalize_text is not None:
        return _dedup_normalize_text(text)
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


def _document_files_exist(item: dict) -> bool:
    """True if the document still has at least one on-disk artifact (PDF or JSON sidecar)."""
    for key in ("pdfPath", "path", "jsonPath"):
        value = item.get(key)
        if value and Path(str(value)).expanduser().is_file():
            return True
    return False


def _prune_orphaned_documents(index: dict) -> list[dict]:
    """Drop index entries whose PDF and JSON sidecar are both gone from disk.

    Returns the removed entries. Non-destructive to real files -- the artifacts are
    already missing; this only repairs the index so it stops listing dead documents.
    Any entry that still has at least one on-disk file is kept.
    """
    docs = index.get("documents")
    if not isinstance(docs, list):
        return []
    kept: list[dict] = []
    pruned: list[dict] = []
    for item in docs:
        if isinstance(item, dict) and not _document_files_exist(item):
            pruned.append(item)
        else:
            kept.append(item)
    if pruned:
        index["documents"] = kept
    return pruned


def reconcile_document_index() -> dict:
    """Reconcile the document index with the filesystem by pruning orphaned entries.

    Safe and non-destructive: only index entries whose PDF *and* JSON sidecar are both
    missing are removed; existing files are never touched. Returns a summary report.
    """
    with _DOCUMENT_INDEX_LOCK:
        index = _load_document_index()
        before = len(index.get("documents", []))
        pruned = _prune_orphaned_documents(index)
        if pruned:
            _save_document_index(index)
    return {
        "ok": True,
        "indexPath": str(_document_index_path()),
        "before": before,
        "after": before - len(pruned),
        "prunedCount": len(pruned),
        "pruned": [
            {"docId": p.get("docId"), "pdfPath": p.get("pdfPath"), "jsonPath": p.get("jsonPath")}
            for p in pruned
        ],
    }


def _iter_scanned_id_log() -> list[dict]:
    path = _scanned_id_log_path()
    if not path.is_file():
        return []
    out: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                out.append(item)
    except Exception:  # noqa: BLE001
        return out
    return out


def _append_scanned_id_log(entry: dict) -> None:
    path = _scanned_id_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _existing_scanned_id(*, doc_id: str, source_sha256: str, text_sha256: str) -> dict | None:
    duplicate: dict | None = None
    for item in _iter_scanned_id_log():
        same_doc = bool(doc_id and item.get("docId") == doc_id)
        same_source = bool(source_sha256 and item.get("sourceSha256") == source_sha256)
        same_text = bool(text_sha256 and item.get("textSha256") == text_sha256)
        if same_doc or same_source or same_text:
            duplicate = item
    return duplicate


def _backfill_scanned_id_log(index: dict) -> None:
    docs = [item for item in index.get("documents", []) if isinstance(item, dict)]
    if not docs:
        return
    existing = _iter_scanned_id_log()
    seen_doc_ids = {str(item.get("docId") or "") for item in existing if item.get("docId")}
    seen_sources = {str(item.get("sourceSha256") or "") for item in existing if item.get("sourceSha256")}
    seen_texts = {str(item.get("textSha256") or "") for item in existing if item.get("textSha256")}
    for item in docs:
        doc_id = str(item.get("docId") or "").strip()
        source_sha256 = str(item.get("sourceSha256") or "").strip()
        text_sha256 = str(item.get("textSha256") or "").strip()
        if (doc_id and doc_id in seen_doc_ids) or (source_sha256 and source_sha256 in seen_sources) or (text_sha256 and text_sha256 in seen_texts):
            continue
        pdf_path = str(item.get("pdfPath") or item.get("path") or "")
        entry = {
            "version": 1,
            "event": "indexed",
            "scannedAt": item.get("createdAt") or _utc_now(),
            "docId": doc_id,
            "docIdProvider": item.get("docIdProvider"),
            "docIdSource": item.get("docIdSource"),
            "duplicate": False,
            "uri": item.get("uri"),
            "pdfPath": pdf_path,
            "jsonPath": item.get("jsonPath"),
            "fileName": Path(pdf_path).name if pdf_path else "",
            "originalPath": item.get("originalPath"),
            "cropPath": item.get("cropPath"),
            "sourceSha256": source_sha256,
            "textSha256": text_sha256,
            "ocrBackend": item.get("ocrBackend"),
            "ocrChars": item.get("ocrChars"),
            "metadata": {
                "type": item.get("type"),
                "date": item.get("date"),
                "contractor": item.get("contractor"),
                "amount": item.get("amount"),
                "currency": item.get("currency"),
            },
        }
        _append_scanned_id_log(entry)
        if doc_id:
            seen_doc_ids.add(doc_id)
        if source_sha256:
            seen_sources.add(source_sha256)
        if text_sha256:
            seen_texts.add(text_sha256)


def _docid_for_file(path: str | Path, ocr_text: str) -> dict:
    if _dedup_document_id is not None:
        return _dedup_document_id(path, ocr_text, normalized_text=_normalized_document_text(ocr_text))

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
    # Guard ends with "not a digit" rather than \b: receipt OCR often glues the date to the
    # preceding word (e.g. "Betkowska06-03-2025"), where there is no word boundary between a
    # letter and a digit. (?<!\d)/(?!\d) still prevents slicing a date out of a longer number.
    for year, month, day in re.findall(r"(?<!\d)(20\d{2})[-./](\d{1,2})[-./](\d{1,2})(?!\d)", text):
        try:
            candidates.append(date(int(year), int(month), int(day)))
        except ValueError:
            pass
    for day, month, year in re.findall(r"(?<!\d)(\d{1,2})[-./](\d{1,2})[-./](20\d{2})(?!\d)", text):
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
        r"^(faktura|paragon|rachunek|invoice|receipt|nip|vat|data|date|razem|suma|total|do zap|sprzedawca|nabywca|lp\.?|ilosc|ilość|cena|kwota|sprzedaz|sprzedaż)\b",
        re.I,
    )
    terminal_noise = re.compile(
        r"\b(pos\s*id|mid|aid|wazna\s*do|ważna\s*do|contactless|visa|uisa|mastercard|"
        r"polskie\s+e\s*p?[łl]atnosci|e\s*p?[łl]atnosci|podpis|autoryzacji|kod\s+autoryzacji)\b",
        re.I,
    )
    candidates: list[tuple[int, str]] = []
    for idx, raw in enumerate(text.splitlines()[:30]):
        line = re.sub(r"\s+", " ", raw.strip(" \t:-")).strip()
        if len(line) < 3 or len(line) > 70 or ignored.search(line):
            continue
        if terminal_noise.search(line):
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


_LLM_DOC_TYPES = ("paragon", "faktura", "rachunek", "potwierdzenie", "dokument")


def _load_env_file(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE .env reader (ignores comments / blanks / `export `)."""
    values: dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                values[key] = val
    except OSError:
        return {}
    return values


def _llm_env_file() -> Path | None:
    """The .env that carries LLM config/credentials, if present.

    ``URIRUN_LLM_ENV_FILE``, then this repo's ``examples/.env``, then ``~/.urirun/llm.env``.
    Used both to read the (non-secret) model name and to *address* the API key by reference —
    never to copy the key into the process environment.
    """
    candidates: list[Path] = []
    explicit = os.environ.get("URIRUN_LLM_ENV_FILE")
    if explicit:
        candidates.append(Path(explicit).expanduser())
    try:
        candidates.append(Path(__file__).resolve().parents[5] / "examples" / ".env")
    except IndexError:
        pass
    candidates.append(Path("~/.urirun/llm.env").expanduser())
    for path in candidates:
        if path.is_file():
            return path
    return None


def _llm_model(*, vision: bool = False) -> str:
    """Resolve the LLM model name (config, not a secret).

    Env wins (``URIRUN_SCANNER_LLM_VISION_MODEL`` for the vision pass, then
    ``URIRUN_SCANNER_LLM_MODEL`` / ``LLM_MODEL``); otherwise ``LLM_MODEL`` is read from the
    .env file as plain config. The model name is never a credential, so reading it directly
    is fine — only the API key goes through the secret layer.
    """
    if vision and os.environ.get("URIRUN_SCANNER_LLM_VISION_MODEL"):
        return os.environ["URIRUN_SCANNER_LLM_VISION_MODEL"].strip()
    model = (os.environ.get("URIRUN_SCANNER_LLM_MODEL") or os.environ.get("LLM_MODEL") or "").strip()
    if model:
        return model
    env_file = _llm_env_file()
    if env_file:
        return str(_load_env_file(env_file).get("LLM_MODEL", "")).strip()
    return ""


def _llm_api_key_ref() -> str:
    """Return the API key as a *secret reference*, never the value.

    Honours ``URIRUN_SCANNER_LLM_API_KEY_REF`` (e.g. ``secret://keyring/openrouter#key``).
    Otherwise: if ``OPENROUTER_API_KEY`` is already in the process env, reference it with
    ``getv://OPENROUTER_API_KEY``; else point at the .env file via
    ``secret://dotenv/<file>#OPENROUTER_API_KEY``. Returns '' when nothing is configured.
    The value is resolved inside the llm connector under a deny-by-default allow-list — it is
    never copied into ``os.environ`` here.
    """
    explicit = os.environ.get("URIRUN_SCANNER_LLM_API_KEY_REF")
    if explicit:
        return explicit.strip()
    if os.environ.get("OPENROUTER_API_KEY"):
        return "getv://OPENROUTER_API_KEY"
    env_file = _llm_env_file()
    if env_file and "OPENROUTER_API_KEY" in _load_env_file(env_file):
        return f"secret://dotenv/{env_file}#OPENROUTER_API_KEY"
    return ""


def _coerce_amount(value: object) -> str:
    """Normalise an LLM-supplied amount to ``NNN.NN`` (or '' when not a number)."""
    if value is None:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    raw = raw.replace(" ", "").replace(" ", "")
    # Keep the last decimal separator, drop thousands separators.
    raw = re.sub(r"[^0-9,.\-]", "", raw)
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".") if raw.rfind(",") > raw.rfind(".") else raw.replace(",", "")
    else:
        raw = raw.replace(",", ".")
    try:
        return f"{float(raw):.2f}"
    except ValueError:
        return ""


_LLM_FIELDS_SPEC = (
    "Zwróć WYŁĄCZNIE obiekt JSON, bez komentarzy, z polami:\n"
    '{"type": jeden z ["paragon","faktura","rachunek","potwierdzenie","dokument"],\n'
    ' "date": data wystawienia/sprzedaży dokumentu w formacie YYYY-MM-DD (NIE dzisiejsza data),\n'
    ' "contractor": nazwa sprzedawcy/firmy (nie etykieta "Sprzedawca"),\n'
    ' "amount": kwota DO ZAPŁATY / SUMA / RAZEM jako liczba z kropką (np. "200.62"),\n'
    ' "currency": kod waluty ISO np. "PLN",\n'
    ' "nip": NIP sprzedawcy (same cyfry) lub "",\n'
    ' "number": numer dokumentu/faktury/paragonu lub ""}\n'
    "Gdy pola nie ma w dokumencie, użyj pustego stringa. Nie zgaduj daty — jeśli brak, zwróć \"\".\n"
)


def _llm_extract_metadata(ocr_text: str, *, captured_at: str | None = None,
                          image_path: str | None = None) -> dict | None:
    """Extract structured document fields with an LLM, from OCR text and/or the image itself.

    The regex parsers are brittle on real receipts (glued tokens, layout noise); an LLM reads
    the document in context and returns clean fields. Two modes:

    * **text** (default): the OCR text is sent to the model.
    * **vision** (``URIRUN_SCANNER_LLM_VISION=1``): the *image* is sent directly to a multimodal
      model (the OCR text, if any, rides along as a hint). This reads layout/totals the OCR may
      have mangled, and works even when OCR returned nothing.

    Returns ``None`` (caller keeps the regex result) when disabled, no model/key is configured,
    or the call/parse fails — always a safe augmentation, never a hard dependency. Pick the
    model with ``URIRUN_SCANNER_LLM_MODEL`` / ``LLM_MODEL`` (or ``URIRUN_SCANNER_LLM_VISION_MODEL``
    for the vision pass).
    """
    if not _truthy_env("URIRUN_SCANNER_LLM_EXTRACT", "1"):
        return None
    text = (ocr_text or "").strip()
    use_vision = bool(
        _truthy_env("URIRUN_SCANNER_LLM_VISION", "0")
        and image_path
        and Path(str(image_path)).is_file()
    )
    if not use_vision and len(text) < 8:
        return None
    model = _llm_model(vision=use_vision)
    if not model:
        return None
    key_ref = _llm_api_key_ref()
    if model.startswith("openrouter/") and not key_ref:
        return None
    try:
        from urirun_connector_llm.core import complete  # type: ignore
    except Exception:  # noqa: BLE001
        return None

    # The API key travels as a reference (getv:// or secret://dotenv/...) and is resolved
    # inside the llm connector under a deny-by-default allow-list — never via os.environ here.
    if use_vision:
        prompt = (
            "Przeanalizuj zdjęcie polskiego paragonu lub faktury i wyciągnij dane. "
            + _LLM_FIELDS_SPEC
        )
        if text:
            prompt += "\nPomocniczy tekst z OCR (może zawierać błędy, zweryfikuj ze zdjęciem):\n" + text[:3000]
        try:
            res = complete(prompt, model=model, image=str(image_path), api_key=key_ref, secret_allow=key_ref)
        except Exception:  # noqa: BLE001
            return None
    else:
        prompt = (
            "Jesteś ekstraktorem danych z polskich paragonów i faktur. Poniżej tekst z OCR "
            "(zachowana kolejność linii). " + _LLM_FIELDS_SPEC
            + "\nTEKST OCR:\n" + text[:6000]
        )
        try:
            res = complete(prompt, model=model, api_key=key_ref, secret_allow=key_ref)
        except Exception:  # noqa: BLE001
            return None
    if not isinstance(res, dict) or not res.get("ok"):
        return None
    raw = str(res.get("response") or "").strip()
    if not raw:
        return None
    # Strip ```json fences and isolate the JSON object.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    if fenced:
        raw = fenced.group(1)
    else:
        brace = re.search(r"\{.*\}", raw, re.S)
        if brace:
            raw = brace.group(0)
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    doc_type = str(data.get("type") or "").strip().lower()
    if doc_type not in _LLM_DOC_TYPES:
        doc_type = ""
    date_val = str(data.get("date") or "").strip()
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", date_val):
        date_val = ""
    else:
        try:
            date.fromisoformat(date_val)
        except ValueError:
            date_val = ""
    contractor = re.sub(r"\s+", " ", str(data.get("contractor") or "").strip())
    if len(contractor) > 70:
        contractor = contractor[:70].strip()
    amount = _coerce_amount(data.get("amount"))
    currency = re.sub(r"[^A-Za-z]", "", str(data.get("currency") or "")).upper()[:3]
    if amount and not currency:
        currency = "PLN"
    nip = re.sub(r"\D", "", str(data.get("nip") or ""))
    number = re.sub(r"\s+", " ", str(data.get("number") or "").strip())[:40]
    return {
        "type": doc_type,
        "date": date_val,
        "contractor": contractor,
        "amount": amount,
        "currency": currency,
        "nip": nip,
        "number": number,
        "model": model,
        "mode": "vision" if use_vision else "text",
    }


def _extract_document_metadata(ocr_text: str, *, captured_at: str | None = None,
                               image_path: str | None = None, use_llm: bool = True) -> dict:
    amount = _parse_amount(ocr_text)
    meta = {
        "type": _document_type(ocr_text),
        "date": _parse_document_date(ocr_text, captured_at),
        "contractor": _parse_contractor(ocr_text),
        "amount": amount["amount"],
        "currency": amount["currency"],
        "metaSource": "regex",
    }
    # LLM augmentation: an LLM reads the document in context and beats the regex parsers on
    # real-world receipts. With URIRUN_SCANNER_LLM_VISION=1 it reads the image directly. It
    # only overrides a field when it returns a confident value; everything it leaves blank
    # keeps the regex result. Failures fall back silently. ``use_llm=False`` keeps transient
    # candidate frames on the cheap regex path (no per-frame LLM cost in the live loop).
    llm = _llm_extract_metadata(ocr_text, captured_at=captured_at, image_path=image_path) if use_llm else None
    if llm:
        for key in ("type", "contractor", "amount", "currency", "date"):
            value = str(llm.get(key) or "").strip()
            if not value:
                continue
            if key == "type" and value == "dokument" and meta["type"] != "dokument":
                continue  # keep the more specific regex type over a generic LLM guess
            if key == "contractor" and value.lower() in {"kontrahent-nieznany", "sprzedawca", "sprzedauca"}:
                continue
            meta[key] = value
        for extra in ("nip", "number"):
            if str(llm.get(extra) or "").strip():
                meta[extra] = str(llm[extra]).strip()
        meta["metaSource"] = "llm"
        meta["llmModel"] = llm.get("model", "")
        meta["llmMode"] = llm.get("mode", "text")
    return meta


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


def _document_filename_with_id(filename: str, doc_id: str) -> str:
    path = Path(filename)
    doc_part = _filename_part(doc_id, default="doc-id", max_len=36)
    if doc_part and doc_part in path.stem:
        return filename
    return f"{path.stem}_{doc_part}{path.suffix or '.pdf'}"


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
            return item
    return None


def _scanner_staging_dir() -> Path:
    """Resolved directory where raw captures + receipt crops are staged."""
    return Path(os.environ.get("URIRUN_SCANNER_DIR", "~/.urirun/host-dashboard/scans")).expanduser().resolve()


def _cleanup_duplicate_scan_files(paths: list) -> list[str]:
    """Delete the transient capture files (raw scan + crop) of a detected duplicate.

    A re-scan of an already-archived document is identified by docid before any
    PDF is written, but the raw image and its ``-receipt-crop.jpg`` were already
    staged on disk. Leaving them there is what makes duplicates pile up in the
    scans folder, so remove them here. Only files inside the scanner staging dir
    are touched -- caller-supplied paths elsewhere (e.g. tests) are left alone.
    Best-effort; never raises.
    """
    try:
        staging = _scanner_staging_dir()
    except Exception:  # noqa: BLE001
        return []
    removed: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        if not raw:
            continue
        try:
            target = Path(str(raw)).expanduser().resolve()
        except Exception:  # noqa: BLE001
            continue
        key = str(target)
        if key in seen:
            continue
        seen.add(key)
        if staging not in target.parents:
            continue
        try:
            if target.is_file():
                target.unlink()
                removed.append(key)
        except OSError:
            continue
    return removed


def _scanner_crop_overlay(original_path: str | Path, crop: dict, quality: dict | None = None) -> dict:
    """Write a diagnostic image with the detected crop box drawn over the raw frame."""
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps

        source = Path(original_path).expanduser().resolve()
        if not source.is_file():
            return {"ok": False, "reason": "source image missing"}
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
        original_width, original_height = image.size
        max_side = int(os.environ.get("URIRUN_SCANNER_OVERLAY_MAX_SIDE", "1100") or "1100")
        scale = min(1.0, max(240, max_side) / max(original_width, original_height))
        canvas = image.resize((max(1, int(original_width * scale)), max(1, int(original_height * scale)))) if scale < 1.0 else image.copy()
        draw = ImageDraw.Draw(canvas)
        ok = bool(crop.get("ok"))
        partial = bool(crop.get("partialEdge"))
        color = (48, 214, 126) if ok else (239, 68, 68) if partial else (245, 158, 11)
        box = crop.get("box") if isinstance(crop.get("box"), (list, tuple)) else None
        if box and len(box) == 4:
            left, top, right, bottom = (float(value) for value in box)
            scaled_box = (
                int(max(0, min(original_width, left)) * scale),
                int(max(0, min(original_height, top)) * scale),
                int(max(0, min(original_width, right)) * scale),
                int(max(0, min(original_height, bottom)) * scale),
            )
            for offset in range(4):
                draw.rectangle(
                    (
                        scaled_box[0] - offset,
                        scaled_box[1] - offset,
                        scaled_box[2] + offset,
                        scaled_box[3] + offset,
                    ),
                    outline=color,
                )
        else:
            draw.rectangle((3, 3, canvas.size[0] - 4, canvas.size[1] - 4), outline=color, width=4)
        quality = quality or {}
        score = quality.get("score")
        label_parts = [
            "crop:ok" if ok else "crop:rejected",
            str(crop.get("method") or crop.get("reason") or ""),
            f"score={score}" if score is not None else "",
        ]
        label = " | ".join(part for part in label_parts if part)[:180]
        font = ImageFont.load_default()
        try:
            text_box = draw.textbbox((0, 0), label, font=font)
            text_width = text_box[2] - text_box[0]
            text_height = text_box[3] - text_box[1]
        except Exception:  # noqa: BLE001
            text_width = min(canvas.size[0] - 16, max(80, len(label) * 6))
            text_height = 12
        draw.rectangle((6, 6, min(canvas.size[0] - 6, text_width + 18), text_height + 18), fill=(0, 0, 0))
        draw.text((12, 10), label, fill=(255, 255, 255), font=font)
        target = source.with_name(f"{source.stem}-crop-overlay.jpg")
        canvas.save(target, format="JPEG", quality=88, optimize=True)
        return {
            "ok": True,
            "path": str(target),
            "width": canvas.size[0],
            "height": canvas.size[1],
            "scale": round(scale, 6),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": str(exc)}


_LAST_STAGING_PRUNE = 0.0


def _prune_scanner_staging(*, min_interval: float = 60.0) -> int:
    """Drop stale candidate frames from the staging dir, keeping a safety window.

    The autonomous/best-frame scanner stages ~6 frames per capture and archives
    only the chosen one, so the staging dir grows unboundedly. This prunes
    orphaned frames, but NEVER touches:

    - files of an archived document (referenced by the index),
    - files of an active, not-yet-finished best series,
    - any file younger than ``URIRUN_SCANNER_KEEP_RECENT`` seconds (default 90).

    The recent-file window matters during scanning: a frame may still be needed
    if image manipulation/capture errors and the user retries within the minute.
    Throttled to once per ``min_interval`` seconds; best-effort, never raises.
    """
    global _LAST_STAGING_PRUNE
    now = time.time()
    if now - _LAST_STAGING_PRUNE < min_interval:
        return 0
    _LAST_STAGING_PRUNE = now
    keep_recent = float(os.environ.get("URIRUN_SCANNER_KEEP_RECENT", "90"))
    if keep_recent <= 0:
        return 0
    try:
        staging = _scanner_staging_dir()
    except Exception:  # noqa: BLE001
        return 0
    if not staging.is_dir():
        return 0

    keep: set[str] = set()
    try:
        for doc in _load_document_index().get("documents", []):
            if isinstance(doc, dict):
                for key in ("originalPath", "cropPath"):
                    if doc.get(key):
                        keep.add(str(Path(str(doc[key])).expanduser().resolve()))
    except Exception:  # noqa: BLE001
        pass
    try:
        with _SCANNER_BEST_LOCK:
            sessions = list(_SCANNER_BEST_SESSIONS.values())
        for session in sessions:
            for cand in (session.get("candidates") or []):
                if isinstance(cand, dict):
                    for key in ("originalPath", "displayPath", "overlayPath"):
                        if cand.get(key):
                            keep.add(str(Path(str(cand[key])).expanduser().resolve()))
    except Exception:  # noqa: BLE001
        pass

    cutoff = now - keep_recent
    removed = 0
    try:
        entries = list(staging.iterdir())
    except OSError:
        return 0
    for entry in entries:
        try:
            if not entry.is_file():
                continue
            if str(entry.resolve()) in keep:
                continue
            if entry.stat().st_mtime > cutoff:  # safety window for in-progress scans
                continue
            entry.unlink()
            removed += 1
        except OSError:
            continue
    return removed


# --- Robust "same document" detection -----------------------------------------------
# The document identity brain lives in docid.dedup. The dashboard aliases it here
# so scanner/archive code does not duplicate token extraction, perceptual hashes
# or match thresholds.

_FINGERPRINT_DISTINCT_FIELDS = _DOCID_FINGERPRINT_DISTINCT_FIELDS
_VISUAL_NEAR_DISTANCE = _DOCID_VISUAL_NEAR_DISTANCE
_VISUAL_STRONG_DISTANCE = _DOCID_VISUAL_STRONG_DISTANCE

if _dedup_transaction_fingerprint is not None:
    _transaction_fingerprint = _dedup_transaction_fingerprint
    _fingerprint_match_count = _dedup_fingerprint_match_count
    _image_dhash = _dedup_image_dhash
    _image_phash = _dedup_image_phash
    _dhash_distance = _dedup_dhash_distance
    _metadata_completeness = _dedup_metadata_completeness
    _document_matches = _dedup_document_matches
    _business_key = _dedup_business_key
else:
    def _transaction_fingerprint(text: str) -> dict:
        return {}

    def _fingerprint_match_count(a: dict | None, b: dict | None) -> int:
        return 0

    def _image_dhash(path: str | Path) -> str:
        return ""

    def _image_phash(path: str | Path) -> str:
        return ""

    def _dhash_distance(a: str, b: str) -> int:
        return 999

    def _metadata_completeness(meta: dict | None) -> int:
        return 0

    def _document_matches(existing: dict, *, doc_id: str, source_sha256: str, text_sha256: str,
                          fingerprint: dict, dhash: str, phash: str = "",
                          metadata: dict | None = None, text: str = "") -> str:
        if doc_id and existing.get("docId") == doc_id:
            return "docId"
        if source_sha256 and existing.get("sourceSha256") == source_sha256:
            return "sourceSha256"
        if text_sha256 and existing.get("textSha256") == text_sha256:
            return "textSha256"
        return ""

    def _business_key(meta: dict | None):
        return None


_MERGE_METADATA_FIELDS = ("type", "date", "contractor", "amount", "currency")
_BLANK_METADATA_MARKERS = {"", "kwota-nieznana", "nieznana", "unknown", "n/a", "-", "kontrahent-nieznany"}


def _is_blank_metadata(value: Any) -> bool:
    return str(value or "").strip().lower() in _BLANK_METADATA_MARKERS


def _merge_metadata_fields(old_meta: dict | None, new_meta: dict, *,
                           old_weight: float, new_weight: float) -> tuple[dict, list[str]]:
    """Fuse two scans of the same document into one best-of-both record.

    Picks each field by weighted consensus, so a value one scan misread or left
    blank ("amount unknown") is filled from the other scan -- together the
    surviving record carries correct data for every field. Falls back to a
    simple "prefer the more complete, non-blank value" when docid is absent.

    Returns (merged_metadata, filled_field_names).
    """
    old_meta = old_meta or {}
    try:
        if _DocidFieldSource is None or _docid_merge_records is None:
            raise RuntimeError("docid.visual_fingerprint unavailable")

        result = _docid_merge_records(
            [
                _DocidFieldSource(fields={k: old_meta.get(k) for k in _MERGE_METADATA_FIELDS},
                                  weight=max(old_weight, 0.0001), label="archived"),
                _DocidFieldSource(fields={k: new_meta.get(k) for k in _MERGE_METADATA_FIELDS},
                                  weight=max(new_weight, 0.0001), label="rescan"),
            ],
            fields=list(_MERGE_METADATA_FIELDS),
        )
        merged = dict(new_meta)
        for key in _MERGE_METADATA_FIELDS:
            value = result["fields"].get(key)
            if not _is_blank_metadata(value):
                merged[key] = value
        return merged, list(result.get("filledGaps") or [])
    except Exception:  # noqa: BLE001
        # Fallback: keep the new scan, but backfill any field it left blank.
        merged = dict(new_meta)
        filled: list[str] = []
        for key in _MERGE_METADATA_FIELDS:
            if _is_blank_metadata(merged.get(key)) and not _is_blank_metadata(old_meta.get(key)):
                merged[key] = old_meta.get(key)
                filled.append(key)
        return merged, filled


def _enrich_archived_record(existing: dict, fused: dict, enriched_fields: list[str]) -> None:
    """Backfill an already-archived record with fields a re-scan recognized.

    Updates the in-memory index entry (``existing``) and its JSON sidecar in
    place. The PDF/image of the kept (better) scan is left untouched -- only the
    structured metadata grows. Best-effort; never raises.
    """
    for key in enriched_fields:
        value = fused.get(key)
        if not _is_blank_metadata(value):
            existing[key] = value
    existing["enrichedAt"] = _utc_now()
    history = existing.get("enrichedFields")
    history = list(history) if isinstance(history, list) else []
    for key in enriched_fields:
        if key not in history:
            history.append(key)
    existing["enrichedFields"] = history

    json_path = existing.get("jsonPath")
    if not json_path:
        return
    try:
        jpath = Path(str(json_path)).expanduser()
        data = json.loads(jpath.read_text(encoding="utf-8")) if jpath.is_file() else {}
        if not isinstance(data, dict):
            return
        for key in enriched_fields:
            value = fused.get(key)
            if not _is_blank_metadata(value):
                data[key] = value
        data["enrichedAt"] = existing["enrichedAt"]
        data["enrichedFields"] = history
        jpath.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception:  # noqa: BLE001
        pass


def _sidecar_text(item: dict) -> str:
    """OCR text for an archived record, read from its JSON sidecar (the index omits it)."""
    json_path = item.get("jsonPath")
    if not json_path:
        return ""
    try:
        path = Path(str(json_path)).expanduser()
        if not path.is_file():
            return ""
        data = json.loads(path.read_text(encoding="utf-8"))
        return str(data.get("text") or "") if isinstance(data, dict) else ""
    except Exception:  # noqa: BLE001
        return ""


def _find_duplicate_document(index: dict, *, doc_id: str, source_sha256: str, text_sha256: str,
                             fingerprint: dict, dhash: str, phash: str = "",
                             metadata: dict | None = None, text: str = "") -> dict | None:
    """Find an already-archived document that is the same as the incoming scan."""
    match: dict | None = None
    cand_key = _business_key(metadata) if (metadata and _business_key) else None
    for item in index.get("documents", []):
        if not isinstance(item, dict):
            continue
        existing = item
        # Index entries omit full OCR text. Hydrate it from the sidecar only when the
        # business key matches (rare: same merchant + date + total), so the monetary-token
        # corroboration can run without reading every sidecar on every scan.
        if cand_key is not None and not item.get("text") and _business_key(item) == cand_key:
            existing = {**item, "text": _sidecar_text(item)}
        reason = _document_matches(
            existing, doc_id=doc_id, source_sha256=source_sha256, text_sha256=text_sha256,
            fingerprint=fingerprint, dhash=dhash, phash=phash, metadata=metadata, text=text,
        )
        if reason:
            match = {**item, "_matchReason": reason}  # last match wins, mirroring _existing_scanned_id
    return match


def _archive_scanned_document(
    *,
    display_path: Path,
    original_path: Path,
    ocr: dict,
    crop: dict,
    source_sha256: str,
    captured_at: str | None,
    metadata: dict | None = None,
) -> dict:
    ocr_text = str(ocr.get("text") or "")
    # Reuse pre-computed metadata when the caller already extracted it (avoids a second LLM
    # call); otherwise extract here, feeding the full original frame to the vision pass.
    extracted = metadata if metadata is not None else _extract_document_metadata(
        ocr_text, captured_at=captured_at, image_path=str(original_path))
    docid_info = _docid_for_file(display_path, ocr_text)
    doc_id = str(docid_info["id"])
    normalized_text = _normalized_document_text(ocr_text)
    text_sha256 = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest() if normalized_text else ""
    fingerprint = _transaction_fingerprint(ocr_text)
    dhash = _image_dhash(display_path)
    phash = _image_phash(display_path)
    new_completeness = _metadata_completeness(extracted)
    month = str(extracted["date"])[:7] if re.match(r"^20\d{2}-\d{2}", str(extracted.get("date", ""))) else time.strftime("%Y-%m", time.gmtime())
    root = _document_archive_root()
    archive_dir = root / month
    filename = _document_filename_with_id(_canonical_document_filename(extracted), doc_id)

    with _DOCUMENT_INDEX_LOCK:
        index = _load_document_index()
        _backfill_scanned_id_log(index)
        index_match = _find_duplicate_document(
            index, doc_id=doc_id, source_sha256=source_sha256, text_sha256=text_sha256,
            fingerprint=fingerprint, dhash=dhash, phash=phash,
            metadata=extracted, text=ocr_text,
        )
        duplicate = index_match or _existing_scanned_id(
            doc_id=doc_id, source_sha256=source_sha256, text_sha256=text_sha256,
        )
        superseded_of = None
        merged_fields: list[str] = []
        if duplicate:
            existing_meta = duplicate.get("metadata") if isinstance(duplicate.get("metadata"), dict) else {
                key: duplicate.get(key) for key in ("type", "date", "contractor", "amount", "currency")
            }
            # Supersede only an already-archived document (index_match), and only when the
            # new scan reads strictly more complete metadata (e.g. amount known vs unknown).
            can_supersede = index_match is not None and new_completeness > _metadata_completeness(existing_meta)
            if not can_supersede:
                duplicate_path = duplicate.get("pdfPath") or duplicate.get("path")
                # The kept document is the better scan, but this re-scan may still have
                # recognized a field the archived record is missing. Fuse those in
                # (best-of-both) instead of discarding the re-scan's data outright.
                enriched_fields: list[str] = []
                if index_match is not None:
                    fused, enriched_fields = _merge_metadata_fields(
                        existing_meta, extracted,
                        old_weight=float(_metadata_completeness(existing_meta)) + 0.5,
                        new_weight=float(new_completeness),
                    )
                    if enriched_fields:
                        _enrich_archived_record(duplicate, fused, enriched_fields)
                        _save_document_index(index)
                # The document is already archived; drop the redundant staged scan + crop
                # so duplicates stop accumulating in the scans folder.
                removed_scan_files = _cleanup_duplicate_scan_files([original_path, display_path])
                duplicate_entry = {
                    "version": 1,
                    "event": "duplicate",
                    "scannedAt": _utc_now(),
                    "docId": doc_id,
                    "docIdProvider": docid_info.get("provider"),
                    "docIdSource": docid_info.get("source"),
                    "duplicate": True,
                    "duplicateOf": duplicate.get("docId") or doc_id,
                    "matchReason": duplicate.get("_matchReason") or "exact",
                    "enrichedFields": enriched_fields or None,
                    "pdfPath": duplicate_path,
                    "jsonPath": duplicate.get("jsonPath"),
                    "fileName": Path(str(duplicate_path)).name if duplicate_path else "",
                    "existingFileExists": bool(duplicate_path and Path(str(duplicate_path)).expanduser().is_file()),
                    "originalPath": str(original_path),
                    "cropPath": str(display_path),
                    "removedScanFiles": removed_scan_files,
                    "sourceSha256": source_sha256,
                    "textSha256": text_sha256,
                    "fingerprint": fingerprint,
                    "dhash": dhash,
                    "phash": phash,
                    "metadata": extracted,
                }
                _append_scanned_id_log(duplicate_entry)
                return {
                    "ok": True,
                    "duplicate": True,
                    "docId": doc_id,
                    "docIdProvider": docid_info.get("provider"),
                    "path": duplicate_path,
                    "jsonPath": duplicate.get("jsonPath"),
                    "duplicateOf": duplicate_entry["duplicateOf"],
                    "matchReason": duplicate_entry["matchReason"],
                    "enrichedFields": enriched_fields or None,
                    "existingFileExists": duplicate_entry["existingFileExists"],
                    "removedScanFiles": removed_scan_files,
                    "metadata": extracted,
                    "indexPath": str(_document_index_path()),
                    "scannedIdLogPath": str(_scanned_id_log_path()),
                }
            # Supersede: keep the better image, but FUSE fields so the surviving
            # record carries the best-of-both -- anything the old scan read that the
            # new one missed is backfilled, instead of being lost on replacement.
            extracted, merged_fields = _merge_metadata_fields(
                existing_meta, extracted,
                old_weight=float(_metadata_completeness(existing_meta)),
                new_weight=float(new_completeness),
            )
            # Recompute name/month from the fused metadata (it may now be richer).
            month = str(extracted["date"])[:7] if re.match(r"^20\d{2}-\d{2}", str(extracted.get("date", ""))) else month
            archive_dir = root / month
            filename = _document_filename_with_id(_canonical_document_filename(extracted), doc_id)
            superseded_of = duplicate.get("docId")
            _cleanup_duplicate_scan_files([duplicate.get("originalPath"), duplicate.get("cropPath")])
            for stale in (duplicate.get("pdfPath") or duplicate.get("path"), duplicate.get("jsonPath")):
                try:
                    if stale and Path(str(stale)).expanduser().is_file():
                        Path(str(stale)).expanduser().unlink()
                except OSError:
                    pass
            index["documents"] = [
                item for item in index.get("documents", [])
                if isinstance(item, dict) and item.get("docId") != superseded_of
            ]

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
            "fingerprint": fingerprint,
            "dhash": dhash,
            "phash": phash,
            "supersededOf": superseded_of,
            "mergedFields": merged_fields or None,
            "ocrBackend": ocr.get("backend"),
            "ocrChars": ocr.get("chars"),
            # OCR text is kept in the index so the business-key monetary-token dedup can run
            # against archived records without re-reading every sidecar on each scan.
            "text": ocr_text,
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
        _append_scanned_id_log({
            "version": 1,
            "event": "superseded" if superseded_of else "scan",
            "scannedAt": entry["createdAt"],
            "docId": doc_id,
            "docIdProvider": docid_info.get("provider"),
            "docIdSource": docid_info.get("source"),
            "docIdError": docid_info.get("docidError"),
            "docIdLog": docid_info.get("docidLog"),
            "duplicate": False,
            "supersededOf": superseded_of,
            "mergedFields": merged_fields or None,
            "uri": entry["uri"],
            "pdfPath": str(pdf_path),
            "jsonPath": str(json_path),
            "fileName": pdf_path.name,
            "originalPath": str(original_path),
            "cropPath": str(display_path),
            "sourceSha256": source_sha256,
            "textSha256": text_sha256,
            "fingerprint": fingerprint,
            "dhash": dhash,
            "phash": phash,
            "ocrBackend": ocr.get("backend"),
            "ocrChars": ocr.get("chars"),
            "metadata": extracted,
        })
    return {
        "ok": True,
        "duplicate": False,
        "superseded": bool(superseded_of),
        "supersededOf": superseded_of,
        "docId": doc_id,
        "docIdProvider": docid_info.get("provider"),
        "path": str(pdf_path),
        "jsonPath": str(json_path),
        "uri": entry["uri"],
        "metadata": extracted,
        "indexPath": str(_document_index_path()),
        "scannedIdLogPath": str(_scanned_id_log_path()),
    }


def shutil_which(binary: str) -> str | None:
    import shutil
    return shutil.which(binary)


def _lan_host() -> str:
    configured = os.environ.get("URIRUN_DASHBOARD_PUBLIC_HOST")
    if configured:
        return configured
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            host = sock.getsockname()[0]
            if host and not host.startswith("127."):
                return host
    except OSError:
        pass
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


def _scanner_autonomy_params() -> dict[str, str]:
    return {
        "autostart": os.environ.get("URIRUN_PHONE_SCANNER_AUTOSTART", "1"),
        "auto": os.environ.get("URIRUN_PHONE_SCANNER_AUTO", "1"),
        "best": os.environ.get("URIRUN_PHONE_SCANNER_BEST", "1"),
        "count": os.environ.get("URIRUN_PHONE_SCANNER_BEST_COUNT", "6"),
        "minScore": os.environ.get("URIRUN_PHONE_SCANNER_MIN_SCORE", "45"),
        "interval": os.environ.get("URIRUN_PHONE_SCANNER_INTERVAL", "3"),
    }


def _scanner_page_url(base_url: str) -> str:
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key, value in _scanner_autonomy_params().items():
        query.setdefault(key, value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/scanner", urlencode(query), parts.fragment))


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
    scanner_url = _scanner_page_url((qr_url or os.environ.get("URIRUN_DASHBOARD_QR_URL") or f"{base_url}/scanner").strip())
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
        detail={"uri": uri, "url": scanner_url, "selectedTargets": ["service:phone-scanner"], "artifact": artifact, "metadata": meta},
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


def _phone_scanner_url(port: int, *, scheme: str | None = None) -> str:
    scanner_scheme = (scheme or os.environ.get("URIRUN_PHONE_SCANNER_SCHEME", "https")).strip() or "https"
    return _scanner_page_url(f"{scanner_scheme}://{_url_host(_lan_host())}:{int(port)}/scanner")


def _phone_scanner_external_status(port: int, *, timeout: float = 0.35) -> dict:
    primary_scheme = os.environ.get("URIRUN_PHONE_SCANNER_SCHEME", "https").strip().lower() or "https"
    schemes = [primary_scheme]
    if os.environ.get("URIRUN_PHONE_SCANNER_PROBE_BOTH", "1").lower() in {"1", "true", "yes", "on"}:
        fallback = "http" if primary_scheme == "https" else "https"
        schemes.append(fallback)

    seen: set[str] = set()
    primary_url = _phone_scanner_url(port, scheme=primary_scheme)
    for scheme in schemes:
        if scheme in seen:
            continue
        seen.add(scheme)
        url = _phone_scanner_url(port, scheme=scheme)
        if _probe_scanner_url(url, timeout=timeout):
            return {"status": "external-running", "reachable": True, "url": url}
    return {"status": "stopped", "reachable": False, "url": primary_url}


def _nl_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.translate(str.maketrans({"ł": "l", "ß": "ss"}))


def _is_phone_scanner_prompt(prompt: str) -> bool:
    text = _nl_text(prompt)
    scanner_terms = (
        "skaner", "scanner", "skan", "scan", "kamera", "camera", "telefon", "phone", "mobile", "mobil",
        "webrtc", "qr", "qrcode", "paragon", "rachunek", "smartfon", "latark", "swiatl", "torch", "flash",
    )
    service_terms = ("aplikac", "uslug", "service", "stron", "narzedz", "interfejs")
    start_terms = (
        "uruchom", "wystart", "stworz", "utworz", "start", "create", "open", "wlacz", "odpal", "daj",
        "pokaz", "link", "adres", "ip", "qr", "wylacz", "zgas", "disable", "off",
    )
    wants_scanner = any(word in text for word in scanner_terms)
    wants_service = any(word in text for word in service_terms)
    wants_start = any(word in text for word in start_terms)
    autonomous_context = any(word in text for word in ("auto", "autonom", "samoczyn", "petl", "ciagl", "co 1"))
    mobile_context = any(word in text for word in ("telefon", "phone", "mobile", "mobil", "smartfon", "webrtc", "kamera", "camera", "qr", "skaner", "scanner", "latark", "swiatl", "torch", "flash"))
    return (wants_start and (wants_scanner or (wants_service and mobile_context))) or (autonomous_context and wants_scanner)


def _is_autonomous_scanner_prompt(prompt: str) -> bool:
    text = _nl_text(prompt)
    autonomous_terms = ("auto", "autonom", "samoczyn", "petl", "ciagl", "co 1")
    document_terms = ("paragon", "rachunek", "faktur", "receipt", "invoice")
    scanner_terms = ("skan", "scan", "skaner", "scanner", "kamera", "camera", "telefon", "smartfon", "phone", "mobile")
    return any(word in text for word in autonomous_terms) and (any(word in text for word in document_terms) or any(word in text for word in scanner_terms))


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
    scanner_url = _scanner_page_url(f"https://{_url_host(_lan_host())}:{scanner_port}/scanner")
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
        if crop.get("partialEdge"):
            reasons.append("partial-edge")
        elif crop.get("reason"):
            reasons.append("crop-rejected")

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
        "cropReason": str(crop.get("reason") or ""),
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
        "overlayPath": candidate.get("overlayPath"),
        "overlay": candidate.get("overlay"),
        "sha256": candidate.get("sha256"),
        "quality": candidate.get("quality"),
        "detectedDocument": candidate.get("detectedDocument"),
        "crop": candidate.get("crop"),
        "ocr": {key: value for key, value in ocr.items() if key != "text"},
    }


def _scanner_live_store_locked(
    series_id: str,
    series: dict,
    *,
    status: str = "running",
    error: str | None = None,
    document: dict | None = None,
    artifact: dict | None = None,
) -> None:
    candidates = [item for item in (series.get("candidates") or []) if isinstance(item, dict)]
    best = series.get("best") if isinstance(series.get("best"), dict) else None
    _SCANNER_LIVE_STREAMS[series_id] = {
        "seriesId": series_id,
        "createdAt": series.get("createdAt") or _utc_now(),
        "updatedAt": _utc_now(),
        "status": status,
        "count": len(candidates),
        "best": best,
        "candidates": candidates[-8:],
        "error": error,
        "document": document or series.get("document"),
        "artifact": artifact or series.get("artifact"),
    }
    if len(_SCANNER_LIVE_STREAMS) > 20:
        keep = sorted(_SCANNER_LIVE_STREAMS.items(), key=lambda item: str(item[1].get("updatedAt") or ""), reverse=True)[:20]
        _SCANNER_LIVE_STREAMS.clear()
        _SCANNER_LIVE_STREAMS.update(dict(keep))


def _scanner_public_candidate_for_live(candidate: dict | None, project: str) -> dict | None:
    if not isinstance(candidate, dict):
        return None
    public = _public_scanner_candidate(candidate)
    path = public.get("path")
    if path:
        public["previewUrl"] = _preview_url(str(path), project)
    original = public.get("originalPath")
    if original:
        public["originalPreviewUrl"] = _preview_url(str(original), project)
    overlay = public.get("overlayPath")
    if overlay:
        public["overlayPreviewUrl"] = _preview_url(str(overlay), project)
    return public


def scanner_live_state(project: str, limit: int = 8) -> dict:
    with _SCANNER_BEST_LOCK:
        streams = sorted(
            [dict(item) for item in _SCANNER_LIVE_STREAMS.values()],
            key=lambda item: str(item.get("updatedAt") or ""),
            reverse=True,
        )[: max(1, min(20, int(limit or 8)))]
    public_streams = []
    for stream in streams:
        candidates = [
            item for item in (_scanner_public_candidate_for_live(candidate, project) for candidate in stream.get("candidates", []))
            if item
        ]
        best = _scanner_public_candidate_for_live(stream.get("best"), project)
        document = stream.get("document") if isinstance(stream.get("document"), dict) else {}
        if document.get("path"):
            document = {**document, "previewUrl": _preview_url(str(document["path"]), project)}
        public_streams.append({
            **{key: value for key, value in stream.items() if key not in {"best", "candidates", "document"}},
            "best": best,
            "candidates": candidates,
            "document": document,
        })
    return {"ok": True, "updatedAt": _utc_now(), "streams": public_streams}


def _latest_scanner_page_status(db: str | None) -> dict:
    try:
        logs = _host_db().recent_logs(db, stream="page-action", limit=80)
    except Exception:  # noqa: BLE001
        return {}
    for item in logs:
        detail = item.get("detail") if isinstance(item.get("detail"), dict) else {}
        if item.get("event") != "result" or (detail.get("target") or "scanner") != "scanner":
            continue
        uri = str(detail.get("uri") or "")
        if not (
            uri.endswith("/camera/query/status")
            or uri.endswith("/camera/command/start")
            or uri.endswith("/ui/button/start-camera/command/click")
        ):
            continue
        result = detail.get("result") if isinstance(detail.get("result"), dict) else {}
        status = result.get("status") if isinstance(result.get("status"), dict) else result
        if not isinstance(status, dict):
            continue
        public_status = {key: value for key, value in status.items() if key != "localActions"}
        public_status.update({
            "actionUri": uri,
            "ok": detail.get("ok"),
            "error": detail.get("error") or public_status.get("error"),
            "at": detail.get("at") or item.get("created_at"),
        })
        return public_status
    return {}


def _scanner_artifact_doc_meta(artifact: dict) -> dict:
    meta = artifact.get("meta") if isinstance(artifact.get("meta"), dict) else {}
    document = meta.get("document") if isinstance(meta.get("document"), dict) else {}
    document_meta = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
    detected = meta.get("detectedDocument") if isinstance(meta.get("detectedDocument"), dict) else {}
    return {**detected, **document_meta}


def _recent_scanner_artifacts(db: str | None, project: str, limit: int = 6) -> list[dict]:
    try:
        artifacts = _host_db().list_artifacts(db, limit=80)
    except Exception:  # noqa: BLE001
        return []
    out: list[dict] = []
    for artifact in artifacts:
        kind = str(artifact.get("kind") or "")
        uri = str(artifact.get("uri") or "")
        meta = artifact.get("meta") if isinstance(artifact.get("meta"), dict) else {}
        scanner_related = (
            kind in {"camera-scan", "document-pdf", "dashboard-qr"}
            and (
                uri.startswith(("scanner://", "document://host/", "dashboard://host/qr/"))
                or str(meta.get("sourceCaptureUri") or "").startswith("scanner://")
            )
        )
        if not scanner_related:
            continue
        path = str(artifact.get("path") or "")
        display_path = str(meta.get("displayImage") or meta.get("displayPath") or path)
        if not _artifact_file_exists(path) and not _artifact_file_exists(display_path):
            continue
        doc = _scanner_artifact_doc_meta(artifact)
        item = {
            "id": artifact.get("id"),
            "kind": kind,
            "uri": uri,
            "path": path,
            "createdAt": artifact.get("created_at"),
            "previewUrl": _preview_url(display_path, project) if display_path else "",
            "filePreviewUrl": _preview_url(path, project) if path else "",
            "label": Path(path).name if path else uri,
            **{key: value for key, value in doc.items() if value},
        }
        out.append(item)
        if len(out) >= max(1, int(limit or 6)):
            break
    return out


def service_live_views(project: str, db: str | None = None, limit: int = 8) -> dict:
    scanner = scanner_live_state(project, limit=limit)
    views: list[dict] = []
    streams = scanner.get("streams") or []
    if streams:
        status_order = {"accepted": 4, "running": 3, "rejected": 2, "failed": 1}
        status = max((str(item.get("status") or "running") for item in streams), key=lambda item: status_order.get(item, 0), default="running")
        views.append({
            "id": "service:phone-scanner/live",
            "target": "service:phone-scanner",
            "serviceId": "service:phone-scanner",
            "title": "phone scanner stream",
            "kind": "stream",
            "view": "scanner-stream",
            "status": status,
            "updatedAt": scanner.get("updatedAt"),
            "refreshMs": 1000,
            "data": {"streams": streams},
            "supportedViews": ["scanner-stream", "scanner-status", "table", "image-list", "video", "iframe", "form", "graph", "json"],
        })
    service = next((item for item in _service_contacts() if item.get("id") == "service:phone-scanner"), {})
    recent_artifacts = _recent_scanner_artifacts(db, project, limit=6)
    camera_status = _latest_scanner_page_status(db)
    if service or recent_artifacts or camera_status:
        views.append({
            "id": "service:phone-scanner/status",
            "target": "service:phone-scanner",
            "serviceId": "service:phone-scanner",
            "title": "phone scanner status",
            "kind": "status",
            "view": "scanner-status",
            "status": "running" if service.get("reachable") else "stopped",
            "updatedAt": camera_status.get("at") or scanner.get("updatedAt"),
            "refreshMs": 1000,
            "data": {
                "service": service,
                "cameraStatus": camera_status,
                "recentArtifacts": recent_artifacts,
                "streamCount": len(streams),
            },
            "supportedViews": ["scanner-status", "scanner-stream", "image-list", "iframe", "json"],
        })
    return {"ok": True, "updatedAt": _utc_now(), "views": views}


def _scanner_best_update(series_id: str, candidate: dict) -> dict:
    with _SCANNER_BEST_LOCK:
        series = _SCANNER_BEST_SESSIONS.setdefault(series_id, {"createdAt": _utc_now(), "candidates": []})
        series["updatedAt"] = _utc_now()
        series["candidates"].append(candidate)
        series["candidates"] = series["candidates"][-24:]
        best = max(series["candidates"], key=lambda item: float((item.get("quality") or {}).get("score") or 0.0))
        series["best"] = best
        _scanner_live_store_locked(series_id, series, status="running")
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
    # The staged crop/image can be gone when docid recognized a duplicate and cleaned
    # staging. In that case do not register a second artifact row that points at the
    # existing document PDF; the document-pdf artifact below is the canonical record.
    display_exists = Path(str(display_path)).expanduser().is_file()
    attachments = []
    document_artifact = None
    scan_artifact = None
    overlay_path = str(meta.get("overlayPath") or "")
    if overlay_path and Path(overlay_path).expanduser().is_file():
        attachments.append({
            "kind": "crop-overlay",
            "path": overlay_path,
            "uri": f"{uri}/crop-overlay",
            "previewUrl": _preview_url(overlay_path, project),
            "meta": {
                "crop": crop,
                "quality": meta.get("quality"),
                "sourceCaptureUri": uri,
                "sourceImage": str(original_path),
            },
        })
    if document.get("ok") and document.get("path"):
        document_id = str(document.get("duplicateOf") or document.get("docId") or meta.get("sha256") or "")
        document_uri = str(document.get("uri") or f"document://host/{quote(document_id, safe='')}")
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
    if document_artifact is None and display_exists:
        scan_artifact = _host_db().register_artifact(db, "camera-scan", uri, str(display_path), meta)
    else:
        scan_artifact = {
            "kind": "camera-scan",
            "uri": uri,
            "path": None,
            "meta": meta,
            "skipped": True,
            "reason": "document-pdf artifact is canonical" if document_artifact else "staged display image is not available",
        }
    primary_artifact = document_artifact or scan_artifact
    content = content_prefix
    if crop.get("ok"):
        content += " (cropped to receipt)"
    if document.get("ok") and document.get("path"):
        content += " -> document PDF"
        if document.get("duplicate"):
            content += " (duplicate)"
    elif document.get("error"):
        content += " (document archive failed)"
    else:
        content += " (no document PDF)"
    if ocr.get("ok") and ocr.get("text"):
        content += f": {str(ocr.get('text'))[:180]}"
    elif ocr.get("error"):
        content += f" (OCR: {ocr.get('error')})"
    message = _chat_message(
        "system",
        content,
        detail={
            "artifact": primary_artifact,
            "scanArtifact": scan_artifact,
            "documentArtifact": document_artifact,
            "primaryArtifact": primary_artifact,
            "uri": uri,
            "selectedTargets": ["service:phone-scanner"],
            "ocr": ocr,
            "document": document,
        },
        attachments=attachments,
    )
    _add_chat_message(db, message)
    return {
        "artifact": primary_artifact,
        "scanArtifact": scan_artifact,
        "documentArtifact": document_artifact,
        "primaryArtifact": primary_artifact,
        "message": message,
    }


def scanner_capture(project: str, db: str | None, payload: dict) -> dict:
    _prune_scanner_staging()
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
    root = _scanner_staging_dir()
    root.mkdir(parents=True, exist_ok=True)
    name = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-phone-scan-{digest[:12]}{ext}"
    path = root / name
    path.write_bytes(raw)
    crop = _auto_crop_receipt(path)
    display_path = Path(crop["path"]) if crop.get("ok") and crop.get("path") else path
    # OCR the full original frame, not the crop: PaddleOCR handles the background and the
    # crop tended to cut the header/footer (losing seller name / "Do zapłaty" total). The
    # crop is kept only as the display thumbnail / archived preview. Set
    # URIRUN_SCANNER_OCR_FULLFRAME=0 to OCR the crop instead (legacy behaviour).
    ocr_source = path if _truthy_env("URIRUN_SCANNER_OCR_FULLFRAME", "1") else display_path
    # Transient "best frame" candidates (archive=False) only need a cheap read for quality
    # scoring; the chosen frame is re-OCR'd with the full backend at archive time
    # (_scanner_best_take). This keeps the live loop responsive while the kept document
    # still gets the accurate paddle read.
    ocr = _local_image_ocr(str(ocr_source), backend=None if archive else "tesseract")
    # LLM metadata extraction (incl. the optional vision pass on the full frame) is paid only
    # for a kept document. Transient candidate frames stay on the cheap regex path.
    detected_document = _extract_document_metadata(
        str(ocr.get("text") or ""),
        captured_at=payload.get("capturedAt"),
        image_path=str(path) if archive else None,
        use_llm=archive,
    )
    quality = _document_frame_quality(crop, ocr, detected_document, display_path)
    overlay = _scanner_crop_overlay(path, crop, quality)
    overlay_path = str(overlay.get("path") or "") if overlay.get("ok") else ""
    uri = f"scanner://host/capture/{digest[:16]}"
    document = {"ok": False, "reason": "analysis-only", "metadata": detected_document}
    # Reject low-confidence single captures (blurry/partial/non-document frames) instead of
    # archiving and showing them. Mirrors the best-frame gate so the manual "Scan" button no
    # longer fills the archive with mis-scanned receipts. Pass force=true to override.
    min_score = float(os.environ.get("URIRUN_PHONE_SCANNER_MIN_SCORE", "45"))
    quality_ok = bool(payload.get("force")) or (
        float(quality.get("score") or 0.0) >= min_score and bool(quality.get("documentLike"))
    )
    if archive and not quality_ok:
        removed_scan_files = _cleanup_duplicate_scan_files([path, display_path, overlay_path])
        reject_reason = str(quality.get("cropReason") or "")
        if not reject_reason and not quality.get("documentLike"):
            reject_reason = "not document-like"
        if not reject_reason:
            reject_reason = "low-quality scan"
        return {
            "ok": True,
            "rejected": True,
            "uri": uri,
            "reason": reject_reason,
            "minScore": min_score,
            "quality": quality,
            "ocr": ocr,
            "crop": crop,
            "overlay": overlay,
            "detectedDocument": detected_document,
            "removedScanFiles": removed_scan_files,
        }
    if archive:
        try:
            document = _archive_scanned_document(
                display_path=display_path,
                original_path=path,
                ocr=ocr,
                crop=crop,
                source_sha256=digest,
                captured_at=payload.get("capturedAt"),
                metadata=detected_document,
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
        "overlayPath": overlay_path,
        "overlay": overlay,
        "crop": crop,
        "capturedAt": payload.get("capturedAt"),
        "userAgent": payload.get("userAgent", ""),
        "ocr": ocr,
        "detectedDocument": detected_document,
        "quality": quality,
        "document": document,
    }
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
            "overlayPath": overlay_path,
            "overlay": overlay,
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
            "candidate": _scanner_public_candidate_for_live(candidate, project),
            "series": series,
            "ocr": ocr,
            "crop": crop,
            "overlay": overlay,
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
        "scanArtifact": registered["scanArtifact"],
        "documentArtifact": registered["documentArtifact"],
        "primaryArtifact": registered["primaryArtifact"],
        "ocr": ocr,
        "detectedDocument": detected_document,
        "quality": quality,
        "overlay": overlay,
        "document": document,
        "message": registered["message"],
    }


def scanner_best_finish(project: str, db: str | None, payload: dict) -> dict:
    _prune_scanner_staging()
    series_id = str(payload.get("seriesId") or "").strip()
    if not series_id:
        raise ValueError("seriesId is required")
    series = _scanner_best_take(series_id, clear=payload.get("clear", True) is not False)
    if not series:
        with _SCANNER_BEST_LOCK:
            _SCANNER_LIVE_STREAMS[series_id] = {
                "seriesId": series_id,
                "createdAt": _utc_now(),
                "updatedAt": _utc_now(),
                "status": "failed",
                "count": 0,
                "best": None,
                "candidates": [],
                "error": "scanner best series not found",
                "document": {},
                "artifact": None,
            }
        return {"ok": False, "error": "scanner best series not found", "seriesId": series_id}
    best = series.get("best")
    if not isinstance(best, dict):
        candidates = [item for item in series.get("candidates", []) if isinstance(item, dict)]
        best = max(candidates, key=lambda item: float((item.get("quality") or {}).get("score") or 0.0)) if candidates else None
    if not isinstance(best, dict):
        with _SCANNER_BEST_LOCK:
            _scanner_live_store_locked(series_id, series, status="failed", error="scanner best series has no candidates")
        return {"ok": False, "error": "scanner best series has no candidates", "seriesId": series_id}
    quality = best.get("quality") if isinstance(best.get("quality"), dict) else {}
    min_score = float(payload.get("minScore") if payload.get("minScore") is not None else 45.0)
    if not payload.get("force") and (float(quality.get("score") or 0.0) < min_score or not quality.get("documentLike")):
        with _SCANNER_BEST_LOCK:
            series["best"] = best
            _scanner_live_store_locked(series_id, series, status="rejected", error="no reliable receipt or invoice candidate found")
        return {
            "ok": False,
            "error": "no reliable receipt or invoice candidate found",
            "seriesId": series_id,
            "best": _scanner_public_candidate_for_live(best, project),
            "minScore": min_score,
        }

    original_path = Path(str(best.get("originalPath") or "")).expanduser().resolve()
    display_path = Path(str(best.get("displayPath") or "")).expanduser().resolve()
    if not original_path.is_file() or not display_path.is_file():
        with _SCANNER_BEST_LOCK:
            series["best"] = best
            _scanner_live_store_locked(series_id, series, status="failed", error="best candidate file is missing")
        return {"ok": False, "error": "best candidate file is missing", "seriesId": series_id, "best": _scanner_public_candidate_for_live(best, project)}
    crop = best.get("crop") if isinstance(best.get("crop"), dict) else {}
    ocr = best.get("ocr") if isinstance(best.get("ocr"), dict) else {}
    # Candidates were scored with the cheap OCR backend; pay for the accurate full read
    # (paddle full-frame) once, on the single frame we are about to keep. Falls back to the
    # candidate's OCR if the re-read fails.
    ocr_source = original_path if _truthy_env("URIRUN_SCANNER_OCR_FULLFRAME", "1") else display_path
    refreshed = _local_image_ocr(str(ocr_source))
    if refreshed.get("ok") and str(refreshed.get("text") or "").strip():
        ocr = refreshed
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
    overlay = best.get("overlay") if isinstance(best.get("overlay"), dict) else {}
    overlay_path = str(best.get("overlayPath") or overlay.get("path") or "")
    if not overlay_path or not Path(overlay_path).expanduser().is_file():
        overlay = _scanner_crop_overlay(original_path, crop, quality)
        overlay_path = str(overlay.get("path") or "") if overlay.get("ok") else ""
        best["overlay"] = overlay
        best["overlayPath"] = overlay_path
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
        "overlayPath": overlay_path,
        "overlay": overlay,
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
    with _SCANNER_BEST_LOCK:
        series["best"] = best
        series["document"] = document
        series["artifact"] = registered["documentArtifact"] or registered["artifact"]
        _scanner_live_store_locked(
            series_id,
            series,
            status="accepted" if document.get("ok") else "failed",
            error=None if document.get("ok") else str(document.get("error") or "document archive failed"),
            document=document,
            artifact=registered["documentArtifact"] or registered["artifact"],
        )
    return {
        "ok": True,
        "seriesId": series_id,
        "best": _scanner_public_candidate_for_live(best, project),
        "uri": uri,
        "artifact": registered["artifact"],
        "scanArtifact": registered["scanArtifact"],
        "documentArtifact": registered["documentArtifact"],
        "primaryArtifact": registered["primaryArtifact"],
        "ocr": ocr,
        "detectedDocument": best.get("detectedDocument") or {},
        "quality": quality,
        "overlay": overlay,
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
        "selectedTargets": ["service:phone-scanner"],
        "href": payload.get("href"),
        "width": payload.get("width"),
        "height": payload.get("height"),
        "userAgent": payload.get("userAgent", ""),
        "at": payload.get("at"),
        "tracks": payload.get("tracks") or [],
    }
    label = "Phone scanner opened" if event == "open" else "Phone scanner camera started" if event == "camera-started" else f"Phone scanner {event}"
    message = _chat_message("system", label, detail=detail)
    try:
        _host_db().add_log(db, "scanner-session", event, detail)
    except Exception:  # noqa: BLE001
        pass
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
            "uri": "scanner://page/camera/command/autonomous",
            "layer": "page",
            "kind": "command",
            "label": "Start autonomous receipt/invoice scanning loop",
            "sideEffects": ["camera-permission", "camera-read", "network", "document-write"],
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
        {
            "uri": "dashboard://host/service/phone-scanner/command/restart",
            "layer": "dashboard",
            "kind": "command",
            "label": "Restart the phone scanner service on its configured port",
            "sideEffects": ["service-restart", "service-start", "chat-message", "qr-artifact"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/service/chat/command/restart",
            "layer": "dashboard",
            "kind": "command",
            "label": "Restart the chat dashboard service through a configured supervisor",
            "sideEffects": ["service-restart"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "document://host/archive/command/sync-to-node",
            "layer": "host",
            "kind": "command",
            "label": "Copy archived document PDFs to a URI node through fs://",
            "sideEffects": ["node-file-write", "chat-message", "sync-log"],
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
        "dashboard://host/phone-scanner/command/restart": "dashboard://host/service/phone-scanner/command/restart",
        "service://host/phone-scanner/command/restart": "dashboard://host/service/phone-scanner/command/restart",
        "service://phone-scanner/command/restart": "dashboard://host/service/phone-scanner/command/restart",
        "scanner://host/service/command/restart": "dashboard://host/service/phone-scanner/command/restart",
        "dashboard://host/chat/command/restart": "dashboard://host/service/chat/command/restart",
        "service://host/chat/command/restart": "dashboard://host/service/chat/command/restart",
        "service://chat/command/restart": "dashboard://host/service/chat/command/restart",
        "document://host/archive/sync": "document://host/archive/command/sync-to-node",
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


def _service_restart_argv(payload: dict, *, service: str, env_prefix: str, default_unit: str) -> tuple[list[str] | None, dict]:
    manager = str(payload.get("manager") or os.environ.get(f"{env_prefix}_RESTART_MANAGER") or "").strip().lower()
    if manager in {"systemd", "systemctl"}:
        unit = str(payload.get("unit") or os.environ.get(f"{env_prefix}_SYSTEMD_UNIT") or default_unit).strip()
        if not unit:
            return None, {"error": "systemd unit is empty"}
        return ["systemctl", "--user", "restart", unit], {"manager": "systemd", "unit": unit}

    configured = str(os.environ.get(f"{env_prefix}_RESTART_CMD") or "").strip()
    if configured:
        try:
            argv = shlex.split(configured)
        except ValueError as exc:
            return None, {"error": f"invalid {env_prefix}_RESTART_CMD: {exc}"}
        if argv:
            return argv, {"manager": "command", "source": f"{env_prefix}_RESTART_CMD"}

    return None, {
        "error": f"{service} restart is not configured",
        "configureAnyOf": [
            "payload.manager=systemd with optional payload.unit",
            f"{env_prefix}_RESTART_MANAGER=systemd",
            f"{env_prefix}_RESTART_CMD='<restart command>'",
        ],
        "examplePayload": {"manager": "systemd", "unit": default_unit},
    }


def _schedule_restart_command(argv: list[str], payload: dict, meta: dict) -> dict:
    delay = float(payload.get("delaySeconds") or 0.35)
    runner = (
        "import subprocess, sys, time; "
        "time.sleep(float(sys.argv[1])); "
        "raise SystemExit(subprocess.run(sys.argv[2:]).returncode)"
    )
    subprocess.Popen(
        [sys.executable, "-c", runner, str(delay), *argv],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {"ok": True, "scheduled": True, "delaySeconds": delay, "command": argv, **meta}


def _chat_service_restart_argv(
    project: str,
    db: str | None,
    config: str | None,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    payload: dict,
) -> tuple[list[str] | None, dict]:
    import shutil

    script = str(payload.get("command") or os.environ.get("URIRUN_CHAT_SERVICE_CMD") or "").strip()
    if not script:
        script = shutil.which("urirun-service-chat") or str(Path(sys.executable).with_name("urirun-service-chat"))
    if not script or (os.path.sep in script and not Path(script).expanduser().exists()):
        return None, {
            "error": "urirun-service-chat command was not found",
            "configureAnyOf": [
                "install urirun-service-chat in the active venv",
                "payload.command=/path/to/urirun-service-chat",
                "URIRUN_CHAT_SERVICE_CMD=/path/to/urirun-service-chat",
            ],
        }
    host = str(payload.get("host") or os.environ.get("URIRUN_CHAT_HOST", "127.0.0.1"))
    port = int(payload.get("port") or os.environ.get("URIRUN_CHAT_PORT", "8194"))
    argv = [script, "restart", "--project", str(Path(project).expanduser().resolve()), "--host", host, "--port", str(port)]
    if db:
        argv.extend(["--db", db])
    if config:
        argv.extend(["--config", config])
    for node_url in node_urls or []:
        argv.extend(["--node-url", node_url])
    if token:
        argv.extend(["--token", token])
    if identity:
        argv.extend(["--identity", identity])
    if str(payload.get("forcePortKill") or payload.get("force") or "").strip().lower() in {"1", "true", "yes", "on"}:
        argv.append("--force-replace")
    return argv, {"manager": "port-replace", "port": port, "commandSource": script}


def restart_chat_service(
    payload: dict,
    *,
    project: str = ".",
    db: str | None = None,
    config: str | None = None,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
) -> dict:
    argv, meta = _service_restart_argv(
        payload,
        service="chat",
        env_prefix="URIRUN_CHAT",
        default_unit="urirun-service-chat.service",
    )
    meta.setdefault("exampleUri", "dashboard://host/service/chat/command/restart")
    if not argv:
        fallback_argv, auto_meta = _chat_service_restart_argv(project, db, config, node_urls, token, identity, payload)
        if fallback_argv:
            argv = fallback_argv
            meta = {"exampleUri": meta.get("exampleUri"), **auto_meta}
        else:
            meta = {**meta, **auto_meta}
    if not argv:
        return {"ok": False, **meta}
    return _schedule_restart_command(argv, payload, meta)


def _phone_scanner_service_id(bind_host: str, port: int) -> str:
    return f"https://{bind_host}:{port}"


def restart_phone_scanner_service(
    project: str,
    db: str | None,
    config: str | None = None,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
    payload: dict | None = None,
) -> dict:
    payload = payload or {}
    force_port_kill = str(payload.get("forcePortKill") or payload.get("force") or "").strip().lower() in {"1", "true", "yes", "on"}
    argv, meta = _service_restart_argv(
        payload,
        service="phone-scanner",
        env_prefix="URIRUN_PHONE_SCANNER",
        default_unit="urirun-service-scanner.service",
    )
    meta.setdefault("exampleUri", "dashboard://host/service/phone-scanner/command/restart")
    if argv:
        return _schedule_restart_command(argv, payload, meta)

    bind_host = str(payload.get("host") or os.environ.get("URIRUN_PHONE_SCANNER_HOST", "0.0.0.0"))
    scanner_port = int(payload.get("port") or os.environ.get("URIRUN_PHONE_SCANNER_PORT", "8196"))
    service_id = _phone_scanner_service_id(bind_host, scanner_port)
    with _SERVICE_LOCK:
        server = _SERVICE_SERVERS.pop(service_id, None)
        thread = _SERVICE_THREADS.pop(service_id, None)

    if server is not None and thread is not None and thread.is_alive():
        def _restart() -> None:
            try:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
            except Exception:  # noqa: BLE001
                pass
            ensure_phone_scanner_service(
                project,
                db,
                config,
                node_urls=node_urls,
                token=token,
                identity=identity,
                host=bind_host,
                port=scanner_port,
            )

        threading.Thread(target=_restart, name=f"urirun-phone-scanner-restart-{scanner_port}", daemon=True).start()
        return {
            "ok": True,
            "scheduled": True,
            "manager": "in-process",
            "service": "phone-scanner",
            "port": scanner_port,
            "url": _phone_scanner_url(scanner_port),
        }

    replaced = _free_port_from_old_scanner(scanner_port, force=force_port_kill)
    if replaced.get("holders"):
        if not replaced.get("ok") or replaced.get("remaining"):
            return {
                "ok": False,
                **meta,
                "replace": replaced,
                "reason": "port is owned by a process that was not safely replaceable; use forcePortKill only in a controlled environment",
            }
        started = ensure_phone_scanner_service(
            project,
            db,
            config,
            node_urls=node_urls,
            token=token,
            identity=identity,
            host=bind_host,
            port=scanner_port,
        )
        return {"ok": True, "manager": "port-replace", "restart": True, "replace": replaced, **started}

    status = _phone_scanner_external_status(scanner_port)
    if not status.get("reachable"):
        started = ensure_phone_scanner_service(
            project,
            db,
            config,
            node_urls=node_urls,
            token=token,
            identity=identity,
            host=bind_host,
            port=scanner_port,
        )
        return {"ok": True, "manager": "start-if-stopped", "restart": False, **started}

    return {
        "ok": False,
        **meta,
        "status": status,
        "reason": "scanner is reachable but is not managed by this dashboard process; configure a supervisor restart command",
    }


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


_INPROCESS_BINDINGS_GROUP = "urirun.bindings"


def _run_inprocess_connector_uri(uri: str, action_payload: dict) -> dict | None:
    """Execute an installed in-process connector URI (widget://, artifact://, …) through the
    urirun runtime and return its unwrapped handler value. Returns None when no connector owns
    the route, so :func:`uri_invoke` can fall back to its legacy "unsupported URI action" error.

    This is what lets the dashboard pull connector output over a URI request rather than baking
    it into the page — e.g. the chat-stream widgets are loaded from
    ``widget://host/bundle/query/js`` instead of being inlined in INDEX_HTML."""
    try:
        import urirun
        from urirun.runtime import discovery

        registry = discovery.registry_for_uri(uri, _INPROCESS_BINDINGS_GROUP)
        env = urirun.run(uri, registry, payload=dict(action_payload or {}),
                         mode="execute", policy={"allowExecute": True})
    except Exception as exc:  # noqa: BLE001 - a connector error must not crash the API
        return {"ok": False, "invokedUri": uri, "error": str(exc)}
    if not env.get("ok") and (env.get("error") or {}).get("category") == "NOT_FOUND":
        return None  # no connector owns this route → let the caller raise the legacy error
    try:
        value = urirun.result_data(env)
    except Exception:  # noqa: BLE001
        value = (env.get("result") or {}).get("value") if isinstance(env.get("result"), dict) else None
    return {"ok": bool(env.get("ok")), "invokedUri": uri,
            "result": value if value is not None else env.get("result"),
            "error": (env.get("error") or {}).get("message") if not env.get("ok") else None}


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
    effective_uri = str(action.get("uri") if action else uri)

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

    if effective_uri in {"scanner://host/capture/command/run", "scanner://host/capture"}:
        result = scanner_capture(project, db, action_payload)
    elif effective_uri in {"scanner://host/best/command/finish", "scanner://host/best/finish"}:
        result = scanner_best_finish(project, db, action_payload)
    elif effective_uri in {"scanner://host/session/command/log", "scanner://host/session"}:
        result = scanner_session(db, action_payload)
    elif effective_uri == "dashboard://host/phone-scanner/command/start":
        result = ensure_phone_scanner_service(
            project,
            db,
            config,
            node_urls=node_urls,
            token=token,
            identity=identity,
        )
    elif effective_uri == "dashboard://host/service/phone-scanner/command/restart":
        result = restart_phone_scanner_service(
            project,
            db,
            config,
            node_urls=node_urls,
            token=token,
            identity=identity,
            payload=action_payload,
        )
    elif effective_uri == "dashboard://host/service/chat/command/restart":
        result = restart_chat_service(
            action_payload,
            project=project,
            db=db,
            config=config,
            node_urls=node_urls,
            token=token,
            identity=identity,
        )
    elif effective_uri in {"document://host/archive/command/sync-to-node", "document://host/archive/sync"}:
        result = sync_documents_to_node(
            project,
            db,
            config,
            action_payload,
            node_urls=node_urls,
            token=token,
            identity=identity,
        )
    else:
        # Not a hardcoded dashboard/scanner action: try an installed in-process connector
        # (widget://, artifact://, …) over the urirun runtime before giving up.
        dispatched = _run_inprocess_connector_uri(effective_uri, action_payload)
        if dispatched is not None:
            return dispatched
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


def _service_contacts() -> list[dict]:
    scanner_port = int(os.environ.get("URIRUN_PHONE_SCANNER_PORT", "8196"))
    scanner_state = _phone_scanner_external_status(scanner_port)
    phone_scanner = {
        "id": "service:phone-scanner",
        "kind": "service",
        "name": "phone-scanner",
        "label": "urirun service: photo scanner",
        "url": scanner_state["url"],
        "status": scanner_state["status"],
        "reachable": scanner_state["reachable"],
        "routes": [
            "dashboard://host/phone-scanner/command/start",
            "dashboard://host/service/phone-scanner/command/restart",
            "service://host/phone-scanner/command/restart",
            "service://phone-scanner/command/restart",
            "scanner://page/camera/command/scan",
            "scanner://page/camera/command/best-pdf",
            "scanner://page/camera/command/autonomous",
        ],
    }
    contacts = [phone_scanner]
    with _SERVICE_LOCK:
        for service_id, server in _SERVICE_SERVERS.items():
            thread = _SERVICE_THREADS.get(service_id)
            parsed = urlparse(service_id)
            port = int(parsed.port or scanner_port)
            service_url = _phone_scanner_url(port)
            name = "phone-scanner" if port == scanner_port else f"service-{port}"
            alive = bool(thread is not None and thread.is_alive())
            external = {"status": "stopped", "reachable": False, "url": service_url} if alive else _phone_scanner_external_status(port)
            item = {
                **phone_scanner,
                "id": f"service:{name}",
                "name": name,
                "label": f"urirun service: {name}",
                "url": service_url if alive else external["url"],
                "bindUrl": service_id,
                "status": "running" if alive else external["status"],
                "reachable": alive or bool(external["reachable"]),
                "serverName": getattr(server, "server_name", ""),
            }
            contacts = [entry for entry in contacts if entry.get("id") != item["id"]]
            contacts.append(item)
    return contacts


def summary(project: str, db: str | None, config: str | None, node_urls: list[str] | None = None) -> dict:
    tickets, task_error = _safe_tickets(project, sprint="all")
    host_db = _host_db()
    mesh = _mesh()
    try:
        discovered = mesh.discover_mesh(_host_config(config, node_urls))
    except Exception as exc:  # noqa: BLE001
        discovered = {"nodes": [], "routes": [], "serviceMap": {}, "error": str(exc)}
    checks = host_db.recent_checks(db, limit=10)
    artifacts = _public_artifacts(host_db.list_artifacts(db, limit=10), project)
    logs = host_db.recent_logs(db, limit=10)
    nodes = discovered.get("nodes") or []
    routes = discovered.get("routes") or []
    services = _service_contacts()
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
        "serviceCount": len(services),
        "nodes": nodes,
        "services": services,
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


def _needs_screen_document_capture(prompt: str) -> bool:
    text_value = prompt.casefold()
    wants_screen = any(word in text_value for word in ("zrzut", "screenshot", "screen capture", "zrzuty ekranu"))
    wants_document = any(word in text_value for word in ("pdf", "dokument", "document", "faktur", "rachunek", "paragon"))
    return wants_screen and wants_document


def _route_in_selected_targets(route: dict, selected_nodes: list[str], selected_targets: list[str]) -> bool:
    if not selected_nodes and not selected_targets:
        return True
    route_node = str(route.get("node") or "")
    uri = str(route.get("uri") or "")
    target_names = set(selected_nodes)
    for target in selected_targets:
        if target.startswith("node:"):
            target_names.add(target.split(":", 1)[1])
        elif target == "host":
            target_names.add("host")
    if route_node and route_node in target_names:
        return True
    if "host" in target_names and "://host/" in uri:
        return True
    return any(f"://{name}/" in uri for name in target_names if name)


def _has_screen_capture_route(routes: list[dict], selected_nodes: list[str], selected_targets: list[str]) -> bool:
    for route in routes:
        if not _route_in_selected_targets(route, selected_nodes, selected_targets):
            continue
        uri = str(route.get("uri") or "").casefold()
        if uri.startswith(("screen://", "kvm://")):
            return True
        if "screenshot" in uri:
            return True
        if uri.startswith("browser://") and "/capture" in uri:
            return True
    return False


def _screen_document_capability_gap(prompt: str, discovered: dict, selected_nodes: list[str], selected_targets: list[str]) -> dict | None:
    if not _needs_screen_document_capture(prompt):
        return None
    routes = discovered.get("routes") or []
    if _has_screen_capture_route(routes, selected_nodes, selected_targets):
        return None
    related = [
        route.get("uri") for route in routes
        if any(token in str(route.get("uri") or "") for token in ("camera://", "ocr://", "fs://", "browser://", "screen://", "kvm://"))
    ][:20]
    return {
        "type": "CapabilityGap",
        "missing": "screen-capture",
        "message": "Brakuje route'u URI do zrzutow ekranu node'a. Dostepne sa camera/ocr/fs, ale nie screen/kvm/browser screenshot.",
        "selectedNodes": selected_nodes,
        "selectedTargets": selected_targets,
        "requiredAnyOf": [
            "screen://<node>/.../screenshot",
            "kvm://<node>/.../screenshot",
            "browser://<node>/page/command/screenshot",
        ],
        "availableRelatedRoutes": related,
    }


def chat_ask(project: str, db: str | None, config: str | None, payload: dict, node_urls: list[str] | None = None,
             token: str | None = None, identity: str | None = None) -> dict:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    selected_nodes = [str(item).strip() for item in (payload.get("nodes") or []) if str(item).strip()]
    selected_targets = [str(item).strip() for item in (payload.get("targets") or []) if str(item).strip()]
    if not selected_targets:
        selected_targets = ["host", *[f"node:{name}" for name in selected_nodes]]
    execute = bool(payload.get("execute"))
    no_llm = bool(payload.get("no_llm") or payload.get("noLlm"))
    _add_chat_message(db, _chat_message(
        "user",
        prompt,
        detail={"execute": execute, "selectedNodes": selected_nodes, "selectedTargets": selected_targets, "noLlm": no_llm},
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
        camera_autonomous_uri = "scanner://page/camera/command/autonomous"
        torch_click_uri = "scanner://page/ui/button/torch/command/click"
        torch_enabled = _torch_enabled_from_prompt(prompt)
        autonomous_scan = _is_autonomous_scanner_prompt(prompt)
        camera_action_uri = camera_autonomous_uri if autonomous_scan else camera_click_uri
        camera_payload = {
            "target": "scanner",
            "startBest": torch_enabled is None,
            "auto": bool(autonomous_scan),
            "count": int(os.environ.get("URIRUN_PHONE_SCANNER_BEST_COUNT", "6")),
            "minScore": float(os.environ.get("URIRUN_PHONE_SCANNER_MIN_SCORE", "45")),
            "interval": float(os.environ.get("URIRUN_PHONE_SCANNER_INTERVAL", "3")),
        }
        if autonomous_scan or _is_camera_start_prompt(prompt) or torch_enabled is not None:
            queued_camera = page_action_enqueue(
                db,
                target="scanner",
                uri=camera_action_uri,
                payload=camera_payload,
                mode="execute",
                source="chat",
            )
            camera_message = _chat_message(
                "system",
                "Autonomous scanner queued for the open scanner page. Open the scanner URL and accept the browser camera permission if prompted."
                if autonomous_scan else
                "Camera start queued for the open scanner page. Open the scanner URL and accept the browser camera permission if prompted.",
                detail={
                    "uri": camera_action_uri,
                    "selectedTargets": ["service:phone-scanner"],
                    "queued": queued_camera,
                    "scannerUrl": service.get("url"),
                    "autonomous": bool(autonomous_scan),
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
                    "selectedTargets": ["service:phone-scanner"],
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
            "selectedTargets": selected_targets,
            "generator": {"provider": "host-dashboard", "intent": "phone-scanner-service"},
            "flow": {
                "task": {"id": "phone-scanner-service", "title": "Start phone scanner service"},
                "steps": [
                    {"id": "start-phone-scanner", "uri": "dashboard://host/phone-scanner/command/start", "payload": {}},
                    *([{
                        "id": "queue-camera-autonomous" if autonomous_scan else "queue-camera-start",
                        "uri": camera_action_uri,
                        "payload": camera_payload,
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
                    "id": "queue-camera-autonomous" if autonomous_scan else "queue-camera-start",
                    "uri": camera_action_uri,
                    "target": "scanner-page",
                    "ok": bool(queued_camera.get("ok")),
                    "status": "queued",
                    "autonomous": bool(autonomous_scan),
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
                    "selectedTargets": selected_targets,
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
        capability_gap = _screen_document_capability_gap(prompt, discovered, selected_nodes, selected_targets)
        if capability_gap:
            result = {
                "ok": False,
                "prompt": prompt,
                "execute": execute,
                "selectedNodes": selected_nodes,
                "selectedTargets": selected_targets,
                "generator": {"provider": "host-dashboard", "intent": "capability-check"},
                "nodeCount": len(discovered.get("nodes") or []),
                "routeCount": len(discovered.get("routes") or []),
                "flow": {"task": {"id": "capability-gap", "title": "Missing URI capability"}, "steps": []},
                "timeline": [],
                "results": {},
                "error": capability_gap,
            }
            _add_chat_message(db, _chat_message(
                "system",
                "failed: missing screen-capture URI route for requested screenshot-to-document workflow",
                detail={
                    "prompt": prompt,
                    "execute": execute,
                    "ok": False,
                    "selectedTargets": selected_targets,
                    "generator": result["generator"],
                    "flow": result["flow"],
                    "timeline": [],
                    "results": {},
                    "error": capability_gap,
                },
            ))
            try:
                _host_db().add_log(
                    db,
                    "chat",
                    "ask",
                    {
                        "prompt": prompt,
                        "execute": execute,
                        "ok": False,
                        "selectedNodes": selected_nodes,
                        "selectedTargets": selected_targets,
                        "generator": result["generator"],
                        "timeline": [],
                        "error": capability_gap,
                    },
                )
            except Exception:
                pass
            return result
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
        "selectedTargets": selected_targets,
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
            "selectedTargets": selected_targets,
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
                "selectedTargets": selected_targets,
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


def _artifact_delete_roots(project: str) -> list[Path]:
    roots = [
        Path(os.environ.get("URIRUN_ARTIFACT_DIR", "~/.urirun/artifacts")).expanduser(),
        Path(os.environ.get("URIRUN_DOCUMENT_DIR", "~/.urirun/documents")).expanduser(),
        Path("~/.urirun/host-dashboard").expanduser(),
    ]
    out: list[Path] = []
    for root in roots:
        try:
            out.append(root.resolve())
        except OSError:
            continue
    return out


def _artifact_file_delete_allowed(path: str, project: str) -> bool:
    if not path:
        return False
    try:
        resolved = Path(path).expanduser().resolve()
    except OSError:
        return False
    roots = _artifact_delete_roots(project)
    return any(resolved == root or root in resolved.parents for root in roots)


def _payload_bool(payload: dict, name: str, default: bool) -> bool:
    if name not in payload:
        return default
    value = payload.get(name)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _global_document_metadata_paths() -> set[Path]:
    paths: set[Path] = set()
    for candidate in (_document_index_path(), _scanned_id_log_path()):
        try:
            paths.add(candidate.expanduser().resolve())
        except OSError:
            continue
    return paths


def _safe_artifact_sidecar_path(path: str | None, project: str) -> str | None:
    if not path:
        return None
    try:
        target = Path(str(path)).expanduser().resolve()
    except OSError:
        return None
    if target.suffix.lower() != ".json":
        return None
    if target in _global_document_metadata_paths():
        return None
    if not _artifact_file_delete_allowed(str(target), project):
        return None
    return str(target)


def _artifact_delete_candidate_paths(item: dict, project: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    artifact_path = str(item.get("path") or "")
    if artifact_path:
        out.append((artifact_path, "artifact"))
        try:
            sibling = Path(artifact_path).expanduser().resolve().with_suffix(".json")
            if sibling.is_file():
                sidecar = _safe_artifact_sidecar_path(str(sibling), project)
                if sidecar:
                    out.append((sidecar, "sidecar"))
        except OSError:
            pass

    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    document = meta.get("document") if isinstance(meta.get("document"), dict) else {}
    for candidate in (meta.get("jsonPath"), document.get("jsonPath")):
        sidecar = _safe_artifact_sidecar_path(str(candidate or ""), project)
        if sidecar:
            out.append((sidecar, "sidecar"))
    return out


def artifacts_delete(project: str, db: str | None, payload: dict) -> dict:
    ids = payload.get("ids") or payload.get("artifactIds") or []
    if isinstance(ids, str):
        ids = [ids]
    clean_ids = [str(item).strip() for item in ids if str(item).strip()]
    if not clean_ids:
        return {"ok": False, "error": "ids are required", "deleted": 0, "filesDeleted": 0}
    host_db = _host_db()
    artifacts = host_db.artifacts_by_ids(db, clean_ids)
    delete_files = _payload_bool(payload, "deleteFiles", True)
    files: list[dict] = []
    if delete_files:
        seen_paths: set[str] = set()
        for item in artifacts:
            candidates = _artifact_delete_candidate_paths(item, project)
            for artifact_path, role in candidates:
                if not artifact_path or artifact_path in seen_paths:
                    continue
                seen_paths.add(artifact_path)
                info = {"path": artifact_path, "role": role, "deleted": False, "skipped": False, "error": ""}
                if not _artifact_file_delete_allowed(artifact_path, project):
                    info["skipped"] = True
                    info["error"] = "path is outside allowed artifact roots"
                    files.append(info)
                    continue
                try:
                    target = Path(artifact_path).expanduser().resolve()
                    if target.is_file():
                        target.unlink()
                        info["deleted"] = True
                    else:
                        info["skipped"] = True
                        info["error"] = "file missing"
                except OSError as exc:
                    info["error"] = str(exc)
                files.append(info)
    deleted = host_db.delete_artifacts(db, clean_ids)
    result = {
        "ok": True,
        "requested": len(clean_ids),
        "matched": len(artifacts),
        "deleted": deleted,
        "filesDeleted": len([item for item in files if item.get("deleted")]),
        "files": files,
    }
    try:
        host_db.add_log(db, "artifacts", "delete", result)
    except Exception:  # noqa: BLE001
        pass
    return result


def artifacts_dedupe_rows(project: str, db: str | None, payload: dict) -> dict:
    """Remove duplicate artifact DB rows that point at the same physical output.

    This is intentionally DB-only: it never removes files. It keeps the same
    canonical row the UI would display, so historical `camera-scan` + `document-pdf`
    duplicates can be compacted without changing the artifact grid semantics.
    """
    limit = int(payload.get("limit") or 10_000)
    limit = max(1, min(limit, 50_000))
    delete_rows = _payload_bool(payload, "deleteRows", True)
    host_db = _host_db()
    public = _public_artifacts(host_db.list_artifacts(db, limit=limit), project)
    groups: dict[tuple[str, str], list[dict]] = {}
    for item in public:
        key = _artifact_dedupe_key(item)
        if not key[1]:
            continue
        groups.setdefault(key, []).append(item)

    duplicate_groups: list[dict] = []
    delete_ids: list[str] = []
    for key, group in groups.items():
        if len(group) < 2:
            continue
        keep = sorted(group, key=_artifact_dedupe_rank)[0]
        keep_id = str(keep.get("id") or "")
        duplicate_ids = [
            str(item.get("id"))
            for item in group
            if item.get("id") and str(item.get("id")) != keep_id
        ]
        if not duplicate_ids:
            continue
        delete_ids.extend(duplicate_ids)
        duplicate_groups.append({
            "key": {"type": key[0], "value": key[1]},
            "keepId": keep_id,
            "keepKind": keep.get("kind"),
            "deleteIds": duplicate_ids,
            "count": len(group),
        })

    deleted = host_db.delete_artifacts(db, delete_ids) if delete_rows and delete_ids else 0
    result = {
        "ok": True,
        "scanned": len(public),
        "groups": duplicate_groups,
        "duplicateRows": len(delete_ids),
        "deleted": deleted,
        "dryRun": not delete_rows,
    }
    try:
        host_db.add_log(db, "artifacts", "dedupe", result)
    except Exception:  # noqa: BLE001
        pass
    return result


def artifacts_cleanup_orphan_sidecars(project: str, db: str | None, payload: dict) -> dict:
    delete_files = _payload_bool(payload, "deleteFiles", True)
    include_artifact_dir = _payload_bool(payload, "includeArtifactDir", False)
    roots = [Path(os.environ.get("URIRUN_DOCUMENT_DIR", "~/.urirun/documents")).expanduser()]
    if include_artifact_dir:
        roots.append(Path(os.environ.get("URIRUN_ARTIFACT_DIR", "~/.urirun/artifacts")).expanduser())
    global_metadata = _global_document_metadata_paths()
    sibling_suffixes = (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".bin")
    files: list[dict] = []
    seen: set[Path] = set()
    for root in roots:
        try:
            resolved_root = root.resolve()
        except OSError:
            continue
        if not resolved_root.is_dir():
            continue
        for candidate in resolved_root.rglob("*.json"):
            try:
                target = candidate.resolve()
            except OSError:
                continue
            if target in seen or target in global_metadata or target.name == "index.json":
                continue
            seen.add(target)
            if not _artifact_file_delete_allowed(str(target), project):
                files.append({"path": str(target), "role": "orphan-sidecar", "deleted": False, "skipped": True, "error": "path is outside allowed artifact roots"})
                continue
            siblings = [target.with_suffix(suffix) for suffix in sibling_suffixes]
            if any(path.is_file() for path in siblings):
                continue
            info = {"path": str(target), "role": "orphan-sidecar", "deleted": False, "skipped": False, "error": ""}
            if delete_files:
                try:
                    target.unlink()
                    info["deleted"] = True
                except OSError as exc:
                    info["error"] = str(exc)
            else:
                info["skipped"] = True
                info["error"] = "dry run"
            files.append(info)
    result = {
        "ok": True,
        "filesDeleted": len([item for item in files if item.get("deleted")]),
        "files": files,
    }
    try:
        _host_db().add_log(db, "artifacts", "cleanup-orphans", result)
    except Exception:  # noqa: BLE001
        pass
    return result


def documents_reconcile(project: str, db: str | None, payload: dict | None = None) -> dict:
    """Prune document-index entries whose artifacts are gone from disk.

    Index-only and non-destructive: existing files are never touched. Returns the
    summary report from :func:`reconcile_document_index` and logs it.
    """
    result = reconcile_document_index()
    try:
        _host_db().add_log(db, "documents", "reconcile-index", result)
    except Exception:  # noqa: BLE001
        pass
    return result


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
        artifacts = host_db.list_artifacts(db, kind=_first(query, "kind"), limit=int(_first(query, "limit", "20") or 20))
        include_missing = str(_first(query, "includeMissing", "") or "").lower() in {"1", "true", "yes", "on"}
        include_duplicates = str(_first(query, "includeDuplicates", "") or "").lower() in {"1", "true", "yes", "on"}
        return 200, {
            "ok": True,
            "artifacts": _visible_public_artifacts(
                artifacts,
                project,
                include_missing=include_missing,
                include_duplicates=include_duplicates,
            ),
        }
    if path == "/api/chat/history":
        return 200, chat_history(db, project, limit=int(_first(query, "limit", "80") or 80))
    if path == "/api/services/live":
        return 200, service_live_views(project, db=db, limit=int(_first(query, "limit", "8") or 8))
    if path == "/api/scanner/live":
        return 200, scanner_live_state(project, limit=int(_first(query, "limit", "8") or 8))
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
                if parsed.path == "/favicon.ico":
                    self.send_response(204)
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.end_headers()
                    return
                if parsed.path == "/scanner":
                    _html_response(self, SCANNER_HTML)
                    return
                if parsed.path == "/services/view":
                    _html_response(self, _service_widget_html(project, parse_qs(parsed.query)))
                    return
                if parsed.path == "/services/view.svg":
                    _asset_response(
                        self,
                        _service_widget_svg(project, parse_qs(parsed.query)).encode("utf-8"),
                        "image/svg+xml; charset=utf-8",
                    )
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
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return
            except Exception as exc:  # noqa: BLE001
                try:
                    _json_response(self, 500, {"ok": False, "error": str(exc)})
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return

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
                if parsed.path == "/api/chat/messages/delete":
                    payload = _read_json(self)
                    _json_response(self, 200, chat_delete_messages(db, payload))
                    return
                if parsed.path == "/api/artifacts/delete":
                    payload = _read_json(self)
                    _json_response(self, 200, artifacts_delete(project, db, payload))
                    return
                if parsed.path == "/api/artifacts/dedupe":
                    payload = _read_json(self)
                    _json_response(self, 200, artifacts_dedupe_rows(project, db, payload))
                    return
                if parsed.path == "/api/artifacts/cleanup-orphans":
                    payload = _read_json(self)
                    _json_response(self, 200, artifacts_cleanup_orphan_sidecars(project, db, payload))
                    return
                if parsed.path == "/api/documents/reconcile":
                    payload = _read_json(self)
                    _json_response(self, 200, documents_reconcile(project, db, payload))
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
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return
            except Exception as exc:  # noqa: BLE001
                try:
                    _json_response(self, 400, {"ok": False, "error": str(exc)})
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return

        def log_message(self, fmt, *args: Any):
            return

    return Handler


def _port_holder_pids(port: int) -> list[int]:
    """PIDs currently LISTENing on `port` (best effort via ss)."""
    try:
        out = subprocess.run(["ss", "-ltnpH"], capture_output=True, text=True, timeout=5).stdout
    except Exception:  # noqa: BLE001
        return []
    pids: list[int] = []
    for line in out.splitlines():
        norm = " ".join(line.split())
        if f":{port} " not in norm:
            continue
        pids.extend(int(m) for m in re.findall(r"pid=(\d+)", norm))
    return pids


def _process_cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            return fh.read().replace(b"\x00", b" ").decode("utf-8", "replace")
    except OSError:
        return ""


def _is_dashboard_process(pid: int) -> bool:
    """True only if `pid` is a urirun host dashboard serve process (cmdline check). The guard
    that keeps auto-replace from ever killing an unrelated service that owns the port."""
    cmd = _process_cmdline(pid)
    return "host dashboard serve" in cmd


def _is_scanner_process(pid: int) -> bool:
    cmd = _process_cmdline(pid)
    return any(term in cmd for term in (
        "urirun-service-scanner",
        "urirun-scanner",
        "urirun_service_scanner",
    ))


def _is_chat_process(pid: int) -> bool:
    cmd = _process_cmdline(pid)
    return any(term in cmd for term in (
        "urirun-service-chat",
        "urirun_service_chat",
    ))


def _free_port_from_matching_processes(
    port: int,
    *,
    force: bool,
    emit: bool,
    is_target: Any,
    event_prefix: str,
) -> dict:
    import signal

    me = os.getpid()

    def holders() -> list[int]:
        return [p for p in _port_holder_pids(port) if p != me]

    def targets() -> list[int]:
        return [p for p in holders() if force or is_target(p)]

    initial_holders = holders()
    initial_targets = targets()
    skipped = [p for p in initial_holders if p not in initial_targets]
    killed: list[int] = []
    for pid in initial_targets:
        try:
            os.kill(pid, signal.SIGTERM)
            killed.append(pid)
            if emit:
                print(json.dumps({"event": f"{event_prefix}.replacing_old", "pid": pid, "port": port}), flush=True)
        except OSError:
            pass
    if initial_targets:
        deadline = time.time() + 8.0
        while time.time() < deadline:
            if not targets():
                break
            time.sleep(0.2)
        for pid in targets():
            try:
                os.kill(pid, signal.SIGKILL)
                killed.append(pid)
                if emit:
                    print(json.dumps({"event": f"{event_prefix}.force_killed_old", "pid": pid, "port": port}), flush=True)
            except OSError:
                pass
        time.sleep(0.3)

    remaining = holders()
    remaining_blockers = [p for p in remaining if force or is_target(p)]
    return {
        "ok": not remaining_blockers and (force or not skipped),
        "port": port,
        "force": bool(force),
        "holders": initial_holders,
        "targets": initial_targets,
        "skipped": [{"pid": p, "cmdline": _process_cmdline(p)} for p in skipped],
        "killed": sorted(set(killed)),
        "remaining": [{"pid": p, "cmdline": _process_cmdline(p)} for p in remaining],
    }


def _free_port_from_old_scanner(port: int, *, force: bool = False, emit: bool = False) -> dict:
    """Free a scanner-owned port before rebinding it.

    By default this only terminates processes whose cmdline is clearly the scanner service.
    `force=True` may be used by an explicit URI/CLI request in a controlled dev environment.
    """
    return _free_port_from_matching_processes(
        port,
        force=force,
        emit=emit,
        is_target=_is_scanner_process,
        event_prefix="urirun.service_scanner",
    )


def _free_port_from_old_chat(port: int, *, force: bool = False, emit: bool = False) -> dict:
    """Free a chat-dashboard-owned port before rebinding it."""
    return _free_port_from_matching_processes(
        port,
        force=force,
        emit=emit,
        is_target=_is_chat_process,
        event_prefix="urirun.service_chat",
    )


def _free_port_from_old_dashboard(port: int) -> None:
    """Before binding, terminate a previous dashboard instance still holding `port` so the new
    one can start cleanly. SAFETY: only kills processes whose cmdline is a urirun host
    dashboard serve — never an unrelated service that happens to own the port."""
    import signal

    me = os.getpid()

    def stale() -> list[int]:
        return [p for p in _port_holder_pids(port) if p != me and _is_dashboard_process(p)]

    targets = stale()
    for pid in targets:
        try:
            os.kill(pid, signal.SIGTERM)
            print(json.dumps({"event": "urirun.host_dashboard.replacing_old", "pid": pid, "port": port}), flush=True)
        except OSError:
            pass
    if not targets:
        return
    deadline = time.time() + 8.0
    while time.time() < deadline:
        if not stale():
            return
        time.sleep(0.2)
    for pid in stale():  # last resort for a stubborn holder
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    time.sleep(0.3)


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
    # Starting a new dashboard auto-replaces the old one holding this port (parent+worker), so
    # `serve` never dies on "Address already in use".
    _free_port_from_old_dashboard(int(port))
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
