"""Safe Namecheap DNS plan/apply adapter.

Namecheap ``setHosts`` replaces the host record set.  This adapter therefore
requires a full desired record set, a backup artifact and explicit confirmation
before applying.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from urirun import domain_monitor


API_PROD = "https://api.namecheap.com/xml.response"
API_SANDBOX = "https://api.sandbox.namecheap.com/xml.response"
SUPPORTED_RECORD_KEYS = ("Name", "Type", "Address", "TTL", "MXPref", "EmailType", "Flag", "Tag")


def split_domain(domain: str) -> tuple[str, str]:
    if "." not in domain:
        raise ValueError(f"domain must include a TLD: {domain}")
    sld, tld = domain.rsplit(".", 1)
    return sld, tld


def env_name(profile: str | None, name: str) -> str:
    if profile:
        return f"NAMECHEAP_{profile.upper()}_{name}"
    return f"NAMECHEAP_{name}"


def config_from_env(profile: str | None = None, env: dict | None = None) -> dict:
    env = env or os.environ
    sandbox = env.get(env_name(profile, "SANDBOX"), env.get("NAMECHEAP_SANDBOX", "false")).lower() in {"1", "true", "yes", "on"}
    config = {
        "api_user": env.get(env_name(profile, "API_USER")) or env.get("NAMECHEAP_API_USER"),
        "api_key": env.get(env_name(profile, "API_KEY")) or env.get("NAMECHEAP_API_KEY"),
        "username": env.get(env_name(profile, "USERNAME")) or env.get("NAMECHEAP_USERNAME"),
        "client_ip": env.get(env_name(profile, "CLIENT_IP")) or env.get("NAMECHEAP_CLIENT_IP"),
        "sandbox": sandbox,
        "endpoint": env.get(env_name(profile, "ENDPOINT")) or env.get("NAMECHEAP_ENDPOINT") or (API_SANDBOX if sandbox else API_PROD),
        "profile": profile,
    }
    missing = [key for key in ("api_user", "api_key", "username", "client_ip") if not config.get(key)]
    if missing:
        raise ValueError(f"missing Namecheap env keys: {', '.join(missing)}")
    return config


def auth_params(config: dict, command: str, domain: str) -> dict[str, str]:
    sld, tld = split_domain(domain)
    return {
        "ApiUser": config["api_user"],
        "ApiKey": config["api_key"],
        "UserName": config["username"],
        "ClientIp": config["client_ip"],
        "Command": command,
        "SLD": sld,
        "TLD": tld,
    }


def request_api(config: dict, command: str, domain: str, params: dict | None = None, method: str = "GET") -> str:
    body = {**auth_params(config, command, domain), **(params or {})}
    encoded = urllib.parse.urlencode(body).encode("utf-8")
    if method.upper() == "POST":
        request = urllib.request.Request(config["endpoint"], data=encoded, method="POST")
    else:
        request = urllib.request.Request(f"{config['endpoint']}?{encoded.decode('utf-8')}", method="GET")
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_api_xml(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    status = root.attrib.get("Status")
    errors = []
    hosts = []
    set_success = None
    for elem in root.iter():
        name = _strip_ns(elem.tag)
        if name == "Error":
            errors.append({"number": elem.attrib.get("Number"), "message": (elem.text or "").strip()})
        elif name.lower() == "host":
            hosts.append(
                normalize_record(
                    {
                        "Name": elem.attrib.get("Name", "@"),
                        "Type": elem.attrib.get("Type", ""),
                        "Address": elem.attrib.get("Address", ""),
                        "TTL": elem.attrib.get("TTL"),
                        "MXPref": elem.attrib.get("MXPref"),
                    }
                )
            )
        elif name == "DomainDNSSetHostsResult":
            set_success = elem.attrib.get("IsSuccess", "").lower() == "true"
    ok = status == "OK" and not errors
    return {"ok": ok, "status": status, "errors": errors, "records": hosts, "setSuccess": set_success}


def normalize_record(record: dict) -> dict:
    output = {
        "Name": str(record.get("Name") or record.get("name") or "@"),
        "Type": str(record.get("Type") or record.get("type") or "").upper(),
        "Address": str(record.get("Address") or record.get("address") or ""),
    }
    ttl = record.get("TTL", record.get("ttl"))
    mxpref = record.get("MXPref", record.get("mxpref", record.get("mx_pref")))
    if ttl not in (None, ""):
        output["TTL"] = str(ttl)
    if mxpref not in (None, ""):
        output["MXPref"] = str(mxpref)
    for key in ("EmailType", "Flag", "Tag"):
        value = record.get(key, record.get(key.lower()))
        if value not in (None, ""):
            output[key] = str(value)
    if not output["Type"] or not output["Address"]:
        raise ValueError(f"record requires Type and Address: {record}")
    return output


def normalize_records(records: list[dict] | None) -> list[dict]:
    return sorted((normalize_record(record) for record in (records or [])), key=record_key)


def record_key(record: dict) -> tuple:
    return (
        record.get("Name", "@"),
        record.get("Type", ""),
        record.get("Address", ""),
        record.get("MXPref", ""),
        record.get("TTL", ""),
        record.get("EmailType", ""),
        record.get("Flag", ""),
        record.get("Tag", ""),
    )


def record_identity(record: dict) -> tuple:
    return (record.get("Name", "@"), record.get("Type", ""), record.get("Address", ""), record.get("MXPref", ""))


def merge_records(current: list[dict], ensure: list[dict] | None = None, remove: list[dict] | None = None) -> list[dict]:
    records = {record_identity(record): record for record in normalize_records(current)}
    for record in normalize_records(remove):
        records.pop(record_identity(record), None)
    for record in normalize_records(ensure):
        records[record_identity(record)] = record
    return sorted(records.values(), key=record_key)


def diff_records(current: list[dict], desired: list[dict]) -> dict:
    current_map = {record_key(record): record for record in normalize_records(current)}
    desired_map = {record_key(record): record for record in normalize_records(desired)}
    added = [desired_map[key] for key in sorted(desired_map.keys() - current_map.keys())]
    removed = [current_map[key] for key in sorted(current_map.keys() - desired_map.keys())]
    return {"changed": bool(added or removed), "added": added, "removed": removed}


def desired_from_payload(current: list[dict], payload: dict) -> list[dict]:
    if payload.get("desired_records") is not None:
        return normalize_records(payload.get("desired_records"))
    return merge_records(current, ensure=payload.get("ensure_records"), remove=payload.get("remove_records"))


def current_records(domain: str, payload: dict) -> list[dict]:
    if payload.get("current_records") is not None:
        return normalize_records(payload.get("current_records"))
    if payload.get("mock_records") is not None:
        return normalize_records(payload.get("mock_records"))
    config = config_from_env(payload.get("profile"))
    response = request_api(config, "namecheap.domains.dns.getHosts", domain)
    parsed = parse_api_xml(response)
    if not parsed["ok"]:
        raise ValueError(f"Namecheap getHosts failed: {parsed['errors']}")
    return normalize_records(parsed["records"])


def plan(domain: str, payload: dict) -> dict:
    current = current_records(domain, payload)
    desired = desired_from_payload(current, payload)
    diff = diff_records(current, desired)
    return {
        "ok": True,
        "domain": domain,
        "currentRecords": current,
        "desiredRecords": desired,
        "diff": diff,
        "requiresBackup": True,
        "requiresConfirm": True,
        "destructive": bool(diff["removed"]),
    }


def sethosts_params(records: list[dict]) -> dict[str, str]:
    params: dict[str, str] = {}
    for index, record in enumerate(normalize_records(records), start=1):
        params[f"HostName{index}"] = record["Name"]
        params[f"RecordType{index}"] = record["Type"]
        params[f"Address{index}"] = record["Address"]
        for key in SUPPORTED_RECORD_KEYS:
            if key in {"Name", "Type", "Address"}:
                continue
            if record.get(key) not in (None, ""):
                prefix = "MXPref" if key == "MXPref" else key
                params[f"{prefix}{index}"] = str(record[key])
    return params


def backup(domain: str, records: list[dict], db: str | None = None, out_dir: str | None = None) -> dict:
    from urirun import host_db

    timestamp = domain_monitor.now_id()
    directory = Path(out_dir or "~/.urirun/artifacts/namecheap").expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{domain}-{timestamp}.dns-backup.json"
    payload = {"domain": domain, "records": normalize_records(records), "createdAt": timestamp, "provider": "namecheap"}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return host_db.register_artifact(db, "dns-backup", f"artifact://host/namecheap/dns-backup/{domain}/{timestamp}", str(path), payload)


def apply(domain: str, payload: dict) -> dict:
    if payload.get("confirm") is not True:
        raise ValueError("Namecheap apply requires payload confirm=true")
    if not payload.get("backup_uri"):
        raise ValueError("Namecheap apply requires backup_uri")
    desired = normalize_records(payload.get("desired_records") or (payload.get("plan") or {}).get("desiredRecords"))
    if not desired:
        raise ValueError("Namecheap apply requires desired_records")

    current = current_records(domain, payload)
    plan_current = payload.get("plan_current_records") or (payload.get("plan") or {}).get("currentRecords")
    if plan_current is not None and normalize_records(plan_current) != current and not payload.get("allow_current_drift"):
        raise ValueError("current DNS records differ from the reviewed plan")

    if payload.get("mock_apply"):
        return {"ok": True, "domain": domain, "applied": False, "mock": True, "desiredRecords": desired, "currentRecords": current}

    config = config_from_env(payload.get("profile"))
    method = "POST" if len(desired) > 10 else "GET"
    response = request_api(config, "namecheap.domains.dns.setHosts", domain, sethosts_params(desired), method=method)
    parsed = parse_api_xml(response)
    if not parsed["ok"] or parsed.get("setSuccess") is False:
        raise ValueError(f"Namecheap setHosts failed: {parsed['errors']}")
    return {"ok": True, "domain": domain, "applied": True, "method": method, "response": parsed}


def run_uri_route(ctx: dict, execute: bool) -> dict:
    payload = dict(ctx.get("payload") or {})
    domain = str(payload.get("domain") or ctx["target"])
    action = (ctx["translation"]["args"] or [ctx["translation"]["operation"]])[0]
    db = payload.get("db") or (ctx["routeEntry"].get("config") or {}).get("db")

    if ctx["translation"]["operation"] == "query" and action == "current":
        return {"type": "namecheap-dns", "action": action, "domain": domain, "records": current_records(domain, payload)}
    if ctx["translation"]["operation"] == "query" and action == "expected":
        return {"type": "namecheap-dns", "action": action, "domain": domain, "expectedRecords": domain_monitor.expected_records(payload)}

    if ctx["translation"]["operation"] != "command":
        raise ValueError(f"unsupported Namecheap DNS action: {action}")

    if action == "plan":
        return {"type": "namecheap-dns", "action": action, **plan(domain, payload)}

    if action == "backup":
        records = current_records(domain, payload)
        if not execute:
            return {"type": "namecheap-dns", "action": action, "simulated": True, "domain": domain, "records": records}
        return {"type": "namecheap-dns", "action": action, "domain": domain, "backup": backup(domain, records, db=db, out_dir=payload.get("backup_dir"))}

    if action == "apply":
        if not execute:
            return {"type": "namecheap-dns", "action": action, "simulated": True, "domain": domain, "plan": plan(domain, payload)}
        return {"type": "namecheap-dns", "action": action, **apply(domain, payload)}

    raise ValueError(f"unsupported Namecheap DNS action: {action}")
