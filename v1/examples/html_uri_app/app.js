import { createUriRuntimeV1 } from './uri-runtime-v1.js';

const state = { runs: 0, logs: [] };

function appendLog(event, detail = {}) {
  state.logs.unshift({ at: new Date().toLocaleTimeString(), event, detail });
  state.logs = state.logs.slice(0, 12);
}

// Browser-safe adapters. The browser cannot spawn ffmpeg/docker, so those are
// simulated but show the *exact* rendered command; fetch does a real request.
const adapters = {
  spawn: async ({ entry, params, translation, mode }) => {
    const base = entry.config.command || [];
    let command = base.map((p) => String(p).replace(/\{([a-zA-Z0-9_.]+)\}/g, (_, k) => String(params[k])));
    const command2 = command.concat(/\{[a-zA-Z0-9_.]+\}/.test(base.join(' ')) ? [] : translation.args);
    if (mode === 'execute') { state.runs += 1; appendLog('spawn', { command: command2 }); }
    return { ok: true, simulated: true, type: 'cli', command: command2, env: entry.config.env, note: 'browser preview; the CLI runs this for real' };
  },
  'shell-template': async ({ entry, params, mode }) => {
    const command = String(entry.config.template || '').replace(/\{([a-zA-Z0-9_.]+)\}/g, (_, k) => String(params[k]));
    if (mode === 'execute') appendLog('shell', { command });
    return { ok: true, simulated: true, type: 'shell', command };
  },
  'docker-exec': async ({ entry, params, target, mode }) => {
    const inner = (entry.config.command || []).map((p) => String(p).replace(/\{([a-zA-Z0-9_.]+)\}/g, (_, k) => String(params[k])));
    const command = ['docker', 'exec', target, ...inner];
    if (mode === 'execute') appendLog('docker.exec', { command });
    return { ok: true, simulated: true, type: 'docker', mode: 'exec', container: target, command };
  },
  'docker-run': async ({ entry, params, mode }) => {
    const inner = (entry.config.command || []).map((p) => String(p).replace(/\{([a-zA-Z0-9_.]+)\}/g, (_, k) => String(params[k])));
    const command = ['docker', 'run', '--rm', '-v', '$PWD:/work', '-w', '/work', entry.config.image, ...inner];
    if (mode === 'execute') appendLog('docker.run', { image: entry.config.image });
    return { ok: true, simulated: true, type: 'docker', mode: 'run', image: entry.config.image, command };
  },
  fetch: async ({ entry, params, payload, mode }) => {
    const url = String(entry.config.url || '').replace(/\{([a-zA-Z0-9_.]+)\}/g, (_, k) => String(params[k]));
    const method = (entry.config.method || 'POST').toUpperCase();
    if (mode !== 'execute') return { ok: true, simulated: true, type: 'http', method, url };
    if (method !== 'GET') {
      appendLog('http.simulated', { method, url });
      return { ok: true, simulated: true, type: 'http', method, url, body: payload, note: 'only GET runs for real in this demo' };
    }
    try {
      const response = await fetch(url, { headers: { Accept: 'application/vnd.github+json' } });
      const text = await response.text();
      appendLog('http.fetch', { status: response.status, url });
      return { ok: response.ok, type: 'http', method, url, status: response.status, body: text.slice(0, 600) };
    } catch (error) {
      return { ok: false, type: 'http', method, url, error: error.message };
    }
  },
};

const els = {
  actions: document.querySelector('#actions'),
  detail: document.querySelector('#detail'),
  output: document.querySelector('#output'),
  logs: document.querySelector('#logs'),
  routeCount: document.querySelector('#route-count'),
  mode: document.querySelector('#mode'),
  execute: document.querySelector('#execute-toggle'),
  confirm: document.querySelector('#confirm-toggle'),
  allow: document.querySelector('#allow-input'),
  addAllow: document.querySelector('#add-allow'),
  reset: document.querySelector('#reset-policy'),
};

const bindingDocument = await fetch('./bindings.json').then((r) => r.json());
const basePolicy = await fetch('./policy.json').then((r) => r.json());
const runtime = createUriRuntimeV1({ bindings: bindingDocument, adapters, state, policy: basePolicy });
window.uriApp = runtime;

