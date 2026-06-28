# Komponenty systemu urirun

<!-- docs-nav -->
📖 **Dokumentacja urirun:** [← README](../README.md) · [Architektura](ARCHITECTURE.md) · **Komponenty** · [URI Objects](URI_OBJECTS.md) · [Łączenie node](NODE_CONNECTIONS.md) · [Dashboard & chat](HOST_DASHBOARD_CHAT.md) · [Host↔Node](HOST_NODE_COMMUNICATION.md) · [Sekrety](SECRETS.md) · [Archiwum dok.](DOCUMENT_ARCHIVE.md) · [Decision Loop](DECISION_LOOP.md) · [Roadmap](REFACTOR_ROADMAP.md) · [Podział paczek](URIRUN_PACKAGE_SPLIT_PLAN.md) · [Planfile](PLANFILE_HOST_INTEGRATION_PLAN.md)
<!-- /docs-nav -->

> **Legenda (TL;DR):** **Host** — lokalne centrum sterowania (dashboard, planuje i rozsyła). · **Node** — kontrolowany runtime: komputer / VM / API / urządzenie (`node:*`). · **Service** — długodziałająca usługa z własnym portem/API (chat `8194`, scanner `8196`). · **Connector** — paczka zdolności URI (`ocr://`, `fs://`, `kvm://`). · **Widget** — żywy widok/panel kontroli. · **Artifact** — gotowy plik/wynik (PDF, JSON OCR, screenshot).

Ten dokument jest słownikiem komponentów. Aktualny opis całościowego przepływu
i ownership paczek jest w `docs/ARCHITECTURE.md`.

Ten dokument opisuje podstawowe elementy systemu urirun i ich granice
odpowiedzialności. Jest przeznaczony dla operatora i developera, który chce
zrozumieć, z czego składa się urirun: host, node, service, connector, widget i
artifact.

Praktyczne komendy podłączania klasycznych node'ów, API node, device node,
browser-debug/browser-plugin/webpage/smartphone node oraz services są w
`docs/NODE_CONNECTIONS.md`.

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

## URI Object

`URI object` to kontrolowalna powierzchnia runtime, która grupuje URI routes,
transport i stan życia. W dashboardzie jest dostępna przez:

```text
GET /api/summary   -> pole objects
GET /api/objects   -> lista obiektów
```

Aktualnie kanoniczne URI object są wdrożone dla:

- `host`
- `node:*`
- `service:*`

Minimalny kształt:

```json
{
  "id": "service:phone-scanner",
  "kind": "service",
  "label": "urirun service: photo scanner",
  "status": "running",
  "reachable": true,
  "url": "https://host:8196/scanner",
  "transport": "http",
  "runtime": "phone-scanner",
  "routes": []
}
```

Widget i artifact nie są pełnym runtime object. Widget jest żywym widokiem
należącym do obiektu, a artifact jest zakończonym wynikiem w rejestrze
artifactów.

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

### Typy node

Typ node nie zastępuje `kind=node`. To metadana operacyjna mówiąca, jakiego
transportu i runtime'u host powinien oczekiwać. Kanoniczna lista jest w
`urirun.host.node_types`, w `GET /api/summary -> nodeTypes` oraz
`GET /api/node-types`.

| Typ | Kiedy używać | Naturalny transport/runtime |
| --- | --- | --- |
| `server` | headless Linux/VM z dostępem SSH | `ssh+http`, `urirun-node` |
| `pc` | fizyczny komputer z GUI, np. Lenovo | `http+kvm`, `urirun-node` |
| `rdp` | pulpit zdalny Windows/xrdp | `rdp+http+kvm`, `remote-desktop-node` |
| `smartphone` | telefon, najpierw webpage node, potem APK/Termux | `https+js`, `mobile-web-or-node` |
| `browser-debug` | cała przeglądarka przez CDP/debug port | `cdp`, `browser-cdp` |
| `browser-chrome-plugin` | aktywna karta przez rozszerzenie Chrome | `extension+http`, `chrome-extension` |
| `browser-firefox-plugin` | aktywna karta przez rozszerzenie Firefox | `extension+http`, `firefox-extension` |
| `webpage` | pojedyncza karta/strona przez JS/page bridge | `cdp+js`, `browser-page-js` |
| `api` | zewnętrzne HTTP/REST/OpenAPI, SaaS lub lokalna usługa | `http+auth`, `external-api` |
| `device` | kamera IP, RPi, NAS, IoT z wieloma protokołami | `multi-api`, `external-device` |

