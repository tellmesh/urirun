// Browser-safe urihandler v7 runtime: policy gate + dry-run/execute, plus
// named parameter binding ({name} from query/payload/positional/target),
// string shorthand bindings, and Docker adapters. Mirrors urihandler/v7.py.

const URI_RE = /^(?<scheme>[a-z][a-z0-9+.-]*):\/\/(?<target>[^/?#]+)(?<path>\/[^?#]*)?(?:\?(?<query>[^#]*))?(?:#(?<fragment>.*))?$/i;
const PLACEHOLDER_RE = /\{([a-zA-Z0-9_.]+)\}/g;
const COMMAND_KEYS = ['command', 'template', 'method', 'url', 'topicPrefix'];
const PROCESS_KEYS = ['image', 'mount', 'env', 'stdin', 'timeout', 'cwd', 'params'];
const DESTRUCTIVE_HINTS = ['rm', 'delete', 'destroy', 'drop', 'shutdown', 'reboot', 'format', 'wipe'];

export function parseUri(uri) {
  const match = String(uri).match(URI_RE);
  if (!match) throw new Error(`Invalid URI: ${uri}`);
  const segments = (match.groups.path || '/').split('/').filter(Boolean).map(decodeURIComponent);
  return {
    package: match.groups.scheme,
    target: decodeURIComponent(match.groups.target),
    segments,
    query: Object.fromEntries(new URLSearchParams(match.groups.query || '')),
    normalized: `${match.groups.scheme}://${decodeURIComponent(match.groups.target)}/${segments.map(encodeURIComponent).join('/')}`,
    raw: uri,
  };
}

export function translate(descriptor) {
  if (descriptor.segments.length < 2) throw new Error(`URI must include resource and operation: ${descriptor.raw}`);
  const [resource, operation, ...args] = descriptor.segments;
  return { package: descriptor.package, target: descriptor.target, resource, operation, args,
    route: [descriptor.package, resource, operation], descriptor };
}

export function routeKey(uri) {
  return translate(parseUri(uri)).route.join('.');
}

export function tokenize(value) {
  const tokens = [];
  const re = /"([^"]*)"|'([^']*)'|(\S+)/g;
  let match;
  while ((match = re.exec(value)) !== null) tokens.push(match[1] ?? match[2] ?? match[3]);
  return tokens;
}

export function expandBinding(uri, binding) {
  if (typeof binding === 'string') {
    return { uri, kind: 'cli', adapter: 'spawn', config: { command: tokenize(binding) }, meta: {} };
  }
  const expanded = { ...binding };
  const config = { ...(expanded.config || {}) };
  for (const key of [...COMMAND_KEYS, ...PROCESS_KEYS]) {
    if (expanded[key] !== undefined) { config[key] = expanded[key]; delete expanded[key]; }
  }
  return {
    uri,
    kind: expanded.kind || 'function',
    adapter: expanded.adapter || expanded.kind || 'local-function',
    config,
    ref: expanded.ref,
    policy: expanded.policy || {},
    meta: expanded.meta || {},
  };
}

export function compileBindings(bindingMap) {
  const entries = bindingMap.bindings || bindingMap;
  const routes = {};
  for (const [uri, binding] of Object.entries(entries)) {
    const key = routeKey(uri);
    if (routes[key]) throw new Error(`Duplicate route: ${key}`);
    routes[key] = expandBinding(uri, binding);
  }
  return routes;
}

// --- parameter binding ------------------------------------------------------
export function resolveParams(entry, descriptor, translation, payload) {
  const spec = (entry.config && entry.config.params) || entry.params || {};
  const values = { ...(descriptor.query || {}) };
  if (payload && typeof payload === 'object' && !Array.isArray(payload)) Object.assign(values, payload);
  values.target = translation.target;
  translation.args.forEach((arg, index) => { values[String(index)] = arg; });

  const missing = [];
  for (const [name, rule = {}] of Object.entries(spec)) {
    const current = values[name];
    if (current === undefined || current === null || current === '') {
      if ('default' in rule) values[name] = rule.default;
      else if (rule.required) missing.push(name);
    }
  }
  if (missing.length) throw Object.assign(new Error(`missing required params: ${missing.sort().join(', ')}`), { paramsError: true });
  return values;
}

export function renderValue(value, params) {
  return String(value).replace(PLACEHOLDER_RE, (_, key) => {
    if (!(key in params)) throw Object.assign(new Error(`unresolved placeholder: ${key}`), { paramsError: true });
    return String(params[key]);
  });
}

export function renderCommand(command, params) {
  return command.map((part) => renderValue(part, params));
}

function hasPlaceholders(parts) {
  return parts.some((part) => /\{[a-zA-Z0-9_.]+\}/.test(String(part)));
}

// --- policy ---------------------------------------------------------------
export function defaultPolicy() {
  return { execute: { allow: [], deny: [] }, allowShellTemplates: false, maxArgs: 16 };
}

