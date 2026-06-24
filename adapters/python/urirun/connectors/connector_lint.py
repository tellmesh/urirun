# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Lint a connector package for authoring duplication (refactor Phase 0 guardrail).

The lint reads a connector package and cross-checks its three declarations of the
same route — the ``@connector.command/.shell/.handler`` decorators in code, the
``routes`` array in ``connector.manifest.json``, and the ``argparse`` subparsers in
``cli.py`` — without importing the package. It reports:

* **drift**: a route in the manifest with no backing decorator, or vice versa
  (a real inconsistency — fails the lint so CI catches it);
* **adapter drift**: a ``manifest.adapterKinds`` entry that no decorator route binds
  to, or — the failing case — a route whose adapter the manifest does not advertise;
* **duplication**: how many distinct places each route identity and signature is
  spelled out (informational until the handler/cli refactor lands; ``--strict``
  turns a duplication factor > 1 into a failure).

It is intentionally static (``ast`` + ``json``) so it can run in CI against any
connector checkout without side effects.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

DECORATOR_KINDS = ("command", "shell", "handler")
MACHINE_FIELDS = ("routes", "uriSchemes", "adapterKinds")

# Env-var names whose *value* is a credential rather than an identifier/host/path. Matched
# case-insensitively against the literal read by os.getenv / os.environ[...] / os.environ.get.
# Only *conventionally* secret names are flagged — the qualified ``*_API_KEY``/``*_SECRET_KEY``
# forms, not a bare ``*_KEY`` (too often a TLS keyfile *path* like ``WEBCAM_KEY``, a partition
# key, etc.). Identifiers (USER/USERNAME/HOST/PORT/MODEL/DIR/PATH/IP/URL) are never secrets.
_SECRET_ENV_RE = re.compile(
    r"(SECRET|PASSWORD|PASSWD|TOKEN|CREDENTIAL|"
    r"API[_-]?KEY|ACCESS[_-]?KEY|PRIVATE[_-]?KEY|AUTH[_-]?KEY|SECRET[_-]?KEY|_PASS$)",
    re.IGNORECASE,
)
# Excluded: keyfile/cert *paths* (a filename, not the value) and ``*_ALLOW`` policy/allow-list
# var names (which hold globs naming a secret, not the secret itself).
_SECRET_ENV_EXCLUDE = re.compile(r"(KEY[_-]?ID|KEYWORD|KEY_?FILE|KEY_?PATH|CERT_?FILE|_ALLOW$)", re.IGNORECASE)

# Each decorator kind binds to one runtime adapter. The manifest's ``adapterKinds``
# advertises which adapters the connector uses; if it omits one a decorator route
# actually binds to, the manifest is lying about how the route executes.
KIND_TO_ADAPTER = {"command": "argv-template", "shell": "shell-template", "handler": "local-function"}

# Vendored / generated trees that aren't the connector's own source — skipped so the lint
# stays fast and correct on a real checkout (a local .venv holds thousands of .py files).
_SKIP_DIRS = {"__pycache__", ".venv", "venv", "env", ".git", "node_modules",
              "build", "dist", "site-packages", ".tox", ".mypy_cache", ".pytest_cache"}


def _connector_py_files(root: Path) -> list[Path]:
    return [
        p for p in root.rglob("*.py")
        if not (_SKIP_DIRS & set(p.parts)) and not any(part.endswith(".egg-info") for part in p.parts)
    ]


def _connector_call_target(call: ast.Call) -> tuple[str | None, str]:
    """Read the (scheme, target) keyword pair from a ``connector(...)`` call."""
    scheme, target = None, "host"
    for kw in call.keywords:
        if kw.arg == "scheme" and isinstance(kw.value, ast.Constant):
            scheme = kw.value.value
        elif kw.arg == "target" and isinstance(kw.value, ast.Constant):
            target = kw.value.value
    return scheme, target


def _connector_assignment(node: ast.AST) -> tuple[list[str], tuple[str, str]] | None:
    """Return (assigned var names, (scheme, target)) if node is a connector(...) assignment."""
    if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
        return None
    fn = node.value.func
    fname = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else None
    if fname != "connector":
        return None
    call = node.value
    cid = call.args[0].value if call.args and isinstance(call.args[0], ast.Constant) else None
    scheme, target = _connector_call_target(call)
    if scheme is None and isinstance(cid, str):
        scheme = cid.replace("-", "")
    if not scheme:
        return None
    return [t.id for t in node.targets if isinstance(t, ast.Name)], (scheme, target)


