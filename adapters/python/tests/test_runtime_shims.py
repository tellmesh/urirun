# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Guards the Phase 5 kernel extraction: urirun/runtime/* are shims onto the urirun-runtime package.
# A shim must make urirun.runtime.X BE urirun_runtime.X (every symbol, public AND private), so the
# 36 importers that do `from urirun.runtime import X` keep resolving unchanged. If a shim regresses
# (e.g. back to `from … import *`, which drops private names like _pool_executors), this fails fast.
import subprocess
import sys
import unittest

_MODULES = ["_registry", "_runtime", "v2", "v2_service", "worker", "dispatch_protocol",
            "discovery", "daemon", "errors", "progress"]


class RuntimeShimIdentityTests(unittest.TestCase):
    def test_shim_is_the_real_package_module(self):
        import importlib
        for name in _MODULES:
            shim = importlib.import_module(f"urirun.runtime.{name}")
            real = importlib.import_module(f"urirun_runtime.{name}")
            self.assertIs(shim, real, f"urirun.runtime.{name} is not urirun_runtime.{name}")

    def test_from_import_resolves_to_real_module(self):
        from urirun.runtime import v2, worker, _registry
        import urirun_runtime.v2, urirun_runtime.worker, urirun_runtime._registry
        self.assertIs(v2, urirun_runtime.v2)
        self.assertIs(worker, urirun_runtime.worker)
        self.assertIs(_registry, urirun_runtime._registry)

    def test_private_cross_module_symbols_are_re_exported(self):
        # the risky part: a `import *` shim would drop these underscore-prefixed names that
        # node/host importers actually use — the sys.modules shim keeps them.
        from urirun.runtime import worker, v2
        self.assertTrue(hasattr(worker, "_pool_executors"))
        self.assertTrue(hasattr(v2, "EXECUTORS"))

    def test_dash_m_cli_delegates_to_the_real_module(self):
        # `python -m urirun.runtime.daemon` must reach the real CLI (runpy delegation), not the
        # no-op shim body. Expect the daemon usage line on stderr.
        proc = subprocess.run([sys.executable, "-m", "urirun.runtime.daemon"],
                              capture_output=True, text=True, timeout=30)
        self.assertIn("usage", (proc.stderr + proc.stdout).lower())


if __name__ == "__main__":
    unittest.main()
