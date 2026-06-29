from __future__ import annotations

import ast
from pathlib import Path

from urirun_twin.experience_retrieval import (
    make_flow_with_retrieval,
    recall_env_fingerprint,
    retrieve_experience_context,
)


def test_recall_env_fingerprint_prefers_node_then_host():
    class Memory:
        def known_good(self, node):
            return {"fingerprint": f"fp-{node}"} if node == "host" else {}

    assert recall_env_fingerprint(Memory(), "lenovo") == "fp-host"


def test_retrieve_experience_context_calls_twin_uri_and_unwraps_result():
    calls = []

    class Memory:
        def known_good(self, node):
            return {"fingerprint": "env-1"}

    def dispatch(uri, payload):
        calls.append((uri, payload))
        return {"ok": True, "result": {"ok": True, "kind": "experience-retrieval", "episodes": []}}

    result = retrieve_experience_context(
        Memory(),
        ["host"],
        "zrob zrzut",
        [{"uri": "kvm://host/screen/query/capture"}],
        dispatch=dispatch,
    )

    assert calls[0][0] == "twin://host/experience/query/retrieve"
    assert calls[0][1]["fingerprint"] == "env-1"
    assert result == {"kind": "experience-retrieval", "episodes": []}


def test_make_flow_with_retrieval_falls_back_for_old_mesh_signature():
    class Mesh:
        def __init__(self):
            self.calls = []

        def make_flow(self, *args, **kwargs):
            self.calls.append(kwargs)
            if "retrieval" in kwargs:
                raise TypeError("unexpected keyword argument 'retrieval'")
            return {"steps": []}, {"provider": "test"}

    mesh = Mesh()
    flow, generator = make_flow_with_retrieval(mesh, "prompt", {"routes": []}, ["host"], False, [], {"routes": []})

    assert flow == {"steps": []}
    assert generator == {"provider": "test"}
    assert "retrieval" in mesh.calls[0]
    assert "retrieval" not in mesh.calls[1]


def test_make_flow_with_retrieval_forwards_llm_model_to_new_mesh():
    class Mesh:
        def __init__(self):
            self.kwargs = None

        def make_flow(self, *args, **kwargs):
            self.kwargs = kwargs
            return {"steps": []}, {"provider": "test"}

    mesh = Mesh()
    flow, generator = make_flow_with_retrieval(
        mesh, "prompt", {"routes": []}, ["host"], False, [], {"episodes": []},
        llm_model="request/model")

    assert flow == {"steps": []}
    assert generator == {"provider": "test"}
    assert mesh.kwargs["retrieval"] == {"episodes": []}
    assert mesh.kwargs["llm_model"] == "request/model"


def test_make_flow_with_retrieval_falls_back_for_old_mesh_without_model_or_retrieval():
    class Mesh:
        def __init__(self):
            self.calls = []

        def make_flow(self, *args, **kwargs):
            self.calls.append(dict(kwargs))
            if "llm_model" in kwargs:
                raise TypeError("unexpected keyword argument 'llm_model'")
            if "retrieval" in kwargs:
                raise TypeError("unexpected keyword argument 'retrieval'")
            return {"steps": []}, {"provider": "test"}

    mesh = Mesh()
    flow, generator = make_flow_with_retrieval(
        mesh, "prompt", {"routes": []}, ["host"], False, [], {"episodes": []},
        llm_model="request/model")

    assert flow == {"steps": []}
    assert generator == {"provider": "test"}
    assert "llm_model" in mesh.calls[0]
    assert "retrieval" in mesh.calls[1]
    assert "llm_model" not in mesh.calls[-1]
    assert "retrieval" not in mesh.calls[-1]


def test_chat_orchestrator_does_not_define_experience_retrieval_helpers():
    path = Path(__file__).resolve().parents[1] / "urirun" / "host" / "chat_orchestrator.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "_retrieve_experience_context" not in defined
    assert "_make_flow_with_retrieval" not in defined