export function mergePolicy(policy = {}) {
  const merged = defaultPolicy();
  for (const [key, value] of Object.entries(policy)) if (key !== 'execute') merged[key] = value;
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
  if (entry.kind === 'shell' || entry.adapter === 'shell-template') {
    if (!(routePolicy.allowExecute || policy.allowShellTemplates)) {
      return { allowed: false, reason: 'shell templates require allowShellTemplates' };
    }
  }
  let allowed = routePolicy.allowExecute === true;
  let reason = allowed ? 'route policy allows execution' : '';
  if (!allowed) {
    const allowMatch = matchesAny(uri, execute.allow || []);
    if (allowMatch) { allowed = true; reason = `matched allow pattern '${allowMatch}'`; }
  }
  if (!allowed) return { allowed: false, reason: 'no allow rule matched (default deny)' };
  const decision = { allowed: true, reason };
  if (routePolicy.requireConfirm || looksDestructive(entry, args)) decision.requireConfirm = true;
  return decision;
}

// --- runtime ----------------------------------------------------------------
export function createUriRuntimeV7({ bindings, adapters, refs = {}, state = {}, policy = {} }) {
  const routes = compileBindings(bindings);
  let activePolicy = mergePolicy(policy);

  const setPolicy = (next) => { activePolicy = mergePolicy(next); return activePolicy; };
  const getPolicy = () => activePolicy;

  function listRoutes(p = activePolicy) {
    const merged = mergePolicy(p);
    return Object.values(routes).map((entry) => {
      const translation = translate(parseUri(entry.uri));
      return {
        uri: entry.uri,
        kind: entry.kind,
        adapter: entry.adapter,
        params: (entry.config && entry.config.params) || {},
        meta: entry.meta || {},
        decision: evaluatePolicy(entry.uri, entry, { args: translation.args }, merged),
      };
    }).sort((a, b) => a.uri.localeCompare(b.uri));
  }

  // Render the command/url for a route without executing - powers live preview.
  function preview(uri, payload = {}) {
    const descriptor = parseUri(uri);
    const translation = translate(descriptor);
    const entry = routes[translation.route.join('.')];
    if (!entry) throw new Error(`Route not found: ${uri}`);
    const params = resolveParams(entry, descriptor, translation, payload);
    const config = entry.config || {};
    if (config.url !== undefined) return renderValue(config.url, params);
    if (config.template !== undefined) return renderValue(config.template, params);
    if (entry.adapter === 'docker-exec') return ['docker', 'exec', translation.target, ...renderCommand(config.command || [], params)].join(' ');
    if (entry.adapter === 'docker-run') return ['docker', 'run', '--rm', config.image, ...renderCommand(config.command || [], params)].join(' ');
    let command = renderCommand(config.command || [], params);
    if (!hasPlaceholders(config.command || [])) command = command.concat(translation.args.map(String));
    return command.join(' ');
  }

  async function dispatch(uri, payload = {}, { mode = 'dry-run', policy: override, confirm = false } = {}) {
    const merged = override ? mergePolicy(override) : activePolicy;
    const descriptor = parseUri(uri);
    const translation = translate(descriptor);
    const entry = routes[translation.route.join('.')];
    if (!entry) throw new Error(`Route not found: ${translation.route.join('.')}`);

    const envelope = { uri: entry.uri, mode, kind: entry.kind, adapter: entry.adapter };
    let params;
    try {
      params = resolveParams(entry, descriptor, translation, payload);
    } catch (err) {
      envelope.ok = false;
      envelope.error = { type: 'params', message: err.message };
      return envelope;
    }

    const ctx = { entry, descriptor, translation, target: translation.target, args: translation.args, payload, params, refs, state, dispatch, mode, policy: merged, confirm };
    const decision = evaluatePolicy(entry.uri, entry, ctx, merged);
    envelope.decision = decision;
    const adapter = adapters[entry.adapter] || adapters[entry.kind];
    if (!adapter) throw new Error(`Adapter not found: ${entry.adapter || entry.kind}`);

    if (mode !== 'execute') {
      try { envelope.result = await adapter({ ...ctx, mode: 'dry-run' }); envelope.ok = true; }
      catch (err) { envelope.ok = false; envelope.error = { type: err.paramsError ? 'params' : 'error', message: err.message }; }
      return envelope;
    }
    if (!decision.allowed) { envelope.ok = false; envelope.error = { type: 'policy', message: decision.reason }; return envelope; }
    if (decision.requireConfirm && !confirm) { envelope.ok = false; envelope.error = { type: 'confirm', message: 'route requires confirmation' }; return envelope; }
    try { envelope.result = await adapter(ctx); envelope.ok = envelope.result?.ok !== false; }
    catch (err) { envelope.ok = false; envelope.error = { type: err.paramsError ? 'params' : (err.name || 'Error'), message: err.message }; }
    return envelope;
  }

  return { dispatch, preview, listRoutes, routes, state, setPolicy, getPolicy, renderCommand };
}
