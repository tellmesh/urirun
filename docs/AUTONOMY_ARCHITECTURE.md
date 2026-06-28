# Architektura autonomii urirun

<!-- docs-nav -->
📖 **Dokumentacja urirun:** [← README](../README.md) · [Architektura](ARCHITECTURE.md) · **Autonomia** · [Komponenty](COMPONENTS.md) · [Decision Loop](DECISION_LOOP.md) · [Roadmap](REFACTOR_ROADMAP.md)
<!-- /docs-nav -->

Status: 2026-06-28.

Ten dokument opisuje docelową warstwę autonomii. Szczegóły AS-IS komponentów są
w [ARCHITECTURE.md](ARCHITECTURE.md); tutaj zapisujemy zasadę podejmowania
decyzji, żeby nie budować kolejnego wielkiego drzewa heurystyk w `chat_orchestrator`.

## Teza

Autonomia nie polega na tym, że jeden centralny moduł zna wszystkie przypadki.
Polega na tym, że LLM, recall albo heurystyka mogą proponować plan, ale plan
musi przejść jedną deterministyczną bramę akceptacji względem kontraktów,
routera, policy i aktualnego stanu Digital Twin.

```text
NL intent + action_space + twin_state
  -> candidate plan                  # LLM / recall / heuristic
  -> deterministic acceptance gate    # router + contracts + policy + env domains
  -> execute or typed block           # no silent fallback
```

Uniwersalna jest brama akceptacji, nie graf `if/else`. Nowa zdolność powinna
dodać kontrakt URI i ewentualne domeny środowiskowe, a nie nową gałąź w
orchestratorze.

## Funkcja planowania

Router traktujemy jak czystą funkcję stanu:

```text
plan(intent, twin_state, action_space) -> routing_plan
```

`twin_state` pochodzi z `twin://*/env/query/drift` i
`twin://*/env/query/inventory`. `action_space` pochodzi z registry i kontraktów
URI. Jeżeli stan środowiska się zmienia, plan może i powinien się zmienić. Jeżeli
intencja i fingerprint środowiska są takie same, recall może stabilizować
znany-dobry plan, ale nadal musi przejść tę samą bramę.

To rozdziela dwa przypadki:

- różny plan po zmianie środowiska jest adaptacją;
- różny plan przy tym samym stanie i tej samej intencji jest niestabilnością,
  którą ogranicza recall + deterministic acceptance.

## Brama Akceptacji

`urirun-connector-router` wystawia dwie warstwy:

```text
router://host/plan/query/diagnose
router://host/plan/query/accept
```

`diagnose` tłumaczy kandydatów na decyzje routingu: route istnieje, target znany,
transport osiągalny, capability pasuje, side effect jest widoczny. `accept`
dodaje predykat dopuszczenia planu: plan jest akceptowany tylko wtedy, gdy kroki
są routowalne i deklarowany efekt kontraktu nie kłóci się z efektem wynikającym
z URI (`query`/`command`).

`urirun-flow` używa tej bramy przed wykonaniem, gdy `router_guard=True`. Błąd
akceptacji nie jest maskowany jako sukces flow: wraca typed block z listą
`violations`.

## LLM Proponuje, Kernel Rozstrzyga

LLM może:

- wybrać intencję i złożyć kandydat flow;
- użyć action-space z registry/kontraktów;
- naprawić plan po typed block;
- zaproponować alternatywną trasę.

LLM nie może:

- samodzielnie uznać mutującej trasy za bezpieczną;
- ominąć `runsOn` i policy;
- rozstrzygać dostępności node bez routera/twina;
- traktować recall jako dowodu, że obecny stan nadal pasuje.

Reguła: LLM proponuje plany, nie bramy.

## Digital Twin Jako Stan Wejściowy

Twin ma dwa osobne zadania:

- `drift`: czy znany dobry profil nadal pasuje;
- `inventory`: jakie opcje środowiskowe istnieją teraz.

Inventory zwraca domeny runtime, np. `env:monitors.id`,
`env:cdp_endpoints.id`, `env:audio_sinks.id`, `env:cameras.id`. Kontrakty mogą
zadeklarować parametr jako `env-enum`, a `urirun_flow.env_selection` stosuje
regułę:

1. jawna wartość z promptu/payloadu;
2. jedyna dostępna opcja;
3. preferencja zapamiętana dla aktualnego fingerprintu;
4. typed `needs-selection` z listą opcji.

Chat renderuje `needs-selection`; nie powinien mieć własnego `if monitors > 1`.

## Pamięć I Preferencje

Preferencje środowiskowe są częścią Digital Twin, a nie UI. Przykład:
`screen.capture.default` jest zapamiętywane z fingerprintem środowiska. Dzięki
temu wybór monitora z układu z dockiem nie zostanie po cichu zastosowany po
odłączeniu docka.

Kodowo właścicielem preferencji capture jest `urirun_twin.capture_preferences`.
`chat_orchestrator` tylko aplikuje tę funkcję w ścieżce orchestration.

## Pętla Decyzyjna

Docelowa pętla autonomii:

```text
observe:   drift + inventory + routes + contracts
propose:   LLM / recall / heuristic -> candidate flow
validate:  router accept + contract gate + env-selection + policy
execute:   connector/node/service transport
learn:     remember successful flow and fingerprint-scoped preferences
repair:    typed block -> next candidate or human task
```

Każde przejście przez pętlę może odświeżyć stan. Przykład: `ensure(cdp)` może
ożywić sesję, więc kolejny krok nie powinien używać starej diagnozy sprzed
`ensure`.

## Granice Implementacyjne

Logika, która powinna opuszczać `chat_orchestrator`:

- target resolution i routing preview -> `urirun-connector-router` /
  `urirun-flow`;
- env-enum resolution -> `urirun_flow.env_selection`;
- preferencje środowiska -> `urirun_twin.*`;
- render widgetów i kart wyboru -> `urirun-widgets`;
- policy safety -> kontrakt/router/policy kernel.

`chat_orchestrator` zostaje warstwą rozmowy: zbiera prompt, pokazuje preview,
wysyła typed blocks do UI i uruchamia flow po zielonej bramie.

## Aktualne Domknięcia

- `twin://*/env/query/inventory` istnieje w thin driverze i dostarcza domeny
  monitorów/CDP dla flow KVM.
- `env-enum` jest deklarowane w kontrakcie KVM capture i rozwiązywane przez
  `urirun_flow.env_selection`.
- `screen.capture.default` jest pamiętane z fingerprintem środowiska.
- `router://host/plan/query/accept` i `accept_plan()` są bramą akceptacji planu.
- Preferencje capture przeniesiono do `urirun_twin.capture_preferences`.

## Nadal Do Zrobienia

1. W UI dorysować pełną, klikalną kartę `needs-selection` i akcję zapisu
   wyboru bez ręcznego wpisywania payloadu.
2. Przenieść resztę target/capture routing heuristics z `chat_orchestrator` do
   router/flow, zostawiając shimy tylko dla kompatybilności testów.
3. Rozszerzyć `accept_plan` o kolejne niezmienniki kontraktu: required inputs,
   destructive policy, human-gated tasks i conformance koperty.
4. Dodać przykład acceptance-loop w `examples/*`, który przechodzi przez:
   inventory -> needs-selection -> remember preference -> auto-run przy tym samym
   fingerprintcie.
