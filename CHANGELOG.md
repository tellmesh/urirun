# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Add a gRPC transport (`urirun.v8_grpc`): a generic `Run` / `RunStream` /
  `ListRoutes` service over JSON-over-gRPC, with a client `call()` that mirrors
  the HTTP service path (schema-validated, target via `URI_GRPC_MAP`).
- Add `urirun.v8_service` for library-native, adapter-agnostic HTTP dispatch
  (validate against the registry schema, then `POST /run`).
- Add `urirun.v8_mcp` (MCP tools manifest, A2A agent card, stdio MCP server) and
  `urirun.v8_adopt` (adopt PyPI `console_scripts` and npm `bin` as URI commands).
- Add `v8/examples/transports` (one registry over in-process, queue, serverless,
  HTTP and gRPC, plus a one-command `scan_and_run.py`).
- Add `v8/examples/multi_transport` (Docker stack mixing HTTP and gRPC workers,
  auto-generated registry, route-conflict detection, cross-environment flow).
- Add docker-free and Docker integration tests for the example flows.
- Add `docs/` with current urirun quick start, naming, commands, registry,
  transports, logo notes, and roadmap.
- Add `www/` PHP documentation site wired to the generated SVG logo assets.
- Add static `www/index.html` and `www/index.en.html` pages with SEO
  `hreflang`, language memory, and a GitHub Pages deployment workflow.
- Add technology tabs to the static `www` landing page showing how Python,
  JavaScript, C, Shell, Docker, TypeScript, and PHP generate bindings and
  compile registries.
- Add generated `logo/` SVG assets for icon, wordmark, favicon, horizontal,
  stacked, and logo sheet variants.
- Add a curated `TODO.md` focused on urirun usability work.
- Add a noVNC LAN flow example with four Docker "computers", a four-iframe
  dashboard, URI agents, and a cross-computer flow.

### Changed
- Disable `[tool.pfix] auto_apply` so configuration and documentation changes
  are explicit rather than auto-applied.
- Standardize the website and docs on the full transport set (in-process, CLI/
  shell, HTTP, gRPC, queue, serverless, Docker, MCP/A2A) and the current example
  list; make `www/index.html` consistent with the canonical site.
- Update README for the current `urirun` runtime name while keeping the GitHub
  repository URL as `tellmesh/urihandler`.
- Refresh the PHP project site with current positioning, workflow, transport,
  examples, docs, and roadmap content.
- Rename the portable spec path to `spec/urirun-spec.md`.
- Align examples and docs on `urirun` imports, schema versions, Docker labels,
  C adapter files, and CLI commands.
- Keep `tellmesh/urihandler` only where it refers to the actual GitHub
  repository URL or historical changelog entries.

### Fixed
- Fix stale references to a non-existing `tellmesh/urirun` GitHub repository in
  examples.

## [0.3.6] - 2026-06-19

### Docs
- Update CHANGELOG.md
- Update README.md
- Update TODO.md
- Update adapters/python/README.md
- Update docs/commands.md
- Update docs/getting-started.md
- Update docs/index.md
- Update docs/logo.md
- Update docs/naming.md
- Update docs/registry-and-bindings.md
- ... and 7 more files

### Other
- Update adapters/c/urirun.c
- Update adapters/c/urirun.h
- Update adapters/c/urirun_test.c
- Update adapters/python/pyproject.toml
- Update examples/reference_adapters/firmware-pseudo.c
- Update v7/examples/html_uri_app/bindings.json
- Update v7/examples/html_uri_app/test.mjs
- Update v7/examples/js/urirun-v7.js
- Update v7/examples/js/urirun-v7.test.js
- Update v7/examples/python/test_extend.py
- ... and 7 more files

## [0.1.10] - 2026-06-19

