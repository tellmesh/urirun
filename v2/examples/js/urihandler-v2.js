import { createHash } from 'node:crypto';

export function parseUri(uri) {
  const match = String(uri).match(/^(?<scheme>[a-z][a-z0-9+.-]*):\/\/(?<target>[^/?#]+)(?<path>\/[^?#]*)?(?:\?(?<query>[^#]*))?(?:#(?<fragment>.*))?$/i);
  if (!match) throw new Error(`Invalid URI: ${uri}`);
  const segments = (match.groups.path || '/').split('/').filter(Boolean).map(decodeURIComponent);
  return {
    package: match.groups.scheme,
    target: decodeURIComponent(match.groups.target),
    segments,
    query: Object.fromEntries(new URLSearchParams(match.groups.query || '')),
    fragment: match.groups.fragment || null,
    raw: uri,
  };
}

export function normalizeUri(d) {
  return `${d.package}://${d.target}/${d.segments.map(encodeURIComponent).join('/')}`;
}

export function translate(d) {
  const [resource, operation, ...rest] = d.segments;
  return {
    route: [d.package, resource, operation],
    args: [d.target, ...rest],
    package: d.package,
    target: d.target,
    resource,
    operation,
    descriptor: { ...d, normalized: normalizeUri(d) },
  };
}

export function validate(t, registry) {
  return !!registry?.[t.package]?.[t.resource]?.[t.operation];
}

export function hashUri(normalized) {
  return createHash('sha256').update(normalized).digest('hex');
}

export function resolve(t, registry, runtimeCache = new Map()) {
  const key = hashUri(t.descriptor.normalized);
  if (runtimeCache.has(key)) return runtimeCache.get(key);
  const fn = registry?.[t.package]?.[t.resource]?.[t.operation];
  if (typeof fn !== 'function') throw new Error(`Unresolved route: ${t.route.join('.')}`);
  runtimeCache.set(key, fn);
  return fn;
}

export async function dispatch(uri, registry, payload, runtimeCache = new Map()) {
  const descriptor = parseUri(uri);
  const translation = translate(descriptor);
  if (!validate(translation, registry)) throw new Error('Route validation failed');
  const fn = resolve(translation, registry, runtimeCache);
  return await fn(translation.target, translation.args.slice(1), payload, translation.descriptor);
}
