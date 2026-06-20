# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.10] - 2026-06-19

### Fixed
- Fix duplicate-imports issues (ticket-1665d840)
- Fix string-concat issues (ticket-b8e19801)
- Fix unused-imports issues (ticket-70da4470)
- Fix magic-numbers issues (ticket-04441770)
- Fix smart-return-type issues (ticket-049184c6)
- Fix string-concat issues (ticket-ae623e62)
- Fix unused-imports issues (ticket-1d79c661)
- Fix magic-numbers issues (ticket-9dfc6c44)
- Fix smart-return-type issues (ticket-4df269e8)
- Fix string-concat issues (ticket-8e187d8c)
- Fix unused-imports issues (ticket-b28370b0)
- Fix magic-numbers issues (ticket-39f6c4f8)
- Fix duplicate-imports issues (ticket-28c5084d)
- Fix smart-return-type issues (ticket-6181097b)
- Fix string-concat issues (ticket-9cd0b999)
- Fix unused-imports issues (ticket-190dff5c)
- Fix magic-numbers issues (ticket-f1115b33)
- Fix duplicate-imports issues (ticket-643daa64)
- Fix string-concat issues (ticket-351dac12)
- Fix unused-imports issues (ticket-4c9cff33)
- Fix magic-numbers issues (ticket-aec33ab4)
- Fix unused-imports issues (ticket-00a4088f)
- Fix magic-numbers issues (ticket-9d63e233)
- Fix smart-return-type issues (ticket-f800d394)
- Fix unused-imports issues (ticket-4e563569)
- Fix string-concat issues (ticket-e452c4be)
- Fix unused-imports issues (ticket-14b02b68)
- Fix magic-numbers issues (ticket-ca0604aa)

## [0.1.10] - 2026-06-19

### Fixed
- Fix smart-return-type issues (ticket-eb869bc1)
- Fix duplicate-imports issues (ticket-99718c09)
- Fix smart-return-type issues (ticket-eaa1a1f7)
- Fix string-concat issues (ticket-189972f1)
- Fix unused-imports issues (ticket-2ae216f5)
- Fix magic-numbers issues (ticket-501340be)
- Fix ai-boilerplate issues (ticket-0d4413a6)
- Fix smart-return-type issues (ticket-8a46e336)
- Fix unused-imports issues (ticket-ce8677da)
- Fix ai-boilerplate issues (ticket-2d28df98)
- Fix smart-return-type issues (ticket-201b30dc)
- Fix unused-imports issues (ticket-b5459d71)
- Fix ai-boilerplate issues (ticket-716210d9)
- Fix smart-return-type issues (ticket-458d3024)
- Fix string-concat issues (ticket-c668e6f1)
- Fix unused-imports issues (ticket-6768fa98)
- Fix ai-boilerplate issues (ticket-b616f41a)
- Fix unused-imports issues (ticket-0937ba6b)
- Fix ai-boilerplate issues (ticket-aead3121)
- Fix smart-return-type issues (ticket-2dc4a55e)
- Fix unused-imports issues (ticket-13dfd8b6)
- Fix magic-numbers issues (ticket-9f2b85cc)
- Fix ai-boilerplate issues (ticket-c05d5ebc)
- Fix duplicate-imports issues (ticket-7ed2df3e)
- Fix unused-imports issues (ticket-e18f1230)
- Fix magic-numbers issues (ticket-f686b7a3)
- Fix smart-return-type issues (ticket-94ce9e76)
- Fix string-concat issues (ticket-095f3619)
- Fix unused-imports issues (ticket-a1bddd24)
- Fix magic-numbers issues (ticket-b2d2ca2f)
- Fix ai-boilerplate issues (ticket-3d6a7d0c)
- Fix smart-return-type issues (ticket-0b9880f6)
- Fix string-concat issues (ticket-ee11fc23)
- Fix unused-imports issues (ticket-ea06d378)
- Fix magic-numbers issues (ticket-04013af9)
- Fix ai-boilerplate issues (ticket-d46eec47)

## [0.3.13] - 2026-06-20

### Changed
- Align root, Python and JavaScript package metadata to the same runtime
  version and add a CI version check.
- Expose `compile_registry`, `list_routes`, `validate_binding_document` and
  `run` from the top-level Python API so connector packages can avoid versioned
  imports in normal smoke tests.

