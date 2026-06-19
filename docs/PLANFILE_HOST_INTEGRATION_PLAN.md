# Plan integracji urirun host z planfile

## Cel

`urirun host` ma zarządzać zadaniami, sprintami, statusami i realizacją prac przez
`planfile`, a nie przez własny system tasków. Host ma używać `planfile` jako
operacyjnego źródła prawdy dla:

- listy zadań dziennych i backlogu,
- statusów: `open`, `in_progress`, `review`, `done`, `blocked`, `canceled`,
- stanu wykonania: `pending`, `ready`, `running`, `waiting_input`, `done`,
  `failed`, `skipped`,
- grupowania w sprinty,
- historii zmian i notatek,
- integracji z LLM, CLI, REST API, GitHub/Jira/GitLab/markdown.

SQLite zostaje opcjonalną bazą kontekstu i wyników operacyjnych, ale nie zastępuje
`planfile` w warstwie zarządzania zadaniami.

W praktyce oznacza to dwa poziomy:

- `.planfile/` - runtime store ticketów, statusów, historii i sprintów,
- `planfile.yaml` - strategia/roadmapa, z której można wygenerować lub
  zaktualizować tickety w `.planfile/`.

## Co wykorzystujemy z planfile

1. `Planfile` i `PlanfileStore`
   - auto-discovery `.planfile/`,
   - plikowy store YAML z blokadą mutacji,
   - tworzenie, aktualizacja, listowanie, przenoszenie i kasowanie ticketów.

2. Modele Pydantic
   - `Ticket`, `TicketStatus`, `TicketSource`,
   - `TicketExecutor`, `TicketExecution`,
   - `TicketInputs`, `TicketOutputs`,
   - `Sprint`, `Strategy`, `Task`.

3. Kolejka wykonawcza
   - `Planfile.next_ticket()`,
   - `claim_ticket()`,
   - `start_ticket()`,
   - `complete_ticket()`,
   - `fail_ticket()`,
   - `wait_for_input()`,
   - `ready_ticket()`.

4. CLI
   - `planfile ticket create/list/update/next/import`,
   - `planfile dsl run`,
   - `planfile serve`,
   - `planfile sync`.

5. Importery
   - JSON/YAML/Markdown,
   - `code2llm`,
   - `vallm`,
   - `redup`.

6. LLM i DSL
   - `DSLParser` i `DSLExecutor` do prostych komend tekstowych,
   - `create_litellm_client()` i istniejące adaptery LLM dla generowania planów.

## Granice odpowiedzialności

`planfile` odpowiada za:

- zadania,
- sprinty,
- statusy,
- zależności między zadaniami,
- wykonanie kolejki,
- synchronizację z zewnętrznymi trackerami.

`urirun` odpowiada za:

- adresację URI,
- odkrywanie host/node,
- dispatch flow,
- komunikację z node przez HTTP/MCP/A2A,
- uruchamianie procesów URI,
- mapowanie zdarzeń runtime na tickety `planfile`.

SQLite odpowiada za:

- dane kontekstowe,
- profile domen i stron,
- wyniki checków,
- artefakty,
- sesje LLM,
- indeks wyszukiwania i dane wejściowe dla planowania.

## Docelowe URI

### Zadania

```txt
task://host/tickets/query/list
task://host/ticket/query/next
task://host/ticket/command/create
task://host/ticket/command/update
task://host/ticket/command/start
task://host/ticket/command/complete
task://host/ticket/command/fail
task://host/ticket/command/block
task://host/ticket/command/wait-for-input
task://host/ticket/command/ready
```

### Sprinty

```txt
sprint://host/sprints/query/list
sprint://host/sprint/command/create
sprint://host/ticket/command/move
```

### Planfile DSL

```txt
planfile://host/dsl/command/run
planfile://host/import/command/tickets
planfile://host/sync/command/run
```

### Flow i wykonanie

```txt
flow://host/ticket/command/attach
flow://host/ticket/command/run
flow://host/daily/command/run
```

### Dane kontekstowe w SQLite

```txt
data://host/datasets/query/list
data://host/dataset/command/create
data://host/record/command/upsert
data://host/records/query/search
data://host/sql/query/read-only
```

## Minimalny format ticketu dla urirun

Przykład ticketu tworzonego przez host po rozmowie z LLM:

