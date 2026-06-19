import { createUriRuntimeV6, parseUri, translate } from './uri-runtime-v6.js';

const state = {
  led: 'off',
  users: ['ada'],
  logs: [],
  portalText: '',
};

function appendLog(event, detail = {}) {
  state.logs.unshift({ at: new Date().toLocaleTimeString(), event, detail });
  state.logs = state.logs.slice(0, 12);
}

function pickPortalText(url) {
  if (url.includes('reports')) return 'supplier portal monthly csv export ready';
  if (url.includes('transfer')) return 'bank batch transfer draft ok, waiting before 2fa';
  return 'page ok';
}

function readPath(object, path) {
  return String(path).split('.').reduce((value, key) => value?.[key], object);
}

// Refs only ever run on the execute path, so dry-run never mutates state.
const refs = {
  'devices.ledSet': ({ translation, payload }) => {
    state.led = translation.args[0] || 'on';
    appendLog('device.led.set', { state: state.led, payload });
    return { ok: true, target: translation.target, state: state.led };
  },
  'devices.telemetryLatest': ({ translation }) => ({
    ok: true,
    target: translation.target,
    telemetry: { led: state.led, temperature: 22.4, rssi: -48 },
  }),
  'logs.write': ({ payload }) => {
    appendLog(payload.event || 'frontend.event', payload.detail || {});
    return { ok: true, written: true };
  },
  'assertions.contains': ({ payload }) => {
    const actual = String(payload.actual ?? '');
    const expected = String(payload.expected ?? '');
    return { ok: actual.toLowerCase().includes(expected.toLowerCase()), actual, expected };
  },
};

const adapters = {
  'local-function': async (ctx) => {
    if (ctx.mode !== 'execute') {
      return { ok: true, simulated: true, type: 'function', wouldCall: ctx.entry.ref, args: ctx.translation.args };
    }
    const fn = refs[ctx.entry.ref];
    if (!fn) throw new Error(`Missing ref: ${ctx.entry.ref}`);
    return fn(ctx);
  },
  fetch: async ({ entry, translation, payload, mode }) => {
    const base = { type: 'http', method: entry.config.method || 'POST', url: entry.config.url };
    if (mode !== 'execute') return { ok: true, simulated: true, ...base, body: { args: translation.args, payload } };
    if (entry.config.method === 'GET' && entry.config.url === '/api/logs/recent') {
      return { ok: true, ...base, logs: state.logs };
    }
    if (entry.config.method === 'DELETE') {
      state.users = state.users.filter((user) => user !== String(payload.name || '').toLowerCase());
      appendLog('user.delete', { name: payload.name, remaining: state.users });
      return { ok: true, ...base, deleted: payload.name, remaining: state.users };
    }
    if (entry.config.method === 'POST' && entry.config.url === '/api/users') {
      const name = String(payload.name || 'user').toLowerCase();
      if (!state.users.includes(name)) state.users.push(name);
      appendLog('user.create', { name, users: state.users });
      return { ok: true, ...base, created: name, users: state.users };
    }
    appendLog('http.fetch', { ...base, payload });
    return { ok: true, simulated: true, ...base, body: { args: translation.args, payload } };
  },
  'mqtt-publish': async ({ entry, translation, payload, mode }) => {
    const topic = [entry.config.topicPrefix, translation.target, ...translation.args].filter(Boolean).join('/');
    if (mode === 'execute') appendLog('mqtt.publish', { topic, payload });
    return { ok: true, simulated: mode !== 'execute', type: 'mqtt', topic, payload, delivered: false, note: 'no broker bound' };
  },
  'shell-template': async ({ entry, translation, mode }) => {
    const command = entry.config.template.replace(/\{(\d+)\}/g, (_, index) => translation.args[Number(index)] || '');
    return { ok: true, simulated: true, type: 'shell', command, delivered: false, note: `not executed in browser (mode: ${mode})` };
  },
  'browser-open': async ({ payload, mode }) => {
    if (mode !== 'execute') return { ok: true, simulated: true, type: 'browser', wouldOpen: payload.url };
    state.portalText = pickPortalText(payload.url || '');
    appendLog('browser.open', { url: payload.url });
    return { ok: true, type: 'browser', url: payload.url, text: state.portalText };
  },
  'dom-read': async ({ mode }) => {
    if (mode !== 'execute') return { ok: true, simulated: true, type: 'dom', bytes: state.portalText.length };
    appendLog('dom.read', { bytes: state.portalText.length });
    return { ok: true, type: 'dom', text: state.portalText };
  },
  'uri-flow': async ({ entry, dispatch, mode, policy, confirm }) => {
    const results = {};
    const steps = [];
    for (const step of entry.config.steps || []) {
      const payload = { ...(step.payload || {}) };
      if (payload.actual_from) payload.actual = readPath(results, payload.actual_from);
      const envelope = await dispatch(step.uri, payload, { mode, policy, confirm });
      results[step.id] = envelope.result || envelope;
      steps.push({ id: step.id, uri: step.uri, ok: envelope.ok, decision: envelope.decision });
      if (envelope.ok === false) break;
    }
    if (mode === 'execute') appendLog('workflow.run', { workflow: entry.uri, steps: steps.length });
    return { ok: steps.every((step) => step.ok !== false), type: 'workflow', steps };
  },
};

