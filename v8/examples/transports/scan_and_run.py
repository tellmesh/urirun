"""Simple scan & run: point at a source, name a URI, pick a transport.

    python scan_and_run.py <dir|bindings.json|registry.json> <uri> [--payload JSON]
                           [--transport inprocess|http|grpc] [--target host] [--execute]

`<source>` is scanned/compiled in memory (directory), or loaded (bindings or
registry). The same call works over any transport because the registry is the
contract.
"""

from __future__ import annotations

import argparse
import json
import sys

from urihandler import v8, v8_service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scan-and-run")
    parser.add_argument("source", help="project dir, v8 bindings file, or registry document")
    parser.add_argument("uri")
    parser.add_argument("--payload", default="{}")
    parser.add_argument("--transport", choices=["inprocess", "http", "grpc"], default="inprocess")
    parser.add_argument("--target", help="host for http/grpc transport (else URI target)")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    registry = v8.load_registry_arg(args.source)          # <-- the scan/compile step
    payload = json.loads(args.payload)
    mode = "execute" if args.execute else "dry-run"

    if args.transport == "inprocess":
        policy = {"execute": {"allow": [args.uri]}} if args.execute else None
        result = v8.run(args.uri, registry, payload=payload, mode=mode, policy=policy)
    elif args.transport == "http":
        result = v8_service.call(args.uri, payload, registry, target=args.target, mode=mode)
    else:
        from urihandler import v8_grpc
        result = v8_grpc.call(args.uri, payload, registry, target=args.target, mode=mode)

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
