import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from urirun import scheduler, v2


class SchedulerTests(unittest.TestCase):
    def test_systemd_preview_and_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = scheduler.preview(
                project="/repo",
                config="/mesh.json",
                queue="daily",
                max_tickets=5,
                time_of_day="07:30",
                execute=True,
                no_llm=True,
                working_directory="/repo",
            )
            self.assertIn("--execute", plan["command"])
            self.assertIn("OnCalendar=*-*-* 07:30:00", plan["files"]["urirun-daily.timer"])
            self.assertIn("WorkingDirectory=/repo", plan["files"]["urirun-daily.service"])

            written = scheduler.install_systemd_user(plan["files"], tmp)
            self.assertEqual(len(written), 2)
            self.assertTrue((Path(tmp) / "urirun-daily.service").exists())
            self.assertTrue((Path(tmp) / "urirun-daily.timer").exists())

    def test_cli_schedule_cron_preview(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = v2.main([
                "host",
                "task",
                "schedule",
                "--kind",
                "cron",
                "--project",
                "/repo",
                "--queue",
                "daily",
                "--time",
                "06:15",
                "--run-execute",
            ])
        self.assertEqual(code, 0)
        result = json.loads(buffer.getvalue())
        self.assertTrue(result["dryRun"])
        self.assertEqual(result["schedule"]["cron"].split()[:5], ["15", "6", "*", "*", "*"])
        self.assertIn("--execute", result["schedule"]["command"])


if __name__ == "__main__":
    unittest.main()
