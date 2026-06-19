import { check, listRoutes, run } from './urihandler-v6.js';

const registry = {
  version: 'urihandler.registry.v4',
  routes: { cli: { echo: { say: { kind: 'cli', adapter: 'spawn', config: { command: ['echo'] } } } } },
  index: { a: { uri: 'cli://local/echo/say', route: ['cli', 'echo', 'say'], source: {} } },
};

// One call to see everything available, with the execute decision applied.
const listed = listRoutes(registry, { execute: { allow: ['cli://local/echo/*'] } });
console.log('routes:', listed.map((r) => `${r.uri} [${r.decision.allowed ? 'allow' : 'deny'}]`).join(', '));

// Default deny: no policy means execute is blocked.
console.log('blocked:', check('cli://local/echo/say/hi', registry).decision.allowed);

// With an allow rule the command actually runs through the gate.
const result = await run('cli://local/echo/say/hello', registry, null, {
  mode: 'execute',
  policy: { execute: { allow: ['cli://local/echo/*'] } },
});
console.log('ok:', result.ok, 'stdout:', result.result.stdout.trim());
