import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createUriRuntimeV1 } from './uri-runtime-v1.js';

const bindings = JSON.parse(await readFile(new URL('./bindings.json', import.meta.url), 'utf8'));
const policy = JSON.parse(await readFile(new URL('./policy.json', import.meta.url), 'utf8'));

const render = (command, params) => command.map((p) => String(p).replace(/\{([a-zA-Z0-9_.]+)\}/g, (_, k) => String(params[k])));

const adapters = {
  spawn: async ({ entry, params }) => ({ ok: true, simulated: true, type: 'cli', command: render(entry.config.command || [], params) }),
  'shell-template': async ({ entry, params }) => ({ ok: true, type: 'shell', command: String(entry.config.template).replace(/\{([a-zA-Z0-9_.]+)\}/g, (_, k) => String(params[k])) }),
  'docker-exec': async ({ entry, params, target }) => ({ ok: true, type: 'docker', command: ['docker', 'exec', target, ...render(entry.config.command || [], params)] }),
  'docker-run': async ({ entry, params }) => ({ ok: true, type: 'docker', command: ['docker', 'run', '--rm', entry.config.image, ...render(entry.config.command || [], params)] }),
  fetch: async ({ entry, params }) => ({ ok: true, simulated: true, type: 'http', url: String(entry.config.url).replace(/\{([a-zA-Z0-9_.]+)\}/g, (_, k) => String(params[k])) }),
};

const runtime = createUriRuntimeV1({ bindings, adapters, policy });

assert.equal(Object.keys(runtime.routes).length, 7);

// Live preview renders the exact command from params + defaults.
assert.equal(
  runtime.preview('media://local/video/transcode', { input: 'a.mp4', output: 'b.mp4' }),
  'ffmpeg -i a.mp4 -vf scale=1280:720 b.mp4',
);

// Dry-run dispatch carries the rendered command.
const dry = await runtime.dispatch('media://local/video/transcode', { input: 'a.mp4', output: 'b.mp4' });
assert.equal(dry.mode, 'dry-run');
assert.deepEqual(dry.result.command, ['ffmpeg', '-i', 'a.mp4', '-vf', 'scale=1280:720', 'b.mp4']);

// Missing required param is a params error, before anything runs.
const missing = await runtime.dispatch('media://local/video/transcode', { output: 'b.mp4' });
assert.equal(missing.ok, false);
assert.equal(missing.error.type, 'params');

// Docker exec uses the target as the container.
const backup = await runtime.dispatch('container://api/db/backup', { database: 'app' }, { mode: 'execute', policy });
assert.deepEqual(backup.result.command, ['docker', 'exec', 'api', 'pg_dump', '-U', 'postgres', 'app']);

// String shorthand expands to a spawn command.
const git = await runtime.dispatch('cli://local/git/status');
assert.deepEqual(git.result.command, ['git', 'status']);

// shell:// is denied in execute mode by policy.json.
const shell = await runtime.dispatch('shell://local/system/restart', { service: 'nginx' }, { mode: 'execute', policy });
assert.equal(shell.ok, false);
assert.equal(shell.error.type, 'policy');

// http endpoint renders the URL in dry-run.
assert.equal(runtime.preview('api://github/repo/get', {}), 'https://api.github.com/repos/tellmesh/urirun');

console.log('PASS html_uri_app v1');
