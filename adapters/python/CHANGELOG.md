# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phone scanner: reject low-confidence single captures (below
  `URIRUN_PHONE_SCANNER_MIN_SCORE`, default 45, or not document-like) instead of
  archiving them; staged files are cleaned and no artifact is shown. `force=true`
  overrides.
- Phone scanner: audible + vibration feedback after each capture, with distinct
  cues for saved / duplicate / superseded / discarded.
- Document archive: robust deduplication via the `docid://` connector — a
  transaction fingerprint (receipt/invoice no., authorization code, time, card
  suffix) plus perceptual hashes (dHash + pHash), so the same receipt re-scanned
  with drifting OCR collapses onto one document.
- Document archive: a more complete re-scan **supersedes** a less-complete
  archived document and fuses missing fields from both scans; otherwise the
  re-scan is dropped and its staged scan + crop files are removed.

### Changed
- Smart crop now crops to the detected text boundary first (Tesseract), falling
  back to the geometric cascade; see `urirun-connector-smart-crop`.

## [0.3.14] - 2026-06-20

### Fixed
- Make MCP tool names and A2A skill ids unique when CQRS URI routes share the
  same resource/operation prefix and differ only by trailing path arguments.

## [0.3.13] - 2026-06-20

### Added
- Add `urirun.connector(...)`, a convention helper for connector packages. It
  builds full URI routes from short paths, fills `meta.connector`, and exports
  connector-scoped bindings through `.bindings()`.

## [0.3.12] - 2026-06-20

### Added
- Add the preferred top-level decorator API:
  `@urirun.command(...)`, `@urirun.shell(...)` and
  `urirun.connector_bindings(...)`.

## [0.3.11] - 2026-06-20

### Fixed
- Restore release-version consistency after the skipped v0.3.8-v0.3.10 tags
  still built `urirun` Python artifacts with version 0.3.5.

## [0.3.5] - 2026-06-20

### Added
- Add `urirun.v2.connector_bindings()` for connector packages that generate
  serializable v2 bindings from `@uri_command` decorated functions.

## [0.3.4] - 2026-06-19

### Changed
- Keep the Python distribution GitHub-installable as `urirun`.
- Remove public console entry points for versions below v1.
- Keep only `urirun`, `urirun-v1`, `urirun-v2`, `urirun-v1`, and
  `urirun-v2` as installed scripts.
- Move legacy registry/scanner/policy helpers behind private module names used
  internally by v1/v2.

## [0.3.3] - 2026-06-19

### Docs
- Update CHANGELOG.md
- Update README.md
- Update adapters/python/CHANGELOG.md
- Update adapters/python/README.md
- Update v2/README.md
- Update v2/examples/docker_uri_flow/README.md
- Update v2/spec/urirun-v2.md

### Other
- Update adapters/python/VERSION
- Update adapters/python/pyproject.toml
- Update adapters/python/urirun/v2.py
- Update adapters/python/urirun/v2_service.py
- Update adapters/python/uv.lock
- Update v2/examples/docker_uri_flow/shell-worker/bindings.json
- Update v2/examples/docker_uri_flow/test_service_adapter.py

## [0.3.1] - 2026-06-19

### Docs
- Update CHANGELOG.md
- Update README.md
- Update adapters/python/README.md
- Update v2/README.md
- Update v2/examples/docker_uri_flow/README.md
- Update v2/spec/urirun-v2.md

### Other
- Update Makefile
- Update adapters/python/.gitignore
- Update adapters/python/pyproject.toml
- Update adapters/python/uv.lock
- Update v2/examples/docker_uri_flow/Makefile
- Update v2/examples/docker_uri_flow/node-worker/package.json
- Update v2/examples/docker_uri_flow/node-worker/server.js
- Update v2/examples/docker_uri_flow/orchestrator/flow_runner.py
- Update v2/examples/docker_uri_flow/python-worker/server.py
- Update v2/examples/docker_uri_flow/shell-worker/server.py
- ... and 2 more files
