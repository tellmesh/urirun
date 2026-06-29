from __future__ import annotations

from pathlib import Path


def _dashboard_js() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "urirun" / "host" / "dashboard.js").read_text(encoding="utf-8")


def test_webpage_node_qr_uses_reconnect_target_not_relay_url_directly():
    source = _dashboard_js()
    assert "function nodeQrTarget" in source
    assert "function webpageReconnectUrl" in source
    assert "qrDetails(nodeQrTarget(node)" in source
    assert "qrDetails(node.url, `node:${node.name}`" not in source


def test_webpage_node_save_persists_reconnect_metadata():
    source = _dashboard_js()
    assert "function webpageNodeMeta" in source
    assert "meta: webpageNodeMeta" in source
    assert "pageUrl" in source
    assert "relayUrl" in source


def test_qr_lan_fallback_does_not_hardcode_private_host():
    source = _dashboard_js()
    assert "function serviceBaseFromLocation" in source
    assert "http://192.168.188.212:8195" not in source


def test_webpage_node_card_exposes_delegated_phone_scanner_service():
    source = _dashboard_js()
    assert "function delegatedPhoneServicesDetails" in source
    assert "function dashboardLanBase" in source
    assert "function phoneScannerDelegatedUrl" in source
    assert "delegatedPhoneServicesDetails(node)" in source
    assert "service:phone-scanner" in source
    assert "Usługi hosta na telefonie" in source
    assert "u.port = '8194'" in source
    assert "dashboardLanBase() + '/scanner?'" in source