### Fixed
- Fix smart-return-type issues (ticket-1e8a22f9)
- Fix duplicate-imports issues (ticket-bfb80289)
- Fix smart-return-type issues (ticket-3a5f272d)
- Fix string-concat issues (ticket-e30f4b7a)
- Fix unused-imports issues (ticket-5639451d)
- Fix magic-numbers issues (ticket-f6f58801)
- Fix ai-boilerplate issues (ticket-ee8097b5)
- Fix smart-return-type issues (ticket-e7a43d6d)
- Fix unused-imports issues (ticket-5590d278)
- Fix ai-boilerplate issues (ticket-aa4ca803)
- Fix smart-return-type issues (ticket-024ce67c)
- Fix unused-imports issues (ticket-e1d19c39)
- Fix ai-boilerplate issues (ticket-a756a06e)
- Fix smart-return-type issues (ticket-0ef971cd)
- Fix string-concat issues (ticket-fd4dbb13)
- Fix unused-imports issues (ticket-784e6941)
- Fix ai-boilerplate issues (ticket-f87226bf)
- Fix unused-imports issues (ticket-d098a065)
- Fix ai-boilerplate issues (ticket-a5490199)
- Fix smart-return-type issues (ticket-38990151)
- Fix unused-imports issues (ticket-4a411d34)
- Fix magic-numbers issues (ticket-72b975f4)
- Fix ai-boilerplate issues (ticket-97895aee)
- Fix smart-return-type issues (ticket-1a33a69c)
- Fix string-concat issues (ticket-ec63e6d2)
- Fix unused-imports issues (ticket-c19aa3e9)
- Fix magic-numbers issues (ticket-e1d61dd4)
- Fix ai-boilerplate issues (ticket-497d146c)
- Fix duplicate-imports issues (ticket-348117a4)
- Fix unused-imports issues (ticket-48784ac1)
- Fix magic-numbers issues (ticket-7dc493f5)
- Fix smart-return-type issues (ticket-b12f017e)
- Fix string-concat issues (ticket-00e03318)
- Fix unused-imports issues (ticket-a247e157)
- Fix magic-numbers issues (ticket-4d1e8444)
- Fix ai-boilerplate issues (ticket-3d1e91c1)

## [Pre-0.3.5 Notes]

### Docs
- Document v8 generated registry workflow for Docker URI flows.
- Document Python package installation as `urirun`.
- Document GitHub-only Python installation.

### Changed
- Rename the Python distribution from `urihandler` to `urirun`.
- Remove public project versions below v7.
- Keep GitHub Release / Git install as the supported Python package channel.

## [0.3.5] - 2026-06-19

### Docs
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update adapters/python/CHANGELOG.md
- Update adapters/python/README.md
- Update v7/examples/extend/README.md
- Update v7/examples/html_uri_app/README.md
- Update v7/spec/urihandler-v7.md

### Test
- Update test/urirun.test.js

### Other
- Update Makefile
- Update adapters/js/package.json
- Update adapters/python/pyproject.toml
- Update adapters/python/tests/test_urihandler.py
- Update adapters/python/urirun/__init__.py
- Update adapters/python/urirun/_registry.py
- Update adapters/python/urirun/_runtime.py
- Update adapters/python/urirun/_scan.py
- Update adapters/python/urirun/v7.py
- Update adapters/python/urirun/v8.py
- ... and 24 more files

## [0.3.2] - 2026-06-19

### Docs
- Update README.md

### Other
- Update .gitignore
- Update Makefile
- Update v5/examples/html_uri_app/app.js
- Update v5/examples/html_uri_app/bindings.json
- Update v5/examples/html_uri_app/index.html
- Update v5/examples/html_uri_app/uri-runtime.js
- Update v6/examples/js/example.js
- Update v6/examples/js/urihandler-v6.js
- Update v6/examples/js/urihandler-v6.test.js
- Update v6/examples/python/test_urihandler_v6.py

## [0.3.1] - 2026-06-19

### Docs
- Update v6/spec/urihandler-v6.md

### Test
- Update test/urihandler.test.js

### Other
- Update .env.example
- Update .gitignore
- Update adapters/python/urihandler/v6.py
- Update package-lock.json
- Update v6/examples/json/policy.example.json
- Update v6/examples/python/example.py
