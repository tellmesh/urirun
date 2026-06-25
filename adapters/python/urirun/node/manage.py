# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Built-in node self-management routes, addressable as URIs (the urirun way) instead of
# a shell script. A node served with `--manage` exposes, admin-gated:
#
#   node://<name>/package/command/install   {spec, upgrade?}   pip-install into the node's OWN venv
#   node://<name>/package/query/list        {match?}           list installed packages
#   node://<name>/runtime/query/info        {}                 interpreter / venv / platform
#   node://<name>/connector/command/install {id}               install a urirun-connector-<id>
#   node://<name>/capability/query/check    {scheme?, route?}  is a scheme/route runnable HERE?
#   node://<name>/registry/command/adopt    {scheme?}          make installed connector routes live
#
# Handlers run in-process and shell out to THIS node's interpreter (sys.executable), so a
# host can provision a remote node — add the office connectors, cryptography, anything —
# over the mesh, no SSH. These are powerful (arbitrary install), so the node server gates
# every node:// route behind the admin token / enrolled key. The adopt command is advertised
# here, but handled by the HTTP node server because it mutates the live served registry.

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from typing import Any

_PIP_LIST_TIMEOUT = 120
_START_TIMEOUT_S = 900       # 15 min: pip install / connector install ceiling
_SCAN_MANIFEST_MAX = 500     # max connector manifests scanned per root


def _pip(args: list[str], timeout: float = _START_TIMEOUT_S) -> dict:
    cmd = [sys.executable, "-m", "pip", *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "cmd": cmd}
    return {"ok": r.returncode == 0, "returncode": r.returncode,
            "stdout": r.stdout[-4000:], "stderr": r.stderr[-2000:]}


# --- install source policy (safe autonomous acquisition) -------------------------
# What an autonomous agent may install, controlled by env (so a node operator sets the
# trust boundary): kinds in URIRUN_INSTALL_ALLOW (default catalog,local — git OFF), local
# paths confined to URIRUN_INSTALL_ROOTS/URIRUN_CONNECTOR_ROOTS (default ~/github), git
# hosts to URIRUN_INSTALL_GIT_HOSTS. Refusals are reported, never silently installed.

def _install_policy() -> dict:
    kinds = {k.strip() for k in os.environ.get("URIRUN_INSTALL_ALLOW", "catalog,local").split(",") if k.strip()}
    roots_env = os.environ.get("URIRUN_INSTALL_ROOTS") or os.environ.get("URIRUN_CONNECTOR_ROOTS") or "~/github"
    roots = [os.path.realpath(os.path.expanduser(r)) for r in roots_env.split(os.pathsep) if r.strip()]
    git_hosts = [h.strip() for h in os.environ.get("URIRUN_INSTALL_GIT_HOSTS", "").split(",") if h.strip()]
    return {"kinds": sorted(kinds), "roots": roots, "gitHosts": git_hosts}


def _classify_source(s: str) -> str:
    if s.startswith(("git+", "git@", "ssh://")):
        return "git"
    if s.startswith(("http://", "https://")):
        return "git" if s.endswith(".git") else "catalog"
    if s.startswith(("~", "/", ".")) or os.sep in s or os.path.exists(os.path.expanduser(s)):
        return "local"
    return "catalog"


def _policy_allows(kind: str, source: str, policy: dict) -> tuple[bool, str]:
    if kind not in policy["kinds"]:
        return False, f"source kind '{kind}' not allowed (URIRUN_INSTALL_ALLOW={','.join(policy['kinds'])})"
    if kind == "local" and policy["roots"]:
        rp = os.path.realpath(os.path.expanduser(source))
        if not any(rp == r or rp.startswith(f"{r}{os.sep}") for r in policy["roots"]):
            return False, f"local path outside allowed roots {policy['roots']}"
    if kind == "git" and policy["gitHosts"] and not any(h in source for h in policy["gitHosts"]):
        return False, f"git host not in allow-list {policy['gitHosts']}"
    return True, "ok"


