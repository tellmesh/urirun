# Dokumentacja urirun

`urirun` to CLI dla pakietów komend adresowanych przez URI. Projekt deklaruje URI
raz i wywołuje je z shella, backendu, frontendu, przepływu usług albo projekcji
narzędzi dla agenta.

## Zacznij tutaj

- [Pierwsze kroki](getting-started.md) - instalacja z GitHuba, skan artefaktów,
  kompilacja registry i uruchomienie URI.
- [Nazewnictwo](naming.md) - co używa `urirun` i dlaczego URL repozytorium na
  GitHubie nadal zawiera `urihandler`.
- [Komendy](commands.md) - komendy CLI i wersjonowane punkty wejścia.
- [Registry i bindingi](registry-and-bindings.md) - jak bindingi stają się
  wykonywalnym registry.
- [Transporty](transports.md) - funkcje lokalne, shell, Docker, HTTP, gRPC,
  przeglądarka, MCP i A2A.
- [Logo](logo.md) - wygenerowane zasoby SVG i uwagi do użycia.
- [Roadmap](roadmap.md) - praktyczna lista TODO ułatwiająca pracę z narzędziem.

## Bieżąca rekomendacja

Dla nowych projektów używaj v8:

```bash
pip install "git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
urirun scan ./project --out generated/bindings.v8.json --registry-out generated/registry.json
urirun list generated/registry.json
```

v7 trzymaj tylko dla starszych przykładów zależnych od pierwszego kontraktu
wiązania parametrów.
