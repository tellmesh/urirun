"""Guard the Phase 5 flow extraction.

``urirun.node.flow`` is a compatibility import path. The flow engine lives in
``urirun_flow.flow`` and this module must stay an alias, not a second
implementation.
"""


def test_node_flow_is_the_real_source_module():
    import urirun.node.flow as shim
    import urirun_flow.flow as real

    assert shim is real
