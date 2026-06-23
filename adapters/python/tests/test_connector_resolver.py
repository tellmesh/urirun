import json
from pathlib import Path

from urirun.connectors import resolver


def test_index_local_reads_connector_manifest(tmp_path):
    package = tmp_path / "urirun-connector-demo" / "urirun_connector_demo"
    package.mkdir(parents=True)
    (package / "connector.manifest.json").write_text(json.dumps({
        "id": "demo",
        "summary": "Demo tools",
        "uriSchemes": ["demo"],
        "routes": ["demo://host/thing/query/read"],
    }), encoding="utf-8")

    items = resolver.index_local([str(tmp_path)])

    assert len(items) == 1
    assert items[0]["id"] == "demo"
    assert items[0]["schemes"] == ["demo"]
    assert items[0]["install"]["local"].endswith("urirun-connector-demo")
    assert items[0]["install"]["git"] == "git+https://github.com/if-uri/urirun-connector-demo.git"


def test_index_local_infers_scheme_from_code(tmp_path):
    package = tmp_path / "org" / "urirun-connector-browser-control" / "urirun_connector_browser_control"
    package.mkdir(parents=True)
    (package / "core.py").write_text(
        "import urirun\nCONNECTOR = urirun.connector('browser-control', scheme='browser')\n",
        encoding="utf-8",
    )

    items = resolver.index_local([str(tmp_path)])

    assert [item["id"] for item in items] == ["browser-control"]
    assert items[0]["schemes"] == ["browser"]


def test_resolve_scores_scheme_uri_and_terms(tmp_path):
    base = Path(tmp_path)
    browser_pkg = base / "urirun-connector-browser-control" / "pkg"
    browser_pkg.mkdir(parents=True)
    (browser_pkg / "connector.manifest.json").write_text(json.dumps({
        "id": "browser-control",
        "summary": "Drive browser pages and screenshots",
        "uriSchemes": ["browser"],
    }), encoding="utf-8")
    email_pkg = base / "urirun-connector-email" / "pkg"
    email_pkg.mkdir(parents=True)
    (email_pkg / "connector.manifest.json").write_text(json.dumps({
        "id": "email",
        "summary": "Send email messages",
        "uriSchemes": ["email"],
    }), encoding="utf-8")

    browser_hits = resolver.resolve("browser://laptop/main/page/query/dom", roots=[str(base)])
    mail_hits = resolver.resolve("send email", roots=[str(base)])

    assert browser_hits[0]["id"] == "browser-control"
    assert browser_hits[0]["score"] >= 100
    assert mail_hits[0]["id"] == "email"
