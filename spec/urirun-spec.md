# urirun spec v0.1

## URI form

```txt
[package]://[target]/[segment1]/[segment2]/.../[segmentN]
```

## Normalized descriptor

```json
{
  "package": "string",
  "target": "string",
  "segments": ["string"],
  "query": {},
  "fragment": null,
  "raw": "string"
}
```

## Default translation strategy

- package/module = `scheme`
- function name = first two segments joined with `_`
- args = `target` + remaining segments

## Safety rules

- Never dispatch to arbitrary modules outside an explicit registry.
- Never execute names built from URI without validation.
- Allow package lookup only from a known adapter map.
- Allow function lookup only if callable and public by adapter policy.
