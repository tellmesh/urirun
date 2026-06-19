# urirun docs

`urirun` is the user-facing CLI for URI-addressed command packages. A project can
declare a URI once and call it from a shell, backend, frontend, service flow, or
agent tool projection.

## Start here

- [Getting started](getting-started.md) - install from GitHub, scan artifacts,
  compile a registry, and run a URI.
- [Naming](naming.md) - what uses `urirun` and why the GitHub repo URL still
  contains `urihandler`.
- [Commands](commands.md) - CLI commands and versioned entry points.
- [Registry and bindings](registry-and-bindings.md) - how bindings become a
  dispatchable registry.
- [Transports](transports.md) - local functions, shell, Docker, HTTP, gRPC,
  browser, MCP, and A2A.
- [Logo](logo.md) - generated SVG logo assets and usage notes.
- [Roadmap](roadmap.md) - practical TODO list for making the tool easier.

## Current recommendation

Use v8 for new projects:

```bash
pip install "git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
urirun scan ./project --out generated/bindings.v8.json --registry-out generated/registry.json
urirun list generated/registry.json
```

Keep v7 only for older examples that depend on the first parameter-binding
contract.