### Added
- Add `urirun.connector(...)`, a convention helper for connector packages. It
  builds full URI routes from short paths, fills `meta.connector`, and exports
  connector-scoped bindings through `.bindings()`.

## [0.3.12] - 2026-06-20

### Added
- Add the preferred top-level decorator API: `@urirun.command(...)`,
  `@urirun.shell(...)` and `urirun.connector_bindings(...)` in
  `adapters/python/urirun/__init__.py`. `urirun.v2.uri_command` /
  `urirun.v2.uri_shell` remain supported.

## [0.3.11] - 2026-06-20

### Added
- Add the release workflow (`.github/workflows/release.yml`): a `v*` tag builds
  the `urirun` wheel + sdist, smoke-tests the wheel, writes `sha256sums.txt`,
  and publishes a GitHub Release with the artifacts attached.
- Add the CI workflow (`.github/workflows/ci.yml`) running `make test` on push
  and pull request.

### Fixed
- Restore release-version consistency after the skipped v0.3.8-v0.3.10 tags
  still built `urirun` Python artifacts with version 0.3.5.

## [Unreleased]

### Added
- Add `docs/` with current urirun quick start, naming, commands, registry,
  transports, logo notes, and roadmap.
- Add `www/` PHP documentation site wired to the generated SVG logo assets.
- Add a minimal-import regression test so core imports stay independent from
  host, dashboard, domain-monitor, planfile and optional transport modules.
- Add `urirun.host_integrations` as the compatibility home for host, planfile
  and domain-monitor v2 bindings while those integrations move out of core.
- Document the external `urirun-connector-planfile` and
  `urirun-connector-domain-monitor` packages as the preferred task/domain
  workflow path.
- Document `urirun-connector-sqlite-context` as the preferred host context data
  connector package.

### Changed
- Load host dashboard and Namecheap/domain-monitor dependencies lazily at call
  time, keeping the minimal `urirun` runtime boundary smaller.
- Keep `urirun.v2` host/domain public functions as thin lazy wrappers instead
  of storing the integration implementations directly in the core module.
- Point active README install examples at the `if-uri/urirun` repository.
- Add generated `logo/` SVG assets for icon, wordmark, favicon, horizontal,
  stacked, and logo sheet variants.
- Add a curated `TODO.md` focused on urirun usability work.
- Add links to the current ifURI cross-repository work summary, connector hub,
  examples, installer and app/host integration repositories.

### Changed
- Update README for the current `urirun` runtime name; the GitHub repository is
  `tellmesh/urirun` (renamed from `tellmesh/urihandler`).
- Refresh the PHP project site with current positioning, workflow, transport,
  examples, docs, and roadmap content.
- Rename the portable spec path to `spec/urirun-spec.md`.
- Align examples and docs on `urirun` imports, schema versions, Docker labels,
  C adapter files, and CLI commands.
- Keep `tellmesh/urihandler` only in historical changelog entries that refer to
  the pre-rename repository.
- Clarify the manual runtime TODO around core/runtime boundaries, connector
  discovery and downstream E2E coverage.
- Align README install examples with the current Python package version
  `v0.3.14`.

### Fixed
- Point all repository references at the renamed `tellmesh/urirun` URL.

## [0.3.10] - 2026-06-20

### Docs
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update project/README.md
- Update project/context.md

### Other
- Update app.doql.less
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- Update project/calls.yaml
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- Update project/evolution.toon.yaml
- ... and 9 more files

## [0.3.9] - 2026-06-20

### Docs
- Update README.md

## [0.3.8] - 2026-06-20

### Test
- Update test/urirun.test.js
- Update testql-scenarios/generated-from-pytests.testql.toon.yaml

## [0.3.7] - 2026-06-19

### Docs
- Update README.md

### Other
- Update v1/examples/html_uri_app/app.js
- Update v1/examples/html_uri_app/test.mjs
- Update v1/examples/html_uri_app/uri-runtime-v1.js
- Update v2/examples/device_mesh_lab/.run/logs/desktop.jsonl
- Update v2/examples/device_mesh_lab/.run/logs/laptop.jsonl
- Update v2/examples/device_mesh_lab/controller.py
- Update v2/examples/device_mesh_lab/device_agent.py
- Update v2/examples/device_mesh_lab/mesh_env.py
- Update v2/examples/device_mesh_lab/tests/gui_smoke.py
- Update v2/examples/device_mesh_lab/www/app.js
- ... and 4 more files

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
- Rename the Python distribution from `urirun` to `urirun`.
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
