from urirun.host import widgets


def test_query_value_returns_first_or_default() -> None:
    assert widgets.query_value({"target": ["host", "node"]}, "target") == "host"
    assert widgets.query_value({}, "target", "service:phone-scanner") == "service:phone-scanner"


def test_select_service_view_prefers_id_then_target_then_fallback() -> None:
    data = {
        "updatedAt": "2026-06-24T00:00:00Z",
        "views": [
            {"id": "service:one/live", "target": "service:one"},
            {"id": "service:two/live", "target": "service:two"},
        ],
    }

    assert widgets.select_service_view(
        data,
        target="service:one",
        view_id="service:two/live",
        utc_now=lambda: "now",
    )["target"] == "service:two"
    assert widgets.select_service_view(
        data,
        target="service:one",
        view_id=None,
        utc_now=lambda: "now",
    )["id"] == "service:one/live"
    fallback = widgets.select_service_view(
        {"views": []},
        target="service:missing",
        view_id=None,
        utc_now=lambda: "now",
    )
    assert fallback["id"] == "service:missing/live"
    assert fallback["status"] == "stopped"
    assert fallback["updatedAt"] == "now"


def test_service_widget_summary_uses_scanner_stream_document() -> None:
    summary = widgets.service_widget_summary({
        "title": "phone scanner stream",
        "status": "accepted",
        "data": {
            "streams": [
                {
                    "seriesId": "series-1",
                    "count": 6,
                    "best": {
                        "detectedDocument": {
                            "type": "paragon",
                            "date": "2026-06-24",
                            "contractor": "ACME",
                            "amount": "12.50 PLN",
                        }
                    },
                }
            ]
        },
    })

    assert summary == {
        "title": "phone scanner stream",
        "status": "accepted",
        "subtitle": "paragon · 2026-06-24 · ACME · 12.50 PLN",
        "detail": "6 frame(s)",
    }


def test_service_widget_summary_falls_back_to_target_and_updated_at() -> None:
    summary = widgets.service_widget_summary({
        "title": "node status",
        "status": "running",
        "target": "node:lenovo",
        "updatedAt": "2026-06-24T00:00:00Z",
    })

    assert summary == {
        "title": "node status",
        "status": "running",
        "subtitle": "node:lenovo",
        "detail": "2026-06-24T00:00:00Z",
    }
