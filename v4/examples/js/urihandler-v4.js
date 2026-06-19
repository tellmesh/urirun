import { createHash } from 'node:crypto';
import {
  dispatch as dispatchV3,
  executors as v3Executors,
  parseUri,
  translate,
} from '../../../v3/examples/js/urihandler-v3.js';

export const REGISTRY_VERSION = 'urihandler.registry.v4';
const HTTP_METHODS = new Set(['delete', 'get', 'head', 'options', 'patch', 'post', 'put']);
const ROUTE_ENTRY_KEYS = new Set(['adapter', 'config', 'kind', 'meta', 'policy', 'ref']);

export function hashUri(normalized) {
  return createHash('sha256').update(normalized).digest('hex');
}

export function defaultAdapter(kind = 'function') {
  return {
    artifact: 'spawn',
    cli: 'spawn',
    event: 'local-function',
    function: 'local-function',
    http: 'fetch',
    mqtt: 'mqtt-publish',
    process: 'spawn',
    shell: 'shell-template',
  }[kind] || kind || 'local-function';
}

export function normalizeRouteEntry(routeEntry = {}) {
  const entry = {};
  for (const [key, value] of Object.entries(routeEntry || {})) {
    if (ROUTE_ENTRY_KEYS.has(key)) entry[key] = value;
  }
  entry.kind ||= routeEntry.type || 'function';
  entry.adapter ||= defaultAdapter(entry.kind);
  entry.config = { ...(entry.config || {}) };
  return entry;
}

export function routeFromUri(uri, routeEntry = {}, source = {}) {
  const descriptor = parseUri(uri);
  const translation = translate(descriptor);
  return {
    uri: descriptor.normalized,
    route: translation.route,
    package: translation.package,
    resource: translation.resource,
    operation: translation.operation,
    routeEntry: normalizeRouteEntry(routeEntry),
    source: { ...source },
  };
}

export function routeFromParts(packageName, resource, operation, routeEntry = {}, source = {}, target = '_') {
  const uri = `${packageName}://${target}/${encodeURIComponent(resource)}/${encodeURIComponent(operation)}`;
  const route = routeFromUri(uri, routeEntry, source);
  route.uri = uri;
  return route;
}

export function coerceRouteSource(item, defaultSource = {}) {
  const source = { ...defaultSource, ...(item.source || {}) };
  const routeEntry = item.routeEntry || item.route_entry || Object.fromEntries(
    Object.entries(item).filter(([key]) => ROUTE_ENTRY_KEYS.has(key)),
  );

  if (item.uri) return routeFromUri(item.uri, routeEntry, source);

  if (item.package && item.resource && item.operation) {
    return routeFromParts(item.package, item.resource, item.operation, routeEntry, source, item.target || '_');
  }

  throw new Error(`Cannot convert route source to registry entry: ${JSON.stringify(item)}`);
}