def _connector_objects(tree: ast.Module) -> dict[str, tuple[str, str]]:
    """Map each ``x = urirun.connector("id", scheme=…, target=…)`` var to (scheme, target)."""
    objs: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        found = _connector_assignment(node)
        if found is None:
            continue
        names, value = found
        for name in names:
            objs[name] = value
    return objs


def _route_uri(scheme: str, target: str, path: str) -> str:
    return path if "://" in path else f"{scheme}://{target}/{path.strip('/')}"


def _decorator_routes(tree: ast.Module, objs: dict[str, tuple[str, str]]) -> list[dict]:
    """Extract decorator-declared routes with the implementing function's signature."""
    routes: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                continue
            obj, attr = dec.func.value, dec.func.attr
            if not (isinstance(obj, ast.Name) and obj.id in objs and attr in DECORATOR_KINDS):
                continue
            if not (dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str)):
                continue
            scheme, target = objs[obj.id]
            routes.append({
                "uri": _route_uri(scheme, target, dec.args[0].value),
                "kind": attr,
                "func": node.name,
                "params": params,
                "subcommand": dec.args[0].value.strip("/").split("/")[-1],
            })
    return routes


def _cli_subcommands(py_files: list[Path]) -> set[str]:
    """Collect argparse ``add_parser("name")`` subcommand names across the package."""
    names: set[str] = set()
    for path in py_files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "add_parser" and node.args
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                names.add(node.args[0].value)
    return names


def _scan_code_routes(py_files: list[Path]) -> tuple[dict[str, tuple[str, str]], list[dict]]:
    """Parse each .py file for connector objects and their decorator routes."""
    objs: dict[str, tuple[str, str]] = {}
    code_routes: list[dict] = []
    for path in py_files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        file_objs = _connector_objects(tree)
        objs.update(file_objs)
        code_routes.extend(_decorator_routes(tree, file_objs))
    return objs, code_routes


def _load_manifest_routes(manifests: list[Path]) -> tuple[dict, list[str]]:
    """Load the first manifest and normalize its routes to a list of URI strings."""
    manifest: dict = {}
    if manifests:
        try:
            manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            manifest = {}
    routes = [r if isinstance(r, str) else r.get("uri") for r in (manifest.get("routes") or [])]
    return manifest, [r for r in routes if r]


def _route_placements(code_routes: list[dict], manifest_uris: set, cli_subs: set) -> list[dict]:
    """Count, per route, how many distinct surfaces spell out the same route identity."""
    placements = []
    for r in code_routes:
        places = ["decorator"]
        if r["uri"] in manifest_uris:
            places.append("manifest")
        if r["subcommand"] in cli_subs:
            places.append("cli")
        if r["kind"] in ("command", "shell"):
            places.append("argv-template")  # argv string repeats the signature
        placements.append({"uri": r["uri"], "places": places, "factor": len(places)})
    return placements


def _compute_drift(code_uris: set, manifest_uris: set, code_routes: list, manifest_declares_routes: bool) -> dict:
    """Cross-check code vs manifest routes.

    A decorator route missing from an explicit manifest is the unambiguous bug (a
    handler not advertised). A manifest route with no recognized decorator is only a
    warning: the connector may declare it declaratively or via another scheme. A
    prose-only manifest (no ``routes`` key) derives machine fields from the code, so
    a code route absent from the manifest is expected, not drift.
    """
    return {
        "in_manifest_not_in_code": sorted(manifest_uris - code_uris) if code_routes else [],
        "in_code_not_in_manifest": sorted(code_uris - manifest_uris) if manifest_declares_routes else [],
    }


