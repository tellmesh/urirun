"""Phone-scanner chat client.

Scanner prompt detection and result shaping live in ``scanner_bridge`` /
``urirun_connector_scanner``. This module owns the chat-specific action queue
and message emission so the main chat orchestrator does not hardcode scanner
page URI details.
"""
from __future__ import annotations

import os
from typing import Any

from .scanner_bridge import (
    is_autonomous_scanner_prompt,
    is_camera_start_prompt,
    is_phone_scanner_prompt,
    scanner_flow_result,
    torch_enabled_from_prompt,
)
from ._chat_message import chat_message


def chat_ask_phone_scanner(
    project: str,
    db: str | None,
    config: str | None,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    prompt: str,
    execute: bool,
    selected_nodes: list[str],
    selected_targets: list[str],
    deps: Any,
) -> dict:
    """Handle phone-scanner chat requests (start scanner, queue camera/torch actions)."""
    service = deps.ensure_phone_scanner_fn(
        project, db, config=config, node_urls=node_urls, token=token, identity=identity,
    )
    queued_camera: dict | None = None
    queued_torch: dict | None = None
    camera_click_uri = "scanner://page/ui/button/start-camera/command/click"
    camera_autonomous_uri = "scanner://page/camera/command/autonomous"
    torch_click_uri = "scanner://page/ui/button/torch/command/click"
    torch_enabled = torch_enabled_from_prompt(prompt)
    autonomous_scan = is_autonomous_scanner_prompt(prompt)
    camera_action_uri = camera_autonomous_uri if autonomous_scan else camera_click_uri
    camera_payload = {
        "target": "scanner",
        "startBest": torch_enabled is None,
        "auto": bool(autonomous_scan),
        "count": int(os.environ.get("URIRUN_PHONE_SCANNER_BEST_COUNT", "6")),
        "minScore": float(os.environ.get("URIRUN_PHONE_SCANNER_MIN_SCORE", "45")),
        "interval": float(os.environ.get("URIRUN_PHONE_SCANNER_INTERVAL", "3")),
    }
    if autonomous_scan or is_camera_start_prompt(prompt) or torch_enabled is not None:
        queued_camera = deps.page_action_enqueue_fn(
            db, target="scanner", uri=camera_action_uri, payload=camera_payload,
            mode="execute", source="chat",
        )
        deps.add_chat_message_fn(db, chat_message(
            "system",
            "Autonomous scanner queued for the open scanner page. Open the scanner URL and accept the browser camera permission if prompted."
            if autonomous_scan else
            "Camera start queued for the open scanner page. Open the scanner URL and accept the browser camera permission if prompted.",
            detail={
                "uri": camera_action_uri,
                "selectedTargets": ["service:phone-scanner"],
                "queued": queued_camera,
                "scannerUrl": service.get("url"),
                "autonomous": bool(autonomous_scan),
            },
        ))
    if torch_enabled is not None:
        queued_torch = deps.page_action_enqueue_fn(
            db, target="scanner", uri=torch_click_uri,
            payload={"target": "scanner", "enabled": bool(torch_enabled)},
            mode="execute", source="chat",
        )
        deps.add_chat_message_fn(db, chat_message(
            "system",
            f"Camera light {'on' if torch_enabled else 'off'} queued for the open scanner page.",
            detail={
                "uri": torch_click_uri,
                "selectedTargets": ["service:phone-scanner"],
                "enabled": bool(torch_enabled),
                "queued": queued_torch,
                "scannerUrl": service.get("url"),
            },
        ))
    result = scanner_flow_result(
        service, autonomous_scan, camera_action_uri, camera_payload,
        torch_click_uri, torch_enabled, queued_camera, queued_torch,
        prompt, selected_nodes, selected_targets,
    )
    try:
        deps.host_db_fn().add_log(db, "chat", "ask", {
            "prompt": prompt,
            "execute": True,
            "ok": result.get("ok"),
            "selectedNodes": selected_nodes,
            "selectedTargets": selected_targets,
            "generator": result.get("generator"),
            "timeline": result.get("timeline") or [],
        })
    except Exception:
        pass
    return result
