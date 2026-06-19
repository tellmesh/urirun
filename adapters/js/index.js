export function parseUri(uri) {
  const match = String(uri).match(/^(?<scheme>[a-z][a-z0-9+.-]*):\/\/(?<target>[^/?#]+)(?<path>\/[^?#]*)?(?:\?(?<query>[^#]*))?(?:#(?<fragment>.*))?$/i);
  if (!match) throw new Error(`Invalid URI: ${uri}`);
  const path = match.groups.path || '/';
  const segments = path.split('/').filter(Boolean).map(decodeURIComponent);
  return {
    package: match.groups.scheme,
    target: decodeURIComponent(match.groups.target),
    segments,
    query: Object.fromEntries(new URLSearchParams(match.groups.query || '')),
    fragment: match.groups.fragment || null,
    raw: uri,
  };
}

export function buildInvocation(descriptor) {
  const functionName = descriptor.segments.slice(0, 2).join('_');
  const args = [descriptor.target, ...descriptor.segments.slice(2)];
  return { ...descriptor, functionName, args };
}

export async function dispatch(uri, registry, payload) {
  const descriptor = parseUri(uri);
  const invocation = buildInvocation(descriptor);
  const mod = registry[invocation.package];
  if (!mod) throw new Error(`Unknown package: ${invocation.package}`);
  const fn = mod[invocation.functionName];
  if (typeof fn !== 'function') throw new Error(`Unknown function: ${invocation.package}.${invocation.functionName}`);
  return await fn(...invocation.args, payload, invocation);
}