def _adapter_drift(code_routes: list, manifest: dict) -> dict:
    """Cross-check the manifest's advertised ``adapterKinds`` against the adapters the
    decorator routes actually bind to.

    ``usedNotDeclared`` is the unambiguous bug: a route executes through an adapter
    the manifest does not advertise (the live case is ``http-check`` declaring
    ``http-service`` while ``@connector.command`` binds ``argv-template``). It fails
    the lint. ``declaredNotUsed`` is only a warning — a declared adapter no decorator
    binds to may belong to a declaratively-defined route the static scan cannot see.
    The check is skipped entirely when the manifest omits ``adapterKinds``.
    """
    declared = manifest.get("adapterKinds")
    if not isinstance(declared, list) or not code_routes:
        return {"checked": False, "declared": [], "implied": [], "usedNotDeclared": [], "declaredNotUsed": []}
    declared_set = set(declared)
    implied = {KIND_TO_ADAPTER[r["kind"]] for r in code_routes if r["kind"] in KIND_TO_ADAPTER}
    return {
        "checked": True,
        "declared": sorted(declared_set),
        "implied": sorted(implied),
        "usedNotDeclared": sorted(implied - declared_set),
        "declaredNotUsed": sorted(declared_set - implied),
    }


def _route_kind_counts(code_routes: list) -> tuple[int, int]:
    """Return (handler route count, argv-style route count)."""
    handler = sum(1 for r in code_routes if r["kind"] == "handler")
    argv = sum(1 for r in code_routes if r["kind"] in ("command", "shell"))
    return handler, argv


