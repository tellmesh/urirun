import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { parseUri, translate } from '../../../v3/examples/js/urihandler-v3.js';
import { defaultAdapter, registryTree } from '../../../v4/examples/js/urihandler-v4.js';
import { compileRegistryDocument, inferKind } from '../../../v5/examples/js/urihandler-v5.js';
import {
  check as v6check,
  evaluatePolicy,
  listRoutes as v6list,
  mergePolicy,
} from '../../../v6/examples/js/urihandler-v6.js';

const PLACEHOLDER_RE = /\{([a-zA-Z0-9_.]+)\}/g;
const PROCESS_CONFIG_KEYS = ['image', 'mount', 'env', 'stdin', 'timeout', 'cwd', 'params'];
const COMMAND_KEYS = ['command', 'template', 'method', 'url', 'topicPrefix'];
const DEFAULT_TIMEOUT = 30000;
const OUTPUT_LIMIT = 4000;

export { check } from '../../../v6/examples/js/urihandler-v6.js';

export function tokenize(value) {
  const tokens = [];
  const re = /"([^"]*)"|'([^']*)'|(\S+)/g;
  let match;
  while ((match = re.exec(value)) !== null) {
    tokens.push(match[1] ?? match[2] ?? match[3]);
  }
  return tokens;
}

