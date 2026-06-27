"""Classifying host→node dispatch — every call goes through here.

Instead of each call-site handling errors differently (chat, dashboard, sync,
task), a single ``run_node_uri`` classifies the failure using the shared
``RemediationClass`` taxonomy, optionally attempts auto-repair, and always
returns ``env["remediation"]`` so the caller has structured next-steps.

Design rules (from HOST_NODE_COMMUNICATION.md):
  • Default dry-run: auto-repair only mutates when execute=True.
  • Bounded: route-missing repair uses ensure_scheme which is itself bounded.
  • classify_error is pure (no I/O) and importable without a live node.
"""
from __future__ import annotations

from typing import Any, Callable

from urirun_contracts import Remediation, RemediationClass

# ──────────────────────────────────────────────────────────────────────────────
# Keyword / category sets (module-level constants — no per-call allocation)
# ──────────────────────────────────────────────────────────────────────────────

_KW_UNREACHABLE = frozenset((
    "connection refused", "timed out", "timeout", "unreachable",
    "no route to host", "nodename nor servname", "name or service not known",
    "failed to establish", "connection reset", "errno 111", "errno 110",
))
_CAT_UNREACHABLE = frozenset(("NETWORK_ERROR", "TIMEOUT"))
_TYP_UNREACHABLE = frozenset(("connectionerror", "timeouterror", "connecttimeout"))

_KW_AUTH = frozenset((
    "401", "403", "unauthorized", "forbidden", "invalid token",
    "auth", "enroll", "signature", "bad token",
))
_CAT_AUTH = frozenset(("AUTH_ERROR",))
_CODE_AUTH = frozenset(("e001", "e002"))

_KW_ROUTE = frozenset((
    "route not found", "no route", "connector_required", "connector required",
    "no connector", "missing connector", "scheme not found",
))
_CAT_ROUTE = frozenset(("NOT_FOUND",))
_TYP_ROUTE = frozenset(("route",))

_KW_VERSION = frozenset((
    "version", "allow list", "allow-list", "mismatch", "compat",
    "merge_mismatch", "deploy_allow",
))

_KW_DEGRADED = frozenset((
    "wayland", "portal", "screenshot failed", "capture failed",
    "display", "xdg-portal", "x11", "gdbus",
))
_CAT_DEGRADED = frozenset(("DEGRADED",))

_KW_PRECONDITION = frozenset((
    "precondition", "acquire", "grant", "permission denied",
    "allow access", "needs approval",
))
_CAT_PRECONDITION = frozenset(("PRECONDITION",))


def _any_kw(msg: str, kw: frozenset) -> bool:
    return any(k in msg for k in kw)


# ──────────────────────────────────────────────────────────────────────────────
# Matcher table — first match wins; evaluated in priority order
# ──────────────────────────────────────────────────────────────────────────────
# Each entry: (RemediationClass, matcher(msg, cat, typ, code, error) -> bool)

_MATCHERS: list[tuple[RemediationClass, Callable[[str, str, str, str, dict], bool]]] = [
    (
        RemediationClass.UNREACHABLE,
        lambda msg, cat, typ, code, _e: (
            _any_kw(msg, _KW_UNREACHABLE) or cat in _CAT_UNREACHABLE or typ in _TYP_UNREACHABLE
        ),
    ),
    (
        RemediationClass.UNAUTHENTICATED,
        lambda msg, cat, typ, code, _e: (
            _any_kw(msg, _KW_AUTH) or cat in _CAT_AUTH or code in _CODE_AUTH
        ),
    ),
    (
        RemediationClass.ROUTE_MISSING,
        lambda msg, cat, typ, code, error: (
            _any_kw(msg, _KW_ROUTE)
            or cat in _CAT_ROUTE
            or typ in _TYP_ROUTE
            or "connector_required" in str(error.get("type") or "")
        ),
    ),
    (
        RemediationClass.VERSION_SKEW,
        lambda msg, cat, typ, code, _e: _any_kw(msg, _KW_VERSION),
    ),
    (
        RemediationClass.DEGRADED_BACKEND,
        lambda msg, cat, typ, code, _e: _any_kw(msg, _KW_DEGRADED) or cat in _CAT_DEGRADED,
    ),
    (
        RemediationClass.PRECONDITION_UNMET,
        lambda msg, cat, typ, code, _e: _any_kw(msg, _KW_PRECONDITION) or cat in _CAT_PRECONDITION,
    ),
]


