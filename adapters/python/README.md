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
import package remains `urihandler`:

```python
import urihandler
```

After installation the `urirun` CLI is available:

```bash
urirun scan ./project --out .urihandler/bindings.v8.json --registry-out .urihandler/registry.merged.json
urirun validate .urihandler/bindings.v8.json
urirun list .urihandler/registry.merged.json
urirun run 'cli://local/git/status' .urihandler/registry.merged.json
```

`urirun-v7` and `urirun-v8` are also installed as explicit versioned entry
points. Compatibility aliases `urihandler-v7` and `urihandler-v8` are kept for
existing v7/v8 scripts.

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
