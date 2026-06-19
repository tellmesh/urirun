const URI_RE = /^(?<scheme>[a-z][a-z0-9+.-]*):\/\/(?<target>[^/?#]+)(?<path>\/[^?#]*)?(?:\?(?<query>[^#]*))?(?:#(?<fragment>.*))?$/i;
const CONFIG_KEYS = ['command', 'template', 'method', 'url', 'topicPrefix', 'steps'];

export function parseUri(uri) {
  const match = String(uri).match(URI_RE);
  if (!match) throw new Error(`Invalid URI: ${uri}`);
  const segments = (match.groups.path || '/').split('/').filter(Boolean).map(decodeURIComponent);
  return {
    package: match.groups.scheme,
    target: decodeURIComponent(match.groups.target),
    segments,
    normalized: `${match.groups.scheme}://${decodeURIComponent(match.groups.target)}/${segments.map(encodeURIComponent).join('/')}`,
    query: Object.fromEntries(new URLSearchParams(match.groups.query || '')),
    fragment: match.groups.fragment || null,
    raw: uri,
  };
}

export function translate(descriptor) {
  if (descriptor.segments.length < 2) {
    throw new Error(`URI must include resource and operation: ${descriptor.raw}`);
  }
  const [resource, operation, ...args] = descriptor.segments;
  return {
    package: descriptor.package,
    target: descriptor.target,
    resource,
    operation,
    args,
    route: [descriptor.package, resource, operation],
    descriptor,
  };
}

export function routeKey(uri) {
  return translate(parseUri(uri)).route.join('.');
}

export function normalizeBinding(binding = {}) {
  const config = { ...(binding.config || {}) };
  for (const key of CONFIG_KEYS) {
    if (binding[key] !== undefined) config[key] = binding[key];
  }
  return {
    kind: binding.kind || 'function',
    adapter: binding.adapter || binding.kind || 'local-function',
    config,
    ref: binding.ref,
    meta: binding.meta || {},
  };
}

export function compileBindings(bindingMap) {
  const entries = bindingMap.bindings || bindingMap;
  const routes = {};
  for (const [uri, binding] of Object.entries(entries)) {
    const key = routeKey(uri);
    if (routes[key]) throw new Error(`Duplicate route: ${key}`);
    routes[key] = { uri, ...normalizeBinding(binding) };
  }
  return routes;
}

export function createUriRuntime({ bindings, adapters, refs = {}, state = {} }) {
  const routes = compileBindings(bindings);

  function resolve(uri) {
    const descriptor = parseUri(uri);
    const translation = translate(descriptor);
    const route = translation.route.join('.');
    const entry = routes[route];
    if (!entry) throw new Error(`Route not found: ${route}`);
    const adapter = adapters[entry.adapter] || adapters[entry.kind];
    if (!adapter) throw new Error(`Adapter not found: ${entry.adapter || entry.kind}`);
    return { adapter, descriptor, entry, route, translation };
  }

  function listRoutes() {
    return Object.values(routes)
      .map((entry) => {
        const translation = translate(parseUri(entry.uri));
        return {
          uri: entry.uri,
          kind: entry.kind,
          adapter: entry.adapter,
          meta: entry.meta,
          route: translation.route,
          target: translation.target,
          args: translation.args,
        };
      })
      .sort((a, b) => a.uri.localeCompare(b.uri));
  }

  async function dispatch(uri, payload = {}) {
    const { adapter, descriptor, entry, translation } = resolve(uri);
    return adapter({ entry, descriptor, translation, payload, refs, state, dispatch });
  }

  async function dispatchEnvelope(uri, payload = {}) {
    try {
      const { adapter, descriptor, entry, translation } = resolve(uri);
      const result = await adapter({ entry, descriptor, translation, payload, refs, state, dispatch });
      return {
        uri: descriptor.normalized,
        kind: entry.kind,
        adapter: entry.adapter,
        ok: result?.ok !== false,
        result,
      };
    } catch (error) {
      return {
        uri,
        ok: false,
        error: { type: error.name || 'Error', message: error.message },
      };
    }
  }

  return { dispatch, dispatchEnvelope, listRoutes, resolve, routes, state };
}
