# urihandler

A small, language-agnostic URI-to-handler translator for integrating URI commands with existing code in any runtime.

## Goal

Normalize URIs like:

`device://device-01/led/set/on`

into a portable invocation descriptor:

```json
{
  "package": "device",
  "target": "device-01",
  "segments": ["led", "set", "on"]
}
```

Then adapt that descriptor to existing functions, methods, classes, MQTT topics, backend handlers, or firmware command tables.

## Core model

- `scheme` -> package / namespace / module
- `target` -> resource instance / receiver
- `path segments` -> operation chain
- `payload` -> optional data

## Repository layout

- `spec/urihandler-spec.md` - portable specification
- `adapters/js/` - JavaScript reference adapter
- `adapters/python/` - Python reference adapter
- `adapters/c/` - C firmware-style reference adapter
- `examples/` - end-to-end examples
- `github/` - GitHub integration notes

## Install from GitHub only

### JavaScript / Node

```bash
npm install github:tellmesh/urihandler
```

or vendor the adapter folder directly into your repo.

### Python

```bash
pip install "git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
```

### C / firmware

Copy `adapters/c/urihandler.c` and `adapters/c/urihandler.h` into your firmware project.

## Verify

```bash
make test
```

## License

MIT