function stableStringify(value) {
  if (Array.isArray(value)) return `[${value.map((item) => stableStringify(item)).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

function routeEntryEqual(left, right) {
  return stableStringify(left) === stableStringify(right);
}

export function addRoute(registryTree, route, routeEntry, { onConflict = 'error' } = {}) {
  const [packageName, resource, operation] = route;
  registryTree[packageName] ||= {};
  registryTree[packageName][resource] ||= {};
  const existing = registryTree[packageName][resource][operation];
  if (existing && !routeEntryEqual(existing, routeEntry)) {
    if (onConflict === 'replace') {
      registryTree[packageName][resource][operation] = routeEntry;
      return;
    }
    if (onConflict === 'keep') return;
    throw new Error(`Route conflict: ${route.join('.')}`);
  }
  registryTree[packageName][resource][operation] = routeEntry;
}

export function flattenRegistryTree(registryTree, source = { type: 'registry-tree' }) {
  const entries = [];
  for (const [packageName, resources] of Object.entries(registryTree || {})) {
    for (const [resource, operations] of Object.entries(resources || {})) {
      for (const [operation, routeEntry] of Object.entries(operations || {})) {
        entries.push(routeFromParts(packageName, resource, operation, routeEntry, source));
      }
    }
  }
  return entries;
}

function getRouteEntry(registryTree, route) {
  const [packageName, resource, operation] = route;
  return registryTree[packageName][resource][operation];
}

export function flattenRegistryDocument(document, source = { type: 'registry' }) {
  const index = document.index || {};
  if (!Object.keys(index).length) return flattenRegistryTree(document.routes || {}, source);

  return Object.values(index).map((meta) => ({
    uri: meta.uri,
    routeEntry: getRouteEntry(document.routes || {}, meta.route),
    source: meta.source || source,
  }));
}

export function discoverManifest(manifest, source = {}) {
  const defaultSource = { type: 'manifest', ...source };
  if (Array.isArray(manifest)) return manifest.map((item) => coerceRouteSource(item, defaultSource));
  if (manifest.version === REGISTRY_VERSION) return flattenRegistryDocument(manifest, { type: 'registry', ...source });
  if (Array.isArray(manifest.routes)) return manifest.routes.map((item) => coerceRouteSource(item, defaultSource));
  if (Array.isArray(manifest.entries)) return manifest.entries.map((item) => coerceRouteSource(item, defaultSource));
  if (manifest.uri || (manifest.package && manifest.resource && manifest.operation)) return [coerceRouteSource(manifest, defaultSource)];
  if (manifest.routes && typeof manifest.routes === 'object') return flattenRegistryTree(manifest.routes, defaultSource);
  return flattenRegistryTree(manifest, defaultSource);
}

export function buildRegistryDocument(routeSources, { generatedAt = new Date().toISOString(), onConflict = 'error' } = {}) {
  const routes = {};
  const index = {};
  const sources = [];
  const seenSources = new Set();

  for (const item of routeSources) {
    const route = coerceRouteSource(item);
    addRoute(routes, route.route, route.routeEntry, { onConflict });
    const source = route.source || {};
    index[hashUri(route.uri)] = { uri: route.uri, route: route.route, source };
    const sourceKey = JSON.stringify(source);
    if (Object.keys(source).length && !seenSources.has(sourceKey)) {
      seenSources.add(sourceKey);
      sources.push(source);
    }
  }

  return {
    version: REGISTRY_VERSION,
    generatedAt,
    routeCount: Object.keys(index).length,
    routes,
    index,
    sources,
  };
}

function parseCommand(value) {
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) return parsed.map(String);
  } catch {
    // Shell-like splitting without bringing a dependency is intentionally simple.
  }
  return String(value).match(/"[^"]+"|'[^']+'|\S+/g)?.map((part) => part.replace(/^['"]|['"]$/g, '')) || [];
}

export function discoverDockerLabels(labels, source = {}) {
  if (!['1', 'true', 'yes', 'on'].includes(String(labels['urihandler.enabled'] ?? 'true').toLowerCase())) return [];

  const kind = labels['urihandler.kind'] || 'http';
  const config = {};
  for (const [key, value] of Object.entries(labels)) {
    if (key.startsWith('urihandler.config.')) config[key.replace('urihandler.config.', '')] = value;
  }
  for (const [labelKey, configKey] of Object.entries({
    'urihandler.method': 'method',
    'urihandler.template': 'template',
    'urihandler.topicPrefix': 'topicPrefix',
    'urihandler.url': 'url',
  })) {
    if (labels[labelKey]) config[configKey] = labels[labelKey];
  }
  if (labels['urihandler.command']) config.command = parseCommand(labels['urihandler.command']);

  const routeEntry = { kind, adapter: labels['urihandler.adapter'] || defaultAdapter(kind), config };
  const mergedSource = { type: 'docker-labels', ...source };
  if (labels['urihandler.uri']) return [routeFromUri(labels['urihandler.uri'], routeEntry, mergedSource)];
  if (labels['urihandler.package'] && labels['urihandler.resource'] && labels['urihandler.operation']) {
    return [
      routeFromParts(
        labels['urihandler.package'],
        labels['urihandler.resource'],
        labels['urihandler.operation'],
        routeEntry,
        mergedSource,
        labels['urihandler.target'] || '_',
      ),
    ];
  }
  throw new Error('Docker labels require urihandler.uri or package/resource/operation');
}

export function discoverDockerInspect(inspectData) {
  const containers = Array.isArray(inspectData) ? inspectData : [inspectData];
  return containers.flatMap((container) => {
    const labels = container?.Config?.Labels || container?.Labels || {};
    if (!Object.keys(labels).length) return [];
    const source = {
      type: 'docker',
      id: container.Id,
      name: container.Names?.[0] || container.Name,
    };
    return discoverDockerLabels(labels, source);
  });
}

function operationFromMethod(method) {
  return { delete: 'delete', get: 'query', patch: 'update', post: 'create', put: 'update' }[method] || method;
}

function defaultOpenApiRoute(method, path, operation, packageName, target) {
  if (operation.operationId) {
    const parts = String(operation.operationId).split(/[_:.-]+/).filter(Boolean);
    if (parts.length >= 2) return `${packageName}://${target}/${encodeURIComponent(parts[0])}/${encodeURIComponent(parts[1])}`;
  }
  const pathParts = path.split('/').filter((part) => part && !part.startsWith('{'));
  const resource = (pathParts.at(-1) || 'root').replace(/s$/, '');
  return `${packageName}://${target}/${encodeURIComponent(resource)}/${operationFromMethod(method)}`;
}

