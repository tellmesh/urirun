# Komponenty systemu urirun

Ten dokument opisuje podstawowe elementy systemu urirun i ich granice
odpowiedzialności. Jest przeznaczony dla operatora i developera, który chce
zrozumieć, z czego składa się urirun: host, node, service, connector, widget i
artifact.

## Model w skrócie

urirun traktuje działania jako adresowalne operacje URI. Każda komenda,
niezależnie czy pochodzi z CLI, chatu, dashboardu, node'a czy usługi, powinna dać
się opisać jako:

```text
scheme://authority/path/kind/action
```

Przykłady:

```text
document://host/archive/command/sync-to-node
service://host/phone-scanner/command/restart
fs://host/file/command/write-b64
widget://host/widget/query/render
urifix://host/chain/command/repair
```

Najważniejszy podział:

| Komponent | Czym jest | Przykład |
| --- | --- | --- |
| Host | centrum sterowania i koordynacji | komputer developera z dashboardem |
| Node | kontrolowany runtime/komputer | laptop Lenovo z urirun node |
| Service | długodziałająca usługa z własnym portem/API | chat `8194`, scanner `8196` |
| Connector | paczka zdolności URI | `ocr://`, `docid://`, `urifix://` |
| Widget | żywy widok lub panel kontroli | podgląd kamery, status usługi |
| Artifact | gotowy plik lub wynik | PDF faktury, JSON OCR, screenshot |

## Host

Host to centrum sterowania systemu. Zwykle działa na komputerze operatora.

Host odpowiada za:

- przyjmowanie komend z CLI, chatu lub API,
- przechowywanie konfiguracji znanych node'ów,
- odkrywanie tras URI przez `/routes`,
- planowanie lub przyjmowanie gotowych flow,
- dispatch kroków URI do hosta, node'ów lub usług,
- zapisywanie logów, wiadomości chatu i artifactów,
- obsługę fallback/recovery, np. przez `urifix://`.

Typowe URI hosta:

```text
dashboard://host/phone-scanner/command/start
document://host/archive/command/sync-to-node
artifact://host/artifacts/query/list
urifix://host/chain/command/repair
```

Host nie musi wykonywać każdej pracy lokalnie. Jego główną rolą jest
koordynacja: wybiera właściwy node, service lub connector i przekazuje tam
konkretną operację URI.

## Node

Node to kontrolowany runtime. Może być fizycznym komputerem, laptopem, VM,
kontenerem albo innym środowiskiem, które wystawia API urirun.

Node udostępnia zwykle:

```text
GET  /health
GET  /routes
GET  /services
POST /run
GET  /events
POST /deploy
POST /enroll
```

Node odpowiada za:

- wykonywanie lokalnych route'ów URI,
- publikowanie swojej powierzchni możliwości,
- emitowanie zdarzeń i wyników,
- dostęp do lokalnego filesystemu, ekranu, procesów lub przeglądarki,
- przyjmowanie kontrolowanego deployu connectorów lub konfiguracji.

Przykłady:

```text
fs://host/file/command/write-b64
screen://host/portal/query/capture
kvm://host/input/command/type
proc://host/process/query/list
```

Node nie powinien sam zgadywać intencji użytkownika. Dostaje konkretny URI,
payload i tryb wykonania. Intencję i wybór targetu rozwiązuje host.

## Service

Service to długodziałająca aplikacja urirun z własnym cyklem życia. Service może
mieć własny port, HTTP API, stan live i endpointy do kontroli.

Przykłady usług:

```text
urirun-service-chat      # dashboard/chat, domyślnie port 8194
urirun-service-scanner   # skaner telefonu, domyślnie port 8196
```

Service odpowiada za:

- start, stop, restart i utrzymanie procesu,
- własne endpointy HTTP lub Web UI,
- publikowanie statusu live,
- obsługę widoków, które zmieniają się w czasie,
- rejestrowanie końcowych artifactów przez hosta.

Typowe URI:

```text
service://host/chat/command/restart
service://host/phone-scanner/command/restart
dashboard://host/service/phone-scanner/command/restart
scanner://page/camera/command/autonomous
```

Service różni się od connectora tym, że żyje jako proces. Connector zwykle
wykonuje pojedynczą operację i kończy pracę.

## Connector

Connector to paczka dostarczająca zdolności URI. Powinna być mała i domenowa.

Przykłady:

```text
urirun-connector-ocr
urirun-connector-smart-crop
urirun-connector-docid
urirun-connector-urifix
urirun-connector-email
```

Connector odpowiada za:

- deklarowanie tras przez `urirun.bindings`,
- walidację inputu,
- wykonanie jednej dobrze określonej klasy operacji,
- zwrócenie przenośnego JSON,
- zwrócenie descriptorów artifactów, jeśli utworzył pliki.

Connector nie powinien:

- utrzymywać własnego dashboardu,
- tworzyć osobnej bazy artifactów,
- ukrywać długich pętli pollingowych,
- przejmować lifecycle service,
- mieszać kilku domen w jednej paczce.

Przykład connectora:

```text
ocr://host/document/query/text
smartcrop://host/document/query/crop
docid://host/document/query/identify
urifix://host/chain/command/repair
```

## Widget

Widget to żywy widok lub panel kontroli. Pokazuje stan, który może się zmieniać
bez tworzenia nowej wiadomości chatu lub nowego pliku.

Przykłady widgetów:

- podgląd kamery skanera,
- status `urirun-service-scanner`,
- lista aktywnych node'ów,
- live tabela ostatnich scanów,
- panel OCR z aktualną klatką i metadanymi,
- iframe kontrolny usługi.

