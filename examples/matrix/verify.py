"""Cross-runtime contract verifier for the matrix.

Reads each runtime's emitted bindings (/shared/<name>.json), validates every one
against urirun, reduces each to the language-independent essential contract, and
checks they are byte-for-byte identical to the python reference. Exit non-zero on
any divergence. This is the "runtimes" axis of the matrix.
"""
import json
import sys

from urirun import validate_binding_document

ROUTE = "hash://host/sha256/command/file"


def essential(doc: dict) -> dict:
    b = doc["bindings"][ROUTE]
    schema = b.get("inputSchema", {})
    return {
        "route": ROUTE,
        "kind": b.get("kind"),
        "adapter": b.get("adapter"),
        "argv": list(b.get("argv", [])),
        "required": sorted(schema.get("required", [])),
        "properties": sorted((schema.get("properties") or {}).keys()),
        "additionalProperties": schema.get("additionalProperties"),
    }


def main(paths: list[str]) -> int:
    contracts: dict[str, dict] = {}
    errors = 0
    for path in paths:
        name = path.rsplit("/", 1)[-1].removesuffix(".json")
        try:
            doc = json.load(open(path))
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL] runtime {name:8s} unreadable: {exc}")
            errors += 1
            continue
        result = validate_binding_document(doc)
        if not (result.get("ok") if isinstance(result, dict) else result):
            print(f"  [FAIL] runtime {name:8s} bindings do not validate")
            errors += 1
            continue
        contracts[name] = essential(doc)

    ref = contracts.get("python")
    for name, contract in sorted(contracts.items()):
        if name == "python":
            print(f"  [ok  ] runtime {name:8s} reference contract")
            continue
        if contract == ref:
            print(f"  [ok  ] runtime {name:8s} contract matches python")
        else:
            print(f"  [FAIL] runtime {name:8s} contract differs from python")
            print(f"         python: {json.dumps(ref, sort_keys=True)}")
            print(f"         {name}:  {json.dumps(contract, sort_keys=True)}")
            errors += 1
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
