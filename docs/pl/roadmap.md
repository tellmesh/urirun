# Roadmap

Najbardziej przydatne kolejne prace ułatwiające `urirun`:

- Dodać `urirun init` jako komendę-przewodnik zapisującą domyślne `.urirun/`,
  przykładową politykę i przykładowy binding.
- Dodać `urirun doctor` sprawdzające wersję Pythona, opcjonalne zależności,
  Docker, PHP, Node, świeżość wygenerowanego registry i zduplikowane konflikty
  tras.
- Dodać `urirun serve` jako jedną komendę konsoli HTTP do logów, listowania
  tras, dry-runów i realnego wykonania za polityką.
- Dodać kanoniczny loader `.env` współdzielony przez przykłady, aby porty i
  ścieżki registry miały jedno źródło prawdy.
- Dodać pełnoprawne trasy `log://` dla frontendu, backendu, shella, firmware i
  usług Docker.
- Dodać komendę diff registry: `urirun diff old-registry.json new-registry.json`.
- Dodać wyjaśnienia skanera: każdy wygenerowany binding powinien zawierać plik
  źródłowy, standard źródła i powód.
- Dodać testy dymne instalatora dla instalacji z GitHuba i wheeli z GitHub
  Release.
- Trzymać publiczne docs skupione na v7 i v8; starsze foldery eksperymentów
  powinny pozostać usunięte lub zarchiwizowane poza głównym projektem.
