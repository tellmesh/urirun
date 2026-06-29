# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Client helpers for the Twin experience-retrieval URI.

Retrieval is PROPOSE-stage context only. This module does not accept, reject or
execute plans; router/contract/env gates remain the hard admission path.
"""

from __future__ import annotations

from typing import Any, Callable


Dispatch = Callable[[str, dict], dict | None]


def recall_env_fingerprint(twin_memory: Any, node: str) -> str:
    """Return the node-specific known-good fingerprint, falling back to host."""
    if twin_memory is None or not hasattr(twin_memory, "known_good"):
        return ""
    for key in (node, "host"):
        fp = (twin_memory.known_good(key) or {}).get("fingerprint")
        if fp:
            return str(fp)
    return ""


def _unwrap_retrieval(result: Any) -> dict:
    if isinstance(result, dict) and isinstance(result.get("result"), dict):
        result = result["result"]
    if not (isinstance(result, dict) and result.get("ok")):
        return {}
    return {key: value for key, value in result.items() if key != "ok"}


def retrieve_experience_context(
    twin_memory: Any,
    selected_nodes: list,
    prompt: str,
    routes: list[dict],
    *,
    dispatch: Dispatch | None = None,
    k: int = 5,
) -> dict:
    """Call ``twin://host/experience/query/retrieve`` and return advisory context.

    Empty dict means no retrieval context. This is deliberately a soft input to
    planning, not a recall short-circuit and not an accepted flow.
    """
    if twin_memory is None:
        return {}
    if dispatch is None:
        from urirun.host.dispatch import inprocess_fallback as dispatch  # noqa: PLC0415
    node = selected_nodes[0] if selected_nodes else "host"
    env_fp = recall_env_fingerprint(twin_memory, node)
    payload = {"intent": prompt, "fingerprint": env_fp, "node": node, "routes": routes, "k": k}
    return _unwrap_retrieval(dispatch("twin://host/experience/query/retrieve", payload) or {})


def make_flow_with_retrieval(
    mesh: Any,
    prompt: str,
    discovered: dict,
    planner_nodes: list[str],
    no_llm: bool,
    environments: list[dict],
    retrieval: dict,
    llm_model: str | None = None,
) -> tuple:
    """Call ``mesh.make_flow`` with retrieval, tolerating older mesh shims."""
    base_kwargs = {
        "selected_nodes": planner_nodes,
        "use_llm": not no_llm,
        "environments": environments,
        "retrieval": retrieval,
    }
    if llm_model:
        base_kwargs["llm_model"] = llm_model
    kwargs = dict(base_kwargs)
    for _ in range(3):
        try:
            return mesh.make_flow(prompt, discovered, **kwargs)
        except TypeError as exc:
            text = str(exc)
            changed = False
            if "llm_model" in text and "llm_model" in kwargs:
                kwargs.pop("llm_model", None)
                changed = True
            if "retrieval" in text and "retrieval" in kwargs:
                kwargs.pop("retrieval", None)
                changed = True
            if not changed:
                raise
    return mesh.make_flow(prompt, discovered, **kwargs)


__all__ = [
    "make_flow_with_retrieval",
    "recall_env_fingerprint",
    "retrieve_experience_context",
]
