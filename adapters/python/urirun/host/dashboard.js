    const VALID_VIEWS = new Set(['overview', 'chat', 'discovery', 'artifacts', 'widgets', 'twin', 'tasks', 'host', 'nodes', 'activity']);
    const params = new URLSearchParams(window.location.search);
    const initialView = VALID_VIEWS.has(params.get('view')) ? params.get('view') : (VALID_VIEWS.has(params.get('tab')) ? params.get('tab') : 'overview');
    const initialChatFull = params.get('chat') === 'full' || params.get('fullscreen') === 'chat';
    const initialTargets = (urlTargetsAreImplicitAutorun(params) ? 'host' : (params.get('targets') || 'host'))
      .split(',').map((item) => item.trim()).filter(Boolean);
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

    function linkify(value) {
      return esc(value).replace(
        /https?:\/\/[^\s&,;'"<>]+/g,
        (url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`
      );
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

    function applyUrlChatExecute(search) {
      if (!$('chatExecute')) return;
      $('chatExecute').checked = search.get('execute') !== '0';
      $('chatMode').textContent = $('chatExecute').checked ? 'execute' : 'dry-run';
    }

    function applyUrlChatPrompt(search) {
      if ($('chatPrompt') && (search.has('prompt') || search.has('message'))) {
        $('chatPrompt').value = search.get('prompt') || search.get('message') || '';
      }
    }

    function applyUrlFilterControls(search) {
      if ($('sprintFilter') && search.get('sprint')) $('sprintFilter').value = search.get('sprint');
      if ($('queueFilter') && search.has('queue')) $('queueFilter').value = search.get('queue') || '';
      applyUrlChatExecute(search);
      if ($('chatNoLlm')) $('chatNoLlm').checked = search.get('no_llm') === '1' || search.get('noLlm') === '1';
      applyUrlChatPrompt(search);
    }

    function applyUrlTargetControls(search) {
      const implicitAutorun = urlTargetsAreImplicitAutorun(search);
      const targets = (implicitAutorun ? 'host' : (search.get('targets') || 'host')).split(',').map((item) => item.trim()).filter(Boolean);
      state.selectedTargets = targets.length ? targets : ['host'];
      if (!implicitAutorun) {
        (search.get('nodes') || '').split(',').map((item) => item.trim()).filter(Boolean).forEach((node) => {
          const target = node.startsWith('node:') ? node : `node:${node}`;
          if (!state.selectedTargets.includes(target)) state.selectedTargets.push(target);
        });
      }
      const discovery = (search.get('discovery') || search.get('registry') || '').trim();
      if (discovery) state.discoveryTarget = discovery;
    }

    function applyControlsFromUrl() {
      const search = new URLSearchParams(window.location.search);
      applyUrlFilterControls(search);
      applyUrlTargetControls(search);
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
    function gatherTicketFormBody() {
      return {
        name: ($('newTicketName') || {}).value || '',
        description: ($('newTicketDesc') || {}).value || '',
        priority: ($('newTicketPriority') || {}).value || 'normal',
        queue: ($('newTicketQueue') || {}).value || 'default',
        labels: ($('newTicketLabels') || {}).value || '',
      };
    }

    function clearTicketFormFields() {
      if ($('newTicketName')) $('newTicketName').value = '';
      if ($('newTicketDesc')) $('newTicketDesc').value = '';
      if ($('newTicketLabels')) $('newTicketLabels').value = '';
    }

    async function createTicket(extra = {}) {
      const status = $('newTicketStatus');
      const body = { ...gatherTicketFormBody(), ...extra };
      if (!String(body.name).trim() && !String(body.prompt || '').trim()) {
        if (status) status.textContent = 'podaj tytuł (lub użyj \u201eZ promptu czatu\u201d)';
        return;
      }
      if (status) status.textContent = 'tworz\u0119 ticket\u2026';
      try {
        const res = await api('/api/tasks/create', { method: 'POST', body: JSON.stringify(body) });
        const t = res.ticket || {};
        if (status) status.textContent = `utworzono: ${t.id || ''} ${t.name || ''}`;
        clearTicketFormFields();
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

    function buildInstallResultLines(res) {
      const lines = [];
      if (res.command) lines.push('$ ' + res.command);
      if (res.schemes && res.schemes.length) lines.push('schematy URI: ' + res.schemes.join(', '));
      if (res.hint) lines.push('hint: ' + res.hint);
      if (res.stdout) lines.push(res.stdout);
      if (res.stderr) lines.push(res.stderr);
      return lines;
    }

    async function applyInstallResult(res, status, out) {
      if (status) status.textContent = res.ok ? '\u2713 zainstalowano' : '\u2717 ' + (res.error || 'blad');
      const lines = buildInstallResultLines(res);
      if (out) out.textContent = lines.join('\n') || JSON.stringify(res, null, 2);
      if (res.ok && typeof load === 'function') load().catch(() => {});
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
        await applyInstallResult(res, status, out);
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

    async function fetchConnectorTestResult(env, uri, payload) {
      if (env === 'host') {
        return await api('/api/connectors/test', { method: 'POST', body: JSON.stringify({ uri, payload }) });
      }
      const node = env.replace(/^node:/, '');
      return await api('/api/nodes/test-routes', { method: 'POST', body: JSON.stringify({ node, uris: [uri] }) });
    }

    function renderConnectorTestResult(res, status, out) {
      const broken = res.results && res.results.filter ? res.results.filter((r) => r.status && r.status !== 'ok').length : 0;
      const ok = res.ok !== false && broken === 0;
      if (status) status.textContent = ok ? '\u2713 dziala' : '\u2717 blad/niepelne';
      if (out) out.textContent = JSON.stringify(res, null, 2).slice(0, 4000);
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
        const res = await fetchConnectorTestResult(env, uri, payload);
        renderConnectorTestResult(res, status, out);
      } catch (error) {
        if (status) status.textContent = '\u2717 ' + error.message;
        if (out) out.textContent = error.message;
      }
    }

    function renderNodeCard(node) {
      return `<div class="item node-row${state.selectedRoutesNode === node.name ? ' node-row-active' : ''}" data-node="${esc(node.name)}" onclick="selectNodeRoutes(this.dataset.node)" title="Kliknij, aby pokazać procesy URI tego węzła">
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
      </div>`;
    }

    function renderNodes(nodes) {
      $('nodeCount').textContent = `${nodes.length} configured`;
      $('nodesList').innerHTML = nodes.map(renderNodeCard).join('') || empty('No nodes configured — use "➕ Jak dodać node" below to add one.');
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
    function updateHostStatusPill(host) {
      const pill = $('hostStatusPill');
      if (pill) {
        pill.textContent = host.status || (host.reachable ? 'up' : 'local');
        pill.className = 'pill ' + (host.reachable === false ? 'down' : 'up');
      }
    }

    function buildHostConfigRows(summary, host) {
      return [
        { label: 'Host', value: host.label || 'urirun host' },
        { label: 'Katalog projektu', value: summary.project || host.url || '', mono: true, copy: true },
        { label: 'Baza danych (db)', value: summary.db || '', mono: true, copy: true },
        { label: 'Plik konfiguracji', value: summary.config || '', mono: true, copy: true },
        { label: 'Węzły (nodes)', value: `${summary.nodesOnline || 0} online · ${summary.nodeCount || 0} skonfigurowanych` },
        { label: 'Procesy URI hosta', value: `${(summary.hostRoutes || []).length}` },
        { label: 'Usługi (services)', value: `${summary.serviceCount || 0}` },
      ];
    }

    function renderHostConfigRow(row) {
      return `<div class="item">
        <div style="display:flex;align-items:center;gap:8px;justify-content:space-between">
          <span class="subtle">${esc(row.label)}</span>
          ${row.copy && row.value ? `<button type="button" title="Kopiuj" onclick="copyHostValue(this, ${JSON.stringify(row.value).replace(/"/g, '&quot;')})">⧉</button>` : ''}
        </div>
        <div class="${row.mono ? 'mono' : ''}">${esc(row.value) || '<span class="subtle">—</span>'}</div>
      </div>`;
    }

    function renderHostRouteItem(route) {
      return `<div class="item">
        <div class="route-title"><span class="mono">${esc(route.uri)}</span>${route.safe === false ? '<span class="pill down">unsafe</span>' : ''}</div>
        ${route.title ? `<div>${esc(route.title)}</div>` : ''}
        <div class="subtle">${esc(text(route.kind, 'route'))} · ${esc(text(route.layer, 'host'))}${route.source ? ` · ${esc(route.source)}` : ''}</div>
      </div>`;
    }

    function populateConnectorEnvSelector(summary) {
      const envSel = $('connectorTestEnv');
      if (envSel) {
        const cur = envSel.value;
        const nodes = summary.nodes || [];
        envSel.innerHTML = ['<option value="host">host (lokalnie)</option>',
          ...nodes.map((n) => `<option value="node:${esc(n.name)}">node: ${esc(n.name)}${n.reachable ? '' : ' (offline)'}</option>`)].join('');
        if (cur) envSel.value = cur;
      }
    }

    function renderHost(summary) {
      summary = summary || {};
      const host = summary.host || {};
      updateHostStatusPill(host);
      const rows = buildHostConfigRows(summary, host);
      $('hostConfigList').innerHTML = rows.map(renderHostConfigRow).join('');
      const hostRoutes = summary.hostRoutes || [];
      $('hostRouteCount').textContent = `${hostRoutes.length} routes`;
      $('hostRoutesList').innerHTML = hostRoutes.slice(0, 80).map(renderHostRouteItem).join('') || empty('Host nie udostępnia żadnych procesów URI.');
      populateConnectorEnvSelector(summary);
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
    function displayPhoneQrResult(res) {
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
    }

    async function showAddPhoneNodeQR() {
      const status = $('addPhoneNodeStatus');
      if (status) status.textContent = 'generuję QR…';
      try {
        const res = await api('/api/nodes/phone-qr', { method: 'POST', body: JSON.stringify({}) });
        if (!res.ok) throw new Error(res.error || 'nie udało się wygenerować QR');
        displayPhoneQrResult(res);
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
    function inputValue(id) {
      return (($(id) || {}).value || '').trim();
    }
    function setStatusText(el, text) {
      if (el) el.textContent = text;
    }
    async function savePhoneNode() {
      const name = inputValue('phoneNodeName');
      const url = inputValue('phoneNodeNodeUrl');
      const status = $('phoneNodeSaveStatus');
      if (!name || !url) { setStatusText(status, 'podaj nazwę i URL telefonu'); return; }
      setStatusText(status, 'zapisuję…');
      try {
        const res = await api('/api/nodes/add', { method: 'POST', body: JSON.stringify({ name, url, kind: 'smartphone' }) });
        setStatusText(status, 'zapisano: ' + (res.node ? res.node.name + ' → ' + res.node.url : name));
        if (typeof load === 'function') load().catch(() => {});
      } catch (error) {
        setStatusText(status, 'błąd zapisu: ' + error.message);
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
    function typedNodeStatusId(kind) {
      if (kind === 'server') return 'srvStatus';
      if (kind === 'pc') return 'pcStatus';
      if (kind === 'rdp') return 'rdpStatus';
      if (kind === 'browser-debug') return 'brStatus';
      if (kind === 'browser-chrome-plugin') return 'chromePluginStatus';
      if (kind === 'browser-firefox-plugin') return 'firefoxPluginStatus';
      return 'webStatus';
    }

    async function saveTypedNode(kind, nameId, url) {
      const name = ((document.getElementById(nameId) || {}).value || '').trim();
      const status = document.getElementById(typedNodeStatusId(kind));
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

    function gatherApiNodeFields() {
      return {
        name: (($('apiNodeName') || {}).value || '').trim(),
        url: (($('apiNodeUrl') || {}).value || '').trim(),
        apiId: (($('apiNodeApiId') || {}).value || 'main').trim(),
        apiKind: (($('apiNodeApiKind') || {}).value || 'rest').trim(),
        authType: (($('apiNodeAuthType') || {}).value || '').trim(),
        secret: (($('apiNodeSecret') || {}).value || '').trim(),
      };
    }

    function buildApiNodeDef(apiId, apiKind, url, authType, secret) {
      const apiDef = {id: apiId, kind: apiKind, url};
      if (authType || secret) apiDef.auth = {type: authType || 'bearer', token: secret};
      return apiDef;
    }

    async function saveApiNode() {
      const status = $('apiNodeStatus');
      const {name, url, apiId, apiKind, authType, secret} = gatherApiNodeFields();
      if (!name || !url) { if (status) status.textContent = 'podaj nazwę i URL API'; return; }
      const apiDef = buildApiNodeDef(apiId, apiKind, url, authType, secret);
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

    function parseDeviceNodeApis() {
      const raw = (($('deviceNodeApis') || {}).value || '[]').trim() || '[]';
      const apis = JSON.parse(raw);
      if (!Array.isArray(apis)) throw new Error('apis[] musi być tablicą JSON');
      return apis;
    }

    async function saveDeviceNodeApiCall(name, url, apis, status) {
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

    async function saveDeviceNode() {
      const status = $('deviceNodeStatus');
      const name = (($('deviceNodeName') || {}).value || '').trim();
      const url = (($('deviceNodeUrl') || {}).value || '').trim();
      if (!name || !url) { if (status) status.textContent = 'podaj nazwę i główny URL urządzenia'; return; }
      let apis;
      try {
        apis = parseDeviceNodeApis();
      } catch (error) {
        if (status) status.textContent = 'błąd JSON apis[]: ' + error.message;
        return;
      }
      await saveDeviceNodeApiCall(name, url, apis, status);
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
    function gatherNodeTokenInput() {
      const name = (($('addNodeName') || {}).value || '').trim();
      const tokenEl = $('addNodeToken');
      const token = (tokenEl && tokenEl.value) || '';
      return {name, tokenEl, token};
    }

    async function saveNodeToken() {
      const status = $('addNodeTokenStatus');
      const {name, tokenEl, token} = gatherNodeTokenInput();
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
    function gatherNodeTokenForData(btn) {
      const name = btn && btn.dataset ? btn.dataset.node : '';
      const form = btn.closest('.node-token-form');
      const input = form ? form.querySelector('.node-token-input') : null;
      const status = form ? form.querySelector('.node-token-status') : null;
      const token = (input && input.value) || '';
      return {name, input, status, token};
    }

    async function saveNodeTokenFor(btn) {
      const {name, input, status, token} = gatherNodeTokenForData(btn);
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

    function contactCardActions(contact) {
      const isPhoneScanner = contact.id === 'service:phone-scanner';
      const startUri = isPhoneScanner ? 'dashboard://host/phone-scanner/command/start' : '';
      const restartUri = isPhoneScanner ? 'dashboard://host/service/phone-scanner/command/restart' : '';
      return [
        startUri ? `<button type="button" data-contact-action="invoke-uri" data-uri="${esc(startUri)}" data-target="${esc(contact.id)}">Start</button>` : '',
        restartUri ? `<button type="button" data-contact-action="invoke-uri" data-uri="${esc(restartUri)}" data-target="${esc(contact.id)}">Restart</button>` : '',
        contact.url ? `<button type="button" data-contact-action="open-url" data-url="${esc(contact.url)}" data-target="${esc(contact.id)}">Open</button>` : '',
      ].filter(Boolean).join('');
    }

    function contactCard(contact) {
      const checked = state.selectedTargets.includes(contact.id) ? 'checked' : '';
      const disabled = contact.disabled ? 'disabled' : '';
      const pillClass = contact.reachable === false ? 'down' : contact.status === 'running' || contact.reachable ? 'up' : '';
      const inputId = `chat-target-${String(contact.id || 'target').replace(/[^a-zA-Z0-9_-]/g, '-')}`;
      const actions = contactCardActions(contact);
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

    function nodeToContact(node) {
      const meta = node.displayUrl && node.displayUrl !== node.url
        ? ('device: ' + node.displayUrl + (node.relayUrl || node.url ? ' | relay: ' + (node.relayUrl || node.url) : ''))
        : (node.url || '');
      return {
        id: `node:${node.name}`,
        kind: 'node',
        label: `urirun node: ${node.name}`,
        status: node.reachable ? 'up' : 'down',
        reachable: !!node.reachable,
        disabled: !node.reachable,
        url: node.url || '',
        meta,
      };
    }

    function serviceToContact(service) {
      return {
        id: service.id || `service:${service.name}`,
        kind: 'service',
        label: service.label || `urirun service: ${service.name}`,
        status: service.status || (service.reachable ? 'running' : 'stopped'),
        reachable: !!service.reachable,
        url: service.url || '',
        routes: service.routes || [],
      };
    }

    function chatContacts(summary) {
      const nodes = summary.nodes || [];
      const services = summary.services || [];
      return [
        { id: 'host', kind: 'host', label: 'urirun host', status: 'local', reachable: true, url: summary.project || '' },
        ...nodes.map(nodeToContact),
        ...services.map(serviceToContact),
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

    function buildHostDiscoveryObject(summary) {
      const host = summary.host || {};
      const hostOwner = {
        id: 'host',
        kind: 'host',
        label: host.label || 'urirun host',
        status: host.status || 'local',
        reachable: host.reachable !== false,
        url: host.url || summary.project || '',
      };
      return {
        ...hostOwner,
        routes: dedupeRoutes((host.routes || summary.hostRoutes || []).map((route) => normalizeRoute(route, hostOwner))),
      };
    }

    function buildNodeDiscoveryObjects(summary) {
      return (summary.nodes || []).map((node) => {
        const owner = {
          id: `node:${node.name}`,
          kind: 'node',
          label: `urirun node: ${node.name}`,
          status: node.reachable ? 'up' : 'down',
          reachable: !!node.reachable,
          url: node.url || '',
        };
        return { ...owner, routes: dedupeRoutes(routesForNode(summary, node).map((route) => normalizeRoute(route, owner))) };
      });
    }

    function buildServiceDiscoveryObjects(summary) {
      return (summary.services || []).map((service) => {
        const owner = {
          id: service.id || `service:${service.name}`,
          kind: 'service',
          label: service.label || `urirun service: ${service.name}`,
          status: service.status || (service.reachable ? 'running' : 'stopped'),
          reachable: !!service.reachable,
          url: service.url || '',
        };
        return { ...owner, routes: dedupeRoutes((service.routes || []).map((route) => normalizeRoute(route, owner))) };
      });
    }

    function discoveryObjects(summary) {
      if (Array.isArray(summary.objects) && summary.objects.length) {
        return summary.objects.map((item) => ({
          ...item,
          routes: dedupeRoutes((item.routes || []).map((route) => normalizeRoute(route, item))),
        }));
      }
      return [buildHostDiscoveryObject(summary), ...buildNodeDiscoveryObjects(summary), ...buildServiceDiscoveryObjects(summary)];
    }

    function chooseDiscoveryTarget(objects) {
      if (objects.some((item) => item.id === state.discoveryTarget)) return state.discoveryTarget;
      const nodeTarget = state.selectedTargets.find((target) => target.startsWith('node:') && objects.some((item) => item.id === target));
      if (nodeTarget) return nodeTarget;
      const serviceTarget = state.selectedTargets.find((target) => target.startsWith('service:') && objects.some((item) => item.id === target));
      if (serviceTarget) return serviceTarget;
      return objects.length ? objects[0].id : 'host';
    }

    function discoveryTargetButton(item) {
      const active = item.id === state.discoveryTarget ? 'active' : '';
      const pillClass = item.reachable === false ? 'down' : 'up';
      return `<button type="button" class="discovery-target ${active}" data-discovery-target="${esc(item.id)}">
          <div><strong>${esc(item.label)}</strong> <span class="pill ${pillClass}">${esc(item.status || item.kind)}</span></div>
          <div class="mono">${esc(item.id)}</div>
          <div class="subtle">${esc(item.url || '')}</div>
          <div class="subtle">${item.routes.length} URI routes · ${esc(item.kind || '')}</div>
        </button>`;
    }

    function discoveryRouteRow(route) {
      return `<div class="item">
        <div class="route-title"><span class="mono">${esc(route.uri)}</span>${route.safe === false ? '<span class="pill down">unsafe</span>' : ''}</div>
        ${route.title ? `<div>${esc(route.title)}</div>` : ''}
        <div class="subtle">${esc(route.ownerLabel)} · ${esc(route.kind || 'route')} · ${esc(route.adapter || 'registry')} · target:${esc(route.target)}</div>
      </div>`;
    }

    function renderDiscovery(summary) {
      const objects = discoveryObjects(summary);
      state.discoveryTarget = chooseDiscoveryTarget(objects);
      const selected = objects.find((item) => item.id === state.discoveryTarget) || objects[0] || null;
      $('discoveryCount').textContent = `${objects.length} objects`;
      $('discoveryList').innerHTML = objects.map(discoveryTargetButton).join('') || empty('No URI objects discovered');
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
      $('discoveryRoutesList').innerHTML = selected.routes.map(discoveryRouteRow).join('') || empty('No URI routes for this object');
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
      const badge = { 'ok': '✅', 'degraded': '⚠️', 'handler-error': '⚠️', 'not-found': '⛔', 'unreachable': '🚫' };
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

    function artifactRowLinks(url) {
      return {
        openLink: url ? `<a href="${esc(url)}" target="_blank" rel="noreferrer">open</a>` : '',
        download: url ? `<a href="${esc(url)}" download>download</a>` : '',
      };
    }

    function artifactRowBadges(item, id, path) {
      const duplicateCount = Number(item.duplicateCount || 0);
      return {
        missing: path && item.fileExists === false ? '<span class="pill down">missing file</span>' : '',
        selected: id && state.selectedArtifactIds.has(id) ? 'checked' : '',
        duplicates: duplicateCount > 1 ? `<span class="pill">${duplicateCount} records</span>` : '',
      };
    }

    function artifactRowActions(item, id) {
      const del = id ? `<button type="button" class="danger" data-artifact-delete="${esc(id)}">Delete</button>` : '';
      const meta = item.meta ? `<details><summary>metadata</summary><pre>${esc(JSON.stringify(item.meta, null, 2))}</pre></details>` : '';
      return `<div class="subtle">${esc(item.created_at || '')}</div>${del}${meta}`;
    }

    function renderArtifactFileRow(item) {
      const id = text(item.id);
      const path = text(item.path);
      const name = basename(path || item.uri || item.id);
      const metaLine = artifactMetaSummary(item);
      const { openLink, download } = artifactRowLinks(artifactFileUrl(item));
      const { missing, selected, duplicates } = artifactRowBadges(item, id, path);
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
        <div>${artifactRowActions(item, id)}</div>
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

    // ── Digital Twin Plan card: section builders ─────────────────────────────
    // Each builder renders one self-contained block of the twin-plan card; renderTwinPlanCard
    // (below) just assembles them. Split out so the card's branching lives in small functions
    // rather than one CC=43 monolith.
    function twinSelBadge(sel) {
      const selMode = (sel && sel.mode) || '';
      if (selMode === 'attach') {
        return `<span class="pill up" title="${esc(sel.reason||'')}">CDP attach :${esc(String(sel.port||''))}${sel.authCookie ? ' 🔑' : ''}</span>`;
      }
      if (selMode === 'needs-login') {
        return `<span class="pill warn" title="${esc(sel.reason||'')}">⚠ login required (human-gated)</span>`;
      }
      if (selMode === 'no-chrome') {
        return '<span class="pill down">no CDP Chrome found</span>';
      }
      return '';
    }

    function twinStepRow(s) {
      const feasMark = s.feasible ? '✓' : '✗';
      const feasCls = s.feasible ? 'color:var(--ok)' : 'color:var(--err)';
      const revMark = s.reversible ? '↩' : '—';
      const uri = (s.uri || '').replace(/^kvm:\/\/[^/]+\//, '');
      const fixHint = !s.feasible && s.fix ? ` → fix: ${s.fix}` : '';
      return `<tr>
          <td style="padding:2px 6px;color:var(--subtle)">${s.step}</td>
          <td style="padding:2px 6px;font-family:monospace;font-size:0.82em">${esc(uri)}</td>
          <td style="padding:2px 6px;font-size:0.8em">${esc(s.surface || '')}</td>
          <td style="padding:2px 6px;${feasCls}">${feasMark}${esc(fixHint)}</td>
          <td style="padding:2px 6px;color:var(--subtle)">${revMark}</td>
        </tr>`;
    }

    function twinStepsHtml(steps) {
      if (!steps.length) return '<div class="subtle" style="font-size:0.82em">no steps derived</div>';
      return `
        <table style="width:100%;border-collapse:collapse;margin:4px 0">
          <thead><tr style="font-size:0.78em;color:var(--subtle)">
            <th style="padding:2px 6px;text-align:left">#</th>
            <th style="padding:2px 6px;text-align:left">URI</th>
            <th style="padding:2px 6px;text-align:left">surface</th>
            <th style="padding:2px 6px;text-align:left">feasible</th>
            <th style="padding:2px 6px;text-align:left">rev</th>
          </tr></thead>
          <tbody>${steps.map(twinStepRow).join('')}</tbody>
        </table>`;
    }

    function twinMockHtml(mock) {
      if (!mock) return '';
      return `
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
        </details>`;
    }

    function twinConstraintsHtml(constraints) {
      return constraints.map(c =>
        `<div style="font-size:0.8em;color:var(--warn,#f59e0b)">⚠ ${esc(c.what||'')} — ${esc(c.reason||'')}${c.fix ? ` → ${esc(c.fix)}` : ''}</div>`
      ).join('');
    }

    function twinPlanBadges(att, plan) {
      return {
        domainTag: att.domain ? `<span class="pill" style="font-size:0.78em">${esc(att.domain)}</span>` : '',
        authTag: att.needsAuth ? `<span class="pill" style="font-size:0.78em;background:var(--warn,#f59e0b20)">auth required</span>` : '',
        humanGated: plan.humanGated ? `<div style="color:var(--warn,#f59e0b);font-size:0.82em;margin:4px 0">⚠ human-gated: ${esc(plan.guidance||plan.blockedBy||'')}</div>` : '',
      };
    }

    function renderTwinPlanCard(att) {
      const plan = att.plan || {};
      const env = att.environment || {};
      const sel = plan.browserSelection || {};
      const steps = (plan.steps || []);
      const taskType = att.taskType || 'task';

      const selBadge = twinSelBadge(sel);
      const { domainTag, authTag, humanGated } = twinPlanBadges(att, plan);

      return `<div class="attachment" style="border:1px solid var(--border-color);border-radius:4px;padding:8px 10px;width:100%;box-sizing:border-box">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">
          <span style="font-weight:600;font-size:0.88em">🤖 Digital Twin Plan</span>
          ${domainTag}${authTag}
          <span class="subtle" style="font-size:0.78em;margin-left:auto">${esc(taskType)}</span>
        </div>
        ${selBadge ? `<div style="margin-bottom:4px">${selBadge}</div>` : ''}
        ${humanGated}
        ${twinConstraintsHtml(env.constraints || [])}
        <div style="margin:4px 0">
          <span style="font-size:0.8em;color:var(--subtle)">${plan.totalSteps||0} steps · ${plan.feasibleSteps||0} feasible · ${plan.infeasibleSteps||0} blocked · ${plan.irreversibleSteps||0} irreversible</span>
        </div>
        ${twinStepsHtml(steps)}
        ${twinMockHtml(att.mock)}
        <details style="margin-top:4px"><summary style="font-size:0.75em;color:var(--subtle);cursor:pointer">raw data</summary><pre style="font-size:0.72em;overflow-x:auto">${esc(JSON.stringify(att, null, 2))}</pre></details>
      </div>`;
    }

    function attachmentPreviewHtml(att, isPdf, fileAvailable) {
      const pdfUrl = isPdf && fileAvailable ? text(att.previewUrl || att.filePreviewUrl || '') : '';
      if (isPdf && pdfUrl) {
        return `<iframe class="attachment-pdf-frame" src="${esc(pdfUrl)}" title="${esc(basename(att.path))}" loading="lazy"></iframe>`;
      }
      const visualUrl = isPdf ? attachmentVisualPreviewUrl(att) : text(att.previewUrl || '');
      if (visualUrl) return `<img src="${esc(visualUrl)}" alt="${esc(basename(att.path))}" loading="lazy">`;
      if (isPdf) return `<div class="attachment-pdf-preview"><span>PDF</span><small>${esc(basename(att.path))}</small></div>`;
      return `<div class="subtle">preview unavailable</div>`;
    }

    function attachmentOcrLine(ocr) {
      if (ocr.ok) return `<div class="subtle">OCR ${esc(ocr.backend || '')}: ${esc(text(ocr.text).slice(0, 160))}</div>`;
      return ocr.error ? `<div class="subtle">OCR: ${esc(ocr.error)}</div>` : '';
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
      const preview = attachmentPreviewHtml(att, isPdf, fileAvailable);
      const fileUrl = fileAvailable ? text(att.previewUrl || att.filePreviewUrl || '') : '';
      const { openLink: open, download } = artifactRowLinks(fileUrl);
      const missing = att.fileExists === false ? '<span class="pill down">missing file</span>' : '';
      const detailAtt = fileAvailable ? att : {...att, previewUrl: '', filePreviewUrl: ''};
      const ocrLine = attachmentOcrLine(ocr);
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

    function streamBestSummary(stream, bestScore, bestQualityLabel) {
      const qual = bestQualityLabel ? ` · ${esc(bestQualityLabel)}` : '';
      const err = stream.error ? ` · ${esc(stream.error)}` : '';
      return `${esc(stream.count || 0)} frame(s) · best score ${esc(bestScore)}${qual}${err}`;
    }

    function streamAcceptedLink(accepted, document) {
      if (!accepted) return '';
      const href = document.previewUrl || `/api/file?path=${encodeURIComponent(document.path)}`;
      return `<div><a href="${esc(href)}" download>${esc(basename(document.path))}</a></div>`;
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
        <div class="subtle">${streamBestSummary(stream, bestScore, bestQualityLabel)}</div>
        ${streamAcceptedLink(accepted, document)}
        ${frames.length ? `<div class="stream-frames">${frames.map(renderStreamFrame).join('')}</div>` : ''}
        <details><summary>URI / JSON</summary><pre>${esc(JSON.stringify(stream, null, 2))}</pre></details>
      </div>`;
    }

    function updateServiceViews() {
      const active = state.selectedTargets.length ? state.selectedTargets : ['host'];
      const visible = state.serviceViews.filter((view) => active.includes(view.target) || active.includes(view.serviceId));
      const render = state.widgetRender;
      $('chatStreamList').innerHTML = render
        ? visible.map(render).join('')
        : empty('Widget renderer bundle is loading');
      if (state.dashboardWidgets && typeof state.dashboardWidgets.renderDashboardWidget === 'function') {
        const services = state.summary && Array.isArray(state.summary.services) ? state.summary.services : [];
        const views = state.serviceViews || [];
        const used = new Set();
        const cards = services.map((service) => {
          const view = views.find((item) => item.target === service.id || item.serviceId === service.id || item.serviceId === service.name || item.target === service.name);
          if (view) used.add(view.id || view.target || view.serviceId);
          return state.dashboardWidgets.renderDashboardWidget('widget-card', { service, view });
        });
        views.forEach((view) => {
          const key = view.id || view.target || view.serviceId;
          if (used.has(key)) return;
          cards.push(state.dashboardWidgets.renderDashboardWidget('widget-card', {
            service: { id: view.target || view.serviceId, label: view.title || view.serviceId || view.target, status: view.status || view.kind || 'live' },
            view,
          }));
        });
        $('widgetCount').textContent = `${cards.length} widget(s)`;
        $('widgetGrid').innerHTML = cards.join('') || empty('No services or widgets available');
      } else {
        $('widgetCount').textContent = '0 widget(s)';
        $('widgetGrid').innerHTML = empty('Widget renderer bundle is loading');
      }
    }

    // Load the chat-stream widgets from the widget:// connector over a URI request, so the page
    // renders chatStreamList from the published catalogue instead of vendoring widget renderers
    // in the dashboard controller.
    function applyWidgetJsBundle(js) {
      if (!js) return;
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

    function applyWidgetCss(css) {
      if (!css) return;
      let styleEl = $('urirunWidgetCss');
      if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'urirunWidgetCss';
        document.head.appendChild(styleEl);
      }
      styleEl.textContent = css;
    }

    async function loadWidgetBundleViaUri() {
      try {
        const jsRes = await api('/api/uri/invoke', {
          method: 'POST',
          body: JSON.stringify({ uri: 'widget://host/bundle/query/js', mode: 'execute', payload: {}, source: 'widget-bundle' }),
        });
        applyWidgetJsBundle(jsRes && jsRes.result && jsRes.result.js);
        const cssRes = await api('/api/uri/invoke', {
          method: 'POST',
          body: JSON.stringify({ uri: 'widget://host/bundle/query/css', mode: 'execute', payload: {}, source: 'widget-bundle' }),
        });
        applyWidgetCss(cssRes && cssRes.result && cssRes.result.css);
        if (state.widgetRender) updateServiceViews();
        if (state.dashboardWidgets && typeof state.dashboardWidgets.renderDashboardWidget === 'function') {
          renderArtifacts(state.artifacts, { force: true });
          renderChatHistory({ force: true });
        }
      } catch (error) {
        if (window.console) console.warn('widget bundle load failed:', error.message);
      }
    }

    let _loadServiceViewsInflight = false;
    async function loadServiceViews() {
      if (_loadServiceViewsInflight) return;
      _loadServiceViewsInflight = true;
      try {
        const data = await api('/api/services/live?limit=8');
        state.serviceViews = data.views || [];
        updateServiceViews();
        renderChatHistory();
      } finally {
        _loadServiceViewsInflight = false;
      }
    }

    // Reconcile a stale summary at READ time (no stored mutation): an old "failed: N URI step(s)"
    // written before the status-aggregation fix, where every timeline step actually succeeded,
    // is relabelled "ok:". Genuinely-failed/degraded summaries are left untouched.
    function reconcileChatContent(message, timeline) {
      const c = String(message.content || '');
      if (/^failed:\s*\d+ URI step/i.test(c) && timeline.length && timeline.every((st) => st && st.ok !== false)) {
        return c.replace(/^failed:/i, 'ok:');
      }
      return c;
    }

    // Per-message action controls (select checkbox + repeat/copy/delete buttons). Returns the
    // raw HTML fragments; absent for messages without an id (transient/system rows).
    function chatMessageControls(message, role) {
      if (!message.id) return { checkbox: '', repeat: '', copyMd: '', remove: '' };
      const selected = state.selectedChatMessageIds.has(message.id) ? 'checked' : '';
      // Re-run the command: only on user messages that carry a prompt (the command text).
      const canRepeat = role === 'user' && (message.content || '').trim();
      return {
        checkbox: `<input type="checkbox" name="chatMessageSelect" value="${esc(message.id)}" ${selected}>`,
        repeat: canRepeat ? `<button type="button" data-chat-repeat="${esc(message.id)}" title="Powtorz komende">Repeat</button>` : '',
        copyMd: `<button type="button" data-chat-copy-md="${esc(message.id)}" title="Copy message as Markdown">Copy MD</button>`,
        remove: `<button type="button" class="danger" data-chat-delete="${esc(message.id)}">Delete</button>`,
      };
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
      const ctl = chatMessageControls(message, role);
      return `<div class="message ${esc(role)}">
        <div class="message-head">
          <span class="message-title">${ctl.checkbox}<strong>${esc(role)}</strong></span>
          <span class="message-actions">
            <span class="subtle">${esc(message.created_at || '')}</span>
            ${ctl.repeat}
            ${ctl.copyMd}
            ${ctl.remove}
          </span>
        </div>
        <div>${linkify(reconcileChatContent(message, timeline))}</div>
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

    function timelinePlainLines(timeline) {
      return timeline.map((step) => `- ${step.ok ? 'ok' : 'fail'} ${step.target || ''} ${step.uri || ''}`.trim());
    }

    function attachmentPlainLines(attachments) {
      return attachments.map((att) => `- ${att.kind || 'file'} ${att.path || att.uri || att.previewUrl || ''}`.trim());
    }

    function chatMessagePlainText(message) {
      const detail = message.detail || {};
      const timeline = detail.timeline || [];
      const attachments = message.attachments || [];
      const parts = [
        `[${message.created_at || ''}] ${message.role || 'system'}`,
        text(message.content || ''),
      ].filter(Boolean);
      if (timeline.length) parts.push('URI timeline:', ...timelinePlainLines(timeline));
      if (attachments.length) parts.push('Attachments:', ...attachmentPlainLines(attachments));
      return parts.join('\n');
    }

    function markdownFence(value, lang='') {
      const body = text(value).replace(/```/g, '`\u200b``');
      return '```' + (lang || '') + '\n' + body + '\n```';
    }

    function timelineMarkdownLine(step) {
      const status = step.ok ? 'ok' : 'fail';
      const target = step.target || '';
      const uri = step.uri || '';
      const error = step.error ? ` error=${JSON.stringify(step.error)}` : '';
      return `${status} ${target} ${uri}${error}`.trim();
    }

    function stripBase64(obj) {
      if (obj === null || obj === undefined) return obj;
      if (typeof obj === 'string') {
        if (obj.startsWith('data:') && obj.includes(';base64,')) {
          const parts = obj.split(';base64,');
          return `${parts[0]};base64,... [truncated]`;
        }
        if (obj.length > 200 && /^[a-zA-Z0-9+/=]+$/.test(obj)) {
          return `${obj.substring(0, 30)}... [base64 truncated]`;
        }
        return obj;
      }
      if (Array.isArray(obj)) {
        return obj.map(stripBase64);
      }
      if (typeof obj === 'object') {
        const copy = {};
        for (const key in obj) {
          if (Object.prototype.hasOwnProperty.call(obj, key)) {
            copy[key] = stripBase64(obj[key]);
          }
        }
        return copy;
      }
      return obj;
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
        parts.push('', '## URI Timeline', '', markdownFence(timeline.map(timelineMarkdownLine).join('\n'), 'text'));
      }
      if (attachments.length) {
        parts.push('', '## Attachments', '');
        attachments.forEach((att) => {
          parts.push(`- ${att.kind || 'file'}: ${att.path || att.uri || att.previewUrl || ''}`);
        });
        parts.push('', markdownFence(JSON.stringify(stripBase64(attachments), null, 2), 'json'));
      }
      if (Object.keys(detail).length) {
        parts.push('', '## URI / JSON', '', markdownFence(JSON.stringify(stripBase64(detail), null, 2), 'json'));
      }
      parts.push('', '## Raw Message', '', markdownFence(JSON.stringify(stripBase64(message), null, 2), 'json'));
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
      let messagesToCopy = [];
      let index = state.chatMessages.findIndex((item) => String(item.id || '') === sid);
      if (index !== -1) {
        const msg = state.chatMessages[index];
        messagesToCopy.push(msg);
        if (msg.role === 'user' && index + 1 < state.chatMessages.length) {
          const nextMsg = state.chatMessages[index + 1];
          if (nextMsg.role === 'system') {
            messagesToCopy.push(nextMsg);
          }
        }
      } else {
        index = state.visibleChatMessages.findIndex((item) => String(item.id || '') === sid);
        if (index !== -1) {
          const msg = state.visibleChatMessages[index];
          messagesToCopy.push(msg);
          if (msg.role === 'user' && index + 1 < state.visibleChatMessages.length) {
            const nextMsg = state.visibleChatMessages[index + 1];
            if (nextMsg.role === 'system') {
              messagesToCopy.push(nextMsg);
            }
          }
        }
      }
      if (messagesToCopy.length === 0) throw new Error(`chat message not found: ${id}`);
      const content = messagesToCopy.map(chatMessageMarkdown).join('\n\n---\n\n');
      const method = await copyTextToClipboard(content);
      window.__urirunLastCopiedChatMarkdown = content;
      $('chatStatus').textContent = `copied markdown (${method})`;
      writeUrlState({ action: 'chat:copy-message-md', copied: messagesToCopy.length }, { replace: true });
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
      updateServiceViews();
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

    async function askChat(event, options = {}) {
      if (event && event.preventDefault) event.preventDefault();
      const prompt = $('chatPrompt').value.trim();
      if (!prompt) return;
      const targetExplicit = options.targetExplicit !== false;
      if (!targetExplicit) {
        document.querySelectorAll('input[name="chatTarget"]').forEach((item) => {
          item.checked = item.value === 'host';
        });
      }
      state.selectedTargets = selectedTargets();
      const nodes = selectedNodeNames();
      const execute = $('chatExecute').checked;
      state.view = 'chat';
      writeUrlState({ action: 'chat:run', prompt, prompt_len: prompt.length, nodes: nodes.join(','), targets: state.selectedTargets.join(',') });
      $('chatMode').textContent = execute ? 'execute' : 'dry-run';
      $('chatStatus').textContent = 'running...';
      $('chatAskBtn').disabled = true;
      try {
        // Send empty targets when nothing was explicitly checked — lets the orchestrator
        // infer the target node from the prompt text (e.g. "screenshot na lenovo").
        const explicitTargets = [...document.querySelectorAll('input[name="chatTarget"]:checked')].map(el => el.value);
        const result = await api('/api/chat/ask', {
          method: 'POST',
          body: JSON.stringify({
            prompt,
            nodes,
            targets: explicitTargets,
            target_explicit: targetExplicit,
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

    function chatAutoRunEnabled(search) {
      const action = search.get('action') || '';
      const prompt = (search.get('prompt') || search.get('message') || '').trim();
      if (!prompt) return false;
      if (!(search.get('execute') === '1' || search.get('autorun') === '1')) return false;
      return action === 'chat:run' || action === 'chat:repeat' || action === 'tab:chat';
    }

    function chatAutoRunKey(search) {
      return ['prompt', 'message', 'nodes', 'targets', 'target_explicit', 'targetExplicit', 'execute', 'no_llm', 'noLlm']
        .map((name) => `${name}=${search.get(name) || ''}`).join('&');
    }

    function chatAutoRunAlreadySeen(key) {
      try {
        const storageKey = `urirun:chat-autorun:${key}`;
        if (sessionStorage.getItem(storageKey)) return true;
        sessionStorage.setItem(storageKey, new Date().toISOString());
      } catch (_) {
        return false;
      }
      return false;
    }

    function chatUrlTargetExplicit(search) {
      const raw = search.has('target_explicit') ? search.get('target_explicit') : search.get('targetExplicit');
      if (raw === null) return false;
      return !['0', 'false', 'no', 'off'].includes(String(raw).trim().toLowerCase());
    }

    function urlTargetsAreImplicitAutorun(search) {
      return chatAutoRunEnabled(search) && !chatUrlTargetExplicit(search);
    }

    async function maybeAutoRunChatFromUrl(search) {
      if (!chatAutoRunEnabled(search)) return;
      const key = chatAutoRunKey(search);
      if (chatAutoRunAlreadySeen(key)) return;
      const targetExplicit = chatUrlTargetExplicit(search);
      state.view = 'chat';
      applyView('chat');
      $('chatStatus').textContent = 'running from URL...';
      await askChat(null, { targetExplicit });
      const normalizedKey = chatAutoRunKey(new URLSearchParams(window.location.search));
      if (normalizedKey !== key) chatAutoRunAlreadySeen(normalizedKey);
    }

    // Re-run a previous user command: resend its prompt with the same nodes/targets/execute
    // captured in the message detail (falls back to the current composer selections).
    function repeatRequestFromMessage(msg) {
      const prompt = (msg.content || '').trim();
      if (!prompt) return null;
      const detail = msg.detail || {};
      const nodes = detail.selectedNodes || detail.requestedNodes || selectedNodeNames();
      // Use requestedTargets (what the user originally selected) rather than selectedTargets
      // (which includes the LLM-inferred node). Empty = let the orchestrator re-infer.
      const targets = detail.requestedTargets || [];
      const execute = detail.execute !== undefined ? !!detail.execute : $('chatExecute').checked;
      return { prompt, nodes, targets, execute };
    }

    async function repeatChatMessage(id) {
      const msg = (state.chatMessages || []).find((m) => m.id === id);
      if (!msg) return;
      const req = repeatRequestFromMessage(msg);
      if (!req) return;
      const { prompt, nodes, targets, execute } = req;
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
        updateServiceViews();
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
    load().then(() => maybeAutoRunChatFromUrl(new URLSearchParams(window.location.search))).catch((error) => {
      $('contextLine').textContent = error.message;
    });
