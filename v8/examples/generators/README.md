# v8 binding generators

These examples show the same v8 binding contract generated from several
language-native declaration styles:

- `js/` - plain JavaScript helper, no transpiler
- `nodejs/` - Node.js script that writes a binding document
- `ts/` - TypeScript decorator-style declaration
- `php/` - PHP 8 attribute + reflection

All examples generate the same shape:

```json
{
  "version": "urirun.bindings.v8",
  "bindings": {
    "scheme://target/resource/operation": {
      "kind": "command",
      "adapter": "argv-template",
      "inputSchema": {},
      "argv": []
    }
  }
}
```

The runtime does not care which language generated the file. It only consumes
the v8 JSON contract.
