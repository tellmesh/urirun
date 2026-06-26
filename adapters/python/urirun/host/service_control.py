from __future__ import annotations

import json
import os
import re
import signal
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable


def payload_truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def service_restart_argv(
    payload: dict,
    *,
    service: str,
    env_prefix: str,
    default_unit: str,
) -> tuple[list[str] | None, dict]:
    manager = str(
        payload.get("manager") or os.environ.get(f"{env_prefix}_RESTART_MANAGER") or ""
    ).strip().lower()
    if manager in {"systemd", "systemctl"}:
        unit = str(payload.get("unit") or os.environ.get(f"{env_prefix}_SYSTEMD_UNIT") or default_unit).strip()
        if not unit:
            return None, {"error": "systemd unit is empty"}
        return ["systemctl", "--user", "restart", unit], {"manager": "systemd", "unit": unit}

    configured = str(os.environ.get(f"{env_prefix}_RESTART_CMD") or "").strip()
    if configured:
        try:
            argv = shlex.split(configured)
        except ValueError as exc:
            return None, {"error": f"invalid {env_prefix}_RESTART_CMD: {exc}"}
        if argv:
            return argv, {"manager": "command", "source": f"{env_prefix}_RESTART_CMD"}

    return None, {
        "error": f"{service} restart is not configured",
        "configureAnyOf": [
            "payload.manager=systemd with optional payload.unit",
            f"{env_prefix}_RESTART_MANAGER=systemd",
            f"{env_prefix}_RESTART_CMD='<restart command>'",
        ],
        "examplePayload": {"manager": "systemd", "unit": default_unit},
    }


