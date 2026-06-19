# Pierwsze kroki

Instalacja bezpośrednio z GitHuba:

```bash
pip install "git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
```

Zainstalowane CLI oraz przestrzeń importu w Pythonie to w obu przypadkach `urirun`.

## Wygeneruj registry

Przeskanuj projekt i skompiluj registry runtime jedną komendą:

```bash
urirun scan ./project \
  --out generated/bindings.v8.json \
  --registry-out generated/registry.json
```

Skaner czyta jawne pliki bindingów, etykiety Dockerfile, skrypty paczek,
punkty wejścia Pythona, cele Makefile i skrypty shell.

## Podejrzyj trasy

```bash
urirun validate generated/bindings.v8.json
urirun list generated/registry.json
```

## Uruchom URI

Dla tras typu komenda domyślny jest dry-run:

```bash
urirun run 'cli://local/git/status' --registry generated/registry.json
```

Realne wykonanie wymaga pliku polityki i flagi `--execute`:

```bash
urirun run 'cli://local/git/status' \
  --registry generated/registry.json \
  --policy policy.json \
  --allow 'cli://local/**' \
  --execute
```

Szablony shell trzymaj za jawną polityką z `allowShellTemplates: true`.
