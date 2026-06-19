# Getting started

Install directly from GitHub:

```bash
pip install "git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
```

The installed CLI and Python import namespace are both `urirun`.

## Generate a registry

Scan a project and compile a runtime registry in one command:

```bash
urirun scan ./project \
  --out generated/bindings.v8.json \
  --registry-out generated/registry.json
```

The scanner can read explicit binding files, Dockerfile labels, package scripts,
Python entry points, Makefile targets, and shell scripts.

## Inspect routes

```bash
urirun validate generated/bindings.v8.json
urirun list generated/registry.json
```

## Run a URI

Dry-run is the default for command-like routes:

```bash
urirun run 'cli://local/git/status' --registry generated/registry.json
```

For real execution, use a policy file and the `--execute` flag:

```bash
urirun run 'cli://local/git/status' \
  --registry generated/registry.json \
  --policy policy.json \
  --allow 'cli://local/**' \
  --execute
```

Keep shell templates behind an explicit policy with `allowShellTemplates: true`.