```yaml
id: PLF-001
name: Daily check for ifuri.com
status: open
priority: high
sprint: daily
labels:
  - urirun
  - daily
  - domain
source:
  tool: urirun-host
  context:
    prompt: "sprawdz codziennie DNS i HTTPS dla ifuri.com"
executor:
  kind: uri-flow
  mode: automatic
  handler: flow://host/daily-domain-check
execution:
  queue: daily
  state: pending
  max_attempts: 3
inputs:
  prompt: "Check HTTPS, DNS and screenshot on failure"
  api_timeout_seconds: 30
outputs:
  artifacts: []
  notes: []
```

`TicketExecutor.kind = uri-flow` nie istnieje dziś jako standard w `planfile`, ale
możemy użyć pola tekstowego bez łamania modelu. Wykonawca `urirun` będzie rozumiał
ten `kind` jako flow URI.

## Plan wdrożenia

### Sprint 0 - decyzje i kompatybilność

Cel: potwierdzić, że `planfile` działa jako biblioteka i CLI w środowisku hosta.

Zakres:

- zainstalować `planfile` jako zależność developerską w środowisku `urirun`,
- uruchomić `planfile --help`,
- uruchomić `planfile ticket list`,
- sprawdzić inicjalizację `.planfile/` w katalogu testowym,
- potwierdzić format statusów i execution state.

Testy:

```bash
python3 - <<'PY'
from planfile import Planfile
pf = Planfile('/tmp/urirun-planfile-smoke')
t = pf.create_ticket(name='Smoke ticket', labels=['urirun'])
assert pf.get_ticket(t.id)
assert pf.list_tickets(sprint='current')
PY
```

Kryterium akceptacji:

- host może utworzyć i odczytać ticket bez używania CLI.

### Sprint 1 - adapter planfile w urirun

Cel: cienki adapter Python bez mieszania logiki `planfile` z mesh/orchestration.

Nowy moduł:

```txt
adapters/python/urirun/planfile_adapter.py
```

Funkcje:

- `load_planfile(project_path)`,
- `create_ticket(payload)`,
- `list_tickets(filters)`,
- `next_ticket(queue=None, sprint='current')`,
- `start_ticket(ticket_id)`,
- `complete_ticket(ticket_id, result=None, artifacts=None, note=None)`,
- `fail_ticket(ticket_id, error)`,
- `run_dsl(command)`.

Testy:

- unit test z `tmp_path`,
- test historii zmian po update,
- test `next_ticket()` z priorytetami i bug-first.

Kryterium akceptacji:

- adapter działa bez uruchamiania node,
- nie tworzy własnego formatu tasków.

### Sprint 2 - URI endpoints dla planfile

Cel: wystawić operacje `planfile` jako procesy URI hosta.

Nowe bindingi lokalne:

```txt
task://host/tickets/query/list
task://host/ticket/query/next
task://host/ticket/command/create
task://host/ticket/command/start
task://host/ticket/command/complete
task://host/ticket/command/fail
planfile://host/dsl/command/run
```

CLI:

```bash
urirun run task://host/ticket/command/create \
  --payload '{"name":"Check ifuri.com","labels":["daily","domain"]}'
```

Testy:

- dry-run zwraca plan bez mutacji,
- execute tworzy ticket w `.planfile/`,
- list zwraca ten ticket,
- fail/complete zapisują `outputs.notes`, `outputs.result` i `history`.

Kryterium akceptacji:

- każde podstawowe działanie taskowe hosta da się wykonać przez URI.

### Sprint 3 - host queue runner

Cel: host ma umieć pobrać kolejne zadanie z `planfile` i wykonać przypisany flow.

Nowe komendy:

```bash
urirun host task next --config ~/.urirun/mesh.json
urirun host task run PLF-001 --execute
urirun host task loop --queue daily --execute
```

Zasada wykonania:

1. `claim_ticket()`
2. `start_ticket()`
3. wykonanie `executor.handler`, np. `flow://host/daily-domain-check`
4. `complete_ticket()` z wynikiem i artefaktami albo `fail_ticket()`

Testy:

- ticket przechodzi `open -> in_progress -> done`,
- błędny flow kończy się `execution.state=failed`,
- ticket z `waiting_input` nie jest wykonywany automatycznie,
- retry respektuje `max_attempts`.

Kryterium akceptacji:

- `urirun host task loop` obsługuje jedną kolejkę bez ręcznego statusowania.

### Sprint 4 - chat LLM do ticketów

Cel: użytkownik pisze zdaniami, ale zapis do task store idzie przez `planfile`.

Wejście:

