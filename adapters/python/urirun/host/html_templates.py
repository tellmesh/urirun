from __future__ import annotations

import html as _html
import json as _json


def docs_nodes_html(profiles: list) -> str:
    rows = []
    for profile in profiles:
        rows.append(
            "<tr>"
            f"<td id=\"{_html.escape(profile['id'])}\"><strong>{_html.escape(profile['label'])}</strong>"
            f"<br><code>{_html.escape(profile['id'])}</code></td>"
            f"<td>{_html.escape(profile['description'])}</td>"
            f"<td><code>{_html.escape(profile['transport'])}</code></td>"
            f"<td><code>{_html.escape(profile['runtime'])}</code></td>"
            f"<td>{_html.escape(', '.join(profile.get('routesHint') or []))}</td>"
            "</tr>"
        )
    return """<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <title>urirun node types</title>
  <style>
    body { font: 15px/1.45 system-ui, sans-serif; margin: 32px; max-width: 1180px; color: #e5e7eb; background: #0f172a; }
    a { color: #67e8f9; } code { color: #bae6fd; }
    table { border-collapse: collapse; width: 100%; margin-top: 18px; }
    th, td { border: 1px solid #334155; padding: 10px; vertical-align: top; }
    th { text-align: left; background: #111827; }
    .subtle { color: #94a3b8; }
  </style>
</head>
<body>
  <h1>Typy node w urirun</h1>
  <p class="subtle">To jest backendowe źródło prawdy używane przez dashboard, discovery i URI object registry.</p>
  <table>
    <thead><tr><th>Typ</th><th>Kiedy używać</th><th>Transport</th><th>Runtime</th><th>Typowe URI</th></tr></thead>
    <tbody>""" + "\n".join(rows) + """</tbody>
  </table>
  <h2>Zasada wyboru komponentu</h2>
  <p>Jeśli komponent żyje jako proces i ma port/status, zrób z niego <strong>service</strong>.
  Jeśli dostarcza ograniczoną zdolność URI, zrób <strong>connector</strong>.
  Jeśli jest żywym widokiem, zrób <strong>widget</strong>.
  Jeśli jest skończonym plikiem lub raportem, zrób <strong>artifact</strong>.</p>
  <p><a href="/">Powrót do dashboardu</a></p>
</body>
</html>"""


def service_widget_html(view: dict) -> str:
    target = str(view.get("target") or view.get("serviceId") or "service:phone-scanner")
    view_id = str(view.get("id") or "")
    refresh = int(view.get("refreshMs") or 1000)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_html.escape(str(view.get("title") or "urirun service view"))}</title>
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
    const target = {_json.dumps(target)};
    const viewId = {_json.dumps(view_id)};
    const refreshMs = Math.max(500, Number({_json.dumps(refresh)}) || 1000);
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


def service_widget_svg(view: dict, summary: dict, width: int = 720, height: int = 180) -> str:
    status = summary["status"]
    status_color = "#34d399" if status in {"accepted", "running"} else "#fb7185" if status in {"failed", "rejected", "stopped"} else "#aaa49a"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{_html.escape(summary['title'])}">
  <rect width="100%" height="100%" rx="8" fill="#11100f"/>
  <rect x="10" y="10" width="{width - 20}" height="{height - 20}" rx="8" fill="#13251f" stroke="#2dd4bf" stroke-opacity=".45"/>
  <text x="24" y="42" fill="#f4f1e9" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="18" font-weight="700">{_html.escape(summary['title'])}</text>
  <rect x="{width - 130}" y="24" width="100" height="28" rx="14" fill="{status_color}" fill-opacity=".16"/>
  <text x="{width - 80}" y="43" text-anchor="middle" fill="{status_color}" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="13">{_html.escape(status)}</text>
  <text x="24" y="78" fill="#f4f1e9" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="15">{_html.escape(summary['subtitle'])}</text>
  <text x="24" y="108" fill="#aaa49a" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="13">{_html.escape(summary['detail'])}</text>
  <text x="24" y="{height - 24}" fill="#aaa49a" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="11">{_html.escape(str(view.get('id') or view.get('target') or ''))}</text>
