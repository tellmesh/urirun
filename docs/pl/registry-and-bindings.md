# Registry i bindingi

`urirun` oddziela kontrakt pakietu od drzewa lookup runtime.

## Dokument bindingów

Dokument bindingów to przenośny JSON. Opisuje trasy URI, schematy wejścia i
konfigurację adaptera.

```json
{
  "version": "urirun.bindings.v8",
  "bindings": {
    "report://local/render/pdf": {
      "kind": "command",
      "adapter": "argv-template",
      "inputSchema": {
        "type": "object",
        "required": ["input", "output"],
        "properties": {
          "input": { "type": "string" },
          "output": { "type": "string" }
        },
        "additionalProperties": false
      },
      "argv": ["python3", "render.py", "{input}", "{output}"]
    }
  }
}
```

## Registry

Registry kompiluje się z jednego lub wielu dokumentów bindingów:

```bash
urirun compile bindings.v8.json --out registry.json
```

Runtime dispatchuje wyłącznie z registry. Dzięki temu wygenerowane registry jest
łatwe do przeglądu, odtwarzalne i bezpieczne do przekazania między klientami
shell, usługami HTTP, konsolami w przeglądarce, orkiestratorami Docker i
projekcjami dla agentów.

## Tożsamość trasy

Liczy się pełny URI. Trasa taka jak:

```text
device://device-01/led/command/set
```

może współistnieć z:

```text
device://device-02/led/command/set
```

ponieważ target jest częścią tożsamości trasy. Unika to konfliktów, gdy wiele
usług wystawia ten sam kształt operacji dla różnych targetów.

## Polityka konfliktów

Wygenerowane bindingi powinny być deterministyczne:

- jawne pliki bindingów wygrywają z trasami wywnioskowanymi ze skryptów/paczek
- zduplikowane pełne URI powinny nie przejść walidacji, chyba że skaner oznaczy
  je jako to samo źródło
- pliki generowane zapisuj do `generated/` lub `.urirun/`, nie edytuj jako
  źródła podstawowego
- przy adopcji przez skaner źródłem prawdy pozostają artefakty źródłowe
