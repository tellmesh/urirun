import assert from 'node:assert/strict';
import test from 'node:test';
import { check, listRoutes, run } from './urihandler-v6.js';

const ECHO_REGISTRY = {
  version: 'urihandler.registry.v4',
  routes: { cli: { echo: { say: { kind: 'cli', adapter: 'spawn', config: { command: ['echo'] } } } } },
};

const NPM_REGISTRY = {
  version: 'urihandler.registry.v4',
  routes: { cli: { npm: { test: { kind: 'cli', adapter: 'spawn', config: { command: ['npm', 'test'] } } } } },
};

test('dry-run is the default and never executes', async () => {
  const result = await run('cli://local/npm/test', NPM_REGISTRY);
  assert.equal(result.mode, 'dry-run');
  assert.equal(result.ok, true);
  assert.equal(result.result.simulated, true);
  assert.deepEqual(result.result.command, ['npm', 'test']);
});

test('execute is denied by default', async () => {
  const result = await run('cli://local/npm/test', NPM_REGISTRY, null, { mode: 'execute' });
  assert.equal(result.ok, false);
  assert.equal(result.error.type, 'policy');
  assert.match(result.decision.reason, /default deny/);
});

test('allow glob permits execution and command actually runs', async () => {
  const result = await run('cli://local/echo/say/hello', ECHO_REGISTRY, null, {
    mode: 'execute',
    policy: { execute: { allow: ['cli://local/echo/*'] } },
  });
  assert.equal(result.ok, true);
  assert.equal(result.result.exitCode, 0);
  assert.equal(result.result.stdout.trim(), 'hello');
});

test('deny glob overrides allow', () => {
  const registry = {
    version: 'urihandler.registry.v4',
    routes: { cli: { script: { deploy: { kind: 'cli', adapter: 'spawn', config: { command: ['sh', 'deploy.sh'] } } } } },
  };
  const decision = check('cli://local/script/deploy', registry, {
    execute: { allow: ['cli://**'], deny: ['cli://local/script/*'] },
  });
  assert.equal(decision.decision.allowed, false);
});

test('listRoutes returns sorted uris with policy decisions', () => {
  // A real registry carries an index that preserves full URIs (incl. target).
  const indexed = {
    ...NPM_REGISTRY,
    index: { a: { uri: 'cli://local/npm/test', route: ['cli', 'npm', 'test'], source: {} } },
  };
  const items = listRoutes(indexed, { execute: { allow: ['cli://local/npm/*'] } });
  assert.equal(items[0].uri, 'cli://local/npm/test');
  assert.equal(items[0].kind, 'cli');
  assert.equal(items[0].decision.allowed, true);
});

test('destructive routes require confirmation', async () => {
  const registry = {
    version: 'urihandler.registry.v4',
    routes: { cli: { disk: { wipe: { kind: 'cli', adapter: 'spawn', config: { command: ['rm', '-rf'] } } } } },
  };
  const result = await run('cli://local/disk/wipe', registry, null, {
    mode: 'execute',
    policy: { execute: { allow: ['cli://local/disk/*'] } },
  });
  assert.equal(result.ok, false);
  assert.equal(result.error.type, 'confirm');
});
