from __future__ import annotations

from typing import Callable


def query_value(query: dict[str, list[str]], name: str, default: str | None = None) -> str | None:
    values = query.get(name)
    return values[0] if values else default


def select_service_view(
    data: dict,
    *,
    target: str,
    view_id: str | None,
    utc_now: Callable[[], str],
) -> dict:
    views = [item for item in data.get("views", []) if isinstance(item, dict)]
    if view_id:
        for view in views:
            if view.get("id") == view_id:
                return view
    for view in views:
        if view.get("target") == target or view.get("serviceId") == target:
            return view
    return {
        "id": view_id or f"{target}/live",
        "target": target,
        "serviceId": target,
        "title": target,
        "kind": "stream",
        "view": "json",
        "status": "stopped",
        "updatedAt": data.get("updatedAt") or utc_now(),
        "data": {},
    }


def scanner_stream_summary(title: str, status: str, stream: dict) -> dict[str, str]:
    best = stream.get("best") if isinstance(stream.get("best"), dict) else {}
    doc = best.get("detectedDocument") if isinstance(best.get("detectedDocument"), dict) else {}
    parts = [
        doc.get("type"),
        doc.get("date"),
        doc.get("contractor") or doc.get("supplier") or doc.get("category"),
        doc.get("amount"),
    ]
    subtitle = " · ".join(str(part) for part in parts if part) or str(stream.get("seriesId") or "")
    detail = f"{stream.get('count') or 0} frame(s)"
    return {"title": title, "status": status, "subtitle": subtitle, "detail": detail}


def service_widget_summary(view: dict) -> dict[str, str]:
    title = str(view.get("title") or view.get("id") or "service view")
    status = str(view.get("status") or "unknown")
    streams = ((view.get("data") or {}).get("streams") or []) if isinstance(view.get("data"), dict) else []
    if streams and isinstance(streams[0], dict):
        return scanner_stream_summary(title, status, streams[0])
    return {
        "title": title,
        "status": status,
        "subtitle": str(view.get("target") or view.get("serviceId") or ""),
        "detail": str(view.get("updatedAt") or ""),
    }
