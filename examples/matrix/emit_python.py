"""Python runtime column: emit the shared hash connector's urirun.bindings.v2.

Mirrors adapters/conformance.py's python reference so the contract is identical
to every other runtime in the matrix.
"""
import json

import urirun

c = urirun.connector("hash", scheme="hash")


@c.command("sha256/command/file")
def f(path: str):  # noqa: ARG001 - the signature IS the input schema
    return ["sha256sum", "{path}"]


if __name__ == "__main__":
    print(json.dumps(c.bindings()))
