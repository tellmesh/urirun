# Architektura systemu urirun

<!-- docs-nav -->
📖 **Dokumentacja urirun:** [← README](../README.md) · **Architektura** · [Komponenty](COMPONENTS.md) · [URI Objects](URI_OBJECTS.md) · [Łączenie node](NODE_CONNECTIONS.md) · [Dashboard & chat](HOST_DASHBOARD_CHAT.md) · [Host↔Node](HOST_NODE_COMMUNICATION.md) · [Sekrety](SECRETS.md) · [Archiwum dok.](DOCUMENT_ARCHIVE.md) · [Decision Loop](DECISION_LOOP.md) · [Roadmap](REFACTOR_ROADMAP.md) · [Podział paczek](URIRUN_PACKAGE_SPLIT_PLAN.md) · [Planfile](PLANFILE_HOST_INTEGRATION_PLAN.md)
<!-- /docs-nav -->

Status: 2026-06-28.

Ten dokument jest aktualnym opisem całości systemu. `COMPONENTS.md` opisuje
pojęcia operatora, `URI_OBJECTS.md` opisuje kontrakt obiektów, a
`ACTIVE_REFACTOR_PLAN.md` opisuje kolejność dalszego odchudzania `urirun`.

## Teza systemu

`urirun` jest lekkim runtime URI. Jego zadanie to przyjąć intencję, registry lub
gotowy flow, sprowadzić je do konkretnych tras URI, sprawdzić gdzie każda trasa
może zostać uruchomiona, wykonać ją przez właściwy transport i oddać
zweryfikowany wynik.

Architektura idzie w stronę:

```text
mały hub urirun
  + urirun-contract            # kontrakty tras i bramy zgodności
  + urirun-connector-router    # routowanie przed dispatch
  + urirun-flow                # flow, planner, recovery, thin driver
  + urirun-connector-*         # domenowe zdolności URI
  + urirun-service-*           # długo działające aplikacje
  + urirun-widgets             # render żywych widoków
  + urirun-artifacts           # powierzchnia artifactów
  + urirun-node                # docelowy właściciel node/mesh
```

Reguła przewodnia: jedna implementacja, wiele shimów. Stare ścieżki importów
mogą istnieć dla kompatybilności, ale nie mogą zawierać drugiej kopii kernela.

## Główne warstwy

| Warstwa | Obecny właściciel | Rola |
| --- | --- | --- |
| Hub runtime | `urirun` | CLI, podstawowy registry, policy, discovery, kompatybilność importów |
| Kontrakty | `urirun-contract` | deklaracje I/O, efekty, odwracalność, JSON Schema, lint, conform |
| Router | `urirun-connector-router` | pre-dispatch diagnosis: gdzie wykonać każdy URI albo dlaczego jest zablokowany |
| Flow | `urirun-flow` | model flow, normalizacja planu, thin driver, recovery, rollback, verification |
| Connectors | `urirun-connector-*` | domenowe trasy URI, np. `kvm://`, `fs://`, `ocr://`, `llm://` |
| Services | `urirun-service-*` | długo działające aplikacje: chat, scanner, android/webpage node |
| Widgets | `urirun-widgets` | render HTML/SVG/JS dla żywych widoków i paneli |
| Artifacts | `urirun-artifacts` + host DB | finalne pliki/wyniki, deskryptory, listing i rejestracja |
| Node/mesh | dziś `urirun`, docelowo `urirun-node` | `/health`, `/routes`, `/run`, transport, deploy, keyauth |
| Digital Twin | `urirun-connector-twin` | model środowiska, drift, planowanie odwracalności |

## Przepływ wykonania

Standardowy przebieg z dashboardu albo chatu:

```text
prompt / command / URI
  -> service-chat / CLI / API
  -> allowed routes + target selection
  -> urirun-flow plan or loaded flow
  -> urirun-connector-router diagnosis
  -> execute_flow / thin driver
  -> node, service or connector transport
  -> contract-shaped result
  -> verification, artifact/widget/log/chat message
  -> recovery nextIntent on failure
```

