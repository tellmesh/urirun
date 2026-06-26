# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""urirun v2 service dispatch - call a URI implemented by a remote worker.

In a polyglot deployment each worker implements its own URI resources natively
(Python, Node.js, shell, ...) and exposes `POST /run`. From a coordinator's point
of view those URIs are *services*: it looks the URI up in the registry, validates
the payload against that route's JSON Schema, then POSTs to the worker.

This makes that the library's job rather than bespoke orchestrator code, and it is
deliberately **adapter-agnostic**: it does not matter how the worker labels the
route (`local-service`, `command`, ...) - to the coordinator every worker URI is
reached over HTTP.

```python
from urirun.runtime import v2_service
env = v2_service.call("python://python-worker/text/normalize", {"text": "Hi"}, registry)
```

The target host resolves to ``http://<target>:8080`` by default, overridable with
``URI_SERVICE_MAP`` (the same env the docker_uri_flow orchestrator uses).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from jsonschema import exceptions as jsonschema_exceptions

from urirun.runtime import _registry as reglib, v2

DEFAULT_PORT = 8080


def service_base(target: str, uri: str | None = None) -> str:
    mapping = os.getenv("URI_SERVICE_MAP")
    if mapping:
        table = json.loads(mapping)
        if uri and uri in table:
            return str(table[uri]).rstrip("/")
        if target in table:
            return str(table[target]).rstrip("/")
    return f"http://{target}:{DEFAULT_PORT}"


def _post(url: str, body: dict, timeout: float):
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    # opt-in auth for nodes started with --require-run-auth (token mode). No env → no
    # header → unchanged behaviour against open nodes.
    identity = os.getenv("URIRUN_RUN_IDENTITY")
    token = os.getenv("URIRUN_RUN_TOKEN")
    if identity:
        from urirun.node import keyauth  # noqa: PLC0415 — lazy: only when URIRUN_RUN_IDENTITY is set
        headers.update(keyauth.sign(os.path.expanduser(identity), keyauth.PURPOSE_RUN, data))
    elif token:
        headers["X-Urirun-Token"] = token
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), response.status
    except urllib.error.HTTPError as err:
        return json.loads(err.read().decode("utf-8") or "{}"), err.code


def call(uri: str, payload: dict | None = None, registry: dict | None = None, mode: str = "execute",
         timeout: float = 30.0, validate: bool = True) -> dict:
    descriptor = reglib.parse_uri(uri)
    translation = reglib.translate(descriptor)
    payload = payload or {}
    envelope = {"uri": descriptor["normalized"], "mode": mode, "target": translation["target"]}

    route_entry = None
    if registry is not None:
        try:
            route_entry = reglib.resolve_route(translation, registry)
        except KeyError:
            envelope["ok"] = False
            envelope["error"] = {"type": "registry", "category": "NOT_FOUND", "message": f"route not found: {descriptor['normalized']}"}
            return envelope

    if validate and route_entry is not None:
        try:
            v2.validate_input(route_entry, descriptor, translation, payload)
        except (jsonschema_exceptions.ValidationError, jsonschema_exceptions.SchemaError) as err:
            envelope["ok"] = False
            envelope["error"] = {"type": "schema", "message": err.message}
            return envelope

    url = f"{service_base(translation['target'], descriptor['normalized'])}/run"
    envelope["url"] = url
    body = {"uri": descriptor["normalized"], "payload": payload}

    if mode != "execute":
        envelope["ok"] = True
        envelope["simulated"] = True
        envelope["request"] = body
        return envelope

    try:
        data, status = _post(url, body, timeout)
    except OSError as err:
        envelope["ok"] = False
        envelope["error"] = {"type": "transport", "message": str(err)}
        return envelope

    envelope["status"] = status
    envelope["response"] = data
    envelope["result"] = data.get("result")
    envelope["ok"] = bool(data.get("ok", status < 400))
    return envelope


def make_dispatch(registry: dict | None, mode: str, fallback=None):
    """Return a two-tier ``dispatch(uri, payload)`` callable.

    Tier 1 — mesh (v2_service.call): fast, covers served nodes in *registry*.
    Tier 2 — *fallback(uri, payload)*: called only when Tier 1 returns
    ``error.category == NOT_FOUND``.  Pass ``None`` to skip Tier 2.

    This is the canonical factory for dispatch callables that flow.execute_flow,
    twin connector handlers, and the dashboard all share — a single seam to swap
    the routing strategy (e.g. inject a test stub or a remote node transport)
    without touching the call sites."""
    def _dispatch(uri: str, payload: dict | None = None) -> dict | None:
        r = call(uri, payload or {}, registry or {}, mode=mode)
        if r and r.get("ok"):
            return r
        _err = (r.get("error") or {})
        # Trigger in-process fallback for any "route not found" signal:
        # - category == "NOT_FOUND": set by v2_service.call on local registry miss
        # - type == "registry": set by node HTTP responses when the served node
        #   doesn't own that route (no category field in that case)
        if fallback is not None and (
            _err.get("category") == "NOT_FOUND"
            or _err.get("type") == "registry"
        ):
            fb = fallback(uri, payload or {})
            return fb if fb is not None else r
        return r
    return _dispatch
