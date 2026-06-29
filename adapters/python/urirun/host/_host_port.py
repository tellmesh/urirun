from __future__ import annotations
import os
import time
from .service_control import (
    free_port_from_matching_processes as _free_port_from_matching_processes_impl,
    free_port_from_old_dashboard as _free_port_from_old_dashboard_impl,
    is_android_node_process as _is_android_node_process_impl,
    is_chat_process as _is_chat_process_impl,
    is_dashboard_process as _is_dashboard_process_impl,
    is_scanner_process as _is_scanner_process_impl,
    port_holder_pids as _port_holder_pids,
    process_cmdline as _process_cmdline,
)

# Patchable aliases for process-type is_target functions used by tests
_is_scanner_process = _is_scanner_process_impl
_is_chat_process = _is_chat_process_impl
_is_android_node_process = _is_android_node_process_impl


def _free_port_from_matching_processes(
    port: int,
    *,
    force: bool,
    emit: bool,
    is_target,
    event_prefix: str,
) -> dict:
    # Wrap is_target so it uses the patchable _process_cmdline global (monkeypatch-friendly).
    # All our is_target functions (is_scanner_process, is_chat_process, etc.) accept
    # process_cmdline_fn as a keyword argument.
    def _wrapped_is_target(pid: int) -> bool:
        return is_target(pid, process_cmdline_fn=_process_cmdline)

    return _free_port_from_matching_processes_impl(
        port,
        force=force,
        emit=emit,
        is_target=_wrapped_is_target,
        event_prefix=event_prefix,
        port_holder_pids_fn=_port_holder_pids,
        process_cmdline_fn=_process_cmdline,
        kill_fn=os.kill,
        getpid_fn=os.getpid,
        sleep_fn=time.sleep,
        time_fn=time.time,
        emit_fn=print,
    )


def _is_dashboard_process(pid: int) -> bool:
    """True only when pid is a urirun host dashboard serve process. Monkeypatch-friendly."""
    return _is_dashboard_process_impl(pid, process_cmdline_fn=_process_cmdline)


def _free_port_from_old_dashboard(port: int) -> None:
    """Before binding, terminate a previous dashboard instance still holding `port` so the new
    one can start cleanly. SAFETY: only kills processes whose cmdline is a urirun host
    dashboard serve — never an unrelated service that happens to own the port."""
    _free_port_from_old_dashboard_impl(
        port,
        is_dashboard_process_fn=_is_dashboard_process,
        port_holder_pids_fn=_port_holder_pids,
        kill_fn=os.kill,
        getpid_fn=os.getpid,
        sleep_fn=time.sleep,
        time_fn=time.time,
        emit_fn=print,
    )


def _free_port_from_old_scanner(port: int, *, force: bool = False, emit: bool = False) -> dict:
    """Free a scanner-owned port before rebinding it."""
    return _free_port_from_matching_processes(
        port,
        force=force,
        emit=emit,
        is_target=_is_scanner_process,
        event_prefix="urirun.service_scanner",
    )


def _free_port_from_old_chat(port: int, *, force: bool = False, emit: bool = False) -> dict:
    """Free a chat-service-owned port before rebinding it."""
    return _free_port_from_matching_processes(
        port,
        force=force,
        emit=emit,
        is_target=_is_chat_process,
        event_prefix="urirun.service_chat",
    )


def _free_port_from_old_android_node(port: int, *, force: bool = False, emit: bool = False) -> dict:
    """Free an android-node-service-owned port before rebinding it."""
    return _free_port_from_matching_processes(
        port,
        force=force,
        emit=emit,
        is_target=_is_android_node_process,
        event_prefix="urirun.service_android_node",
    )
