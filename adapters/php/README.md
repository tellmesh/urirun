# urirun — PHP SDK

Build `urirun.bindings.v2` documents from PHP so a PHP program can be a urirun
connector (or embed the contract as a library).

```bash
php example/hash-connector.php > bindings.json
urirun validate bindings.json
urirun compile bindings.json --out registry.json
```

See the cross-language contract at https://docs.ifuri.com/generating-connectors.html