def install_policy(**payload: Any) -> dict:
    """The node's install source policy (what an agent may install + from where)."""
    return {"ok": True, **_install_policy()}


def package_install(**payload: Any) -> dict:
    """pip-install one or more specs into the node's venv (PyPI name / version / git+url /
    local path). Each spec is checked against the node's install policy."""
    spec = payload.get("spec") or payload.get("package")
    if not spec:
        return {"ok": False, "error": "spec required (PyPI name, version spec, or git+url)"}
    specs = spec if isinstance(spec, list) else [str(spec)]
    policy = _install_policy()
    for sp in specs:
        ok, reason = _policy_allows(_classify_source(str(sp)), str(sp), policy)
        if not ok:
            return {"ok": False, "error": f"install blocked by policy: {reason}", "spec": sp, "policy": policy}
    args = ["install"]
    if payload.get("upgrade", True):
        args.append("--upgrade")
    args += specs
    res = _pip(args)
    res["installed"] = specs if res.get("ok") else []
    return res


def _refresh_install_caches() -> None:
    """Make a just-pip-installed connector visible to THIS long-running process without a
    restart. Two things go stale: (1) an EDITABLE install adds its source via a .pth/finder that
    site only processes at interpreter startup — so re-run site.addsitedir to activate it, else
    ep.load() raises ModuleNotFoundError and the connector is silently skipped; (2) importlib's
    metadata/import caches — drop them so the new dist-info and modules are discoverable."""
    import site
    for d in (*site.getsitepackages(), site.getusersitepackages()):
        if os.path.isdir(d):
            site.addsitedir(d)  # replays .pth files → activates a new editable install's finder
    importlib.invalidate_caches()
    try:
        from importlib import metadata as _md
        for cached in (getattr(_md.FastPath.__new__, "cache_clear", None),
                       getattr(_md.FastPath.lookup, "cache_clear", None)):
            if cached:
                cached()
    except Exception:  # noqa: BLE001
        pass


