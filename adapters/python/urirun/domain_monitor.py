"""Domain monitoring URI runtime.

This module intentionally stops at observe/plan:
- HTTP and DNS are read-only checks,
- screenshots are artifacts,
- DNS mismatch creates a review ticket, never an apply action.
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def now_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return sorted({str(item) for item in value})
    return sorted({item.strip() for item in str(value).split(",") if item.strip()})


def _domain(target: str, payload: dict) -> str:
    return str(payload.get("domain") or target)


def default_url(domain: str) -> str:
    return domain if domain.startswith(("http://", "https://")) else f"https://{domain}"


def http_status(url: str, timeout: float = 10.0, expected_status: int | None = None) -> dict:
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": "urirun-domain-monitor/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            ok = status == expected_status if expected_status is not None else status < 400
            return {
                "ok": ok,
                "url": url,
                "status": status,
                "elapsedMs": int((time.monotonic() - started) * 1000),
                "headers": dict(response.headers.items()),
            }
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        ok = status == expected_status if expected_status is not None else status < 400
        return {
            "ok": ok,
            "url": url,
            "status": status,
            "elapsedMs": int((time.monotonic() - started) * 1000),
            "error": str(exc),
        }
    except OSError as exc:
        return {
            "ok": False,
            "url": url,
            "status": None,
            "elapsedMs": int((time.monotonic() - started) * 1000),
            "error": str(exc),
        }


def dns_records(domain: str, record_types: list[str] | None = None) -> dict:
    requested = {item.upper() for item in (record_types or ["A", "AAAA"])}
    records = {"A": [], "AAAA": []}
    try:
        infos = socket.getaddrinfo(domain, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        return {"ok": False, "domain": domain, "records": records, "error": str(exc), "provider": "system-resolver"}

    for family, _kind, _proto, _canon, sockaddr in infos:
        if family == socket.AF_INET and "A" in requested:
            records["A"].append(sockaddr[0])
        elif family == socket.AF_INET6 and "AAAA" in requested:
            records["AAAA"].append(sockaddr[0])
    normalized = {key: sorted(set(value)) for key, value in records.items() if key in requested}
    return {"ok": True, "domain": domain, "records": normalized, "provider": "system-resolver"}


def expected_records(payload: dict) -> dict[str, list[str]]:
    expected = payload.get("expected_records") or payload.get("expected") or {}
    if not isinstance(expected, dict):
        expected = {"A": _list(expected)}
    if payload.get("expected_a") is not None:
        expected["A"] = _list(payload.get("expected_a"))
    if payload.get("expected_aaaa") is not None:
        expected["AAAA"] = _list(payload.get("expected_aaaa"))
    return {str(key).upper(): _list(value) for key, value in expected.items() if _list(value)}


def dns_mismatches(current: dict, expected: dict[str, list[str]]) -> list[dict]:
    records = current.get("records") or {}
    mismatches = []
    for record_type, expected_values in expected.items():
        actual_values = _list(records.get(record_type))
        if actual_values != expected_values:
            mismatches.append({"type": record_type, "expected": expected_values, "actual": actual_values})
    return mismatches


def capture_screenshot_artifact(
    *,
    db: str | None,
    domain: str,
    url: str,
    out_dir: str | None = None,
    reason: str = "failure",
    meta: dict | None = None,
) -> dict:
    from urirun import host_db

    timestamp = now_id()
    directory = Path(out_dir or "~/.urirun/artifacts/screenshots").expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{domain}-{timestamp}.screenshot.json"
    content = {"domain": domain, "url": url, "reason": reason, "createdAt": timestamp, "meta": meta or {}}
    path.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifact_uri = f"artifact://host/screenshot/{domain}/{timestamp}"
    return host_db.register_artifact(db, "screenshot", artifact_uri, str(path), content)


def create_dns_repair_ticket(
    *,
    project: str,
    domain: str,
    current: dict,
    expected: dict,
    mismatches: list[dict],
) -> dict:
    from urirun import planfile_adapter

    prompt = (
        f"Review DNS mismatch for {domain}. "
        f"Expected={json.dumps(expected, sort_keys=True)} "
        f"Current={json.dumps(current.get('records') or {}, sort_keys=True)}. "
        "Prepare a safe DNS plan only; do not apply changes automatically."
    )
    return planfile_adapter.create_ticket(
        project,
        {
            "name": f"Review DNS mismatch: {domain}",
            "description": prompt,
            "priority": "high",
            "labels": ["domain", "dns", "repair", "review"],
            "queue": "review",
            "executor_kind": "uri-flow",
            "executor_mode": "interactive",
            "executor_handler": "dns://host/records/command/plan",
            "prompt": prompt,
            "source_tool": "urirun-domain-monitor",
            "source_context": {
                "domain": domain,
                "current": current,
                "expected": expected,
                "mismatches": mismatches,
            },
        },
    )


def check_domain(
    *,
    domain: str,
    url: str | None = None,
    expected: dict[str, list[str]] | None = None,
    db: str | None = None,
    project: str | None = None,
    execute: bool = False,
    timeout: float = 10.0,
    screenshot_when: str = "failure",
    screenshot_dir: str | None = None,
    create_repair_ticket: bool = True,
) -> dict:
    from urirun import host_db

    target_url = url or default_url(domain)
    http = http_status(target_url, timeout=timeout)
    dns = dns_records(domain, sorted((expected or {"A": []}).keys()) if expected else None)
    mismatches = dns_mismatches(dns, expected or {})
    ok = bool(http.get("ok")) and bool(dns.get("ok")) and not mismatches
    result: dict[str, Any] = {
        "ok": ok,
        "domain": domain,
        "url": target_url,
        "http": http,
        "dns": dns,
        "dnsMismatches": mismatches,
        "executed": execute,
        "artifacts": [],
        "tickets": [],
    }

    if not execute:
        return result

    check = host_db.add_check(
        db,
        domain,
        f"monitor://{domain}/domain/command/check",
        "ok" if ok else "failed",
        {"http": http, "dns": dns, "dnsMismatches": mismatches},
    )
    result["check"] = check

    if not ok and screenshot_when in {"failure", "always"}:
        result["artifacts"].append(
            capture_screenshot_artifact(
                db=db,
                domain=domain,
                url=target_url,
                out_dir=screenshot_dir,
                reason="failure",
                meta={"http": http, "dns": dns, "dnsMismatches": mismatches},
            )
        )
    elif screenshot_when == "always":
        result["artifacts"].append(capture_screenshot_artifact(db=db, domain=domain, url=target_url, out_dir=screenshot_dir, reason="manual"))

    if mismatches and project and create_repair_ticket:
        result["tickets"].append(create_dns_repair_ticket(project=project, domain=domain, current=dns, expected=expected or {}, mismatches=mismatches))

    result["log"] = host_db.add_log(
        db,
        "daily",
        "daily_domain_check.finished",
        {"domain": domain, "ok": ok, "httpStatus": http.get("status"), "dnsMismatches": mismatches},
    )
    return result


def run_daily(
    *,
    db: str | None,
    project: str | None,
    execute: bool,
    dataset: str = "domains",
    limit: int = 50,
    screenshot_when: str = "failure",
    screenshot_dir: str | None = None,
) -> dict:
    from urirun import host_db

    try:
        records = host_db.search_records(db, "", dataset=dataset, limit=limit)
    except ValueError:
        records = []
    results = []
    for record in records:
        data = record.get("data") or {}
        domain = data.get("domain") or record.get("key")
        if not domain:
            continue
        results.append(
            check_domain(
                domain=str(domain),
                url=data.get("url"),
                expected=expected_records(data),
                db=db,
                project=project,
                execute=execute,
                timeout=float(data.get("timeout", 10.0)),
                screenshot_when=screenshot_when,
                screenshot_dir=screenshot_dir,
            )
        )
    return {"ok": all(item.get("ok") for item in results), "count": len(results), "results": results, "executed": execute}


def _db(ctx: dict, payload: dict) -> str | None:
    return payload.get("db") or (ctx["routeEntry"].get("config") or {}).get("db")


def _project(ctx: dict, payload: dict) -> str | None:
    return payload.get("project") or (ctx["routeEntry"].get("config") or {}).get("project")


def _screenshot_dir(ctx: dict, payload: dict) -> str | None:
    return payload.get("screenshot_dir") or (ctx["routeEntry"].get("config") or {}).get("screenshot_dir")


def _provider(ctx: dict, payload: dict) -> str:
    return str(payload.get("provider") or (ctx["routeEntry"].get("config") or {}).get("provider") or "").lower()


def run_uri_route(ctx: dict, execute: bool) -> dict:
    from urirun import host_db

    payload = dict(ctx.get("payload") or {})
    descriptor = ctx["descriptor"]
    target = ctx["target"]
    resource = ctx["translation"]["resource"]
    operation = ctx["translation"]["operation"]
    args = ctx["translation"]["args"]
    action = args[0] if args else operation
    package = descriptor["package"]

    if package == "monitor" and resource == "http" and operation == "query" and action == "status":
        domain = _domain(target, payload)
        return {"type": "domain-monitor", "http": http_status(payload.get("url") or default_url(domain), timeout=float(payload.get("timeout", 10.0)), expected_status=payload.get("expected_status"))}

    if package == "dns" and resource == "records" and operation == "query" and action == "current":
        domain = _domain(target, payload)
        if _provider(ctx, payload) == "namecheap":
            from urirun import namecheap_dns

            return namecheap_dns.run_uri_route(ctx, execute)
        return {"type": "domain-monitor", "dns": dns_records(domain, _list(payload.get("record_types")) or None)}

    if package == "dns" and resource == "records" and operation == "query" and action == "expected":
        return {"type": "domain-monitor", "expectedRecords": expected_records(payload)}

    if package == "dns" and resource == "records" and operation == "command" and action in {"plan", "backup", "apply"}:
        from urirun import namecheap_dns

        return namecheap_dns.run_uri_route(ctx, execute)

    if package == "browser" and resource == "page" and operation == "command" and action == "screenshot":
        domain = _domain(target, payload)
        url = payload.get("url") or default_url(domain)
        if not execute:
            return {"type": "domain-monitor", "simulated": True, "artifactKind": "screenshot", "url": url}
        return {
            "type": "domain-monitor",
            "artifact": capture_screenshot_artifact(db=_db(ctx, payload), domain=domain, url=url, out_dir=_screenshot_dir(ctx, payload), reason=payload.get("reason", "manual"), meta=payload.get("meta")),
        }

    if package == "log" and operation == "command" and action == "write":
        if not execute:
            return {"type": "domain-monitor", "simulated": True, "stream": payload.get("stream") or resource, "event": payload.get("event")}
        return {"type": "domain-monitor", "log": host_db.add_log(_db(ctx, payload), payload.get("stream") or resource, payload["event"], payload.get("detail"))}

    if package == "log" and operation == "query":
        return {"type": "domain-monitor", "logs": host_db.recent_logs(_db(ctx, payload), stream=payload.get("stream") or resource, limit=int(payload.get("limit", 20)))}

    if package == "flow" and resource == "domain" and operation == "command" and action == "check":
        domain = str(payload.get("domain") or target)
        return {
            "type": "domain-monitor",
            "flow": "domain-check",
            **check_domain(
                domain=domain,
                url=payload.get("url"),
                expected=expected_records(payload),
                db=_db(ctx, payload),
                project=_project(ctx, payload),
                execute=execute,
                timeout=float(payload.get("timeout", 10.0)),
                screenshot_when=payload.get("screenshot_when", "failure"),
                screenshot_dir=_screenshot_dir(ctx, payload),
                create_repair_ticket=payload.get("create_repair_ticket", True) is not False,
            ),
        }

    if package == "flow" and resource == "daily" and operation == "command" and action == "run":
        return {
            "type": "domain-monitor",
            "flow": "daily-domain-run",
            **run_daily(
                db=_db(ctx, payload),
                project=_project(ctx, payload),
                execute=execute,
                dataset=payload.get("dataset", "domains"),
                limit=int(payload.get("limit", 50)),
                screenshot_when=payload.get("screenshot_when", "failure"),
                screenshot_dir=_screenshot_dir(ctx, payload),
            ),
        }

    raise ValueError(f"unsupported domain monitor URI: {descriptor['normalized']}")
