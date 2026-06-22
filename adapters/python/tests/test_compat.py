# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

import contextlib
import io
import json
import unittest
from unittest.mock import patch

import urirun
from urirun import compat


def _healthy_importable(name):
    # backend host/node layers stay in core; namecheap was extracted (removed),
    # its connector replacement is installed.
    if name == "urirun.namecheap_dns":
        return False
    if name == "urirun_connector_namecheap_dns":
        return True
    return bool(name and (name.startswith("urirun.host.") or name.startswith("urirun.node.")))


class CompatReportTests(unittest.TestCase):
    def test_backend_layer_is_kept(self):
        with patch.object(compat, "_entry_point_names", return_value={"namecheap-dns"}), \
             patch.object(compat, "_importable", side_effect=_healthy_importable):
            data = compat.report()

        host_db = next(m for m in data["modules"] if m["module"] == "urirun.host.host_db")
        self.assertEqual(host_db["owner"], "backend")
        self.assertEqual(host_db["layer"], "host")
        self.assertEqual(host_db["reusedBy"], "urirun-connector-sqlite-context")
        self.assertTrue(host_db["currentImportable"])
        self.assertEqual(host_db["status"], "kept")

    def test_namecheap_is_extracted(self):
        with patch.object(compat, "_entry_point_names", return_value={"namecheap-dns"}), \
             patch.object(compat, "_importable", side_effect=_healthy_importable):
            data = compat.report()

        nc = next(m for m in data["modules"] if m["module"] == "urirun.namecheap_dns")
        self.assertEqual(nc["owner"], "extracted")
        self.assertFalse(nc["currentImportable"])  # removed from core
        self.assertTrue(nc["replacementInstalled"])
        self.assertEqual(nc["status"], "extracted")
        self.assertTrue(data["ok"])

    def test_top_level_api_exposes_compat_report(self):
        data = urirun.compat_report()
        # The top-level API must expose the report with its core fields; whether
        # ``ok`` is True depends on which connectors are installed in this env
        # (covered deterministically by test_compat_report_includes_namecheap),
        # so this exposure test asserts structure, not install state.
        self.assertIn("ok", data)
        self.assertTrue(any(m["module"] == "urirun.host.host_integrations" for m in data["modules"]))

    def test_cli_list_json_reports_node_layer(self):
        with patch.object(compat, "_entry_point_names", return_value={"namecheap-dns"}), \
             patch.object(compat, "_importable", side_effect=_healthy_importable):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = compat.main(["list", "--json"])

        self.assertEqual(code, 0)
        data = json.loads(buffer.getvalue())
        self.assertTrue(data["ok"])
        self.assertGreater(data["backendLayers"], 0)
        self.assertEqual(data["extracted"], 1)
        mesh = next(m for m in data["modules"] if m["module"] == "urirun.node.mesh")
        self.assertEqual(mesh["layer"], "node")

    def test_cli_check_ok_when_layers_present_and_namecheap_extracted(self):
        with patch.object(compat, "_entry_point_names", return_value={"namecheap-dns"}), \
             patch.object(compat, "_importable", side_effect=_healthy_importable), \
             contextlib.redirect_stdout(io.StringIO()):
            code = compat.main(["check"])

        self.assertEqual(code, 0)

    def test_cli_check_nonzero_when_namecheap_replacement_missing(self):
        def importable(name):
            # backend present, but the namecheap connector is NOT installed
            return bool(name and (name.startswith("urirun.host.") or name.startswith("urirun.node.")))

        with patch.object(compat, "_entry_point_names", return_value=set()), \
             patch.object(compat, "_importable", side_effect=importable), \
             contextlib.redirect_stdout(io.StringIO()):
            code = compat.main(["check"])

        self.assertEqual(code, 1)

    def test_cli_check_nonzero_when_backend_layer_missing(self):
        with patch.object(compat, "_entry_point_names", return_value={"namecheap-dns"}), \
             patch.object(compat, "_importable", return_value=False), \
             contextlib.redirect_stdout(io.StringIO()):
            code = compat.main(["check"])

        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
