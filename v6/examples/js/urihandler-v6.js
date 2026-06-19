import { spawnSync } from 'node:child_process';
import {
  dispatchGenerated,
  flattenRegistryDocument,
  registryTree,
} from '../../../v4/examples/js/urihandler-v4.js';
import { parseUri, translate } from '../../../v3/examples/js/urihandler-v3.js';

export const POLICY_VERSION = 'urihandler.policy.v6';
const OUTPUT_LIMIT = 4000;
const DEFAULT_TIMEOUT = 30000;
const DESTRUCTIVE_HINTS = ['rm', 'delete', 'destroy', 'drop', 'shutdown', 'reboot', 'format', 'wipe'];

export function defaultPolicy() {
  return {
    version: POLICY_VERSION,
    defaultMode: 'dry-run',
    execute: { allow: [], deny: [] },
    allowShellTemplates: false,
    maxArgs: 16,
    timeout: DEFAULT_TIMEOUT,
  };
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
  // Mirror Python fnmatch: '*' matches across path separators too.
  const escaped = pattern.replace(/[.+^${}()|[\]\\?]/g, '\\$&').replace(/\*/g, '.*');
  return new RegExp('^' + escaped + '$');
}

function matchesAny(uri, patterns) {
  return patterns.find((pattern) => globToRegExp(pattern).test(uri)) || null;
}

function looksDestructive(routeEntry, ctx) {
  const config = routeEntry.config || {};
  const words = [...(config.command || []).map(String), String(config.template || ''), ...ctx.args]
    .join(' ').toLowerCase().split(/\s+/);
  return DESTRUCTIVE_HINTS.some((hint) => words.includes(hint));
}

export function evaluatePolicy(uri, routeEntry, ctx, policy) {
  const routePolicy = routeEntry.policy || {};
  const execute = policy.execute || {};

  if (routePolicy.deny === true) return { allowed: false, reason: 'route policy denies execution' };

  const denyMatch = matchesAny(uri, execute.deny || []);
  if (denyMatch) return { allowed: false, reason: `matched deny pattern '${denyMatch}'` };

  const maxArgs = routePolicy.maxArgs ?? policy.maxArgs ?? 16;
  if (maxArgs != null && ctx.args.length > maxArgs) {
    return { allowed: false, reason: `too many arguments (${ctx.args.length} > ${maxArgs})` };
  }

  if (routeEntry.kind === 'shell' || routeEntry.adapter === 'shell-template') {
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
  if (routePolicy.requireConfirm || looksDestructive(routeEntry, ctx)) decision.requireConfirm = true;
  return decision;
}

function truncate(text) {
  if (text == null) return '';
  return text.length > OUTPUT_LIMIT
    ? `${text.slice(0, OUTPUT_LIMIT)}\n...[truncated ${text.length - OUTPUT_LIMIT} chars]`
    : text;
}

function runSpawn(ctx, policy) {
  const config = ctx.routeEntry.config || {};
  const command = [...(config.command || []).map(String), ...ctx.args.map(String)];
  if (command.length === 0) throw new Error('spawn route has no command');
  const [cmd, ...rest] = command;
  const result = spawnSync(cmd, rest, { encoding: 'utf-8', timeout: policy.timeout, cwd: config.cwd });
  return {
    type: 'cli',
    command,
    exitCode: result.status ?? -1,
    stdout: truncate(result.stdout || ''),
    stderr: truncate(result.stderr || ''),
  };
}

async function runFetch(ctx, policy) {
  const config = ctx.routeEntry.config || {};
  const url = config.url;
  const method = (config.method || 'POST').toUpperCase();
  if (!url) throw new Error('http route has no url');
  if (!/^https?:\/\//i.test(url)) throw new Error(`refusing non-http url: ${url}`);
  const headers = { ...(config.headers || {}) };
  let body;
  if (ctx.payload != null) {
    body = JSON.stringify(ctx.payload);
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }
  const response = await fetch(url, { method, headers, body, signal: AbortSignal.timeout(policy.timeout) });
  return { type: 'http', method, url, status: response.status, body: truncate(await response.text()) };
}

async function runLocalFunction(ctx) {
  const fn = ctx.routeEntry.ref;
  if (typeof fn !== 'function') {
    throw new Error(`local function ref is not callable (hydrate the registry first): ${fn}`);
  }
  return { type: 'function', ref: fn.name || String(fn), value: await fn(ctx.target, ctx.args, ctx.payload, ctx.descriptor) };
}

export const executors = {
  spawn: runSpawn,
  'shell-template': runSpawn,
  fetch: runFetch,
  'local-function': runLocalFunction,
};

export async function run(uri, registry, payload = null, { mode = 'dry-run', policy, confirm = false } = {}) {
  const merged = mergePolicy(policy);
  const descriptor = parseUri(uri);
  const translation = translate(descriptor);
  const tree = registryTree(registry);
  const routeEntry = tree?.[translation.package]?.[translation.resource]?.[translation.operation];
  if (!routeEntry) throw new Error(`Route not found: ${translation.route.join('.')}`);

  const ctx = {
    routeEntry,
    descriptor,
    translation,
    target: translation.target,
    args: translation.args,
    payload,
  };
  const decision = evaluatePolicy(descriptor.normalized, routeEntry, ctx, merged);
  const envelope = {
    uri: descriptor.normalized,
    mode,
    kind: routeEntry.kind,
    adapter: routeEntry.adapter,
    decision,
  };

  if (mode !== 'execute') {
    envelope.ok = true;
    envelope.result = await dispatchGenerated(uri, registry, payload);
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

  const executor = executors[routeEntry.adapter] || executors[routeEntry.kind];
  if (!executor) throw new Error(`Executor not found: ${routeEntry.adapter || routeEntry.kind}`);
  try {
    envelope.result = await executor(ctx, merged);
    envelope.ok = (envelope.result.exitCode ?? 0) === 0;
  } catch (err) {
    envelope.ok = false;
    envelope.error = { type: err.name || 'Error', message: err.message };
  }
  return envelope;
}

export function listRoutes(registry, policy) {
  const merged = policy === undefined ? undefined : mergePolicy(policy);
  return flattenRegistryDocument(registry)
    .map((route) => {
      const item = {
        uri: route.uri,
        kind: route.routeEntry.kind,
        adapter: route.routeEntry.adapter,
        source: route.source || {},
      };
      if (merged) {
        const descriptor = parseUri(route.uri);
        const translation = translate(descriptor);
        item.decision = evaluatePolicy(descriptor.normalized, route.routeEntry, { args: translation.args }, merged);
      }
      return item;
    })
    .sort((a, b) => a.uri.localeCompare(b.uri));
}

export function check(uri, registry, policy) {
  const merged = mergePolicy(policy);
  const descriptor = parseUri(uri);
  const translation = translate(descriptor);
  const tree = registryTree(registry);
  const routeEntry = tree?.[translation.package]?.[translation.resource]?.[translation.operation];
  if (!routeEntry) throw new Error(`Route not found: ${translation.route.join('.')}`);
  return {
    uri: descriptor.normalized,
    kind: routeEntry.kind,
    adapter: routeEntry.adapter,
    decision: evaluatePolicy(descriptor.normalized, routeEntry, { args: translation.args }, merged),
  };
}