W konfiguracji hosta typ zapisujemy jako tag, np. `kind:webpage` albo `kind:pc`.
Dzięki temu registry, discovery i dashboard nie muszą zgadywać po nazwie typu
`lenovo` czy `laptop`.

Kompatybilność: stare `kind:browser` jest aliasem do `browser-debug`, a stare
`kind:web` jest aliasem do `webpage`. Nowe konfiguracje powinny używać nazw
kanonicznych.

### API node i device node

`api` i `device` są node'ami konfiguracyjnymi. Nie muszą wystawiać natywnego
urirun `/health` i `/routes`. Host przechowuje ich interfejsy w polu `apis[]` i
na tej podstawie pokazuje syntetyczne route'y typu:

```text
api://crm-api/main/command/request
device://rpi-camera/panel/query/status
media://rpi-camera/stream/query/stream
camera://rpi-camera/stream/query/snapshot
ssh://rpi-camera/ssh/command/run
fs://nas/share/query/list
```

Przykład konfiguracji API node:

```json
{
  "name": "crm-api",
  "url": "https://api.example.test/v1",
  "tags": ["kind:api"],
  "apis": [
    {
      "id": "main",
      "kind": "rest",
      "url": "https://api.example.test/v1",
      "auth": {
        "type": "bearer",
        "secretRef": "secret://keyring/urirun-node-api/crm-api/main#credential"
      }
    }
  ]
}
```

Ten sam wpis można utworzyć z CLI:

```bash
urirun host add-node crm-api https://api.example.test/v1 \
  --kind api \
  --api-id main \
  --api-kind rest \
  --auth-type bearer \
  --auth-token 'PASTE_ONCE'
```

Przykład `device` dla RPi/kamery/NAS:

```json
{
  "name": "rpi-camera",
  "url": "http://rpi.local",
  "tags": ["kind:device"],
  "capabilities": ["api", "camera", "files", "shell"],
  "apis": [
    {"id": "panel", "kind": "web", "url": "http://rpi.local"},
    {"id": "stream", "kind": "rtsp", "role": "camera", "url": "rtsp://rpi.local/live"},
    {"id": "share", "kind": "smb", "url": "smb://rpi.local/share"},
    {"id": "ssh", "kind": "ssh", "url": "ssh://pi@rpi.local"}
  ]
}
```

Wariant CLI dla device node:

```bash
urirun host add-node rpi-camera http://rpi.local \
  --kind device \
  --api '{"id":"panel","kind":"web","url":"http://rpi.local"}' \
  --api '{"id":"stream","kind":"rtsp","role":"camera","url":"rtsp://rpi.local/live"}' \
  --api '{"id":"share","kind":"smb","url":"smb://rpi.local/share"}' \
  --api '{"id":"ssh","kind":"ssh","url":"ssh://pi@rpi.local"}'
```

Sekrety autoryzacyjne nie powinny być zapisywane jako plaintext. Dashboard może
przyjąć token w payloadzie, ale zapisuje go do keyring i w konfiguracji zostawia
tylko `secretRef`.

Host umie bezpośrednio wykonać skonfigurowane interfejsy HTTP/REST/OpenAPI przez
route:

```text
configured://host/node-api/command/request
configured://host/node-api/query/status
```

Dla wygody discovery może też pokazać bezpośredni wariant:

```text
api://crm-api/main/command/request
```

Payload powinien wskazać metodę, ścieżkę i opcjonalne query/body, np.

```json
{
  "node": "crm-api",
  "apiId": "main",
  "method": "GET",
  "path": "/accounts",
  "query": {"limit": 10}
}
```

Interfejsy nie-HTTP, takie jak `rtsp`, `smb`, `nfs` czy `ssh`, pozostają
metadanymi device node'a dopóki nie ma dedykowanego connectora. Host nie udaje
ich wykonania; powinien zwrócić `connector_required`, żeby planner mógł
zainstalować albo wybrać właściwy connector.

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

Decyzja refaktoryzacyjna: `urirun-service-chat` ma być **real-source** ownerem
dashboardu/chatu, ale nie przez przeniesienie całego `urirun.host`. Do service
trafia aplikacja operatora (`host_dashboard`, `chat_orchestrator`, API/UI
dashboardu, decision loop). Widget render ma być konsumowany z
`urirun-widgets`, node/mesh z przyszłego `urirun-node`, a store/artifact/log
powinny iść przez connector/service właściciela danych. Inaczej service-chat
stałby się tym samym monolitem pod nową nazwą.

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

