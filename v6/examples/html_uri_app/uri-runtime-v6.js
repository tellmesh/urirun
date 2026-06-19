// Browser-safe urihandler v6 runtime: the same URI contract as v5, plus a
// policy gate, a dry-run/execute mode, and a uniform result envelope. It mirrors
// adapters/python/urihandler/v6.py so the browser behaves like the CLI.

const URI_RE = /^(?<scheme>[a-z][a-z0-9+.-]*):\/\/(?<target>[^/?#]+)(?<path>\/[^?#]*)?(?:\?(?<query>[^#]*))?(?:#(?<fragment>.*))?$/i;
const CONFIG_KEYS = ['command', 'template', 'method', 'url', 'topicPrefix', 'steps'];
const DESTRUCTIVE_HINTS = ['rm', 'delete', 'destroy', 'drop', 'shutdown', 'reboot', 'format', 'wipe'];

export function parseUri(uri) {
  const match = String(uri).match(URI_RE);
  if (!match) throw new Error(`Invalid URI: ${uri}`);
  const segments = (match.groups.path || '/').split('/').filter(Boolean).map(decodeURIComponent);
  return {
    package: match.groups.scheme,
    target: decodeURIComponent(match.groups.target),
    segments,
    normalized: `${match.groups.scheme}://${decodeURIComponent(match.groups.target)}/${segments.map(encodeURIComponent).join('/')}`,
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
    policy: binding.policy || {},
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

export function defaultPolicy() {
  return { execute: { allow: [], deny: [] }, allowShellTemplates: false, maxArgs: 16 };
}

export function mergePolicy(policy = {}) {
  const merged = defaultPolicy();
  for (const [key, value] of Object.entries(policy)) {
    if (key !== 'execute') merged[key] = value;
  }
  const execute = policy.execute || {};
  merged.execute = { allow: [...(execute.allow || [])], deny: [...(execute.deny || [])] };
  return merged;
}

function globToRegExp(pattern) {
  const escaped = pattern.replace(/[.+^${}()|[\]\\?]/g, '\\$&').replace(/\*/g, '.*');
  return new RegExp('^' + escaped + '$');
}

function matchesAny(uri, patterns) {
  return patterns.find((pattern) => globToRegExp(pattern).test(uri)) || null;
}

function looksDestructive(entry, args) {
  const words = [...(entry.config.command || []), entry.config.template || '', ...args]
    .flatMap((piece) => String(piece).toLowerCase().split(/\s+/));
  return DESTRUCTIVE_HINTS.some((hint) => words.includes(hint));
}

export function evaluatePolicy(uri, entry, ctx, policy) {
  const routePolicy = entry.policy || {};
  const execute = policy.execute || {};
  const args = ctx.args || [];

  if (routePolicy.deny === true) return { allowed: false, reason: 'route policy denies execution' };

  const denyMatch = matchesAny(uri, execute.deny || []);
  if (denyMatch) return { allowed: false, reason: `matched deny pattern '${denyMatch}'` };

  const maxArgs = routePolicy.maxArgs ?? policy.maxArgs ?? 16;
  if (maxArgs != null && args.length > maxArgs) {
    return { allowed: false, reason: `too many arguments (${args.length} > ${maxArgs})` };
  }

  if (entry.kind === 'shell' || entry.adapter === 'shell-template') {
    if (!(routePolicy.allowExecute || policy.allowShellTemplates)) {
      return { allowed: false, reason: 'shell templates require allowShellTemplates' };
    }
  }

  let allowed = routePolicy.allowExecute === true;
  let reason = allowed ? 'route policy allows execution' : '';
  if (!allowed) {
    const allowMatch = matchesAny(uri, execute.allow || []);
    if (allowMatch) {
      allowed = true;
      reason = `matched allow pattern '${allowMatch}'`;
    }
  }
  if (!allowed) return { allowed: false, reason: 'no allow rule matched (default deny)' };

  const decision = { allowed: true, reason };
  if (routePolicy.requireConfirm || looksDestructive(entry, args)) decision.requireConfirm = true;
  return decision;
}

export function createUriRuntimeV6({ bindings, adapters, refs = {}, state = {}, policy = {} }) {
  const routes = compileBindings(bindings);
  let activePolicy = mergePolicy(policy);

  function setPolicy(next) {
    activePolicy = mergePolicy(next);
    return activePolicy;
  }

  function getPolicy() {
    return activePolicy;
  }

  function listRoutes(p = activePolicy) {
    const merged = mergePolicy(p);
    return Object.values(routes)
      .map((entry) => {
        const translation = translate(parseUri(entry.uri));
        return {
          uri: entry.uri,
          kind: entry.kind,
          adapter: entry.adapter,
          meta: entry.meta,
          decision: evaluatePolicy(entry.uri, entry, { args: translation.args }, merged),
        };
      })
      .sort((a, b) => a.uri.localeCompare(b.uri));
  }

  async function dispatch(uri, payload = {}, { mode = 'dry-run', policy: override, confirm = false } = {}) {
    const merged = override ? mergePolicy(override) : activePolicy;
    const descriptor = parseUri(uri);
    const translation = translate(descriptor);
    const route = translation.route.join('.');
    const entry = routes[route];
    if (!entry) throw new Error(`Route not found: ${route}`);

    const decision = evaluatePolicy(entry.uri, entry, { args: translation.args }, merged);
    const envelope = { uri: entry.uri, mode, kind: entry.kind, adapter: entry.adapter, decision };
    const adapter = adapters[entry.adapter] || adapters[entry.kind];
    if (!adapter) throw new Error(`Adapter not found: ${entry.adapter || entry.kind}`);

    const ctx = { entry, descriptor, translation, payload, refs, state, dispatch, mode, policy: merged, confirm };

    if (mode !== 'execute') {
      envelope.ok = true;
      envelope.result = await adapter({ ...ctx, mode: 'dry-run' });
      return envelope;
    }
    if (!decision.allowed) {
      envelope.ok = false;
      envelope.error = { type: 'policy', message: decision.reason };
      return envelope;
    }
    if (decision.requireConfirm && !confirm) {
      envelope.ok = false;
      envelope.error = { type: 'confirm', message: 'route requires confirmation' };
      return envelope;
    }
    try {
      envelope.result = await adapter(ctx);
      envelope.ok = envelope.result?.ok !== false;
    } catch (error) {
      envelope.ok = false;
      envelope.error = { type: error.name || 'Error', message: error.message };
    }
    return envelope;
  }

  return { dispatch, listRoutes, routes, state, setPolicy, getPolicy };
}
