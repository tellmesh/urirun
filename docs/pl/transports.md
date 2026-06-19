# Transporty

`urirun` trzyma kontrakt URI oddzielnie od transportu. Ten sam URI można wywołać
lokalnie, przez endpoint usługi albo przez orkiestrator przepływu. Registry,
JSON Schema i bramka polityki to kontrakt; transport jedynie przenosi
`{uri, payload}` tam, gdzie `v8.run` to wykonuje.

`v8/examples/transports` napędza jedno registry przez pięć transportów
(in-process, kolejka, serverless, HTTP, gRPC) i dostarcza jednokomendowy
`scan_and_run.py`.

## Lokalnie i shell

- `local-function` wywołuje funkcję w procesie zarejestrowaną przez kod.
- `argv-template` renderuje listę argv i wykonuje ją bez shella.
- `shell-template` renderuje string powłoki i wymaga jawnej zgody polityki.

## Kolejka i serverless

- Konsument kolejki/zdarzeń mapuje wiadomość z tematu na `v8.run` (kształt
  MQTT/NATS/Kafka) i publikuje odpowiedź.
- Funkcja serverless to czyste `handler(event)`, które per żądanie woła `v8.run`,
  z registry skompilowanym w pamięci.

## Docker

Przykłady Docker używają targetów URI jako nazw usług:

```text
python://python-worker/text/normalize
node://node-worker/text/slugify
shell://shell-worker/report/write
```

Zobacz `v8/examples/docker_uri_flow` - przepływ Compose, w którym usługi
publikują bindingi, a orkiestrator uruchamia wielokrokowy przepływ URI.

## HTTP i przeglądarka

Przykład HTML w `v8/examples/html_uri_app` ładuje dokument bindingów, renderuje
formularze URI i woła backend Pythona przez `POST /api/run`.

Backend może z tego samego registry wystawiać logi, ostatnie wywołania,
narzędzia MCP i karty A2A, więc akcje frontendu używają tych samych nazw URI co
backend.

## gRPC

`urirun.v8_grpc` udostępnia mały interfejs RPC: listowanie tras, wywołania unary
i strumieniowe. Zainstaluj opcjonalny zestaw zależności:

```bash
pip install "urirun[grpc] @ git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
```

`v8/examples/multi_transport` to stos Docker łączący workery HTTP i gRPC,
auto-generuje jedno registry z ich `/routes` i `ListRoutes`, wykrywa konflikty
tras i uruchamia przepływ międzyśrodowiskowy, którego kroki trafiają na oba
transporty.

## MCP i A2A

Ponieważ bindingi v8 zawierają JSON Schema, registry można rzutować na:

- MCP `tools/list`
- MCP `tools/call`
- umiejętności karty agenta A2A

Wykonanie i tak przechodzi przez tę samą bramkę polityki `urirun`.
