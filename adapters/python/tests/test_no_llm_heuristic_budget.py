"""Ratchet for the deterministic no-LLM fallback.

The no-LLM path is documented coverage, not the autonomy path. These budgets
make it visible when someone grows lexical prompt heuristics to improve a
prompt-matrix score instead of moving the case through LLM + action_space +
router/twin gates.
"""

from __future__ import annotations

import inspect

from urirun.host import task_planner
from urirun_flow import flow_planner


def test_flow_planner_screenshot_heuristic_budget_does_not_grow():
    assert len(flow_planner._SCREENSHOT_KWS) <= 13
    assert len(flow_planner._ALL_MONITOR_KWS) <= 14
    assert len(flow_planner._MONITOR_ORDINALS) <= 12
    assert inspect.getsource(flow_planner._screenshot_capture_payload).count("re.search(") <= 9


def test_ticket_planner_legacy_word_budget_does_not_grow():
    assert len(task_planner.AMBIGUOUS_PHRASES) <= 6
    assert len(task_planner.DESTRUCTIVE_WORDS) <= 12
    assert len(task_planner.DAILY_WORDS) <= 4
    assert len(task_planner.SCREENSHOT_WORDS) <= 3
