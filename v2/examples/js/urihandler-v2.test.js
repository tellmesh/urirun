import assert from 'node:assert/strict';
import test from 'node:test';
import {
  dispatch,
  hashUri,
  normalizeUri,
  parseUri,
  resolve,
  translate,
  validate,
} from './urihandler-v2.js';

const registry = {
  device: {
    led: {
      set(target, args, payload, descriptor) {
        return { descriptor, ok: true, payload, state: args[0], target };
      },
    },
  },
  log: {
    info: {
      'user-created'(target, args, payload, descriptor) {
        return { args, descriptor, event: 'user-created', ok: true, payload, sink: target };
      },
    },
  },
};

test('parses, normalizes, and translates logical URI', () => {
  const descriptor = parseUri('device://device-01/led/set/on?trace=1#ui');
  assert.equal(normalizeUri(descriptor), 'device://device-01/led/set/on');
  assert.deepEqual(translate(descriptor).route, ['device', 'led', 'set']);
  assert.deepEqual(translate(descriptor).args, ['device-01', 'on']);
});

test('validates and resolves through route tree', () => {
  const translation = translate(parseUri('device://device-01/led/set/on'));
  const cache = new Map();
  assert.equal(validate(translation, registry), true);
  assert.equal(resolve(translation, registry, cache), registry.device.led.set);
  assert.equal(resolve(translation, registry, cache), registry.device.led.set);
  assert.equal(cache.size, 1);
});

test('dispatches device and log routes', async () => {
  assert.deepEqual(await dispatch('device://device-01/led/set/on', registry, { source: 'test' }), {
    descriptor: {
      fragment: null,
      normalized: 'device://device-01/led/set/on',
      package: 'device',
      query: {},
      raw: 'device://device-01/led/set/on',
      segments: ['led', 'set', 'on'],
      target: 'device-01',
    },
    ok: true,
    payload: { source: 'test' },
    state: 'on',
    target: 'device-01',
  });
  assert.equal((await dispatch('log://app/info/user-created', registry, { userId: 42 })).sink, 'app');
});

test('hashes normalized URI with sha256 hex', () => {
  assert.match(hashUri('device://device-01/led/set/on'), /^[a-f0-9]{64}$/);
});

test('rejects invalid route', async () => {
  await assert.rejects(() => dispatch('device://device-01/motor/set/on', registry), /Route validation failed/);
});