```txt
Dodaj codzienne sprawdzanie ifuri.com, z screenshotem gdy strona nie odpowiada.
```

Pipeline:

1. LLM rozpoznaje intencję.
2. LLM zwraca JSON zgodny z Pydantic schema.
3. Host pokazuje plan do akceptacji.
4. Po akceptacji tworzy ticket przez `task://host/ticket/command/create`.
5. Jeśli trzeba, tworzy też rekord kontekstowy w SQLite.

Nie wolno:

- pozwalać LLM na dowolny zapis SQL,
- pozwalać LLM na bezpośrednie `setHosts` w Namecheap,
- pomijać walidacji schematu.

Testy:

- fixture prompt -> expected JSON,
- prompt niejednoznaczny -> `waiting_input`,
- prompt tworzący task destrukcyjny -> wymaga `review` albo confirm.

Kryterium akceptacji:

- chat potrafi utworzyć ticket i przypisać flow bez ręcznej edycji YAML.

### Sprint 5 - SQLite jako baza kontekstu

Cel: host ma lokalną bazę danych do planowania, ale zadania zostają w `planfile`.

Plik:

```txt
~/.urirun/host.db
```

Tabele:

```sql
datasets(id, name, description, schema_json, created_at)
records(id, dataset_id, key, data_json, source_uri, confidence, created_at, updated_at)
artifacts(id, kind, uri, path, meta_json, created_at)
checks(id, subject, check_uri, status, result_json, created_at)
llm_sessions(id, title, created_at)
llm_messages(id, session_id, role, content, extracted_json, created_at)
```

URI:

```txt
data://host/record/command/upsert
data://host/records/query/search
artifact://host/artifact/command/register
check://host/checks/query/recent
```

Testy:

- JSON Schema per dataset,
- FTS/search dla rekordów tekstowych,
- ticket może linkować `records` przez `source.context`.

Kryterium akceptacji:

- host może planować zadania na podstawie zapisanych domen, stron i wyników checków.

### Sprint 6 - daily scheduler

Cel: codzienne zadania mają być uruchamiane automatycznie.

MVP:

- `systemd user timer` albo cron,
- komenda:

```bash
urirun host task loop --queue daily --execute --max-tickets 20
```

Dane:

- harmonogram w `TicketExecution.queue`,
- `labels: [daily]`,
- `sprint: daily`.

Testy:

- dry-run scheduler pokazuje tickety do wykonania,
- execute zapisuje wyniki do ticket outputs,
- awaria node blokuje ticket i dopisuje notatkę.

Kryterium akceptacji:

- codzienna kolejka działa bez ręcznego uruchamiania pojedynczych flow.

### Sprint 7 - domeny, HTTP, screenshoty

Cel: pierwsze realne zadania operacyjne bez automatycznej zmiany DNS.

URI:

```txt
monitor://ifuri.com/http/query/status
dns://ifuri.com/records/query/current
browser://lenovo/page/command/screenshot
log://host/daily/command/write
```

Flow:

```yaml
task:
  id: daily_domain_check
  title: Daily domain check
steps:
  - id: http
    uri: monitor://ifuri.com/http/query/status
    payload:
      url: https://ifuri.com
  - id: dns
    uri: dns://ifuri.com/records/query/current
    payload:
      provider: namecheap
  - id: screenshot
    uri: browser://lenovo/page/command/screenshot
    payload:
      url: https://ifuri.com
      when: failure
  - id: log
    uri: log://host/daily/command/write
    payload:
      event: daily_domain_check.finished
```

Testy:

- HTTP 200 zapisuje sukces,
- HTTP failure tworzy screenshot artifact,
- DNS mismatch tworzy ticket naprawczy, ale go nie wykonuje.

Kryterium akceptacji:

- system tworzy kontekstowe zadania naprawcze na podstawie wyników checków.

### Sprint 8 - Namecheap adapter

Cel: bezpieczne plan/apply dla DNS przez Namecheap API.

Status: zaimplementowane jako adapter `urirun.namecheap_dns` pod istniejącym
kontraktem `dns://.../records/...`.

URI:

```txt
dns://DOMAIN/records/query/current
dns://DOMAIN/records/query/expected
dns://DOMAIN/records/command/plan
dns://DOMAIN/records/command/apply
dns://DOMAIN/records/command/backup
```

Zasady:

