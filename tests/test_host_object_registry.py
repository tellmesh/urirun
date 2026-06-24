from urirun.host import object_registry


def test_host_registry_routes_keeps_only_host_dashboard_connector_layers() -> None:
    routes = object_registry.host_registry_routes([
        {
            "uri": "scanner://host/capture/command/run",
            "kind": "command",
            "label": "Capture",
            "where": "host",
            "sideEffects": ["file-write"],
            "layer": "host",
        },
        {
            "uri": "scanner://page/camera/command/start",
            "kind": "command",
            "label": "Start",
            "where": "page",
            "sideEffects": ["media-stream"],
            "layer": "page",
        },
    ])

    assert routes == [{
        "uri": "scanner://host/capture/command/run",
        "kind": "command",
        "title": "Capture",
        "source": "host",
        "safe": False,
        "layer": "host",
    }]


def test_service_contacts_marks_external_scanner_state() -> None:
    contacts = object_registry.service_contacts(
        scanner_port=8196,
        scanner_state={
            "url": "https://192.168.1.10:8196/scanner",
            "status": "external-running",
            "reachable": True,
        },
        service_entries=[],
        phone_scanner_url=lambda port: f"https://host:{port}/scanner",
        phone_scanner_status=lambda port: {"url": f"https://host:{port}/scanner", "status": "stopped", "reachable": False},
    )

    assert contacts[0]["id"] == "service:phone-scanner"
    assert contacts[0]["status"] == "external-running"
    assert contacts[0]["reachable"] is True
    assert "scanner://page/camera/command/scan" in contacts[0]["routes"]


def test_service_contacts_replaces_default_with_in_process_scanner() -> None:
    contacts = object_registry.service_contacts(
        scanner_port=8196,
        scanner_state={
            "url": "https://host:8196/scanner",
            "status": "stopped",
            "reachable": False,
        },
        service_entries=[{
            "service_id": "https://0.0.0.0:8196",
            "alive": True,
            "server_name": "scanner-server",
        }],
        phone_scanner_url=lambda port: f"https://host:{port}/scanner",
        phone_scanner_status=lambda port: {"url": f"https://host:{port}/scanner", "status": "stopped", "reachable": False},
    )

    assert len(contacts) == 1
    assert contacts[0]["id"] == "service:phone-scanner"
    assert contacts[0]["status"] == "running"
    assert contacts[0]["reachable"] is True
    assert contacts[0]["serverName"] == "scanner-server"


def test_annotate_node_tokens_never_raises() -> None:
    nodes = [{"name": "lenovo"}, {"name": "broken"}, {"url": "missing-name"}]

    def token_for(name):
        if name == "broken":
            raise RuntimeError("keyring down")
        return "token"

    assert object_registry.annotate_node_tokens(nodes, token_for) == [
        {"name": "lenovo", "hasToken": True},
        {"name": "broken", "hasToken": False},
        {"url": "missing-name"},
    ]
