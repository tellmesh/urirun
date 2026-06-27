"""Guard: detect package-name collisions where one import name is provided by two distributions.

Known-OK collisions (monorepo dev setup, Phase 5 extraction in progress):

  urirun_runtime          → urirun (editable) + urirun-runtime (site-packages)
  urirun_cdp              → urirun (editable) + urirun-cdp (site-packages)
  urirun_connectors_toolkit → urirun (editable) + urirun-connectors-toolkit (site-packages)

These are tolerated because:
  a) adapters/python/ is first on sys.path (editable install) — Python always resolves here
  b) the standalone packages are byte-for-byte copies of adapters/python/
  c) this test catches CONTENT DRIFT between the two copies

Any NEW unexpected collision → immediate FAIL.

Fix path (when standalone packages are published to PyPI):
  1. pip install urirun-runtime urirun-cdp urirun-connectors-toolkit  (publish them)
  2. add them as [project.dependencies] in adapters/python/pyproject.toml
  3. change include = ["urirun*"] to exclude the now-external packages
  4. re-run this test — collisions list becomes empty, content-drift checks removed
"""
from __future__ import annotations

import filecmp
import hashlib
import importlib.metadata as _meta
import importlib
import pathlib
import pytest

# ── Known-OK collision triplet (Phase 5 extraction in progress) ───────────────
_KNOWN_COLLISIONS: dict[str, tuple[str, str]] = {
    # import_name: (canonical_dist, standalone_dist)
    "urirun_runtime": ("urirun", "urirun-runtime"),
    "urirun_cdp": ("urirun", "urirun-cdp"),
    "urirun_connectors_toolkit": ("urirun", "urirun-connectors-toolkit"),
}

# ── Authoritative source paths (adapters/python takes priority via sys.path) ──
_ADAPTERS_PY = pathlib.Path(__file__).parent.parent.resolve()


def _all_urirun_collisions() -> dict[str, list[str]]:
    """Return {import_name: [dist1, dist2]} for all urirun_* names with 2+ providers."""
    pkgs = _meta.packages_distributions()
    return {
        name: dists
        for name, dists in pkgs.items()
        if name.startswith("urirun") and len(set(dists)) > 1
    }


def _dir_hash(directory: pathlib.Path) -> dict[str, str]:
    """SHA-256 of every .py file in directory (relative path → hex digest)."""
    result: dict[str, str] = {}
    for f in sorted(directory.rglob("*.py")):
        rel = f.relative_to(directory)
        if "__pycache__" in str(rel):
            continue
        result[str(rel)] = hashlib.sha256(f.read_bytes()).hexdigest()
    return result


def _standalone_dir(dist_name: str, pkg_name: str) -> pathlib.Path | None:
    """Locate the .py files installed by the standalone distribution.

    Handles both regular and editable installs (reads direct_url.json for the latter).
    """
    import json

    try:
        dist = _meta.distribution(dist_name)
    except _meta.PackageNotFoundError:
        return None

    # Editable install: direct_url.json has the source root
    direct_url = pathlib.Path(str(dist._path)) / "direct_url.json"
    if direct_url.exists():
        try:
            info = json.loads(direct_url.read_text())
            url = info.get("url", "")
            if url.startswith("file://"):
                src_root = pathlib.Path(url[7:])
                for candidate in (
                    src_root / pkg_name,
                    src_root / "src" / pkg_name,
                ):
                    if candidate.is_dir():
                        return candidate
        except Exception:
            pass

    # Regular install: package files are in the same site-packages directory as dist-info
    dist_path = pathlib.Path(str(dist._path)).parent
    for candidate in (dist_path / pkg_name, dist_path / "src" / pkg_name):
        if candidate.is_dir():
            return candidate
    return None


# ═════════════════════════════════════════════════════════════════════════════
# Tests
# ═════════════════════════════════════════════════════════════════════════════

def test_no_unexpected_collisions():
    """Any collision NOT in _KNOWN_COLLISIONS is a bug — fail loudly."""
    collisions = _all_urirun_collisions()
    unexpected = {
        name: dists
        for name, dists in collisions.items()
        if name not in _KNOWN_COLLISIONS
    }
    assert not unexpected, (
        "Unexpected package-name collision(s) detected — one import name is now provided "
        "by two distributions. This causes shadowing on PyPI installs.\n\n"
        + "\n".join(f"  {n}: {sorted(set(d))}" for n, d in unexpected.items())
        + "\n\nFix: choose ONE owner per name; remove the duplicate from the other distribution."
    )


@pytest.mark.parametrize("pkg_name,dists", [
    (k, v) for k, v in _KNOWN_COLLISIONS.items()
])
def test_known_collision_resolves_to_adapters_python(pkg_name: str, dists: tuple[str, str]):
    """Python import must always resolve to the adapters/python copy (editable priority)."""
    canonical_dist, _ = dists
    pkgs = _meta.packages_distributions()
    if pkg_name not in pkgs or len(set(pkgs[pkg_name])) < 2:
        pytest.skip(f"{pkg_name}: collision not present in this environment (standalone not installed)")
    mod = importlib.import_module(pkg_name)
    resolved = pathlib.Path(mod.__file__).resolve()
    assert str(_ADAPTERS_PY) in str(resolved), (
        f"{pkg_name} resolved to {resolved}, expected path under {_ADAPTERS_PY}. "
        f"The standalone package is shadowing the editable source — check sys.path order."
    )


@pytest.mark.parametrize("pkg_name,dists", [
    (k, v) for k, v in _KNOWN_COLLISIONS.items()
])
def test_known_collision_no_content_drift(pkg_name: str, dists: tuple[str, str]):
    """Both copies must be byte-identical — detect drift before it causes runtime surprises."""
    _, standalone_dist = dists
    pkgs = _meta.packages_distributions()
    if pkg_name not in pkgs or len(set(pkgs[pkg_name])) < 2:
        pytest.skip(f"{pkg_name}: standalone not installed, skipping drift check")

    canonical_dir = _ADAPTERS_PY / pkg_name
    standalone_dir = _standalone_dir(standalone_dist, pkg_name)

    if standalone_dir is None:
        pytest.skip(f"Cannot locate standalone {standalone_dist} directory")

    canonical_hashes = _dir_hash(canonical_dir)
    standalone_hashes = _dir_hash(standalone_dir)

    # Files in canonical but missing from standalone
    missing_from_standalone = set(canonical_hashes) - set(standalone_hashes)
    # Files present in both but with different content
    drifted = {
        f: (canonical_hashes[f], standalone_hashes[f])
        for f in canonical_hashes
        if f in standalone_hashes and canonical_hashes[f] != standalone_hashes[f]
    }

    issues: list[str] = []
    if missing_from_standalone:
        issues.append(
            f"Files in adapters/python/{pkg_name} NOT in {standalone_dist}:\n"
            + "\n".join(f"  {f}" for f in sorted(missing_from_standalone))
        )
    if drifted:
        issues.append(
            f"Content drift between adapters/python/{pkg_name} and {standalone_dist}:\n"
            + "\n".join(
                f"  {f}\n    adapters: {h[0][:12]}…\n    standalone: {h[1][:12]}…"
                for f, h in sorted(drifted.items())
            )
        )

    assert not issues, (
        f"Package collision {pkg_name} has content drift between the two copies:\n\n"
        + "\n\n".join(issues)
        + "\n\nFix: sync the content, then publish standalone to PyPI, pin in urirun deps."
    )
