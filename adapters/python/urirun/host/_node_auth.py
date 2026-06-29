from __future__ import annotations

import json
import os
import re
from typing import Any


def node_api_slug(value: Any, fallback: str) -> str:
    raw = str(value or "").strip().lower()
    slug = re.sub(r"[^a-z0-9_-]+", "-", raw).strip("-")
    return slug or fallback


def node_api_secret_ref(name: str, api_id: str) -> str:
    account = f"{node_api_slug(name, 'node')}/{node_api_slug(api_id, 'api')}"
    return f"secret://keyring/urirun-node-api/{account}#credential"


def store_node_api_secret(name: str, api_id: str, secret: str) -> tuple[str | None, str | None]:
    if not secret:
        return None, None
    try:
        import keyring
        account = f"{node_api_slug(name, 'node')}/{node_api_slug(api_id, 'api')}"
        keyring.set_password("urirun-node-api", account, secret)
        return node_api_secret_ref(name, api_id), None
    except Exception as exc:  # noqa: BLE001
        return None, f"could not store API credential securely (keyring): {exc}"


def extract_raw_secret(auth_data: dict, api: dict) -> str | None:
    return (
        auth_data.get("token")
        or auth_data.get("apiKey")
        or auth_data.get("password")
        or auth_data.get("secret")
        or api.get("token")
        or api.get("apiKey")
        or api.get("password")
        or api.get("secret")
    )


def extract_secret_ref(auth_data: dict, api: dict) -> str | None:
    return (
        auth_data.get("secretRef")
        or auth_data.get("ref")
        or auth_data.get("credentialRef")
        or api.get("secretRef")
        or api.get("credentialRef")
    )


def build_auth_extra_fields(auth_data: dict, api: dict) -> dict:
    extra: dict = {}
    for key in ("username", "header", "headerName", "queryParam", "scheme", "tokenUrl", "clientIdRef"):
        value = auth_data.get(key) if key in auth_data else api.get(key)
        if value not in (None, ""):
            extra[key] = value
    return extra


def normalize_node_api_auth(name: str, api_id: str, api: dict, auth: Any) -> tuple[dict, str | None]:
    auth_data = auth if isinstance(auth, dict) else {}
    raw_secret = extract_raw_secret(auth_data, api)
    secret_ref = extract_secret_ref(auth_data, api)
    auth_type = str(
        auth_data.get("type")
        or api.get("authType")
        or ("bearer" if raw_secret else ("ref" if secret_ref else "none"))
    ).strip().lower()
    if raw_secret:
        secret_ref, error = store_node_api_secret(name, api_id, str(raw_secret))
        if error:
            return {}, error
    if auth_type in {"", "none", "no", "false"} and not secret_ref:
        return {}, None
    out: dict = {"type": auth_type or "ref"}
    if secret_ref:
        out["secretRef"] = str(secret_ref)
    out.update(build_auth_extra_fields(auth_data, api))
    return out, None


def default_api_items(url: str, kind: str, payload: dict) -> list[dict]:
    return [{
        "id": "default",
        "label": "default API",
        "url": url,
        "kind": payload.get("protocol") or payload.get("apiKind") or ("web" if kind == "device" else "http"),
        "auth": payload.get("auth") if isinstance(payload.get("auth"), dict) else {},
    }]


def api_item_fields(item: dict, url: str, index: int) -> tuple[str, str, str]:
    api_id = node_api_slug(item.get("id") or item.get("name") or item.get("role"), f"api-{index}")
    api_url = str(item.get("url") or item.get("endpoint") or item.get("baseUrl") or url).strip()
    api_kind = str(item.get("kind") or item.get("protocol") or item.get("transport") or "http").strip().lower()
    return api_id, api_url, api_kind


def normalize_api_item(name: str, url: str, index: int, item: dict,
                       fallback_auth: Any) -> tuple[dict | None, str | None]:
    api_id, api_url, api_kind = api_item_fields(item, url, index)
    if not api_url:
        return None, None
    api: dict = {"id": api_id, "kind": api_kind, "url": api_url}
    for key in ("label", "role", "openapi", "basePath", "mount", "description"):
        if item.get(key) not in (None, ""):
            api[key] = item[key]
    auth, error = normalize_node_api_auth(name, api_id, item, item.get("auth") or fallback_auth)
    if error:
        return None, error
    if auth:
        api["auth"] = auth
    return api, None


def normalize_node_apis(name: str, url: str, kind: str | None, payload: dict) -> tuple[list[dict], str | None]:
    raw = payload.get("apis") or payload.get("interfaces") or payload.get("api")
    if isinstance(raw, dict):
        raw_items: list = [raw]
    elif isinstance(raw, list):
        raw_items = raw
    else:
        raw_items = []
    if not raw_items and kind in {"api", "device"}:
        raw_items = default_api_items(url, kind, payload)
    apis: list[dict] = []
    fallback_auth = payload.get("auth")
    for index, item in enumerate(raw_items, 1):
        if not isinstance(item, dict):
            continue
        api, error = normalize_api_item(name, url, index, item, fallback_auth)
        if error:
            return [], error
        if api is not None:
            apis.append(api)
    return apis, None
