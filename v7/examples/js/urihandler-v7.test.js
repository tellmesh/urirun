import assert from 'node:assert/strict';
import test from 'node:test';
import { compileRegistry, run } from './urihandler-v7.js';

const ALLOW_ALL = { execute: { allow: ['*'] } };

test('named params from payload render into the command', async () => {
  const registry = compileRegistry({
    bindings: {
      'media://local/video/transcode': {
        command: ['ffmpeg', '-i', '{input}', '-vf', 'scale={width}:{height}', '{output}'],
        params: { input: { required: true }, output: { required: true }, width: { default: 1280 }, height: { default: 720 } },
      },
    },
  });
  const result = await run('media://local/video/transcode', registry, { input: 'a.mp4', output: 'b.mp4' });
  assert.deepEqual(result.result.command, ['ffmpeg', '-i', 'a.mp4', '-vf', 'scale=1280:720', 'b.mp4']);
});

test('missing required param is an error even in dry-run', async () => {
  const registry = compileRegistry({
    bindings: { 'media://x/v/t': { command: ['ffmpeg', '{input}'], params: { input: { required: true } } } },
  });
  const result = await run('media://x/v/t', registry, {});
  assert.equal(result.ok, false);
  assert.equal(result.error.type, 'params');
});

test('string shorthand expands to a spawn command', async () => {
  const registry = compileRegistry({ bindings: { 'cli://local/git/status': 'git status' } });
  const result = await run('cli://local/git/status', registry);
  assert.equal(result.adapter, 'spawn');
  assert.deepEqual(result.result.command, ['git', 'status']);
});

test('docker-exec uses the target as container name', async () => {
  const registry = compileRegistry({
    bindings: {
      'container://api/db/backup': {
        kind: 'docker', adapter: 'docker-exec',
        command: ['pg_dump', '-U', '{user}', '{database}'],
        params: { user: { default: 'postgres' }, database: { required: true } },
      },
    },
  });
  const result = await run('container://api/db/backup', registry, { database: 'app' });
  assert.deepEqual(result.result.command, ['docker', 'exec', 'api', 'pg_dump', '-U', 'postgres', 'app']);
});

test('spawn executes with bound params and inline allow', async () => {
  const registry = compileRegistry({
    bindings: { 'say://local/echo/msg': { command: ['echo', '{text}'], params: { text: { required: true } } } },
  });
  const result = await run('say://local/echo/msg', registry, { text: 'hello' }, { mode: 'execute', policy: ALLOW_ALL });
  assert.equal(result.ok, true);
  assert.equal(result.result.stdout.trim(), 'hello');
});

test('execute is denied by default', async () => {
  const registry = compileRegistry({ bindings: { 'cli://local/git/status': 'git status' } });
  const result = await run('cli://local/git/status', registry, null, { mode: 'execute' });
  assert.equal(result.ok, false);
  assert.equal(result.error.type, 'policy');
});