def schedule_restart_command(argv: list[str], payload: dict, meta: dict) -> dict:
    delay = float(payload.get("delaySeconds") or 0.35)
    runner = (
        "import subprocess, sys, time; "
        "time.sleep(float(sys.argv[1])); "
        "raise SystemExit(subprocess.run(sys.argv[2:]).returncode)"
    )
    subprocess.Popen(
        [sys.executable, "-c", runner, str(delay), *argv],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {"ok": True, "scheduled": True, "delaySeconds": delay, "command": argv, **meta}


def _resolve_chat_service_script(payload: dict) -> str | None:
    """Locate the urirun-service-chat binary from payload/env/PATH/venv fallback."""
    script = str(payload.get("command") or os.environ.get("URIRUN_CHAT_SERVICE_CMD") or "").strip()
    if not script:
        script = shutil.which("urirun-service-chat") or str(
            Path(sys.executable).with_name("urirun-service-chat")
        )
    if not script or (os.path.sep in script and not Path(script).expanduser().exists()):
        return None
    return script


def _append_chat_restart_options(argv: list[str], *, db: str | None, config: str | None,
                                 node_urls: list[str] | None, token: str | None,
                                 identity: str | None, payload: dict) -> None:
    """Append the optional --db/--config/--node-url/--token/--identity/--force-replace flags."""
    if db:
        argv.extend(["--db", db])
    if config:
        argv.extend(["--config", config])
    for node_url in node_urls or []:
        argv.extend(["--node-url", node_url])
    if token:
        argv.extend(["--token", token])
    if identity:
        argv.extend(["--identity", identity])
    if payload_truthy(payload.get("forcePortKill") or payload.get("force")):
        argv.append("--force-replace")


def chat_service_restart_argv(
    project: str,
    db: str | None,
    config: str | None,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    payload: dict,
) -> tuple[list[str] | None, dict]:
    script = _resolve_chat_service_script(payload)
    if script is None:
        return None, {
            "error": "urirun-service-chat command was not found",
            "configureAnyOf": [
                "install urirun-service-chat in the active venv",
                "payload.command=/path/to/urirun-service-chat",
                "URIRUN_CHAT_SERVICE_CMD=/path/to/urirun-service-chat",
            ],
        }
    host = str(
        payload.get("host") or os.environ.get("URIRUN_CHAT_HOST", "127.0.0.1")
    )
    port = int(
        payload.get("port") or os.environ.get("URIRUN_CHAT_PORT", "8194")
    )
    argv = [
        script,
        "restart",
        "--project",
        str(Path(project).expanduser().resolve()),
        "--host",
        host,
        "--port",
        str(port),
    ]
    _append_chat_restart_options(argv, db=db, config=config, node_urls=node_urls,
                                 token=token, identity=identity, payload=payload)
    return argv, {"manager": "port-replace", "port": port, "commandSource": script}


def restart_chat_service(
    payload: dict,
    *,
    project: str = ".",
    db: str | None = None,
    config: str | None = None,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
) -> dict:
    argv, meta = service_restart_argv(
        payload,
        service="chat",
        env_prefix="URIRUN_CHAT",
        default_unit="urirun-service-chat.service",
    )
    meta.setdefault("exampleUri", "dashboard://host/service/chat/command/restart")
    if not argv:
        fallback_argv, auto_meta = chat_service_restart_argv(
            project,
            db,
            config,
            node_urls,
            token,
            identity,
            payload,
        )
        if fallback_argv:
            argv = fallback_argv
            meta = {"exampleUri": meta.get("exampleUri"), **auto_meta}
        else:
            meta = {**meta, **auto_meta}
    if not argv:
        return {"ok": False, **meta}
    return schedule_restart_command(argv, payload, meta)


def port_holder_pids(port: int) -> list[int]:
    """PIDs currently LISTENing on `port` (best effort via ss)."""
    try:
        out = subprocess.run(["ss", "-ltnpH"], capture_output=True, text=True, timeout=5).stdout
    except Exception:  # noqa: BLE001
        return []
    pids: list[int] = []
    for line in out.splitlines():
        norm = " ".join(line.split())
        if f":{port} " not in norm:
            continue
        pids.extend(int(m) for m in re.findall(r"pid=(\d+)", norm))
    return pids


def process_cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            return fh.read().replace(b"\x00", b" ").decode("utf-8", "replace")
    except OSError:
        return ""


def _cmdline_contains(pid: int, terms: tuple[str, ...], *, process_cmdline_fn: Callable[[int], str]) -> bool:
    cmd = process_cmdline_fn(pid)
    return any(term in cmd for term in terms)


def is_dashboard_process(pid: int, *, process_cmdline_fn: Callable[[int], str] = process_cmdline) -> bool:
    """True only for a urirun host dashboard serve process."""
    return _cmdline_contains(pid, ("host dashboard serve",), process_cmdline_fn=process_cmdline_fn)


def is_scanner_process(pid: int, *, process_cmdline_fn: Callable[[int], str] = process_cmdline) -> bool:
    return _cmdline_contains(
        pid,
        (
            "urirun-service-scanner",
            "urirun-scanner",
            "urirun_service_scanner",
        ),
        process_cmdline_fn=process_cmdline_fn,
    )


def is_chat_process(pid: int, *, process_cmdline_fn: Callable[[int], str] = process_cmdline) -> bool:
    return _cmdline_contains(
        pid,
        (
            "urirun-service-chat",
            "urirun_service_chat",
        ),
        process_cmdline_fn=process_cmdline_fn,
    )


def is_android_node_process(pid: int, *, process_cmdline_fn: Callable[[int], str] = process_cmdline) -> bool:
    return _cmdline_contains(
        pid,
        (
            "urirun-service-android-node",
            "urirun-android-node",
            "urirun_service_android_node",
        ),
        process_cmdline_fn=process_cmdline_fn,
    )


def _signal_pids(pids: list[int], sig: int, *, port: int, emit: bool, emit_fn: Callable[..., Any],
                 kill_fn: Callable[[int, int], Any], event_prefix: str, event: str) -> list[int]:
    """Send `sig` to each pid (best-effort), emitting an event per kill; return the pids signalled."""
    killed: list[int] = []
    for pid in pids:
        try:
            kill_fn(pid, sig)
            killed.append(pid)
            if emit:
                emit_fn(
                    json.dumps({"event": f"{event_prefix}.{event}", "pid": pid, "port": port}),
                    flush=True,
                )
        except OSError:
            pass
    return killed


def free_port_from_matching_processes(
    port: int,
    *,
    force: bool,
    emit: bool,
    is_target: Callable[[int], bool],
    event_prefix: str,
    port_holder_pids_fn: Callable[[int], list[int]] = port_holder_pids,
    process_cmdline_fn: Callable[[int], str] = process_cmdline,
    kill_fn: Callable[[int, int], Any] = os.kill,
    getpid_fn: Callable[[], int] = os.getpid,
    sleep_fn: Callable[[float], Any] = time.sleep,
    time_fn: Callable[[], float] = time.time,
    emit_fn: Callable[..., Any] = print,
) -> dict:
    me = getpid_fn()

    def holders() -> list[int]:
        return [p for p in port_holder_pids_fn(port) if p != me]

    def targets() -> list[int]:
        return [p for p in holders() if force or is_target(p)]

    initial_holders = holders()
    initial_targets = targets()
    skipped = [p for p in initial_holders if p not in initial_targets]
    killed = _signal_pids(initial_targets, signal.SIGTERM, port=port, emit=emit, emit_fn=emit_fn,
                          kill_fn=kill_fn, event_prefix=event_prefix, event="replacing_old")
    if initial_targets:
        deadline = time_fn() + 8.0
        while time_fn() < deadline:
            if not targets():
                break
            sleep_fn(0.2)
        killed += _signal_pids(targets(), signal.SIGKILL, port=port, emit=emit, emit_fn=emit_fn,
                               kill_fn=kill_fn, event_prefix=event_prefix, event="force_killed_old")
        sleep_fn(0.3)

    remaining = holders()
    return _free_port_result(
        port=port, force=force, is_target=is_target,
        initial_holders=initial_holders, initial_targets=initial_targets,
        skipped=skipped, killed=killed, remaining=remaining,
        process_cmdline_fn=process_cmdline_fn,
    )


def _free_port_result(
    *,
    port: int,
    force: bool,
    is_target: Callable[[int], bool],
    initial_holders: list[int],
    initial_targets: list[int],
    skipped: list[int],
    killed: list[int],
    remaining: list[int],
    process_cmdline_fn: Callable[[int], str],
) -> dict:
    remaining_blockers = [p for p in remaining if force or is_target(p)]
    return {
        "ok": not remaining_blockers and (force or not skipped),
        "port": port,
        "force": bool(force),
        "holders": initial_holders,
        "targets": initial_targets,
        "skipped": [{"pid": p, "cmdline": process_cmdline_fn(p)} for p in skipped],
        "killed": sorted(set(killed)),
        "remaining": [{"pid": p, "cmdline": process_cmdline_fn(p)} for p in remaining],
    }


def free_port_from_old_dashboard(
    port: int,
    *,
    is_dashboard_process_fn: Callable[[int], bool] = is_dashboard_process,
    port_holder_pids_fn: Callable[[int], list[int]] = port_holder_pids,
    kill_fn: Callable[[int, int], Any] = os.kill,
    getpid_fn: Callable[[], int] = os.getpid,
    sleep_fn: Callable[[float], Any] = time.sleep,
    time_fn: Callable[[], float] = time.time,
    emit_fn: Callable[..., Any] = print,
) -> None:
    me = getpid_fn()

    def stale() -> list[int]:
        return [p for p in port_holder_pids_fn(port) if p != me and is_dashboard_process_fn(p)]

    targets = stale()
    for pid in targets:
        try:
            kill_fn(pid, signal.SIGTERM)
            emit_fn(
                json.dumps({"event": "urirun.host_dashboard.replacing_old", "pid": pid, "port": port}),
                flush=True,
            )
        except OSError:
            pass
    if not targets:
        return
    deadline = time_fn() + 8.0
    while time_fn() < deadline:
        if not stale():
            return
        sleep_fn(0.2)
    for pid in stale():
        try:
            kill_fn(pid, signal.SIGKILL)
        except OSError:
            pass
    sleep_fn(0.3)


# ─── Service lifecycle URI helpers ───────────────────────────────────────────

def canonical_service_uri(name: str, verb: str) -> str:
    """Return the canonical lifecycle URI for a named host service.

    ``verb`` is one of the four standard lifecycle verbs:
    ``command/start``, ``command/stop``, ``command/restart``, ``query/status``.
    """
    return f"dashboard://host/service/{name}/{verb}"


def service_lifecycle_uris(name: str) -> dict[str, str]:
    """Canonical start / stop / restart / status URIs for a named host service."""
    return {
        "start":   canonical_service_uri(name, "command/start"),
        "stop":    canonical_service_uri(name, "command/stop"),
        "restart": canonical_service_uri(name, "command/restart"),
        "status":  canonical_service_uri(name, "query/status"),
    }


def service_lifecycle_aliases(name: str) -> dict[str, str]:
    """Map all recognized legacy / alternate restart URIs to the canonical form.

    Covers the three patterns that accumulated before the ``dashboard://host/service/``
    namespace was standardized: bare dashboard scheme, ``service://host/``, and
    ``service://`` (no explicit host target).
    """
    canonical = canonical_service_uri(name, "command/restart")
    return {
        f"dashboard://host/{name}/command/restart": canonical,
        f"service://host/{name}/command/restart": canonical,
        f"service://{name}/command/restart": canonical,
    }


def service_status(
    port: int,
    is_process_fn: Callable[[int], bool],
    *,
    port_holder_pids_fn: Callable[[int], list[int]] = port_holder_pids,
    process_cmdline_fn: Callable[[int], str] = process_cmdline,
) -> dict:
    """Return the live status of a host service identified by its port + process classifier.

    Returns ``{ok, running, port, pids, pid_count}``.  ``running`` is True when AT LEAST
    one PID on the port matches the classifier — a different process holding the port is
    reported as ``running=False`` (port-busy, not the target service).
    """
    holders = port_holder_pids_fn(port)
    matching = [p for p in holders if is_process_fn(p)]
    running = bool(matching)
    return {
        "ok": True,
        "running": running,
        "port": port,
        "pids": matching,
        "pid_count": len(matching),
    }


def stop_service_pids(
    port: int,
    is_process_fn: Callable[[int], bool],
    *,
    port_holder_pids_fn: Callable[[int], list[int]] = port_holder_pids,
    process_cmdline_fn: Callable[[int], str] = process_cmdline,
    kill_fn: Callable[[int, int], Any] = os.kill,
) -> dict:
    """Send SIGTERM to all matching service PIDs on `port`.

    Returns ``{ok, stopped, pids}`` — ``stopped`` is the count of processes signalled.
    Not an error when no process was found (service was already stopped).
    """
    holders = port_holder_pids_fn(port)
    targets = [p for p in holders if is_process_fn(p)]
    signalled: list[int] = []
    for pid in targets:
        try:
            kill_fn(pid, signal.SIGTERM)
            signalled.append(pid)
        except OSError:
            pass
    return {"ok": True, "stopped": len(signalled), "pids": signalled}
