# Releasing urirun 0.4.4 — the keystone, then repinning the fleet

Why this is the unblocker: the v2 **authoring layer** (`Connector.handler` / `.cli`
/ `.manifest`, top-level `ok` / `fail` / `plan`) exists only on git HEAD. PyPI 0.4.3
has the `runtime/` split but **not** that layer, so every migrated connector is
forced to track git HEAD and `urirun>=0.4.3` from PyPI would break them. Cutting
0.4.4 to PyPI is what lets connectors pin a *version* and lets the installers prefer
PyPI. Do this first; everything below depends on it.

## 0. Pre-flight (must be green before tagging)

```bash
cd adapters/python
python -m pytest -q                      # codegen + lint suites green (test_compat may be
                                         # pre-existing-red until namecheap_dns extraction lands)
python -m ruff check urirun
cd ../.. && make lint-connectors         # fleet gate: no code<->manifest drift
```

Confirm the layer that's actually being released is present:

```bash
python -c "import urirun; assert all(hasattr(urirun, n) for n in ('ok','fail','plan','handler')); \
from urirun import Connector; assert all(hasattr(Connector, m) for m in ('handler','cli','manifest')); \
print('v2 authoring layer present')"
```

## 1. Version + changelog

```bash
# version lives in adapters/python/pyproject.toml ([project] version = "0.4.4")
grep -n '^version' adapters/python/pyproject.toml          # expect 0.4.4
# bump helper if needed:
bash scripts/release-bump.sh 0.4.4                         # if it isn't already 0.4.4
```

In `CHANGELOG.md`, rename the `## [Unreleased]` heading to `## [0.4.4] - <today>`
(the codegen / adapter-drift / fleet-gate entries from this work are already there)
and open a fresh empty `## [Unreleased]` above it.

## 2. Build + verify the artifact

```bash
cd adapters/python
python -m build                          # -> dist/urirun-0.4.4-*.whl + .tar.gz
python -m twine check dist/urirun-0.4.4*
# smoke the wheel in a clean venv BEFORE uploading
python -m venv /tmp/relcheck && /tmp/relcheck/bin/pip install -q dist/urirun-0.4.4-*.whl
/tmp/relcheck/bin/python -c "import urirun; from urirun import Connector; \
assert hasattr(urirun,'handler') and hasattr(Connector,'manifest'); print('wheel ok')"
```

## 3. Tag + publish

```bash
git tag v0.4.4 && git push origin v0.4.4
make publish                             # or: twine upload adapters/python/dist/urirun-0.4.4*
```

## 4. Confirm it's live on PyPI

```bash
python -m venv /tmp/pypicheck
/tmp/pypicheck/bin/pip install "urirun==0.4.4"
/tmp/pypicheck/bin/python -c "import urirun; from urirun import Connector; \
assert hasattr(urirun,'ok') and hasattr(Connector,'handler'); print('PyPI 0.4.4 has the authoring layer')"
```

## 5. Repin the connector fleet (git HEAD -> version)

`scripts/repin_connectors.py` rewrites each `urirun-connector-*`'s
`urirun @ git+…urirun.git…` dep to `urirun>=0.4.4`, preserving `[extras]`, never
touching `urirun-connector-*` / `urirun-flow` deps or existing version pins, and
**refusing to write unless 0.4.4 is actually on PyPI** (so it can't run before step 4).

```bash
python scripts/repin_connectors.py                       # dry-run report across the fleet
python scripts/repin_connectors.py --write               # apply (guard confirms PyPI has 0.4.4)
make lint-connectors                                     # still green after the repin
```

Then commit each connector repo (they're separate repos):

```bash
for d in ../urirun-connector-*; do
  git -C "$d" diff --quiet pyproject.toml || \
    git -C "$d" commit -am "deps: pin urirun>=0.4.4 (v2 authoring layer released)"
done
```

## 6. Installers self-correct

`get-urirun-com/{node,host}.sh` and `node.ps1` already default to
`URIRUN_CHANNEL=auto` with `URIRUN_MIN_VERSION=0.4.4`: before this release they fell
back to git `main`; after it they install `urirun>=0.4.4` from PyPI. No installer
edit is needed — but re-run one smoke install to confirm:

```bash
URIRUN_CHANNEL=auto bash get-urirun-com/node.sh --name ci-smoke --dry-run --no-start
```

---

## Appendix — per-connector CI lint (drop into each `urirun-connector-*/.github/workflows/ci.yml`)

The fleet gate (`connectors.yml` in the urirun repo) is the org-wide net; this is the
per-repo gate that fails a single connector's own PR on drift:

```yaml
  - name: Lint URI contract (no code<->manifest drift)
    run: |
      python -m pip install -e . --no-deps
      python -m pip install "urirun>=0.4.4"
      python -m urirun.connectors.connector_lint .
```

## Appendix — post-release sweep, one shot

```bash
# from the urirun repo, after 0.4.4 is on PyPI
python scripts/repin_connectors.py --write && make lint-connectors && echo "fleet on urirun>=0.4.4"
```