def _is_os_name(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "os"


def _const_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _env_read_from_subscript(node: ast.Subscript) -> str | None:
    """``os.environ["X"]`` → ``"X"``."""
    target = node.value
    if isinstance(target, ast.Attribute) and target.attr == "environ" and _is_os_name(target.value):
        return _const_str(node.slice)
    return None


def _env_read_from_call(node: ast.Call) -> str | None:
    """``os.getenv("X")`` / ``os.environ.get("X")`` / bare ``getenv("X")`` → ``"X"``."""
    fn = node.func
    first = node.args[0] if node.args else None
    if isinstance(fn, ast.Attribute):
        if fn.attr == "getenv" and _is_os_name(fn.value):
            return _const_str(first)
        if (fn.attr == "get" and isinstance(fn.value, ast.Attribute)
                and fn.value.attr == "environ" and _is_os_name(fn.value.value)):
            return _const_str(first)
    elif isinstance(fn, ast.Name) and fn.id == "getenv":
        return _const_str(first)
    return None


def _env_read_name(node: ast.AST) -> str | None:
    """Return the env-var name if ``node`` reads the process env, else ``None``.

    Recognises ``os.getenv("X")``, ``os.environ.get("X")``, ``os.environ["X"]`` and a bare
    ``getenv("X")`` (``from os import getenv``).
    """
    if isinstance(node, ast.Subscript):
        return _env_read_from_subscript(node)
    if isinstance(node, ast.Call):
        return _env_read_from_call(node)
    return None


def _scan_secret_env_reads(py_files: list[Path]) -> list[dict]:
    """Find reads of secret-shaped env vars straight from the process environment.

    These bypass the secrets layer (no ``secret_allow`` policy, no redaction, no node guard).
    The fix is to take the credential as a route argument and resolve it with
    ``urirun.resolve_secret`` (a reference may then live in the env, but its *value* is gated).
    """
    findings: list[dict] = []
    for path in py_files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            name = _env_read_name(node)
            if not name or not _SECRET_ENV_RE.search(name) or _SECRET_ENV_EXCLUDE.search(name):
                continue
            findings.append({"file": path.name, "line": getattr(node, "lineno", 0), "name": name})
    return sorted(findings, key=lambda f: (f["file"], f["line"]))


def _uses_resolve_secret(py_files: list[Path]) -> bool:
    """True if the connector routes credentials through the secrets layer at all — either the
    ``resolve_secret`` function (local-function connectors) OR a declarative reference
    (``{getv:..}`` / ``{secret:..}`` placeholder, or a bare ``getv://`` / ``secret://`` URI)
    consumed by the ``fetch`` adapter, as ksef does. A secret-env read alongside either is a
    deliberate fallback/CLI convenience, not a layer bypass."""
    for path in py_files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "resolve_secret" in text or "{getv:" in text or "{secret:" in text \
                or "getv://" in text or "secret://" in text:
            return True
    return False


def lint_connector(pkg_dir: str | Path) -> dict:
    """Analyse a connector package directory and return a structured lint report."""
    root = Path(pkg_dir)
    manifests = list(root.rglob("connector.manifest.json"))
    py_files = _connector_py_files(root)

    objs, code_routes = _scan_code_routes(py_files)
    manifest, manifest_routes = _load_manifest_routes(manifests)

    code_uris = {r["uri"] for r in code_routes}
    manifest_uris = set(manifest_routes)
    cli_subs = _cli_subcommands(py_files)
    manifest_declares_routes = "routes" in manifest

    drift = _compute_drift(code_uris, manifest_uris, code_routes, manifest_declares_routes)
    adapter_drift = _adapter_drift(code_routes, manifest)
    placements = _route_placements(code_routes, manifest_uris, cli_subs)
    handler_routes, argv_routes = _route_kind_counts(code_routes)
    secret_reads = _scan_secret_env_reads(py_files)
    uses_resolver = _uses_resolve_secret(py_files)

    return {
        "package": str(root),
        "pattern": "decorator" if code_routes else "declarative-or-unrecognized",
        "manifestMode": "explicit" if manifest_declares_routes else "derived",
        "connectorObjects": {k: {"scheme": v[0], "target": v[1]} for k, v in objs.items()},
        "routeCount": {"code": len(code_routes), "manifest": len(manifest_routes), "cliSubcommands": len(cli_subs)},
        "drift": drift,
        "hasDrift": bool(drift["in_code_not_in_manifest"]),
        "adapterDrift": adapter_drift,
        "hasAdapterDrift": bool(adapter_drift["usedNotDeclared"]),
        "machineFieldsHandWritten": [f for f in MACHINE_FIELDS if f in manifest],
        "duplication": {
            "maxFactor": max((p["factor"] for p in placements), default=0),
            "perRoute": placements,
        },
        "handlerRoutes": handler_routes,
        "argvRoutes": argv_routes,
        "secretEnvReads": {
            "count": len(secret_reads),
            "usesResolveSecret": uses_resolver,
            # A read with no resolve_secret anywhere is a likely ambient-secret bypass.
            "bypass": bool(secret_reads) and not uses_resolver,
            "findings": secret_reads,
        },
    }


def _desired_machine_fields(code_routes: list[dict]) -> dict:
    """The manifest machine fields a connector's decorator routes should project to."""
    routes = sorted({r["uri"] for r in code_routes})
    return {
        "routes": routes,
        "uriSchemes": sorted({u.split("://", 1)[0] for u in routes if "://" in u}),
        "adapterKinds": sorted({KIND_TO_ADAPTER[r["kind"]] for r in code_routes if r["kind"] in KIND_TO_ADAPTER}),
    }


def _changed_machine_fields(manifest: dict, desired: dict) -> list[str]:
    """Machine fields whose manifest value differs from the desired projection.

    A field already absent and desired-empty is left alone; everything else that drifts is
    reported (and, when writing, overwritten)."""
    return [f for f in MACHINE_FIELDS if manifest.get(f) != desired[f] and (desired[f] or f in manifest)]


def sync_manifest(pkg_dir: str | Path, write: bool = True) -> dict:
    """Make the manifest's machine fields a PROJECTION of the code: derive ``routes``,
    ``uriSchemes`` and ``adapterKinds`` from the ``@handler``/``.command``/``.shell``
    decorators (static AST scan, no import) and write them into connector.manifest.json so
    the manifest can never drift from the code. `write=False` reports the diff without writing
    (a CI check). Skips declarative / JS connectors that have no decorator routes."""
    root = Path(pkg_dir)
    manifests = list(root.rglob("connector.manifest.json"))
    if not manifests:
        return {"ok": False, "error": "no connector.manifest.json under " + str(root)}
    mpath = manifests[0]
    py_files = _connector_py_files(root)
    _objs, code_routes = _scan_code_routes(py_files)
    if not code_routes:
        return {"ok": False, "error": "no @decorator routes found (declarative or non-Python connector)",
                "manifest": str(mpath)}
    desired = _desired_machine_fields(code_routes)
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    changed = _changed_machine_fields(manifest, desired)
    if write and changed:
        for f in changed:
            manifest[f] = desired[f]
        mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"ok": True, "manifest": str(mpath), "changed": changed, "wrote": bool(write and changed), **desired}


