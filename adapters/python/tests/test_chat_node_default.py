"""Tests for _apply_host_default_when_no_node_in_prompt — 'if prompt doesn't say which node, use host'."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from urirun.host import chat_orchestrator as co
from urirun.host.chat_orchestrator import _apply_host_default_when_no_node_in_prompt
from urirun.node.reversible import TwinMemory


def _deps(alias_map: dict) -> MagicMock:
    d = MagicMock()
    d.node_alias_map_fn.return_value = alias_map
    return d


ALIAS = {"lenovo": "lenovo", "laptop": "lenovo"}


class TestHostDefault(unittest.TestCase):

    def _call(self, prompt, selected_nodes, selected_targets, alias_map=None):
        deps = _deps(alias_map or ALIAS)
        return _apply_host_default_when_no_node_in_prompt(
            prompt, selected_nodes, selected_targets, None, None, deps)

    def _chat_ask_selection(self, payload):
        messages = []
        deps = co.ChatDeps(
            host_db_fn=MagicMock(),
            mesh_fn=MagicMock(),
            host_config_fn=MagicMock(return_value={}),
            node_alias_map_fn=MagicMock(return_value=ALIAS),
            add_chat_message_fn=lambda db, msg: messages.append(msg),
            page_action_enqueue_fn=MagicMock(),
            ensure_phone_scanner_fn=MagicMock(),
            sync_documents_fn=MagicMock(),
        )

        def fake_general(project, db, config, payload, node_urls, token, identity,
                         prompt, execute, no_llm, selected_nodes, selected_targets, deps):
            return {"ok": True, "selectedNodes": selected_nodes, "selectedTargets": selected_targets}

        with patch.object(co, "_chat_insert_twin_preview", lambda *a, **k: None), \
             patch.object(co, "_chat_ask_general", fake_general):
            result = co.chat_ask("proj", "db", None, payload, [], None, None, deps)
        return result, messages

    def test_chat_ask_url_tab_autorun_filters_remote_routes_before_planning(self):
        messages = []
        captured = {}

        class FakeMesh:
            def discover_mesh(self, _config):
                return {
                    "nodes": [{"name": "lenovo", "url": "http://192.168.1.10:8765", "reachable": True}],
                    "routes": [
                        {"uri": "time://host/clock/query/now", "node": "host"},
                        {"uri": "kvm://host/ui/command/click", "node": "lenovo"},
                    ],
                    "serviceMap": {"time": "local", "kvm": "http://192.168.1.10:8765"},
                }

            def registry_from_routes(self, routes):
                return {"routes": routes}

            def fetch_planner_environments(self, *args, **kwargs):
                return []

            def make_flow(self, prompt, discovered, selected_nodes=None, use_llm=True, environments=None):
                captured["routes"] = [r["uri"] for r in discovered.get("routes") or []]
                captured["selected_nodes"] = selected_nodes
                return (
                    {"steps": [{"id": "now", "uri": "time://host/clock/query/now", "payload": {}}]},
                    {"provider": "test"},
                )

            def execute_flow(self, *args, **kwargs):
                return {
                    "ok": True,
                    "timeline": [{"id": "now", "uri": "time://host/clock/query/now", "ok": True}],
                    "results": {"now": {"ok": True, "result": {"value": {"ok": True}}}},
                }

        deps = co.ChatDeps(
            host_db_fn=MagicMock(),
            mesh_fn=FakeMesh,
            host_config_fn=MagicMock(return_value={}),
            node_alias_map_fn=MagicMock(return_value=ALIAS),
            add_chat_message_fn=lambda db, msg: messages.append(msg),
            page_action_enqueue_fn=MagicMock(),
            ensure_phone_scanner_fn=MagicMock(),
            sync_documents_fn=MagicMock(),
        )
        payload = {
            "prompt": "która godzina",
            "nodes": ["lenovo"],
            "targets": ["host", "node:lenovo"],
            "target_explicit": False,
            "execute": False,
            "no_llm": True,
        }

        with patch.object(co, "_chat_insert_twin_preview", lambda *a, **k: None), \
             patch.object(co, "capture_episode", lambda **k: {}), \
             patch.object(co, "append_twin_widget", lambda *a, **k: None), \
             patch.object(co, "local_entry_point_host_routes", lambda: []):
            result = co.chat_ask("proj", "db", None, payload, [], None, None, deps)

        self.assertEqual(result["selectedTargets"], ["host"])
        self.assertEqual(captured["routes"], ["time://host/clock/query/now"])
        self.assertEqual(captured["selected_nodes"], ["host"])

    def test_chat_execute_enables_router_guard(self):
        messages = []
        captured = {}

        class FakeMesh:
            def discover_mesh(self, _config):
                return {
                    "nodes": [],
                    "routes": [{"uri": "time://host/clock/query/now", "node": "host", "safe": True}],
                    "serviceMap": {},
                }

            def registry_from_routes(self, routes):
                return {"routes": routes}

            def fetch_planner_environments(self, *args, **kwargs):
                return []

            def make_flow(self, prompt, discovered, selected_nodes=None, use_llm=True, environments=None):
                return (
                    {"steps": [{"id": "now", "uri": "time://host/clock/query/now", "payload": {}}]},
                    {"provider": "test"},
                )

            def execute_flow(self, *args, **kwargs):
                captured["router_guard"] = kwargs.get("router_guard")
                return {
                    "ok": True,
                    "timeline": [{"id": "now", "uri": "time://host/clock/query/now", "ok": True}],
                    "results": {"now": {"ok": True, "result": {"value": {"ok": True}}}},
                }

        deps = co.ChatDeps(
            host_db_fn=MagicMock(),
            mesh_fn=FakeMesh,
            host_config_fn=MagicMock(return_value={}),
            node_alias_map_fn=MagicMock(return_value=ALIAS),
            add_chat_message_fn=lambda db, msg: messages.append(msg),
            page_action_enqueue_fn=MagicMock(),
            ensure_phone_scanner_fn=MagicMock(),
            sync_documents_fn=MagicMock(),
        )

        with patch.object(co, "_try_recall_gate", lambda *a, **k: (None, None)), \
             patch.object(co, "_suggest_recall_for_memory", lambda *a, **k: None), \
             patch.object(co, "capture_episode", lambda **k: {}), \
             patch.object(co, "append_twin_widget", lambda *a, **k: None):
            result = co._chat_ask_general(
                "proj", "db", None,
                {"prompt": "która godzina", "targets": ["host"], "execute": True},
                [], None, None, "która godzina", True, True, [], ["host"], deps,
            )

        self.assertTrue(result["ok"])
        self.assertIs(result["noLlm"], True)
        self.assertIs(captured["router_guard"], True)
        system = [m for m in messages if m.get("role") == "system"][-1]
        self.assertIs(system.get("detail", {}).get("noLlm"), True)

    def test_capture_preference_applies_only_to_ambiguous_capture(self):
        mem = TwinMemory()
        fp = mem.remember("host", {"platform": "linux", "display": {"width": 1, "height": 1}})["fingerprint"]
        mem.remember_preference("host", "screen.capture.default", {"scope": "all", "monitor": -1}, fp)
        flow = {"steps": [{"id": "cap", "uri": "kvm://host/screen/query/capture", "payload": {}}]}

        updated = co._apply_capture_preferences(flow, mem)

        self.assertEqual(updated["steps"][0]["payload"], {"scope": "all", "monitor": -1})

        explicit = {"steps": [{"id": "cap", "uri": "kvm://host/screen/query/capture", "payload": {"monitor": 2}}]}
        explicit_updated = co._apply_capture_preferences(explicit, mem)
        self.assertEqual(explicit_updated["steps"][0]["payload"], {"monitor": 2})

    def test_successful_explicit_capture_remembers_preference(self):
        mem = TwinMemory()
        fp = mem.remember("host", {"platform": "linux", "display": {"width": 1, "height": 1}})["fingerprint"]
        flow = {"steps": [{"id": "cap", "uri": "kvm://host/screen/query/capture",
                           "payload": {"scope": "all", "monitor": -1}}]}

        co._remember_capture_preferences(flow, {"ok": True}, mem)

        pref = mem.recall_preference("host", "screen.capture.default", fp)
        self.assertIsNotNone(pref)
        self.assertEqual(pref["value"], {"scope": "all", "monitor": -1})

    def test_env_enum_resolution_requests_selection_for_ambiguous_monitor(self):
        flow = {"steps": [{"id": "cap", "uri": "kvm://host/screen/query/capture", "payload": {}}]}
        routes = [{
            "uri": "kvm://host/screen/query/capture",
            "meta": {"contract": {"domains": {"monitor": {
                "type": "enum",
                "domain": "env:monitors.id",
                "emptyValues": [0, ""],
                "preference": "screen.capture.default",
            }}}},
        }]

        with patch("urirun_flow.flow._build_env_inventory", return_value={
            "node": "host",
            "fingerprint": "env-two",
            "domains": {"env:monitors.id": [
                {"value": 1, "label": "HDMI-1"},
                {"value": 2, "label": "DP-2"},
            ]},
        }):
            selection = co._resolve_env_enum_flow(flow, {}, routes, TwinMemory())

        self.assertFalse(selection["ok"])
        self.assertEqual(selection["kind"], "needs-selection")
        self.assertEqual(selection["needsSelection"]["parameter"], "monitor")

    def test_chat_emits_routing_plan_before_execute(self):
        messages = []
        events = []

        class FakeMesh:
            def discover_mesh(self, _config):
                return {
                    "nodes": [{"name": "lenovo", "url": "http://192.168.1.10:8765", "reachable": True}],
                    "routes": [{
                        "uri": "kvm://host/screen/query/capture",
                        "node": "lenovo",
                        "safe": True,
                    }],
                    "serviceMap": {},
                }

            def registry_from_routes(self, routes):
                return {"routes": routes}

            def fetch_planner_environments(self, *args, **kwargs):
                return []

            def make_flow(self, prompt, discovered, selected_nodes=None, use_llm=True, environments=None):
                return (
                    {"steps": [{"id": "cap", "uri": "kvm://host/screen/query/capture", "payload": {}}]},
                    {"provider": "test"},
                )

            def execute_flow(self, *args, **kwargs):
                events.append("execute")
                return {
                    "ok": True,
                    "timeline": [{"id": "cap", "uri": "kvm://host/screen/query/capture", "ok": True}],
                    "results": {"cap": {"ok": True, "result": {"value": {"ok": True}}}},
                }

        def add_message(db, msg):
            messages.append(msg)
            if msg.get("detail", {}).get("kind") == "routing-plan":
                events.append("routing-plan")

        deps = co.ChatDeps(
            host_db_fn=MagicMock(),
            mesh_fn=FakeMesh,
            host_config_fn=MagicMock(return_value={}),
            node_alias_map_fn=MagicMock(return_value=ALIAS),
            add_chat_message_fn=add_message,
            page_action_enqueue_fn=MagicMock(),
            ensure_phone_scanner_fn=MagicMock(),
            sync_documents_fn=MagicMock(),
        )

        with patch.object(co, "_try_recall_gate", lambda *a, **k: (None, None)), \
             patch.object(co, "_suggest_recall_for_memory", lambda *a, **k: None), \
             patch.object(co, "capture_episode", lambda **k: {}), \
             patch.object(co, "append_twin_widget", lambda *a, **k: None):
            result = co._chat_ask_general(
                "proj", "db", None,
                {"prompt": "zrób zrzut ekranu na lenovo", "targets": ["node:lenovo"], "execute": True},
                [], None, None, "zrób zrzut ekranu na lenovo", True, True, ["lenovo"], ["node:lenovo"], deps,
            )

        routing_messages = [m for m in messages if m.get("detail", {}).get("kind") == "routing-plan"]
        self.assertTrue(result["ok"])
        self.assertEqual(events[:2], ["routing-plan", "execute"])
        self.assertEqual(len(routing_messages), 1)
        routing = routing_messages[0]["detail"]["routing"]
        self.assertEqual(routing["runsOnByStep"]["kvm://host/screen/query/capture"], "lenovo")

    def test_no_node_in_prompt_strips_remote(self):
        nodes, targets = self._call(
            "opublikuj post na LinkedIn",
            ["lenovo"], ["host", "node:lenovo"])
        self.assertEqual(targets, ["host"])
        self.assertEqual(nodes, [])

    def test_chat_ask_defaults_to_host_even_with_stale_dashboard_node_selection(self):
        payload = {
            "prompt": "opublikuj post na LinkedIn",
            "nodes": ["lenovo"],
            "targets": ["host", "node:lenovo"],
            "execute": True,
        }
        result, messages = self._chat_ask_selection(payload)

        self.assertEqual(result["selectedNodes"], [])
        self.assertEqual(result["selectedTargets"], ["host"])
        self.assertEqual(messages[0]["detail"]["resolvedNodes"], [])
        self.assertEqual(messages[0]["detail"]["resolvedTargets"], ["host"])

    def test_chat_ask_url_tab_autorun_defaults_to_host_when_prompt_omits_node(self):
        payload = {
            "prompt": "opublikuj post na LinkedIn",
            "nodes": ["lenovo"],
            "targets": ["host", "node:lenovo"],
            "target_explicit": False,
            "execute": True,
        }
        result, messages = self._chat_ask_selection(payload)

        self.assertEqual(result["selectedNodes"], [])
        self.assertEqual(result["selectedTargets"], ["host"])
        self.assertEqual(messages[0]["detail"]["resolvedNodes"], [])
        self.assertEqual(messages[0]["detail"]["resolvedTargets"], ["host"])

    def test_chat_ask_records_request_model_in_user_message(self):
        result, messages = self._chat_ask_selection({
            "prompt": "zrob zrzut ekranu",
            "targets": ["host"],
            "execute": True,
            "model": "request/model",
        })

        self.assertEqual(result["selectedTargets"], ["host"])
        self.assertEqual(messages[0]["detail"]["model"], "request/model")

    def test_chat_ask_url_tab_autorun_infers_node_from_prompt_not_stale_url(self):
        payload = {
            "prompt": "opublikuj post na LinkedIn na lenovo",
            "nodes": ["old-node"],
            "targets": ["host", "node:old-node"],
            "target_explicit": False,
            "execute": True,
        }
        result, messages = self._chat_ask_selection(payload)

        self.assertEqual(result["selectedNodes"], ["lenovo"])
        self.assertEqual(result["selectedTargets"], ["node:lenovo"])
        self.assertEqual(messages[0]["detail"]["resolvedNodes"], ["lenovo"])
        self.assertEqual(messages[0]["detail"]["resolvedTargets"], ["node:lenovo"])

    def test_chat_ask_host_default_infers_node_from_prompt(self):
        payload = {
            "prompt": "otworz przegladarke i zrob zrzut ekranu na node lenovo laptop",
            "targets": ["host"],
            "execute": True,
        }
        result, messages = self._chat_ask_selection(payload)

        self.assertEqual(result["selectedNodes"], ["lenovo"])
        self.assertEqual(result["selectedTargets"], ["node:lenovo"])
        self.assertEqual(messages[0]["detail"]["requestedTargets"], ["host"])
        self.assertEqual(messages[0]["detail"]["resolvedNodes"], ["lenovo"])
        self.assertEqual(messages[0]["detail"]["resolvedTargets"], ["node:lenovo"])

    def test_chat_ask_named_offline_node_emits_human_task_with_beep(self):
        messages = []

        class FakeMesh:
            def discover_mesh(self, _config):
                return {
                    "nodes": [{"name": "lenovo", "url": "http://lenovo:8765", "reachable": False}],
                    "routes": [{"uri": "human://host/task/create", "node": "host", "nodeUrl": "http://host:8765"}],
                    "serviceMap": {},
                }

        deps = co.ChatDeps(
            host_db_fn=MagicMock(),
            mesh_fn=FakeMesh,
            host_config_fn=MagicMock(return_value={}),
            node_alias_map_fn=MagicMock(return_value=ALIAS),
            add_chat_message_fn=lambda db, msg: messages.append(msg),
            page_action_enqueue_fn=MagicMock(),
            ensure_phone_scanner_fn=MagicMock(),
            sync_documents_fn=MagicMock(),
        )
        payload = {
            "prompt": "otworz przegladarke i zrob zrzut ekranu na node lenovo laptop",
            "targets": ["host"],
            "execute": True,
            "no_llm": True,
        }
        human_env = {
            "ok": True,
            "result": {
                "value": {
                    "task": {"id": "task-1"},
                    "surface": {"queueUrl": "/tasks", "url": "/tasks"},
                    "next": {},
                }
            },
        }

        with patch.object(co, "_chat_insert_twin_preview", lambda *a, **k: None), \
             patch("urirun.host.node_dispatch.run_node_uri", return_value=human_env):
            result = co.chat_ask("proj", "db", None, payload, [], None, None, deps)

        self.assertFalse(result["ok"])
        self.assertTrue(result["humanEscalation"])
        self.assertEqual(result["selectedTargets"], ["node:lenovo"])
        system = [m for m in messages if m.get("role") == "system"][-1]
        self.assertEqual(system["detail"]["kind"], "human-task")
        self.assertEqual(system["detail"]["notify"]["sound"], "beep")
        self.assertEqual(system["detail"]["humanTask"]["targetNode"], "lenovo")

    def test_node_name_in_prompt_keeps_remote(self):
        nodes, targets = self._call(
            "opublikuj post na LinkedIn na lenovo",
            ["lenovo"], ["host", "node:lenovo"])
        self.assertEqual(targets, ["host", "node:lenovo"])

    def test_alias_in_prompt_keeps_remote(self):
        # "laptop" (exact alias) must appear; inflected "laptopie" does NOT match
        nodes, targets = self._call(
            "otwórz stronę na laptop",
            ["lenovo"], ["host", "node:lenovo"])
        self.assertEqual(targets, ["host", "node:lenovo"])

    def test_remote_keyword_keeps_remote(self):
        nodes, targets = self._call(
            "zrób zrzut ekranu na zdalnym komputerze",
            ["lenovo"], ["host", "node:lenovo"])
        self.assertEqual(targets, ["host", "node:lenovo"])

    def test_local_keyword_already_host_unchanged(self):
        nodes, targets = self._call(
            "zrób zrzut ekranu na lokalnym komputerze",
            [], ["host"])
        self.assertEqual(targets, ["host"])
        self.assertEqual(nodes, [])

    def test_already_host_only_unchanged(self):
        nodes, targets = self._call(
            "zrób cokolwiek",
            [], ["host"])
        self.assertEqual(targets, ["host"])

    def test_remote_keyword_zdalny(self):
        nodes, targets = self._call(
            "otwórz zdalny terminal",
            ["lenovo"], ["host", "node:lenovo"])
        self.assertEqual(targets, ["host", "node:lenovo"])


if __name__ == "__main__":
    unittest.main()
