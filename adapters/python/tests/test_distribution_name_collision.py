"""Guard: no top-level import name is shipped by more than one distribution.

Phase-5 extraction left several ``urirun_*`` import packages copied into BOTH the bundled
``urirun`` distribution (``adapters/python``, ``include = ["urirun*"]``) and a standalone
repo-root distribution (``urirun-runtime``, ``urirun-cdp``, ``urirun-connectors-toolkit``).
When two installed distributions ship the same top-level import name, which
copy wins is install-order dependent, and the hand-maintained copies drift — exactly the
"fresh install broken" failure mode this project has hit before.

This test parses every ``pyproject.toml`` in the working tree, computes the set of top-level
import packages each distribution would ship, and asserts no name is shipped by more than one
distribution. It runs in normal pytest (no install needed) so a regression — re-adding a
colliding source tree — fails in <1s, which the within-bundle shim tests cannot catch.

The companion install-time check lives in ``scripts/test_pypi_install.sh --collision`` (it uses
``importlib.metadata.packages_distributions`` against a real multi-distribution venv).
"""
from __future__ import annotations

import sys
from fnmatch import fnmatch
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - <3.11 fallback
    import tomli as tomllib

# Directories that never contain shippable source (build artifacts, caches, VCS, venvs).
_SKIP_DIRS = {
    ".git", ".github", "build", "dist", "node_modules", "__pycache__",
    ".pytest_cache", ".venv", "venv", ".mypy_cache", ".ruff_cache", ".tox",
}


def _repo_root() -> Path:
    """The directory under which the sibling distributions live.

    In the full monorepo working tree this is the parent that holds ``urirun-cdp`` /
    ``urirun-runtime`` next to ``urirun``. In a standalone ``urirun`` checkout (only the
    bundle present) it falls back to ``adapters/python`` — the test then trivially passes
    (the bundle ships each name exactly once).
    """
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / "urirun-cdp" / "pyproject.toml").exists() or (anc / "urirun-runtime" / "pyproject.toml").exists():
            return anc
    return here.parents[2]  # .../urirun/adapters/python


def _iter_pyprojects(root: Path):
    """Every pyproject.toml under root, skipping build/cache/VCS directories."""
    for path in root.rglob("pyproject.toml"):
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def _package_dir_name(child: Path, includes: list[str], excludes: list[str]) -> str | None:
    """Return ``child``'s import name if it is a shippable package dir, else ``None``.

    Shippable = a real importable package directory (has ``__init__.py``, not a skip/egg-info
    dir) whose name matches an ``include`` pattern and no ``exclude`` pattern."""
    name = child.name
    if not child.is_dir() or name in _SKIP_DIRS or name.endswith(".egg-info"):
        return None
    if not (child / "__init__.py").exists():
        return None
    if not any(fnmatch(name, pat) for pat in includes):
        return None
    if any(fnmatch(name, pat) for pat in excludes):
        return None
    return name


def _packages_from_find(dist_dir: Path, find: dict) -> set[str]:
    """Physical packages discovered by a ``[tool.setuptools.packages.find]`` table.

    Scans each ``where`` root (default ``.``) for immediate child package dirs that pass the
    ``include`` / ``exclude`` globs."""
    wheres = find.get("where", ["."])
    includes = find.get("include", ["*"])
    excludes = find.get("exclude", [])
    found: set[str] = set()
    for where in wheres:
        base = (dist_dir / where).resolve()
        if not base.is_dir():
            continue
        for child in base.iterdir():
            name = _package_dir_name(child, includes, excludes)
            if name is not None:
                found.add(name)
    return found


def _top_level_packages(pyproject: Path) -> set[str]:
    """Top-level import packages a distribution would ship, from its setuptools config.

    Handles the three shapes used in this repo:
      * ``[tool.setuptools] packages = [...]``      → explicit list (``[]`` = ships nothing).
      * ``[tool.setuptools] py-modules = [...]``     → top-level modules.
      * ``[tool.setuptools.packages.find]``          → scan ``where`` roots for packages
                                                       matching ``include`` / not ``exclude``.
    Packages are discovered *physically* (dirs with ``__init__.py``) so the result reflects
    what actually lands on ``sys.path`` — which is what causes install-time shadowing.
    """
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    setuptools_cfg = data.get("tool", {}).get("setuptools", {})
    dist_dir = pyproject.parent
    pkgs_node = setuptools_cfg.get("packages")

    # `[tool.setuptools] packages = [...]` → explicit list (an empty list = ship nothing).
    if isinstance(pkgs_node, list):
        names = {p.split(".")[0] for p in pkgs_node}
        names |= {m.split(".")[0] for m in setuptools_cfg.get("py-modules", [])}
        return names
    # `[tool.setuptools] py-modules = [...]` with no packages table.
    if pkgs_node is None and "py-modules" in setuptools_cfg:
        return {m.split(".")[0] for m in setuptools_cfg["py-modules"]}

    # `[tool.setuptools.packages.find]` → scan `where` roots; default to find-all from ".".
    find = pkgs_node.get("find", {}) if isinstance(pkgs_node, dict) else {}
    return _packages_from_find(dist_dir, find)


def test_no_import_name_shipped_by_two_distributions():
    root = _repo_root()
    # import-name -> {distribution name (project.name): pyproject path}
    shipped: dict[str, dict[str, str]] = {}

    for pyproject in _iter_pyprojects(root):
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        dist_name = data.get("project", {}).get("name")
        if not dist_name:  # not a PEP 621 distribution (e.g. a bare tool config)
            continue
        for pkg in _top_level_packages(pyproject):
            shipped.setdefault(pkg, {})[dist_name] = str(pyproject.relative_to(root))

    collisions = {pkg: dists for pkg, dists in shipped.items() if len(dists) > 1}
    assert not collisions, "import names shipped by >1 distribution:\n" + "\n".join(
        f"  {pkg}: " + ", ".join(f"{d} ({p})" for d, p in sorted(dists.items()))
        for pkg, dists in sorted(collisions.items())
    )


def test_bundle_owns_the_urirun_namespace_packages():
    """Positive assertion: the bundled ``urirun`` distribution is the one that ships the
    formerly-colliding ``urirun_*`` import names (so the meta-packages truly ship nothing)."""
    root = _repo_root()
    bundle = root / "urirun" / "adapters" / "python" / "pyproject.toml"
    if not bundle.exists():  # standalone layout — bundle is at the discovered root itself
        bundle = next((p for p in _iter_pyprojects(root)
                       if tomllib.loads(p.read_text())["project"].get("name") == "urirun"), None)
    assert bundle is not None, "could not locate the urirun bundle pyproject"
    pkgs = _top_level_packages(bundle)
    for name in ("urirun_runtime", "urirun_cdp", "urirun_connectors_toolkit"):
        assert name in pkgs, f"bundle no longer ships {name}: {sorted(pkgs)}"
    assert "urirun_flow" not in pkgs, "bundle must not ship urirun_flow; urirun-flow owns it"


def test_urirun_flow_owned_by_standalone_distribution():
    root = _repo_root()
    owners: dict[str, set[str]] = {}
    for pyproject in _iter_pyprojects(root):
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        dist_name = data.get("project", {}).get("name")
        if not dist_name:
            continue
        for pkg in _top_level_packages(pyproject):
            owners.setdefault(pkg, set()).add(dist_name)

    assert owners.get("urirun_flow") == {"urirun-flow"}, (
        f"urirun_flow ownership drifted: {owners.get('urirun_flow')}"
    )
