from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

CONNECTOR_DOCKER_TIMEOUT = 600
_CONNECTOR_BINDINGS_GROUP = "urirun.bindings"


def connector_pip_tail(source: str, spec: str) -> list[str] | None:
    """Translate a (source, spec) pair into the pip-install argv tail, or None when the source is
    not host pip-installable (npm/docker/http live in their own runtimes). This is the native
    urirun connector path: a pip package exposing a `urirun.bindings` entry point."""
    spec = (spec or "").strip()
    if not spec:
        return None
    if source == "pip":
        return [spec]
    if source == "github":
        url = spec
        if url.startswith("git+"):
            pass
        elif url.startswith("http://") or url.startswith("https://"):
            url = "git+" + url
        else:
            url = "git+https://github.com/" + url.strip("/")
        return [url]
    if source in {"local", "folder", "path"}:
        path = str(Path(spec).expanduser())
        target = Path(path)
        editable = target.is_dir() and ((target / "pyproject.toml").exists() or (target / "setup.py").exists())
        return ["-e", path] if editable else [path]
    return None




def refresh_connector_schemes() -> list[str]:
    """After a host pip-install, rebuild the discovery index and return the now-live schemes."""
    try:
        from urirun.runtime import discovery as _discovery
        index = _discovery.build_index(_CONNECTOR_BINDINGS_GROUP)  # mtime-aware: busts the scheme cache
        return sorted(str(k) for k in ((index or {}).get("schemes") or {}).keys())
    except Exception:  # noqa: BLE001 - install still succeeded if introspection fails
        return []




def env_check_error(ok: bool, image: str, returncode: int, tail: str) -> str | None:
    """The error message for a connector env-check result (None on success)."""
    if ok:
        return None
    if returncode == 0:
        return "no urirun.bindings registered in " + image
    return tail or "docker check failed"




def docker_install_target(source: str, spec: str) -> tuple[list[str] | None, str | None, dict | None]:
    """Resolve (docker mounts, pip install target) for a connector env-check by source kind,
    or (None, None, error_dict) when the source/path is unusable."""
    if source in {"local", "folder", "path"}:
        abspath = str(Path(spec).expanduser().resolve())
        if not Path(abspath).exists():
            return None, None, {"ok": False, "error": "path not found: " + abspath}
        return ["-v", abspath + ":/conn:ro"], "/conn", None
    if source == "github":
        tail = connector_pip_tail("github", spec)
        return [], (tail[0] if tail else spec), None
    if source == "pip":
        return [], spec, None
    return None, None, {"ok": False, "error": "docker check supports pip/github/local, not '" + source + "'"}




