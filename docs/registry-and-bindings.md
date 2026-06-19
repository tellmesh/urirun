# Registry and bindings

`urirun` separates the package contract from the runtime lookup tree.

## Binding document

A binding document is portable JSON. It describes URI routes, input schemas, and
adapter configuration.

```json
{
  "version": "urirun.bindings.v8",
  "bindings": {
    "report://local/render/pdf": {
      "kind": "command",
      "adapter": "argv-template",
      "inputSchema": {
        "type": "object",
        "required": ["input", "output"],
        "properties": {
          "input": { "type": "string" },
          "output": { "type": "string" }
        },
        "additionalProperties": false
      },
      "argv": ["python3", "render.py", "{input}", "{output}"]
    }
  }
}
```

## Registry

The registry is compiled from one or more binding documents:

```bash
urirun compile bindings.v8.json --out registry.json
```

The runtime dispatches from the registry only. This makes a generated registry
reviewable, reproducible, and safe to pass between shell clients, HTTP services,
browser consoles, Docker orchestrators, and agent projections.

## Route identity

The full URI matters. A route such as:

```text
device://device-01/led/command/set
```

can coexist with:

```text
device://device-02/led/command/set
```

because the target is part of the route identity. This avoids conflicts when
multiple services expose the same operation shape for different targets.

## Conflict policy

Generated bindings should be deterministic:

- explicit binding files win over inferred script/package routes
- duplicate full URIs should fail validation unless the scanner marks them as
  the same source
- generated files should be written to `generated/` or `.urirun/`, not edited
  as primary source
- source artifacts remain the source of truth when using scanner adoption
