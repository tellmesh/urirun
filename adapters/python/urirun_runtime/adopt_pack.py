# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Least-invasive URI adoption for capability packs.

Many packages already describe their URI surface in a manifest (tellmesh-style
``manifest.yaml`` with ``scheme`` + ``uri_patterns`` + ``handlers``). This module
maps that manifest 1:1 onto ``urirun.bindings.v2`` so the package becomes a URI
connector with no code change — point urirun at the manifest:

```bash
python -m urirun.runtime.adopt_pack ../tellmesh/urikvm/urikvm/manifest.yaml --out kvm.bindings.v2.json
```

The mapping is structural:

    pattern  -> binding uri
    kind     -> meta.uriKind (query/command)
    operation + handlers.python[operation] (python://mod:func) -> local-function ref
    side_effects / approval -> policy

Unhydrated ``local-function`` refs run in simulated mode, so the registry
validates and dispatches before the pack's own dependencies are installed.
"""

from __future__ import annotations

import json
from pathlib import Path


def _load(path: str | Path) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    if str(path).endswith((".yaml", ".yml")):
        import yaml  # optional dependency; only needed for YAML manifests

        return yaml.safe_load(text)
    return json.loads(text)


def _policy(pattern: dict) -> dict:
    policy: dict = {}
    if pattern.get("approval") == "required":
        policy["approval"] = "required"
    if pattern.get("side_effects"):
        policy["sideEffects"] = True
    return policy


def _handlers(manifest: dict) -> dict:
    """The operation->handler map, language-agnostic (python first, then node/js)."""
    handlers = manifest.get("handlers") or {}
    for lang in ("python", "node", "js", "javascript"):
        if isinstance(handlers.get(lang), dict):
            return handlers[lang]
    for value in handlers.values():  # any single-language map
        if isinstance(value, dict):
            return value
    return {}


def manifest_bindings(manifest: dict) -> list[dict]:
    """Map a manifest dict (scheme/uri_patterns/handlers) to v2 binding dicts."""
    scheme = manifest.get("scheme")
    pack = manifest.get("id")
    handlers = _handlers(manifest)
    bindings: list[dict] = []
    for pat in manifest.get("uri_patterns") or []:
        operation = pat.get("operation")
        raw = handlers.get(operation, "")  # e.g. python://urikvm.handlers:monitor_list
        ref = raw.split("://", 1)[-1] if raw else (operation or "")
        binding = {
            "uri": pat["pattern"],
            "kind": "function",
            "adapter": "local-function",
            "ref": ref,
            "meta": {
                "label": operation or pat["pattern"],
                "operation": operation,
                "uriKind": pat.get("kind"),
                "scheme": scheme,
                "standard": f"pack '{pack}' manifest",
            },
            "source": {"type": "pack-manifest", "pack": pack, "scheme": scheme, "handler": raw},
        }
        # A python:// handler carries a re-importable descriptor so the adopted route
        # can EXECUTE from a file registry (urirun run <uri> <registry> --execute),
        # not only dry-run — the runtime hydrates module:export at call time.
        if raw.startswith("python://") and ":" in ref:
            module, _, export = ref.partition(":")
            if module and export:
                binding["python"] = {"type": "python", "module": module, "export": export}
        policy = _policy(pat)
        if policy:
            binding["policy"] = policy
        bindings.append(binding)
    return bindings


def _document(manifest: dict) -> dict:
    from urirun.runtime import v2

    bindings = manifest_bindings(manifest)
    expanded = {b["uri"]: v2.expand_binding(b["uri"], b) for b in bindings}
    return {"version": v2.VERSION, "bindings": expanded}


def adopt_document(path: str | Path) -> dict:
    return _document(_load(path))


# --------------------------------------------------------------------------- #
# Discovery: turn an *installed package name* or a *project dir* into bindings
# --------------------------------------------------------------------------- #
def _tool_urirun(pyproject: Path) -> dict:
    """Read the [tool.urirun] table from a pyproject.toml (source adoption)."""
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - py<3.11
        import tomli as tomllib  # type: ignore
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return (data.get("tool") or {}).get("urirun") or {}


def installed_manifest_path(package: str) -> Path | None:
    """Locate an installed package's manifest *without importing it* (so a pack's
    own dependencies need not be present to adopt its URI surface). Prefers a
    ``urirun.packs`` entry point, then a ``manifest.yaml`` recorded by the dist."""
    from importlib import metadata

    candidates = {package, package.replace("-", "_"), package.replace("_", "-")}

    try:
        eps = metadata.entry_points(group="urirun.packs")
    except TypeError:  # pragma: no cover - older API
        eps = metadata.entry_points().get("urirun.packs", [])  # type: ignore
    wanted = {ep.value.partition(":")[2] or "manifest.yaml" for ep in eps if ep.name in candidates}

    for name in candidates:
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        files = dist.files or []
        # entry-point-named manifest first, then any manifest.yaml in the dist
        for target in list(wanted) + ["manifest.yaml"]:
            for f in files:
                if f.name == Path(target).name or str(f).endswith(target):
                    located = Path(dist.locate_file(f))
                    if located.is_file():
                        return located
    return None


def _package_json_manifest(package_json: Path) -> dict:
    """Read the ``"urirun"`` key from a package.json (node/js adoption). It either
    points at a manifest file or carries an inline manifest (scheme/uri_patterns)."""
    data = json.loads(package_json.read_text(encoding="utf-8"))
    cfg = data.get("urirun")
    if not isinstance(cfg, dict):
        raise FileNotFoundError(f"no 'urirun' key in {package_json}")
    if cfg.get("manifest"):
        return _load(package_json.parent / cfg["manifest"])
    manifest = dict(cfg)
    manifest.setdefault("id", data.get("name"))
    return manifest


def _config_manifest(cfg: dict, base: Path, name: str | None) -> dict | None:
    """A [tool.urirun] / package.json config -> manifest dict (file ref or inline)."""
    if not isinstance(cfg, dict):
        return None
    if cfg.get("manifest"):
        return _load(base / cfg["manifest"])
    if cfg.get("uri_patterns"):
        manifest = dict(cfg)
        manifest.setdefault("id", name)
        return manifest
    return None


def adopt(target: str | Path) -> dict:
    """Adopt a manifest file, a package.json, a project dir ([tool.urirun] for
    Python or a ``urirun`` key for node), or an installed package name."""
    path = Path(target)
    if path.is_file():
        if path.name == "package.json":
            return _document(_package_json_manifest(path))
        return adopt_document(path)
    if path.is_dir():
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            manifest = _config_manifest(_tool_urirun(pyproject), path, path.name)
            if manifest is not None:
                return _document(manifest)
        package_json = path / "package.json"
        if package_json.exists():
            try:
                return _document(_package_json_manifest(package_json))
            except FileNotFoundError:
                pass
        # A tree of packs: adopt EVERY manifest.yaml (depth 1-2, matching the
        # tellmesh layout) and MERGE into one document, so adopting a whole library
        # tree is a single command instead of a per-pack loop + compile.
        manifests = sorted(set(path.glob("*/manifest.yaml")) | set(path.glob("*/*/manifest.yaml")))
        if not manifests:
            raise FileNotFoundError(f"no [tool.urirun]/urirun config or */manifest.yaml under {path}")
        if len(manifests) == 1:
            return adopt_document(manifests[0])
        from urirun.runtime import v2

        merged: dict = {"version": v2.VERSION, "bindings": {}}
        for manifest in manifests:
            try:
                merged["bindings"].update(adopt_document(manifest).get("bindings", {}))
            except Exception:  # noqa: BLE001 - skip a non-connector / invalid pack, adopt the rest
                continue
        return merged
    manifest = installed_manifest_path(str(target))
    if manifest is None:
        raise FileNotFoundError(f"no manifest for installed package {target!r} (urirun.packs entry point or <pkg>/manifest.yaml)")
    return adopt_document(manifest)


def main(argv: list[str] | None = None) -> int:
    import argparse

    from urirun.runtime import _registry as reglib

    parser = argparse.ArgumentParser(prog="urirun-adopt-pack")
    parser.add_argument("target", help="manifest file, project dir ([tool.urirun]), or installed package name")
    parser.add_argument("--out", default="-", help="bindings.v2 output (default: stdout)")
    args = parser.parse_args(argv)

    document = adopt(args.target)
    if args.out == "-":
        print(json.dumps(document, indent=2))
    else:
        reglib.write_json(args.out, document)
        print(f"{len(document['bindings'])} binding(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
