"""Guard: `import urirun` must bind to the real package, never the bare `urirun/` namespace shell
at the monorepo root. If this fails, the root conftest.py path-shim is missing/ineffective and the
"module 'urirun' has no attribute 'connector'" footgun is back. See RETROSPECTIVE.md (#1)."""
import urirun


def test_urirun_is_the_real_package_not_a_namespace_shadow():
    assert urirun.__file__ is not None, (
        "urirun resolved to a namespace shell (the root urirun/ dir shadows the package); "
        "root conftest.py should prepend urirun/adapters/python to sys.path"
    )
    # the SDK surface the connectors rely on
    assert hasattr(urirun, "connector"), "urirun.connector missing — wrong (shadowed) package"
    assert hasattr(urirun, "run") and hasattr(urirun, "tag")