def _project_root(path: str) -> str:
    """A local connector's installable root: the nearest ancestor (incl. itself) holding a
    pyproject.toml/setup.py/setup.cfg. Connectors that keep connector.manifest.json INSIDE the
    package dir yield a `source` that pip can't install (-e on a bare package dir); walk up so
    `pip install -e` resolves to the project that actually declares the build."""
    cur = os.path.abspath(path)
    for _ in range(5):
        if any(os.path.exists(os.path.join(cur, f)) for f in ("pyproject.toml", "setup.py", "setup.cfg")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return path


def connector_install(**payload: Any) -> dict:
    """Install a connector from ANY source into the node's venv:
      - a catalog id ("browser-control") → urirun-connector-<id> (PyPI, then if-uri GitHub),
      - a local path ("~/github/foo" or "/abs/path", `editable` for -e),
      - a git url ("git+https://…", "https://…/x.git", "git@…").
    """
    src = payload.get("source") or payload.get("id") or payload.get("connector")
    if not src:
        return {"ok": False, "error": "source/id required (catalog id, local path, or git url)"}
    s = str(src).strip()
    kind = _classify_source(s)
    policy = _install_policy()
    ok, reason = _policy_allows(kind, s, policy)
    if not ok:
        return {"ok": False, "error": f"install blocked by policy: {reason}", "source": s, "sourceKind": kind, "policy": policy}
    if kind == "git":
        spec = s if s.startswith(("git+", "git@", "ssh://")) else f"git+{s}"
        res = _pip(["install", "--upgrade", spec])
    elif kind == "local":
        path = _project_root(os.path.expanduser(s))
        res = _pip(["install", "--upgrade", *(["-e"] if payload.get("editable") else []), path])
    else:
        res = _pip(["install", "--upgrade", f"urirun-connector-{s}"])
        if not res.get("ok"):  # if-uri GitHub fallback, only when git is permitted
            gurl = f"git+https://github.com/if-uri/urirun-connector-{s}.git"
            if _policy_allows("git", gurl, policy)[0]:
                res = _pip(["install", "--upgrade", gurl])
    if res.get("ok"):
        _refresh_install_caches()
    res["connector"], res["source"], res["sourceKind"] = s, s, kind
    res["hint"] = "make routes live: run node://<name>/registry/command/adopt or deploy the connector bindings with --merge"
    return res


def _connector_match(obj: Any, match: str) -> bool:
    """A connector entry matches when no filter is set, or the filter substring is
    present anywhere in its serialized form (id, scheme, summary, source path, ...)."""
    return not match or match in json.dumps(obj, ensure_ascii=False).lower()


def _scan_local_connectors(roots: list, match: str) -> list:
    """Scan roots for connector manifests — if-uri `connector.manifest.json` and tellmesh
    `manifest.yaml` — returning matched local entries (each tagged with its `_mf` path)."""
    import glob
    local, seen = [], set()
    for root in roots:
        base = os.path.expanduser(root)
        patterns = [os.path.join(base, *(["*"] * d), name)
                    for d in (1, 2, 3) for name in ("connector.manifest.json", "*/connector.manifest.json")]
        patterns += [os.path.join(base, *(["*"] * d), "manifest.yaml") for d in (2, 3)]
        for mf in sorted({p for pat in patterns for p in glob.glob(pat)})[:_SCAN_MANIFEST_MAX]:
            path = os.path.dirname(mf)
            if path in seen:
                continue
            seen.add(path)
            entry = _read_connector_manifest(mf, path)
            if not entry:
                continue
            entry["_mf"] = mf
            if _connector_match(entry, match):
                local.append(entry)
    return local


def _augment_local_routes(local: list, payload: dict) -> None:
    """Derive each local connector's real route URIs from source (zero-install), in place,
    so a planner can choose a not-yet-installed capability. Capped to bound subprocess cost."""
    for entry in local[:int(payload.get("max_derive", 12))]:
        routes = _derive_local_routes(entry.get("_mf", ""), entry["source"])
        if routes:
            entry["routes"] = routes
            entry["schemes"] = sorted({u.split("://", 1)[0] for u in routes}) or entry.get("schemes")


def _list_installed_connectors(match: str) -> list:
    """Matched connectors already installed in this node's environment (entry points)."""
    installed = []
    try:
        from urirun.runtime import v2
        for c in v2.connector_health():
            e = {"id": c.get("name"), "bindingCount": c.get("bindingCount"), "ok": c.get("ok")}
            if _connector_match(e, match):
                installed.append(e)
    except Exception:  # noqa: BLE001
        pass
    return installed


def connector_discover(**payload: Any) -> dict:
    """Find connectors to satisfy a capability, across local projects and what's installed.

    Scans `roots` (default $URIRUN_CONNECTOR_ROOTS or ~/github) for connector projects —
    if-uri `connector.manifest.json` and tellmesh `manifest.yaml` (scheme + uri_patterns) —
    and lists installed connectors. `match`/`scheme` narrows results. Each local hit carries
    a `source` path usable directly with connector/command/install."""
    roots = payload.get("roots") or os.environ.get("URIRUN_CONNECTOR_ROOTS") or "~/github"
    roots = roots if isinstance(roots, list) else str(roots).split(os.pathsep)
    match = str(payload.get("match") or payload.get("scheme") or "").lower()
    local = _scan_local_connectors(roots, match)
    if payload.get("include_routes") or payload.get("routes"):
        _augment_local_routes(local, payload)
    for entry in local:
        entry.pop("_mf", None)
    installed = _list_installed_connectors(match)
    return {"ok": True, "roots": [os.path.expanduser(r) for r in roots], "local": local, "installed": installed}


def _derive_local_routes(mf: str, path: str) -> list:
    """Real route URIs of a local (uninstalled) connector: tellmesh from manifest.yaml
    uri_patterns (no import); if-uri by importing its urirun_bindings() in an ISOLATED
    subprocess (so a faulty/heavy connector can't affect the node)."""
    if mf.endswith(".yaml"):
        try:
            return [ln.split("pattern:", 1)[1].strip()
                    for ln in open(mf, encoding="utf-8").read().splitlines() if "pattern:" in ln]
        except Exception:  # noqa: BLE001
            return []
    parent, pkg = os.path.dirname(path), os.path.basename(path)
    code = ("import sys,json;sys.path.insert(0,%r);m=__import__(%r);"
            "b=getattr(m,'urirun_bindings',None);"
            "print(json.dumps(sorted((b() if callable(b) else {}).get('bindings',{}).keys())))" % (parent, pkg))
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=25)
        return json.loads(r.stdout.strip() or "[]") if r.returncode == 0 else []
    except Exception:  # noqa: BLE001
        return []


