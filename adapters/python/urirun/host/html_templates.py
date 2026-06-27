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
  <link rel="stylesheet" href="/dashboard.css">
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
  <script src="/dashboard.js"></script>
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
  <script src="/scanner.js"></script>
</body>
</html>
"""