- `query/current` tylko czyta,
- `plan` generuje diff,
- `backup` zapisuje obecne rekordy jako artifact,
- `apply` wymaga polityki `allowExecute`, backupu i jawnego confirm,
- `apply` odmawia wykonania, jeśli aktualne rekordy różnią się od
  zatwierdzonego planu, chyba że operator jawnie poda `allow_current_drift`,
- `apply` wysyła do `setHosts` pełny zestaw rekordów,
- LLM nie wywołuje `apply` bezpośrednio; może tworzyć ticket do review.

Sekrety:

- `.env` albo secret store,
- żadnych API key w ticketach,
- w `source.context` tylko nazwy profili, np. `namecheap_profile=ifuri`.

Testy:

- sandbox/mock Namecheap,
- test parsowania `getHosts`,
- test dodania rekordu,
- test backupu artifact,
- test odmowy `apply` bez backupu,
- test ochrony przed dryfem aktualnych rekordów,
- test URI runtime dla plan/backup/mock apply.

Kryterium akceptacji:

- system potrafi zaplanować i bezpiecznie wykonać zmianę DNS tylko po zatwierdzeniu.

### Sprint 9 - UI host dashboard

Cel: widok dla operatora.

Status: zaimplementowane jako lokalny dashboard `urirun host dashboard serve`.

Widoki:

- dzisiejsze zadania,
- sprinty,
- node status,
- ostatnie flow,
- artefakty,
- tickety `waiting_input`,
- tickety `blocked`,
- akcje `Start`, `Complete`, `Block`, `Run flow`.

Źródła danych:

- `planfile` REST API dla ticketów,
- `urirun host agents/routes` dla możliwości node,
- SQLite dla wyników checków i artefaktów.

Testy:

- smoke GUI,
- HTTP smoke test HTML + JSON API,
- responsywność mobile,
- brak możliwości odpalenia destrukcyjnych akcji bez confirm.

Kryterium akceptacji:

- operator może prowadzić dzień pracy z jednego widoku bez edycji YAML.

## Pierwszy zestaw ticketów do utworzenia w planfile

Po zaakceptowaniu tego planu utworzymy w `.planfile/` repo `urirun` tickety:

1. `Create urirun planfile adapter`
2. `Expose task URI endpoints backed by planfile`
3. `Add host task queue runner`
4. `Add chat-to-ticket planning path`
5. `Add host SQLite context database`
6. `Add daily scheduler example`
7. `Add domain monitor flow`
8. `Add safe Namecheap DNS plan/apply adapter`
9. `Add host dashboard task view`

Każdy ticket będzie miał:

- `source.tool=urirun-roadmap`,
- etykiety `urirun`, `planfile`,
- sprint zgodny z etapem,
- acceptance criteria z sekcji powyżej.

## Komendy kontrolne

Planfile:

```bash
planfile ticket list --sprint all --format table
planfile ticket next --format json
planfile dsl run 'create ticket "Check ifuri.com daily" priority=high labels=daily,domain'
planfile dsl run 'list tickets sprint=current status=open'
```

Urirun host:

```bash
urirun host nodes --config ~/.urirun/mesh.json
urirun host routes --config ~/.urirun/mesh.json
urirun host ask --config ~/.urirun/mesh.json --no-llm --execute "sprawdz stan lenovo i procesy"
```

Docelowo:

```bash
urirun host task next --config ~/.urirun/mesh.json
urirun host task run PLF-001 --config ~/.urirun/mesh.json --execute
urirun host task loop --config ~/.urirun/mesh.json --queue daily --execute
```

## Ryzyka

- `planfile` jest plikowym YAML store, więc przy dużej liczbie automatycznych
  zapisów trzeba pilnować blokad i atomowych zapisów.
- Status `medium` pojawia się w części starych danych, ale obecny bug-first
  ordering zna `critical`, `high`, `normal`, `low`; adapter powinien mapować
  `medium -> normal`.
- `planfile.yaml` i `.planfile/` to dwa różne poziomy: strategia vs store
  ticketów. `urirun host` powinien operować głównie na `.planfile/`.
- LLM musi działać przez schematy i URI, nie przez dowolny SQL ani shell.
- Namecheap `setHosts` może usunąć rekordy nieprzekazane w request, więc adapter
  musi robić pełny merge i backup.

## Decyzja techniczna

Wdrażamy `planfile` jako jedyny system zadań dla hosta. Nie tworzymy własnej
tabeli `tasks` w SQLite. SQLite używamy tylko dla danych kontekstowych,
artefaktów i wyników checków, które potem są linkowane do ticketów `planfile`.
