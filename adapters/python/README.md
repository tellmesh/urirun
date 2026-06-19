# urihandler python adapter

Install directly from GitHub:

```bash
pip install "git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
```

After installation the `urihandler` CLI is available:

```bash
urihandler discover manifest ./urihandler-routes.json --out /tmp/manifest.registry.json
urihandler build-registry /tmp/manifest.registry.json --out .urihandler/registry.merged.json
urihandler call 'cli://local/git/status' --registry .urihandler/registry.merged.json
```
