#!/usr/bin/env python3
# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Repin every sibling ``urirun-connector-*`` from a git source to a PyPI range.

Once urirun's v2 authoring layer ships to PyPI (>= ``--min-version``), connectors
no longer need to track git HEAD. This rewrites each connector's
``urirun @ git+...urirun.git...`` core dependency to ``urirun>=<min>``, preserving
any ``[extras]`` and leaving every other dependency, comment and bit of formatting
untouched (targeted string rewrite, not a TOML round-trip).

Safe by construction:
  * only the urirun *core* git requirement is rewritten — ``urirun-connector-*`` and
    ``urirun-flow`` deps, and existing ``urirun>=x`` version pins, are never touched;
  * connectors with no urirun dependency (base64/hash/uuid) are skipped;
  * default mode is ``--check`` (dry-run); ``--write`` applies;
  * ``--write`` refuses unless ``urirun==<min>`` actually exists on PyPI, so you
    cannot repin to an unreleased version (override with ``--no-require-pypi``);
  * every rewritten file is re-parsed as TOML before it is saved.

Usage:
  python repin_connectors.py                 # dry-run report across the fleet
  python repin_connectors.py --write         # apply (requires urirun<min> on PyPI)
  python repin_connectors.py --min-version 0.4.4 --write
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore

# Only the urirun CORE git requirement (optional [extras], must reference urirun.git).
_GIT_REQ = re.compile(
    r'"urirun(?P<extras>\[[^\]]*\])?\s*@\s*git\+[^"]*?urirun\.git[^"]*"'
)
# Any urirun core requirement at all (git pin, version spec, or bare) — for reporting.
_ANY_REQ = re.compile(
    r'"urirun(?:\[[^\]]*\])?(?:\s*@\s*git\+[^"]*?urirun\.git[^"]*|\s*[<>=!~][^"]*)?"'
)


def find_root(explicit: str | None) -> Path:
    """Locate the directory that holds the ``urirun-connector-*`` packages."""
    if explicit:
        return Path(explicit).resolve()
    here = Path(__file__).resolve()
    candidates = [Path.cwd(), *here.parents]
    for c in candidates:
        if any(c.glob("urirun-connector-*")):
            return c
    return here.parents[2] if len(here.parents) > 2 else Path.cwd()


def pypi_has(version: str, *, timeout: float = 10.0) -> bool | None:
    """True/False if urirun==version is on PyPI; None if PyPI couldn't be reached."""
    try:
        with urllib.request.urlopen("https://pypi.org/pypi/urirun/json", timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return version in (data.get("releases") or {})
    except (urllib.error.URLError, OSError, ValueError):
        return None


def repin_text(text: str, min_version: str) -> tuple[str, list[str]]:
    """Rewrite the urirun core git req to ``urirun[extras]>=min``. Returns (new, changes)."""
    changes: list[str] = []

    def _sub(m: re.Match) -> str:
        extras = m.group("extras") or ""
        new = f'"urirun{extras}>={min_version}"'
        if new != m.group(0):
            changes.append(f"{m.group(0)}  ->  {new}")
        return new

    return _GIT_REQ.sub(_sub, text), changes


def classify(text: str) -> str:
    if _GIT_REQ.search(text):
        return "git"
    if _ANY_REQ.search(text):
        return "versioned-or-bare"
    return "no-urirun-dep"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Repin urirun-connector-* from git to a PyPI range")
    ap.add_argument("--root", default=None, help="dir containing urirun-connector-* (auto-detected)")
    ap.add_argument("--min-version", default="0.4.4")
    ap.add_argument("--write", action="store_true", help="apply changes (default: dry-run)")
    ap.add_argument("--no-require-pypi", action="store_true",
                    help="skip the 'is the target version on PyPI?' guard")
    args = ap.parse_args(argv)

    root = find_root(args.root)
    pkgs = sorted(p for p in root.glob("urirun-connector-*/pyproject.toml"))
    print(f"root: {root}")
    print(f"connectors: {len(pkgs)}   target: urirun>={args.min_version}   "
          f"mode: {'WRITE' if args.write else 'check (dry-run)'}\n")

    if args.write and not args.no_require_pypi:
        present = pypi_has(args.min_version)
        if present is None:
            print(f"refusing to write: could not reach PyPI to confirm urirun=={args.min_version} "
                  f"exists (use --no-require-pypi to override)")
            return 2
        if not present:
            print(f"refusing to write: urirun=={args.min_version} is not on PyPI yet — "
                  f"publish it first, or use --no-require-pypi")
            return 2

    changed = skipped = already = failed = 0
    for pyproject in pkgs:
        name = pyproject.parent.name
        text = pyproject.read_text(encoding="utf-8")
        kind = classify(text)
        if kind == "no-urirun-dep":
            print(f"  skip   {name:<42} no urirun dependency")
            skipped += 1
            continue
        if kind == "versioned-or-bare":
            print(f"  ok     {name:<42} already a version spec / bare (left as-is)")
            already += 1
            continue
        new_text, diffs = repin_text(text, args.min_version)
        if not diffs:
            print(f"  ok     {name:<42} already urirun>={args.min_version}")
            already += 1
            continue
        # validate TOML before committing
        if tomllib is not None:
            try:
                tomllib.loads(new_text)
            except Exception as exc:  # noqa: BLE001
                print(f"  FAIL   {name:<42} rewrite produced invalid TOML: {exc}")
                failed += 1
                continue
        if args.write:
            pyproject.write_text(new_text, encoding="utf-8")
            print(f"  REPIN  {name:<42} {diffs[0]}")
        else:
            print(f"  would  {name:<42} {diffs[0]}")
        changed += 1

    verb = "repinned" if args.write else "to repin"
    print(f"\n{changed} {verb} · {already} already-versioned · {skipped} no-dep · {failed} failed")
    if failed:
        return 1
    if not args.write and changed:
        print("dry-run only — re-run with --write to apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