`urirun-widgets` jest źródłem prawdy dla renderu widgetów: JS bundle
`widget://host/bundle/query/js`, server-side `render.py`, HTML i SVG widgetu.
Host/dashboard może wybierać dane i sterować aplikacją operatora, ale nie powinien
utrzymywać własnych kopii `render*ServiceView`, `service_widget_html` ani
`service_widget_svg`.

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

## Podsystemy

Poza obiektami runtime (host/node/service/connector/widget/artifact) urirun ma kilka
przekrojowych podsystemów koordynujących wykonanie URI. Każdy żyje we własnym pakiecie i ma
własny dokument szczegółowy.

### Flow planner i autonomia (`urirun_flow`)

Zamienia prompt w języku naturalnym na flow kroków URI. Planner LLM (`make_flow` → `llm_flow`)
buduje kroki wyłącznie z `allowedRoutes`, a deterministyczne normalizatory naprawiają typowe
pomyłki: wstrzykują `cdp/session/query/ready` po `ensure`, przepisują `user_data_dir=<żywy profil>`
na `copy_from=<root profilu>` dla zadań wymagających logowania (`_rewrite_cdp_profile_for_auth`,
żeby debug-Chrome nie walczył z SingletonLock i sklonował cookies), oraz mapują niedostępne
`cdp/page/command/click|fill` na router `ui/command/*`. Wykonanie idzie przez jeden silnik
(`_thin_driver`, „follow-the-intent"), z diagnostyką błędów (`diag://host/error/command/classify`)
i rollbackiem kroków odwracalnych. Szczegóły: [Decision Loop](DECISION_LOOP.md).

### Digital Twin i odwracalność (`urirun_twin`)

Model środowiska + silnik odwracalny. `ReversibleProcess` wykonuje flow z niezmiennikiem „mutacja
bez zarejestrowanego inverse jest NIEWYKONYWALNA", buduje ledger i robi rollback LIFO z dowodem
pozycji (scan stanu przed/po). Schemat odwracalności (`list[CallSpec]`) pochodzi z kontraktu przez
`schema_from_contracts` (jedyne źródło — strategia #3; runtime ledger nadal jedzie konwencją
„inverse w wyniku"). Twin planner ocenia wykonalność i odwracalność kroków PRZED wykonaniem
(twin-plan widoczny w chacie). Connector: `urirun-connector-twin`.

### Warstwa kontraktowa (`urirun_connectors_toolkit` → `urirun-contract`)

Kontrakt operacji (kształt I/O, efekt `query`/`command`, odwracalność, błędy, przykłady) jest
deklarowanym artefaktem `contracts.json`, nie emergentny z kodu. Kernel (gate/codegen/lint/
reversible/jsonschema/typescript/export) został wydzielony do osobnego repo `urirun-contract`;
`urirun_connectors_toolkit` to fasada re-eksportująca. Bramy (`conform`, `lint_handler_signatures`,
`regen-check`, `check_single_source`) trzymają kontrakt zgodny z kodem. Pokrycie floty jest
ratchetowane (`fleet_coverage.py`). Szczegóły: `urirun-contract/ARCHITECTURE.md`.

### Pakiety wydzielone

Runtime jest rozbity na pakiety instalowane osobno: `urirun_node` (mesh/CLI/routing), `urirun_flow`
(planner+wykonanie), `urirun_twin` (twin+odwracalność), `urirun_runtime` (registry/MCP/v2),
`urirun_cdp` (CDP/Chrome), `urirun_scanner`, `urirun_connectors_toolkit` (fasada kontraktów).
Flota ~40 connectorów i kernel kontraktu (`urirun-contract`) to osobne repozytoria
`if-uri/urirun-connector-*`. Plan i stan podziału: [Podział paczek](URIRUN_PACKAGE_SPLIT_PLAN.md).

**Decyzja per-paczka (meta vs real-source).** `runtime/cdp/connectors-toolkit` zostają **meta-paczkami**
(źródło w monorepo, sibling = wrapper PyPI). **Real-source** (własne źródło, monorepo shimuje):
`contract`, `connector-router`, `twin`, `declarative`, `widgets`, `artifacts` oraz — od ekstrakcji
2026-06-28 — `flow` (`urirun.node.flow` → shim do `urirun-flow/urirun_flow/flow.py`; standalone
owner potwierdzony collision-smoke). `runtime` jest następny w kolejce do real-source (po opóźnieniu
top-level importów). Reguła: paczka jest ALBO meta ALBO real-source, nigdy w pół — `dev-install.sh
--check` + slim-core import-smoke pilnują, że każda ekstrakcja nie zostawia cofki ani połowicznego
właściciela.

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
