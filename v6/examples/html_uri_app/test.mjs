import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createUriRuntimeV6 } from './uri-runtime-v6.js';

const bindings = JSON.parse(await readFile(new URL('./bindings.json', import.meta.url), 'utf8'));
const policy = JSON.parse(await readFile(new URL('./policy.json', import.meta.url), 'utf8'));
const state = { led: 'off', users: ['ada'], portalText: '', logs: [] };

const refs = {
  'devices.ledSet': ({ translation }) => {
    state.led = translation.args[0] || 'on';
    return { ok: true, state: state.led };
  },
  'devices.telemetryLatest': () => ({ ok: true, telemetry: { led: state.led } }),
  'logs.write': ({ payload }) => {
    state.logs.push(payload);
    return { ok: true };
  },
  'assertions.contains': ({ payload }) => ({
    ok: String(payload.actual || '').includes(String(payload.expected || '')),
  }),
};

function readPath(object, path) {
  return String(path).split('.').reduce((value, key) => value?.[key], object);
}

const adapters = {
  'local-function': async (ctx) => {
    if (ctx.mode !== 'execute') return { ok: true, simulated: true, wouldCall: ctx.entry.ref };
    return refs[ctx.entry.ref](ctx);
  },
  fetch: async ({ entry, mode }) => ({ ok: true, simulated: mode !== 'execute', url: entry.config.url }),
  'mqtt-publish': async ({ entry, translation }) => ({
    ok: true,
    topic: [entry.config.topicPrefix, translation.target, ...translation.args].filter(Boolean).join('/'),
  }),
  'shell-template': async ({ entry, translation }) => ({
    ok: true,
    command: entry.config.template.replace(/\{(\d+)\}/g, (_, index) => translation.args[Number(index)] || ''),
  }),
  'browser-open': async ({ payload, mode }) => {
    if (mode === 'execute') state.portalText = payload.url.includes('reports') ? 'csv export ready' : 'ok';
    return { ok: true, text: state.portalText };
  },
  'dom-read': async () => ({ ok: true, text: state.portalText }),
  'uri-flow': async ({ entry, dispatch, mode, policy: p, confirm }) => {
    const results = {};
    for (const step of entry.config.steps) {
      const payload = { ...(step.payload || {}) };
      if (payload.actual_from) payload.actual = readPath(results, payload.actual_from);
      const envelope = await dispatch(step.uri, payload, { mode, policy: p, confirm });
      results[step.id] = envelope.result || envelope;
    }
    return { ok: Object.values(results).every((result) => result.ok !== false), results };
  },
};

const runtime = createUriRuntimeV6({ bindings, adapters, refs, state, policy });

// Contract size.
assert.equal(Object.keys(runtime.routes).length, 13);

// Dry-run is the default and never mutates application state.
const dry = await runtime.dispatch('device://device-01/led/set/on');
assert.equal(dry.mode, 'dry-run');
assert.equal(dry.ok, true);
assert.equal(dry.result.simulated, true);
assert.equal(state.led, 'off');

// Execute is gated by policy. device://** is allowed, so the LED really changes.
const executed = await runtime.dispatch('device://device-01/led/set/on', {}, { mode: 'execute' });
assert.equal(executed.ok, true);
assert.equal(executed.decision.allowed, true);
assert.equal(state.led, 'on');

// shell:// is explicitly denied, even in execute mode.
const shell = await runtime.dispatch('shell://local/system/restart/nginx', {}, { mode: 'execute' });
assert.equal(shell.ok, false);
assert.equal(shell.error.type, 'policy');

// Destructive route is allowed but needs confirmation.
const unconfirmed = await runtime.dispatch('service://api/user/delete/basic', { name: 'Ada' }, { mode: 'execute' });
assert.equal(unconfirmed.ok, false);
assert.equal(unconfirmed.error.type, 'confirm');
const confirmed = await runtime.dispatch('service://api/user/delete/basic', { name: 'Ada' }, { mode: 'execute', confirm: true });
assert.equal(confirmed.ok, true);

// listRoutes exposes the decision per URI for a UI to render.
const decisions = Object.fromEntries(runtime.listRoutes().map((item) => [item.uri, item.decision]));
assert.equal(decisions['shell://local/system/restart/nginx'].allowed, false);
assert.equal(decisions['service://api/user/delete/basic'].requireConfirm, true);
assert.equal(decisions['device://device-01/led/set/on'].allowed, true);

// A workflow runs every step through the same gate.
const flow = await runtime.dispatch('workflow://office/supplier-report/monthly', {}, { mode: 'execute' });
assert.equal(flow.ok, true);

console.log('PASS html_uri_app v6');