def _read_json_manifest(mf: str, path: str) -> dict:
    """An if-uri ``connector.manifest.json`` → normalized connector record."""
    m = json.loads(open(mf, encoding="utf-8").read())
    routes = [r if isinstance(r, str) else r.get("uri") for r in (m.get("routes") or [])]
    return {"id": m.get("id"), "name": m.get("name"), "kind": "if-uri",
            "schemes": m.get("uriSchemes") or m.get("schemes") or [],
            "routes": [r for r in routes if r], "source": path}


def _read_tellmesh_manifest(mf: str, path: str) -> dict | None:
    """A tellmesh ``manifest.yaml`` (has ``uri_patterns``) → normalized record, else None."""
    text = open(mf, encoding="utf-8").read()
    if "uri_patterns" not in text:
        return None  # not a connector pack manifest
    scheme = next((ln.split(":", 1)[1].strip() for ln in text.splitlines() if ln.startswith("scheme:")), "")
    cid = next((ln.split(":", 1)[1].strip() for ln in text.splitlines() if ln.startswith("id:")), os.path.basename(path))
    return {"id": cid, "name": cid, "kind": "tellmesh", "schemes": [scheme] if scheme else [], "source": path}


def _read_connector_manifest(mf: str, path: str) -> dict | None:
    try:
        if mf.endswith(".json"):
            return _read_json_manifest(mf, path)
        return _read_tellmesh_manifest(mf, path)
    except Exception:  # noqa: BLE001
        return None


def registry_installed(**payload: Any) -> dict:
    """The bindings exposed by connectors INSTALLED in this node's venv — calls each
    `urirun.bindings` entry point (a `urirun_bindings()` returning a {version,bindings}
    doc) so a host can `deploy --merge` them to make the routes live."""
    from urirun.runtime import v2
    merged: dict = {}
    for ep in v2._select_entry_points(v2.ENTRY_POINT_GROUP):
        try:
            obj = ep.load()
            doc = obj() if callable(obj) else obj
            merged.update((doc or {}).get("bindings") or {})
        except Exception:  # noqa: BLE001 - one faulty connector must not blank the rest
            continue
    match = str(payload.get("match") or payload.get("scheme") or "").lower()
    if match:
        merged = {u: e for u, e in merged.items() if match in u.lower()}
    return {"ok": True, "version": v2.VERSION, "bindings": merged, "count": len(merged)}


def _installed_route_owners() -> dict:
    """{route-uri -> connector(entry-point name)} for every connector installed in this
    env. Pure `urirun.bindings` introspection — no node, no admin mutation, no import of
    the heavy connector modules beyond their bindings entry point."""
    from urirun.runtime import v2
    owners: dict = {}
    for ep in v2._select_entry_points(v2.ENTRY_POINT_GROUP):
        try:
            obj = ep.load()
            doc = obj() if callable(obj) else obj
            for uri in (doc or {}).get("bindings") or {}:
                owners.setdefault(uri, ep.name)
        except Exception:  # noqa: BLE001 - one faulty connector must not blank the rest
            continue
    return owners


def _route_key(uri: str) -> str:
    """Normalise a route URI for matching regardless of the host/<name> segment, so
    ``fs://host/file/command/write-b64`` matches ``fs://laptop/file/command/write-b64``."""
    if "://" not in uri:
        return uri
    scheme, rest = uri.split("://", 1)
    tail = rest.split("/", 1)[1] if "/" in rest else ""
    return f"{scheme}://*/{tail}"