def _format_secret_reads(sr: dict) -> list[str]:
    lines: list[str] = []
    for f in sr.get("findings", []):
        label = "SECRET ambient env read" if sr.get("bypass") else "warn  secret env read"
        lines.append(f"  {label} `{f['name']}` ({f['file']}:{f['line']}) — address by reference via urirun.resolve_secret")
    if sr.get("bypass"):
        lines.append("  → connector reads secret-shaped env vars and never calls resolve_secret: it bypasses the secrets layer (no policy/redaction/node-guard)")
    return lines


def _format_drift(rep: dict) -> list[str]:
    lines: list[str] = []
    for u in rep["drift"]["in_code_not_in_manifest"]:
        lines.append(f"  DRIFT decorator route missing from manifest: {u}")
    for u in rep["drift"]["in_manifest_not_in_code"]:
        lines.append(f"  warn  manifest route has no recognized decorator: {u}")
    ad = rep["adapterDrift"]
    if ad["checked"]:
        for a in ad["usedNotDeclared"]:
            lines.append(f"  DRIFT adapter `{a}` is used by a route but not in manifest.adapterKinds {ad['declared']}")
        for a in ad["declaredNotUsed"]:
            lines.append(f"  warn  manifest.adapterKinds declares `{a}` but no decorator route binds it")
    return lines


def _format_duplication(dup: dict) -> list[str]:
    lines = [f"  duplication: max {dup['maxFactor']}× (each route spelled out in up to {dup['maxFactor']} places)"]
    for p in dup["perRoute"]:
        if p["factor"] > 1:
            lines.append(f"    {p['uri']} — {p['factor']}×: {', '.join(p['places'])}")
    return lines


def _format_report(rep: dict) -> str:
    lines = [f"connector lint · {rep['package']}"]
    rc = rep["routeCount"]
    lines.append(f"  routes: {rc['code']} in code · {rc['manifest']} in manifest · {rc['cliSubcommands']} CLI subcommands")
    if rep["connectorObjects"]:
        objs = ", ".join(f"{k}={v['scheme']}://{v['target']}" for k, v in rep["connectorObjects"].items())
        lines.append(f"  connectors: {objs}")
    lines.extend(_format_secret_reads(rep.get("secretEnvReads") or {}))
    if rep["pattern"] != "decorator":
        lines.append("  pattern: declarative / no @connector decorators recognized — duplication & drift checks skipped")
        return "\n".join(lines)
    lines.append(f"  handler routes (in-process): {rep['handlerRoutes']} · argv routes (subprocess): {rep['argvRoutes']}")
    lines.append(f"  manifest: {rep['manifestMode']} ({'machine fields derived from code' if rep['manifestMode'] == 'derived' else 'routes declared in JSON'})")
    if rep["machineFieldsHandWritten"]:
        lines.append(f"  manifest hand-writes derivable fields: {', '.join(rep['machineFieldsHandWritten'])}")
    lines.extend(_format_drift(rep))
    lines.extend(_format_duplication(rep["duplication"]))
    return "\n".join(lines)


def sync_manifest_command(args: argparse.Namespace) -> int:
    """`urirun connectors sync-manifest <package> [--check]` — project the code's routes/
    schemes/adapters into the manifest (or, with --check, fail if they have drifted)."""
    res = sync_manifest(args.package, write=not getattr(args, "check", False))
    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif not res.get("ok"):
        print(f"sync-manifest · {res.get('error')}")
    elif getattr(args, "check", False):
        if res["changed"]:
            print(f"DRIFT · manifest machine fields are stale: {res['changed']} (run without --check to fix)")
        else:
            print("ok · manifest machine fields match the code")
    else:
        print(f"synced {res['manifest']} · {('updated ' + str(res['changed'])) if res['wrote'] else 'already in sync'}"
              f"\n  routes={len(res['routes'])} uriSchemes={res['uriSchemes']} adapterKinds={res['adapterKinds']}")
    if not res.get("ok"):
        return 2
    return 1 if (getattr(args, "check", False) and res["changed"]) else 0