export function discoverOpenApi(spec, { baseUrl = '', packageName = 'service', target = 'api', source = {} } = {}) {
  const entries = [];
  for (const [path, pathItem] of Object.entries(spec.paths || {})) {
    for (const [method, operation] of Object.entries(pathItem || {})) {
      if (!HTTP_METHODS.has(method.toLowerCase()) || typeof operation !== 'object') continue;
      const uri = operation['x-urihandler-uri'] || defaultOpenApiRoute(method.toLowerCase(), path, operation, packageName, target);
      entries.push(routeFromUri(uri, {
        kind: 'http',
        adapter: 'fetch',
        config: { method: method.toUpperCase(), url: `${baseUrl.replace(/\/$/, '')}${path}` },
      }, { type: 'openapi', method: method.toUpperCase(), path, ...source }));
    }
  }
  return entries;
}

export function withUriRoute(fn, uri, routeEntry = {}) {
  fn.uriHandlerRoute = {
    uri,
    routeEntry: normalizeRouteEntry({ ...routeEntry, ref: routeEntry.ref || fn.name }),
  };
  return fn;
}

export function discoverObjectRoutes(modules) {
  const entries = [];
  for (const [moduleName, moduleExports] of Object.entries(modules)) {
    for (const [exportName, value] of Object.entries(moduleExports)) {
      const meta = value?.uriHandlerRoute;
      if (!meta) continue;
      const routeEntry = { ...meta.routeEntry, ref: meta.routeEntry?.ref || `${moduleName}.${exportName}` };
      entries.push(routeFromUri(meta.uri, routeEntry, { type: 'js', module: moduleName, export: exportName }));
    }
  }
  return entries;
}

export function registryTree(registry) {
  return registry?.routes || registry;
}

function walkRouteEntries(node, visit) {
  if (!node || typeof node !== 'object') return;
  if (node.kind && node.adapter) {
    visit(node);
    return;
  }
  for (const value of Object.values(node)) walkRouteEntries(value, visit);
}

export function hydrateRegistry(registry, refs) {
  const hydrated = structuredClone(registry);
  walkRouteEntries(registryTree(hydrated), (routeEntry) => {
    if (typeof routeEntry.ref === 'string' && refs[routeEntry.ref]) routeEntry.ref = refs[routeEntry.ref];
  });
  return hydrated;
}

export const generatedExecutors = {
  ...v3Executors,
  'local-function': async (ctx) => {
    if (typeof ctx.routeEntry.ref === 'function') return v3Executors['local-function'](ctx);
    return {
      ok: true,
      simulated: true,
      type: 'function',
      ref: ctx.routeEntry.ref,
      target: ctx.target,
      args: ctx.args,
      payload: ctx.payload,
    };
  },
};

export async function dispatchGenerated(uri, registry, payload, runtimeCache = new Map(), executorRegistry = generatedExecutors) {
  return dispatchV3(uri, registryTree(registry), payload, runtimeCache, executorRegistry);
}
