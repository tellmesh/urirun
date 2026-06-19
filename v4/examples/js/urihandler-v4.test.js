import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildRegistryDocument,
  discoverDockerLabels,
  discoverManifest,
  discoverObjectRoutes,
  discoverOpenApi,
  dispatchGenerated,
  hydrateRegistry,
  withUriRoute,
} from './urihandler-v4.js';

const ledSet = withUriRoute(
  (target, args, payload) => ({ ok: true, target, state: args[0], payload }),
  'device://device-01/led/set/on',
  { kind: 'function', adapter: 'local-function', ref: 'devices.ledSet' },
);

test('discovers JS handlers, manifests, Docker labels, and OpenAPI operations', () => {
  const jsRoutes = discoverObjectRoutes({ devices: { ledSet } });
  const manifestRoutes = discoverManifest({
    routes: [
      {
        package: 'cli',
        resource: 'git',
        operation: 'status',
        routeEntry: { kind: 'cli', adapter: 'spawn', config: { command: ['git', 'status'] } },
      },
      {
        uri: 'shell://local/system/restart/nginx',
        routeEntry: { kind: 'shell', adapter: 'shell-template', config: { template: 'systemctl restart {0}' } },
      },
    ],
  });
  const dockerRoutes = discoverDockerLabels({
    'urihandler.enabled': 'true',
    'urihandler.uri': 'service://api/user/create/basic',
    'urihandler.kind': 'http',
    'urihandler.adapter': 'fetch',
    'urihandler.method': 'POST',
    'urihandler.url': 'http://user-service:8080/api/users',
  });
  const openApiRoutes = discoverOpenApi({
    paths: {
      '/api/logs': {
        get: {
          operationId: 'log_recent',
          'x-urihandler-uri': 'log://backend/logs/query/recent',
        },
      },
    },
  }, { baseUrl: 'http://backend:8080' });

  const registry = buildRegistryDocument(
    [...jsRoutes, ...manifestRoutes, ...dockerRoutes, ...openApiRoutes],
    { generatedAt: '2026-06-19T00:00:00.000Z' },
  );

  assert.equal(registry.version, 'urihandler.registry.v4');
  assert.equal(registry.routeCount, 5);
  assert.equal(registry.routes.device.led.set.ref, 'devices.ledSet');
  assert.deepEqual(registry.routes.cli.git.status.config.command, ['git', 'status']);
  assert.equal(registry.routes.service.user.create.config.url, 'http://user-service:8080/api/users');
  assert.equal(registry.routes.log.logs.query.config.method, 'GET');
  assert.equal(Object.keys(registry.index).length, 5);
});

test('dispatches generated registry documents and hydrates symbolic refs', async () => {
  const registry = buildRegistryDocument(discoverObjectRoutes({ devices: { ledSet } }));
  const symbolic = await dispatchGenerated('device://device-01/led/set/off', registry, { source: 'test' });
  assert.deepEqual(symbolic, {
    ok: true,
    simulated: true,
    type: 'function',
    ref: 'devices.ledSet',
    target: 'device-01',
    args: ['off'],
    payload: { source: 'test' },
  });

  const hydrated = hydrateRegistry(registry, { 'devices.ledSet': ledSet });
  assert.deepEqual(await dispatchGenerated('device://device-01/led/set/off', hydrated, { source: 'test' }), {
    ok: true,
    target: 'device-01',
    state: 'off',
    payload: { source: 'test' },
  });
});

test('merges registry documents without losing original index URIs', () => {
  const dockerRegistry = buildRegistryDocument(discoverDockerLabels({
    'urihandler.uri': 'service://api/user/create/basic',
    'urihandler.kind': 'http',
    'urihandler.adapter': 'fetch',
    'urihandler.method': 'POST',
    'urihandler.url': 'http://user-service:8080/api/users',
  }), { generatedAt: '2026-06-19T00:00:00.000Z' });

  const merged = buildRegistryDocument(discoverManifest(dockerRegistry), { generatedAt: '2026-06-19T00:00:00.000Z' });
  assert.equal(Object.values(merged.index)[0].uri, 'service://api/user/create/basic');
});
