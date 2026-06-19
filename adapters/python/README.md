# urirun python adapter

Install directly from GitHub:

```bash
pip install "git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
```

Or install a GitHub Release wheel:

```bash
pip install "https://github.com/tellmesh/urihandler/releases/download/v0.3.4/urirun-0.3.4-py3-none-any.whl"
```

PyPI publishing is not required. The distribution is named `urirun`; the Python
import package remains `urirun`:

```python
import urirun
```

After installation the `urirun` CLI is available:

```bash
urirun scan ./project --out .urirun/bindings.v8.json --registry-out .urirun/registry.merged.json
urirun validate .urirun/bindings.v8.json
urirun list .urirun/registry.merged.json
urirun run 'cli://local/git/status' .urirun/registry.merged.json
```

`urirun-v7` and `urirun-v8` are also installed as explicit versioned entry
points for scripts that need a stable major-version command.

The optional v8 gRPC transport can be installed with:

```bash
pip install "urirun[grpc] @ git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
```

v8 can generate schema-first bindings and a compiled registry from existing
artifacts:

```bash
urirun scan ./project \
  --out generated/bindings.v8.json \
  --registry-out generated/registry.json
urirun validate generated/bindings.v8.json
urirun list generated/registry.json
```


## License

Licensed under Apache-2.0.
