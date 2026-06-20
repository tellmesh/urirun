# urirun — Go SDK

Build `urirun.bindings.v2` documents from Go so a Go program can be a urirun
connector (or embed the contract as a library).

```bash
go run ./example/hash-connector > bindings.json
urirun validate bindings.json
urirun compile bindings.json --out registry.json
urirun list registry.json
```

See the cross-language contract at https://docs.ifuri.com/generating-connectors.html
