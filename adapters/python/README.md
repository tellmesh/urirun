# urirun python adapter

Install directly from GitHub:

```bash
pip install "git+https://github.com/tellmesh/urirun.git@main#subdirectory=adapters/python"
```

Or install a GitHub Release wheel:

```bash
pip install "https://github.com/tellmesh/urirun/releases/download/v0.3.4/urirun-0.3.4-py3-none-any.whl"
```

PyPI publishing is not required. The distribution is named `urirun`; the Python
import package remains `urirun`:

```python
import urirun
```

After installation the `urirun` CLI is available:

```bash
urirun scan ./project --out .urirun/bindings.v2.json --registry-out .urirun/registry.merged.json
urirun validate .urirun/bindings.v2.json
urirun list .urirun/registry.merged.json
urirun run 'cli://local/git/status' .urirun/registry.merged.json
```

`urirun-v1` and `urirun-v2` are also installed as explicit versioned entry
points for scripts that need a stable major-version command.

The optional v2 gRPC transport can be installed with:

```bash
pip install "urirun[grpc] @ git+https://github.com/tellmesh/urirun.git@main#subdirectory=adapters/python"
```

v2 can generate schema-first bindings and a compiled registry from existing
artifacts:

```bash
urirun scan ./project \
  --out generated/bindings.v2.json \
  --registry-out generated/registry.json
urirun validate generated/bindings.v2.json
urirun list generated/registry.json
```

Connector packages can also generate bindings directly from decorated Python
functions:

```python
from urirun import v2

@v2.uri_command("httpcheck://host/http/query/status", meta={"connector": "http-check"})
def status_command(url: str, expectStatus: int = 200, timeout: float = 10.0):
    return ["urirun-http-check", "status", "{url}", "--expect-status", "{expectStatus}"]

def urirun_bindings():
    return v2.connector_bindings(connector="http-check")
```


## License

Licensed under Apache-2.0.
