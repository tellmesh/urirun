# urirun package split plan

<!-- docs-nav -->
📖 **Dokumentacja urirun:** [← README](../README.md) · [Architektura](ARCHITECTURE.md) · [Komponenty](COMPONENTS.md) · [URI Objects](URI_OBJECTS.md) · [Łączenie node](NODE_CONNECTIONS.md) · [Dashboard & chat](HOST_DASHBOARD_CHAT.md) · [Host↔Node](HOST_NODE_COMMUNICATION.md) · [Sekrety](SECRETS.md) · [Archiwum dok.](DOCUMENT_ARCHIVE.md) · [Decision Loop](DECISION_LOOP.md) · [Roadmap](REFACTOR_ROADMAP.md) · **Podział paczek** · [Planfile](PLANFILE_HOST_INTEGRATION_PLAN.md)
<!-- /docs-nav -->

> **NOWY CEL REFAKTORYZACJI (2026-06-28, nadrzędny względem reszty dokumentu).**
> Aktywna kolejność prac jest w `docs/ACTIVE_REFACTOR_PLAN.md`; ten dokument opisuje
> model docelowy i historyczne decyzje splitu.
> `urirun` ma zostać **maksymalnie prostym kernelem URI + CLI**, a nie
> samodzielnym backendem aplikacyjnym. Wszystko, co jest zdolnością domenową,
> procesem long-running, UI, przepływem, integracją lub kontraktem, ma mieć
> właściciela poza rdzeniem: `urirun-contract`, `urirun-connector-*`,
> `urirun-service-*`, `urirun-flow`, `urirun-node`, `urirun-widgets`,
> `urirun-artifacts` itd.
>
> **Rdzeń `urirun` zostawia tylko minimalny zestaw:**
> - parser URI, binding/registry compile-validate-list-run,
> - policy gate, envelope, error taxonomy i dry-run/execute semantics,
> - discovery entry pointów connectorów/services,
> - minimalne adaptery wykonania (`python-call`, `argv-template`,
>   `shell-template`, `http-service`) bez domenowych handlerów,
> - kompatybilne shimy z ostrzeżeniami i testami, które nie importują ciężkich
>   warstw przy `import urirun`.
>
> **Reguła zależności:** connector/service/flow/node może zależeć od `urirun`;
> `urirun` nie może importować implementacji connectorów, usług hosta, dashboardu,
> skanera, digital twin ani domenowych integracji. Jeśli core potrzebuje zdolności,
> wywołuje ją przez registry/URI albo przez mały publiczny kontrakt danych.
>
> **Kontrakty są osobnym kernelem jakości.** `urirun-contract` jest właścicielem
> gate, JSON Schema, lint, reversible, compat i codegen. `urirun` tylko ładuje
> `meta.contract` z registry i egzekwuje minimalne policy/envelope; nie utrzymuje
> lokalnych kopii kernela kontraktowego.
>
> **Stan implementacji dziś:** `urirun` nadal fizycznie zawiera wiele warstw
> (`host`, `node`, `urirun_runtime`, `urirun_flow`, `urirun_scanner` itd.) oraz
> meta-paczki wskazujące z powrotem na `urirun`. Plan poniżej aktualizuje kierunek:
> kod ma migrować na zewnątrz, a meta-paczki mają stać się realnymi paczkami albo
> zostać jawnie oznaczone jako tylko-kompatybilnościowe. Nie dodawać nowych
> zdolności do core, jeśli mogą być connector/service/contract package.

> **STATUS DEKOMPOZYCJI (2026-06-23).** Dwa hotspoty wymienione niżej (`urirun.v2`
> i `urirun.mesh`) zostały rozbite — bez zmiany API, z re-eksportem dla zgodności,
> testy zielone (334 passed):
> - **`node/mesh.py` 3099 → ~2050 L** → 8 modułów warstwowych: `_util`, `_artifacts`,
>   `paths`, `_version`, `routing`, `config`, `transport`, `flow` (re-eksport z `mesh`).
>   Pozostają w `mesh` (na razie): server (`NodeContext`/`NodeHandler`/`serve_node`/
>   `apply_deploy`) i kontroler CLI (`*_command`).
> - **`runtime/v2.py` 2593 → ~1970 L** → warstwa budowy parsera (`_build_parser` +
>   pod-buildery per-komenda) wyniesiona do **`runtime/cli.py`**; `_build_parser`
>   fan-out 116 → 25. Handlery `_cmd_*` + `main()` ZOSTAJĄ w v2 — są kontrolerem
>   runtime'u (~30 zależności od wewnętrznych nazw v2); ich wyniesienie wymaga
>   najpierw czystego publicznego API runtime, więc to osobny krok.
> - Bezpieczeństwo: decyzja `safe` scentralizowana w `node/routing.route_is_safe`
>   (jedno źródło prawdy) — fundament pod deny-by-default.