# ──────────────────────────────────────────────────────────────────────────────
# Remediation factories — one per class; called only after table match
# ──────────────────────────────────────────────────────────────────────────────

def _build_remediation(
    cls: RemediationClass,
    node: str,
    uri: str,
    scheme: str,
    error: dict,
) -> Remediation:
    if cls == RemediationClass.UNREACHABLE:
        return Remediation(
            cls=cls, node=node, raw_error=error, retry_uri=uri,
            human_action=f"Node '{node}' offline. Uruchom: urirun node serve --name {node}",
            command=f"urirun node serve --name {node}",
        )
    if cls == RemediationClass.UNAUTHENTICATED:
        return Remediation(
            cls=cls, node=node, raw_error=error, retry_uri=uri,
            auto_fix_uri=f"node://{node}/auth/command/resign",
            human_action=(
                f"Node '{node}' odrzucił token. Enroll: "
                f"uri-copy-id http://{node}:8765 -i ~/.ssh/id_ed25519 --enroll-token <PIN>"
            ),
            command=f"uri-copy-id http://{node}:8765 -i ~/.ssh/id_ed25519 --enroll-token <PIN>",
        )
    if cls == RemediationClass.ROUTE_MISSING:
        hint = str(error.get("connectorHint") or error.get("connector") or scheme or "")
        install_cmd = str(
            error.get("installCommand")
            or (f"pip install urirun-connector-{hint}" if hint else "")
        )
        return Remediation(
            cls=cls, node=node, raw_error=error, retry_uri=uri,
            auto_fix_uri=f"node://{node}/registry/command/ensure",
            auto_fix_payload={"scheme": scheme, "route": uri},
            human_action=f"Node '{node}' nie ma trasy '{uri}'. Zainstaluj: {install_cmd}",
            command=install_cmd,
        )
    if cls == RemediationClass.VERSION_SKEW:
        return Remediation(
            cls=cls, node=node, raw_error=error, retry_uri=uri,
            auto_fix_uri=f"node://{node}/registry/command/deploy-allow",
            human_action=f"Node '{node}' ma starą allow-listę. Zaktualizuj: pip install -U urirun na {node}",
            command="pip install -U urirun",
        )
    if cls == RemediationClass.DEGRADED_BACKEND:
        return Remediation(
            cls=cls, node=node, raw_error=error, retry_uri=uri,
            human_action=(
                f"Backend na '{node}' zdegradowany (capture/Wayland). "
                f"Zainstaluj grim lub uruchom node w sesji GUI."
            ),
            command="sudo dnf install grim  # lub: DISPLAY=:0 urirun node serve",
        )
    if cls == RemediationClass.PRECONDITION_UNMET:
        return Remediation(
            cls=cls, node=node, raw_error=error, retry_uri=uri,
            auto_fix_uri=f"ready://{node}/precondition/command/satisfy",
            auto_fix_payload={"uri": uri},
            human_action=f"Node '{node}' wymaga zgody. Zatwierdź na {node}, potem retry.",
        )
    return Remediation(
        cls=RemediationClass.UNKNOWN, node=node, raw_error=error, retry_uri=uri,
        human_action=f"Nieznana awaria na '{node}': {error.get('message', '')}",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Classification entry point (pure — no I/O)
# ──────────────────────────────────────────────────────────────────────────────

def classify_error(error: Any, *, node: str, uri: str = "") -> Remediation:
    """Map a raw envelope error to a ``RemediationClass`` + structured instructions.

    Pure function — no I/O.  CC ≤ 3: one early-return for missing node,
    one loop over the matcher table, one fallback.
    """
    if not isinstance(error, dict):
        error = {"message": str(error)}

    if not node:
        return Remediation(
            cls=RemediationClass.NO_NODE_URL, node=node, raw_error=error, retry_uri=uri,
            human_action="Brak URL dla node. Ustaw w panelu lub --node-url <name>=http://...",
            command="urirun node serve --name <name>",
        )

    msg = str(error.get("message") or "").lower()
    cat = str(error.get("category") or "").upper()
    typ = str(error.get("type") or "").lower()
    code = str(error.get("code") or "").lower()
    scheme = uri.split("://", 1)[0] if "://" in uri else ""

    for cls, matcher in _MATCHERS:
        if matcher(msg, cat, typ, code, error):
            return _build_remediation(cls, node, uri, scheme, error)

    return _build_remediation(RemediationClass.UNKNOWN, node, uri, scheme, error)


# ──────────────────────────────────────────────────────────────────────────────
# Dispatch
# ──────────────────────────────────────────────────────────────────────────────

def run_node_uri(
    node_url: str,
    uri: str,
    payload: dict | None = None,
    *,
    token: str | None = None,
    identity: str | None = None,
    timeout: float = 120.0,
    node_name: str = "",
    auto_repair: bool = False,
    execute: bool = False,
    dashboard_base: str = "",
) -> dict:
    """Classifying host→node dispatch.

    Executes ``uri`` on ``node_url``, classifies any failure through the
    ``RemediationClass`` taxonomy (via ``classify_error``), and attaches the
    result as ``env["remediation"]``.  When ``auto_repair=True`` AND
    ``execute=True``, attempts to repair ``ROUTE_MISSING`` via
    ``NodeClient.ensure_scheme`` and retries the call once.

    Dry-run invariant: ``auto_repair=True, execute=False`` populates
    ``env["repairAttempt"]`` with ``{"dryRun": True}`` without mutating remote state.
    """
    from urirun.host.fs_transfer import node_client as _node_client

    node = node_name or _node_from_url(node_url)

    if not node_url:
        r = Remediation(
            cls=RemediationClass.NO_NODE_URL, node=node,
            human_action=f"Brak URL dla node '{node}'.",
            retry_uri=uri, retry_payload=payload or {},
        )
        return {"ok": False, "remediation": r.to_dict(),
                "error": {"type": "NoNodeUrl", "message": r.human_action}}

    client = _node_client(node_url, token=token, identity=identity)
    try:
        env = client.run(uri, payload or {}, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        env = {"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}, "uri": uri}

    if env.get("ok"):
        return env

    error = _extract_error(env)
    r = classify_error(error, node=node, uri=uri)
    if dashboard_base:
        r.dashboard_url = f"{dashboard_base}?node={node}&fix={r.cls.value}"
    r.retry_uri = uri
    r.retry_payload = payload or {}

    repair_result: dict[str, Any] | None = None
    if auto_repair and r.auto_fix_uri:
        if not execute:
            repair_result = {"dryRun": True, "wouldCall": r.auto_fix_uri, "wouldPayload": r.auto_fix_payload}
        elif r.cls == RemediationClass.ROUTE_MISSING:
            repair_result, env = _try_route_repair(client, r, uri, payload, timeout)

    env["remediation"] = r.to_dict()
    if repair_result is not None:
        env["repairAttempt"] = repair_result
    return env


# ──────────────────────────────────────────────────────────────────────────────
# Helpers (private)
# ──────────────────────────────────────────────────────────────────────────────

def _node_from_url(node_url: str) -> str:
    if not node_url:
        return ""
    host = node_url.split("://", 1)[-1].split("/")[0]
    return host.split(":")[0]


def _extract_error(env: dict) -> dict:
    error = env.get("error") or (env.get("envelope") or {}).get("error") or {}
    if isinstance(error, str):
        return {"message": error}
    return error if isinstance(error, dict) else {}


def _try_route_repair(
    client: Any, r: Remediation, uri: str, payload: dict | None, timeout: float
) -> tuple[dict, dict]:
    """Attempt ensure_scheme repair; retry the original call if it succeeds."""
    scheme = r.auto_fix_payload.get("scheme") or uri.split("://", 1)[0]
    route = r.auto_fix_payload.get("route") or uri
    try:
        ensured = client.ensure_scheme(scheme, route=route)
        if ensured.get("ok"):
            retry_env = client.run(uri, payload or {}, timeout=timeout)
            if retry_env.get("ok"):
                retry_env["repairedVia"] = r.auto_fix_uri
                retry_env["remediation"] = r.to_dict()
                return ensured, retry_env
        return ensured, {}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}, {}
