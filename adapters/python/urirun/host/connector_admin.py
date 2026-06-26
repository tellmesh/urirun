from __future__ import annotations

import subprocess
from pathlib import Path

CONNECTOR_DOCKER_TIMEOUT = 600


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




def connector_env_check(payload: dict) -> dict:
    """Verify a connector installs and registers its urirun.bindings entry points inside a clean
    Docker image — the 'does it work in a defined environment' smoke. Local folders are bind-mounted
    read-only; pip/github specs install from the index. --no-deps (default) keeps it fast: entry-point
    metadata registers without importing heavy deps."""
    payload = payload if isinstance(payload, dict) else {}
    image = str(payload.get("image") or "python:3.13-slim").strip()
    source = str(payload.get("source") or "pip").strip().lower()
    spec = str(payload.get("spec") or "").strip()
    no_deps = payload.get("no_deps", True)
    if not spec:
        return {"ok": False, "error": "spec is required (package, repo or folder)"}
    mounts, install_target, error = docker_install_target(source, spec)
    if error:
        return error
    smoke = ("import importlib.metadata as md; "
             "eps=list(md.entry_points(group='urirun.bindings')); "
             "print('BINDINGS:'+str(len(eps))+':'+','.join(sorted({e.name for e in eps})))")
    pip_flags = "--no-deps " if no_deps else ""
    # bind-mounted folder is read-only; copy it to a writable dir so pip can build egg-info/wheel.
    setup = "cp -r /conn /build && " if mounts else ""
    build_target = "/build" if mounts else install_target
    inner = setup + "pip install --quiet " + pip_flags + build_target + " && python -c \"" + smoke + "\""
    cmd = ["docker", "run", "--rm", *mounts, image, "sh", "-lc", inner]
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