const els = {
  actions: document.querySelector('#actions'),
  output: document.querySelector('#output'),
  logs: document.querySelector('#logs'),
  state: document.querySelector('#state'),
  routeCount: document.querySelector('#route-count'),
  mode: document.querySelector('#mode'),
  execute: document.querySelector('#execute-toggle'),
  confirm: document.querySelector('#confirm-toggle'),
  allow: document.querySelector('#allow-input'),
  addAllow: document.querySelector('#add-allow'),
  reset: document.querySelector('#reset-policy'),
};

const bindingDocument = await fetch('./bindings.json').then((response) => response.json());
const basePolicy = await fetch('./policy.json').then((response) => response.json());

const runtime = createUriRuntimeV6({ bindings: bindingDocument, adapters, refs, state, policy: basePolicy });
window.uriApp = runtime;

els.routeCount.textContent = Object.keys(runtime.routes).length;

function executeMode() {
  return els.execute.checked;
}

function badgeFor(decision) {
  if (!executeMode()) return { text: 'dry-run', cls: 'dry' };
  if (decision.allowed && decision.requireConfirm) return { text: 'confirm', cls: 'confirm' };
  if (decision.allowed) return { text: 'allow', cls: 'allow' };
  return { text: 'deny', cls: 'deny' };
}

function labelFor(item) {
  if (item.meta && item.meta.label) return item.meta.label;
  const translation = translate(parseUri(item.uri));
  return `${translation.resource} ${translation.operation}`;
}

function renderActions() {
  const items = runtime.listRoutes();
  els.mode.textContent = executeMode() ? 'execute' : 'dry-run';
  els.actions.innerHTML = items
    .map((item) => {
      const badge = badgeFor(item.decision);
      const uri = item.meta && item.meta.uri ? item.meta.uri : item.uri;
      const payload = item.meta && item.meta.payload ? JSON.stringify(item.meta.payload) : '';
      return `
        <button class="action ${item.kind}" data-uri="${escapeHtml(uri)}" data-payload='${escapeHtml(payload)}'>
          <span class="pill ${badge.cls}">${badge.text}</span>
          <strong>${escapeHtml(labelFor(item))}</strong>
          <code>${escapeHtml(uri)}</code>
        </button>`;
    })
    .join('');
}

els.actions.addEventListener('click', async (event) => {
  const target = event.target.closest('[data-uri]');
  if (!target) return;
  const uri = target.dataset.uri;
  const payload = target.dataset.payload ? JSON.parse(target.dataset.payload) : { source: 'html-uri-app' };
  const envelope = await runtime.dispatch(uri, payload, {
    mode: executeMode() ? 'execute' : 'dry-run',
    confirm: els.confirm.checked,
  });
  els.output.textContent = JSON.stringify(envelope, null, 2);
  render();
});

els.execute.addEventListener('change', renderActions);
els.confirm.addEventListener('change', renderActions);
els.addAllow.addEventListener('click', () => {
  const glob = els.allow.value.trim();
  if (!glob) return;
  const policy = runtime.getPolicy();
  runtime.setPolicy({ ...policy, execute: { allow: [...policy.execute.allow, glob], deny: policy.execute.deny } });
  els.allow.value = '';
  renderActions();
});
els.reset.addEventListener('click', () => {
  runtime.setPolicy(basePolicy);
  renderActions();
});

function render() {
  els.state.textContent = JSON.stringify({ led: state.led, users: state.users, portalText: state.portalText }, null, 2);
  els.logs.innerHTML = state.logs
    .map((item) => `<li><strong>${item.at}</strong><span>${item.event}</span><code>${escapeHtml(JSON.stringify(item.detail))}</code></li>`)
    .join('');
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  })[char]);
}

renderActions();
render();
