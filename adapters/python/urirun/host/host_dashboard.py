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
from urllib.parse import parse_qs, parse_qsl, quote, unquote, urlencode, urlparse, urlsplit, urlunsplit

from .document_sync import (
    DocumentSyncDeps,
    document_archive_pdfs as _document_archive_pdfs_impl,
    document_sync_verification as _document_sync_verification_impl,
    sync_documents_to_node as _sync_documents_to_node_impl,
)
from .discovery import (
    add_node_aliases as _add_node_aliases_impl,
    alias_map_from_dict as _alias_map_from_dict_impl,
    alias_map_from_list as _alias_map_from_list_impl,
    classify_route_run as _classify_route_run_impl,
    host_config as _host_config_impl,
    iter_node_alias_values as _iter_node_alias_values_impl,
    known_nodes_file_data as _known_nodes_file_data_impl,
    known_nodes_file_urls as _known_nodes_file_urls_impl,
    merge_known_nodes_into_config as _merge_known_nodes_into_config_impl,
    node_alias_map_from_config_doc as _node_alias_map_from_config_doc_impl,
    node_alias_map_from_context as _node_alias_map_from_context_impl,
    node_alias_map_from_env as _node_alias_map_from_env_impl,
    node_alias_map_from_known_nodes_file as _node_alias_map_from_known_nodes_file_impl,
    node_alias_map_from_node_urls as _node_alias_map_from_node_urls_impl,
    node_alias_map_from_value as _node_alias_map_from_value_impl,
    node_dicts_from_url_map as _node_dicts_from_url_map_impl,
    node_spec_aliases as _node_spec_aliases_impl,
    node_test_routes as _node_test_routes_impl,
    node_url_map_from_value as _node_url_map_from_value_impl,
    normalize_known_node_url as _normalize_known_node_url_impl,
    prompt_node_match as _prompt_node_match_impl,
    route_inputs_example as _route_inputs_example_impl,
    url_map_from_dict as _url_map_from_dict_impl,
    url_map_from_list as _url_map_from_list_impl,
)
from .fs_transfer import (
    deploy_fs_file_transfer_fallback as _deploy_fs_file_transfer_fallback_impl,
    ensure_node_uri_routes as _ensure_node_uri_routes_impl,
    fs_file_transfer_binding as _fs_file_transfer_binding_impl,
    fs_file_transfer_fallback_bindings as _fs_file_transfer_fallback_bindings_impl,
    node_has_route as _node_has_route_impl,
    route_key as _route_key_impl,
)
from .object_registry import (
    annotate_node_tokens as _annotate_node_tokens_impl,
    host_object as _host_object_impl,
    host_registry_routes as _host_registry_routes_impl,
    service_contacts as _service_contacts_impl,
)
from .scanner_bridge import (
    PAGE_ACTION_LOCK as _SCANNER_PAGE_ACTION_LOCK,
    PAGE_ACTION_QUEUES as _SCANNER_PAGE_ACTION_QUEUES,
    ScannerBridgeDeps,
    crop_overlay_attachment as _crop_overlay_attachment_impl,
    page_action_enqueue as _page_action_enqueue_impl,
    page_action_poll as _page_action_poll_impl,
    page_action_result as _page_action_result_impl,
    is_scanner_artifact as _is_scanner_artifact_impl,
    latest_scanner_page_status as _latest_scanner_page_status_impl,
    register_document_artifact as _register_document_artifact_impl,
    register_scanner_result as _register_scanner_result_impl,
    scanner_artifact_item as _scanner_artifact_item_impl,
    scanner_artifact_doc_meta as _scanner_artifact_doc_meta_impl,
    scanner_status_from_log as _scanner_status_from_log_impl,
    scanner_session as _scanner_session_impl,
    scanner_result_content as _scanner_result_content_impl,
    scanner_service_live_views as _scanner_service_live_views_impl,
    uri_event as _uri_event_impl,
)
from .service_control import (
    chat_service_restart_argv as _chat_service_restart_argv_impl,
    free_port_from_matching_processes as _free_port_from_matching_processes_impl,
    free_port_from_old_dashboard as _free_port_from_old_dashboard_impl,
    is_chat_process as _is_chat_process_impl,
    is_dashboard_process as _is_dashboard_process_impl,
    is_scanner_process as _is_scanner_process_impl,
    port_holder_pids as _port_holder_pids_impl,
    process_cmdline as _process_cmdline_impl,
    restart_chat_service as _restart_chat_service_impl,
    schedule_restart_command as _schedule_restart_command_impl,
    service_restart_argv as _service_restart_argv_impl,
)
from .widgets import (
    query_value as _widget_query_value,
    scanner_stream_summary as _scanner_stream_summary_impl,
    select_service_view as _select_service_view_impl,
    service_widget_summary as _service_widget_summary_impl,
)


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
_PAGE_ACTION_LOCK = _SCANNER_PAGE_ACTION_LOCK
_PAGE_ACTION_QUEUES = _SCANNER_PAGE_ACTION_QUEUES


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
    /* Nodes view goes full page width so the Nodes | URI Processes columns are roomy. */
    body[data-view="nodes"] .grid {
      grid-template-columns: minmax(0, 1fr);
    }
    body[data-view="nodes"] .grid > .stack:not(aside) {
      grid-column: 1 / -1;
    }
    body[data-view="nodes"] .grid > aside.stack {
      display: none;
    }
    /* Activity view is logs-only and full page width (its panels live in the aside). */
    body[data-view="activity"] .grid {
      grid-template-columns: minmax(0, 1fr);
    }
    body[data-view="activity"] .grid > .stack:not(aside) {
      display: none;
    }
    body[data-view="activity"] .grid > aside.stack {
      grid-column: 1 / -1;
      display: grid;
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
      grid-template-columns: minmax(260px, .35fr) minmax(0, .65fr);
      gap: 14px;
      align-items: start;
    }
    .discovery-target {
      width: 100%;
      text-align: left;
      display: block;
      border: 1px solid var(--line);
      background: var(--surface-2);
      color: var(--text);
      border-radius: 8px;
      padding: 10px 12px;
      cursor: pointer;
    }
    .discovery-target.active {
      border-color: var(--accent);
      box-shadow: inset 3px 0 0 var(--accent);
      background: var(--surface);
    }
    .discovery-route-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 8px;
    }
    .route-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
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
    .nodes-layout {
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 14px;
      align-items: start;
    }
    .nodes-layout.hidden { display: none; }
    .node-row { cursor: pointer; }
    .node-row.node-row-active { border-color: var(--accent); background: var(--surface-3); }
    @media (max-width: 920px) { .nodes-layout { grid-template-columns: 1fr; } }
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
      .discovery-layout { grid-template-columns: 1fr; }
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
        <button data-view="host">Host</button>
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
          <div class="panel-head"><h2>URI Objects</h2><span class="subtle" id="discoveryCount"></span></div>
          <div class="panel-body"><div class="list" id="discoveryList"></div></div>
        </article>
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2 id="discoveryRouteTitle">URI Registry</h2>
              <p class="subtle" id="discoveryRouteMeta"></p>
            </div>
            <span class="subtle" id="discoveryRouteCount"></span>
          </div>
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
      <section class="nodes-layout view-block" data-section="host">
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2>Konfiguracja hosta</h2>
              <p class="subtle">Tożsamość, ścieżki i status lokalnego hosta urirun.</p>
            </div>
            <span class="pill" id="hostStatusPill"></span>
          </div>
          <div class="panel-body"><div class="list" id="hostConfigList"></div></div>
        </article>
        <article class="panel">
          <div class="panel-head"><h2>Możliwości hosta (URI)</h2><span class="subtle" id="hostRouteCount"></span></div>
          <div class="panel-body"><div class="list" id="hostRoutesList"></div></div>
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
        <section class="nodes-layout view-block" data-section="nodes">
        <article class="panel">
          <div class="panel-head"><h2>Nodes</h2><span class="subtle" id="nodeCount"></span></div>
          <div class="panel-body">
            <div class="list" id="nodesList"></div>
            <details class="add-node-help" style="margin-top:10px">
              <summary>➕ Jak dodać node (gdy nie ma go na liście)</summary>
              <div class="stack" style="margin-top:8px">
                <div class="artifact-actions">
                  <button type="button" id="scanNodesBtn" onclick="scanNodes()">🔎 Skanuj sieć (LAN)</button>
                  <span id="scanNodesStatus" class="subtle"></span>
                </div>
                <div id="scanNodesResults" class="list"></div>
                <p class="subtle">Mesh nie wykrywa węzłów automatycznie (świadomie — węzły są jawne i enrolled). Skan to jednorazowe, read-only sondowanie /health po lokalnej podsieci na porcie węzła; znalezione węzły dodajesz przyciskiem „dodaj".</p>
                <p class="subtle">Albo wpisz ręcznie: node to nazwa + URL usługi urirun (port węzła) — poniżej dostaniesz gotowy wpis do wklejenia (host i urifix rozwiążą ten node).</p>
                <label class="stack"><span class="subtle">Nazwa node'a</span><input id="addNodeName" oninput="nodeAddSnippet()" placeholder="office-node"></label>
                <label class="stack"><span class="subtle">URL node'a</span><input id="addNodeUrl" oninput="nodeAddSnippet()" placeholder="http://host-or-ip:8765"></label>
                <div class="artifact-actions">
                  <button type="button" onclick="saveNodeFromForm()">💾 Zapisz node</button>
                  <a id="addNodeHealth" href="#" target="_blank" rel="noreferrer">otwórz /health (sprawdź osiągalność)</a>
                  <span id="addNodeStatus" class="subtle"></span>
                </div>
                <label class="stack"><span class="subtle">Token zarządzania węzłem (X-Urirun-Token) — potrzebny do provisioningu tras na zdalnym węźle</span>
                  <input id="addNodeToken" type="password" autocomplete="off" placeholder="wklej token węzła (zapisywany w keyring, nie w plaintext)"></label>
                <div class="artifact-actions">
                  <button type="button" onclick="saveNodeToken()">🔑 Zapisz token (keyring)</button>
                  <span id="addNodeTokenStatus" class="subtle"></span>
                </div>
                <p class="subtle">„Zapisz" trwale dodaje node do host config (host go rozwiąże) i do ~/.urirun/nodes.json (urifix auto-naprawa). Albo wklej ręcznie jeden z poniższych:</p>
                <pre id="addNodeSnippet" class="mono">— wpisz nazwę i URL powyżej —</pre>
              </div>
            </details>
          </div>
        </article>
        <article class="panel">
          <div class="panel-head"><h2>URI Processes</h2><span class="subtle" id="routeCount"></span><span id="routesNodeFilter" class="subtle"></span></div>
          <div class="panel-body"><div class="list" id="routesList"></div></div>
        </article>
        </section>
      </div>
      <aside class="stack">
        <article class="panel view-block" data-section="activity">
          <div class="panel-head"><h2>Logs</h2><span class="subtle" id="logCount"></span></div>
          <div class="panel-body"><div id="logsList"></div></div>
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
    <button data-view="host">Host</button>
    <button data-view="nodes">Nodes</button>
    <button data-view="activity">Activity</button>
  </nav>
  <script>
    const VALID_VIEWS = new Set(['overview', 'chat', 'discovery', 'artifacts', 'widgets', 'tasks', 'host', 'nodes', 'activity']);
    const params = new URLSearchParams(window.location.search);
    const initialView = VALID_VIEWS.has(params.get('view')) ? params.get('view') : (VALID_VIEWS.has(params.get('tab')) ? params.get('tab') : 'overview');
    const initialChatFull = params.get('chat') === 'full' || params.get('fullscreen') === 'chat';
    const initialTargets = (params.get('targets') || 'host').split(',').map((item) => item.trim()).filter(Boolean);
    const initialDiscoveryTarget = (params.get('discovery') || params.get('registry') || '').trim();
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
      dashboardWidgets: null,
      selectedRoutesNode: null,
      visibleChatMessages: [],
      visibleChatMessageIds: [],
      selectedChatMessageIds: new Set(),
      chatFullscreen: initialChatFull,
      discoveryTarget: initialDiscoveryTarget,
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
        targets: state.selectedTargets.join(','),
        discovery: state.discoveryTarget || '',
        prompt: $('chatPrompt') ? $('chatPrompt').value.trim() : ''
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
      setParam(search, 'discovery', controls.discovery);
      setParam(search, 'prompt', controls.prompt);
      setParam(search, 'prompt_len', controls.prompt ? controls.prompt.length : '');
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
      if ($('chatPrompt') && (search.has('prompt') || search.has('message'))) {
        $('chatPrompt').value = search.get('prompt') || search.get('message') || '';
      }
      const targets = (search.get('targets') || 'host').split(',').map((item) => item.trim()).filter(Boolean);
      state.selectedTargets = targets.length ? targets : ['host'];
      (search.get('nodes') || '').split(',').map((item) => item.trim()).filter(Boolean).forEach((node) => {
        const target = node.startsWith('node:') ? node : `node:${node}`;
        if (!state.selectedTargets.includes(target)) state.selectedTargets.push(target);
      });
      const discovery = (search.get('discovery') || search.get('registry') || '').trim();
      if (discovery) state.discoveryTarget = discovery;
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
      $('nodesList').innerHTML = nodes.map((node) => `<div class="item node-row${state.selectedRoutesNode === node.name ? ' node-row-active' : ''}" data-node="${esc(node.name)}" onclick="selectNodeRoutes(this.dataset.node)" title="Kliknij, aby pokazać procesy URI tego węzła">
        <div style="display:flex;align-items:center;gap:8px;justify-content:space-between">
          <span><strong>${esc(node.name)}</strong> <span class="pill ${node.reachable ? 'up' : 'down'}">${node.reachable ? 'up' : 'down'}</span></span>
          <button type="button" data-node="${esc(node.name)}" onclick="event.stopPropagation(); testNodeFromList(this.dataset.node)" title="Przetestuj route'y query tego węzła">Test</button>
        </div>
        <div class="mono">${esc(node.url)}</div>
        <div class="subtle">${(node.routes || []).length} routes${node.error ? ` · ${esc(node.error)}` : ''}</div>
        <details class="node-token-form" onclick="event.stopPropagation()" style="margin-top:6px">
          <summary class="subtle">🔑 Token zarządzania (X-Urirun-Token) · ${node.hasToken ? '✓ ustawiony' : 'brak'}</summary>
          <div class="stack" style="margin-top:6px">
            <p class="subtle">Potrzebny do zarządzania zdalnym węzłem — provisioning/deploy i trasy <code>node://</code>. Bez niego takie wywołania zwracają <em>unauthorized</em>. Wartość trafia do systemowego <strong>keyring</strong> (referencja <code>secret://keyring/urirun-node-token/${esc(node.name)}</code>), nigdy do pliku, DOM ani logów.</p>
            <input type="password" autocomplete="off" class="node-token-input" placeholder="wklej token węzła '${esc(node.name)}'">
            <div class="artifact-actions">
              <button type="button" data-node="${esc(node.name)}" onclick="saveNodeTokenFor(this)">🔑 Zapisz token (keyring)</button>
              <span class="node-token-status subtle"></span>
            </div>
          </div>
        </details>
      </div>`).join('') || empty('No nodes configured — use “➕ Jak dodać node” below to add one.');
      // Surface the how-to-add panel automatically when nothing is configured, so a missing
      // node (e.g. a sync target that failed with "node_url is required") is fixable in place.
      const help = document.querySelector('.add-node-help');
      if (help && nodes.length === 0) help.open = true;
      nodeAddSnippet();
    }

    // Copy a value (config path, host URL) to the clipboard with light visual feedback.
    async function copyHostValue(btn, value) {
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) await navigator.clipboard.writeText(value || '');
        if (btn) { const prev = btn.textContent; btn.textContent = '✓'; setTimeout(() => { btn.textContent = prev; }, 1200); }
      } catch (error) { /* clipboard unavailable — value is still visible inline */ }
    }

    // Render the dedicated Host menu: identity, on-disk paths and mesh counts for the local host,
    // plus the URI routes the host itself exposes. Data comes straight from /api/summary (no extra
    // endpoint) — this is the host counterpart to the Nodes view, split out into its own tab.
    function renderHost(summary) {
      summary = summary || {};
      const host = summary.host || {};
      const pill = $('hostStatusPill');
      if (pill) {
        pill.textContent = host.status || (host.reachable ? 'up' : 'local');
        pill.className = 'pill ' + (host.reachable === false ? 'down' : 'up');
      }
      const rows = [
        { label: 'Host', value: host.label || 'urirun host' },
        { label: 'Katalog projektu', value: summary.project || host.url || '', mono: true, copy: true },
        { label: 'Baza danych (db)', value: summary.db || '', mono: true, copy: true },
        { label: 'Plik konfiguracji', value: summary.config || '', mono: true, copy: true },
        { label: 'Węzły (nodes)', value: `${summary.nodesOnline || 0} online · ${summary.nodeCount || 0} skonfigurowanych` },
        { label: 'Procesy URI hosta', value: `${(summary.hostRoutes || []).length}` },
        { label: 'Usługi (services)', value: `${summary.serviceCount || 0}` },
      ];
      $('hostConfigList').innerHTML = rows.map((row) => `<div class="item">
        <div style="display:flex;align-items:center;gap:8px;justify-content:space-between">
          <span class="subtle">${esc(row.label)}</span>
          ${row.copy && row.value ? `<button type="button" title="Kopiuj" onclick="copyHostValue(this, ${JSON.stringify(row.value).replace(/"/g, '&quot;')})">⧉</button>` : ''}
        </div>
        <div class="${row.mono ? 'mono' : ''}">${esc(row.value) || '<span class="subtle">—</span>'}</div>
      </div>`).join('');

      const hostRoutes = summary.hostRoutes || [];
      $('hostRouteCount').textContent = `${hostRoutes.length} routes`;
      $('hostRoutesList').innerHTML = hostRoutes.slice(0, 80).map((route) => `<div class="item">
        <div class="route-title"><span class="mono">${esc(route.uri)}</span>${route.safe === false ? '<span class="pill down">unsafe</span>' : ''}</div>
        ${route.title ? `<div>${esc(route.title)}</div>` : ''}
        <div class="subtle">${esc(text(route.kind, 'route'))} · ${esc(text(route.layer, 'host'))}${route.source ? ` · ${esc(route.source)}` : ''}</div>
      </div>`).join('') || empty('Host nie udostępnia żadnych procesów URI.');
    }

    // Build the ready-to-paste config for adding a node by name + URL (host + urifix resolve it).
    function nodeAddSnippet() {
      const nameEl = $('addNodeName'); if (!nameEl) return;
      const name = (nameEl.value || '').trim() || 'office-node';
      const url = ($('addNodeUrl').value || '').trim().replace(/\/+$/, '') || 'http://HOST:PORT';
      const health = $('addNodeHealth'); if (health) health.href = url + '/health';
      const entry = {}; entry[name] = url;
      $('addNodeSnippet').textContent =
        '1) ~/.urirun/nodes.json  (czyta to urifix do auto-naprawy node_url):\n' +
        JSON.stringify(entry, null, 2) + '\n\n' +
        '2) zmienna srodowiskowa hosta:\n' +
        'URIRUN_NODES="' + name + '=' + url + '"\n\n' +
        '3) jednorazowo w wywolaniu URI (np. document://host/archive/command/sync-to-node):\n' +
        'node_urls=["' + name + '=' + url + '"]';
    }

    // Reuse the netscan:// connector over the existing URI dispatch (no host-specific endpoint):
    // /api/uri/invoke runs netscan://host/lan/query/nodes in-process and returns discovered nodes.
    async function scanNodes() {
      const btn = $('scanNodesBtn'); const status = $('scanNodesStatus'); const out = $('scanNodesResults');
      if (!btn) return;
      btn.disabled = true; status.textContent = 'skanuję LAN…'; out.innerHTML = '';
      try {
        const env = await api('/api/uri/invoke', {
          method: 'POST',
          body: JSON.stringify({ uri: 'netscan://host/lan/query/nodes', mode: 'execute', payload: {}, source: 'nodes-scan' }),
        });
        const data = (env && env.result) || env || {};
        const nodes = data.nodes || [];
        status.textContent = `${esc(data.subnet || '')} · znaleziono ${nodes.length} / przeskanowano ${data.scanned || 0}`;
        out.innerHTML = nodes.map((n) => `<div class="item">
          <div><strong>${esc(n.name || n.host)}</strong> <span class="pill up">node</span> <span class="subtle">v${esc(n.version || '?')}</span></div>
          <div class="mono">${esc(n.url)}</div>
          <div class="artifact-actions"><button type="button" data-name="${esc(n.name || n.host)}" data-url="${esc(n.url)}" onclick="saveNode(this.dataset.name, this.dataset.url)">dodaj</button></div>
        </div>`).join('') || empty('Brak węzłów urirun w tej podsieci na porcie 8765. Jeśli netscan nie jest zainstalowany: pip install urirun-connector-netscan.');
      } catch (error) {
        status.textContent = 'błąd skanu: ' + error.message;
      } finally {
        btn.disabled = false;
      }
    }

    // A discovered node -> prefill the add-node form + snippet (then paste it where shown).
    function useScannedNode(name, url) {
      if ($('addNodeName')) $('addNodeName').value = name || '';
      if ($('addNodeUrl')) $('addNodeUrl').value = url || '';
      nodeAddSnippet();
      const snip = $('addNodeSnippet'); if (snip && snip.scrollIntoView) snip.scrollIntoView({ block: 'nearest' });
    }

    // Persist a node to host config (+ urifix's nodes.json) and refresh the Nodes list.
    async function saveNode(name, url) {
      const status = $('addNodeStatus');
      useScannedNode(name, url);  // reflect what we're saving in the form + snippet
      name = (name || '').trim(); url = (url || '').trim();
      if (!name || !url) { if (status) status.textContent = 'podaj nazwę i URL'; return; }
      if (status) status.textContent = 'zapisuję…';
      try {
        const res = await api('/api/nodes/add', { method: 'POST', body: JSON.stringify({ name, url }) });
        if (status) status.textContent = 'zapisano: ' + (res.node ? res.node.name + ' → ' + res.node.url : name);
        if (typeof load === 'function') load().catch(() => {});  // refresh /health-checked node status
      } catch (error) {
        if (status) status.textContent = 'błąd zapisu: ' + error.message;
      }
    }
    function saveNodeFromForm() {
      saveNode(($('addNodeName') || {}).value || '', ($('addNodeUrl') || {}).value || '');
    }

    // Store the node's management token in the OS keyring (server-side). The value is sent once,
    // never echoed back; the field is cleared on success. User types it — never pre-filled.
    async function saveNodeToken() {
      const status = $('addNodeTokenStatus');
      const name = (($('addNodeName') || {}).value || '').trim();
      const tokenEl = $('addNodeToken');
      const token = (tokenEl && tokenEl.value) || '';
      if (!name) { if (status) status.textContent = 'najpierw podaj nazwę node\'a'; return; }
      if (!token) { if (status) status.textContent = 'wklej token'; return; }
      if (status) status.textContent = 'zapisuję token…';
      try {
        const res = await api('/api/nodes/token', { method: 'POST', body: JSON.stringify({ name, token }) });
        if (tokenEl) tokenEl.value = '';  // never keep the secret in the DOM
        if (status) status.textContent = 'token zapisany w keyring dla ' + (res.name || name) + ' (' + (res.tokenRef || '') + ')';
      } catch (error) {
        if (status) status.textContent = 'błąd: ' + error.message;
      }
    }

    // Per-node token save (from a node card in the Nodes view). Reuses /api/nodes/token; the
    // node name is the card's, the value goes straight to the OS keyring server-side.
    async function saveNodeTokenFor(btn) {
      const name = btn && btn.dataset ? btn.dataset.node : '';
      const form = btn.closest('.node-token-form');
      const input = form ? form.querySelector('.node-token-input') : null;
      const status = form ? form.querySelector('.node-token-status') : null;
      const token = (input && input.value) || '';
      if (!name) { if (status) status.textContent = 'brak nazwy węzła'; return; }
      if (!token) { if (status) status.textContent = 'wklej token'; return; }
      if (status) status.textContent = 'zapisuję token…';
      try {
        const res = await api('/api/nodes/token', { method: 'POST', body: JSON.stringify({ name, token }) });
        if (input) input.value = '';  // never keep the secret in the DOM
        if (status) status.textContent = '✓ zapisano w keyring (' + (res.tokenRef || 'secret://keyring/urirun-node-token/' + name) + ')';
      } catch (error) {
        if (status) status.textContent = 'błąd: ' + error.message;
      }
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

    function uriTarget(uri) {
      const value = text(uri);
      if (!value.includes('://')) return '';
      return value.split('://', 2)[1].split('/', 1)[0] || '';
    }

    function normalizeRoute(route, owner) {
      const item = typeof route === 'string' ? { uri: route } : (route || {});
      return {
        uri: text(item.uri),
        kind: text(item.kind),
        adapter: text(item.adapter || item.source),
        title: text(item.title || item.label || ''),
        safe: item.safe,
        owner: owner.id,
        ownerLabel: owner.label,
        target: text(item.node || item.target || uriTarget(item.uri) || owner.id),
      };
    }

    function dedupeRoutes(routes) {
      const seen = new Set();
      return routes.filter((route) => {
        const key = `${route.uri}|${route.kind}|${route.adapter}`;
        if (!route.uri || seen.has(key)) return false;
        seen.add(key);
        return true;
      });
    }

    function routesForNode(summary, node) {
      const ownRoutes = Array.isArray(node.routes) ? node.routes : [];
      if (ownRoutes.length) return ownRoutes;
      return (summary.routes || []).filter((route) => route.node === node.name || uriTarget(route.uri) === node.name);
    }

    function discoveryObjects(summary) {
      const host = summary.host || {};
      const hostOwner = {
        id: 'host',
        kind: 'host',
        label: host.label || 'urirun host',
        status: host.status || 'local',
        reachable: host.reachable !== false,
        url: host.url || summary.project || '',
      };
      const hostObject = {
        ...hostOwner,
        routes: dedupeRoutes((host.routes || summary.hostRoutes || []).map((route) => normalizeRoute(route, hostOwner))),
      };
      const nodeObjects = (summary.nodes || []).map((node) => {
        const owner = {
          id: `node:${node.name}`,
          kind: 'node',
          label: `urirun node: ${node.name}`,
          status: node.reachable ? 'up' : 'down',
          reachable: !!node.reachable,
          url: node.url || '',
        };
        return {
          ...owner,
          routes: dedupeRoutes(routesForNode(summary, node).map((route) => normalizeRoute(route, owner))),
        };
      });
      const serviceObjects = (summary.services || []).map((service) => {
        const owner = {
          id: service.id || `service:${service.name}`,
          kind: 'service',
          label: service.label || `urirun service: ${service.name}`,
          status: service.status || (service.reachable ? 'running' : 'stopped'),
          reachable: !!service.reachable,
          url: service.url || '',
        };
        return {
          ...owner,
          routes: dedupeRoutes((service.routes || []).map((route) => normalizeRoute(route, owner))),
        };
      });
      return [hostObject, ...nodeObjects, ...serviceObjects];
    }

    function chooseDiscoveryTarget(objects) {
      if (objects.some((item) => item.id === state.discoveryTarget)) return state.discoveryTarget;
      const nodeTarget = state.selectedTargets.find((target) => target.startsWith('node:') && objects.some((item) => item.id === target));
      if (nodeTarget) return nodeTarget;
      const serviceTarget = state.selectedTargets.find((target) => target.startsWith('service:') && objects.some((item) => item.id === target));
      if (serviceTarget) return serviceTarget;
      return objects.length ? objects[0].id : 'host';
    }

    function renderDiscovery(summary) {
      const objects = discoveryObjects(summary);
      state.discoveryTarget = chooseDiscoveryTarget(objects);
      const selected = objects.find((item) => item.id === state.discoveryTarget) || objects[0] || null;
      $('discoveryCount').textContent = `${objects.length} objects`;
      $('discoveryList').innerHTML = objects.map((item) => {
        const active = item.id === state.discoveryTarget ? 'active' : '';
        const pillClass = item.reachable === false ? 'down' : 'up';
        return `<button type="button" class="discovery-target ${active}" data-discovery-target="${esc(item.id)}">
          <div><strong>${esc(item.label)}</strong> <span class="pill ${pillClass}">${esc(item.status || item.kind)}</span></div>
          <div class="mono">${esc(item.id)}</div>
          <div class="subtle">${esc(item.url || '')}</div>
          <div class="subtle">${item.routes.length} URI routes · ${esc(item.kind || '')}</div>
        </button>`;
      }).join('') || empty('No URI objects discovered');
      if (!selected) {
        $('discoveryRouteTitle').textContent = 'URI Registry';
        $('discoveryRouteMeta').textContent = '';
        $('discoveryRouteCount').textContent = '0 routes';
        $('discoveryRoutesList').innerHTML = empty('No object selected');
        return;
      }
      $('discoveryRouteTitle').textContent = `${selected.label} registry`;
      $('discoveryRouteMeta').textContent = `${selected.id}${selected.url ? ` · ${selected.url}` : ''}`;
      $('discoveryRouteCount').textContent = `${selected.routes.length} routes`;
      $('discoveryRoutesList').innerHTML = selected.routes.map((route) => `<div class="item">
        <div class="route-title"><span class="mono">${esc(route.uri)}</span>${route.safe === false ? '<span class="pill down">unsafe</span>' : ''}</div>
        ${route.title ? `<div>${esc(route.title)}</div>` : ''}
        <div class="subtle">${esc(route.ownerLabel)} · ${esc(route.kind || 'route')} · ${esc(route.adapter || 'registry')} · target:${esc(route.target)}</div>
      </div>`).join('') || empty('No URI routes for this object');
    }

    function renderRoutes(routes) {
      // When a node is selected (clicked in the Nodes column), show only its URI processes.
      const sel = state.selectedRoutesNode;
      const filterEl = $('routesNodeFilter');
      let list = routes || [];
      if (sel) {
        const node = (((state.summary || {}).nodes) || []).find((n) => n.name === sel) || { name: sel };
        list = routesForNode(state.summary || {}, node);
        if (filterEl) filterEl.innerHTML = ` · <strong>node:${esc(sel)}</strong> <a href="#" onclick="clearRoutesNodeFilter();return false;">(wszystkie)</a>`;
      } else if (filterEl) {
        filterEl.textContent = '';
      }
      $('routeCount').textContent = `${list.length} routes`;
      // When a node is selected, offer URI testing: probe all read-only query routes, or tick
      // specific routes and test just those (commands included = an explicit choice).
      const testBar = sel ? `<div class="node-test-bar" style="display:flex;gap:8px;align-items:center;margin-bottom:8px;flex-wrap:wrap">
          <button type="button" data-node="${esc(sel)}" onclick="testNodeRoutes(this.dataset.node, null)">Test query routes</button>
          <button type="button" data-node="${esc(sel)}" onclick="testNodeRoutes(this.dataset.node, 'selected')">Test selected</button>
          <span class="subtle" id="nodeTestSummary"></span>
        </div>` : '';
      const rows = list.slice(0, 60).map((route) => {
        const u = esc(route.uri);
        const cb = sel ? `<input type="checkbox" class="rt-sel" value="${u}"> ` : '';
        return `<div class="item" data-rt="${u}">
          <div class="mono">${cb}${u}<span class="route-test subtle"></span></div>
          <div class="subtle">${esc(text(route.node))} · ${esc(text(route.kind))} · ${esc(text(route.adapter))}</div>
        </div>`;
      }).join('') || empty(sel ? `Brak procesów URI przypisanych do node:${sel}` : 'No routes discovered');
      $('routesList').innerHTML = testBar + rows;
    }

    function nodeTestSelectedUris() {
      return [...document.querySelectorAll('#routesList .rt-sel:checked')].map((c) => c.value);
    }

    async function testNodeRoutes(node, mode) {
      if (!node) return;
      const uris = mode === 'selected' ? nodeTestSelectedUris() : null;
      if (mode === 'selected' && (!uris || !uris.length)) { alert('Zaznacz route(y) do przetestowania.'); return; }
      const summaryEl = $('nodeTestSummary');
      if (summaryEl) summaryEl.textContent = 'testowanie...';
      document.querySelectorAll('#routesList .route-test').forEach((s) => { s.textContent = ''; s.title = ''; });
      writeUrlState({ action: 'nodes:test-routes', node, mode: mode || 'query' }, { replace: true });
      try {
        const res = await api('/api/nodes/test-routes', {
          method: 'POST', body: JSON.stringify({ node, ...(uris ? { uris } : {}) }),
        });
        renderNodeTestResults(res);
      } catch (error) {
        if (summaryEl) summaryEl.textContent = 'błąd: ' + error.message;
        alert(error.message);
      }
    }

    function renderNodeTestResults(res) {
      const summaryEl = $('nodeTestSummary');
      if (!res || res.ok === false) {
        if (summaryEl) summaryEl.textContent = 'błąd: ' + ((res && res.error) || 'test failed');
        return;
      }
      if (summaryEl) summaryEl.textContent = `${res.okCount}/${res.tested} ok · ${res.reachable} reachable · ${res.broken} broken (${esc(res.mode)})`;
      const badge = { 'ok': '✅', 'handler-error': '⚠️', 'not-found': '⛔', 'unreachable': '🚫' };
      const byUri = {};
      (res.results || []).forEach((r) => { byUri[r.uri] = r; });
      document.querySelectorAll('#routesList .item[data-rt]').forEach((el) => {
        const r = byUri[el.dataset.rt];
        const slot = el.querySelector('.route-test');
        if (r && slot) { slot.textContent = ` ${badge[r.status] || '?'} ${r.status}`; slot.title = r.detail || ''; }
      });
    }

    // Click a node -> filter the URI Processes column to that node (click again / "(wszystkie)" to clear).
    function selectNodeRoutes(name) {
      if (!name) return;
      state.selectedRoutesNode = (state.selectedRoutesNode === name) ? null : name;
      const summary = state.summary || {};
      renderNodes(summary.nodes || []);
      renderRoutes(summary.routes || []);
    }
    // "Test" button on a node row: reveal that node's routes (so the result badges have a home),
    // then probe its read-only query routes — one click, no need to open the column first.
    function testNodeFromList(name) {
      if (!name) return;
      state.selectedRoutesNode = name;
      const summary = state.summary || {};
      renderNodes(summary.nodes || []);
      renderRoutes(summary.routes || []);
      testNodeRoutes(name, null);
    }
    function clearRoutesNodeFilter() {
      state.selectedRoutesNode = null;
      const summary = state.summary || {};
      renderNodes(summary.nodes || []);
      renderRoutes(summary.routes || []);
    }

    function renderChecks(items) {
      const el = $('checksList');
      if (!el) return;  // Checks panel removed from the activity view (logs-only)
      el.innerHTML = items.map((item) => `<div class="item">
        <div><strong>${item.subject}</strong> <span class="status ${item.status}">${item.status}</span></div>
        <div class="mono">${item.check_uri}</div>
        <div class="subtle">${item.created_at}</div>
      </div>`).join('') || empty('No checks recorded');
    }

    function renderLogs(items) {
      const el = $('logsList');
      if (!el) return;
      const cnt = $('logCount');
      if (cnt) cnt.textContent = `${(items || []).length} entries`;
      const rows = (items || []).map((item) => `<tr>
        <td class="mono">${esc(item.created_at || '')}</td>
        <td><span class="pill">${esc(item.stream || '')}</span></td>
        <td><strong>${esc(item.event || '')}</strong></td>
        <td>${item.detail ? `<details><summary>JSON</summary><pre>${esc(JSON.stringify(item.detail, null, 2))}</pre></details>` : ''}</td>
      </tr>`).join('');
      el.innerHTML = rows
        ? `<div class="service-table-wrap"><table><thead><tr><th>Time</th><th>Stream</th><th>Event</th><th>Detail</th></tr></thead><tbody>${rows}</tbody></table></div>`
        : empty('No logs recorded');
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
      const widgetRenderer = state.dashboardWidgets && state.dashboardWidgets.renderDashboardWidget;
      $('artifactFileGrid').innerHTML = typeof widgetRenderer === 'function'
        ? widgetRenderer('artifact-grid', { items, selectedIds: [...state.selectedArtifactIds] })
        : (items.length
          ? `<div class="artifact-file-row header">
            <div></div><div>Preview</div><div>File</div><div>URI / document</div><div>Created</div>
          </div>${items.map(renderArtifactFileRow).join('')}`
          : empty('No artifacts recorded'));
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
      const artifactsListEl = $('artifactsList');  // removed from the activity view (logs-only)
      if (artifactsListEl) artifactsListEl.innerHTML = state.artifacts.map((item) => `<div class="item">
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
      if (att && att.visualPreviewUrl !== undefined) return text(att.visualPreviewUrl);
      if (att && att.previewExists === false) return '';
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
      const attachments = message.attachments || [];
      const rows = Array.isArray(message.attachments) ? attachments
        : (Array.isArray(detail.attachments) ? detail.attachments : []);
      const hasPdf = rows.some(isPdfAttachment);
      return rows.filter((att) => {
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
      const fileAvailable = att.fileExists !== false;
      const kindClass = att.kind === 'qr-code' ? ' attachment-qr' : isPdf ? ' attachment-pdf' : '';
      const visualUrl = isPdf ? attachmentVisualPreviewUrl(att) : text(att.previewUrl || '');
      const pdfUrl = isPdf && fileAvailable ? text(att.previewUrl || att.filePreviewUrl || '') : '';
      const preview = isPdf && pdfUrl
        ? `<iframe class="attachment-pdf-frame" src="${esc(pdfUrl)}" title="${esc(basename(att.path))}" loading="lazy"></iframe>`
        : (visualUrl
          ? `<img src="${esc(visualUrl)}" alt="${esc(basename(att.path))}" loading="lazy">`
          : (isPdf
            ? `<div class="attachment-pdf-preview"><span>PDF</span><small>${esc(basename(att.path))}</small></div>`
            : `<div class="subtle">preview unavailable</div>`));
      const fileUrl = fileAvailable ? text(att.previewUrl || att.filePreviewUrl || '') : '';
      const open = fileUrl
        ? `<a href="${esc(fileUrl)}" target="_blank" rel="noreferrer">open</a>`
        : '';
      const download = fileUrl ? `<a href="${esc(fileUrl)}" download>download</a>` : '';
      const missing = att.fileExists === false ? '<span class="pill down">missing file</span>' : '';
      const detailAtt = fileAvailable ? att : {...att, previewUrl: '', filePreviewUrl: ''};
      const ocrLine = ocr.ok
        ? `<div class="subtle">OCR ${esc(ocr.backend || '')}: ${esc(text(ocr.text).slice(0, 160))}</div>`
        : (ocr.error ? `<div class="subtle">OCR: ${esc(ocr.error)}</div>` : '');
      return `<div class="attachment${kindClass}">
        ${preview}
        <div class="mono">${esc(basename(att.path))}</div>
        <div class="subtle">${esc(att.kind || 'file')} ${meta.width && meta.height ? `· ${meta.width}x${meta.height}` : ''} ${missing}</div>
        <div class="artifact-actions">${open}${download}</div>
        ${ocrLine}
        <details><summary>metadata</summary><pre>${esc(JSON.stringify(detailAtt, null, 2))}</pre></details>
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
          // its own scope and hand back the renderers the dashboard can consume. The generic
          // service-view renderer is used for live widgets; dashboard widgets cover artifacts and
          // chat cards without duplicating those templates in this file.
          const factory = new Function(js + "\n;return {"
            + "renderServiceView: (typeof renderServiceView === 'function') ? renderServiceView : null,"
            + "renderDashboardWidget: (typeof renderDashboardWidget === 'function') ? renderDashboardWidget : null"
            + "};");
          const widgets = factory();
          if (widgets && typeof widgets.renderServiceView === 'function') state.widgetRender = widgets.renderServiceView;
          state.dashboardWidgets = widgets || null;
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
        if (state.dashboardWidgets && typeof state.dashboardWidgets.renderDashboardWidget === 'function') {
          renderArtifacts(state.artifacts, { force: true });
          renderChatHistory({ force: true });
        }
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
      const widgetRenderer = state.dashboardWidgets && state.dashboardWidgets.renderDashboardWidget;
      if (typeof widgetRenderer === 'function') {
        return widgetRenderer('chat-message', { message, selectedIds: [...state.selectedChatMessageIds] });
      }
      const detail = message.detail || {};
      const timeline = detail.timeline || [];
      const lines = timeline.map((step) => `${step.ok ? 'ok' : 'fail'} · ${step.target || ''} · ${step.uri}`).join('\n');
      const attachments = messageAttachments(message);
      const role = message.role || 'system';
      const selected = message.id && state.selectedChatMessageIds.has(message.id) ? 'checked' : '';
      const checkbox = message.id ? `<input type="checkbox" name="chatMessageSelect" value="${esc(message.id)}" ${selected}>` : '';
      const deleteButton = message.id ? `<button type="button" class="danger" data-chat-delete="${esc(message.id)}">Delete</button>` : '';
      const copyMarkdownButton = message.id ? `<button type="button" data-chat-copy-md="${esc(message.id)}" title="Copy message as Markdown">Copy MD</button>` : '';
      // Re-run the command: only on user messages that carry a prompt (the command text).
      const repeatButton = (message.id && role === 'user' && (message.content || '').trim())
        ? `<button type="button" data-chat-repeat="${esc(message.id)}" title="Powtorz komende">Repeat</button>` : '';
      return `<div class="message ${esc(role)}">
        <div class="message-head">
          <span class="message-title">${checkbox}<strong>${esc(role)}</strong></span>
          <span class="message-actions">
            <span class="subtle">${esc(message.created_at || '')}</span>
            ${repeatButton}
            ${copyMarkdownButton}
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

    function markdownFence(value, lang='') {
      const body = text(value).replace(/```/g, '`\u200b``');
      return '```' + (lang || '') + '\n' + body + '\n```';
    }

    function chatMessageMarkdown(message) {
      const detail = message.detail || {};
      const timeline = detail.timeline || [];
      const attachments = messageAttachments(message);
      const parts = [
        '# Chat Message',
        '',
        `- role: ${message.role || 'system'}`,
        `- created_at: ${message.created_at || ''}`,
      ];
      if (message.id) parts.push(`- id: ${message.id}`);
      parts.push('', '## Content', '', markdownFence(message.content || '', 'text'));
      if (timeline.length) {
        parts.push('', '## URI Timeline', '', markdownFence(timeline.map((step) => {
          const status = step.ok ? 'ok' : 'fail';
          const target = step.target || '';
          const uri = step.uri || '';
          const error = step.error ? ` error=${JSON.stringify(step.error)}` : '';
          return `${status} ${target} ${uri}${error}`.trim();
        }).join('\n'), 'text'));
      }
      if (attachments.length) {
        parts.push('', '## Attachments', '');
        attachments.forEach((att) => {
          parts.push(`- ${att.kind || 'file'}: ${att.path || att.uri || att.previewUrl || ''}`);
        });
        parts.push('', markdownFence(JSON.stringify(attachments, null, 2), 'json'));
      }
      if (Object.keys(detail).length) {
        parts.push('', '## URI / JSON', '', markdownFence(JSON.stringify(detail, null, 2), 'json'));
      }
      parts.push('', '## Raw Message', '', markdownFence(JSON.stringify(message, null, 2), 'json'));
      return parts.join('\n');
    }

    async function copyTextToClipboard(value) {
      let clipboardError = null;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(value);
          return 'clipboard';
        } catch (error) {
          clipboardError = error;
        }
      }
      const textarea = document.createElement('textarea');
      textarea.value = value;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.left = '0';
      textarea.style.top = '0';
      textarea.style.width = '1px';
      textarea.style.height = '1px';
      textarea.style.opacity = '0';
      const previousFocus = document.activeElement;
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      textarea.setSelectionRange(0, textarea.value.length);
      const copied = document.execCommand && document.execCommand('copy');
      textarea.remove();
      if (previousFocus && typeof previousFocus.focus === 'function') {
        try { previousFocus.focus(); } catch (error) {}
      }
      if (!copied) {
        const reason = clipboardError ? ` (${clipboardError.message || clipboardError})` : '';
        throw new Error(`clipboard copy failed${reason}`);
      }
      return 'execCommand';
    }

    async function copyVisibleChat() {
      const content = state.visibleChatMessages.map(chatMessagePlainText).join('\n\n---\n\n');
      if (!content) return;
      await copyTextToClipboard(content);
      window.__urirunLastCopiedChat = content;
      $('chatStatus').textContent = `copied ${state.visibleChatMessages.length}`;
      writeUrlState({ action: 'chat:copy', copied: state.visibleChatMessages.length }, { replace: true });
    }

    async function copyChatMessageMarkdown(id) {
      const sid = String(id || '');
      const message = state.chatMessages.find((item) => String(item.id || '') === sid)
        || state.visibleChatMessages.find((item) => String(item.id || '') === sid);
      if (!message) throw new Error(`chat message not found: ${id}`);
      const content = chatMessageMarkdown(message);
      const method = await copyTextToClipboard(content);
      window.__urirunLastCopiedChatMarkdown = content;
      $('chatStatus').textContent = `copied markdown (${method})`;
      writeUrlState({ action: 'chat:copy-message-md', copied: 1 }, { replace: true });
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

    function renderChatHistory(options={}) {
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
      if (!options.force && renderKey === state.chatRenderKey) {
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
      renderHost(summary);
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
      writeUrlState({ action: 'chat:run', prompt, prompt_len: prompt.length, nodes: nodes.join(','), targets: state.selectedTargets.join(',') });
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

    // Re-run a previous user command: resend its prompt with the same nodes/targets/execute
    // captured in the message detail (falls back to the current composer selections).
    async function repeatChatMessage(id) {
      const msg = (state.chatMessages || []).find((m) => m.id === id);
      if (!msg) return;
      const prompt = (msg.content || '').trim();
      if (!prompt) return;
      const detail = msg.detail || {};
      const nodes = detail.selectedNodes || detail.requestedNodes || selectedNodeNames();
      const targets = detail.selectedTargets || detail.requestedTargets || selectedTargets();
      const execute = detail.execute !== undefined ? !!detail.execute : $('chatExecute').checked;
      if ($('chatPrompt')) $('chatPrompt').value = prompt;
      state.view = 'chat';
      writeUrlState({ action: 'chat:repeat', prompt, prompt_len: prompt.length, nodes: (nodes || []).join(','), targets: (targets || []).join(',') });
      $('chatStatus').textContent = 'repeating...';
      try {
        const result = await api('/api/chat/ask', {
          method: 'POST',
          body: JSON.stringify({ prompt, nodes, targets, execute, no_llm: $('chatNoLlm') ? $('chatNoLlm').checked : false }),
        });
        await loadChatHistory();
        $('chatStatus').textContent = result.ok ? 'ok' : 'failed';
      } catch (error) {
        $('chatStatus').textContent = error.message;
        alert(error.message);
      }
    }

    document.addEventListener('click', (event) => {
      const discoveryButton = event.target && event.target.closest ? event.target.closest('[data-discovery-target]') : null;
      if (discoveryButton) {
        event.preventDefault();
        state.discoveryTarget = discoveryButton.dataset.discoveryTarget || 'host';
        if (state.summary) renderDiscovery(state.summary);
        writeUrlState({ action: 'discovery:select', discovery: state.discoveryTarget }, { replace: true });
        return;
      }
	      const contactButton = event.target && event.target.closest ? event.target.closest('[data-contact-action]') : null;
	      if (contactButton) {
	        event.preventDefault();
	        event.stopPropagation();
	        contactAction(contactButton).catch((error) => alert(error.message));
	        return;
	      }
      const deleteButton = event.target && event.target.closest ? event.target.closest('[data-chat-delete]') : null;
      const deleteId = deleteButton ? deleteButton.dataset.chatDelete : '';
      if (deleteId) {
	        deleteChatMessages([deleteId]).catch((error) => alert(error.message));
        return;
      }
      const copyMarkdownButton = event.target && event.target.closest ? event.target.closest('[data-chat-copy-md]') : null;
      const copyMarkdownId = copyMarkdownButton ? copyMarkdownButton.dataset.chatCopyMd : '';
      if (copyMarkdownId) {
        copyChatMessageMarkdown(copyMarkdownId).catch((error) => {
          $('chatStatus').textContent = error.message;
          alert(error.message);
        });
        return;
      }
      const repeatButton = event.target && event.target.closest ? event.target.closest('[data-chat-repeat]') : null;
      const repeatId = repeatButton ? repeatButton.dataset.chatRepeat : '';
      if (repeatId) {
        event.preventDefault();
        repeatChatMessage(repeatId).catch((error) => alert(error.message));
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
    let chatPromptUrlTimer = null;
    $('chatPrompt').addEventListener('input', () => {
      clearTimeout(chatPromptUrlTimer);
      chatPromptUrlTimer = setTimeout(() => {
        const prompt = $('chatPrompt').value.trim();
        writeUrlState({ prompt, prompt_len: prompt ? prompt.length : '' }, { replace: true });
      }, 250);
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
    target = _widget_query_value(query, "target") or _widget_query_value(query, "service") or "service:phone-scanner"
    view_id = _widget_query_value(query, "id")
    data = service_live_views(project, limit=int(_first(query, "limit", "8") or 8))
    return _select_service_view_impl(data, target=target, view_id=view_id, utc_now=_utc_now)


def _scanner_stream_summary(title: str, status: str, stream: dict) -> dict[str, str]:
    return _scanner_stream_summary_impl(title, status, stream)


def _service_widget_summary(view: dict) -> dict[str, str]:
    return _service_widget_summary_impl(view)


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


def _attachment_visual_path(meta: dict) -> str:
    return str(meta.get("displayImage") or meta.get("displayPath") or meta.get("previewImage") or meta.get("image") or "")


def _apply_attachment_file_fields(item: dict, path: str, file_preview: str | None) -> None:
    if path:
        item["fileExists"] = bool(file_preview)
        item["filePreviewUrl"] = file_preview or ""


def _apply_attachment_visual_fields(item: dict, visual_path: str, visual_preview: str | None) -> None:
    if visual_path:
        item["previewExists"] = bool(visual_preview)
        item["visualPath"] = visual_path
        item["visualPreviewUrl"] = visual_preview or ""


def _public_chat_attachment(attachment: dict, project: str) -> dict:
    """Normalize old chat attachments so the UI never embeds stale /api/file links."""
    item = dict(attachment or {})
    path = str(item.get("path") or "")
    file_preview = _preview_url(path, project) if path else None
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    visual_path = _attachment_visual_path(meta)
    visual_preview = _preview_url(visual_path, project) if visual_path else None
    _apply_attachment_file_fields(item, path, file_preview)
    _apply_attachment_visual_fields(item, visual_path, visual_preview)
    preview = str(item.get("previewUrl") or "")
    if preview.startswith("/api/file?path="):
        item["previewUrl"] = file_preview or ""
    elif not preview and file_preview:
        item["previewUrl"] = file_preview
    return item


def _public_chat_attachments(attachments: Any, project: str) -> list[dict]:
    if not isinstance(attachments, list):
        return []
    return [_public_chat_attachment(item, project) for item in attachments if isinstance(item, dict)]


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


def _merge_artifact_group(group: list[dict]) -> dict:
    """Collapse one group of same-identity artifacts to the best-ranked one, annotated with
    the ids/uris of the duplicates it absorbed."""
    if len(group) == 1:
        return group[0]
    keep = sorted(group, key=_artifact_dedupe_rank)[0].copy()
    keep_id = str(keep.get("id") or "")
    keep["duplicateCount"] = len(group)
    keep["duplicateIds"] = [str(item.get("id")) for item in group if item.get("id") and str(item.get("id")) != keep_id]
    keep["duplicateArtifactIds"] = [str(item.get("id")) for item in group if item.get("id")]
    keep["duplicateUris"] = [
        str(item.get("uri"))
        for item in group
        if item.get("uri") and str(item.get("uri")) != str(keep.get("uri") or "")
    ]
    return keep


def _dedupe_public_artifacts(public: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = {}
    order: list[tuple[str, str]] = []
    for item in public:
        key = _artifact_dedupe_key(item)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)
    return [_merge_artifact_group(groups[key]) for key in order]


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
        msg["attachments"] = _public_chat_attachments(msg.get("attachments"), project)
        if isinstance(msg.get("detail"), dict) and isinstance(msg["detail"].get("attachments"), list):
            msg["detail"] = {**msg["detail"], "attachments": _public_chat_attachments(msg["detail"].get("attachments"), project)}
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


def _ocr_text_ok(result: dict | None) -> bool:
    """True when an OCR result envelope actually carries usable (non-blank) text."""
    return bool(result and result.get("ok") and str(result.get("text") or "").strip())


def _ocr_connector_envelope(path: str, backend: str) -> tuple[dict | None, dict | None]:
    """Run the urirun-connector-ocr read. Returns ``(envelope, None)`` on a successful call,
    or ``(None, finished)`` where ``finished`` is a ready tesseract-fallback result when the
    connector is unavailable or raised."""
    try:
        from urirun_connector_ocr.core import image_text  # type: ignore
    except Exception as exc:  # noqa: BLE001
        result = _local_image_ocr_tesseract(path)
        result.setdefault("connectorError", f"urirun-connector-ocr unavailable: {exc}")
        return None, result
    try:
        envelope = image_text(image=path, backend=backend, lang="eng+pol", max_chars=20000)
    except Exception as exc:  # noqa: BLE001
        result = _local_image_ocr_tesseract(path)
        result.setdefault("connectorError", str(exc))
        return None, result
    return envelope, None


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
    envelope, finished = _ocr_connector_envelope(path, backend)
    if finished is not None:  # connector unavailable / errored — tesseract fallback already built
        return finished
    if _ocr_text_ok(envelope):
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
    if _ocr_text_ok(fallback):
        return fallback
    # Last resort: read the image with a vision LLM. Covers the case where paddle is broken
    # AND tesseract is missing/blank — the scan still yields text instead of empty metadata.
    llm = _local_image_ocr_llm(path)
    if _ocr_text_ok(llm):
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
    return os.environ.get("URIRUN_DOCUMENT_SYNC_NODE", "").strip()


def _iter_node_alias_values(value: Any) -> list[str]:
    return _iter_node_alias_values_impl(value)


def _add_node_aliases(out: dict[str, str], name: str, aliases: Any = None) -> None:
    _add_node_aliases_impl(out, name, aliases)


def _node_spec_aliases(spec: dict, fallback_name: str) -> tuple[str, list[str]]:
    return _node_spec_aliases_impl(spec, fallback_name)


def _alias_map_from_dict(value: dict) -> dict[str, str]:
    return _alias_map_from_dict_impl(value)


def _alias_map_from_list(value: Any) -> dict[str, str]:
    return _alias_map_from_list_impl(value)


def _node_alias_map_from_value(value: Any) -> dict[str, str]:
    return _node_alias_map_from_value_impl(value)


def _normalize_known_node_url(raw: Any) -> str:
    return _normalize_known_node_url_impl(raw)


def _url_map_from_dict(value: dict) -> dict[str, str]:
    return _url_map_from_dict_impl(value)


def _url_map_from_list(value: Any) -> dict[str, str]:
    return _url_map_from_list_impl(value)


def _node_url_map_from_value(value: Any) -> dict[str, str]:
    return _node_url_map_from_value_impl(value)


def _node_dicts_from_url_map(nodes: dict[str, str], *, source: str) -> list[dict]:
    return _node_dicts_from_url_map_impl(nodes, source=source)


def _node_alias_map_from_config_doc(config_doc: dict | None) -> dict[str, str]:
    return _node_alias_map_from_config_doc_impl(config_doc)


def _node_alias_map_from_env() -> dict[str, str]:
    return _node_alias_map_from_env_impl(default_node=_document_sync_default_node())


def _node_alias_map_from_node_urls(node_urls: list[str] | None) -> dict[str, str]:
    return _node_alias_map_from_node_urls_impl(node_urls)


def _known_nodes_file_data() -> Any:
    return _known_nodes_file_data_impl()


def _node_alias_map_from_known_nodes_file() -> dict[str, str]:
    return _node_alias_map_from_known_nodes_file_impl()


def _known_nodes_file_urls() -> dict[str, str]:
    return _known_nodes_file_urls_impl()


def _merge_known_nodes_into_config(config_doc: dict | None) -> dict:
    return _merge_known_nodes_into_config_impl(config_doc)


def _node_alias_map_from_context(config: str | None, node_urls: list[str] | None = None) -> dict[str, str]:
    try:
        config_doc = _host_config(config, node_urls)
    except Exception:
        config_doc = None
    return _node_alias_map_from_context_impl(
        config_doc,
        node_urls,
        default_node=_document_sync_default_node(),
    )


def _prompt_node_match(prompt: str, alias_map: dict[str, str]) -> str:
    return _prompt_node_match_impl(prompt, alias_map)


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


def _node_token_for(node: str, fallback: str | None = None) -> str | None:
    """Resolve a node's management token (X-Urirun-Token) from the keyring — set by the user via
    the dashboard Nodes view (service 'urirun-node-token', account = node name) — falling back to
    the host-wide token. Read-only on the secret store; the value is never logged or echoed."""
    name = (node or "").strip()
    if name:
        try:
            import keyring
            value = keyring.get_password("urirun-node-token", name)
            if value:
                return value
        except Exception:  # noqa: BLE001 - no keyring / no backend -> host-wide fallback
            pass
    return fallback


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


def _route_inputs_example(route: dict) -> dict:
    return _route_inputs_example_impl(route)


def _classify_route_run(envelope: Any, value: Any) -> tuple[str, str]:
    return _classify_route_run_impl(envelope, value)


def node_test_routes(project: str, db: str | None, config: str | None, payload: dict, *,
                     node_urls: list[str] | None = None, token: str | None = None,
                     identity: str | None = None) -> dict:
    return _node_test_routes_impl(
        payload,
        node_url_from_config=lambda node: _node_url_from_config(config, node_urls, node),
        node_token_for=lambda node: _node_token_for(node, token),
        node_client=_node_client,
        token=token,
        identity=identity,
    )


def _route_key(uri: str) -> tuple[str, str]:
    return _route_key_impl(uri)


def _node_has_route(routes: list[dict], uri: str) -> bool:
    return _node_has_route_impl(routes, uri)


def _fs_file_transfer_binding(uri: str) -> dict:
    return _fs_file_transfer_binding_impl(uri)


def _fs_file_transfer_fallback_bindings(required_uris: list[str]) -> dict:
    return _fs_file_transfer_fallback_bindings_impl(required_uris)


def _deploy_fs_file_transfer_fallback(client: Any, required_uris: list[str], *, timeout: float) -> dict:
    return _deploy_fs_file_transfer_fallback_impl(client, required_uris, timeout=timeout)


def _ensure_node_uri_routes(
    node_url: str,
    required_uris: list[str],
    *,
    node: str,
    token: str | None = None,
    identity: str | None = None,
    timeout: float = 120.0,
    roots: Any = None,
) -> dict:
    return _ensure_node_uri_routes_impl(
        node_url,
        required_uris,
        node=node,
        node_client=_node_client,
        token=token,
        identity=identity,
        timeout=timeout,
        roots=roots,
    )


def _short_value(value: Any, *, limit: int = 600) -> Any:
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "..."
    if isinstance(value, dict):
        return {str(k): _short_value(v, limit=limit) for k, v in value.items() if k not in {"bytes_b64", "dataUri"}}
    if isinstance(value, list):
        return [_short_value(item, limit=limit) for item in value[:20]]
    return value


def _compact_remote_run(run: dict) -> dict:
    envelope = run.get("envelope") if isinstance(run.get("envelope"), dict) else {}
    result = envelope.get("result") if isinstance(envelope.get("result"), dict) else {}
    compact = {
        "ok": bool(run.get("ok")),
        "envelopeOk": envelope.get("ok"),
    }
    if envelope.get("error"):
        compact["error"] = _short_value(envelope.get("error"))
    if result:
        compact["result"] = _short_value({
            key: result.get(key)
            for key in ("kind", "status", "ok", "error", "value", "stdout", "stderr")
            if key in result
        })
    value = run.get("value")
    if value not in ({}, None):
        compact["value"] = _short_value(value)
    return {k: v for k, v in compact.items() if v not in ({}, None, "")}


def _route_not_found_remedy(error: Any) -> str:
    """Actionable message when the remote node lacks the fs write route (its connector is
    outdated): a NOT_FOUND / "route not found" on write-b64 means urirun-connector-fs on the
    target node predates the route, so every file fails identically. Empty when not that case."""
    if not isinstance(error, dict):
        return ""
    message = str(error.get("message") or "")
    if (
        str(error.get("category") or "") == "NOT_FOUND"
        or str(error.get("type") or "").casefold() == "route"
        or "route not found" in message.lower()
    ):
        return ("remote node is missing an fs file-transfer route "
                "(fs://host/file/command/write-b64 or fs://host/file/query/read-b64) — "
                f"update urirun-connector-fs on the target node; node said: {message or error}")
    return ""


def _envelope_error_message(error: Any) -> str | None:
    """Render an error field to a message string, or None when there is no error."""
    if isinstance(error, dict):
        return str(error.get("message") or error)
    if error:
        return str(error)
    return None


def _remote_write_error(run: dict, value: Any, *, expected_sha: str, remote_sha: str | None) -> str:
    envelope = run.get("envelope") if isinstance(run.get("envelope"), dict) else {}
    # A route/transport NOT_FOUND means the call never reached the write handler, so `value` is
    # empty and "no sha256" would be misleading — surface the connector-outdated remedy first.
    remedy = _route_not_found_remedy(envelope.get("error")) or _route_not_found_remedy(
        value.get("error") if isinstance(value, dict) else None) or _route_not_found_remedy(
        value if isinstance(value, dict) else None)
    if remedy:
        return remedy
    if isinstance(value, dict):
        msg = _envelope_error_message(value.get("error"))
        if msg is not None:
            return msg
        if value.get("ok") is False:
            return "remote write returned ok=false"
        if not remote_sha:
            return "remote write returned no sha256"
        if remote_sha != expected_sha:
            return f"sha256 mismatch: expected {expected_sha}, got {remote_sha}"
    msg = _envelope_error_message(envelope.get("error"))
    if msg is not None:
        return msg
    if value:
        return f"remote write returned non-object result: {_short_value(value)!r}"
    return "remote write failed without a result"


def _remote_read_error(run: dict, value: Any, *, expected_sha: str, remote_sha: str | None) -> str:
    remedy = _route_not_found_remedy(value if isinstance(value, dict) else None)
    if remedy:
        return remedy
    if isinstance(value, dict):
        msg = _envelope_error_message(value.get("error"))
        if msg is not None:
            return msg
        if value.get("ok") is False:
            return "remote read returned ok=false"
        if not remote_sha:
            return "remote read returned no sha256"
        if remote_sha != expected_sha:
            return f"read-back sha256 mismatch: expected {expected_sha}, got {remote_sha}"
    envelope = run.get("envelope") if isinstance(run.get("envelope"), dict) else {}
    msg = _envelope_error_message(envelope.get("error"))
    if msg is not None:
        return msg
    if value:
        return f"remote read returned non-object result: {_short_value(value)!r}"
    return "remote read failed without a result"


def _document_sync_verification(
    files: list[Path],
    results: list[dict],
    *,
    source_root: Path,
    read_back: bool,
) -> dict:
    return _document_sync_verification_impl(files, results, source_root=source_root, read_back=read_back)


def _document_archive_pdfs(root: Path) -> list[Path]:
    return _document_archive_pdfs_impl(root)


def _document_sync_deps() -> DocumentSyncDeps:
    return DocumentSyncDeps(
        document_archive_root=_document_archive_root,
        default_node=_document_sync_default_node,
        default_dest_root=_document_sync_default_dest_root,
        node_url_from_config=_node_url_from_config,
        archive_pdfs=_document_archive_pdfs,
        verification=lambda files, results, source_root, read_back: _document_sync_verification(
            files,
            results,
            source_root=source_root,
            read_back=read_back,
        ),
        ensure_node_uri_routes=_ensure_node_uri_routes,
        run_node_uri=_run_node_uri,
        compact_remote_run=_compact_remote_run,
        remote_write_error=_remote_write_error,
        remote_read_error=_remote_read_error,
        utc_now=_utc_now,
        host_db=_host_db,
        chat_message=_chat_message,
        add_chat_message=_add_chat_message,
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
    # Use the per-node management token (set via the dashboard Nodes view, stored in keyring) when
    # present, so node:// route provisioning on the target is authorized; else the host-wide token.
    node_name = str((payload or {}).get("node") or (payload or {}).get("targetNode") or "").strip()
    token = _node_token_for(node_name, token)
    return _sync_documents_to_node_impl(
        project,
        db,
        config,
        payload,
        deps=_document_sync_deps(),
        node_urls=node_urls,
        token=token,
        identity=identity,
    )


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


def _scanned_log_entry(item: dict) -> dict:
    """Build a scanned-id-log entry from an existing document-index record."""
    pdf_path = str(item.get("pdfPath") or item.get("path") or "")
    return {
        "version": 1,
        "event": "indexed",
        "scannedAt": item.get("createdAt") or _utc_now(),
        "docId": str(item.get("docId") or "").strip(),
        "docIdProvider": item.get("docIdProvider"),
        "docIdSource": item.get("docIdSource"),
        "duplicate": False,
        "uri": item.get("uri"),
        "pdfPath": pdf_path,
        "jsonPath": item.get("jsonPath"),
        "fileName": Path(pdf_path).name if pdf_path else "",
        "originalPath": item.get("originalPath"),
        "cropPath": item.get("cropPath"),
        "sourceSha256": str(item.get("sourceSha256") or "").strip(),
        "textSha256": str(item.get("textSha256") or "").strip(),
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


def _scanned_entry_seen(entry: dict, seen: dict[str, set[str]]) -> bool:
    """True when any of the entry's identity keys is already in the seen-bucket of that key."""
    return any(entry[key] and entry[key] in bucket for key, bucket in seen.items())


def _scanned_seen_buckets(existing: list[dict]) -> dict[str, set[str]]:
    """Index the existing scanned-id log by each identity key for O(1) duplicate checks."""
    return {
        "docId": {str(i.get("docId") or "") for i in existing if i.get("docId")},
        "sourceSha256": {str(i.get("sourceSha256") or "") for i in existing if i.get("sourceSha256")},
        "textSha256": {str(i.get("textSha256") or "") for i in existing if i.get("textSha256")},
    }


def _backfill_scanned_id_log(index: dict) -> None:
    docs = [item for item in index.get("documents", []) if isinstance(item, dict)]
    if not docs:
        return
    seen = _scanned_seen_buckets(_iter_scanned_id_log())
    for item in docs:
        entry = _scanned_log_entry(item)
        if _scanned_entry_seen(entry, seen):
            continue
        _append_scanned_id_log(entry)
        for key, bucket in seen.items():
            if entry[key]:
                bucket.add(entry[key])


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
    res = _llm_complete_metadata(model, key_ref, text, use_vision=use_vision, image_path=image_path)
    data = _parse_llm_json_object(res)
    if data is None:
        return None
    return _normalize_llm_doc_fields(data, model=model, use_vision=use_vision)


def _llm_complete_metadata(model: str, key_ref: str | None, text: str, *,
                           use_vision: bool, image_path: str | None) -> dict | None:
    """Call the LLM connector (vision or text mode) and return its raw response envelope.

    The API key travels as a reference (getv:// or secret://dotenv/...) and is resolved inside
    the llm connector under a deny-by-default allow-list — never via os.environ here."""
    try:
        from urirun_connector_llm.core import complete  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    if use_vision:
        prompt = "Przeanalizuj zdjęcie polskiego paragonu lub faktury i wyciągnij dane. " + _LLM_FIELDS_SPEC
        if text:
            prompt += "\nPomocniczy tekst z OCR (może zawierać błędy, zweryfikuj ze zdjęciem):\n" + text[:3000]
        try:
            return complete(prompt, model=model, image=str(image_path), api_key=key_ref, secret_allow=key_ref)
        except Exception:  # noqa: BLE001
            return None
    prompt = (
        "Jesteś ekstraktorem danych z polskich paragonów i faktur. Poniżej tekst z OCR "
        "(zachowana kolejność linii). " + _LLM_FIELDS_SPEC
        + "\nTEKST OCR:\n" + text[:6000]
    )
    try:
        return complete(prompt, model=model, api_key=key_ref, secret_allow=key_ref)
    except Exception:  # noqa: BLE001
        return None


def _parse_llm_json_object(res: Any) -> dict | None:
    """Pull the JSON object out of an LLM completion envelope (strips ```json fences)."""
    if not isinstance(res, dict) or not res.get("ok"):
        return None
    raw = str(res.get("response") or "").strip()
    if not raw:
        return None
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
    return data if isinstance(data, dict) else None


def _normalize_llm_doc_fields(data: dict, *, model: str, use_vision: bool) -> dict:
    """Coerce/validate the LLM's raw fields into the canonical document-metadata shape."""
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
        try:
            from urirun_connector_smart_crop import orient_document_image

            image, _orientation = orient_document_image(image, auto_orient=True, prefer_portrait=True)
        except Exception:  # noqa: BLE001 - PDF generation must not fail when smart-crop is unavailable
            pass
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


def _draw_crop_box(draw: Any, canvas: Any, color: tuple, box: Any, scale: float,
                   original_width: int, original_height: int) -> None:
    """Draw the detected crop rectangle (4-pt box scaled to canvas), or a full-frame border."""
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


def _draw_overlay_label(draw: Any, canvas: Any, crop: dict, quality: dict | None, ok: bool) -> None:
    """Draw the crop status/score caption with a contrasting background box."""
    from PIL import ImageFont

    score = (quality or {}).get("score")
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


def _scanner_crop_overlay(original_path: str | Path, crop: dict, quality: dict | None = None) -> dict:
    """Write a diagnostic image with the detected crop box drawn over the raw frame."""
    try:
        from PIL import Image, ImageDraw, ImageOps

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
        _draw_crop_box(draw, canvas, color, box, scale, original_width, original_height)
        _draw_overlay_label(draw, canvas, crop, quality, ok)
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


def _staging_keep_paths() -> set[str]:
    """Resolved paths that pruning must never remove: files of an archived document and of any
    active (not-yet-finished) best-frame series. Best-effort; a read failure just keeps less."""
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
    return keep


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

    keep = _staging_keep_paths()
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


def _artifact_schema_known(type_id: str) -> bool | None:
    """Whether ``type_id`` matches a registered urirun-artifacts schema id.

    Bridges the file-artifact's document ``type`` (e.g. ``paragon``/``faktura``) to the
    urirun-artifacts schema registry WITHOUT making it a hard dependency: returns ``None``
    when the registry is not installed (validation skipped), else ``True``/``False``.
    """
    normalized = str(type_id or "").strip().lower()
    if not normalized:
        return None
    try:
        import urirun_artifacts  # noqa: F401  (import registers the models)
        from urirun_artifacts import registry
        known = {str(i).strip().lower() for i in registry.all_ids()}
    except Exception:  # noqa: BLE001
        return None
    return normalized in known


def _document_schema_fields(doc_type: str) -> dict:
    """The schema-registry annotation written onto an archived document entry.

    ``schemaKnown`` is True/False when the urirun-artifacts registry is installed and the
    document ``type`` is/isn't a registered schema, or None when the registry is absent.
    ``schemaId`` carries the matched schema id only when known.
    """
    known = _artifact_schema_known(doc_type)
    return {
        "schemaKnown": known,
        "schemaId": str(doc_type or "").strip().lower() if known else None,
    }


def _archive_redundant_duplicate(*, duplicate: dict, index_match: dict | None, existing_meta: dict,
                                 extracted: dict, new_completeness: float, index: dict,
                                 docid_info: dict, doc_id: str, original_path: Path, display_path: Path,
                                 source_sha256: str, text_sha256: str,
                                 fingerprint: Any, dhash: Any, phash: Any) -> dict:
    """The new scan matches an already-archived document and is NOT more complete: enrich the
    kept record with any newly-read fields, drop the redundant staged files, log a duplicate
    event, and return the duplicate result. Called with _DOCUMENT_INDEX_LOCK held."""
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


def _supersede_archived_document(*, duplicate: dict, existing_meta: dict, extracted: dict,
                                 new_completeness: float, root: Path, month: str, doc_id: str,
                                 index: dict) -> tuple:
    """Supersede an archived document with a better scan: fuse best-of-both metadata, recompute
    the destination from the (possibly richer) fields, delete the old files, and drop the old
    index entry. Returns the updated (extracted, month, archive_dir, filename, superseded_of,
    merged_fields). Called with _DOCUMENT_INDEX_LOCK held."""
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
    return extracted, month, archive_dir, filename, superseded_of, merged_fields


def _archive_month(extracted: dict) -> str:
    """The YYYY-MM archive bucket from the document's date, or the current month."""
    if re.match(r"^20\d{2}-\d{2}", str(extracted.get("date", ""))):
        return str(extracted["date"])[:7]
    return time.strftime("%Y-%m", time.gmtime())


def _existing_document_meta(duplicate: dict) -> dict:
    """The duplicate record's metadata dict, or a flat projection of its top-level fields."""
    if isinstance(duplicate.get("metadata"), dict):
        return duplicate["metadata"]
    return {key: duplicate.get(key) for key in ("type", "date", "contractor", "amount", "currency")}


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
    month = _archive_month(extracted)
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
            existing_meta = _existing_document_meta(duplicate)
            # Supersede only an already-archived document (index_match), and only when the
            # new scan reads strictly more complete metadata (e.g. amount known vs unknown).
            can_supersede = index_match is not None and new_completeness > _metadata_completeness(existing_meta)
            if not can_supersede:
                return _archive_redundant_duplicate(
                    duplicate=duplicate, index_match=index_match, existing_meta=existing_meta,
                    extracted=extracted, new_completeness=new_completeness, index=index,
                    docid_info=docid_info, doc_id=doc_id, original_path=original_path,
                    display_path=display_path, source_sha256=source_sha256, text_sha256=text_sha256,
                    fingerprint=fingerprint, dhash=dhash, phash=phash,
                )
            extracted, month, archive_dir, filename, superseded_of, merged_fields = _supersede_archived_document(
                duplicate=duplicate, existing_meta=existing_meta, extracted=extracted,
                new_completeness=new_completeness, root=root, month=month, doc_id=doc_id, index=index,
            )

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
        _schema_fields = _document_schema_fields(extracted.get("type"))
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
            # Bridge to the urirun-artifacts schema registry: annotate whether the document
            # type is a known schema (None when the registry isn't installed). Non-fatal.
            "schemaKnown": _schema_fields["schemaKnown"],
            "schemaId": _schema_fields["schemaId"],
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


def _crop_dimensions(crop: dict) -> tuple[int, int]:
    return (
        int(crop.get("width") or crop.get("cropWidth") or 0),
        int(crop.get("height") or crop.get("cropHeight") or 0),
    )


def _crop_geometry_score(crop: dict, reasons: list[str]) -> float:
    score = 0.0
    width, height = _crop_dimensions(crop)
    if min(width, height) >= 220 and max(width, height) >= 420:
        score += 12.0
        reasons.append("size")
    orientation = crop.get("orientation") if isinstance(crop.get("orientation"), dict) else {}
    if orientation.get("enabled") and int(orientation.get("height") or height) >= int(orientation.get("width") or width):
        score += 5.0
        reasons.append("portrait")
    return score


def _crop_quality_score(crop: dict, reasons: list[str]) -> float:
    if not crop.get("ok"):
        if crop.get("partialEdge"):
            reasons.append("partial-edge")
        elif crop.get("reason"):
            reasons.append("crop-rejected")
        return -20.0
    score = 42.0
    reasons.append("crop")
    bbox_area = float(crop.get("bboxArea") or 0.0)
    if bbox_area:
        score += 18.0 * _bounded(1.0 - abs(bbox_area - 0.42) / 0.42)
    score += _crop_geometry_score(crop, reasons)
    return score


def _doctype_quality_score(doc_type: str, reasons: list[str]) -> float:
    if doc_type in {"paragon", "faktura"}:
        reasons.append(doc_type)
        return 32.0
    if doc_type in {"rachunek", "potwierdzenie"}:
        reasons.append(doc_type)
        return 20.0
    if doc_type != "dokument":
        return 10.0
    return 0.0


def _metadata_quality_score(metadata: dict, reasons: list[str]) -> float:
    score = 0.0
    if metadata.get("date"):
        score += 8.0
        reasons.append("date")
    if metadata.get("amount"):
        score += 10.0
        reasons.append("amount")
    return score


def _ocr_quality_score(ocr: dict, chars: int, reasons: list[str]) -> float:
    if ocr.get("ok") and chars:
        reasons.append("ocr")
        return min(36.0, chars / 4.0)
    return 0.0


def _visual_quality_score(visual: dict, reasons: list[str]) -> float:
    if not visual.get("ok"):
        return 0.0
    reasons.append("visual")
    return (
        18.0 * float(visual.get("sharpnessScore") or 0.0)
        + 10.0 * float(visual.get("contrastScore") or 0.0)
        + 7.0 * float(visual.get("brightnessScore") or 0.0)
    )


def _document_frame_quality(crop: dict, ocr: dict, metadata: dict, display_path: str | Path) -> dict:
    visual = _frame_visual_metrics(display_path)
    reasons: list[str] = []
    doc_type = str(metadata.get("type") or "dokument")
    chars = int(ocr.get("chars") or len(str(ocr.get("text") or "")))
    score = (
        _crop_quality_score(crop, reasons)
        + _doctype_quality_score(doc_type, reasons)
        + _metadata_quality_score(metadata, reasons)
        + _ocr_quality_score(ocr, chars, reasons)
        + _visual_quality_score(visual, reasons)
    )
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


def _scanner_status_from_log(item: dict) -> tuple[dict, str, dict] | None:
    return _scanner_status_from_log_impl(item)


def _latest_scanner_page_status(db: str | None) -> dict:
    try:
        logs = _host_db().recent_logs(db, stream="page-action", limit=80)
    except Exception:  # noqa: BLE001
        return {}
    return _latest_scanner_page_status_impl(logs)


def _scanner_artifact_doc_meta(artifact: dict) -> dict:
    return _scanner_artifact_doc_meta_impl(artifact)


def _is_scanner_artifact(kind: str, uri: str, meta: dict) -> bool:
    return _is_scanner_artifact_impl(kind, uri, meta)


def _scanner_artifact_item(artifact: dict, kind: str, uri: str, path: str,
                           display_path: str, doc: dict, project: str) -> dict:
    return _scanner_artifact_item_impl(
        artifact,
        kind,
        uri,
        path,
        display_path,
        doc,
        project,
        preview_url=_preview_url,
    )


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
        if not _is_scanner_artifact(kind, uri, meta):
            continue
        path = str(artifact.get("path") or "")
        display_path = str(meta.get("displayImage") or meta.get("displayPath") or path)
        if not _artifact_file_exists(path) and not _artifact_file_exists(display_path):
            continue
        doc = _scanner_artifact_doc_meta(artifact)
        out.append(_scanner_artifact_item(artifact, kind, uri, path, display_path, doc, project))
        if len(out) >= max(1, int(limit or 6)):
            break
    return out


def service_live_views(project: str, db: str | None = None, limit: int = 8) -> dict:
    scanner = scanner_live_state(project, limit=limit)
    service = next((item for item in _service_contacts() if item.get("id") == "service:phone-scanner"), {})
    recent_artifacts = _recent_scanner_artifacts(db, project, limit=6)
    camera_status = _latest_scanner_page_status(db)
    return _scanner_service_live_views_impl(
        scanner,
        service,
        recent_artifacts,
        camera_status,
        utc_now=_utc_now,
    )


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


def _scanner_bridge_deps() -> ScannerBridgeDeps:
    return ScannerBridgeDeps(
        preview_url=_preview_url,
        register_artifact=lambda db, kind, uri, path, meta: _host_db().register_artifact(
            db, kind, uri, path, meta
        ),
        chat_message=_chat_message,
        add_chat_message=_add_chat_message,
        add_log=lambda db, stream, event, detail: _host_db().add_log(db, stream, event, detail),
    )


def _crop_overlay_attachment(uri: str, project: str, overlay_path: str, crop: dict,
                             meta: dict, original_path: Path) -> dict:
    return _crop_overlay_attachment_impl(
        _scanner_bridge_deps(),
        uri=uri,
        project=project,
        overlay_path=overlay_path,
        crop=crop,
        meta=meta,
        original_path=original_path,
    )


def _register_document_artifact(db: str | None, project: str, *, uri: str, display_path: Path,
                                original_path: Path, meta: dict, ocr: dict, document: dict) -> tuple[Any, dict]:
    return _register_document_artifact_impl(
        _scanner_bridge_deps(),
        db,
        project,
        uri=uri,
        display_path=display_path,
        original_path=original_path,
        meta=meta,
        ocr=ocr,
        document=document,
    )


def _scanner_result_content(content_prefix: str, crop: dict, document: dict, ocr: dict) -> str:
    return _scanner_result_content_impl(content_prefix, crop, document, ocr)


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
    return _register_scanner_result_impl(
        _scanner_bridge_deps(),
        project,
        db,
        uri=uri,
        display_path=display_path,
        original_path=original_path,
        meta=meta,
        crop=crop,
        ocr=ocr,
        document=document,
        content_prefix=content_prefix,
    )


def _orientation_summary(crop: dict) -> dict:
    """Compact orientation facts for the capture response / UI: which signal decided the
    rotation (``paddle-doc-orientation`` | ``osd`` | ``geometry``) and the applied PIL angle
    (0 = the scan was already upright)."""
    o = crop.get("orientation") if isinstance(crop, dict) and isinstance(crop.get("orientation"), dict) else {}
    source = o.get("source")
    if not source and o.get("enabled"):
        source = "osd" if (o.get("osd") or {}).get("appliedAngle") is not None else "geometry"
    return {
        "source": source,
        "angle": int(o.get("angle") or 0),
        "rotated": bool(o.get("rotated")),
        "score": o.get("score"),
    }


def _decode_capture_image(raw_image: str) -> tuple[str, bytes, str, str]:
    """Parse a ``data:image/*;base64`` payload into (mime, raw_bytes, sha256, file_ext)."""
    match = re.match(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", raw_image, re.S)
    if not match:
        raise ValueError("image must be a data:image/*;base64 payload")
    mime, encoded = match.group(1), match.group(2)
    raw = base64.b64decode(encoded.encode("ascii"), validate=False)
    digest = hashlib.sha256(raw).hexdigest()
    ext = ".jpg" if mime in {"image/jpeg", "image/jpg"} else ".png" if mime == "image/png" else ".bin"
    return mime, raw, digest, ext


def _capture_quality_ok(payload: dict, quality: dict, min_score: float) -> bool:
    """A capture passes the document gate when forced, or scored >= min and document-like."""
    return bool(payload.get("force")) or (
        float(quality.get("score") or 0.0) >= min_score and bool(quality.get("documentLike"))
    )


def _capture_reject_result(*, uri: str, min_score: float, quality: dict, ocr: dict, crop: dict,
                           overlay: dict, detected_document: dict, paths: list) -> dict:
    """Clean up a low-confidence capture's staged files and build the rejection response."""
    removed_scan_files = _cleanup_duplicate_scan_files(paths)
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


def _capture_candidate_result(project: str, payload: dict, *, uri: str, mime: str, digest: str,
                              raw_len: int, path: Path, display_path: Path, overlay_path: str,
                              overlay: dict, crop: dict, ocr: dict, detected_document: dict,
                              quality: dict) -> dict:
    """Stage a transient best-frame candidate (no archive) and return the live-stream response."""
    candidate = {
        "seriesId": str(payload.get("seriesId") or ""),
        "frameIndex": payload.get("frameIndex"),
        "uri": uri,
        "mime": mime,
        "sha256": digest,
        "bytes": raw_len,
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


def _capture_display_path(crop: dict, path: Path) -> Path:
    """The cropped image when the auto-crop succeeded, else the original frame."""
    return Path(crop["path"]) if crop.get("ok") and crop.get("path") else path


def _capture_ocr_and_detect(path: Path, display_path: Path, payload: dict, archive: bool) -> tuple[dict, dict]:
    """OCR the frame and extract document metadata for a capture.

    OCRs the full original frame, not the crop: PaddleOCR handles the background and the crop
    tended to cut the header/footer (losing seller name / "Do zapłaty" total). The crop is kept
    only as the display thumbnail. Set URIRUN_SCANNER_OCR_FULLFRAME=0 to OCR the crop (legacy).
    Transient candidates (archive=False) use the cheap tesseract read + regex path; only a kept
    document pays for the full backend and the optional LLM/vision metadata pass."""
    ocr_source = path if _truthy_env("URIRUN_SCANNER_OCR_FULLFRAME", "1") else display_path
    ocr = _local_image_ocr(str(ocr_source), backend=None if archive else "tesseract")
    detected_document = _extract_document_metadata(
        str(ocr.get("text") or ""),
        captured_at=payload.get("capturedAt"),
        image_path=str(path) if archive else None,
        use_llm=archive,
    )
    return ocr, detected_document


def scanner_capture(project: str, db: str | None, payload: dict) -> dict:
    _prune_scanner_staging()
    mode = str(payload.get("mode") or "").lower()
    archive = not (payload.get("archive") is False or mode in {"candidate", "best-candidate", "analyze", "analysis"})
    mime, raw, digest, ext = _decode_capture_image(str(payload.get("image") or ""))
    root = _scanner_staging_dir()
    root.mkdir(parents=True, exist_ok=True)
    name = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-phone-scan-{digest[:12]}{ext}"
    path = root / name
    path.write_bytes(raw)
    crop = _auto_crop_receipt(path)
    display_path = _capture_display_path(crop, path)
    ocr, detected_document = _capture_ocr_and_detect(path, display_path, payload, archive)
    quality = _document_frame_quality(crop, ocr, detected_document, display_path)
    overlay = _scanner_crop_overlay(path, crop, quality)
    overlay_path = str(overlay.get("path") or "") if overlay.get("ok") else ""
    uri = f"scanner://host/capture/{digest[:16]}"
    document = {"ok": False, "reason": "analysis-only", "metadata": detected_document}
    # Reject low-confidence single captures (blurry/partial/non-document frames) instead of
    # archiving and showing them. Mirrors the best-frame gate so the manual "Scan" button no
    # longer fills the archive with mis-scanned receipts. Pass force=true to override.
    min_score = float(os.environ.get("URIRUN_PHONE_SCANNER_MIN_SCORE", "45"))
    if archive and not _capture_quality_ok(payload, quality, min_score):
        return _capture_reject_result(
            uri=uri, min_score=min_score, quality=quality, ocr=ocr, crop=crop, overlay=overlay,
            detected_document=detected_document, paths=[path, display_path, overlay_path],
        )
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
    if not archive:
        return _capture_candidate_result(
            project, payload, uri=uri, mime=mime, digest=digest, raw_len=len(raw), path=path,
            display_path=display_path, overlay_path=overlay_path, overlay=overlay, crop=crop,
            ocr=ocr, detected_document=detected_document, quality=quality,
        )
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
        "orientation": _orientation_summary(crop),
        "quality": quality,
        "overlay": overlay,
        "document": document,
        "message": registered["message"],
    }


def _best_series_not_found(series_id: str) -> dict:
    """Record a 'series not found' live-stream entry and return its failure response."""
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


def _resolve_best_candidate(series: dict) -> dict | None:
    """The series' recorded best frame, or the highest-scoring candidate, or None."""
    best = series.get("best")
    if isinstance(best, dict):
        return best
    candidates = [item for item in series.get("candidates", []) if isinstance(item, dict)]
    if not candidates:
        return None
    return max(candidates, key=lambda item: float((item.get("quality") or {}).get("score") or 0.0))


def _best_quality_rejected(payload: dict, quality: dict) -> tuple[bool, float]:
    """Return (rejected, min_score). rejected is True when below threshold and force is not set."""
    min_score = float(payload.get("minScore") if payload.get("minScore") is not None else 45.0)
    rejected = not payload.get("force") and (
        float(quality.get("score") or 0.0) < min_score or not quality.get("documentLike")
    )
    return rejected, min_score


def _best_candidate_paths(best: dict) -> tuple[Path, Path]:
    return (
        Path(str(best.get("originalPath") or "")).expanduser().resolve(),
        Path(str(best.get("displayPath") or "")).expanduser().resolve(),
    )


def _best_finish_store_failure(series_id: str, series: dict, *, status: str, error: str,
                               best: dict | None = None, project: str = "",
                               extra: dict | None = None) -> dict:
    """Record a rejected/failed best-finish in the live stream and build its response dict."""
    with _SCANNER_BEST_LOCK:
        if best is not None:
            series["best"] = best
        _scanner_live_store_locked(series_id, series, status=status, error=error)
    result = {"ok": False, "error": error, "seriesId": series_id}
    if best is not None:
        result["best"] = _scanner_public_candidate_for_live(best, project)
    if extra:
        result.update(extra)
    return result


def _refresh_best_ocr(fallback_ocr: dict, original_path: Path, display_path: Path) -> dict:
    """Re-OCR the kept frame with the accurate full backend, falling back to the cheap read."""
    ocr_source = original_path if _truthy_env("URIRUN_SCANNER_OCR_FULLFRAME", "1") else display_path
    refreshed = _local_image_ocr(str(ocr_source))
    if refreshed.get("ok") and str(refreshed.get("text") or "").strip():
        return refreshed
    return fallback_ocr


def _ensure_best_overlay(best: dict, crop: dict, quality: dict, original_path: Path) -> tuple[dict, str]:
    """Reuse the candidate's crop overlay if its file still exists, else render a fresh one."""
    overlay = best.get("overlay") if isinstance(best.get("overlay"), dict) else {}
    overlay_path = str(best.get("overlayPath") or overlay.get("path") or "")
    if not overlay_path or not Path(overlay_path).expanduser().is_file():
        overlay = _scanner_crop_overlay(original_path, crop, quality)
        overlay_path = str(overlay.get("path") or "") if overlay.get("ok") else ""
        best["overlay"] = overlay
        best["overlayPath"] = overlay_path
    return overlay, overlay_path


def _store_best_finish(series: dict, series_id: str, best: dict, document: dict, registered: dict) -> None:
    """Persist the accepted/failed best-finish outcome to the live stream under the lock."""
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


def _best_crop_and_ocr(best: dict) -> tuple[dict, dict]:
    crop = best.get("crop") if isinstance(best.get("crop"), dict) else {}
    ocr = best.get("ocr") if isinstance(best.get("ocr"), dict) else {}
    return crop, ocr


def scanner_best_finish(project: str, db: str | None, payload: dict) -> dict:
    _prune_scanner_staging()
    series_id = str(payload.get("seriesId") or "").strip()
    if not series_id:
        raise ValueError("seriesId is required")
    series = _scanner_best_take(series_id, clear=payload.get("clear", True) is not False)
    if not series:
        return _best_series_not_found(series_id)
    best = _resolve_best_candidate(series)
    if not isinstance(best, dict):
        return _best_finish_store_failure(series_id, series, status="failed",
                                          error="scanner best series has no candidates")
    quality = best.get("quality") if isinstance(best.get("quality"), dict) else {}
    quality_rejected, min_score = _best_quality_rejected(payload, quality)
    if quality_rejected:
        return _best_finish_store_failure(
            series_id, series, status="rejected",
            error="no reliable receipt or invoice candidate found",
            best=best, project=project, extra={"minScore": min_score},
        )
    original_path, display_path = _best_candidate_paths(best)
    if not original_path.is_file() or not display_path.is_file():
        return _best_finish_store_failure(series_id, series, status="failed",
                                          error="best candidate file is missing",
                                          best=best, project=project)
    crop, ocr = _best_crop_and_ocr(best)
    # Candidates were scored with the cheap OCR backend; pay for the accurate full read
    # (paddle full-frame) once, on the single frame we are about to keep. Falls back to the
    # candidate's OCR if the re-read fails.
    ocr = _refresh_best_ocr(ocr, original_path, display_path)
    digest = str(best.get("sha256") or _file_sha256(original_path))
    detected_document = best.get("detectedDocument") or {}
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
        document = {"ok": False, "error": str(exc), "metadata": detected_document}
    uri = str(best.get("uri") or f"scanner://host/capture/{digest[:16]}")
    overlay, overlay_path = _ensure_best_overlay(best, crop, quality, original_path)
    meta = {
        "source": "phone-best",
        "seriesId": series_id,
        "frameIndex": best.get("frameIndex"),
        "candidateCount": len(series.get("candidates", [])),
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
        "detectedDocument": detected_document,
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
    _store_best_finish(series, series_id, best, document, registered)
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
        "detectedDocument": detected_document,
        "orientation": _orientation_summary(crop),
        "quality": quality,
        "overlay": overlay,
        "document": document,
        "message": registered["message"],
    }


def scanner_session(db: str | None, payload: dict) -> dict:
    return _scanner_session_impl(_scanner_bridge_deps(), db, payload)


def uri_event(db: str | None, query: dict[str, list[str]]) -> dict:
    return _uri_event_impl(_scanner_bridge_deps(), db, query)


def page_action_enqueue(
    db: str | None,
    *,
    target: str,
    uri: str,
    payload: dict | None = None,
    mode: str = "execute",
    source: str = "host",
) -> dict:
    return _page_action_enqueue_impl(
        _scanner_bridge_deps(),
        db,
        target=target,
        uri=uri,
        payload=payload,
        mode=mode,
        source=source,
        uri_mode=_uri_mode,
        utc_now=_utc_now,
    )


def page_action_poll(target: str = "scanner", limit: int = 4) -> dict:
    return _page_action_poll_impl(target, limit)


def page_action_result(db: str | None, payload: dict) -> dict:
    return _page_action_result_impl(_scanner_bridge_deps(), db, payload, utc_now=_utc_now)


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
        {
            "uri": "urifix://host/chain/command/repair",
            "layer": "connector",
            "kind": "command",
            "label": "Diagnose and repair a failed URI decision chain",
            "sideEffects": ["optional-retry"],
            "where": "host dashboard /api/uri/invoke via urirun-connector-urifix",
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
    return _service_restart_argv_impl(
        payload,
        service=service,
        env_prefix=env_prefix,
        default_unit=default_unit,
    )


def _schedule_restart_command(argv: list[str], payload: dict, meta: dict) -> dict:
    return _schedule_restart_command_impl(argv, payload, meta)


def _chat_service_restart_argv(
    project: str,
    db: str | None,
    config: str | None,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    payload: dict,
) -> tuple[list[str] | None, dict]:
    return _chat_service_restart_argv_impl(project, db, config, node_urls, token, identity, payload)


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
    return _restart_chat_service_impl(
        payload,
        project=project,
        db=db,
        config=config,
        node_urls=node_urls,
        token=token,
        identity=identity,
    )


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


def _result_artifact_class(value: Any) -> str | None:
    """Classify a connector result via the shared ``urirun.tag`` contract.

    Returns ``"widget"`` for a live view (``live=True``), ``"artifact"`` for a frozen
    output (``live=False``), or ``None`` when the result is untagged (no ``live`` key) so
    the host falls back to its own taxonomy. This is how the host *consumes* the contract:
    a live view is routed to the chat-stream (never the frozen artifact store) and a frozen
    output to the artifact catalogue, by the connector's own declaration rather than a guess.
    """
    if not isinstance(value, dict) or "live" not in value:
        return None
    return "widget" if value.get("live") else "artifact"


def register_tagged_artifact(db: str | None, *, uri: str, result: Any, meta: dict | None = None) -> dict | None:
    """Route a tagged connector result per the shared ``urirun.tag`` contract.

    * frozen **artifact** (``live=False``) pointing at an on-disk ``path`` -> cataloged in
      the artifact store under its connector-declared ``kind``;
    * live **widget** (``live=True``) -> never stored (it is a self-updating view);
    * untagged result -> left alone (the host's own taxonomy decides elsewhere).

    Returns the registered artifact row, or ``None`` when nothing was stored. Best-effort:
    never raises, so a catalog hiccup cannot fail the connector call.
    """
    if _result_artifact_class(result) != "artifact":
        return None
    path = str((result or {}).get("path") or "")
    if not path or not Path(path).expanduser().is_file():
        return None
    kind = str(result.get("kind") or "artifact")
    try:
        return _host_db().register_artifact(db, kind, uri, path, meta or {})
    except Exception:  # noqa: BLE001
        return None


def _run_inprocess_connector_uri(uri: str, action_payload: dict, db: str | None = None) -> dict | None:
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
    # Route by the tag contract: a frozen artifact with a path gets cataloged under its
    # declared kind; a live widget never does. No-op for today's in-process traffic
    # (widget://, artifact:// registry/schema queries are untagged), correct for any
    # connector that returns a frozen file artifact over this path.
    registered = register_tagged_artifact(db, uri=uri, result=value) if db else None
    return {"ok": bool(env.get("ok")), "invokedUri": uri,
            "result": value if value is not None else env.get("result"),
            "artifactClass": _result_artifact_class(value),
            "registeredArtifact": registered,
            "error": (env.get("error") or {}).get("message") if not env.get("ok") else None}


def _uri_invoke_route(effective_uri: str, *, project: str, db: str | None, config: str | None,
                      action_payload: dict, node_urls: list[str] | None, token: str | None,
                      identity: str | None):
    """Route a concrete (execute-mode, non-page) dashboard/scanner URI to its handler.

    Returns the handler's result, or None when the URI is not a built-in dashboard action (the
    caller then tries an in-process connector)."""
    if effective_uri in {"scanner://host/capture/command/run", "scanner://host/capture"}:
        return scanner_capture(project, db, action_payload)
    if effective_uri in {"scanner://host/best/command/finish", "scanner://host/best/finish"}:
        return scanner_best_finish(project, db, action_payload)
    if effective_uri in {"scanner://host/session/command/log", "scanner://host/session"}:
        return scanner_session(db, action_payload)
    if effective_uri == "dashboard://host/phone-scanner/command/start":
        return ensure_phone_scanner_service(
            project,
            db,
            config,
            node_urls=node_urls,
            token=token,
            identity=identity,
        )
    if effective_uri == "dashboard://host/service/phone-scanner/command/restart":
        return restart_phone_scanner_service(
            project,
            db,
            config,
            node_urls=node_urls,
            token=token,
            identity=identity,
            payload=action_payload,
        )
    if effective_uri == "dashboard://host/service/chat/command/restart":
        return restart_chat_service(
            action_payload,
            project=project,
            db=db,
            config=config,
            node_urls=node_urls,
            token=token,
            identity=identity,
        )
    if effective_uri in {"document://host/archive/command/sync-to-node", "document://host/archive/sync"}:
        return sync_documents_to_node(
            project,
            db,
            config,
            action_payload,
            node_urls=node_urls,
            token=token,
            identity=identity,
        )
    return None


def _uri_invoke_page_action(uri: str, mode: str, payload: dict, action_payload: dict, db: str | None) -> dict:
    """Enqueue a `layer=page` URI action for the scanner page (or reject if it must run locally)."""
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


def _finalize_uri_result(result, uri: str) -> dict:
    """Annotate a handler result with invokedUri and the urirun.tag artifact class."""
    if isinstance(result, dict):
        result.setdefault("invokedUri", uri)
        # Surface the artifact/widget class when the result carries the urirun.tag contract.
        tag_class = _result_artifact_class(result)
        if tag_class is not None:
            result.setdefault("artifactClass", tag_class)
        return result
    return {"ok": True, "invokedUri": uri, "result": result}


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
        return _uri_invoke_page_action(uri, mode, payload, action_payload, db)

    result = _uri_invoke_route(
        effective_uri, project=project, db=db, config=config, action_payload=action_payload,
        node_urls=node_urls, token=token, identity=identity,
    )
    if result is None:
        # Not a hardcoded dashboard/scanner action: try an installed in-process connector
        # (widget://, artifact://, …) over the urirun runtime before giving up.
        dispatched = _run_inprocess_connector_uri(effective_uri, action_payload, db=db)
        if dispatched is not None:
            return dispatched
        raise ValueError(f"unsupported URI action: {uri}")

    return _finalize_uri_result(result, uri)


def _first(query: dict[str, list[str]], name: str, default: str | None = None) -> str | None:
    return _widget_query_value(query, name, default)


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
    return _host_config_impl(_mesh(), config, node_urls)


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
    service_entries: list[dict] = []
    with _SERVICE_LOCK:
        for service_id, server in _SERVICE_SERVERS.items():
            thread = _SERVICE_THREADS.get(service_id)
            service_entries.append({
                "service_id": service_id,
                "alive": bool(thread is not None and thread.is_alive()),
                "server_name": getattr(server, "server_name", ""),
            })
    return _service_contacts_impl(
        scanner_port=scanner_port,
        scanner_state=scanner_state,
        service_entries=service_entries,
        phone_scanner_url=_phone_scanner_url,
        phone_scanner_status=_phone_scanner_external_status,
    )


def _host_registry_routes() -> list[dict]:
    return _host_registry_routes_impl(_uri_action_catalog())


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
    _annotate_node_tokens_impl(nodes, _node_token_for)
    routes = discovered.get("routes") or []
    services = _service_contacts()
    host_routes = _host_registry_routes()
    host = _host_object_impl(project, host_routes)
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
        "host": host,
        "hostRoutes": host_routes,
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


_DOCUMENT_SYNC_URI = "document://host/archive/command/sync-to-node"


def node_add(config: str | None, payload: dict) -> dict:
    """Persist a node (name + URL) to the host config so the host resolves it for real runs, and
    mirror it to ~/.urirun/nodes.json so urifix can auto-repair node_url. Reuses the canonical
    node/config.add_node helper (same path as `urirun host add-node`) — no bespoke writer."""
    from urirun.node import config as node_config
    payload = payload if isinstance(payload, dict) else {}
    name = str(payload.get("name") or "").strip()
    raw_url = str(payload.get("url") or "").strip()
    if not name or not raw_url:
        return {"ok": False, "error": "name and url are required"}
    try:
        url = node_config._coerce_node_url(raw_url)  # accepts URL or host[:port], defaults :8765
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        updated = node_config.add_node(config, name, url)
    except Exception as exc:  # noqa: BLE001 - report a persist failure, don't 500 the dashboard
        return {"ok": False, "error": f"could not persist node: {exc}"}
    try:  # best-effort mirror for urifix's node-URL discovery
        nodes_path = os.environ.get("URIRUN_NODES_FILE") or os.path.expanduser("~/.urirun/nodes.json")
        known: dict = {}
        if os.path.exists(nodes_path):
            with open(nodes_path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                inner = loaded.get("nodes")
                known = inner if isinstance(inner, dict) else loaded
        known[name] = url
        os.makedirs(os.path.dirname(nodes_path) or ".", exist_ok=True)
        with open(nodes_path, "w", encoding="utf-8") as fh:
            json.dump(known, fh, indent=2)
    except Exception:  # noqa: BLE001 - the urifix mirror is optional
        pass
    return {"ok": True, "node": {"name": name, "url": url}, "nodes": updated.get("nodes", [])}


def node_set_token(config: str | None, payload: dict) -> dict:
    """Store a node's management token (X-Urirun-Token) the user typed in the Nodes view — into the
    OS keyring (the system's secret store), never plaintext. Records only a non-secret reference
    (`secret://keyring/urirun-node-token/<name>`) on the node config so the run path knows a token
    exists. The token value is never persisted in config, returned, or logged."""
    payload = payload if isinstance(payload, dict) else {}
    name = str(payload.get("name") or "").strip()
    secret = str(payload.get("token") or "")
    if not name or not secret:
        return {"ok": False, "error": "name and token are required"}
    try:
        import keyring
        keyring.set_password("urirun-node-token", name, secret)
    except Exception as exc:  # noqa: BLE001 - never fall back to plaintext
        return {"ok": False, "error": f"could not store token securely (keyring): {exc}. "
                                      f"Install keyring or set X-Urirun-Token via host env instead."}
    token_ref = f"secret://keyring/urirun-node-token/{name}"
    try:  # mark a non-secret reference on the node so the UI/run path know a token is set
        from urirun.node import config as node_config
        cfg = node_config.load_host_config(config)
        for node in cfg.get("nodes", []):
            if isinstance(node, dict) and node.get("name") == name:
                node["tokenRef"] = token_ref
                node.pop("token", None)  # defensive: never keep a plaintext token in config
                node_config.save_host_config(cfg, config)
                break
    except Exception:  # noqa: BLE001 - the marker is best-effort; the keyring store is authoritative
        pass
    return {"ok": True, "name": name, "stored": "keyring", "tokenRef": token_ref}


def _try_urifix_repair(prompt: str, request: dict, result: dict, *, node_urls: list[str] | None = None,
                       host_config: dict | None = None, known_nodes: list[str] | dict | None = None,
                       apply: bool = False, registry: Any = None) -> dict | None:
    """Diagnose (and, when apply=True + a registry are given, resolve) a failed URI chain via the
    urifix connector. `known_nodes` lets urifix resolve a missing node URL from the host's known
    set; urifix also reads ~/.urirun/nodes.json on its own. apply is left False here: callers that
    want automatic recovery must validate the returned retry contract before doing side effects."""
    try:
        from urirun_connector_urifix.core import repair_chain  # type: ignore
    except Exception:  # noqa: BLE001 - urifix is optional.
        return None
    kwargs: dict[str, Any] = {
        "prompt": prompt,
        "request": request,
        "result": result,
        "node_urls": node_urls or [],
        "host_config": host_config or {},
    }
    # Forward the newer args only when supported, so the host stays compatible with an older urifix.
    import inspect
    params = inspect.signature(repair_chain).parameters
    if "known_nodes" in params and known_nodes is not None:
        kwargs["known_nodes"] = known_nodes
    if "apply" in params and apply:
        kwargs["apply"] = True
    if "registry" in params and registry is not None:
        kwargs["registry"] = registry
    try:
        fixed = repair_chain(**kwargs)
    except Exception as exc:  # noqa: BLE001 - never mask the original URI failure.
        return {"ok": False, "error": str(exc)}
    return fixed if isinstance(fixed, dict) else None


def _boolish(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() not in {"", "0", "false", "no", "off"}


def _document_sync_auto_retry_enabled(payload: dict) -> bool:
    for key in ("autoRetry", "auto_retry", "autoRepair", "auto_repair"):
        if key in payload:
            return _boolish(payload.get(key), default=True)
    return _truthy_env("URIRUN_DOCUMENT_SYNC_AUTO_RETRY", "1")


def _urifix_auto_retry(urifix: dict) -> bool:
    """True when a urifix diagnosis authorizes an automatic retry."""
    diagnosis = urifix.get("diagnosis") if isinstance(urifix.get("diagnosis"), dict) else {}
    if urifix.get("repaired") or diagnosis.get("canAutoRetry"):
        return True
    return any(bool(item.get("automatic")) for item in (urifix.get("recovery") or []) if isinstance(item, dict))


def _validated_sync_retry_payload(retry: dict, sync_node: str) -> dict | None:
    """Validate a urifix `retry` block targets this document-sync node, returning its payload."""
    if str(retry.get("uri") or "") != _DOCUMENT_SYNC_URI:
        return None
    if str(retry.get("mode") or "").casefold() != "execute":
        return None
    retry_payload = retry.get("payload")
    if not isinstance(retry_payload, dict):
        return None
    node_url = str(retry_payload.get("node_url") or retry_payload.get("nodeUrl") or "").strip()
    if not node_url:
        return None
    retry_node = str(retry_payload.get("node") or retry_payload.get("targetNode") or sync_node).strip()
    if sync_node and retry_node and retry_node != sync_node:
        return None
    return dict(retry_payload)


def _document_sync_retry_payload_from_urifix(urifix: dict | None, *, sync_node: str) -> dict | None:
    if not isinstance(urifix, dict):
        return None
    if not _urifix_auto_retry(urifix):
        return None
    retry = urifix.get("retry")
    if not isinstance(retry, dict):
        return None
    return _validated_sync_retry_payload(retry, sync_node)


def _needs_screen_document_capture(prompt: str) -> bool:
    text_value = prompt.casefold()
    wants_screen = any(word in text_value for word in ("zrzut", "screenshot", "screen capture", "zrzuty ekranu"))
    wants_document = any(word in text_value for word in ("pdf", "dokument", "document", "faktur", "rachunek", "paragon"))
    return wants_screen and wants_document


def _is_document_sync_prompt(prompt: str, selected_nodes: list[str] | None = None,
                             selected_targets: list[str] | None = None, config: str | None = None,
                             node_urls: list[str] | None = None) -> bool:
    text_value = prompt.casefold()
    wants_transfer = any(word in text_value for word in (
        "wyślij", "wyslij", "prześlij", "przeslij", "skopiuj", "kopiuj",
        "przenieś", "przenies", "sync", "synchroniz",
    ))
    wants_documents = any(word in text_value for word in (
        "artifact", "artefakt", "documents", "dokument", "pdf",
        "faktur", "rachunek", "paragon", "scan", "skan",
    ))
    alias_map = _node_alias_map_from_context(config, node_urls)
    target_nodes = _selected_nodes_from_targets(selected_nodes or [], selected_targets or [])
    wants_node = bool(
        target_nodes
        or _document_sync_default_node()
        or _prompt_node_match(prompt, alias_map)
        or re.search(r"(?<![\w.-])node(?![\w.-])", text_value)
    )
    return wants_transfer and wants_documents and wants_node


def _document_sync_node_from_prompt(prompt: str, selected_nodes: list[str],
                                    selected_targets: list[str] | None = None,
                                    config: str | None = None, node_urls: list[str] | None = None) -> str:
    if selected_nodes:
        return selected_nodes[0]
    target_nodes = _selected_nodes_from_targets([], selected_targets or [])
    if target_nodes:
        return target_nodes[0]
    matched = _prompt_node_match(prompt, _node_alias_map_from_context(config, node_urls))
    if matched:
        return matched
    return _document_sync_default_node()


def _document_sync_dest_from_prompt(prompt: str) -> str:
    text_value = prompt.casefold()
    if "download" in text_value or "pobrane" in text_value:
        return os.environ.get("URIRUN_DOCUMENT_SYNC_DEST", "~/Downloads/urirun-scans")
    return _document_sync_default_dest_root()


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


def _selected_nodes_from_targets(selected_nodes: list[str], selected_targets: list[str]) -> list[str]:
    """Keep API callers and the browser form consistent: node targets imply selected nodes."""
    out: list[str] = []
    seen: set[str] = set()
    for node in selected_nodes:
        clean = str(node).strip()
        if clean and clean not in seen:
            out.append(clean)
            seen.add(clean)
    for target in selected_targets:
        clean = str(target).strip()
        if not clean.startswith("node:"):
            continue
        node = clean.split(":", 1)[1].strip()
        if node and node not in seen:
            out.append(node)
            seen.add(node)
    return out


def _decision_loop_status(execute: bool, error: dict | None, retry_available: bool) -> str:
    if execute and not error:
        return "done"
    if error:
        return "retryable" if retry_available else "blocked"
    return "dry-run"


def _decision_loop_next_intent(*, error: dict | None, execute: bool, recovery: list, urifix: dict | None,
                               retry_available: bool, can_auto_execute_retry: bool,
                               auto_retry_enabled: bool, retry_attempted: bool) -> dict | None:
    """The next-action proposal for a document-sync decision loop (repair on error, execute on dry-run)."""
    if error:
        return {
            "id": "repair-uri-chain",
            "uri": "urifix://host/chain/command/repair",
            "automatic": can_auto_execute_retry,
            "status": "ready" if retry_available else "needs-input",
            "actions": recovery,
            "retry": (urifix or {}).get("retry"),
            "policy": {
                "autoRetry": auto_retry_enabled,
                "retryAttempted": retry_attempted,
            },
        }
    if not execute:
        return {
            "id": "execute-document-sync",
            "uri": "document://host/archive/command/sync-to-node",
            "automatic": False,
            "status": "awaiting-execute",
        }
    return None


def _decision_loop_observation(*, error: dict | None, execute: bool, recovered: bool,
                               initial_error: dict | None) -> dict:
    """The observation record (outcome kind + error context) for a document-sync decision loop."""
    kind = (
        "uri-step-failed" if error
        else ("dry-run" if not execute else ("uri-flow-recovered" if recovered else "uri-flow-complete"))
    )
    observation = {
        "kind": kind,
        "failedStep": "sync-documents-to-node" if error or recovered else None,
        "error": error,
    }
    if recovered:
        observation["initialError"] = initial_error
        observation["recoveredBy"] = "urifix://host/chain/command/repair"
    return observation


def _decision_loop_for_document_sync(prompt: str, *, execute: bool, sync_node: str, selected_nodes: list[str],
                                     selected_targets: list[str], flow: dict, timeline: list[dict],
                                     error: dict | None = None, urifix: dict | None = None,
                                     sync_result: dict | None = None, initial_error: dict | None = None,
                                     recovered: bool = False, retry_attempted: bool = False,
                                     auto_retry_enabled: bool = True) -> dict:
    recovery = (urifix or {}).get("recovery") or []
    diagnosis = (urifix or {}).get("diagnosis") or {}
    if not isinstance(diagnosis, dict):
        diagnosis = {}
    can_auto_retry = bool(diagnosis.get("canAutoRetry") or (urifix or {}).get("repaired"))
    retry_available = can_auto_retry and not retry_attempted
    can_auto_execute_retry = retry_available and auto_retry_enabled
    status = _decision_loop_status(execute, error, retry_available)
    next_intent = _decision_loop_next_intent(
        error=error, execute=execute, recovery=recovery, urifix=urifix,
        retry_available=retry_available, can_auto_execute_retry=can_auto_execute_retry,
        auto_retry_enabled=auto_retry_enabled, retry_attempted=retry_attempted,
    )
    return {
        "schema": "urirun.decision-loop.v1",
        "intent": {
            "id": "document-sync",
            "source": "host.document-archive",
            "target": f"node:{sync_node}",
            "prompt": prompt,
            "selectedNodes": selected_nodes,
            "selectedTargets": selected_targets,
        },
        "flow": flow,
        "execution": {
            "status": status,
            "execute": execute,
            "timeline": timeline,
            "results": {"sync-documents-to-node": sync_result} if sync_result else {},
        },
        "observation": _decision_loop_observation(
            error=error, execute=execute, recovered=recovered, initial_error=initial_error,
        ),
        "nextIntent": next_intent,
    }


def _scanner_flow_result(
    service: dict,
    autonomous_scan: bool,
    camera_action_uri: str,
    camera_payload: dict,
    torch_click_uri: str,
    torch_enabled: bool | None,
    queued_camera: dict | None,
    queued_torch: dict | None,
    prompt: str,
    selected_nodes: list[str],
    selected_targets: list[str],
) -> dict:
    """Build the response dict for the phone-scanner chat path."""
    return {
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


def _chat_ask_phone_scanner(
    project: str,
    db: str | None,
    config: str | None,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    prompt: str,
    execute: bool,
    selected_nodes: list[str],
    selected_targets: list[str],
) -> dict:
    """Handle phone-scanner chat requests (start scanner, queue camera/torch actions)."""
    service = ensure_phone_scanner_service(
        project, db, config=config, node_urls=node_urls, token=token, identity=identity,
    )
    queued_camera: dict | None = None
    queued_torch: dict | None = None
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
            db, target="scanner", uri=camera_action_uri, payload=camera_payload,
            mode="execute", source="chat",
        )
        _add_chat_message(db, _chat_message(
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
        ))
    if torch_enabled is not None:
        queued_torch = page_action_enqueue(
            db, target="scanner", uri=torch_click_uri,
            payload={"target": "scanner", "enabled": bool(torch_enabled)},
            mode="execute", source="chat",
        )
        _add_chat_message(db, _chat_message(
            "system",
            f"Camera light {'on' if torch_enabled else 'off'} queued for the open scanner page.",
            detail={
                "uri": torch_click_uri,
                "selectedTargets": ["service:phone-scanner"],
                "enabled": bool(torch_enabled),
                "queued": queued_torch,
                "scannerUrl": service.get("url"),
            },
        ))
    result = _scanner_flow_result(
        service, autonomous_scan, camera_action_uri, camera_payload,
        torch_click_uri, torch_enabled, queued_camera, queued_torch,
        prompt, selected_nodes, selected_targets,
    )
    try:
        _host_db().add_log(db, "chat", "ask", {
            "prompt": prompt,
            "execute": True,
            "ok": result.get("ok"),
            "selectedNodes": selected_nodes,
            "selectedTargets": selected_targets,
            "generator": result.get("generator"),
            "timeline": result.get("timeline") or [],
        })
    except Exception:
        pass
    return result


def _sync_execute_initial(
    project: str,
    db: str | None,
    config: str | None,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    sync_payload: dict,
) -> tuple[dict | None, dict | None]:
    """Run the first sync attempt. Returns (sync_result, error)."""
    try:
        sync_result = sync_documents_to_node(
            project, db, config, sync_payload, node_urls=node_urls, token=token, identity=identity,
        )
    except Exception as exc:  # noqa: BLE001
        return None, {"type": type(exc).__name__, "message": str(exc), "uri": _DOCUMENT_SYNC_URI}
    if sync_result is not None and not sync_result.get("ok"):
        failed_reasons = sync_result.get("failedReasons") if isinstance(sync_result.get("failedReasons"), dict) else {}
        top_reason = max(failed_reasons.items(), key=lambda item: item[1])[0] if failed_reasons else "document sync contract failed"
        return sync_result, {
            "type": "ContractError",
            "message": str(top_reason),
            "uri": _DOCUMENT_SYNC_URI,
            "verification": sync_result.get("verification"),
        }
    return sync_result, None


def _sync_ok_and_status(sync_result: dict | None, error: dict | None, execute: bool) -> tuple[bool, str]:
    """Compute (ok, timeline_status) for the document-sync path."""
    ok = bool((sync_result or {}).get("ok")) if execute and not error else not bool(error)
    status = "done" if execute and ok else ("failed" if error else "dry-run")
    return ok, status


def _apply_urifix_recovery(
    result: dict,
    timeline: list[dict],
    *,
    project: str,
    db: str | None,
    config: str | None,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    prompt: str,
    execute: bool,
    no_llm: bool,
    payload: dict,
    sync_node: str,
    selected_nodes: list[str],
    selected_targets: list[str],
    error: dict,
    sync_result: dict | None,
) -> tuple[dict | None, dict | None, dict | None, bool, bool]:
    """Diagnose the failed sync with urifix and, if possible, auto-retry.

    Mutates result and timeline in place. Returns (urifix, final_error, initial_error, recovered, retry_attempted).
    Single source of truth is decisionLoop (built by caller from urifix); raw urifix stays in
    result only for the DB debug log — not promoted to recovery/patch/retry copies in chat.
    """
    initial_error = dict(error)
    host_config_snapshot = None
    try:
        host_config_snapshot = _host_config(config, node_urls)
    except Exception:  # noqa: BLE001
        pass
    urifix = _try_urifix_repair(
        prompt,
        {"nodes": selected_nodes, "targets": selected_targets, "execute": execute, "no_llm": no_llm},
        result,
        node_urls=node_urls,
        host_config=host_config_snapshot,
    )
    if not urifix:
        return None, error, initial_error, False, False
    result["urifix"] = urifix
    timeline[0]["recoverable"] = bool(urifix.get("recovery"))
    retry_payload = (
        _document_sync_retry_payload_from_urifix(urifix, sync_node=sync_node)
        if execute and _document_sync_auto_retry_enabled(payload) else None
    )
    if not retry_payload:
        return urifix, error, initial_error, False, False
    retry_step = {
        "id": "sync-documents-to-node.retry",
        "uri": _DOCUMENT_SYNC_URI,
        "target": retry_payload.get("node") or sync_node,
        "ok": False,
        "status": "failed",
        "recoveredFrom": "sync-documents-to-node",
        "generatedBy": "urifix://host/chain/command/repair",
    }
    recovered = False
    try:
        retry_result = sync_documents_to_node(
            project, db, config, retry_payload, node_urls=node_urls, token=token, identity=identity,
        )
        retry_ok = bool(retry_result.get("ok"))
        sync_result = retry_result
        retry_step["ok"] = retry_ok
        retry_step["status"] = "done" if retry_ok else "failed"
        if retry_ok:
            recovered = True
            error = None
            result["initialError"] = initial_error
            result["recovered"] = True
            result["recoveredBy"] = "urifix://host/chain/command/repair"
        else:
            error = {
                "type": "RecoveryError",
                "message": "document sync retry returned ok=false",
                "uri": _DOCUMENT_SYNC_URI,
                "initialError": initial_error,
            }
    except Exception as exc:  # noqa: BLE001
        error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "uri": _DOCUMENT_SYNC_URI,
            "initialError": initial_error,
        }
    timeline.append(retry_step)
    ok = bool((sync_result or {}).get("ok")) if execute and not error else False
    result["ok"] = ok
    result["timeline"] = timeline
    result["results"] = {"sync-documents-to-node": sync_result} if sync_result else {}
    result["error"] = error
    return urifix, error, initial_error, recovered, True


def _chat_ask_document_sync(
    project: str,
    db: str | None,
    config: str | None,
    payload: dict,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    prompt: str,
    execute: bool,
    no_llm: bool,
    selected_nodes: list[str],
    selected_targets: list[str],
) -> dict:
    """Handle document-sync chat requests."""
    sync_node = _document_sync_node_from_prompt(prompt, selected_nodes, selected_targets, config, node_urls)
    sync_selected_nodes = _selected_nodes_from_targets([*selected_nodes, sync_node], selected_targets)
    sync_selected_targets = list(selected_targets)
    node_target = f"node:{sync_node}"
    if node_target not in sync_selected_targets:
        sync_selected_targets.append(node_target)
    sync_payload = {"node": sync_node, "dest_root": _document_sync_dest_from_prompt(prompt)}
    step = {
        "id": "sync-documents-to-node",
        "uri": "document://host/archive/command/sync-to-node",
        "payload": sync_payload,
        "depends_on": [],
    }
    flow = {
        "task": {"id": "document-sync-to-node", "title": "Copy archived document PDFs to URI node"},
        "steps": [step],
    }
    generator = {"provider": "host-dashboard", "intent": "document-sync", "fallback": True}
    sync_result: dict | None = None
    error: dict | None = None
    initial_error: dict | None = None
    recovered = False
    retry_attempted = False
    if execute:
        sync_result, error = _sync_execute_initial(project, db, config, node_urls, token, identity, sync_payload)
    ok, status = _sync_ok_and_status(sync_result, error, execute)
    timeline: list[dict] = [{
        "id": "sync-documents-to-node",
        "uri": _DOCUMENT_SYNC_URI,
        "target": sync_node,
        "ok": ok,
        "status": status,
    }]
    result: dict = {
        "ok": ok,
        "prompt": prompt,
        "execute": execute,
        "selectedNodes": sync_selected_nodes,
        "selectedTargets": sync_selected_targets,
        "generator": generator,
        "flow": flow,
        "timeline": timeline,
        "results": {"sync-documents-to-node": sync_result} if sync_result else {},
        "error": error,
    }
    if error:
        _, error, initial_error, recovered, retry_attempted = _apply_urifix_recovery(
            result,
            timeline,
            project=project,
            db=db,
            config=config,
            node_urls=node_urls,
            token=token,
            identity=identity,
            prompt=prompt,
            execute=execute,
            no_llm=no_llm,
            payload=payload,
            sync_node=sync_node,
            selected_nodes=selected_nodes,
            selected_targets=selected_targets,
            error=error,
            sync_result=sync_result,
        )
    result["decisionLoop"] = _decision_loop_for_document_sync(
        prompt,
        execute=execute,
        sync_node=sync_node,
        selected_nodes=sync_selected_nodes,
        selected_targets=sync_selected_targets,
        flow=flow,
        timeline=result.get("timeline") or timeline,
        error=error,
        urifix=result.get("urifix"),
        sync_result=(result.get("results") or {}).get("sync-documents-to-node"),
        initial_error=initial_error,
        recovered=recovered,
        retry_attempted=retry_attempted,
        auto_retry_enabled=_document_sync_auto_retry_enabled(payload),
    )
    if recovered:
        _add_chat_message(db, _chat_message(
            "system",
            "recovered: document sync URI step",
            detail={
                "schema": "urirun.decision-loop.v1",
                "ok": result.get("ok"),
                "decisionLoop": result.get("decisionLoop"),
            },
        ))
    elif not execute or error:
        _add_chat_message(db, _chat_message(
            "system",
            ("failed: document sync URI step" if error else "dry-run: document sync URI step"),
            # The decision-loop object is self-contained (intent → flow → execution →
            # observation → nextIntent), so the chat message carries just it (+ ok) instead
            # of the former duplicated recovery/patch/retry/urifix/flow/timeline copies.
            detail={
                "schema": "urirun.decision-loop.v1",
                "ok": result.get("ok"),
                "decisionLoop": result.get("decisionLoop"),
            },
        ))
    try:
        _host_db().add_log(db, "chat", "ask", {
            "prompt": prompt,
            "execute": execute,
            "ok": result.get("ok"),
            "selectedNodes": sync_selected_nodes,
            "selectedTargets": sync_selected_targets,
            "decisionLoop": result.get("decisionLoop"),
            "urifix": result.get("urifix"),
        })
    except Exception:
        pass
    return result


def _chat_ask_general_planner_failure(
    exc: BaseException,
    db: str | None,
    prompt: str,
    execute: bool,
    selected_nodes: list[str],
    selected_targets: list[str],
) -> dict:
    """Build a planner-recovery result and emit chat/DB log when make_flow raises."""
    from urirun.node.recovery import planner_failure  # noqa: PLC0415

    result = planner_failure(exc, prompt=prompt, selected_nodes=selected_nodes, selected_targets=selected_targets)
    result["execute"] = execute
    result["generator"] = {
        "provider": "host-dashboard",
        "intent": "planner-recovery",
        "fallback": True,
        "reason": str(exc),
    }
    _add_chat_message(db, _chat_message(
        "system",
        f"failed: planner error ({(result.get('error') or {}).get('category') or 'UNKNOWN'}); recovery available",
        detail={
            "prompt": prompt,
            "execute": execute,
            "ok": False,
            "selectedTargets": selected_targets,
            "generator": result["generator"],
            "flow": result.get("flow") or {},
            "timeline": result.get("timeline") or [],
            "results": {},
            "error": result.get("error"),
            "recovery": result.get("recovery") or [],
        },
    ))
    try:
        _host_db().add_log(db, "chat", "ask", {
            "prompt": prompt,
            "execute": execute,
            "ok": False,
            "selectedNodes": selected_nodes,
            "selectedTargets": selected_targets,
            "generator": result["generator"],
            "timeline": result.get("timeline") or [],
            "error": result.get("error"),
            "recovery": result.get("recovery") or [],
        })
    except Exception:  # noqa: BLE001
        pass
    return result


def _general_path_complete(
    result: dict,
    db: str | None,
    prompt: str,
    execute: bool,
    selected_nodes: list[str],
    selected_targets: list[str],
    generator: dict,
    flow: dict,
    attachments: list,
) -> None:
    """Emit the chat message and DB log for the completed general mesh path."""
    timeline = result.get("timeline") or []
    status = "ok" if result.get("ok") else "failed"
    content = f"{status}: {len(timeline)} URI step(s)"
    if result.get("recovery"):
        content += f", {len(result.get('recovery') or [])} recovery action(s)"
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
            "recovery": result.get("recovery") or [],
        },
        attachments=attachments,
    ))
    try:
        _host_db().add_log(db, "chat", "ask", {
            "prompt": prompt,
            "execute": execute,
            "ok": result.get("ok"),
            "selectedNodes": selected_nodes,
            "selectedTargets": selected_targets,
            "generator": generator,
            "timeline": result.get("timeline") or [],
            "recovery": result.get("recovery") or [],
        })
    except Exception:  # noqa: BLE001
        pass


def _chat_ask_general(
    project: str,
    db: str | None,
    config: str | None,
    payload: dict,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    prompt: str,
    execute: bool,
    no_llm: bool,
    selected_nodes: list[str],
    selected_targets: list[str],
) -> dict:
    """Handle general LLM-to-URI mesh chat requests."""
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
                _host_db().add_log(db, "chat", "ask", {
                    "prompt": prompt,
                    "execute": execute,
                    "ok": False,
                    "selectedNodes": selected_nodes,
                    "selectedTargets": selected_targets,
                    "generator": result["generator"],
                    "timeline": [],
                    "error": capability_gap,
                })
            except Exception:  # noqa: BLE001
                pass
            return result
        try:
            flow, generator = mesh.make_flow(prompt, discovered, selected_nodes=selected_nodes, use_llm=not no_llm)
        except Exception as exc:  # noqa: BLE001 - return a recovery contract instead of a raw API failure.
            return _chat_ask_general_planner_failure(exc, db, prompt, execute, selected_nodes, selected_targets)
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
    _general_path_complete(result, db, prompt, execute, selected_nodes, selected_targets, generator, flow, attachments)
    return result


def _chat_phone_scanner_response(project: str, db: str | None, config: str | None, payload: dict, *, prompt: str,
        selected_nodes: list, selected_targets: list, execute: bool, no_llm: bool,
        node_urls: list[str] | None, token: str | None, identity: str | None) -> dict:
    """Handle a phone-scanner chat prompt: start the service, queue camera/torch page
    actions, and return the chat result. (Extracted from chat_ask.)"""
    return _chat_ask_phone_scanner(
        project, db, config, node_urls, token, identity, prompt, execute, selected_nodes, selected_targets,
    )


def _chat_document_sync_response(project: str, db: str | None, config: str | None, payload: dict, *, prompt: str,
        selected_nodes: list, selected_targets: list, execute: bool, no_llm: bool,
        node_urls: list[str] | None, token: str | None, identity: str | None) -> dict:
    """Handle a document-sync chat prompt: run sync-to-node with urifix recovery/retry and
    a decision-loop record. (Extracted from chat_ask.)"""
    return _chat_ask_document_sync(
        project, db, config, payload, node_urls, token, identity,
        prompt, execute, no_llm, selected_nodes, selected_targets,
    )


def _chat_generic_response(project: str, db: str | None, config: str | None, payload: dict, *, prompt: str,
        selected_nodes: list, selected_targets: list, execute: bool, no_llm: bool,
        node_urls: list[str] | None, token: str | None, identity: str | None) -> dict:
    """Handle a generic chat prompt: discover the mesh, plan a flow, execute it, and return
    the compacted result. (Extracted from chat_ask.)"""
    return _chat_ask_general(
        project, db, config, payload, node_urls, token, identity,
        prompt, execute, no_llm, selected_nodes, selected_targets,
    )


def _add_chat_user_message(db: str | None, prompt: str, config: str | None, node_urls: list[str] | None,
                           *, execute: bool, no_llm: bool, requested_nodes: list, requested_targets: list,
                           selected_nodes: list, selected_targets: list) -> None:
    """Record the user's chat turn, previewing the resolved document-sync target when detected."""
    user_selected_nodes = list(selected_nodes)
    user_selected_targets = list(selected_targets)
    user_intent = None
    if _is_document_sync_prompt(prompt, selected_nodes, selected_targets, config, node_urls):
        preview_node = _document_sync_node_from_prompt(prompt, selected_nodes, selected_targets, config, node_urls)
        preview_target = f"node:{preview_node}"
        user_selected_targets = list(selected_targets)
        if preview_target not in user_selected_targets:
            user_selected_targets.append(preview_target)
        user_selected_nodes = _selected_nodes_from_targets([*selected_nodes, preview_node], user_selected_targets)
        user_intent = {
            "id": "document-sync",
            "source": "prompt",
            "target": preview_target,
            "confidence": "deterministic",
        }
    _add_chat_message(db, _chat_message(
        "user",
        prompt,
        detail={
            "execute": execute,
            "noLlm": no_llm,
            "requestedNodes": requested_nodes,
            "requestedTargets": requested_targets,
            "selectedNodes": user_selected_nodes,
            "selectedTargets": user_selected_targets,
            "resolvedNodes": user_selected_nodes,
            "resolvedTargets": user_selected_targets,
            **({"intent": user_intent} if user_intent else {}),
        },
    ))


def chat_ask(project: str, db: str | None, config: str | None, payload: dict, node_urls: list[str] | None = None,
             token: str | None = None, identity: str | None = None) -> dict:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    requested_nodes = [str(item).strip() for item in (payload.get("nodes") or []) if str(item).strip()]
    requested_targets = [str(item).strip() for item in (payload.get("targets") or []) if str(item).strip()]
    selected_nodes = list(requested_nodes)
    selected_targets = list(requested_targets)
    if not selected_targets:
        selected_targets = ["host", *[f"node:{name}" for name in selected_nodes]]
    selected_nodes = _selected_nodes_from_targets(selected_nodes, selected_targets)
    execute = bool(payload.get("execute"))
    no_llm = bool(payload.get("no_llm") or payload.get("noLlm"))
    _add_chat_user_message(
        db, prompt, config, node_urls, execute=execute, no_llm=no_llm,
        requested_nodes=requested_nodes, requested_targets=requested_targets,
        selected_nodes=selected_nodes, selected_targets=selected_targets,
    )
    _dispatch = dict(
        project=project, db=db, config=config, payload=payload, prompt=prompt,
        selected_nodes=selected_nodes, selected_targets=selected_targets,
        execute=execute, no_llm=no_llm, node_urls=node_urls, token=token, identity=identity,
    )
    if _is_phone_scanner_prompt(prompt):
        return _chat_phone_scanner_response(**_dispatch)
    if _is_document_sync_prompt(prompt, selected_nodes, selected_targets, config, node_urls):
        return _chat_document_sync_response(**_dispatch)
    return _chat_generic_response(**_dispatch)



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


def _delete_one_artifact_file(artifact_path: str, role: str, project: str) -> dict:
    """Delete one artifact file (if inside an allowed root) and return its delete-info record."""
    info = {"path": artifact_path, "role": role, "deleted": False, "skipped": False, "error": ""}
    if not _artifact_file_delete_allowed(artifact_path, project):
        info["skipped"] = True
        info["error"] = "path is outside allowed artifact roots"
        return info
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
    return info


def _delete_artifact_files(artifacts: list, project: str) -> list[dict]:
    """Delete the on-disk files backing the given artifacts (deduped by path)."""
    files: list[dict] = []
    seen_paths: set[str] = set()
    for item in artifacts:
        for artifact_path, role in _artifact_delete_candidate_paths(item, project):
            if not artifact_path or artifact_path in seen_paths:
                continue
            seen_paths.add(artifact_path)
            files.append(_delete_one_artifact_file(artifact_path, role, project))
    return files


def artifacts_delete(project: str, db: str | None, payload: dict) -> dict:
    ids = payload.get("ids") or payload.get("artifactIds") or []
    if isinstance(ids, str):
        ids = [ids]
    clean_ids = [str(item).strip() for item in ids if str(item).strip()]
    if not clean_ids:
        return {"ok": False, "error": "ids are required", "deleted": 0, "filesDeleted": 0}
    host_db = _host_db()
    artifacts = host_db.artifacts_by_ids(db, clean_ids)
    files = _delete_artifact_files(artifacts, project) if _payload_bool(payload, "deleteFiles", True) else []
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


def _iter_orphan_candidates(roots: list, seen: set, global_metadata: set):
    """Yield resolved ``*.json`` sidecar paths under roots, skipping the index and known metadata."""
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
            yield target


def _cleanup_one_sidecar(target: Path, project: str, *, delete_files: bool, sibling_suffixes: tuple) -> dict | None:
    """Return a delete-info record for an orphan sidecar, or None when it still has a real sibling."""
    if not _artifact_file_delete_allowed(str(target), project):
        return {"path": str(target), "role": "orphan-sidecar", "deleted": False, "skipped": True, "error": "path is outside allowed artifact roots"}
    siblings = [target.with_suffix(suffix) for suffix in sibling_suffixes]
    if any(path.is_file() for path in siblings):
        return None
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
    return info


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
    for target in _iter_orphan_candidates(roots, seen, global_metadata):
        info = _cleanup_one_sidecar(target, project, delete_files=delete_files, sibling_suffixes=sibling_suffixes)
        if info is not None:
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


def _api_summary(project: str, db: str | None, config: str | None, query: dict, node_urls: list[str] | None) -> tuple[int, dict]:
    return 200, summary(project, db, config, node_urls=node_urls)


def _api_tasks(project: str, db: str | None, config: str | None, query: dict, node_urls: list[str] | None) -> tuple[int, dict]:
    tickets, error = _safe_tickets(
        project,
        sprint=str(_first(query, "sprint", "current")),
        status=_first(query, "status"),
        queue=_first(query, "queue") or None,
    )
    return 200, {"ok": error is None, "tickets": tickets, "error": error}


def _api_checks(project: str, db: str | None, config: str | None, query: dict, node_urls: list[str] | None) -> tuple[int, dict]:
    host_db = _host_db()
    return 200, {"ok": True, "checks": host_db.recent_checks(db, subject=_first(query, "subject"), limit=int(_first(query, "limit", "20") or 20))}


def _api_logs(project: str, db: str | None, config: str | None, query: dict, node_urls: list[str] | None) -> tuple[int, dict]:
    host_db = _host_db()
    return 200, {"ok": True, "logs": host_db.recent_logs(db, stream=_first(query, "stream"), limit=int(_first(query, "limit", "20") or 20))}


def _api_artifacts(project: str, db: str | None, config: str | None, query: dict, node_urls: list[str] | None) -> tuple[int, dict]:
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


def _api_chat_history(project: str, db: str | None, config: str | None, query: dict, node_urls: list[str] | None) -> tuple[int, dict]:
    return 200, chat_history(db, project, limit=int(_first(query, "limit", "80") or 80))


def _api_services_live(project: str, db: str | None, config: str | None, query: dict, node_urls: list[str] | None) -> tuple[int, dict]:
    return 200, service_live_views(project, db=db, limit=int(_first(query, "limit", "8") or 8))


def _api_scanner_live(project: str, db: str | None, config: str | None, query: dict, node_urls: list[str] | None) -> tuple[int, dict]:
    return 200, scanner_live_state(project, limit=int(_first(query, "limit", "8") or 8))


def _api_nodes_or_routes(path: str, config: str | None, node_urls: list[str] | None) -> tuple[int, dict]:
    mesh = _mesh()
    discovered = mesh.discover_mesh(_host_config(config, node_urls))
    key = "nodes" if path == "/api/nodes" else "routes"
    return 200, {"ok": True, key: discovered.get(key) or []}


_API_ROUTES = {
    "/api/summary": _api_summary,
    "/api/tasks": _api_tasks,
    "/api/checks": _api_checks,
    "/api/logs": _api_logs,
    "/api/artifacts": _api_artifacts,
    "/api/chat/history": _api_chat_history,
    "/api/services/live": _api_services_live,
    "/api/scanner/live": _api_scanner_live,
}


def _dashboard_api_response(path: str, project: str, db: str | None, config: str | None, query: dict, node_urls: list[str] | None = None) -> tuple[int, dict]:
    """Resolve a dashboard /api/* path to an (HTTP status, JSON payload) pair."""
    handler = _API_ROUTES.get(path)
    if handler is not None:
        return handler(project, db, config, query, node_urls)
    if path in {"/api/nodes", "/api/routes"}:
        return _api_nodes_or_routes(path, config, node_urls)
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
                if parsed.path == "/api/nodes/test-routes":
                    payload = _read_json(self)
                    _json_response(self, 200, node_test_routes(project, db, config, payload,
                                                               node_urls=node_urls, token=token, identity=identity))
                    return
                if parsed.path == "/api/nodes/add":
                    payload = _read_json(self)
                    _json_response(self, 200, node_add(config, payload))
                    return
                if parsed.path == "/api/nodes/token":
                    payload = _read_json(self)
                    _json_response(self, 200, node_set_token(config, payload))
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
    return _port_holder_pids_impl(port)


def _process_cmdline(pid: int) -> str:
    return _process_cmdline_impl(pid)


def _is_dashboard_process(pid: int) -> bool:
    """True only if `pid` is a urirun host dashboard serve process (cmdline check). The guard
    that keeps auto-replace from ever killing an unrelated service that owns the port."""
    return _is_dashboard_process_impl(pid, process_cmdline_fn=_process_cmdline)


def _is_scanner_process(pid: int) -> bool:
    return _is_scanner_process_impl(pid, process_cmdline_fn=_process_cmdline)


def _is_chat_process(pid: int) -> bool:
    return _is_chat_process_impl(pid, process_cmdline_fn=_process_cmdline)


def _free_port_from_matching_processes(
    port: int,
    *,
    force: bool,
    emit: bool,
    is_target: Any,
    event_prefix: str,
) -> dict:
    return _free_port_from_matching_processes_impl(
        port,
        force=force,
        emit=emit,
        is_target=is_target,
        event_prefix=event_prefix,
        port_holder_pids_fn=_port_holder_pids,
        process_cmdline_fn=_process_cmdline,
        kill_fn=os.kill,
        getpid_fn=os.getpid,
        sleep_fn=time.sleep,
        time_fn=time.time,
        emit_fn=print,
    )


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
    _free_port_from_old_dashboard_impl(
        port,
        is_dashboard_process_fn=_is_dashboard_process,
        port_holder_pids_fn=_port_holder_pids,
        kill_fn=os.kill,
        getpid_fn=os.getpid,
        sleep_fn=time.sleep,
        time_fn=time.time,
        emit_fn=print,
    )


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
