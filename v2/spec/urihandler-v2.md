# urihandler v2

`urihandler v2` defines a language-agnostic addressing and translation layer for turning URI commands into validated route descriptors and runtime callables.

## Goal

Separate four concerns:

1. URI as a logical address
2. Translation from URI to route descriptor
3. Validation against an available registry tree
4. Runtime resolution to a callable with cache support

## Canonical URI form

```txt
[package]://[target]/[resource]/[operation]/[arg1]/[arg2]/...
```

Examples:

- `device://device-01/led/set/on`
- `log://app/info/user-created`
- `process://bridge/run/smoke`
- `mqtt://broker/publish/home/kitchen/light/on`

## Normalized descriptor

```json
{
  "package": "device",
  "target": "device-01",
  "segments": ["led", "set", "on"],
  "query": {},
  "fragment": null,
  "raw": "device://device-01/led/set/on",
  "normalized": "device://device-01/led/set/on"
}
```

## Translation descriptor

```json
{
  "route": ["device", "led", "set"],
  "args": ["device-01", "on"],
  "package": "device",
  "target": "device-01",
  "resource": "led",
  "operation": "set"
}
```

## Default translation rules

For:

```txt
device://device-01/led/set/on
```

translate to:

- `package = device`
- `target = device-01`
- `resource = led`
- `operation = set`
- `args = [target, ...remainingSegments]`
- `route = [package, resource, operation]`

## Registry tree

Runtime resolution should use a tree, not generated function names.

Example conceptual registry:

```json
{
  "device": {
    "led": {
      "set": "callable"
    }
  },
  "log": {
    "app": {
      "info": "callable"
    }
  }
}
```

## `.urihandler` cache

Use a project-local folder:

```txt
.urihandler/
```

Each entry is keyed by a stable hash of the normalized URI.

Recommended key:

```txt
sha256(normalized_uri)
```

Recommended file name:

```txt
.urihandler/<sha256>.json
```

Example cache entry:

```json
{
  "uri": "log://app/info/user-created",
  "normalized": "log://app/info/user-created",
  "hash": "...",
  "translation": {
    "route": ["log", "info", "user-created"],
    "args": ["app"],
    "package": "log",
    "target": "app",
    "resource": "info",
    "operation": "user-created"
  },
  "validated": true,
  "strategy": "tree-registry-v2"
}
```

## Two-level cache model

### Persistent cache

Stores translation output and validation metadata.

### Runtime cache

Stores in-memory callable references:

```txt
hash -> callable
```

Do not attempt to serialize language-specific callable references into persistent cache.

## Validation rules

Before execution:

1. Parse URI
2. Normalize URI
3. Translate to route descriptor
4. Verify `package`, `resource`, `operation` exist in registry tree
5. Resolve callable
6. Execute with `args` and optional `payload`

## `log://` support

`log://` is a first-class package.

Examples:

- `log://app/info/user-created`
- `log://audit/write/order/123`
- `log://device-01/debug/temp/42`

Suggested interpretation:

- `package = log`
- `target = logging channel, sink, or source`
- `resource = log level or category`
- `operation = event name or action`
- remaining segments = log args

## Adapter contract

Each adapter should expose:

- `parseUri(uri)`
- `normalizeUri(descriptor)`
- `translate(descriptor)`
- `validate(translation, registry)`
- `resolve(translation, registry, runtimeCache)`
- `dispatch(uri, registry, payload?)`

## Recommended dispatch contract

```txt
registry[package][resource][operation](target, args, payload, descriptor)
```

Example:

```txt
device://device-01/led/set/on
-> registry.device.led.set("device-01", ["on"], payload, descriptor)
```
