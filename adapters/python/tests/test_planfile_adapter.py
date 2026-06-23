# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from urirun import mesh, planfile_adapter, task_planner, v2
from urirun.node import task_cli


PLANFILE_AVAILABLE = importlib.util.find_spec("planfile") is not None


@unittest.skipUnless(PLANFILE_AVAILABLE, "planfile is not installed")
class PlanfileAdapterTests(unittest.TestCase):
    def test_create_next_and_complete_ticket(self):
        with tempfile.TemporaryDirectory() as tmp:
            ticket = planfile_adapter.create_ticket(tmp, {
                "name": "Daily domain check",
                "priority": "medium",
                "labels": ["daily", "domain"],
                "queue": "daily",
                "prompt": "sprawdz domeny",
                "executor_handler": "flow://host/daily-domain-check",
                "max_attempts": 3,
            })
            self.assertEqual(ticket["priority"], "normal")
            self.assertEqual(ticket["execution"]["queue"], "daily")
            self.assertEqual(ticket["inputs"]["prompt"], "sprawdz domeny")
            self.assertEqual(ticket["executor"]["kind"], "uri-flow")

            next_ticket = planfile_adapter.next_ticket(tmp, queue="daily")
            self.assertEqual(next_ticket["id"], ticket["id"])

            started = planfile_adapter.start_ticket(tmp, ticket["id"], assigned_to="host")
            self.assertEqual(started["status"], "in_progress")
            self.assertEqual(started["execution"]["state"], "running")

            completed = planfile_adapter.complete_ticket(
                tmp,
                ticket["id"],
                note="done by test",
                result={"ok": True},
                artifacts=["artifact://test/result"],
            )
            self.assertEqual(completed["status"], "done")
            self.assertEqual(completed["execution"]["state"], "done")
            self.assertEqual(completed["outputs"]["result"], {"ok": True})
            self.assertIn("artifact://test/result", completed["outputs"]["artifacts"])

    def test_dsl_create_ticket(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = planfile_adapter.run_dsl(tmp, 'create ticket "Check ifuri" priority=high labels=daily,domain')
            self.assertTrue(result["ok"])

            tickets = planfile_adapter.list_tickets(tmp, label=["daily"])
            self.assertEqual(len(tickets), 1)
            self.assertEqual(tickets[0]["name"], "Check ifuri")

    def test_cli_host_task_create_and_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(v2.main(["host", "task", "create", "CLI ticket", "--project", tmp, "--prompt", "pokaz procesy"]), 0)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(v2.main(["host", "task", "list", "--project", tmp, "--json"]), 0)
            self.assertIn("CLI ticket", buffer.getvalue())

    def test_host_task_run_updates_ticket(self):
        with tempfile.TemporaryDirectory() as tmp:
            ticket = planfile_adapter.create_ticket(tmp, {
                "name": "Process check",
                "prompt": "pokaz procesy",
                "queue": "daily",
            })
            args = SimpleNamespace(
                task_command="run",
                project=tmp,
                ticket_id=ticket["id"],
                config=str(Path(tmp) / "mesh.json"),
                node=[],
                execute=True,
                no_llm=True,
                assigned_to="host",
                lease_seconds=None,
                note=None,
                artifact=[],
            )
            fake_mesh = {
                "nodes": [{"name": "pc1", "reachable": True}],
                "routes": [
                    {"uri": "env://pc1/runtime/query/health", "safe": True},
                    {"uri": "proc://pc1/process/query/list", "safe": True},
                ],
                "serviceMap": {"pc1": "http://127.0.0.1:8765"},
            }
            fake_execution = {
                "ok": True,
                "timeline": [{"id": "proc", "uri": "proc://pc1/process/query/list", "target": "pc1", "ok": True}],
                "results": {"proc": {"ok": True}},
            }
            with (
                patch.object(task_cli, "host_config_for_args", return_value={}),
                patch.object(task_cli, "discover_mesh", return_value=fake_mesh),
                patch.object(task_cli, "execute_flow", return_value=fake_execution),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(mesh.task_command(args), 0)

            updated = planfile_adapter.get_ticket(tmp, ticket["id"])
            self.assertEqual(updated["status"], "done")
            self.assertEqual(updated["execution"]["state"], "done")
            self.assertTrue(updated["outputs"]["result"]["timeline"])

    def test_v2_task_uri_bindings_create_and_list_ticket(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = v2.compile_registry(v2.planfile_task_bindings(project=tmp))

            # dry-run create returns a plan and must NOT mutate the store.
            simulated = v2.run(
                "task://host/ticket/command/create",
                registry,
                {"name": "URI ticket", "prompt": "sprawdz procesy", "queue": "daily"},
                mode="dry-run",
            )
            self.assertTrue(simulated["ok"], simulated)
            self.assertTrue(simulated["result"]["simulated"])
            self.assertEqual(planfile_adapter.list_tickets(tmp, sprint="current"), [])

            created = v2.run(
                "task://host/ticket/command/create",
                registry,
                {"name": "URI ticket", "prompt": "sprawdz procesy", "queue": "daily"},
                mode="execute",
            )
            self.assertTrue(created["ok"], created)
            ticket = created["result"]["ticket"]
            self.assertEqual(ticket["name"], "URI ticket")

            listed = v2.run(
                "task://host/tickets/query/list",
                registry,
                {"queue": "daily"},
                mode="dry-run",
            )
            self.assertTrue(listed["ok"], listed)
            self.assertEqual(listed["result"]["tickets"][0]["id"], ticket["id"])

    def test_v2_task_uri_complete_and_fail_record_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = v2.compile_registry(v2.planfile_task_bindings(project=tmp))

            def run(uri, payload, mode="execute"):
                result = v2.run(uri, registry, payload, mode=mode)
                self.assertTrue(result["ok"], result)
                return result["result"]

            tid = run("task://host/ticket/command/create", {"name": "Lifecycle"})["ticket"]["id"]
            run("task://host/ticket/command/start", {"ticket_id": tid})
            completed = run(
                "task://host/ticket/command/complete",
                {"ticket_id": tid, "note": "ok via uri", "result": {"http": 200}, "artifact": ["a://x"]},
            )["ticket"]
            self.assertEqual(completed["status"], "done")
            self.assertEqual(completed["outputs"]["result"], {"http": 200})
            self.assertIn("ok via uri", completed["outputs"]["notes"])
            self.assertIn("a://x", completed["outputs"]["artifacts"])
            self.assertGreaterEqual(len(completed["history"]), 2)

            # fail path records the error on a fresh ticket.
            other = run("task://host/ticket/command/create", {"name": "Breaks"})["ticket"]["id"]
            run("task://host/ticket/command/start", {"ticket_id": other})
            failed = run("task://host/ticket/command/fail", {"ticket_id": other, "error": "boom"})["ticket"]
            self.assertEqual(failed["execution"]["last_error"], "boom")

    def test_v2_task_uri_rejects_invalid_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = v2.compile_registry(v2.planfile_task_bindings(project=tmp))
            result = v2.run(
                "task://host/ticket/command/create",
                registry,
                {"name": 123},
                mode="execute",
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["type"], "schema")
            self.assertEqual(planfile_adapter.list_tickets(tmp, sprint="current"), [])

    def test_host_task_run_dispatches_executor_handler(self):
        with tempfile.TemporaryDirectory() as tmp:
            ticket = planfile_adapter.create_ticket(tmp, {
                "name": "Handler ticket",
                "queue": "daily",
                "executor_kind": "uri-flow",
                "executor_handler": "task://host/tickets/query/list",
            })
            args = SimpleNamespace(
                task_command="run",
                project=tmp,
                ticket_id=ticket["id"],
                config=str(Path(tmp) / "mesh.json"),
                node=[],
                execute=True,
                no_llm=True,
                assigned_to="host",
                lease_seconds=None,
                note=None,
                artifact=[],
            )
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(mesh.task_command(args), 0)
            result = __import__("json").loads(buffer.getvalue())
            # The handler URI was dispatched locally instead of an LLM/heuristic flow.
            self.assertEqual(result["generator"]["kind"], "executor-handler")
            self.assertEqual(result["generator"]["handler"], "task://host/tickets/query/list")
            self.assertTrue(result["results"]["handler"]["ok"])

            final = planfile_adapter.get_ticket(tmp, ticket["id"])
            self.assertEqual(final["status"], "done")
            self.assertEqual(final["execution"]["state"], "done")

    def test_fail_or_retry_requeues_until_max_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            ticket = planfile_adapter.create_ticket(tmp, {"name": "Flaky", "queue": "daily", "max_attempts": 2})
            tid = ticket["id"]
            planfile_adapter.start_ticket(tmp, tid)

            first = planfile_adapter.fail_or_retry(tmp, tid, "boom1")
            self.assertTrue(first["retry"]["retried"])
            self.assertEqual(first["status"], "open")
            self.assertEqual(first["execution"]["state"], "ready")
            self.assertEqual(first["execution"]["attempt"], 1)
            self.assertEqual(first["execution"]["last_error"], "boom1")
            # Requeued ticket is runnable again.
            self.assertEqual(planfile_adapter.next_ticket(tmp, queue="daily")["id"], tid)

            planfile_adapter.start_ticket(tmp, tid)
            final = planfile_adapter.fail_or_retry(tmp, tid, "boom2")
            self.assertFalse(final["retry"]["retried"])
            self.assertEqual(final["execution"]["state"], "failed")
            self.assertEqual(final["execution"]["attempt"], 2)
            # Exhausted ticket is no longer runnable.
            self.assertIsNone(planfile_adapter.next_ticket(tmp, queue="daily"))

    def test_fail_or_retry_default_max_attempts_fails_terminally(self):
        with tempfile.TemporaryDirectory() as tmp:
            ticket = planfile_adapter.create_ticket(tmp, {"name": "OneShot", "queue": "daily"})
            planfile_adapter.start_ticket(tmp, ticket["id"])
            result = planfile_adapter.fail_or_retry(tmp, ticket["id"], "x")
            self.assertFalse(result["retry"]["retried"])
            self.assertEqual(result["execution"]["state"], "failed")

    def test_host_task_loop_retries_failing_flow_until_exhausted(self):
        with tempfile.TemporaryDirectory() as tmp:
            ticket = planfile_adapter.create_ticket(tmp, {
                "name": "Always fails",
                "prompt": "pokaz procesy",
                "queue": "daily",
                "max_attempts": 2,
            })
            args = SimpleNamespace(
                task_command="loop",
                project=tmp,
                sprint="current",
                queue="daily",
                label=[],
                max_tickets=5,
                continue_on_error=True,
                config=str(Path(tmp) / "mesh.json"),
                node=[],
                execute=True,
                no_llm=True,
                assigned_to="host",
                lease_seconds=None,
                note=None,
                artifact=[],
            )
            fake_mesh = {"nodes": [], "routes": [], "serviceMap": {}}
            fake_execution = {"ok": False, "timeline": [], "results": {}}
            with (
                patch.object(task_cli, "host_config_for_args", return_value={}),
                patch.object(task_cli, "discover_mesh", return_value=fake_mesh),
                patch.object(task_cli, "execute_flow", return_value=fake_execution),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(mesh.task_command(args), 1)

            final = planfile_adapter.get_ticket(tmp, ticket["id"])
            self.assertEqual(final["execution"]["state"], "failed")
            self.assertEqual(final["execution"]["attempt"], 2)

    def test_chat_plan_domain_prompt_creates_ticket(self):
        with tempfile.TemporaryDirectory() as tmp:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = v2.main([
                    "host",
                    "task",
                    "plan",
                    "Dodaj codzienne sprawdzanie ifuri.com, z screenshotem gdy strona nie odpowiada.",
                    "--project",
                    tmp,
                    "--create",
                    "--no-llm",
                ])
            self.assertEqual(code, 0)
            result = __import__("json").loads(buffer.getvalue())
            self.assertFalse(result["dryRun"])
            created = result["createdTickets"][0]
            self.assertEqual(created["execution"]["queue"], "daily")
            self.assertIn("domain", created["labels"])
            self.assertIn("screenshot", created["labels"])
            self.assertIn("ifuri.com", created["inputs"]["prompt"])

    def test_chat_plan_ambiguous_prompt_waits_for_input(self):
        plan = task_planner.plan_chat_request("zrob cos", use_llm=False)
        self.assertTrue(plan.needs_input)
        self.assertTrue(plan.tickets[0].wait_for_input)

        with tempfile.TemporaryDirectory() as tmp:
            created = task_planner.create_tickets_from_plan(tmp, plan)
            self.assertEqual(created[0]["execution"]["state"], "waiting_input")
            self.assertIn("needs-input", created[0]["labels"])

    def test_chat_plan_destructive_prompt_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = task_planner.plan_chat_request("usun rekordy DNS w Namecheap dla ifuri.com", use_llm=False)
            self.assertTrue(plan.requires_review)
            created = task_planner.create_tickets_from_plan(tmp, plan)
            self.assertEqual(created[0]["execution"]["queue"], "review")
            self.assertEqual(created[0]["executor"]["mode"], "interactive")
            self.assertIn("review", created[0]["labels"])


if __name__ == "__main__":
    unittest.main()