Rekomendowany descriptor:

```json
{
  "kind": "scanner-stream",
  "target": "service:phone-scanner",
  "view": "scanner-stream",
  "live": true,
  "refreshMs": 1000,
  "dataUri": "dashboard://host/services/query/live"
}
```

Najważniejsza zasada: widget jest żywy. Nie jest plikiem i nie powinien pojawiać
się na liście artifactów. Jeśli podgląd kamery zapisze finalny PDF, to PDF jest
artifactem, ale sam podgląd kamery jest widgetem.

## Artifact

Artifact to gotowy, statyczny wynik pracy. Może być plikiem, raportem lub
utrwalonym rekordem.

Przykłady artifactów:

- PDF faktury lub paragonu,
- JSON z OCR,
- CSV z grupowaniem,
- screenshot,
- QR code,
- zapisany raport analizy,
- gotowy obraz po smart-crop.

Rekomendowany descriptor:

```json
{
  "kind": "document-pdf",
  "uri": "document://host/DOC-PAR-123",
  "path": "/home/tom/.urirun/documents/2026-06/example.pdf",
  "mime": "application/pdf",
  "live": false,
  "meta": {
    "docId": "doc-par-123",
    "sourceCaptureUri": "scanner://host/capture/abc"
  }
}
```

Artifact powinien być rejestrowany raz jako finalny wynik. Pliki pośrednie mogą
być metadanymi, attachmentami wiadomości albo stanem widgetu, ale nie powinny
tworzyć wielu wpisów wskazujących na ten sam dokument końcowy.

## Transport

Transport to sposób dostarczenia operacji URI do runtime'u. Nie jest osobnym
typem obiektu biznesowego, ale częścią wykonania.

Przykłady transportu:

- lokalne wywołanie funkcji Python,
- HTTP `POST /run` do node'a,
- subprocess,
- przeglądarka przez CDP,
- input KVM,
- Web API usługi,
- przyszły transport gRPC/MQTT.

Ten sam URI powinien mieć możliwie stabilne znaczenie niezależnie od transportu.

## Runtime

Runtime to granica wykonania: miejsce, w którym route URI jest rzeczywiście
uruchamiany. Runtime może istnieć w hoście, node, service albo connectorze.

Przykłady:

- Python runtime CLI,
- node server na Lenovo,
- service scanner na porcie `8196`,
- lokalny subprocess connectora,
- kontener Docker wystawiający URI API.

Runtime jest odpowiedzialny za policy, walidację, wykonanie i wynik.

## Relacje między komponentami

Typowy przepływ z chatu:

```text
User prompt
  -> urirun-service-chat
  -> Host dashboard
  -> URI flow
  -> Node / Service / Connector
  -> Result
  -> Artifact lub Widget
  -> Chat message + logs
```

Przykład skanowania dokumentu:

```text
service://host/phone-scanner/command/start
  -> urirun-service-scanner
  -> widget: scanner live preview
  -> smartcrop://host/document/query/crop
  -> ocr://host/document/query/text
  -> docid://host/document/query/identify
  -> artifact: document-pdf
  -> chat: scan saved
```

Przykład synchronizacji PDF na Lenovo:

```text
document://host/archive/command/sync-to-node
  -> host wybiera node z konfiguracji lub node_url
  -> fs://host/file/command/write-b64 na wybranym node
  -> fs://host/file/query/read-b64 na wybranym node
  -> node zapisuje pliki w ~/Downloads/urirun-scans
  -> host weryfikuje kontrakt read-back SHA-256
  -> chat pokazuje copied/failed
```

Przykład naprawy błędu:

```text
document sync failed: missing node_url
  -> urifix://host/chain/command/repair
  -> recovery: retry-with-node-url albo provide-node-url
  -> chat pokazuje retry/payload
```

## Granice odpowiedzialności

| Pytanie | Właściwy komponent |
| --- | --- |
| Kto zna intencję użytkownika? | Host / chat planner |
| Kto wykonuje lokalną akcję na laptopie? | Node |
| Kto utrzymuje port i proces? | Service |
| Kto dostarcza nową zdolność URI? | Connector |
| Kto pokazuje live status? | Widget |
| Kto reprezentuje gotowy plik? | Artifact |
| Kto naprawia failed URI chain? | `urifix://` jako connector recovery |
| Kto trzyma katalog artifactów i logi? | Host DB / artifact registry |

## Zasady projektowe

1. URI jest podstawowym kontraktem między warstwami.
2. Host koordynuje, ale nie powinien przejmować logiki domenowej connectorów.
3. Node wykonuje konkretne URI, ale nie powinien zgadywać intencji.
4. Service zarządza procesem i live stanem.
5. Connector dostarcza zdolność, a nie dashboard.
6. Widget jest żywy, artifact jest skończony.
7. Artifact finalny powinien być rejestrowany raz.
8. Recovery powinno zwracać patch/retry albo akcję dla człowieka, nie zgadywać.

## Nazewnictwo

Używaj konsekwentnie:

- `URI Host` lub `host` dla centrum sterowania.
- `URI Node` lub `node` dla kontrolowanego runtime'u.
- `URI Service` lub `service` dla długodziałającej usługi.
- `Connector` dla paczki zdolności URI.
- `Widget` dla live view/control surface.
- `Artifact` dla statycznego wyniku.
- `Runtime` dla miejsca wykonania.
- `Transport` dla kanału komunikacji.
