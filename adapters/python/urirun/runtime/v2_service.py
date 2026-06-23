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
from urirun import v2_service
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

from urirun import _registry as reglib, v2

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
    token = os.getenv("URIRUN_RUN_TOKEN")
    if token:
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
            envelope["error"] = {"type": "registry", "message": f"route not found: {descriptor['normalized']}"}
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
