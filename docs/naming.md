# Naming

The public runtime name is `urirun`. The GitHub repository URL is still
`tellmesh/urihandler`.

## Use `urirun` for runtime surfaces

Use `urirun` for:

- Python distribution name
- Python import namespace
- JS package name and imports
- primary CLI command
- versioned CLI commands
- JSON document versions
- Docker/OCI labels
- C firmware adapter files
- documentation title
- logo and website branding

Recommended commands:

```bash
urirun --help
urirun scan ./project
urirun validate generated/bindings.v8.json
urirun list generated/registry.json
urirun run 'tool://local/report/render' --registry generated/registry.json
```

Version-specific CLIs are also available:

```bash
urirun-v7 --help
urirun-v8 --help
```

Examples:

```python
from urirun import v8
from urirun.v8 import uri_command
```

```js
import { parseUri } from "urirun";
```

```json
{ "version": "urirun.bindings.v8" }
```

```dockerfile
LABEL io.tellmesh.urirun.manifest="/app/bindings.json"
```

## Keep `urihandler` only for the repository URL

The current remote is:

```txt
git@github.com:tellmesh/urihandler.git
```

That is why install commands still use:

```bash
pip install "git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
npm install github:tellmesh/urihandler
```

Historical changelog entries can also mention `urihandler`.