> **STATUS EKSTRAKCJI (2026-06-26) — narzędzie audytu + PIERWSZA wydzielona paczka.**
> Dodano `scripts/extraction_audit.py` — statyczny (AST) audyt granicy pakietu: dla kandydata
> klasyfikuje każdą krawędź importu jako **OUTWARD** (blokująca — pakiet importuje warstwę
> wyżej), **CYCLE** (dwukierunkowa) albo **INWARD** (powierzchnia shimu = symbole do re-eksportu).
> Zielony = 0 OUTWARD + 0 CYCLE. Presety: `A`=scanner, `B`=runtime/kernel (allow_outward=∅),
> `C`=domain_monitor, `D`=cdp, `E`=connectors-toolkit, `F`=node, `G`=flow. Ma green self-test
> (`--selftest`). **Reguła szwu** (cała architektura w jednej decyzji): dla pary A→B —
> *capability którą A konsumuje → URI*, *kontrakt/typ → import*, *middleware owijające dispatch →
> kompozycja w kernelu*. Wpięte w CI: `tests/test_{scanner,runtime,connector}_extractable.py` +
> krok „Extraction boundary gate" w `.github/workflows/ci.yml` — fizyczny strażnik przed
> pełzaniem rdzenia (runtime = ratchet znanych krawędzi; reszta = green-gate).
>
> **Zmierzony stan (audyt, nie deklaracja):**
> - **GREEN / podnoszą się dziś:** connectors-toolkit (14 modułów: backend_registry, resolver,
>   cdp, uinput, scaffold, sdk… — tylko kernel + stdlib), cdp, domain_monitor (po odwróceniu
>   sprzężenia planfile przez wstrzykiwany `set_ticket_creator`), scanner.
> - **node:** **0 cykli** — oba zbite ruchem „przenieś źle ulokowany helper w dół": cykl
>   `flow_planner↔task_planner` przez `quiet_completion`→`node._util`; cykl
>   `event_schema↔twin_bridge` przez `_step_inverse`→`node.event_schema` (twin_bridge trzyma
>   re-eksport w dół). Zostaje ~33 OUTWARD = ~20 kanonizacji shimów runtime (`from urirun import
>   v2` → `from urirun.runtime import v2`) + ~13 sprzężeń CLI (`node_cli`/`task_cli`→host; CLI to
>   composition root → należą do warstwy host).
> - **runtime (kernel):** ratchet — 11 znanych krawędzi OUTWARD (3 top-level: `cli→node.config`,
>   `v2→urirun`, `v2_service→node.keyauth`; 11 to leniwe sięgnięcia do opcjonalnych warstw) + 2 cykle.
>
> **Pierwsza fizyczna ekstrakcja: `urirun-cdp`** (dowód wzorca move+shim, end-to-end).
> cdp = najczystszy cel (preset D GREEN, **czysty stdlib, 0 zależności od urirun**, promień
> rażenia = 2 pliki testów; kvm używa WŁASNEGO `urirun_connector_kvm.cdp`, nie rdzeniowego).
> Wzorzec do powtórzenia przy każdej kolejnej GREEN-paczce:
> 1. Nowa paczka `if-uri/urirun-cdp/` (src-layout, `src/urirun_cdp/cdp.py` = przeniesione źródło,
>    `pyproject.toml` z `dependencies=[]`), editable-install.
> 2. **Shim** w starej lokalizacji: `urirun/.../connectors/surfaces/cdp.py` →
>    `from urirun_cdp import cdp` + `sys.modules[__name__] = _moved` (wzorzec repo, jak
>    `urirun/host_db.py`) — stara ścieżka importu działa bez zmian u wszystkich konsumentów.
> 3. **Testy własne modułu** przenoszą się do `urirun-cdp/tests/` (uruchamiane w CI tej paczki).
> 4. **Test kontraktowy** w core (`test_kernel_adoption`) osłonięty
>    `pytestmark = pytest.mark.skipif(cdp is None)` + `try/except ImportError` — urirun-only CI
>    pomija go łagodnie (sibling-repo nie jest checkout'owany), jak pakiety connectorów.
> Zweryfikowane: 20 testów (15 kontrakt + 5 cdp), pełny pakiet urirun 1499 passed. UWAGA: rdzeń
> jest aktywnie współedytowany — shim cdp.py bywa cofany przez drugi tor; bez commitu/koordynacji
> dryfuje do dwóch kopii (nic się nie psuje, ale rozjeżdża).

> **STATUS EKSTRAKCJI (2026-06-28) — `urirun-connector-router`.**
> Routing URI jest teraz osobnym real-source package, a nie kolejną funkcją w `urirun`.
> Paczka `urirun-connector-router` jest właścicielem parsera URI, `safe`/denylisty,
> dopasowania template routes, `route.node`/`runsOn`, `diagnose_plan` i warstw
> `parse -> target -> route -> reachability -> safety`. Stara ścieżka
> `urirun.node.routing`/`urirun_node.routing` ma zostać shimem do tej paczki.
> `execute_flow(router_guard=True)` używa raportu przed dispatch i blokuje plan z błędem
> `ROUTING_BLOCKED`; chat dodatkowo emituje komunikat `Routing Plan` przed pierwszą akcją,
> żeby operator widział, czy np. `kvm://host/...` faktycznie zostanie uruchomione na `lenovo`
> przez `route.node`.

> **GRANICA AKTUALNOŚCI.** Blok powyżej oraz sekcje "Docelowy Model
> Slim-Core", "Minimalne API `urirun`" i "Reguły Ekstrakcji" poniżej są
> bieżącym planem: `urirun` jako slim-core, kontrakty w `urirun-contract`,
> zdolności w `urirun-connector-*`, procesy w `urirun-service-*`. Sekcje od
> "Cel (historyczny)" są historycznym planem dekompozycji i nie powinny być
> używane jako bieżąca lista migracji bez ponownego audytu
> `project/map.toon.yaml` oraz `scripts/extraction_audit.py`.

## Docelowy Model Slim-Core

| Odpowiedzialność | Właściciel docelowy | Zasada |
| --- | --- | --- |
| URI grammar, registry, policy, envelope, minimal dispatch | `urirun` | Core bez domeny i bez UI |
| Route contract, schema, lint, reversible, compat, codegen | `urirun-contract` | Jedno źródło jakości kontraktów |
| URI route planning, target/runsOn resolution, pre-dispatch diagnostics | `urirun-connector-router` | Jedno źródło decyzji gdzie wykonać krok |
| Authoring toolkit, scaffold, resolver, catalog helpers | `urirun-connectors-toolkit` | Narzędzia dla paczek, nie runtime core |
| Domenowe możliwości (`fs`, `email`, `ksef`, `kvm`, `planfile`, `sqlite`, `domain-monitor`) | `urirun-connector-*` | Każda zdolność ma własny manifest, testy i opcjonalny `contracts.json` |
| Long-running dashboard/scanner/android node | `urirun-service-*` | Procesy mają własne entry pointy i `service.manifest.json` |
| Flow DSL, planner, diagnostics, recovery | `urirun-flow` | Flow jako osobny model/przepływ, core tylko wykonuje kroki URI |
| Node server, mesh, deploy, keyauth, transport | `urirun-node` | Node to runtime usługi, nie import przy `import urirun` |
| Widgets, artifacts, object registry | `urirun-widgets`, `urirun-artifacts` | UI/artefakty poza core |

### Minimalne API `urirun`

Docelowo publiczny import `urirun` powinien eksportować tylko:

```text
command, shell, connector, connector_bindings,
validate, compile, list, run,
load_registry, discover_entry_points,
Envelope, PolicyDecision, UrirunError
```

CLI core:

```text
urirun validate
urirun compile
urirun list
urirun run
urirun connectors list/bindings/registry
urirun services list/manifest
urirun compat check
```

Komendy `urirun host ...`, `urirun node ...`, `urirun flow ...`,
`urirun scanner ...` powinny stać się shimami do paczek właścicielskich albo
zostać przeniesione do ich CLI (`urirun-service-chat`, `urirun-node`,
`urirun-flow`, `urirun-service-scanner`).

### Reguły Ekstrakcji

1. Najpierw kontrakt: paczka z trasą mutującą ma `contracts.json` albo
   `contracts.py` eksportujący do neutralnego JSON.
2. Potem paczka: kod runtime przenosi się do właściciela (`connector`,
   `service`, `flow`, `node`, `widgets`, `artifacts`).
3. Potem shim: stara ścieżka w `urirun` re-eksportuje i emituje deprecation
   warning, ale nie kopiuje implementacji.
4. Potem brama: `scripts/extraction_audit.py`, fleet coverage i test importu
   pilnują, że core nie importuje z powrotem ciężkiej warstwy.
5. Ekstrakcja jest zakończona dopiero po publikacji/pinningu albo po jawnym
   oznaczeniu paczki jako compatibility meta-package.

Cel (historyczny): odchudzic `urirun` do malego runtime/contract core i wyniesc
integracje oraz aplikacje hosta do osobnych paczek. Obecny stan miesza trzy
warstwy:

- core runtime: URI, registry, schema, policy, executors,
- connectory: planfile, SQLite, domain monitor, Namecheap,
- aplikacje hosta: mesh, node server, dashboard, task loop, scheduler.

To powoduje, ze `urirun.v2` i `urirun.mesh` sa hotspotami: CLI, registry,
host app i konkretne integracje znajduja sie w tych samych modulach.

## Slownik publiczny

- `runtime` - core uruchamiajacy URI przez binding, adapter i executor.
- `connector` - paczka integracyjna, np. Namecheap, MQTT, planfile, SQLite.
- `adapter` - sposob wykonania bindingu, np. `argv-template`,
  `shell-template`, `http-service`, `mqtt-publish`, `python-call`.
- `binding` - deklaracja `URI -> kind/adapter/config/schema/policy/ref`.
- `registry` - skompilowany i zwalidowany katalog tras URI.
- `flow` - uporzadkowana sekwencja wywolan URI.
- `host app` - aplikacja operatora: mesh, node discovery, dashboard, task loop.
- `runtime SDK` - port jezykowy/runtime, np. Python, JS, C. Nie uzywac tu slowa
  `adapter`, bo `adapter` ma znaczyc mechanizm wykonania.

## Nazwy repo i domen

Rekomendowany podzial docelowy:

```txt
if-uri/urirun        core runtime + SDKs/runtimes
if-uri/connectors    connector packages
if-uri/app           host/node/dashboard application
if-uri/flows         reusable URI flows
if-uri/registry      generated connector/flow catalog
```

Strony:

```txt
connect.ifuri.com   landing + getting started
hub.ifuri.com       katalog connectorow, flows i registry
registry.ifuri.com  maszynowy endpoint katalogu, jesli bedzie potrzebny
```

Na start mozna trzymac to jako monorepo z katalogami `packages/*`, a osobne
repozytoria wydzielac dopiero, gdy connector ma wlasny cykl wydan.

## Docelowe pakiety Python

```txt
urirun
  Stabilne API publiczne, CLI core, registry, runtime.

urirun-connectors-namecheap
  Import: urirun_connectors.namecheap

urirun-connectors-planfile
  Import: urirun_connectors.planfile

urirun-connectors-sqlite
  Import: urirun_connectors.sqlite

urirun-connectors-domain-monitor
  Import: urirun_connectors.domain_monitor

ifuri-host
  Import: ifuri_host
  CLI: ifuri host ..., ifuri node ..., opcjonalnie aliasy urirun host/node.
```

Dystrybucje moga miec nazwy z myslnikami, ale import powinien byc namespace:

```txt
urirun_connectors.namecheap
urirun_connectors.planfile
urirun_connectors.sqlite
```

## Stabilne API dla connectorow

Connector nie powinien importowac `urirun.v2`. Publiczne API powinno byc
wersjonowane kontraktem danych, nie sciezka modulu:

```python
import urirun

@urirun.command(
    "dns://host/records/command/plan",
    adapter="python-call",
    kind="command",
    meta={"connector": "namecheap"},
)
def plan_dns(domain: str, ensure_records: list[dict] | None = None):
    ...

def urirun_bindings():
    return urirun.connector_bindings(connector="namecheap")
```

Entry point connectora:

```toml
[project.entry-points."urirun.connectors"]
namecheap = "urirun_connectors.namecheap:urirun_bindings"
```

Core powinien umiec:

```bash
urirun connectors list
urirun connectors bindings --out generated/bindings.json
urirun connectors registry --out generated/registry.json
```

Aktualny guard migracyjny:

```bash
urirun compat list
urirun compat check --json
```

`compat` jest metadata-only: nie importuje `mesh`, dashboardu, host DB ani
connector runtime. Pokazuje, ktory legacy modul nadal istnieje w core, jaka
paczka go zastapi i czy replacement jest widoczny jako import oraz entry point
`urirun.bindings`.

## Mapowanie obecnych modulow

| Obecny modul | Docelowa paczka | Uzasadnienie |
| --- | --- | --- |
| `urirun.__init__` | `urirun` core | Publiczne API, ale powinno eksportowac tez dekoratory i registry helpers. |
| `urirun._registry` | `urirun` core | Parser, translate, resolve, entry points, registry document. |
| `urirun._runtime` | `urirun` core | Policy, built-in executors, envelope, dry-run/execute. |
| `urirun._scan` | `urirun` core | Adoption/generator artefaktow, ale bez integracji hostowych. |
| `urirun.v2` | rozbic | Zostawic core CLI/API; wyniesc task/data/monitor bindings i runnery. |
| `urirun.v1` | `urirun` legacy albo `urirun_legacy` | Zachowac kompatybilnosc, potem deprecate. |
| `urirun.v2_service` | `urirun` transport core | `http-service` jest podstawowym mechanizmem wykonania zdalnego. |
| `urirun.v2_grpc` | `urirun-transport-grpc` albo optional extra | Transport opcjonalny, nie host app. |
| `urirun.v2_mcp` | `urirun-interop-mcp` albo optional extra | Projekcja registry na MCP/A2A, zalezy od core registry. |
| `urirun.v2_adopt` | `urirun` core lub `urirun-adopt` | Generator bindingow z artefaktow; nie powinien znac host app. |
| `urirun.planfile_adapter` | `urirun_connectors.planfile` | Integracja z planfile, osobny optional dependency. |
| `urirun.host_db` | `urirun_connectors.sqlite` | SQLite context store jako connector `data://`, `artifact://`, `check://`, `log://`. |
| `urirun.domain_monitor` | `urirun_connectors.domain_monitor` | HTTP/DNS/browser/log flow, connector operacyjny. |
| `urirun.namecheap_dns` | `urirun_connectors.namecheap` | Provider DNS/API, oddzielne sekrety i testy. |
| `urirun.task_planner` | `ifuri_host` | Chat/NL -> planfile tasks to logika aplikacji hosta. |
| `urirun.scheduler` | `ifuri_host` | Harmonogram kolejek hosta, nie core. |
| `urirun.mesh` | `ifuri_host` | Host/node discovery, A2A/MCP/URI aggregation, queue runner. |
| `urirun.host_dashboard` | `ifuri_host` | UI operatora i API dashboardu. |

## Co wyciac z `urirun.v2`

Zostaje w core:

- `command`, `shell`, `connector_bindings`,
- schema generation and validation,
- `compile`, `validate`, `scan`, `list`, `run`,
- built-in execution adapters: `argv-template`, `shell-template`,
  `http-service`, optionally Docker/process primitives,
- stable loader dla connector entry points.

Do connectorow:

- `PLANFILE_TASK_SCHEMA`, `planfile_task_bindings`, `run_planfile_task`,
- `HOST_DATA_SCHEMA`, `host_data_bindings`, `run_host_data`,
- `DOMAIN_MONITOR_SCHEMA`, `domain_monitor_bindings`, `run_domain_monitor`.

Do host app:

- `host` CLI subtree,
- `node` CLI subtree,
- task queue loop,
- mesh discovery,
- dashboard serve.

Po refaktorze `urirun.v2.main` nie powinien importowac `planfile_adapter`,
`host_db`, `domain_monitor`, `namecheap_dns`, `mesh` ani `host_dashboard`.

## Runtime SDK rename

Obecny katalog:

```txt
adapters/python
adapters/js
adapters/c
```

powinien docelowo przestac uzywac slowa `adapters`. Propozycja:

```txt
runtimes/python
runtimes/js
runtimes/c
```

Alternatywa:

```txt
sdks/python
sdks/js
sdks/c
```

Rekomendacja: `runtimes/*`, bo Python/JS/C sa implementacjami runtime i CLI,
nie tylko klientami SDK.

## Minimalny kontrakt connectora

Kazdy connector powinien miec:

```txt
pyproject.toml
src/urirun_connectors/<name>/__init__.py
src/urirun_connectors/<name>/bindings.py
src/urirun_connectors/<name>/runtime.py
tests/
README.md
```

`bindings.py`:

```python
def bindings(target: str = "host", **options) -> dict:
    return {
        "version": "urirun.bindings.v2",
        "bindings": {
            "dns://host/records/command/plan": {
                "kind": "command",
                "adapter": "python-call",
                "ref": "urirun_connectors.namecheap.runtime.plan",
                "config": {"inputSchema": PLAN_SCHEMA},
                "policy": {"allowExecute": True},
            }
        },
    }
```

`__init__.py`:

```python
def urirun_bindings():
    from .bindings import bindings
    return bindings()
```

Entry point discovery laczy wszystkie connector bindings w jeden dokument,
potem `urirun compile` tworzy registry.

## Kolejnosc migracji

### Faza 0 - zamrozenie slownika

- Przyjac publiczne znaczenia `connector`, `adapter`, `runtime`, `host app`.
- Dodac aliasy w dokumentacji.
- Nie przenosic jeszcze kodu.

### Faza 1 - stabilne API core

- Wyeksportowac z `urirun.__init__`:
  - `command`,
  - `shell`,
  - `connector_bindings`,
  - `compile_registry`,
  - `load_registry_arg`.
- Dodac `urirun connectors ...` jako loader entry pointow.
- Nie wymagac od connectorow importu `urirun.v2`.

### Faza 2 - connector planfile

- Przeniesc `planfile_adapter.py`.
- Przeniesc `PLANFILE_TASK_SCHEMA`, `planfile_task_bindings`,
  `run_planfile_task`.
- W core zostawic compatibility shim z ostrzezeniem deprecation.
- Test: stary `urirun host task bindings` dziala przez host app, a registry
  moze byc wygenerowane z entry pointa connectora.

### Faza 3 - connector sqlite/context

- Przeniesc `host_db.py`.
- Connector wystawia `data://`, `artifact://`, `check://`, `log://`.
- Host dashboard korzysta z connector API, nie z `urirun.host_db`.

### Faza 4 - connector domain-monitor i Namecheap

- Przeniesc `domain_monitor.py`.
- Przeniesc `namecheap_dns.py`.
- `domain-monitor` moze zalezec opcjonalnie od `namecheap` albo delegowac przez
  registry do `dns://.../records/command/plan`.
- Namecheap ma osobne testy mock/sandbox i osobny zestaw env vars.

### Faza 5 - host app

- Przeniesc `mesh.py`, `task_planner.py`, `scheduler.py`,
  `host_dashboard.py` do `ifuri_host`.
- CLI:
  - `ifuri host ...`
  - `ifuri node ...`
  - opcjonalnie alias `urirun host ...` przez extra `urirun[host]`.
- Host app sklada registry z connectorow, ale core nie zna host app.

### Faza 6 - runtime folder rename

- Przeniesc `adapters/python` -> `runtimes/python`.
- Przeniesc `adapters/js` -> `runtimes/js`.
- Przeniesc `adapters/c` -> `runtimes/c`.
- Zachowac przez jeden release aliasy/instrukcje instalacji dla starych sciezek.

### Faza 7 - registry CI

- Publiczny registry generowac w CI z:
  - zainstalowanych connectorow,
  - manifestow flow,
  - testowych fixtures.
- Nie commitowac recznie wygenerowanych registry jako zrodla prawdy.

## Kryteria sukcesu

- `urirun` core instaluje sie bez `planfile`, `litellm`, Namecheap, dashboardu.
- `python -c "import urirun"` nie importuje host app ani connectorow.
- `urirun run/list/compile/validate` dziala bez connectorow.
- Connector moze byc zainstalowany i odkryty przez entry point bez edycji core.
- Host dashboard dziala po instalacji `ifuri-host` i connectorow, nie przez core.
- `v2.py` traci host/data/monitor sections i zostaje ponizej sensownego rozmiaru.

## Decyzje do zatwierdzenia

1. Czy publiczna nazwa warstwy integracji to `connectors`?
2. Czy katalog `adapters/*` zmieniamy na `runtimes/*`?
3. Czy `ifuri-host` ma miec CLI `ifuri`, a `urirun host` tylko alias?
4. Czy startujemy jako monorepo `packages/*`, a osobne repo robimy pozniej?
5. Czy registry publiczne ma byc generowane w CI i publikowane na `hub.ifuri.com`
   lub `registry.ifuri.com`?
