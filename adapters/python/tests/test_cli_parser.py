"""CLI parser construction (urirun.runtime.cli) — structure + no-import-cycle guard.

The parser builders were split out of v2.py into cli.py. This locks in:
  * cli imports cleanly on its own (regression guard: a module-level v2<->cli back-import
    reintroduced a circular import that only surfaced on `import cli` first);
  * `_build_parser` still wires every top-level command and the nested host/node/connectors
    trees, parsing representative argv to the right dest.
Command routing is in v2.main via args.command (not set_defaults), so parsing is enough.
"""
from urirun.runtime import cli   # direct import — must not trigger a circular import


def test_cli_imports_without_cycle_and_builds():
    parser = cli._build_parser("urirun")
    assert parser is not None


def _commands(parser):
    sub = next(a for a in parser._subparsers._group_actions if a.choices)
    return set(sub.choices)


def test_all_top_level_commands_present():
    parser = cli._build_parser("urirun")
    cmds = _commands(parser)
    for expected in ("doctor", "scan", "compile", "validate", "gen", "connectors",
                     "agent", "host", "node", "run", "list", "version"):
        assert expected in cmds, expected


def test_representative_subcommands_parse_to_right_dest():
    parser = cli._build_parser("urirun")
    cases = [
        (["doctor"], "command", "doctor"),
        (["run", "x://a/b/c/d"], "command", "run"),
        (["host", "probe", "n"], "host_command", "probe"),
        (["host", "task", "list"], "task_command", "list"),
        (["node", "serve"], "node_command", "serve"),
        (["connectors", "list"], "connectors_command", "list"),
    ]
    for argv, dest, expected in cases:
        ns = parser.parse_args(argv)
        assert getattr(ns, dest) == expected, (argv, dest, getattr(ns, dest, None))


def test_inherited_and_typed_args_survive_extraction():
    parser = cli._build_parser("urirun")
    # connectors_common parent contributes --catalog to subcommands
    ns = parser.parse_args(["connectors", "show", "some-id", "--catalog", "https://x"])
    assert ns.catalog == "https://x" and ns.id == "some-id"
    # node serve's repeatable --allow
    ns = parser.parse_args(["node", "serve", "--allow", "a://**", "--allow", "b://**"])
    assert ns.allow == ["a://**", "b://**"]