export function resolveParams(routeEntry, descriptor, translation, payload) {
  const spec = (routeEntry.config && routeEntry.config.params) || routeEntry.params || {};
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

function renderCommand(command, params) {
  return command.map((part) => renderValue(part, params));
}

function hasPlaceholders(parts) {
  return parts.some((part) => /\{[a-zA-Z0-9_.]+\}/.test(String(part)));
}

function truncate(text) {
  if (text == null) return '';
  return text.length > OUTPUT_LIMIT ? `${text.slice(0, OUTPUT_LIMIT)}\n...[truncated]` : text;
}

function renderedEnv(config, params) {
  if (!config.env) return undefined;
  const env = { ...process.env };
  for (const [key, value] of Object.entries(config.env)) env[key] = renderValue(String(value), params);
  return env;
}

function runProcess(cmd, rest, config, policy, params, shell = false) {
  const result = spawnSync(cmd, rest, {
    encoding: 'utf-8',
    shell,
    timeout: config.timeout || policy.timeout || DEFAULT_TIMEOUT,
    cwd: config.cwd,
    env: renderedEnv(config, params),
    input: config.stdin,
  });
  return { exitCode: result.status ?? -1, stdout: truncate(result.stdout || ''), stderr: truncate(result.stderr || '') };
}

function envFlags(config, params) {
  const flags = [];
  for (const [key, value] of Object.entries(config.env || {})) flags.push('-e', `${key}=${renderValue(String(value), params)}`);
  return flags;
}

export const executors = {
  spawn: (ctx, policy, execute) => {
    const config = ctx.routeEntry.config || {};
    const base = config.command || [];
    let command = renderCommand(base, ctx.params);
    if (!hasPlaceholders(base)) command = command.concat(ctx.args.map(String));
    if (!command.length) throw new Error('spawn route has no command');
    if (!execute) return { simulated: true, type: 'cli', command };
    const [cmd, ...rest] = command;
    return { type: 'cli', command, ...runProcess(cmd, rest, config, policy, ctx.params) };
  },
  'shell-template': (ctx, policy, execute) => {
    const config = ctx.routeEntry.config || {};
    const rendered = renderValue(config.template || '', ctx.params);
    if (!execute) return { simulated: true, type: 'shell', command: rendered };
    const tokens = tokenize(rendered);
    const [cmd, ...rest] = tokens;
    return { type: 'shell', command: rendered, ...runProcess(cmd, rest, config, policy, ctx.params) };
  },
  'docker-exec': (ctx, policy, execute) => {
    const config = ctx.routeEntry.config || {};
    const inner = renderCommand(config.command || [], ctx.params);
    const flags = [];
    if (config.cwd) flags.push('--workdir', config.cwd);
    flags.push(...envFlags(config, ctx.params));
    const command = ['docker', 'exec', ...flags, ctx.target, ...inner];
    if (!execute) return { simulated: true, type: 'docker', mode: 'exec', container: ctx.target, command };
    const [cmd, ...rest] = command;
    return { type: 'docker', mode: 'exec', container: ctx.target, command, ...runProcess(cmd, rest, config, policy, ctx.params) };
  },
  'docker-run': (ctx, policy, execute) => {
    const config = ctx.routeEntry.config || {};
    if (!config.image) throw new Error('docker-run route requires an image');
    const inner = renderCommand(config.command || [], ctx.params);
    const flags = ['--rm'];
    if (config.mount) flags.push('-v', `${path.resolve(renderValue(String(config.mount), ctx.params))}:/work`, '-w', '/work');
    flags.push(...envFlags(config, ctx.params));
    const command = ['docker', 'run', ...flags, config.image, ...inner];
    if (!execute) return { simulated: true, type: 'docker', mode: 'run', image: config.image, command };
    const [cmd, ...rest] = command;
    return { type: 'docker', mode: 'run', image: config.image, command, ...runProcess(cmd, rest, config, policy, ctx.params) };
  },
  fetch: async (ctx, policy, execute) => {
    const config = { ...(ctx.routeEntry.config || {}) };
    config.url = renderValue(String(config.url || ''), ctx.params);
    const method = (config.method || 'POST').toUpperCase();
    if (!execute) return { simulated: true, type: 'http', method, url: config.url };
    if (!/^https?:\/\//i.test(config.url)) throw new Error(`refusing non-http url: ${config.url}`);
    const headers = { ...(config.headers || {}) };
    let body;
    if (ctx.payload != null) { body = JSON.stringify(ctx.payload); headers['Content-Type'] = headers['Content-Type'] || 'application/json'; }
    const response = await fetch(config.url, { method, headers, body });
    return { type: 'http', method, url: config.url, status: response.status, body: truncate(await response.text()) };
  },
};

export async function run(uri, registry, payload = null, { mode = 'dry-run', policy, confirm = false } = {}) {
  const merged = mergePolicy(policy);
  const descriptor = parseUri(uri);
  const translation = translate(descriptor);
  const tree = registryTree(registry);
  const routeEntry = tree?.[translation.package]?.[translation.resource]?.[translation.operation];
  if (!routeEntry) throw new Error(`Route not found: ${translation.route.join('.')}`);

  const envelope = { uri: descriptor.normalized, mode, kind: routeEntry.kind, adapter: routeEntry.adapter };

  let params;
  try {
    params = resolveParams(routeEntry, descriptor, translation, payload);
  } catch (err) {
    envelope.ok = false;
    envelope.error = { type: 'params', message: err.message };
    return envelope;
  }

  const ctx = { routeEntry, descriptor, translation, target: translation.target, args: translation.args, payload, params };
  const decision = evaluatePolicy(descriptor.normalized, routeEntry, ctx, merged);
  envelope.decision = decision;

  const executor = executors[routeEntry.adapter] || executors[routeEntry.kind];
  if (!executor) throw new Error(`Executor not found: ${routeEntry.adapter || routeEntry.kind}`);

  if (mode !== 'execute') {
    try {
      envelope.result = await executor(ctx, merged, false);
      envelope.ok = true;
    } catch (err) {
      envelope.ok = false;
      envelope.error = { type: err.paramsError ? 'params' : 'error', message: err.message };
    }
    return envelope;
  }
  if (!decision.allowed) {
    envelope.ok = false;
    envelope.error = { type: 'policy', message: decision.reason };
    return envelope;
  }
  if (decision.requireConfirm && !confirm) {
    envelope.ok = false;
    envelope.error = { type: 'confirm', message: 'route requires confirmation; pass confirm: true' };
    return envelope;
  }
  try {
    const result = await executor(ctx, merged, true);
    envelope.result = result;
    envelope.ok = (result.exitCode ?? 0) === 0;
  } catch (err) {
    envelope.ok = false;
    envelope.error = { type: err.paramsError ? 'params' : err.name || 'Error', message: err.message };
  }
  return envelope;
}

export function listRoutes(registry, policy) {
  return v6list(registry, policy);
}

export function expandBinding(uri, binding) {
  if (typeof binding === 'string') {
    return { uri, kind: 'cli', adapter: 'spawn', config: { command: tokenize(binding) } };
  }
  const expanded = { ...binding };
  if (uri && expanded.uri === undefined) expanded.uri = uri;
  const config = { ...(expanded.config || {}) };
  for (const key of [...COMMAND_KEYS, ...PROCESS_CONFIG_KEYS]) {
    if (expanded[key] !== undefined) { config[key] = expanded[key]; delete expanded[key]; }
  }
  expanded.config = config;
  expanded.kind = expanded.kind || inferKind({ ...expanded, ...config });
  expanded.adapter = expanded.adapter || defaultAdapter(expanded.kind);
  return expanded;
}

export function expandBindings(doc) {
  let pairs;
  if (Array.isArray(doc)) pairs = doc.map((item) => [item.uri, item]);
  else if (doc && doc.bindings) {
    pairs = Array.isArray(doc.bindings) ? doc.bindings.map((item) => [item.uri, item]) : Object.entries(doc.bindings);
  } else pairs = Object.entries(doc);
  return { version: 'urihandler.bindings.v5', bindings: pairs.map(([uri, binding]) => expandBinding(uri, binding)) };
}

export function compileRegistry(doc, options = {}) {
  return compileRegistryDocument(expandBindings(doc), options);
}