def capability_check(**payload: Any) -> dict:
    """Is a ``scheme`` (optionally a specific ``route``) served by a connector INSTALLED in
    this environment? Pure read-only capability introspection exposed AS A URI:

        node://<name>/capability/query/check {scheme?, route?}

    Lets any caller — a host, a workflow, a flow step, or a test — gate on what is actually
    runnable HERE without importing connector internals or guessing module names. Returns
    ``{available, scheme, route, connectors:[…], routes:[…], count}``; ``available`` is
    true iff the scheme (or the exact route, host-segment-insensitive) has a provider."""
    scheme = str(payload.get("scheme") or "").lower().strip()
    route = str(payload.get("route") or "").strip()
    if route and "://" in route and not scheme:
        scheme = route.split("://", 1)[0].lower()
    owners = _installed_route_owners()
    scoped = {u: c for u, c in owners.items()
              if not scheme or (u.split("://", 1)[0].lower() == scheme if "://" in u else False)}
    if route:
        want = _route_key(route)
        routes = sorted(u for u in scoped if _route_key(u) == want)
    else:
        routes = sorted(scoped)
    connectors = sorted({scoped[u] for u in routes}) if route else sorted(set(scoped.values()))
    return {"ok": True, "available": bool(routes), "scheme": scheme or None,
            "route": route or None, "connectors": connectors, "routes": routes, "count": len(routes)}


def registry_adopt(**payload: Any) -> dict:
    """Advertised management route; the live node HTTP handler owns the mutation."""
    return {"ok": False, "error": "registry/command/adopt must be executed against a managed node"}


def package_list(**payload: Any) -> dict:
    res = _pip(["list", "--format=freeze"], timeout=_PIP_LIST_TIMEOUT)
    if not res.get("ok"):
        return res
    lines = (res.get("stdout") or "").splitlines()
    match = str(payload.get("match") or "").lower()
    if match:
        lines = [ln for ln in lines if match in ln.lower()]
    return {"ok": True, "packages": lines}


def runtime_info(**payload: Any) -> dict:
    import platform

    info = {"ok": True, "python": sys.executable, "pythonVersion": platform.python_version(),
            "prefix": sys.prefix, "platform": platform.platform()}
    try:
        from importlib.metadata import version
        info["urirun"] = version("urirun")
    except Exception:
        pass
    return info


_ROUTES = [
    ("package/command/install", "command", "package_install",
     {"spec": {"type": ["string", "array"]}, "upgrade": {"type": "boolean"}}),
    ("connector/command/install", "command", "connector_install",
     {"source": {"type": "string"}, "id": {"type": "string"}, "editable": {"type": "boolean"}}),
    ("connector/query/discover", "query", "connector_discover",
     {"match": {"type": "string"}, "scheme": {"type": "string"}, "roots": {"type": ["string", "array"]}}),
    ("registry/query/installed", "query", "registry_installed", {"match": {"type": "string"}, "scheme": {"type": "string"}}),
    ("capability/query/check", "query", "capability_check",
     {"scheme": {"type": "string"}, "route": {"type": "string"}}),
    ("registry/command/adopt", "command", "registry_adopt", {"scheme": {"type": "string"}}),
    ("policy/query/show", "query", "install_policy", {}),
    ("package/query/list", "query", "package_list", {"match": {"type": "string"}}),
    ("runtime/query/info", "query", "runtime_info", {}),
]


def bindings(name: str) -> dict:
    """v2 bindings for this node's management surface, namespaced under its name."""
    out: dict[str, dict] = {}
    for path, kind, export, props in _ROUTES:
        out[f"node://{name}/{path}"] = {
            "kind": kind, "adapter": "local-function",
            "ref": f"urirun.node.manage:{export}",
            "python": {"type": "python", "module": "urirun.node.manage", "export": export},
            "inputSchema": {"type": "object", "additionalProperties": True, "properties": props},
            "policy": {"allowExecute": True},
            "meta": {"label": f"node management · {path}"},
        }
    return {"version": "urirun.bindings.v2", "bindings": out}
