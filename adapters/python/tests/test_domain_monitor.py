# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

import contextlib
import importlib.util
import io
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from urirun import domain_monitor, host_db, planfile_adapter, v2
from urirun.host import host_integrations


PLANFILE_AVAILABLE = importlib.util.find_spec("planfile") is not None


class _StatusHandler(BaseHTTPRequestHandler):
    status = 200

    def do_GET(self):
        self.send_response(self.status)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, _format, *args):
        return


@contextlib.contextmanager
def local_http(status: int = 200):
    class Handler(_StatusHandler):
        pass

    Handler.status = status
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class DomainMonitorTests(unittest.TestCase):
    def test_http_200_writes_success_check(self):
        with tempfile.TemporaryDirectory() as tmp, local_http(200) as url:
            db = str(Path(tmp) / "host.db")
            result = domain_monitor.check_domain(domain="localhost", url=url, db=db, execute=True)
            self.assertTrue(result["ok"], result)

            checks = host_db.recent_checks(db, subject="localhost")
            self.assertEqual(checks[0]["status"], "ok")
            self.assertEqual(checks[0]["result"]["http"]["status"], 200)
            logs = host_db.recent_logs(db, stream="daily")
            self.assertEqual(logs[0]["event"], "daily_domain_check.finished")
            self.assertTrue(logs[0]["detail"]["ok"])

    def test_http_failure_creates_screenshot_artifact(self):
        with tempfile.TemporaryDirectory() as tmp, local_http(503) as url:
            db = str(Path(tmp) / "host.db")
            result = domain_monitor.check_domain(
                domain="localhost",
                url=url,
                db=db,
                execute=True,
                screenshot_dir=str(Path(tmp) / "shots"),
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["http"]["status"], 503)
            self.assertEqual(result["artifacts"][0]["kind"], "screenshot")
            self.assertTrue(Path(result["artifacts"][0]["path"]).exists())

    @unittest.skipUnless(PLANFILE_AVAILABLE, "planfile is not installed")
    def test_dns_mismatch_creates_review_ticket_only(self):
        with tempfile.TemporaryDirectory() as tmp, local_http(200) as url:
            db = str(Path(tmp) / "host.db")
            result = domain_monitor.check_domain(
                domain="localhost",
                url=url,
                expected={"A": ["203.0.113.10"]},
                db=db,
                project=tmp,
                execute=True,
                screenshot_dir=str(Path(tmp) / "shots"),
            )
            self.assertFalse(result["ok"])
            self.assertTrue(result["dnsMismatches"])
            self.assertEqual(result["tickets"][0]["execution"]["queue"], "review")
            self.assertEqual(result["tickets"][0]["executor"]["mode"], "interactive")

            tickets = planfile_adapter.list_tickets(tmp, sprint="current", queue="review")
            self.assertEqual(len(tickets), 1)
            self.assertEqual(tickets[0]["status"], "open")

    def test_v2_domain_monitor_bindings(self):
        with tempfile.TemporaryDirectory() as tmp, local_http(200) as url:
            db = str(Path(tmp) / "host.db")
            registry = v2.compile_registry(host_integrations.domain_monitor_bindings(db=db, project=tmp, screenshot_dir=str(Path(tmp) / "shots")))

            http = v2.run(
                "monitor://localhost/http/query/status",
                registry,
                {"url": url},
            )
            self.assertTrue(http["ok"], http)
            self.assertEqual(http["result"]["http"]["status"], 200)

            flow = v2.run(
                "flow://host/domain/command/check",
                registry,
                {"domain": "localhost", "url": url},
                mode="execute",
            )
            self.assertTrue(flow["ok"], flow)
            self.assertTrue(flow["result"]["ok"])
            self.assertEqual(host_db.recent_checks(db, subject="localhost")[0]["status"], "ok")

    @unittest.skipUnless(PLANFILE_AVAILABLE, "planfile is not installed")
    def test_v2_domain_monitor_mismatch_sets_failed_envelope_and_review_ticket(self):
        with tempfile.TemporaryDirectory() as tmp, local_http(200) as url:
            db = str(Path(tmp) / "host.db")
            registry = v2.compile_registry(host_integrations.domain_monitor_bindings(db=db, project=tmp, screenshot_dir=str(Path(tmp) / "shots")))
            flow = v2.run(
                "flow://host/domain/command/check",
                registry,
                {"domain": "localhost", "url": url, "expected_a": ["203.0.113.10"]},
                mode="execute",
            )
            self.assertFalse(flow["ok"], flow)
            self.assertEqual(flow["result"]["exitCode"], 1)
            tickets = planfile_adapter.list_tickets(tmp, sprint="current", queue="review")
            self.assertEqual(len(tickets), 1)

    def test_cli_monitor_domain_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp, local_http(200) as url:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = v2.main([
                    "host",
                    "monitor",
                    "domain",
                    "localhost",
                    "--url",
                    url,
                    "--db",
                    str(Path(tmp) / "host.db"),
                ])
            self.assertEqual(code, 0)
            result = json.loads(buffer.getvalue())
            self.assertFalse(result["executed"])
            self.assertEqual(host_db.recent_checks(str(Path(tmp) / "host.db"), subject="localhost"), [])


if __name__ == "__main__":
    unittest.main()