</svg>"""


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
    .node-kind-tabs { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0; }
    .node-kind-tab { display: inline-flex; flex-direction: column; align-items: flex-start; gap: 1px; padding: 6px 10px; border: 1px solid var(--border, #334155); border-radius: 8px; background: var(--surface-2, #1e293b); cursor: pointer; font-size: .85rem; }
    .node-kind-tab .subtle { font-size: .68rem; }
    .node-kind-tab.active { border-color: var(--accent); background: var(--surface-3); }
    .node-kind-form { border: 1px solid var(--border, #334155); border-radius: 8px; padding: 10px; margin-top: 6px; }
    .phone-node-qr { text-align: center; margin: 8px 0; }
    .phone-node-qr img { width: 200px; height: 200px; background: #fff; padding: 6px; border-radius: 8px; }
    .pill.kind { background: rgba(56,189,248,.16); color: var(--accent, #38bdf8); text-transform: uppercase; font-size: .62rem; letter-spacing: .04em; }
    @media (max-width: 920px) { .nodes-layout { grid-template-columns: 1fr; } }
    .ticket-form-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
    }
    .ticket-form-grid .ticket-form-full { grid-column: 1 / -1; }
    .ticket-form-grid textarea { width: 100%; resize: vertical; }
    .qr-block { border-top: 1px solid var(--line-soft); padding-top: 6px; }
    .qr-block summary { cursor: pointer; }
    .qr-wrap { display: flex; align-items: center; gap: 10px; margin-top: 6px; flex-wrap: wrap; }
    .qr-img { width: 120px; height: 120px; image-rendering: pixelated; background: #fff; padding: 4px; border-radius: 6px; }
    .qr-img-lg { width: 260px; height: 260px; image-rendering: pixelated; background: #fff; padding: 8px; border-radius: 8px; }
    .qr-link { word-break: break-all; font-size: 12px; }
    .qr-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.6); display: grid; place-items: center; z-index: 1000; }
    .qr-overlay-card { background: var(--surface-2); border: 1px solid var(--line-soft); border-radius: 10px; padding: 16px; display: grid; gap: 10px; justify-items: center; max-width: 90vw; }
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
    .attachment.attachment-widget {
      grid-column: 1 / -1;
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
        <button data-view="twin">Digital Twin</button>
        <button data-view="tasks">Tasks</button>
        <button data-view="host">Host</button>
        <button data-view="nodes">Nodes</button>
        <button data-view="activity">Activity</button>
      </div>
      <button id="scannerBtn" type="button">Phone Scanner</button>
      <button id="phoneQrBtn" type="button" title="Pokaz QR tego widoku do otwarcia na telefonie" onclick="showViewQr()">Telefon (QR)</button>
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

      <section class="widget-layout view-block" data-section="twin" style="display: flex; flex-direction: column; height: 100%;">
        <div class="panel-head"><h2>Digital Twin Monitor</h2></div>
        <div class="panel-body" style="flex: 1; padding: 0;">
          <iframe src="/twin?source=live" title="Digital Twin Monitor" style="width:100%;height:100%;border:none;min-height:70vh;"></iframe>
        </div>
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
      <section class="artifact-layout view-block" data-section="host">
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2>Rozszerzenia URI (connectory)</h2>
              <p class="subtle">Dodaj connector ze \u017ar\u00f3d\u0142a i przetestuj, czy dzia\u0142a na ho\u015bcie lub wybranym w\u0119\u017ale.</p>
            </div>
            <span class="subtle" id="connectorInstallStatus"></span>
          </div>
          <div class="panel-body">
            <div class="ticket-form-grid">
              <label class="stack"><span class="subtle">\u0179r\u00f3d\u0142o</span>
                <select id="connectorSource" onchange="connectorSourceHint()">
                  <option value="pip">pip (PyPI)</option>
                  <option value="github">github repo</option>
                  <option value="local">lokalny folder</option>
                  <option value="npm">npm</option>
                  <option value="docker">docker image</option>
                  <option value="http">gotowe API (http)</option>
                </select></label>
              <label class="stack ticket-form-full"><span class="subtle" id="connectorSpecLabel">Pakiet / spec</span>
                <input id="connectorSpec" placeholder="urirun-connector-hash"></label>
            </div>
            <div class="artifact-actions" style="margin-top:8px">
              <button type="button" class="primary" onclick="installConnector()">\u2b07\ufe0f Zainstaluj connector</button>
              <span class="subtle">instaluje na ho\u015bcie (pip/github/lokalny); npm/docker/http \u2192 komenda do ich \u015brodowiska</span>
            </div>
            <pre id="connectorInstallResult" class="mono" style="margin-top:8px;white-space:pre-wrap"></pre>
            <hr style="border-color:var(--line-soft);margin:12px 0">
            <h3 style="margin:0 0 6px">Test connectora</h3>
            <div class="ticket-form-grid">
              <label class="stack ticket-form-full"><span class="subtle">URI testowy (najlepiej read-only query)</span>
                <input id="connectorTestUri" placeholder="uuid://host/id/query/v4"></label>
              <label class="stack ticket-form-full"><span class="subtle">Payload (JSON)</span>
                <input id="connectorTestPayload" placeholder="{}"></label>
              <label class="stack"><span class="subtle">\u015arodowisko</span>
                <select id="connectorTestEnv"><option value="host">host (lokalnie)</option></select></label>
            </div>
            <div class="artifact-actions" style="margin-top:8px">
              <button type="button" onclick="testConnector()">\u25b6\ufe0f Testuj</button>
              <span id="connectorTestStatus" class="subtle"></span>
            </div>
            <pre id="connectorTestResult" class="mono" style="margin-top:8px;white-space:pre-wrap"></pre>
          </div>
        </article>
      </section>
      <section class="artifact-layout view-block" data-section="tasks">
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2>Tickety</h2>
              <p class="subtle">Tickety infrastruktury — dodawaj ręcznie lub z czatu, uruchamiaj i zamykaj.</p>
            </div>
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
                <option value="infra">infra</option>
                <option value="default">default</option>
              </select>
              <button type="button" id="taskRefreshBtn" onclick="reloadTasks()">Odśwież</button>
            </div>
          </div>
          <div class="panel-body">
            <details class="add-ticket-form" id="addTicketDetails" style="margin-bottom:12px">
              <summary>➕ Nowy ticket (ręcznie lub z bieżącego promptu czatu)</summary>
              <div class="ticket-form-grid" style="margin-top:10px">
                <label class="stack"><span class="subtle">Tytuł</span><input id="newTicketName" placeholder="np. Wdróż node lenovo do mesh"></label>
                <label class="stack"><span class="subtle">Priorytet</span>
                  <select id="newTicketPriority"><option value="normal">normal</option><option value="high">high</option><option value="low">low</option></select></label>
                <label class="stack"><span class="subtle">Kolejka</span>
                  <select id="newTicketQueue"><option value="default">default</option><option value="infra">infra</option><option value="implementation">implementation</option><option value="daily">daily</option><option value="review">review</option></select></label>
                <label class="stack"><span class="subtle">Etykiety (po przecinku)</span><input id="newTicketLabels" placeholder="infra, deploy"></label>
                <label class="stack ticket-form-full"><span class="subtle">Opis</span><textarea id="newTicketDesc" rows="3" placeholder="Szczegóły zadania infrastrukturalnego…"></textarea></label>
              </div>
              <div class="artifact-actions" style="margin-top:8px">
                <button type="button" class="primary" onclick="createTicket()">💾 Utwórz ticket</button>
                <button type="button" onclick="createTicketFromChat()" title="Użyj tekstu z pola czatu jako nowy ticket">💬 Z promptu czatu</button>
                <span id="newTicketStatus" class="subtle"></span>
              </div>
            </details>
            <div class="table-wrap">
              <table>
                <thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Queue</th><th>Priority</th><th>Actions</th></tr></thead>
                <tbody id="tasksBody"></tbody>
              </table>
            </div>
          </div>
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
                    <button type="button" id="chatTwinBtn" title="Otwórz Digital Twin Monitor">&#128190; Twin</button>
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
                    <label class="check"><input type="checkbox" id="chatExecute" checked> Execute URI operations</label>
                    <label class="check"><input type="checkbox" id="chatNoLlm"> Heuristic planner only</label>
                    <button class="primary" type="submit" id="chatAskBtn">Send</button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        </article>
        <section class="nodes-layout view-block" data-section="nodes">
        <article class="panel">
          <div class="panel-head"><h2>Nodes</h2><span class="subtle" id="nodeCount"></span></div>
          <div class="panel-body">
            <div class="list" id="nodesList"></div>
            <details class="add-node-help" style="margin-top:10px">
              <summary>➕ Dodaj node (wybierz typ połączenia)</summary>
              <div class="stack" style="margin-top:8px">
                <p class="subtle">Każdy typ node ma inny poziom integracji i wymaga innej wiedzy. Wybierz typ, wypełnij formularz i otwórz pełną instrukcję. <a href="/docs/nodes" target="_blank" rel="noreferrer">📖 Dokumentacja typów node</a></p>
                <div class="node-kind-tabs" id="nodeKindTabs">
                  <button type="button" class="node-kind-tab" data-kind="server" onclick="selectNodeKind('server')">🖥️ Server <span class="subtle">shell/SSH</span></button>
                  <button type="button" class="node-kind-tab" data-kind="pc" onclick="selectNodeKind('pc')">💻 PC <span class="subtle">app + shell</span></button>
                  <button type="button" class="node-kind-tab" data-kind="rdp" onclick="selectNodeKind('rdp')">🪟 RDP <span class="subtle">pulpit zdalny</span></button>
	                  <button type="button" class="node-kind-tab" data-kind="smartphone" onclick="selectNodeKind('smartphone')">📱 Smartphone <span class="subtle">webpage → APK</span></button>
	                  <button type="button" class="node-kind-tab" data-kind="browser-debug" onclick="selectNodeKind('browser-debug')">🌐 Browser Debug <span class="subtle">CDP</span></button>
	                  <button type="button" class="node-kind-tab" data-kind="browser-chrome-plugin" onclick="selectNodeKind('browser-chrome-plugin')">🧩 Chrome Plugin <span class="subtle">extension</span></button>
	                  <button type="button" class="node-kind-tab" data-kind="browser-firefox-plugin" onclick="selectNodeKind('browser-firefox-plugin')">🧩 Firefox Plugin <span class="subtle">extension</span></button>
	                  <button type="button" class="node-kind-tab" data-kind="webpage" onclick="selectNodeKind('webpage')">📄 Webpage <span class="subtle">jedna strona JS</span></button>
	                  <button type="button" class="node-kind-tab" data-kind="api" onclick="selectNodeKind('api')">🔌 API <span class="subtle">HTTP/auth</span></button>
	                  <button type="button" class="node-kind-tab" data-kind="device" onclick="selectNodeKind('device')">🧩 Device <span class="subtle">multi-API</span></button>
                </div>

                <!-- SERVER -->
                <div class="node-kind-form" id="nodeForm-server" style="display:none">
                  <p class="subtle">🖥️ <strong>Server</strong> — sterowanie przez <strong>shell/SSH</strong>. Headless maszyna; instalujesz węzeł urirun zdalnie przez SSH. Wymaga: dostęp SSH (user@host), uprawnienia do instalacji. <a href="/docs/nodes#server" target="_blank" rel="noreferrer">instrukcja</a></p>
                  <label class="stack"><span class="subtle">Nazwa node'a</span><input id="srvName" placeholder="server-01"></label>
                  <label class="stack"><span class="subtle">Host / IP</span><input id="srvHost" oninput="srvSnippet()" placeholder="192.168.1.50"></label>
                  <div class="artifact-actions">
                    <label class="stack" style="flex:1"><span class="subtle">SSH user</span><input id="srvUser" oninput="srvSnippet()" placeholder="ubuntu"></label>
                    <label class="stack"><span class="subtle">Port node'a</span><input id="srvPort" oninput="srvSnippet()" value="8765" style="width:90px"></label>
                  </div>
                  <p class="subtle">Uruchom zdalnie (instaluje węzeł i serwuje go w tle):</p>
                  <pre id="srvSnippet" class="mono">— podaj host i usera —</pre>
                  <div class="artifact-actions">
                    <button type="button" onclick="saveTypedNode('server','srvName',srvUrl())">💾 Zapisz node (po instalacji)</button>
                    <span id="srvStatus" class="subtle"></span>
                  </div>
                </div>

                <!-- PC -->
                <div class="node-kind-form" id="nodeForm-pc" style="display:none">
                  <p class="subtle">💻 <strong>PC</strong> — sterowanie przez <strong>aplikację desktop + shell</strong>. Maszyna z GUI; uruchamiasz węzeł lokalnie (lub przez aplikację ifURI). Wymaga: dostęp do pulpitu, terminal. <a href="/docs/nodes#pc" target="_blank" rel="noreferrer">instrukcja</a></p>
                  <label class="stack"><span class="subtle">Nazwa node'a</span><input id="pcName" placeholder="lenovo"></label>
                  <label class="stack"><span class="subtle">URL węzła (po uruchomieniu)</span><input id="pcUrl" placeholder="http://192.168.1.20:8765"></label>
                  <p class="subtle">Na PC uruchom węzeł:</p>
                  <pre class="mono">curl -fsSL https://get.ifuri.com/node.sh | bash -s -- --name pc --port 8765 --background</pre>
                  <div class="artifact-actions">
                    <button type="button" onclick="saveTypedNode('pc','pcName',document.getElementById('pcUrl').value)">💾 Zapisz node</button>
                    <span id="pcStatus" class="subtle"></span>
                  </div>
                </div>

                <!-- RDP -->
                <div class="node-kind-form" id="nodeForm-rdp" style="display:none">
                  <p class="subtle">🪟 <strong>RDP</strong> — <strong>pulpit zdalny</strong> (Windows/xrdp). Sterujesz klawiaturą/myszą/ekranem zdalnego pulpitu. Wymaga: host RDP, login, port 3389, węzeł urirun z connectorem KVM po stronie pulpitu. <a href="/docs/nodes#rdp" target="_blank" rel="noreferrer">instrukcja</a></p>
                  <label class="stack"><span class="subtle">Nazwa node'a</span><input id="rdpName" placeholder="win-desktop"></label>
                  <div class="artifact-actions">
                    <label class="stack" style="flex:1"><span class="subtle">Host RDP</span><input id="rdpHost" oninput="rdpSnippet()" placeholder="192.168.1.30"></label>
                    <label class="stack"><span class="subtle">Port RDP</span><input id="rdpPort" oninput="rdpSnippet()" value="3389" style="width:90px"></label>
                  </div>
                  <label class="stack"><span class="subtle">URL węzła urirun na pulpicie</span><input id="rdpUrl" placeholder="http://192.168.1.30:8765"></label>
                  <p class="subtle">Połącz pulpit (przykład xfreerdp):</p>
                  <pre id="rdpSnippet" class="mono">— podaj host RDP —</pre>
                  <div class="artifact-actions">
                    <button type="button" onclick="saveTypedNode('rdp','rdpName',document.getElementById('rdpUrl').value)">💾 Zapisz node</button>
                    <span id="rdpStatus" class="subtle"></span>
                  </div>
                </div>

                <!-- SMARTPHONE (two-stage: webpage node now then mobile node after APK) -->
                <div class="node-kind-form" id="nodeForm-smartphone" style="display:none">
                  <p class="subtle">📱 <strong>Smartphone</strong> — dwa etapy: <strong>(1) webpage node</strong> od razu po otwarciu strony w przeglądarce telefonu (sterowanie przez JS na stronie), <strong>(2) mobile node</strong> po instalacji APK/Termux (pełny węzeł: pliki, system). Wymaga: serwis android-node (port 8195) + telefon w tej samej sieci. <a href="/docs/nodes#smartphone" target="_blank" rel="noreferrer">instrukcja</a></p>
                  <div class="artifact-actions">
                    <button type="button" id="phoneSvcBtn" onclick="startPhoneService()">▶ Uruchom serwis android-node</button>
                    <button type="button" onclick="restartPhoneService()">↻ Restart 8195</button>
                    <button type="button" id="addPhoneNodeBtn" onclick="showAddPhoneNodeQR()">📱 Pokaż QR</button>
                    <span id="addPhoneNodeStatus" class="subtle"></span>
                  </div>
                  <div id="phoneNodeQrContainer" style="display:none;margin-top:8px">
                    <div id="phoneNodeQr" class="phone-node-qr"></div>
                    <p class="subtle">URL instalacji: <code id="phoneNodeUrl"></code></p>
                    <p class="subtle" id="phoneNodeReach"></p>
                    <div id="phoneWebNodes" class="subtle">Brak podłączonych telefonów (webpage node) — otwórz URL na telefonie.</div>
                    <label class="stack" style="margin-top:6px"><span class="subtle">Po instalacji APK — zarejestruj jako mobile node (nazwa + URL telefonu, port 8765)</span></label>
                    <div class="artifact-actions">
                      <input id="phoneNodeName" placeholder="nexus7">
                      <input id="phoneNodeNodeUrl" placeholder="http://192.168.x.x:8765">
                      <button type="button" onclick="savePhoneNode()">💾 Zapisz mobile node</button>
                      <span id="phoneNodeSaveStatus" class="subtle"></span>
                    </div>
                  </div>
                </div>

                <!-- BROWSER DEBUG -->
                <div class="node-kind-form" id="nodeForm-browser-debug" style="display:none">
                  <p class="subtle">🌐 <strong>Browser Debug</strong> — sterowanie <strong>całą przeglądarką</strong> przez DevTools/CDP. Wszystkie karty: otwieraj/zamykaj/nawiguj. Wymaga: przeglądarka z <code>--remote-debugging-port=9222</code> + connector webnode. <a href="/docs/nodes#browser-debug" target="_blank" rel="noreferrer">instrukcja</a></p>
                  <div class="phone-node-qr" id="connectQr-browser-debug"></div>
                  <p class="subtle">QR powyżej = ścieżka <strong>relay</strong> (otwórz na urządzeniu, <code>http://HOST:8195/</code>, <strong>HTTP</strong>). Pola CDP poniżej = osobny tryb debugowania: lista kart i pełne sterowanie przez DevTools, ale wymaga uruchomienia przeglądarki z <code>--remote-debugging-port=9222</code>.</p>
                  <label class="stack"><span class="subtle">Nazwa node'a</span><input id="brName" placeholder="chrome"></label>
                  <label class="stack"><span class="subtle">Endpoint debugowania (CDP)</span><input id="brUrl" placeholder="http://127.0.0.1:9222" oninput="updateEndpointQr('brUrl','cdpQr-browser-debug')"></label>
                  <div class="phone-node-qr" id="cdpQr-browser-debug"><span class="subtle">wpisz endpoint CDP — QR pojawi się tutaj</span></div>
                  <p class="subtle">Uruchom przeglądarkę z debugowaniem:</p>
                  <pre class="mono">google-chrome --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1</pre>
                  <div class="artifact-actions">
                    <button type="button" onclick="saveTypedNode('browser-debug','brName',document.getElementById('brUrl').value)">💾 Zapisz node</button>
                    <span id="brStatus" class="subtle"></span>
                  </div>
                </div>

                <!-- CHROME PLUGIN -->
                <div class="node-kind-form" id="nodeForm-browser-chrome-plugin" style="display:none">
                  <p class="subtle">🧩 <strong>Chrome Plugin</strong> — kontrola aktywnej karty przez rozszerzenie Chrome. Używa <code>browser-plugin://chrome/...</code> i może czytać DOM, listować urządzenia strony, uruchamiać kamerę oraz przekazywać inne URI do node <code>/run</code>. <a href="/docs/nodes#browser-chrome-plugin" target="_blank" rel="noreferrer">instrukcja</a></p>
                  <label class="stack"><span class="subtle">Nazwa node'a</span><input id="chromePluginName" placeholder="chrome-plugin"></label>
                  <label class="stack"><span class="subtle">Node URL dla popupu pluginu</span><input id="chromePluginUrl" placeholder="http://127.0.0.1:8765"></label>
                  <p class="subtle">Załaduj folder <code>/home/tom/github/if-uri/chrome-plugin</code> w <code>chrome://extensions</code> jako unpacked extension.</p>
                  <div class="artifact-actions">
                    <button type="button" onclick="saveTypedNode('browser-chrome-plugin','chromePluginName',document.getElementById('chromePluginUrl').value)">💾 Zapisz node</button>
                    <span id="chromePluginStatus" class="subtle"></span>
                  </div>
                </div>

                <!-- FIREFOX PLUGIN -->
                <div class="node-kind-form" id="nodeForm-browser-firefox-plugin" style="display:none">
                  <p class="subtle">🧩 <strong>Firefox Plugin</strong> — kontrola aktywnej karty przez rozszerzenie Firefox. Używa <code>browser-plugin://firefox/...</code> i zachowuje kompatybilność z <code>browser://</code>. <a href="/docs/nodes#browser-firefox-plugin" target="_blank" rel="noreferrer">instrukcja</a></p>
                  <label class="stack"><span class="subtle">Nazwa node'a</span><input id="firefoxPluginName" placeholder="firefox-plugin"></label>
                  <label class="stack"><span class="subtle">Node URL dla popupu pluginu</span><input id="firefoxPluginUrl" placeholder="http://127.0.0.1:8765"></label>
                  <p class="subtle">Załaduj folder <code>/home/tom/github/if-uri/firefox-plugin</code> w <code>about:debugging#/runtime/this-firefox</code>.</p>
                  <div class="artifact-actions">
                    <button type="button" onclick="saveTypedNode('browser-firefox-plugin','firefoxPluginName',document.getElementById('firefoxPluginUrl').value)">💾 Zapisz node</button>
                    <span id="firefoxPluginStatus" class="subtle"></span>
                  </div>
                </div>

                <!-- WEBPAGE -->
                <div class="node-kind-form" id="nodeForm-webpage" style="display:none">
                  <p class="subtle">📄 <strong>Webpage</strong> — sterowanie <strong>konkretną stroną</strong> przez HTML/JS (relay). Otwórz QR na urządzeniu — strona rejestruje się sama w serwisie android-node pod <code>http://HOST:8195/</code> (czysty <strong>HTTP</strong>, bez „s") i staje się webpage node: lista URI process, urządzenia strony (kamera/mikrofon), sensory, akcje navigate/eval/iframe. Tryb debugowania przeglądarki (CDP/DevTools) jest w osobnej zakładce <strong>Browser Debug</strong>. <a href="/docs/nodes#webpage" target="_blank" rel="noreferrer">instrukcja</a></p>
                  <div class="phone-node-qr" id="connectQr-webpage"></div>
                  <div id="webpageNodes" class="subtle">Brak podłączonych stron — otwórz QR na urządzeniu (telefon/przeglądarka).</div>
                  <label class="stack"><span class="subtle">Nazwa node'a</span><input id="webName" placeholder="page-checkout"></label>
                  <div class="artifact-actions">
                    <button type="button" onclick="saveWebpageNode()">💾 Zapisz webpage node</button>
                    <span id="webStatus" class="subtle"></span>
                  </div>
                </div>

                <!-- API NODE -->
	                <div class="node-kind-form" id="nodeForm-api" style="display:none">
	                  <p class="subtle">🔌 <strong>API Node</strong> — zewnętrzne API HTTP/REST/OpenAPI z autoryzacją. Sekret zostanie zapisany w keyring, a w configu zostanie tylko <code>secretRef</code>. <a href="/docs/nodes#api" target="_blank" rel="noreferrer">instrukcja</a></p>
	                  <label class="stack"><span class="subtle">Nazwa node'a</span><input id="apiNodeName" placeholder="crm-api"></label>
	                  <label class="stack"><span class="subtle">Base URL API</span><input id="apiNodeUrl" placeholder="https://api.example.test/v1"></label>
	                  <div class="artifact-actions">
	                    <label class="stack" style="flex:1"><span class="subtle">API id</span><input id="apiNodeApiId" value="main"></label>
	                    <label class="stack" style="flex:1"><span class="subtle">Kind/protocol</span><input id="apiNodeApiKind" value="rest"></label>
	                  </div>
	                  <div class="artifact-actions">
	                    <label class="stack" style="flex:1"><span class="subtle">Auth type</span><input id="apiNodeAuthType" placeholder="bearer / api-key / basic"></label>
	                    <label class="stack" style="flex:2"><span class="subtle">Token/API key (keyring)</span><input id="apiNodeSecret" type="password" autocomplete="off" placeholder="nie zapisuje się w pliku"></label>
	                  </div>
	                  <div class="artifact-actions">
	                    <button type="button" onclick="saveApiNode()">💾 Zapisz API node</button>
	                    <span id="apiNodeStatus" class="subtle"></span>
	                  </div>
	                </div>

	                <!-- DEVICE NODE -->
	                <div class="node-kind-form" id="nodeForm-device" style="display:none">
	                  <p class="subtle">🧩 <strong>Device Node</strong> — urządzenie z wieloma interfejsami, np. kamera IP/RPi/NAS: panel WWW, RTSP/RTMP, SSH, SMB/NFS. <a href="/docs/nodes#device" target="_blank" rel="noreferrer">instrukcja</a></p>
	                  <label class="stack"><span class="subtle">Nazwa node'a</span><input id="deviceNodeName" placeholder="rpi-camera"></label>
	                  <label class="stack"><span class="subtle">Główny URL/panel</span><input id="deviceNodeUrl" placeholder="http://rpi.local"></label>
	                  <label class="stack"><span class="subtle">apis[] JSON</span><textarea id="deviceNodeApis" rows="7">[
  {"id":"panel","kind":"web","url":"http://rpi.local"},
  {"id":"stream","kind":"rtsp","role":"camera","url":"rtsp://rpi.local/live"},
  {"id":"share","kind":"smb","url":"smb://rpi.local/share"},
  {"id":"ssh","kind":"ssh","url":"ssh://pi@rpi.local"}
]</textarea></label>
	                  <div class="artifact-actions">
	                    <button type="button" onclick="saveDeviceNode()">💾 Zapisz device node</button>
	                    <span id="deviceNodeStatus" class="subtle"></span>
	                  </div>
	                </div>

	                <hr style="border:none;border-top:1px solid var(--border,#334155);margin:12px 0">
                <details>
                  <summary class="subtle">🔎 Skan LAN / wpis ręczny / token (zaawansowane)</summary>
                  <div class="stack" style="margin-top:8px">
                    <div class="artifact-actions">
                      <button type="button" id="scanNodesBtn" onclick="scanNodes()">🔎 Skanuj sieć (LAN)</button>
                      <span id="scanNodesStatus" class="subtle"></span>
                    </div>
                    <div id="scanNodesResults" class="list"></div>
                    <label class="stack"><span class="subtle">Nazwa node'a</span><input id="addNodeName" oninput="nodeAddSnippet()" placeholder="office-node"></label>
                    <label class="stack"><span class="subtle">URL node'a</span><input id="addNodeUrl" oninput="nodeAddSnippet()" placeholder="http://host-or-ip:8765"></label>
                    <div class="artifact-actions">
                      <button type="button" onclick="saveNodeFromForm()">💾 Zapisz node</button>
                      <a id="addNodeHealth" href="#" target="_blank" rel="noreferrer">otwórz /health</a>
                      <span id="addNodeStatus" class="subtle"></span>
                    </div>
                    <label class="stack"><span class="subtle">Token zarządzania węzłem (X-Urirun-Token)</span>
                      <input id="addNodeToken" type="password" autocomplete="off" placeholder="wklej token (keyring, nie plaintext)"></label>
                    <div class="artifact-actions">
                      <button type="button" onclick="saveNodeToken()">🔑 Zapisz token (keyring)</button>
                      <span id="addNodeTokenStatus" class="subtle"></span>
                    </div>
                    <pre id="addNodeSnippet" class="mono">— wpisz nazwę i URL powyżej —</pre>
                  </div>
                </details>
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
    <button data-view="twin">Digital Twin</button>
    <button data-view="tasks">Tasks</button>
    <button data-view="host">Host</button>
    <button data-view="nodes">Nodes</button>
    <button data-view="activity">Activity</button>
  </nav>
  <script>
    const VALID_VIEWS = new Set(['overview', 'chat', 'discovery', 'artifacts', 'widgets', 'twin', 'tasks', 'host', 'nodes', 'activity']);
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
      const { signal: callerSignal, timeoutMs = 15000, ...rest } = options;
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), timeoutMs);
      if (callerSignal) callerSignal.addEventListener('abort', () => ctrl.abort());
      try {
        const response = await fetch(path, {
          headers: { 'Content-Type': 'application/json' },
          signal: ctrl.signal,
          ...rest,
        });
        const data = await response.json();
        if (!response.ok || data.ok === false) throw new Error(data.error || response.statusText);
        return data;
      } finally {
        clearTimeout(timer);
      }
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
        execute: $('chatExecute') && $('chatExecute').checked ? '1' : '0',
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
        $('chatExecute').checked = search.get('execute') !== '0';
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

    // Reload only the tickets table (sprint/queue filters applied) without a full dashboard reload.
    async function reloadTasks() {
      const sprint = $('sprintFilter') ? $('sprintFilter').value : 'current';
      const queue = $('queueFilter') ? $('queueFilter').value : '';
      try {
        const data = await api(`/api/tasks?sprint=${encodeURIComponent(sprint)}&queue=${encodeURIComponent(queue)}`);
        state.tasks = data.tickets || [];
        renderTasks(state.tasks);
        renderMetrics(state.summary || {});
      } catch (error) { /* surfaced on next full load */ }
    }

    // Create a planfile ticket from the manual form. POSTs to /api/tasks/create (planfile_adapter),
    // so it is the same ticket store the CLI and agents use.
    async function createTicket(extra = {}) {
      const status = $('newTicketStatus');
      const body = {
        name: ($('newTicketName') || {}).value || '',
        description: ($('newTicketDesc') || {}).value || '',
        priority: ($('newTicketPriority') || {}).value || 'normal',
        queue: ($('newTicketQueue') || {}).value || 'default',
        labels: ($('newTicketLabels') || {}).value || '',
        ...extra,
      };
      if (!String(body.name).trim() && !String(body.prompt || '').trim()) {
        if (status) status.textContent = 'podaj tytuł (lub użyj \u201eZ promptu czatu\u201d)';
        return;
      }
      if (status) status.textContent = 'tworz\u0119 ticket\u2026';
      try {
        const res = await api('/api/tasks/create', { method: 'POST', body: JSON.stringify(body) });
        const t = res.ticket || {};
        if (status) status.textContent = `utworzono: ${t.id || ''} ${t.name || ''}`;
        if ($('newTicketName')) $('newTicketName').value = '';
        if ($('newTicketDesc')) $('newTicketDesc').value = '';
        if ($('newTicketLabels')) $('newTicketLabels').value = '';
        await reloadTasks();
      } catch (error) {
        if (status) status.textContent = 'b\u0142\u0105d: ' + error.message;
      }
    }

    // "Add from chat": turn whatever is currently typed in the chat composer into a ticket.
    function createTicketFromChat() {
      const prompt = ($('chatPrompt') ? $('chatPrompt').value : '').trim();
      const status = $('newTicketStatus');
      if (!prompt) { if (status) status.textContent = 'pole czatu jest puste'; return; }
      createTicket({ prompt, source_tool: 'urirun-host-chat' });
    }

    // ---- Host menu: install + smoke-test URI connectors ----
    function connectorSourceHint() {
      const src = ($('connectorSource') || {}).value || 'pip';
      const hints = {
        pip: ['Pakiet PyPI', 'urirun-connector-hash'],
        github: ['Repo GitHub (user/repo lub URL)', 'if-uri/urirun-connector-hash'],
        local: ['Folder connectora', '/home/tom/github/if-uri/urirun-connector-hash'],
        npm: ['Pakiet npm', '@urirun/connector-uuid'],
        docker: ['Obraz docker', 'ghcr.io/if-uri/connector:latest'],
        http: ['Bazowy URL API', 'https://api.example.com'],
      };
      const pair = hints[src] || hints.pip;
      if ($('connectorSpecLabel')) $('connectorSpecLabel').textContent = pair[0];
      if ($('connectorSpec')) $('connectorSpec').placeholder = pair[1];
    }

    async function installConnector() {
      const source = ($('connectorSource') || {}).value || 'pip';
      const spec = (($('connectorSpec') || {}).value || '').trim();
      const status = $('connectorInstallStatus');
      const out = $('connectorInstallResult');
      if (!spec) { if (status) status.textContent = 'podaj pakiet/spec'; return; }
      if (status) status.textContent = 'instaluje...';
      if (out) out.textContent = 'pip install ... (' + source + ': ' + spec + ')';
      try {
        const res = await api('/api/connectors/install', { method: 'POST', body: JSON.stringify({ source, spec }) });
        if (status) status.textContent = res.ok ? '\u2713 zainstalowano' : '\u2717 ' + (res.error || 'blad');
        const lines = [];
        if (res.command) lines.push('$ ' + res.command);
        if (res.schemes && res.schemes.length) lines.push('schematy URI: ' + res.schemes.join(', '));
        if (res.hint) lines.push('hint: ' + res.hint);
        if (res.stdout) lines.push(res.stdout);
        if (res.stderr) lines.push(res.stderr);
        if (out) out.textContent = lines.join('\n') || JSON.stringify(res, null, 2);
        if (res.ok && typeof load === 'function') load().catch(() => {});
      } catch (error) {
        if (status) status.textContent = '\u2717 ' + error.message;
        if (out) out.textContent = error.message;
      }
    }

    function parseConnectorTestPayload() {
      const raw = (($('connectorTestPayload') || {}).value || '').trim();
      if (!raw) return {};
      try { return JSON.parse(raw); } catch (e) { throw new Error('payload nie jest poprawnym JSON: ' + e.message); }
    }

    async function testConnector() {
      const uri = (($('connectorTestUri') || {}).value || '').trim();
      const env = ($('connectorTestEnv') || {}).value || 'host';
      const status = $('connectorTestStatus');
      const out = $('connectorTestResult');
      if (!uri) { if (status) status.textContent = 'podaj URI testowy'; return; }
      let payload;
      try { payload = parseConnectorTestPayload(); } catch (e) { if (status) status.textContent = e.message; return; }
      if (status) status.textContent = 'testuje na ' + env + '...';
      if (out) out.textContent = '';
      try {
        let res;
        if (env === 'host') {
          res = await api('/api/connectors/test', { method: 'POST', body: JSON.stringify({ uri, payload }) });
        } else {
          const node = env.replace(/^node:/, '');
          res = await api('/api/nodes/test-routes', { method: 'POST', body: JSON.stringify({ node, uris: [uri] }) });
        }
        const broken = res.results && res.results.filter ? res.results.filter((r) => r.status && r.status !== 'ok').length : 0;
        const ok = res.ok !== false && broken === 0;
        if (status) status.textContent = ok ? '\u2713 dziala' : '\u2717 blad/niepelne';
        if (out) out.textContent = JSON.stringify(res, null, 2).slice(0, 4000);
      } catch (error) {
        if (status) status.textContent = '\u2717 ' + error.message;
        if (out) out.textContent = error.message;
      }
    }

    function renderNodes(nodes) {
      $('nodeCount').textContent = `${nodes.length} configured`;
      $('nodesList').innerHTML = nodes.map((node) => `<div class="item node-row${state.selectedRoutesNode === node.name ? ' node-row-active' : ''}" data-node="${esc(node.name)}" onclick="selectNodeRoutes(this.dataset.node)" title="Kliknij, aby pokazać procesy URI tego węzła">
        <div style="display:flex;align-items:center;gap:8px;justify-content:space-between">
          <span><strong>${esc(node.name)}</strong> <span class="pill ${node.reachable ? 'up' : 'down'}">${node.reachable ? 'up' : 'down'}</span>${node.kind ? ` <span class="pill kind">${esc(node.kind)}</span>` : ''}</span>
          <span style="display:flex;gap:6px">
            <button type="button" data-node="${esc(node.name)}" onclick="event.stopPropagation(); testNodeFromList(this.dataset.node)" title="Przetestuj route'y query tego węzła">Test</button>
            <button type="button" class="danger" data-node="${esc(node.name)}" data-transient="${node.transient ? '1' : ''}" onclick="event.stopPropagation(); removeNode(this.dataset.node, this.dataset.transient === '1')" title="${node.transient ? 'Węzeł chwilowy (live) — zniknie po rozłączeniu; usuń z widoku' : 'Usuń węzeł z host config'}">✕ Usuń</button>
          </span>
        </div>
        <div class="mono">${esc(node.url)}</div>
        <div class="subtle">${(node.routes || []).length} routes${node.error ? ` · ${esc(node.error)}` : ''}</div>
        ${qrDetails(node.url, `node:${node.name}`, node.kind)}
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
    // ---- Phone QR codes: open a plugin / webpage / view on a smartphone by scanning ----
    // Phones cannot reach the 127.0.0.1 dashboard, so QR targets use the LAN base from summary.lan
    // (env URIRUN_LAN_QR_BASE, default the android-node on :8195); camera-type targets use https.
    function lanBase(secure) {
      const lan = (state.summary && state.summary.lan) || {};
      const base = (secure ? lan.secureBase : lan.base) || 'http://192.168.188.212:8195';
      return base.replace(/\/+$/, '');
    }
    function lanNeedsSecure(s) { return /camera|webcam|scanner|getusermedia|mediadevices/i.test(String(s || '')); }
    // Build a LAN-openable URL: rebase an absolute http(s) URL onto the LAN host, or append a path.
    function lanUrl(pathOrUrl, secure) {
      const value = String(pathOrUrl || '').trim();
      const useSecure = secure === undefined ? lanNeedsSecure(value) : secure;
      const base = lanBase(useSecure);
      if (/^https?:\/\//i.test(value)) {
        try {
          const u = new URL(value);
          // Already LAN/remote-reachable (a real node host) -> keep as-is; only upgrade to https
          // when the target needs it (camera). Localhost = the dashboard -> rebase to the LAN base.
          if (!/^(127\.|0\.0\.0\.0$|localhost$)/i.test(u.hostname)) {
            if (useSecure && u.protocol === 'http:') u.protocol = 'https:';
            return u.toString();
          }
          return base + u.pathname + u.search + u.hash;
        } catch (e) { return value; }
      }
      if (!value) return base + '/';
      return base + (value.startsWith('/') ? value : '/' + value);
    }
    function qrSrc(url) { return '/api/nodes/qr?url=' + encodeURIComponent(url); }
    // Collapsible QR block reused by node cards and widget cards.
    function qrDetails(pathOrUrl, label, kind) {
      const url = lanUrl(pathOrUrl);
      return `<details class="qr-block" onclick="event.stopPropagation()" style="margin-top:6px">
        <summary class="subtle">📱 QR (otworz na telefonie)${kind ? ` · ${esc(kind)}` : ''}</summary>
        <div class="qr-wrap"><img class="qr-img" loading="lazy" src="${qrSrc(url)}" alt="QR ${esc(label || url)}">
          <a class="mono qr-link" href="${esc(url)}" target="_blank" rel="noreferrer">${esc(url)}</a></div>
      </details>`;
    }
    // Toolbar action: show a QR of the CURRENT view (LAN base + current path) in an overlay.
    function showViewQr() {
      const url = lanUrl(window.location.pathname + window.location.search, false);
      let box = document.getElementById('qrOverlay');
      if (!box) {
        box = document.createElement('div'); box.id = 'qrOverlay'; box.className = 'qr-overlay';
        box.addEventListener('click', (e) => { if (e.target === box) box.remove(); });
        document.body.appendChild(box);
      }
      box.innerHTML = `<div class="qr-overlay-card">
        <div class="stream-head"><strong>Otworz ten widok na telefonie</strong>
          <button type="button" onclick="document.getElementById('qrOverlay').remove()">✕</button></div>
        <img class="qr-img-lg" src="${qrSrc(url)}" alt="QR ${esc(url)}">
        <a class="mono qr-link" href="${esc(url)}" target="_blank" rel="noreferrer">${esc(url)}</a>
        <p class="subtle">Baza LAN: ${esc(lanBase(false))} · skanuj aparatem telefonu (ta sama siec Wi-Fi)</p>
      </div>`;
    }

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
      const envSel = $('connectorTestEnv');
      if (envSel) {
        const cur = envSel.value;
        const nodes = summary.nodes || [];
        envSel.innerHTML = ['<option value="host">host (lokalnie)</option>',
          ...nodes.map((n) => `<option value="node:${esc(n.name)}">node: ${esc(n.name)}${n.reachable ? '' : ' (offline)'}</option>`)].join('');
        if (cur) envSel.value = cur;
      }
      if (typeof connectorSourceHint === 'function') connectorSourceHint();
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

    // Remove a node from the nodes list. Persistent nodes are deleted from host config;
    // transient (live webpage) nodes are forgotten in the 8195 service so they stop reappearing.
    async function removeNode(name, transient) {
      if (!name) return;
      const msg = transient
        ? `Usunąć chwilowy węzeł „${name}"? (rozłączy stronę web; wróci, jeśli ją odświeżysz)`
        : `Usunąć węzeł „${name}" z host config?`;
      if (!window.confirm(msg)) return;
      try {
        const res = await api('/api/nodes/remove', { method: 'POST', body: JSON.stringify({ name, transient: !!transient }) });
        if (!res.ok) throw new Error(res.error || 'nie udało się usunąć');
        if (typeof load === 'function') load().catch(() => {});
      } catch (error) {
        window.alert('Błąd usuwania: ' + error.message);
      }
    }

    // Smartphone node enrollment: ask the host for a QR pointing at the android-node setup
    // service (port 8195). The phone scans it, downloads the APK / Termux bootstrap, and joins
    // the mesh as a node — same model as the Lenovo laptop.
    async function showAddPhoneNodeQR() {
      const status = $('addPhoneNodeStatus');
      if (status) status.textContent = 'generuję QR…';
      try {
        const res = await api('/api/nodes/phone-qr', { method: 'POST', body: JSON.stringify({}) });
        if (!res.ok) throw new Error(res.error || 'nie udało się wygenerować QR');
        const box = $('phoneNodeQrContainer');
        const img = $('phoneNodeQr');
        if (img) img.innerHTML = res.previewUrl
          ? '<img src="' + esc(res.previewUrl) + '" alt="QR instalacji smartfona">'
          : '<span class="subtle">QR zapisany: ' + esc(res.uri || '') + '</span>';
        if ($('phoneNodeUrl')) $('phoneNodeUrl').textContent = res.url || '';
        if ($('phoneNodeReach')) $('phoneNodeReach').textContent = res.serviceReachable
          ? '✅ Serwis android-node odpowiada — zeskanuj QR telefonem.'
          : '⚠️ Serwis android-node nie odpowiada pod ' + (res.url || '') + ' — uruchom „urirun-android-node serve" na hoście.';
        if (box) box.style.display = '';
        if (status) status.textContent = '';
        startWebNodePolling();  // pages that open the URL auto-appear as webpage nodes
      } catch (error) {
        if (status) status.textContent = 'błąd: ' + error.message;
      }
    }

    // Poll the android/webpage-node service for browsers/phones that opened the page.
    // auto-registered server-side; here we just surface them and offer one-click "save as node".
    let _webNodeTimer = null;
    function startWebNodePolling() {
      if (_webNodeTimer) return;
      const tick = async () => {
        try {
          const res = await api('/api/nodes/phone-web');
          const box = $('phoneWebNodes');
          if (!box) return;
          const devs = (res && res.devices) || [];
          if (!devs.length) {
            box.innerHTML = 'Brak podłączonych przeglądarek/telefonów (webpage node) — otwórz URL.';
            return;
          }
          box.innerHTML = '<strong>Podłączone przeglądarki/telefony (webpage node):</strong>' + devs.map((d) =>
            '<div class="device" style="margin:4px 0">📱 <code>' + esc(d.name || d.id) + '</code> '
            + '<span class="subtle">' + esc(d.platform || '') + ' · ' + (d.online ? 'online' : 'offline') + '</span> '
            + '<button type="button" onclick="saveWebNode(' + JSON.stringify(d.id) + ',' + JSON.stringify(d.name || d.id) + ',' + JSON.stringify(d.nodeUrl || '') + ')">💾 zapisz jako node</button>'
            + '</div>'
          ).join('');
        } catch (e) { /* service may be down; ignore */ }
      };
      tick();
      _webNodeTimer = setInterval(tick, 4000);
    }

    // Persist a connected webpage-node phone/browser as a node (kind=webpage). Its URL is the service relay endpoint.
    async function saveWebNode(id, name, nodeUrl) {
      try {
        const url = nodeUrl || (($('phoneNodeUrl') || {}).textContent || '');
        const res = await api('/api/nodes/add', { method: 'POST', body: JSON.stringify({ name, url, kind: 'webpage' }) });
        if (typeof load === 'function') load().catch(() => {});
      } catch (e) {}
    }

    // After the phone has installed the APK and is serving on :8765, persist it as a MOBILE node.
    async function savePhoneNode() {
      const name = (($('phoneNodeName') || {}).value || '').trim();
      const url = (($('phoneNodeNodeUrl') || {}).value || '').trim();
      const status = $('phoneNodeSaveStatus');
      if (!name || !url) { if (status) status.textContent = 'podaj nazwę i URL telefonu'; return; }
      if (status) status.textContent = 'zapisuję…';
      try {
        const res = await api('/api/nodes/add', { method: 'POST', body: JSON.stringify({ name, url, kind: 'smartphone' }) });
        if (status) status.textContent = 'zapisano: ' + (res.node ? res.node.name + ' → ' + res.node.url : name);
        if (typeof load === 'function') load().catch(() => {});
      } catch (error) {
        if (status) status.textContent = 'błąd zapisu: ' + error.message;
      }
    }

    // === Node type selector + per-type config forms ===
    function selectNodeKind(kind) {
      document.querySelectorAll('.node-kind-tab').forEach((t) =>
        t.classList.toggle('active', t.dataset.kind === kind));
      document.querySelectorAll('.node-kind-form').forEach((f) =>
        f.style.display = (f.id === 'nodeForm-' + kind) ? '' : 'none');
      // browser-debug/webpage nodes can show a QR: opening it registers a webpage node.
      if (kind === 'browser-debug' || kind === 'webpage') renderConnectQr(kind);
      // webpage = relay only: poll for pages that opened the QR and offer to save them.
      if (kind === 'webpage') startWebpagePolling();
      // Reflect the picked kind in the URL so it is shareable/bookmarkable, like the
      // other dashboard actions (replace: no history spam from tab clicks).
      writeUrlState({ kind }, { replace: true });
    }

    // Render a QR (default for browser-debug/webpage) that encodes the android/webpage service URL.
    async function renderConnectQr(kind) {
      const el = document.getElementById('connectQr-' + kind);
      if (!el || el.dataset.loaded) return;
      try {
        const res = await api('/api/nodes/phone-qr', { method: 'POST', body: JSON.stringify({}) });
        if (res && res.previewUrl) {
          el.innerHTML = '<img src="' + esc(res.previewUrl) + '" alt="QR - otworz jako webpage node">'
            + '<div class="subtle">' + esc(res.url || '') + '</div>';
          el.dataset.loaded = '1';
        }
      } catch (e) { /* service may be down */ }
    }

    // Webpage relay: poll connected pages (devices that opened the QR) and render save buttons.
    let _webpageTimer = null;
    function startWebpagePolling() {
      if (_webpageTimer) return;
      const tick = async () => {
        const box = document.getElementById('webpageNodes');
        if (!box) return;
        try {
          const res = await api('/api/nodes/phone-web');
          const devs = (res && res.devices) || [];
          if (!devs.length) { box.innerHTML = 'Brak podłączonych stron — otwórz QR na urządzeniu (telefon/przeglądarka).'; return; }
          box.innerHTML = '<strong>Podłączone strony (webpage node):</strong>' + devs.map((d) =>
            '<div class="device" style="margin:4px 0">📄 <code>' + esc(d.name || d.id) + '</code> '
            + '<span class="subtle">' + esc(d.platform || '') + ' · ' + (d.online ? 'online' : 'offline') + '</span> '
            + '<button type="button" onclick="saveOneWebpageNode(' + JSON.stringify(d.id) + ',' + JSON.stringify(d.name || d.id) + ',' + JSON.stringify(d.nodeUrl || '') + ')">💾 zapisz</button>'
            + '</div>').join('');
        } catch (e) { /* service down */ }
      };
      tick();
      _webpageTimer = setInterval(tick, 4000);
    }

    async function saveOneWebpageNode(id, name, nodeUrl) {
      try {
        await api('/api/nodes/add', { method: 'POST', body: JSON.stringify({ name, url: nodeUrl, kind: 'webpage' }) });
        if (typeof load === 'function') load().catch(() => {});
      } catch (e) {}
    }

    // Save the first connected page under the typed name (when you just want one webpage node).
    async function saveWebpageNode() {
      const name = ((document.getElementById('webName') || {}).value || '').trim();
      const status = document.getElementById('webStatus');
      if (!name) { if (status) status.textContent = 'podaj nazwę'; return; }
      try {
        const res = await api('/api/nodes/phone-web');
        const dev = ((res && res.devices) || [])[0];
        if (!dev) { if (status) status.textContent = 'najpierw otwórz QR na urządzeniu (brak podłączonych stron)'; return; }
        await api('/api/nodes/add', { method: 'POST', body: JSON.stringify({ name, url: dev.nodeUrl, kind: 'webpage' }) });
        if (status) status.textContent = 'zapisano: ' + name + ' → ' + dev.nodeUrl;
        if (typeof load === 'function') load().catch(() => {});
      } catch (e) { if (status) status.textContent = 'błąd: ' + e.message; }
    }

    // Option B (CDP page-scope): live QR encoding the endpoint URL the user types, so the
    // debug endpoint can be transferred to another device/tool. Uses the generic /api/nodes/qr.
    function updateEndpointQr(inputId, boxId) {
      const url = ((document.getElementById(inputId) || {}).value || '').trim();
      const box = document.getElementById(boxId);
      if (!box) return;
      if (!url) { box.innerHTML = '<span class="subtle">wpisz endpoint CDP — QR pojawi się tutaj</span>'; return; }
      box.innerHTML = '<img src="/api/nodes/qr?url=' + encodeURIComponent(url) + '" alt="QR endpointu CDP">'
        + '<div class="subtle">' + esc(url) + '</div>';
    }

    // Generic typed-node save: persists name + url + kind via /api/nodes/add.
	    async function saveTypedNode(kind, nameId, url) {
	      const name = ((document.getElementById(nameId) || {}).value || '').trim();
	      const status = document.getElementById(kind === 'server' ? 'srvStatus'
	        : kind === 'pc' ? 'pcStatus' : kind === 'rdp' ? 'rdpStatus'
	        : kind === 'browser-debug' ? 'brStatus'
	        : kind === 'browser-chrome-plugin' ? 'chromePluginStatus'
	        : kind === 'browser-firefox-plugin' ? 'firefoxPluginStatus'
	        : 'webStatus');
      url = (url || '').trim();
      if (!name || !url) { if (status) status.textContent = 'podaj nazwę i URL/endpoint'; return; }
      if (status) status.textContent = 'zapisuję…';
      try {
        const res = await api('/api/nodes/add', { method: 'POST', body: JSON.stringify({ name, url, kind }) });
        if (status) status.textContent = 'zapisano (' + kind + '): ' + (res.node ? res.node.url : name);
        if (typeof load === 'function') load().catch(() => {});
      } catch (error) {
	        if (status) status.textContent = 'błąd zapisu: ' + error.message;
	      }
	    }

	    async function saveApiNode() {
	      const status = $('apiNodeStatus');
	      const name = (($('apiNodeName') || {}).value || '').trim();
	      const url = (($('apiNodeUrl') || {}).value || '').trim();
	      const apiId = (($('apiNodeApiId') || {}).value || 'main').trim();
	      const apiKind = (($('apiNodeApiKind') || {}).value || 'rest').trim();
	      const authType = (($('apiNodeAuthType') || {}).value || '').trim();
	      const secret = (($('apiNodeSecret') || {}).value || '').trim();
	      if (!name || !url) { if (status) status.textContent = 'podaj nazwę i URL API'; return; }
	      const apiDef = {id: apiId, kind: apiKind, url};
	      if (authType || secret) apiDef.auth = {type: authType || 'bearer', token: secret};
	      if (status) status.textContent = 'zapisuję…';
	      try {
	        const res = await api('/api/nodes/api/add', {
	          method: 'POST',
	          body: JSON.stringify({name, url, kind: 'api', apis: [apiDef]}),
	        });
	        if (!res.ok) throw new Error(res.error || 'nie udało się zapisać API node');
	        if ($('apiNodeSecret')) $('apiNodeSecret').value = '';
	        if (status) status.textContent = 'zapisano API node: ' + (res.node ? res.node.url : name);
	        if (typeof load === 'function') load().catch(() => {});
	      } catch (error) {
	        if (status) status.textContent = 'błąd zapisu: ' + error.message;
	      }
	    }

	    async function saveDeviceNode() {
	      const status = $('deviceNodeStatus');
	      const name = (($('deviceNodeName') || {}).value || '').trim();
	      const url = (($('deviceNodeUrl') || {}).value || '').trim();
	      if (!name || !url) { if (status) status.textContent = 'podaj nazwę i główny URL urządzenia'; return; }
	      let apis = [];
	      try {
	        apis = JSON.parse((($('deviceNodeApis') || {}).value || '[]').trim() || '[]');
	        if (!Array.isArray(apis)) throw new Error('apis[] musi być tablicą JSON');
	      } catch (error) {
	        if (status) status.textContent = 'błąd JSON apis[]: ' + error.message;
	        return;
	      }
	      if (status) status.textContent = 'zapisuję…';
	      try {
	        const res = await api('/api/nodes/api/add', {
	          method: 'POST',
	          body: JSON.stringify({name, url, kind: 'device', apis}),
	        });
	        if (!res.ok) throw new Error(res.error || 'nie udało się zapisać device node');
	        if (status) status.textContent = 'zapisano device node: ' + (res.node ? res.node.url : name);
	        if (typeof load === 'function') load().catch(() => {});
	      } catch (error) {
	        if (status) status.textContent = 'błąd zapisu: ' + error.message;
	      }
	    }

	    function srvUrl() {
      const host = (($('srvHost') || {}).value || '').trim();
      const port = (($('srvPort') || {}).value || '8765').trim();
      return host ? ('http://' + host + ':' + port) : '';
    }
    function srvSnippet() {
      const host = (($('srvHost') || {}).value || 'HOST').trim() || 'HOST';
      const user = (($('srvUser') || {}).value || 'user').trim() || 'user';
      const port = (($('srvPort') || {}).value || '8765').trim() || '8765';
      const el = $('srvSnippet');
      if (el) el.textContent = 'ssh ' + user + '@' + host
        + ' "curl -fsSL https://get.ifuri.com/node.sh | bash -s -- --name ' + host + ' --port ' + port + ' --background"';
    }
    function rdpSnippet() {
      const host = (($('rdpHost') || {}).value || 'HOST').trim() || 'HOST';
      const port = (($('rdpPort') || {}).value || '3389').trim() || '3389';
      const el = $('rdpSnippet');
      if (el) el.textContent = 'xfreerdp /v:' + host + ':' + port + ' /u:USER /p:PASS /cert:ignore';
    }

    // Start the android-node service (port 8195) from the host so the smartphone QR works.
    async function startPhoneService() {
      const status = $('addPhoneNodeStatus');
      if (status) status.textContent = 'uruchamiam serwis android-node…';
      try {
        const res = await api('/api/nodes/phone-service/start', { method: 'POST', body: JSON.stringify({}) });
        if (status) status.textContent = res.ok
          ? (res.alreadyRunning ? 'serwis już działał ✅' : 'serwis uruchomiony ✅') + ' (' + (res.url || '') + ')'
          : 'nie udało się: ' + (res.error || '');
      } catch (error) {
        if (status) status.textContent = 'błąd: ' + error.message;
      }
    }

    async function restartPhoneService() {
      const status = $('addPhoneNodeStatus');
      if (status) status.textContent = 'restartuję serwis android-node…';
      try {
        const res = await api('/api/uri/invoke', {
          method: 'POST',
          body: JSON.stringify({
            uri: 'dashboard://host/service/android-node/command/restart',
            mode: 'execute',
            payload: { forcePortKill: true }
          })
        });
        const result = res.result || res;
        if (status) status.textContent = res.ok && result.ok !== false
          ? 'restart 8195 zaplanowany/wykonany ✅ ' + ((result.url || res.url || '') ? '(' + (result.url || res.url) + ')' : '')
          : 'restart nieudany: ' + (result.error || res.error || result.reason || 'unknown error');
      } catch (error) {
        if (status) status.textContent = 'błąd: ' + error.message;
      }
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
        if (status) status.innerHTML = renderTokenVerdict(res, name);
      } catch (error) {
        if (status) status.textContent = 'błąd: ' + error.message;
      }
    }

    // Green/red verdict after saving a node token: did it actually authorize the node?
    function renderTokenVerdict(res, name) {
      const chk = (res && res.check) || {};
      if (res && res.valid === true) {
        return '<span style="color:#16a34a;font-weight:600">🟢 token poprawny</span> — zapisany w keyring, autoryzuje node ' + esc(name);
      }
      if (res && res.valid === false) {
        let msg = '<span style="color:#dc2626;font-weight:600">🔴 token niepoprawny</span> — node odrzucił: ' + esc(chk.tokenReason || 'unauthorized');
        if (chk.keyValid) msg += '<br><span style="color:#16a34a">✓ ale autoryzacja kluczem (uri-copy-id) działa — token jest zbędny</span>';
        else if (chk.keyAuth) msg += '<br><span class="subtle">ten node używa key-auth — enrolluj klucz: uri-copy-id</span>';
        return msg;
      }
      // valid === null/undefined: stored, but could not verify (node unreachable, no URL)
      return '<span style="color:#a16207">🟡 zapisano w keyring, nie zweryfikowano</span> — ' + esc((chk && chk.reason) || 'węzeł niedostępny');
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
	          <span class="contact-meta">${esc(contact.meta || contact.url || '')}</span>
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
          meta: node.displayUrl && node.displayUrl !== node.url
            ? ('device: ' + node.displayUrl + (node.relayUrl || node.url ? ' | relay: ' + (node.relayUrl || node.url) : ''))
            : (node.url || ''),
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
      if (Array.isArray(summary.objects) && summary.objects.length) {
        return summary.objects.map((item) => ({
          ...item,
          routes: dedupeRoutes((item.routes || []).map((route) => normalizeRoute(route, item))),
        }));
      }
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

    let _loadArtifactsInflight = false;
    async function loadArtifacts() {
      if (_loadArtifactsInflight) return;
      _loadArtifactsInflight = true;
      try {
        const data = await api('/api/artifacts?limit=80');
        state.artifacts = data.artifacts || [];
        renderArtifacts(state.artifacts);
      } finally {
        _loadArtifactsInflight = false;
      }
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
        if (att.kind === 'twin-plan') return true;
        if (att.kind === 'twin-monitor') return true;
        if (isPdfAttachment(att)) return true;
        if (hasPdf && isScannerFrameAttachment(att)) return false;
        if (isScannerFrameAttachment(att) && !(document.ok && document.path)) return false;
        return true;
      });
    }

    function renderTwinPlanCard(att) {
      const plan = att.plan || {};
      const env = att.environment || {};
      const mock = att.mock;
      const sel = plan.browserSelection || {};
      const steps = (plan.steps || []);
      const constraints = (env.constraints || []);
      const domain = att.domain || '';
      const taskType = att.taskType || 'task';
      const needsAuth = att.needsAuth;

      // ── session selection badge ──────────────────────────────────────────────
      const selMode = sel.mode || '';
      const selBadge = selMode === 'attach'
        ? `<span class="pill up" title="${esc(sel.reason||'')}">CDP attach :${esc(String(sel.port||''))}${sel.authCookie ? ' 🔑' : ''}</span>`
        : selMode === 'needs-login'
        ? `<span class="pill warn" title="${esc(sel.reason||'')}">⚠ login required (human-gated)</span>`
        : selMode === 'no-chrome'
        ? `<span class="pill down">no CDP Chrome found</span>`
        : '';

      // ── steps table ─────────────────────────────────────────────────────────
      const stepRows = steps.map(s => {
        const feasMark = s.feasible ? '✓' : '✗';
        const feasCls = s.feasible ? 'color:var(--ok)' : 'color:var(--err)';
        const revMark = s.reversible ? '↩' : '—';
        const surf = s.surface || '';
        const uri = (s.uri || '').replace(/^kvm:\/\/[^/]+\//, '');
        const fixHint = !s.feasible && s.fix ? ` → fix: ${s.fix}` : '';
        return `<tr>
          <td style="padding:2px 6px;color:var(--subtle)">${s.step}</td>
          <td style="padding:2px 6px;font-family:monospace;font-size:0.82em">${esc(uri)}</td>
          <td style="padding:2px 6px;font-size:0.8em">${esc(surf)}</td>
          <td style="padding:2px 6px;${feasCls}">${feasMark}${esc(fixHint)}</td>
          <td style="padding:2px 6px;color:var(--subtle)">${revMark}</td>
        </tr>`;
      }).join('');

      const stepsHtml = steps.length ? `
        <table style="width:100%;border-collapse:collapse;margin:4px 0">
          <thead><tr style="font-size:0.78em;color:var(--subtle)">
            <th style="padding:2px 6px;text-align:left">#</th>
            <th style="padding:2px 6px;text-align:left">URI</th>
            <th style="padding:2px 6px;text-align:left">surface</th>
            <th style="padding:2px 6px;text-align:left">feasible</th>
            <th style="padding:2px 6px;text-align:left">rev</th>
          </tr></thead>
          <tbody>${stepRows}</tbody>
        </table>` : '<div class="subtle" style="font-size:0.82em">no steps derived</div>';

      // ── Docker mock section ──────────────────────────────────────────────────
      const mockHtml = mock ? `
        <details style="margin-top:6px">
          <summary style="cursor:pointer;font-size:0.82em;color:var(--subtle)">
            Docker mock: ${esc(mock.service || '')} (port ${mock.port || ''})
          </summary>
          <pre style="margin:4px 0;font-size:0.78em;overflow-x:auto;background:var(--bg2);padding:6px;border-radius:3px">${esc(mock.dockerCompose || '')}</pre>
          <div style="font-size:0.8em;margin-top:2px">
            <code>${esc(mock.startCmd || '')}</code><br>
            <code style="color:var(--subtle)">${esc(mock.stopCmd || '')}</code>
          </div>
          ${(mock.notes||[]).map(n=>`<div class="subtle" style="font-size:0.78em">• ${esc(n)}</div>`).join('')}
        </details>` : '';

      // ── constraints summary ──────────────────────────────────────────────────
      const constraintsHtml = constraints.length ? constraints.map(c =>
        `<div style="font-size:0.8em;color:var(--warn,#f59e0b)">⚠ ${esc(c.what||'')} — ${esc(c.reason||'')}${c.fix ? ` → ${esc(c.fix)}` : ''}</div>`
      ).join('') : '';

      const domainTag = domain ? `<span class="pill" style="font-size:0.78em">${esc(domain)}</span>` : '';
      const authTag = needsAuth ? `<span class="pill" style="font-size:0.78em;background:var(--warn,#f59e0b20)">auth required</span>` : '';
      const humanGated = plan.humanGated ? `<div style="color:var(--warn,#f59e0b);font-size:0.82em;margin:4px 0">⚠ human-gated: ${esc(plan.guidance||plan.blockedBy||'')}</div>` : '';

      return `<div class="attachment" style="border:1px solid var(--border-color);border-radius:4px;padding:8px 10px;width:100%;box-sizing:border-box">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">
          <span style="font-weight:600;font-size:0.88em">🤖 Digital Twin Plan</span>
          ${domainTag}${authTag}
          <span class="subtle" style="font-size:0.78em;margin-left:auto">${esc(taskType)}</span>
        </div>
        ${selBadge ? `<div style="margin-bottom:4px">${selBadge}</div>` : ''}
        ${humanGated}
        ${constraintsHtml}
        <div style="margin:4px 0">
          <span style="font-size:0.8em;color:var(--subtle)">${plan.totalSteps||0} steps · ${plan.feasibleSteps||0} feasible · ${plan.infeasibleSteps||0} blocked · ${plan.irreversibleSteps||0} irreversible</span>
        </div>
        ${stepsHtml}
        ${mockHtml}
        <details style="margin-top:4px"><summary style="font-size:0.75em;color:var(--subtle);cursor:pointer">raw data</summary><pre style="font-size:0.72em;overflow-x:auto">${esc(JSON.stringify(att, null, 2))}</pre></details>
      </div>`;
    }

    function renderAttachment(att) {
      if (att.kind === 'twin-plan') {
        return renderTwinPlanCard(att);
      }
      if (att.kind === 'twin-monitor') {
        const url = att.uri || '/twin';
        return `<div class="attachment attachment-widget"><iframe src="${esc(url)}" title="Digital Twin Monitor" loading="lazy"></iframe></div>`;
      }
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
        ${qrDetails(service.url || service.bindUrl || ('/services/view?target=' + encodeURIComponent(target)), service.name || target, 'widget')}
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

    let _loadServiceViewsInflight = false;
    async function loadServiceViews() {
      if (_loadServiceViewsInflight) return;
      _loadServiceViewsInflight = true;
      try {
        const data = await api('/api/services/live?limit=8');
        state.serviceViews = data.views || [];
        renderServiceViews();
        renderChatHistory();
      } finally {
        _loadServiceViewsInflight = false;
      }
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

    let _loadChatHistoryInflight = false;
    async function loadChatHistory() {
      if (_loadChatHistoryInflight) return;
      _loadChatHistoryInflight = true;
      try {
        const history = await api('/api/chat/history?limit=80');
        state.chatMessages = history.messages || [];
        renderChatHistory();
      } finally {
        _loadChatHistoryInflight = false;
      }
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
    $('chatTwinBtn').addEventListener('click', () => {
      const el = $('chatTwinEmbed');
      if (el) { el.remove(); return; }
      const wrap = document.createElement('div');
      wrap.id = 'chatTwinEmbed';
      wrap.style.cssText = 'width:100%;margin:8px 0;border:1px solid var(--border-color);border-radius:4px;overflow:hidden;';
      const fr = document.createElement('iframe');
      fr.src = '/twin?source=live';
      fr.style.cssText = 'width:100%;height:340px;border:none;display:block;';
      fr.title = 'Digital Twin Monitor';
      wrap.appendChild(fr);
      $('chatResult').parentNode.insertBefore(wrap, $('chatResult'));
    });
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
    // Restore a node-kind tab from ?kind=… (shareable deep link), if it names a real tab.
    const initialKind = params.get('kind');
    if (initialKind && document.querySelector('.node-kind-tab[data-kind="' + initialKind + '"]')) {
      selectNodeKind(initialKind);
    }
    writeUrlState({ action: params.get('action') || 'load' }, { replace: true });
    renderChatHistory();
    setInterval(() => loadChatHistory().catch(() => {}), 4000);
    setInterval(() => loadServiceViews().catch(() => {}), 2000);
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

NODE_TYPES_DOC_HTML = r"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>urirun — typy node i konfiguracja połączeń</title>
<style>
  body { max-width: 820px; margin: 0 auto; padding: 2rem 1rem; font-family: system-ui, sans-serif;
         line-height: 1.6; color: #e2e8f0; background: #0f172a; }
  h1 { color: #38bdf8; } h2 { color: #38bdf8; margin-top: 2rem; border-top: 1px solid #334155; padding-top: 1rem; }
  code, pre { font-family: ui-monospace, monospace; background: #0d1117; border-radius: 4px; }
  code { padding: 1px 5px; color: #4ade80; } pre { display: block; padding: .8rem; overflow-x: auto; color: #4ade80; }
  table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
  th, td { border: 1px solid #334155; padding: 6px 10px; text-align: left; font-size: .9rem; }
  th { background: #1e293b; color: #38bdf8; }
  a { color: #38bdf8; } .lead { color: #94a3b8; }
</style>
</head>
<body>
<h1>Typy node i konfiguracja połączeń</h1>
<p class="lead">Każdy node ma inny poziom integracji i wymaga innej wiedzy. Wybierz typ pasujący do
maszyny/urządzenia i postępuj według sekcji poniżej. Wszystkie node wystawiają trasy <code>URI</code>,
ale różnią się <strong>transportem</strong> i tym, <strong>co</strong> potrafią.</p>

<table>
  <tr><th>Typ</th><th>Transport</th><th>Wymagana wiedza</th><th>Connector</th></tr>
  <tr><td>🖥️ server</td><td>shell / SSH</td><td>SSH, instalacja zdalna</td><td>get-node + shell</td></tr>
  <tr><td>💻 pc</td><td>aplikacja + shell</td><td>pulpit, terminal</td><td>get-node + kvm</td></tr>
  <tr><td>🪟 rdp</td><td>pulpit zdalny (RDP)</td><td>RDP, login Windows</td><td>kvm / rdp</td></tr>
  <tr><td>📱 smartphone</td><td>webpage → APK/Termux</td><td>instalacja apki, sieć LAN</td><td>android-node + adb</td></tr>
  <tr><td>🌐 browser-debug</td><td>DevTools (CDP)</td><td>uruchomienie z debug portem</td><td>webnode</td></tr>
  <tr><td>🧩 browser-chrome-plugin</td><td>Chrome Extension</td><td>Load unpacked, permissions</td><td>chrome-plugin</td></tr>
  <tr><td>🧩 browser-firefox-plugin</td><td>Firefox Extension</td><td>Temporary Add-on, permissions</td><td>firefox-plugin</td></tr>
  <tr><td>📄 webpage</td><td>HTML/JS na stronie</td><td>CDP, plugin albo page bridge</td><td>webnode / js-urirun-com</td></tr>
  <tr><td>🔌 api</td><td>HTTP/REST/OpenAPI</td><td>URL API + auth</td><td>http-api / fetch / oauth</td></tr>
  <tr><td>🧩 device</td><td>wiele protokołów</td><td>panel, RTSP, SSH, SMB/NAS</td><td>camera / rtsp / ssh / smb</td></tr>
</table>

<h2 id="server">🖥️ Server — shell / SSH</h2>
<p>Headless maszyna (VPS, serwer). Sterowanie przez shell; węzeł urirun instalujesz zdalnie po SSH.</p>
<p><strong>Potrzebujesz:</strong> dostęp SSH (<code>user@host</code>), prawa do instalacji.</p>
<pre>ssh user@HOST "curl -fsSL https://get.ifuri.com/node.sh | bash -s -- --name HOST --port 8765 --background"</pre>
<p>Następnie w dashboardzie zapisz node z URL <code>http://HOST:8765</code>. Test: <code>http://HOST:8765/health</code>.</p>

<h2 id="pc">💻 PC — aplikacja + shell</h2>
<p>Maszyna z GUI (laptop, desktop). Uruchamiasz węzeł lokalnie lub przez aplikację ifURI; dochodzi
sterowanie pulpitem (connector <code>kvm</code>: zrzut ekranu, klawiatura, mysz).</p>
<pre>curl -fsSL https://get.ifuri.com/node.sh | bash -s -- --name pc --port 8765 --background</pre>
<p>Zapisz node z URL <code>http://IP-PC:8765</code>.</p>

<h2 id="rdp">🪟 RDP — pulpit zdalny</h2>
<p>Windows/xrdp przez RDP (port 3389). Łączysz się z pulpitem i sterujesz nim; po stronie pulpitu
działa węzeł urirun z connectorem KVM.</p>
<p><strong>Potrzebujesz:</strong> host RDP, login, klient RDP (np. <code>xfreerdp</code>).</p>
<pre>xfreerdp /v:HOST:3389 /u:USER /p:PASS /cert:ignore</pre>
<p>Na pulpicie uruchom węzeł (jak PC) i zapisz node z URL <code>http://HOST:8765</code>.</p>

<h2 id="smartphone">📱 Smartphone — webpage node → mobile node</h2>
<p>Dwa etapy integracji telefonu:</p>
<ol>
  <li><strong>Webpage node (od razu):</strong> uruchom serwis android-node/webpage i otwórz jego URL w przeglądarce
  telefonu. Przeglądarka rejestruje się jako <code>webpage</code> node — sterowanie przez
  JS na otwartej stronie: nawigacja, eval, lista urządzeń, kamera i akcje strony. Nic nie instalujesz.</li>
  <li><strong>Mobile node (pełny):</strong> ze strony pobierasz APK lub uruchamiasz skrypt Termux.
  Telefon staje się pełnym węzłem (port 8765): pliki, system, wejście — przez connector <code>adb</code>.</li>
</ol>
<pre>urirun-android-node serve     # serwis dystrybucji (port 8195), QR + APK + bootstrap</pre>
<p>W dashboardzie: <em>Smartphone → Uruchom serwis android-node → Pokaż QR</em>. Zeskanuj telefonem.
Podłączone telefony pojawią się na liście „webpage node"; po instalacji APK zapisz je jako „mobile node".</p>

<h2 id="browser-debug">🌐 Browser Debug — cała przeglądarka (CDP)</h2>
<p>Sterowanie całą przeglądarką przez Chrome DevTools Protocol: wszystkie karty (otwórz/zamknij/nawiguj),
status, zrzuty. Connector <code>webnode</code>, zakres <code>browser</code>. Stary typ <code>browser</code>
jest aliasem do <code>browser-debug</code>.</p>
<pre>google-chrome --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1</pre>
<pre>urirun run "webnode://browser/tabs/query/list" --entry-points --execute --allow 'webnode://*'</pre>
<p>Zapisz node z endpointem <code>http://127.0.0.1:9222</code> i typem <code>browser-debug</code>.</p>

<h2 id="browser-chrome-plugin">🧩 Chrome Plugin — aktywna karta przez rozszerzenie</h2>
<p>Tryb bez debug portu. Rozszerzenie działa w aktywnej karcie, obsługuje
<code>browser-plugin://chrome/...</code> oraz kompatybilne <code>browser://...</code>,
a inne URI przekazuje do skonfigurowanego node <code>/run</code>.</p>
<pre>cd /home/tom/github/if-uri/chrome-plugin
make test
# chrome://extensions -> Developer mode -> Load unpacked -> ten folder</pre>

<h2 id="browser-firefox-plugin">🧩 Firefox Plugin — aktywna karta przez rozszerzenie</h2>
<p>Analogiczny tryb dla Firefox. Rozszerzenie obsługuje
<code>browser-plugin://firefox/...</code> oraz kompatybilne <code>browser://...</code>.</p>
<pre>cd /home/tom/github/if-uri/firefox-plugin
make test
# about:debugging#/runtime/this-firefox -> Load Temporary Add-on</pre>

<h2 id="webpage">📄 Webpage — pojedyncza strona (HTML/JS)</h2>
<p>Sterowanie <strong>konkretną stroną/kartą</strong>: nawigacja, eval JS, klik po selektorze,
wpisywanie, zrzut, lista urządzeń strony, kamera, sensory, iframe/proxy. Może działać przez
CDP page scope, plugin albo page bridge na porcie <code>8195</code>. Stary typ <code>web</code>
jest aliasem do <code>webpage</code>.</p>
<pre># lista kart i ich id:
urirun run "webnode://browser/tabs/query/list" --entry-points --execute --allow 'webnode://*'
# steruj jedną stroną:
WEBNODE_TARGET=&lt;id&gt; urirun run "webnode://page/command/navigate" \
  --entry-points --execute --allow 'webnode://*' --payload '{"url":"https://example.com"}'</pre>
<p>Zapisz node z endpointem CDP i typem <code>webpage</code>, albo otwórz QR z serwisu
<code>8195</code>, żeby strona zarejestrowała się jako webpage node.</p>

<h2 id="api">🔌 API — zewnętrzny endpoint z autoryzacją</h2>
<p>API node służy do podpinania SaaS, lokalnych usług HTTP, REST/OpenAPI albo paneli sterowania.
Sekret przekazany w formularzu jest zapisywany w keyring jako <code>secretRef</code>, a nie w pliku config.</p>
<pre>urirun host add-node crm-api https://api.example.test/v1 \
  --kind api --api-id main --api-kind rest \
  --auth-type bearer --auth-token PASTE_ONCE</pre>
<pre>{
  "name": "crm-api",
  "url": "https://api.example.test/v1",
  "kind": "api",
  "apis": [
    {"id": "main", "kind": "rest", "url": "https://api.example.test/v1",
     "auth": {"type": "bearer", "token": "PASTE_ONCE"}}
  ]
}</pre>
<p>Discovery pokazuje wtedy route'y konfiguracyjne, np. <code>api://crm-api/main/command/request</code>.</p>
<p>HTTP/REST/OpenAPI może być wykonane bezpośrednio przez hosta. Przykład payloadu:</p>
<pre>{
  "uri": "api://crm-api/main/command/request",
  "mode": "execute",
  "payload": {"method": "GET", "path": "/accounts", "query": {"limit": 10}}
}</pre>
<p>Wariant neutralny dla plannerów to <code>configured://host/node-api/command/request</code>
z payloadem zawierającym <code>node</code> i <code>apiId</code>.</p>

<h2 id="device">🧩 Device — kamera, RPi, NAS, nietypowe urządzenie</h2>
<p>Device node ma wiele interfejsów API. Przykład: RPi jako kamera i NAS ma panel WWW,
RTSP stream, SMB share i SSH shell. Jeden obiekt node grupuje je jako <code>apis[]</code>.</p>
<pre>urirun host add-node rpi-camera http://rpi.local \
  --kind device \
  --api '{"id":"panel","kind":"web","url":"http://rpi.local"}' \
  --api '{"id":"stream","kind":"rtsp","role":"camera","url":"rtsp://rpi.local/live"}' \
  --api '{"id":"share","kind":"smb","url":"smb://rpi.local/share"}' \
  --api '{"id":"ssh","kind":"ssh","url":"ssh://pi@rpi.local"}'</pre>
<pre>{
  "name": "rpi-camera",
  "url": "http://rpi.local",
  "kind": "device",
  "apis": [
    {"id": "panel", "kind": "web", "url": "http://rpi.local"},
    {"id": "stream", "kind": "rtsp", "role": "camera", "url": "rtsp://rpi.local/live"},
    {"id": "share", "kind": "smb", "url": "smb://rpi.local/share"},
    {"id": "ssh", "kind": "ssh", "url": "ssh://pi@rpi.local"}
  ]
}</pre>
<p>Discovery tworzy syntetyczne route'y: <code>device://</code>, <code>media://</code>,
<code>camera://</code>, <code>ssh://</code> i <code>fs://</code>. Wykonanie tych route'ów
powinny przejąć odpowiednie connectory. Host wykona tylko interfejsy HTTP-like;
dla RTSP/SMB/SSH zwróci <code>connector_required</code>, zamiast udawać wykonanie.</p>

<p class="lead" style="margin-top:2rem">⬅ <a href="/?view=nodes">Powrót do dashboardu</a></p>
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

    let _pollPageActionsInflight = false;
    async function pollPageActions() {
      if (_pollPageActionsInflight) return;
      if (!window.urirun || typeof window.urirun.invoke !== 'function') return;
      _pollPageActionsInflight = true;
      let data = null;
      try {
        const response = await fetch('/api/page/actions/poll?target=scanner&limit=4', {cache: 'no-store'});
        data = await response.json();
      } catch (_) {
        _pollPageActionsInflight = false;
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
      _pollPageActionsInflight = false;
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

