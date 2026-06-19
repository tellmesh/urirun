import contextlib
import io
import importlib.util
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from urirun import host_dashboard, host_db, mesh, planfile_adapter, v2


PLANFILE_AVAILABLE = importlib.util.find_spec("planfile") is not None


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


@unittest.skipUnless(PLANFILE_AVAILABLE, "planfile is not installed")
class HostDashboardTests(unittest.TestCase):
    def test_dashboard_html_summary_and_task_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "host.db")
            config = str(Path(tmp) / "mesh.json")
            mesh.init_host(config, name="test-host")
            ticket = planfile_adapter.create_ticket(
                tmp,
                {
                    "name": "Check daily domains",
                    "queue": "daily",
                    "prompt": "check domains",
                    "executor_handler": "flow://host/daily/command/run",
                },
            )
            host_db.add_log(db, "daily", "dashboard.test", {"ok": True})
            host_db.add_check(db, "ifuri.com", "monitor://ifuri.com/http/query/status", "ok", {"status": 200})
            with contextlib.redirect_stdout(io.StringIO()):
                server = host_dashboard.serve(project=tmp, db=db, config=config, host="127.0.0.1", port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with urllib.request.urlopen(f"{base}/", timeout=5) as response:
                    html = response.read().decode("utf-8")
                self.assertIn("urirun host", html)
                self.assertIn("/api/summary", html)

                summary = get_json(f"{base}/api/summary")
                self.assertTrue(summary["ok"], summary)
                self.assertEqual(summary["taskCounts"]["open"], 1)
                self.assertEqual(summary["logs"][0]["event"], "dashboard.test")
                self.assertEqual(summary["checks"][0]["subject"], "ifuri.com")

                tasks = get_json(f"{base}/api/tasks?sprint=current")
                self.assertEqual(tasks["tickets"][0]["id"], ticket["id"])

                started = post_json(f"{base}/api/tasks/{ticket['id']}/start", {"assigned_to": "dashboard"})
                self.assertTrue(started["ok"], started)
                self.assertEqual(started["ticket"]["status"], "in_progress")
            finally:
                server.shutdown()
                server.server_close()

    def test_v2_dashboard_url_command(self):
        buffer = []

        class Writer:
            def write(self, value):
                buffer.append(value)

        with patch("sys.stdout", Writer()):
            code = v2.main(["host", "dashboard", "url", "--port", "8123"])
        self.assertEqual(code, 0)
        self.assertIn("http://127.0.0.1:8123/", "".join(buffer))


if __name__ == "__main__":
    unittest.main()
