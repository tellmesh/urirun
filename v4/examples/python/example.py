from urihandler.v4 import (
    build_registry_document,
    discover_docker_labels,
    discover_manifest,
    dispatch_generated,
    hydrate_registry,
    uri_handler,
)


@uri_handler("device://device-01/led/set/on", kind="function", adapter="local-function", ref="devices.led_set")
def led_set(target, args, payload, descriptor):
    return {"ok": True, "target": target, "state": args[0], "payload": payload}


routes = [
    *discover_manifest(
        {
            "routes": [
                {
                    "package": "cli",
                    "resource": "git",
                    "operation": "status",
                    "routeEntry": {"kind": "cli", "adapter": "spawn", "config": {"command": ["git", "status"]}},
                }
            ]
        }
    ),
    *discover_docker_labels(
        {
            "urihandler.uri": "service://api/user/create/basic",
            "urihandler.kind": "http",
            "urihandler.adapter": "fetch",
            "urihandler.method": "POST",
            "urihandler.url": "http://user-service:8080/api/users",
        }
    ),
    {
        "uri": "device://device-01/led/set/on",
        "routeEntry": {"kind": "function", "adapter": "local-function", "ref": "devices.led_set"},
    },
]

registry = build_registry_document(routes)
hydrated = hydrate_registry(registry, {"devices.led_set": led_set})

print(dispatch_generated("device://device-01/led/set/off", hydrated, {"source": "example"}))
print(dispatch_generated("cli://local/git/status", registry))
