import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createUriRuntime } from './uri-runtime.js';

const bindings = JSON.parse(await readFile(new URL('./bindings.json', import.meta.url), 'utf8'));
const state = { led: 'off', portalText: '', logs: [] };

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
  'local-function': async ({ entry, translation, payload }) => refs[entry.ref]({ translation, payload }),
  fetch: async ({ entry }) => ({ ok: true, type: 'http', url: entry.config.url }),
  'backend-dispatch': async ({ entry, descriptor, translation, payload }) => {
    if (descriptor.package === 'log') {
      state.logs.push({ uri: descriptor.raw, payload });
      return { ok: true, written: true };
    }
    if (descriptor.package === 'shell') {
      return {
        ok: true,
        simulated: true,
        command: entry.config.template.replace(/\{(\d+)\}/g, (_, index) => translation.args[Number(index)] || ''),
      };
    }
    return { ok: true, uri: descriptor.raw, payload };
  },
  'mqtt-publish': async ({ entry, translation }) => ({
    ok: true,
    topic: [entry.config.topicPrefix, translation.target, ...translation.args].filter(Boolean).join('/'),
  }),
  'shell-template': async ({ entry, translation }) => ({
    ok: true,
    command: entry.config.template.replace(/\{(\d+)\}/g, (_, index) => translation.args[Number(index)] || ''),
  }),
  'browser-open': async ({ payload }) => {
    state.portalText = payload.url.includes('reports') ? 'csv export ready' : 'ok';
    return { ok: true, text: state.portalText };
  },
  'dom-read': async () => ({ ok: true, text: state.portalText }),
  'uri-flow': async ({ entry, dispatch }) => {
    const results = {};
    for (const step of entry.config.steps) {
      const payload = { ...(step.payload || {}) };
      if (payload.actual_from) payload.actual = readPath(results, payload.actual_from);
      results[step.id] = await dispatch(step.uri, payload);
    }
    return { ok: Object.values(results).every((result) => result.ok !== false), results };
  },
};

const runtime = createUriRuntime({ bindings, adapters, refs, state });

assert.equal(Object.keys(runtime.routes).length, 13);
const routeItems = runtime.listRoutes();
assert.equal(routeItems.length, 13);
assert.equal(routeItems.find((item) => item.uri === 'mqtt://broker/publish/home').meta.uri, 'mqtt://broker/publish/home/kitchen/light/on');
const envelope = await runtime.dispatchEnvelope('device://device-01/led/set/on');
assert.equal(envelope.ok, true);
assert.equal(envelope.kind, 'function');
assert.equal(envelope.result.state, 'on');
assert.deepEqual(await runtime.dispatch('device://device-01/led/set/off'), { ok: true, state: 'off' });
assert.deepEqual((await runtime.dispatch('device://device-01/telemetry/query/latest')).telemetry, { led: 'off' });
assert.equal((await runtime.dispatch('mqtt://broker/publish/home/kitchen/light/on')).topic, 'home/broker/kitchen/light/on');
assert.equal((await runtime.dispatch('shell://local/system/restart/nginx')).command, 'systemctl restart nginx');
assert.equal((await runtime.dispatch('workflow://office/supplier-report/monthly')).ok, true);

console.log('PASS html_uri_app');
