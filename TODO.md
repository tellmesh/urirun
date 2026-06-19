# TODO

Practical backlog for making `urirun` easier to use.

## Product

- [ ] Add `urirun init` to create a starter binding, policy file, generated
  directory, and example URI.
- [ ] Add `urirun doctor` to check Python, optional extras, Docker, Node, PHP,
  generated registry freshness, and duplicate routes.
- [ ] Add `urirun serve` for a local web console with routes, payload forms,
  browser logs, backend logs, dry-run preview, and policy-gated execution.
- [ ] Standardize `log://` routes across frontend, backend, shell, firmware, and
  Docker examples.
- [ ] Add `urirun diff` for comparing two registries before deployment.

## Developer Experience

- [ ] Keep all user-facing examples on `urirun`, `urirun-v7`, or `urirun-v8`.
- [ ] Keep `urihandler` only for the GitHub repository URL and historical notes.
- [ ] Add clearer scanner provenance for every generated binding.
- [ ] Add conflict reports that show duplicate URI, source file, and adapter.
- [ ] Add one-command GitHub install smoke tests in Docker.

## Documentation

- [ ] Keep `README.md`, `docs/`, and `www/` in sync before publishing.
- [ ] Add screenshots for `www/` and `v8/examples/html_uri_app`.
- [ ] Add a migration note for projects that previously used `urihandler`
  imports or commands directly.
- [ ] Add an examples index generated from `project/map.toon.yaml`.

## Cleanup

- [ ] Continue removing or archiving pre-v7 experiment folders from the public
  surface.
- [ ] Fix remaining lint findings in `project/planfile-tickets.yaml` when they
  affect runtime behavior or public APIs.
- [ ] Decide whether to publish a compatibility shim for older `urihandler`
  Python or JS imports.
