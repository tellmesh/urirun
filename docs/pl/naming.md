# Nazewnictwo

Publiczna nazwa runtime to `urirun`. URL repozytorium na GitHubie to nadal
`tellmesh/urihandler`.

## Używaj `urirun` dla powierzchni runtime

Używaj `urirun` dla:

- nazwy dystrybucji Pythona
- przestrzeni importu w Pythonie
- nazwy i importów paczki JS
- głównej komendy CLI
- wersjonowanych komend CLI
- wersji dokumentów JSON
- etykiet Docker/OCI
- plików adaptera C dla firmware
- tytułu dokumentacji
- logo i identyfikacji strony

Zalecane komendy:

```bash
urirun --help
urirun scan ./project
urirun validate generated/bindings.v8.json
urirun list generated/registry.json
urirun run 'tool://local/report/render' --registry generated/registry.json
```

Dostępne są też CLI dla konkretnych wersji:

```bash
urirun-v7 --help
urirun-v8 --help
```

Przykłady:

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

## `urihandler` zostaje tylko w URL repozytorium

Bieżący remote to:

```txt
git@github.com:tellmesh/urihandler.git
```

Dlatego komendy instalacji nadal używają:

```bash
pip install "git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
npm install github:tellmesh/urihandler
```

Historyczne wpisy w changelogu również mogą wspominać `urihandler`.