Najważniejsza zasada autonomii: natural-language step nie powinien być wysyłany
do wykonania dopóki router nie powie, gdzie ma zostać uruchomiony. Każdy krok
dostaje `runsOn` albo typed block, np. `ROUTING_BLOCKED`, `connector_required`,
`unreachable_node`, `missing_route`.

## URI i target

Kanoniczny kształt operacji:

```text
scheme://authority/path/kind/action
```

Przykłady:

```text
kvm://host/cdp/page/command/navigate
fs://host/file/command/write-b64
router://host/plan/query/diagnose
twin://lenovo/env/query/drift
widget://host/bundle/query/js
artifact://host/artifacts/query/list
```

`scheme` mówi jaka domena/connector obsługuje trasę. `authority` jest logiczną
powierzchnią URI, a nie zawsze miejscem wykonania. Rzeczywisty runtime wybiera
router na podstawie selected targets, node config, route ownera i capability
evidence.

Przykład: `kvm://host/...` może zostać wykonane na node `lenovo`, jeżeli flow
jest skierowany do `node:lenovo`, a node publikuje trasę KVM przez `/routes`.

## Host

Host jest centrum koordynacji. Obecnie większość implementacji hosta nadal jest
w `urirun/adapters/python/urirun/host/*`, ale docelowo aplikacje hostowe mają
zejść do service packages.

Host odpowiada za:

- konfigurację node i service,
- object registry (`host`, `node:*`, `service:*`),
- chat/dashboard API,
- dispatch do node/service/connector,
- rejestr wiadomości, logów i artifactów,
- recovery przez `urifix://` i `nextIntent`,
- widok operatora.

Duże obecne moduły właścicielskie, które są celami ekstrakcji:

- `host/chat_orchestrator.py`
- `host/dashboard.js`
- `host/host_dashboard.py`
- `host/object_registry.py`
- `urirun_node/server.py`

## Node

Node to kontrolowany runtime: laptop, serwer, VM, kontener, przeglądarka, telefon
albo skonfigurowane API/device. Klasyczny node wystawia:

```text
GET  /health
GET  /routes
GET  /services
POST /run
GET  /events
POST /deploy
POST /enroll
```

Node nie zgaduje intencji. Dostaje konkretny URI i payload. Typ node (`pc`,
`server`, `browser-debug`, `webpage`, `api`, `device` itd.) jest metadanym
operacyjnym dla discovery/routera, nie osobnym rodzajem kontraktu.

## Services

Service to długo działająca aplikacja z własnym portem, lifecycle i opcjonalnym
UI. Service różni się od connectora tym, że żyje jako proces i publikuje stan w
czasie.

Aktywne service packages:

| Package | Rola | Status ownership |
| --- | --- | --- |
| `urirun-service-chat` | dashboard/chat operatora, endpoint `8194` | istnieje, docelowo real-source owner chatu |
| `urirun-service-scanner` | telefon/skaner, endpoint `8196` | istnieje, scanner runtime powinien tam zostać |
| `urirun-service-android-node` | android/webpage node bridge | istnieje jako service/node bridge |

Service powinien posiadać lifecycle (`query/status`, `command/start`,
`command/restart`, `command/stop`) i publikować URI routes. Nie powinien
vendoryzować widget renderu ani kernela kontraktów.

## Connectors

Connector to mała paczka zdolności URI. Deklaruje trasy przez entry point
`urirun.bindings` albo `urirun_bindings()`, opcjonalnie dostarcza
`contracts.json`, testy i przykłady.

Przykładowe rodziny:

- desktop/browser: `urirun-connector-kvm`, `browser-control`, `webnode`,
  `adb`, `camera`, `camera-web`;