def run_docker_check(cmd: list[str]) -> tuple[Any, dict | None]:
    """Run the docker smoke command; return (completed_process, None) or (None, error_dict)."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=CONNECTOR_DOCKER_TIMEOUT), None
    except FileNotFoundError:
        return None, {"ok": False, "error": "docker not available on host"}
    except subprocess.TimeoutExpired:
        return None, {"ok": False, "command": " ".join(cmd),
                      "error": "docker check timed out after " + str(CONNECTOR_DOCKER_TIMEOUT) + "s"}
    except Exception as exc:  # noqa: BLE001
        return None, {"ok": False, "command": " ".join(cmd), "error": str(exc)}




def parse_bindings_output(stdout: str | None) -> tuple[int, list[str]]:
    """Parse the ``BINDINGS:<count>:<names>`` smoke marker into (count, names)."""
    count, bindings = 0, []
    for line in (stdout or "").splitlines():
        if line.startswith("BINDINGS:"):
            parts = line.split(":", 2)
            try:
                count = int(parts[1] or 0)
            except ValueError:
                count = 0
            bindings = [b for b in (parts[2] if len(parts) > 2 else "").split(",") if b]
    return count, bindings




def _parse_env_check_payload(payload: dict) -> tuple[str, str, str, bool]:
    """Normalise and extract the four env-check payload fields."""
    payload = payload if isinstance(payload, dict) else {}
    image = str(payload.get("image") or "python:3.13-slim").strip()
    source = str(payload.get("source") or "pip").strip().lower()
    spec = str(payload.get("spec") or "").strip()
    no_deps = bool(payload.get("no_deps", True))
    return image, source, spec, no_deps


def _build_docker_cmd(mounts: list, install_target: str, no_deps: bool, image: str) -> list[str]:
    """Build the full docker-run command for the env-check smoke test."""
    smoke = ("import importlib.metadata as md; "
             "eps=list(md.entry_points(group='urirun.bindings')); "
             "print('BINDINGS:'+str(len(eps))+':'+','.join(sorted({e.name for e in eps})))")
    pip_flags = "--no-deps " if no_deps else ""
    # bind-mounted folder is read-only; copy it to a writable dir so pip can build egg-info/wheel.
    setup = "cp -r /conn /build && " if mounts else ""
    build_target = "/build" if mounts else install_target
    inner = setup + "pip install --quiet " + pip_flags + build_target + " && python -c \"" + smoke + "\""
    return ["docker", "run", "--rm", *mounts, image, "sh", "-lc", inner]


def connector_env_check(payload: dict) -> dict:
    """Verify a connector installs and registers its urirun.bindings entry points inside a clean
    Docker image — the 'does it work in a defined environment' smoke. Local folders are bind-mounted
    read-only; pip/github specs install from the index. --no-deps (default) keeps it fast: entry-point
    metadata registers without importing heavy deps."""
    image, source, spec, no_deps = _parse_env_check_payload(payload)
    if not spec:
        return {"ok": False, "error": "spec is required (package, repo or folder)"}
    mounts, install_target, error = docker_install_target(source, spec)
    if error:
        return error
    cmd = _build_docker_cmd(mounts, install_target, no_deps, image)
    proc, error = run_docker_check(cmd)
    if error:
        return error
    count, bindings = parse_bindings_output(proc.stdout)
    combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    tail = "\n".join(combined.splitlines()[-15:])
    ok = proc.returncode == 0 and count > 0
    return {"ok": ok, "image": image, "source": source, "spec": spec,
            "returncode": proc.returncode, "bindings": bindings, "bindingCount": count,
            "command": " ".join(cmd), "log": tail,
            "error": env_check_error(ok, image, proc.returncode, tail)}



import subprocess
import sys

CONNECTOR_INSTALL_TIMEOUT = 300


def _connector_install_node(node: str, payload: dict, *, config: "str | None",
                            node_urls: "list[str] | None", token: "str | None",
                            identity: "str | None",
                            node_url_from_config: "Any", node_token_for: "Any",
                            node_client: "Any") -> dict:
    """Install a connector on a remote node (NodeClient.ensure_scheme)."""
    raw = str(payload.get("scheme") or payload.get("spec") or "").strip()
    scheme = raw.split("://", 1)[0].strip().lower()
    if scheme.startswith("urirun-connector-"):
        scheme = scheme[len("urirun-connector-"):]
    if not scheme:
        return {"ok": False, "error": "scheme is required to install on a node (e.g. 'time')"}
    node_url = node_url_from_config(config, node_urls, node)
    if not node_url:
        return {"ok": False, "error": "unknown node '" + node + "'"}
    tok = node_token_for(node, token)
    client = node_client(node_url, token=tok, identity=identity)
    try:
        before = sorted(client.schemes())
    except Exception:  # noqa: BLE001
        before = []
    try:
        res = client.ensure_scheme(scheme, install=True)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "target": "node:" + node, "nodeUrl": node_url, "scheme": scheme, "error": str(exc)}
    res = res if isinstance(res, dict) else {"ok": bool(res)}
    try:
        after = sorted(client.schemes())
    except Exception:  # noqa: BLE001
        after = before
    ok = bool(res.get("ok"))
    return {"ok": ok, "target": "node:" + node, "nodeUrl": node_url, "scheme": scheme,
            "already": bool(res.get("already")), "schemes": after,
            "added": sorted(set(after) - set(before)), "detail": res,
            "error": None if ok else (res.get("error") or "ensure_scheme failed")}


def connector_install(project: str, payload: dict, *, config: "str | None" = None,
                      node_urls: "list[str] | None" = None, token: "str | None" = None,
                      identity: "str | None" = None,
                      node_url_from_config: "Any" = None,
                      node_token_for: "Any" = None,
                      node_client: "Any" = None) -> dict:
    """Install a URI connector on the host or a node from a chosen source."""
    payload = payload if isinstance(payload, dict) else {}
    target = str(payload.get("target") or "host").strip()
    if target.startswith("node:"):
        return _connector_install_node(
            target[len("node:"):], payload, config=config, node_urls=node_urls,
            token=token, identity=identity,
            node_url_from_config=node_url_from_config,
            node_token_for=node_token_for,
            node_client=node_client,
        )
    source = str(payload.get("source") or "pip").strip().lower()
    spec = str(payload.get("spec") or "").strip()
    if not spec:
        return {"ok": False, "error": "spec is required (package, repo, path or image)"}
    pip_tail = connector_pip_tail(source, spec)
    if pip_tail is None:
        hints = {
            "npm": "npm install -g " + spec + "   # expose via a urirun node argv connector",
            "docker": "docker pull " + spec + "   # run via a docker-exec / docker-run adapter route",
            "http": "register " + spec + " as an http:// connector route (no host install needed)",
        }
        return {"ok": False, "source": source, "spec": spec,
                "error": "source '" + source + "' is not host pip-installable",
                "hint": hints.get(source, "unsupported source")}
    cmd = [sys.executable, "-m", "pip", "install", *pip_tail]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CONNECTOR_INSTALL_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"ok": False, "source": source, "spec": spec, "command": " ".join(cmd),
                "error": "pip install timed out after " + str(CONNECTOR_INSTALL_TIMEOUT) + "s"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "source": source, "spec": spec, "command": " ".join(cmd), "error": str(exc)}
    ok = proc.returncode == 0
    schemes = refresh_connector_schemes() if ok else []

    def _tail(text: str) -> str:
        return "\n".join((text or "").strip().splitlines()[-12:])

    return {"ok": ok, "source": source, "spec": spec, "command": " ".join(cmd),
            "returncode": proc.returncode, "schemes": schemes,
            "stdout": _tail(proc.stdout), "stderr": _tail(proc.stderr),
            "error": None if ok else (_tail(proc.stderr) or "pip install failed")}