els.routeCount.textContent = Object.keys(runtime.routes).length;
let selected = runtime.listRoutes()[0]?.uri;

const executeMode = () => els.execute.checked;

function badgeFor(decision) {
  if (!executeMode()) return { text: 'dry-run', cls: 'dry' };
  if (decision.allowed && decision.requireConfirm) return { text: 'confirm', cls: 'confirm' };
  if (decision.allowed) return { text: 'allow', cls: 'allow' };
  return { text: 'deny', cls: 'deny' };
}

function currentPayload() {
  const payload = {};
  els.detail.querySelectorAll('[data-param]').forEach((input) => {
    if (input.value !== '') payload[input.dataset.param] = input.value;
  });
  return payload;
}

function renderActions() {
  els.mode.textContent = executeMode() ? 'execute' : 'dry-run';
  const items = runtime.listRoutes();
  els.actions.innerHTML = items.map((item) => {
    const badge = badgeFor(item.decision);
    const label = (item.meta && item.meta.label) || item.uri;
    const active = item.uri === selected ? ' active' : '';
    return `<button class="action ${item.kind}${active}" data-select="${escapeHtml(item.uri)}">
      <span class="pill ${badge.cls}">${badge.text}</span>
      <strong>${escapeHtml(label)}</strong>
      <code>${escapeHtml(item.uri)}</code>
    </button>`;
  }).join('');
}

function renderDetail() {
  const item = runtime.listRoutes().find((r) => r.uri === selected);
  if (!item) { els.detail.innerHTML = '<p class="muted">Select an endpoint.</p>'; return; }
  const params = Object.entries(item.params);
  const inputs = params.length
    ? params.map(([name, rule]) => {
        const ph = rule.required ? 'required' : (rule.default !== undefined ? `default: ${rule.default}` : 'optional');
        return `<label class="field"><span>${escapeHtml(name)}${rule.required ? ' *' : ''}</span>
          <input data-param="${escapeHtml(name)}" placeholder="${escapeHtml(String(ph))}"></label>`;
      }).join('')
    : '<p class="muted">No parameters.</p>';
  els.detail.innerHTML = `
    <h2>${escapeHtml((item.meta && item.meta.label) || item.uri)}</h2>
    <code class="uri">${escapeHtml(item.uri)}</code>
    <div class="fields">${inputs}</div>
    <h3>Command preview</h3>
    <pre id="preview" class="preview"></pre>
    <button id="run-btn" type="button">Run</button>`;
  els.detail.querySelectorAll('[data-param]').forEach((input) => input.addEventListener('input', updatePreview));
  els.detail.querySelector('#run-btn').addEventListener('click', runSelected);
  updatePreview();
}

function updatePreview() {
  const node = els.detail.querySelector('#preview');
  if (!node) return;
  try {
    node.textContent = runtime.preview(selected, currentPayload());
    node.classList.remove('error');
  } catch (error) {
    node.textContent = `! ${error.message}`;
    node.classList.add('error');
  }
}

async function runSelected() {
  const envelope = await runtime.dispatch(selected, currentPayload(), {
    mode: executeMode() ? 'execute' : 'dry-run',
    confirm: els.confirm.checked,
  });
  els.output.textContent = JSON.stringify(envelope, null, 2);
  renderLogs();
}

els.actions.addEventListener('click', (event) => {
  const target = event.target.closest('[data-select]');
  if (!target) return;
  selected = target.dataset.select;
  renderActions();
  renderDetail();
});
els.execute.addEventListener('change', () => { renderActions(); });
els.confirm.addEventListener('change', () => {});
els.addAllow.addEventListener('click', () => {
  const glob = els.allow.value.trim();
  if (!glob) return;
  const p = runtime.getPolicy();
  runtime.setPolicy({ ...p, execute: { allow: [...p.execute.allow, glob], deny: p.execute.deny } });
  els.allow.value = '';
  renderActions();
});
els.reset.addEventListener('click', () => { runtime.setPolicy(basePolicy); renderActions(); });

function renderLogs() {
  els.logs.innerHTML = state.logs
    .map((item) => `<li><strong>${item.at}</strong><span>${item.event}</span><code>${escapeHtml(JSON.stringify(item.detail))}</code></li>`)
    .join('');
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' })[char]);
}

renderActions();
renderDetail();
renderLogs();
