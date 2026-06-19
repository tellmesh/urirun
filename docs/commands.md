# Commands

## v8 CLI

`urirun` defaults to the v8 schema-first runtime.

```bash
urirun scan PATH --out generated/bindings.v8.json --registry-out generated/registry.json
urirun validate generated/bindings.v8.json
urirun compile generated/bindings.v8.json --out generated/registry.json
urirun list generated/registry.json
urirun run URI --registry generated/registry.json --payload '{"name":"Ada"}'
```

## Generate bindings in one line

Expose a package command:

```bash
urirun add-pypi sampleproject --out urirun.bindings.v8.json
```

Expose a command template:

```bash
urirun add-command 'util://local/echo/message' \
  --argv 'python3 -c "import sys; print(sys.argv[1])" {text}' \
  --param text:string:required \
  --out urirun.bindings.v8.json
```

## Versioned commands

```bash
urirun-v7 compile v7/examples/json/bindings.v7.example.json --out /tmp/registry.json
urirun-v7 run 'media://local/video/transcode' /tmp/registry.json --payload '{"input":"a.mp4","output":"b.mp4"}'
urirun-v8 --help
```

Use these versioned commands when a script must stay pinned to a major registry
contract.

## Module commands

The module namespace is `urirun`, so these are also valid:

```bash
python -m urirun.v8 --help
python -m urirun.v8_mcp tools generated/registry.json
python -m urirun.v8_mcp card generated/registry.json
```