- dokumenty: `ocr`, `smart-crop`, `docid`, `invoice`, `doc`, `scanner`;
- system/data: `fs`, `sqlite-context`, `hash`, `base64`, `uuid`,
  `time-tools`;
- sieć i integracje: `http-check`, `domain-monitor`, `github`,
  `namecheap-dns`, `mqtt`, `email`, `mcp-filesystem`, `linkedin`;
- autonomia: `router`, `twin`, `urifix`, `flow-repair`, `llm`, `adopt`,
  `get-node`;
- urządzenia: `usb`, `netscan`, `ksef`.

Connector powinien zwracać przenośny JSON i deskryptory artifactów, jeśli tworzy
pliki. Nie powinien utrzymywać własnego dashboardu, bazy artifactów ani
długiego lifecycle procesu.

## Contracts

`urirun-contract` jest źródłem prawdy dla kontraktów tras. Kontrakt opisuje:

- input i output shape,
- efekt (`query` albo `command`),
- odwracalność i inverse,
- klasy błędów,
- przykłady/goldeny,
- eksport do JSON Schema / TypeScript / MCP/A2A.

Historyczne `urirun_connectors_toolkit.contract_*` są fasadami. Implementacja
żyje w `urirun_contract/*`. Bramy utrzymujące spójność:

- `check_single_source`,
- `lint_handler_signatures`,
- `conform`,
- `regen-check`,
- `fleet_coverage.py`,
- additive-only compatibility gate.

Mutująca trasa autonomiczna powinna mieć kontrakt przed dopuszczeniem do
domyślnego wykonania.

## Router

`urirun-connector-router` jest pre-dispatch kernel. Zanim flow zostanie
wykonany, router diagnozuje każdy krok:

- czy scheme i route istnieją,
- czy wybrany host/node/service ma capability,
- czy transport jest osiągalny,
- czy target wynika z polecenia, defaultu hosta czy explicit node,
- czy brakuje connectora albo service,
- czy operacja jest bezpieczna do wykonania.

Router ma URI surface:

```text
router://host/plan/query/diagnose
```

W dashboardzie wynik routera powinien być widoczny przed dispatch. Celem jest,
żeby autonomia wiedziała gdzie wykonać każdą akcję jeszcze przed pierwszym
side-effectem.

## Flow i recovery

`urirun-flow` jest real-source ownerem importu `urirun_flow`. Hub `urirun` nie
powinien już wysyłać własnej kopii `urirun_flow*`.

Flow odpowiada za:

- model kroków i zależności,
- normalizację flow od LLM/recall,
- thin driver,
- verification i rollup,
- diagnostykę błędów,
- rollback kroków odwracalnych,
- `nextIntent` / `urifix://` recovery.

Aktualny istotny fix: flow screenshotów normalizuje `ui/query/verify` przed
`screen/query/capture`. Jeżeli verify tylko informacyjnie sprawdza tekst strony,
nie może blokować samego screenshotu; capture zostaje reachable, a verify staje
się optional telemetry.

## Widgets

Widget to żywy widok lub panel kontroli. Nie jest finalnym plikiem.

`urirun-widgets` jest źródłem prawdy dla:

- JS bundle widgetów,
- server-side render helpers,
- HTML/SVG widgetu,
- service-view selection i summary.

Host dashboard konsumuje te helpery. Nie powinien definiować własnych kopii
`service_widget_html`, `service_widget_svg`, `select_service_view`,
`service_widget_summary` ani rodziny `render*ServiceView` /
`renderWidget*`.

Przykłady widgetów: scanner stream, status service, node health panel, tabela
live z `/api/summary`, iframe kontrolny service.

## Artifacts

Artifact to finalny, statyczny wynik: PDF, screenshot, JSON OCR, CSV, raport,
obraz po cropie. Artifact ma `live: false`.

Kanoniczna powierzchnia:

```text
artifact://host/artifact/command/register
artifact://host/artifacts/query/list
```

