import {
  buildRegistryDocument,
  discoverDockerLabels,
  discoverManifest,
  dispatchGenerated,
  hydrateRegistry,
  withUriRoute,
} from './urihandler-v4.js';

const ledSet = withUriRoute(
  (target, args, payload) => ({ ok: true, target, state: args[0], payload }),
  'device://device-01/led/set/on',
  { kind: 'function', adapter: 'local-function', ref: 'devices.ledSet' },
);

const routes = [
  ...discoverManifest({
    routes: [
      {
        package: 'cli',
        resource: 'git',
        operation: 'status',
        routeEntry: { kind: 'cli', adapter: 'spawn', config: { command: ['git', 'status'] } },
      },
    ],
  }),
  ...discoverDockerLabels({
    'urihandler.uri': 'service://api/user/create/basic',
    'urihandler.kind': 'http',
    'urihandler.adapter': 'fetch',
    'urihandler.method': 'POST',
    'urihandler.url': 'http://user-service:8080/api/users',
  }),
  {
    uri: 'device://device-01/led/set/on',
    routeEntry: { kind: 'function', adapter: 'local-function', ref: 'devices.ledSet' },
  },
];

const registry = buildRegistryDocument(routes);
const hydrated = hydrateRegistry(registry, { 'devices.ledSet': ledSet });

console.log(await dispatchGenerated('device://device-01/led/set/off', hydrated, { source: 'example' }));
console.log(await dispatchGenerated('cli://local/git/status', registry));
