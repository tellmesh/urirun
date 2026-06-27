# urirun python adapter

Install from PyPI (the published wheel is self-contained — it bundles the
kernel and the extracted runtime packages):

```bash
pip install urirun
```

Or install from source for an unreleased commit:

```bash
pip install "git+https://github.com/if-uri/urirun.git#subdirectory=adapters/python"
```

The distribution is named `urirun`; the Python import package remains `urirun`:

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
pip install "urirun[grpc]"
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

Connector packages can generate bindings directly from decorated Python
functions. The shortest path is to declare the connector once and then attach
short URI paths to functions:

```python
import urirun

connector = urirun.connector("http-check", scheme="httpcheck")

@connector.command("http/query/status")
def status_command(url: str, expectStatus: int = 200, timeout: float = 10.0):
    return ["urirun-http-check", "status", "{url}", "--expect-status", "{expectStatus}"]

def urirun_bindings():
    return connector.bindings()
```


## License

Licensed under Apache-2.0.