Obecny storage jest związany z host DB i `urirun-connector-sqlite-context`.
Docelowy model: connector/service zwraca descriptor artifactu, a host/service
rejestruje finalny wynik raz. Pliki pośrednie mogą być attachmentami lub stanem
widgetu, ale nie powinny mnożyć rekordów dla tego samego dokumentu.

## Digital Twin

`urirun-connector-twin` dostarcza warstwę planowania środowiska:

- drift środowiska (`known-good` vs current),
- mock/sandbox/proof,
- recall epizodów,
- browser/monitor diagnostics,
- odwracalność opartą o kontrakty.

Twin daje operatorowi evidence przed wykonaniem. Jeżeli router mówi, że trasa
jest wykonywalna, a twin preflight mówi, że dana warstwa jest unreachable, to ma
być typed diagnostic, nie dwa sprzeczne zielone/czerwone raporty.

## Registry, MCP i A2A

Runtime registry kompiluje lokalne i entry-pointowe trasy. Te same kontrakty są
projektowane do kilku powierzchni:

- native URI registry,
- MCP tools,
- A2A cards,
- JSON Schema dla edytorów/CI,
- TypeScript/Go/Rust/Python consumer shape.

`v2_mcp` i eksporty kontraktowe powinny czytać z `urirun-contract`, nie z
równoległych deklaracji.

## Sekrety i policy

Sekrety są przekazywane przez referencje:

```text
secret://...
getv://...
```

Connector nie powinien czytać dowolnych zmiennych środowiskowych poza
zadeklarowaną polityką. `SECRETS.md` opisuje `secretAllow`, keyring-backed
`secretRef` i lint przeciw omijaniu sekretów.

## Testy i bramy

Minimalny zestaw bram architektonicznych:

- contract single-source i fleet coverage w `urirun-contract`,
- router single-source i package check w `urirun-connector-router`,
- example diagnosis przez router,
- `urirun-flow` tests dla planner/normalizer/thin driver,
- hub tests dla chat/orchestrator/recall gate,
- widget render single-source w `urirun-widgets`,
- collision smoke dla paczek real-source,
- slim import smoke: `import urirun` nie może importować host/node/flow/widgets.

Praktyczne komendy są utrzymywane w `ACTIVE_REFACTOR_PLAN.md` i w Makefile
poszczególnych paczek.

## Aktualne luki

1. `urirun-connector-router` i `urirun-widgets` muszą zostać opublikowane przed
   kolejnym release hub, inaczej świeża instalacja może mieć niespełnialne
   zależności.
2. `urirun-service-chat` istnieje, ale pełny kod operator chat/dashboard nadal
   jest głównie w hub `urirun.host`.
3. `urirun-node` jest meta-package; real-source split node/mesh jest następny po
   ustabilizowaniu flow/runtime.
4. `urirun-runtime` i `urirun-cdp` są nadal meta-package albo shimowane
   powierzchnie; decyzja real-source/fold-in jest otwarta.
5. Duże moduły hosta nadal są właścicielami wielu concernów i powinny być
   rozbijane dopiero po zielonych smoke testach router/chat/flow.

## Gdzie szukać szczegółów

- [Komponenty](COMPONENTS.md): pojęcia operatora i granice host/node/service.
- [URI Objects](URI_OBJECTS.md): kontrakt objectów, artifactów i widgetów.
- [Dashboard & chat](HOST_DASHBOARD_CHAT.md): UI operatora, chat, recovery.
- [Host↔Node](HOST_NODE_COMMUNICATION.md): API i transport host-node.
- [Łączenie node](NODE_CONNECTIONS.md): jak dodawać PC/API/device/webpage node.
- [Decision Loop](DECISION_LOOP.md): autonomia, `nextIntent`, recovery.
- [Podział paczek](URIRUN_PACKAGE_SPLIT_PLAN.md): strategia ekstrakcji.
- [Active refactor plan](ACTIVE_REFACTOR_PLAN.md): aktualna kolejność prac.
