# urihandler v2

A simpler URI handler model based on:

- URI as logical address
- route translation instead of direct function naming
- registry tree lookup
- `.urihandler/` persistent translation cache
- in-memory callable cache

## Route contract

```txt
registry[package][resource][operation](target, args, payload, descriptor)
```

## Examples

- `device://device-01/led/set/on`
- `log://app/info/user-created`

## Included

- `spec/urihandler-v2.md`
- `examples/js/`
- `examples/python/`
- `examples/c/`

## Verify

From the repository root:

```bash
make test-v2
```

## JavaScript import after GitHub install

```js
import { dispatch } from 'urihandler/v2/js';
```
