import assert from 'node:assert/strict';
import test from 'node:test';
import { buildInvocation, dispatch, parseUri } from './index.js';

test('parses URI into descriptor', () => {
  assert.deepEqual(parseUri('device://device-01/led/set/on?trace=1#ui'), {
    fragment: 'ui',
    package: 'device',
    query: { trace: '1' },
    raw: 'device://device-01/led/set/on?trace=1#ui',
    segments: ['led', 'set', 'on'],
    target: 'device-01',
  });
});

test('builds invocation from descriptor', () => {
  assert.deepEqual(buildInvocation({
    package: 'device',
    target: 'device-01',
    segments: ['led', 'set', 'on'],
  }), {
    args: ['device-01', 'on'],
    functionName: 'led_set',
    package: 'device',
    segments: ['led', 'set', 'on'],
    target: 'device-01',
  });
});

test('dispatches through explicit registry', async () => {
  const result = await dispatch('device://device-01/led/set/on', {
    device: {
      led_set(target, state, payload) {
        return { ok: true, payload, state, target };
      },
    },
  }, { source: 'test' });
  assert.deepEqual(result, {
    ok: true,
    payload: { source: 'test' },
    state: 'on',
    target: 'device-01',
  });
});

test('rejects missing packages and functions', async () => {
  await assert.rejects(() => dispatch('device://device-01/led/set/on', {}, {}), /Unknown package/);
  await assert.rejects(() => dispatch('device://device-01/led/set/on', { device: {} }, {}), /Unknown function/);
});