def lint_command(args: argparse.Namespace) -> int:
    report = lint_connector(args.package)
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_format_report(report))
    if report["hasDrift"] or report["hasAdapterDrift"]:
        return 1
    if getattr(args, "strict", False) and report["duplication"]["maxFactor"] > 1:
        return 1
    # A clear secrets-layer bypass (secret env read, never routed through resolve_secret)
    # fails strict mode so CI can gate it.
    if getattr(args, "strict", False) and report.get("secretEnvReads", {}).get("bypass"):
        return 1
    return 0


def _import_first_bindings(root: Path, add) -> tuple[dict | None, str | None]:
    """Import the first child package exposing ``urirun_bindings()`` and return
    ``(doc, modname)``; records a failed ``import/<pkg>`` check on each import error."""
    import importlib
    import sys

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    for child in sorted(root.iterdir()):
        if not (child / "__init__.py").exists():
            continue
        try:
            mod = importlib.import_module(child.name)
        except Exception as exc:  # noqa: BLE001
            add(f"import/{child.name}", False, f"{type(exc).__name__}: {exc}")
            continue
        if hasattr(mod, "urirun_bindings"):
            return mod.urirun_bindings(), child.name
    return None, None


def _unresolved_handlers(doc: dict) -> list[str]:
    """URIs whose ``python: {module, export}`` handler can't be imported/resolved — the
    'advertised but dead route' class that yields ``ModuleNotFoundError`` after deploy."""
    import importlib

    unresolved: list[str] = []
    for uri, binding in (doc.get("bindings") or {}).items():
        py = binding.get("python") or {}
        module, export = py.get("module"), py.get("export")
        if not (module and export):
            continue  # argv-template / declarative — no python handler to import
        try:
            obj = importlib.import_module(module)
            if not hasattr(obj, export):
                unresolved.append(f"{uri} -> {module}:{export} (no such attribute)")
        except Exception as exc:  # noqa: BLE001
            unresolved.append(f"{uri} -> {module} ({type(exc).__name__})")
    return unresolved


def verify_connector(pkg_dir: str | Path) -> dict:
    """Pre-deploy GATE. Unlike :func:`lint_connector` (which is static), this IMPORTS
    the package and checks it is actually deployable: static lint (no manifest drift)
    + import + validate the bindings + compile + **resolve every route's handler**.

    The handler-resolution check catches the 'advertised but dead route' class — a
    binding whose ``python: {module, export}`` the node cannot import — which is
    exactly what produces ``ModuleNotFoundError`` after a code-less deploy. A connector
    that passes ``verify`` won't advertise routes it can't run."""
    import urirun

    root = Path(pkg_dir).resolve()
    report: dict = {"package": str(root), "ok": True, "checks": []}

    def add(name: str, ok: bool, detail: str = "") -> None:
        report["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        report["ok"] = report["ok"] and bool(ok)

    lint = lint_connector(root)
    add("lint/no-manifest-drift", not (lint.get("hasDrift") or lint.get("hasAdapterDrift")),
        f"in code not in manifest: {lint['drift']['in_code_not_in_manifest']}" if lint.get("hasDrift") else "")

    doc, modname = _import_first_bindings(root, add)
    if doc is None:
        add("bindings/found", False, "no importable package exposes urirun_bindings()")
        return report
    add(f"import/{modname}", True)

    valid = urirun.validate_binding_document(doc)
    add("bindings/valid", valid.get("ok"), str(valid.get("errors"))[:200] if not valid.get("ok") else "")
    try:
        urirun.compile_registry(doc)
        add("registry/compiles", True)
    except Exception as exc:  # noqa: BLE001
        add("registry/compiles", False, f"{type(exc).__name__}: {exc}")

    add("handlers/resolve", not (unresolved := _unresolved_handlers(doc)), "; ".join(unresolved[:5]))
    return report


def verify_command(args: argparse.Namespace) -> int:
    report = verify_connector(args.package)
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["ok"] else 1
    print(f"connector verify · {report['package']}")
    for check in report["checks"]:
        print(f"  {'PASS' if check['ok'] else 'FAIL'}  {check['check']}"
              + (f"  — {check['detail']}" if check["detail"] else ""))
    print("OK — connector is correctly built and deployable" if report["ok"]
          else "FAIL — fix the above before deploying (routes would be advertised but dead)")
    return 0 if report["ok"] else 1
