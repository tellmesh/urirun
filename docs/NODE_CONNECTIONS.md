# Sposoby laczenia node, services i zewnetrznych runtime przez urirun

<!-- docs-nav -->
📖 **Dokumentacja urirun:** [← README](../README.md) · [Architektura](ARCHITECTURE.md) · [Komponenty](COMPONENTS.md) · [URI Objects](URI_OBJECTS.md) · **Łączenie node** · [Dashboard & chat](HOST_DASHBOARD_CHAT.md) · [Host↔Node](HOST_NODE_COMMUNICATION.md) · [Sekrety](SECRETS.md) · [Archiwum dok.](DOCUMENT_ARCHIVE.md) · [Decision Loop](DECISION_LOOP.md) · [Roadmap](REFACTOR_ROADMAP.md) · [Podział paczek](URIRUN_PACKAGE_SPLIT_PLAN.md) · [Planfile](PLANFILE_HOST_INTEGRATION_PLAN.md)
<!-- /docs-nav -->

Ostatnia aktualizacja: 2026-06-24.

Ten dokument zbiera w jednym miejscu aktualny, praktyczny model podlaczania
komputerow, uslug, przegladarek, telefonow, API i urzadzen do urirun. Jest
uzupelnieniem:

- `docs/COMPONENTS.md` - pojecia: host, node, service, connector, widget,
  artifact,
- `docs/HOST_NODE_COMMUNICATION.md` - protokol host-node,
- `docs/URI_OBJECTS.md` - kontrakt URI object,
- `docs/HOST_DASHBOARD_CHAT.md` - chat, widgets, artifacts i `urifix://`.

## Model w skrocie

urirun ma jeden nadrzedny model: operator wysyla intencje, host zamienia ja na
konkretne kroki URI, a kazdy krok trafia do obiektu, ktory ma wlasny transport i
runtime.

```text
intencja NL / flow YAML
  -> host
  -> wybrany URI object
  -> konkretna trasa URI
  -> wynik + verification/recovery
```

Najwazniejsze obiekty:

| Obiekt | Co reprezentuje | Przyklad |
| --- | --- | --- |
| `host` | lokalne centrum sterowania | komputer developera z dashboardem |
| `node:*` | kontrolowany runtime/komputer/API/device | `node:lenovo`, `node:crm-api` |
| `service:*` | dlugotrwala usluga z portem/API | `service:phone-scanner`, `service:chat` |
| `connector` | paczka zdolnosci URI | `ocr://`, `fs://`, `smartcrop://` |
| `widget` | zywy widok/status | live camera, service status |
| `artifact` | gotowy plik/wynik | PDF, JSON OCR, screenshot |

## Typy node w dashboardzie (zakladki)

Widok Nodes ma zakladki wyboru typu node (`data-kind`, `selectNodeKind`); wybrana
zakladka jest mirrorowana do URL jako `?kind=<typ>` (patrz HOST_DASHBOARD_CHAT.md
"URL State"). Kazdy typ to inny sposob laczenia opisany nizej:

| Zakladka | `data-kind` | Co to | Sposob / transport |
| --- | --- | --- | --- |
| 🖥️ Server | `server` | serwer/VM/kontener, dostep shell/SSH | Sposob 3 (`shell://`, deploy przez node) |
| 💻 PC | `pc` | desktop z aplikacjami + shell | Sposob 2 (`app://`, `shell://`, `screen://`) |
| 🪟 RDP | `rdp` | pulpit zdalny (RDP/VNC) — node po stronie zdalnego desktopu, obserwacja i wejscie | Sposob 2 (desktop) + `screen://`/`kvm://`; wymaga sesji graficznej |
| 📱 Smartphone | `smartphone` | telefon: najpierw webpage (przegladarka mobilna), potem APK | Sposob 5 (`service:android-node`, QR) |
| 🌐 Browser Debug | `browser-debug` | przegladarka przez Chrome DevTools Protocol | Sposob 4 (`browser://.../cdp/...`) |
| 🧩 Chrome Plugin | `browser-chrome-plugin` | rozszerzenie Chrome jako node | Sposob 4 (load unpacked) |
| 🧩 Firefox Plugin | `browser-firefox-plugin` | dodatek Firefox jako node | Sposob 4 (temporary add-on) |
| 📄 Webpage | `webpage` | pojedyncza strona JS rejestrowana jako node | Sposob 4/5 (QR → webpage node) |
| 🔌 API | `api` | zewnetrzne HTTP API z auth | Sposob 6 (`api://`, fetch + secret://) |
| 🧩 Device | `device` | urzadzenie multi-API (non-HTTP czesto) | Sposob 7 (device connector) |

## Sposob 1: klasyczny urirun node

To pelny runtime urirun na zdalnym komputerze, VM, kontenerze lub laptopie.

### Start node

Na maszynie node:

```bash
urirun node init --name lenovo --registry .urirun/registry.merged.json --port 8765
urirun node serve --execute
```

Node wystawia:

```text
GET  /health
GET  /routes
GET  /services
GET  /mcp/tools
GET  /a2a/card
POST /run
GET  /events
POST /deploy
POST /enroll
```

`/routes` jest zrodlem prawdy. MCP i A2A sa projekcjami tej samej powierzchni,
nie osobnym systemem funkcji.

### Zapis node na hoscie

Na hoscie:

```bash
urirun host init --name operator
urirun host add-node lenovo http://192.168.188.201:8766 --kind pc
urirun host nodes
urirun host routes
```

Jesli nie chcesz jeszcze zapisywac node w configu:

```bash
urirun host routes --node-url lenovo=http://192.168.188.201:8766 --json
urirun host run --node-url lenovo=http://192.168.188.201:8766 \
  lenovo env://laptop/runtime/query/health --payload '{}'
```

### Bezpieczenstwo node

Sa dwa rozne mechanizmy:

- enrollment PIN - krotki token z konsoli node, sluzy tylko do `uri-copy-id`,
- admin token / key-auth - autoryzuje `/deploy` i operacje administracyjne.

Typowy pierwszy enrollment:

```bash
uri-copy-id http://192.168.188.201:8766 \
  -i ~/.ssh/id_ed25519 \
  --enroll-token TOKEN_Z_KONSOLI_NODE
```

Po enrollment kolejny deploy moze isc podpisem SSH:

```bash
urirun host deploy lenovo \
  --bindings bindings.json \
  --code handler.py \
  --allow 'screen://**' \
  --allow 'kvm://**' \
  --merge \
  --identity ~/.ssh/id_ed25519
```

## Sposob 2: PC/desktop node

Typ `pc` oznacza pelny komputer z GUI. Przyklad: Lenovo.

```bash
urirun host add-node lenovo http://192.168.188.201:8766 --kind pc
```

Mozliwe powierzchnie:

| Schemat | Do czego | Warunek |
| --- | --- | --- |
| `screen://` | realny screenshot monitora | portal/Wayland/X11 backend |
| `kvm://` | klawiatura/mysz/OCR-click | input tool + OCR/backend |
| `browser://` | przegladarka przez CDP lub browser-control | debug/CDP albo connector |
| `fs://` | pliki na node | connector/route `fs://...` |
| `proc://` | procesy | route procesow na node |

Regula praktyczna: nie zakladamy, ze `browser://` dowodzi stanu fizycznego
ekranu. Do realnej obserwacji monitora zaczynamy od `screen://`/OCR.

## Sposob 3: server/VM/container node

Typ `server` to headless Linux, VM albo kontener z portem urirun.

```bash
urirun host add-node worker http://worker.local:8765 --kind server
```

Kontener nie jest osobnym typem obiektu. To dalej `node:*`; roznica jest w
runtime/transport, np. `runtime.type=docker`.

Warto podpinac w ten sposob:

- OCR worker,
- worker indeksowania plikow,
- usluge AI z lokalnym GPU,
- NAS/helper do plikow,
- osobny runtime do taskow dlugich.

## Sposob 4: browser-debug, pluginy i webpage

Sa cztery rozne tryby pracy z przegladarka. Nie nalezy ich mieszac:

| Typ | Kiedy uzywac | URI / transport |
| --- | --- | --- |
| `browser-debug` | cala przegladarka, wszystkie karty, CDP | `webnode://browser`, `cdp` |
| `browser-chrome-plugin` | aktywna karta przez rozszerzenie Chrome | `browser-plugin://chrome`, extension |
| `browser-firefox-plugin` | aktywna karta przez rozszerzenie Firefox | `browser-plugin://firefox`, extension |
| `webpage` | pojedyncza strona/karta przez JS/page bridge | `webpage://`, `webnode://page` |

`browser-debug` oznacza cala przegladarke sterowana przez CDP.

```bash
google-chrome --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1
urirun host add-node chrome-debug http://127.0.0.1:9222 --kind browser-debug
```

Plugin Chrome:

```bash
cd /home/tom/github/if-uri/chrome-plugin
make test
# chrome://extensions -> Developer mode -> Load unpacked
urirun host add-node chrome-plugin http://127.0.0.1:8765 --kind browser-chrome-plugin
```

Plugin Firefox:

```bash
cd /home/tom/github/if-uri/firefox-plugin
make test
# about:debugging#/runtime/this-firefox -> Load Temporary Add-on
urirun host add-node firefox-plugin http://127.0.0.1:8765 --kind browser-firefox-plugin
```

`webpage` oznacza pojedyncza strone/karte sterowana przez JS, CDP page scope albo
przez page bridge na porcie `8195`.

```bash
urirun host add-node checkout-page http://127.0.0.1:9222 --kind webpage
```

Webpage node powinien pokazywac route'y typu:

```text
webpage://<id>/page/query/info
webpage://<id>/page/query/devices
webpage://<id>/camera/command/start
webpage://<id>/sensor/query/capabilities
webpage://<id>/iframe/command/open
```

Serwis page bridge na porcie `8195` mozna podmienic bez recznego szukania PID:

```bash
urirun-android-node restart --host 0.0.0.0 --port 8195 --force-replace
```

albo przez dashboard URI:

```text
dashboard://host/service/android-node/command/restart
```

Kompatybilnosc: stare `kind:browser` mapuje sie do `browser-debug`, a stare
`kind:web` / `kind:webnode` do `webpage`.

## Sposob 5: smartphone/webpage/mobile node

Telefon mozna podpiac etapami:

1. webpage node - telefon otwiera strone z QR, sterowanie jest przez JS w stronie,
2. mobile node - APK/Termux/ADB daje pelniejszy dostep do plikow/systemu.

Przyklady sa w:

```text
/home/tom/github/if-uri/examples/47-android-nexus7-node
```

Smartphone jako webpage node jest dobry do:

- kamery przegladarkowej,
- formularzy i paneli web,
- lokalnego skanera przez WebRTC/MediaDevices.

Do latarki, pelnego filesystemu lub natywnej kontroli potrzebny jest zwykle
dedykowany mobile connector/service, np. ADB/Termux/APK.

## Sposob 6: API node

`api` node sluzy do zewnetrznych HTTP/REST/OpenAPI, SaaS lub lokalnych uslug,
ktore nie wystawiaja urirun `/health` i `/routes`.

Rejestracja z CLI:

```bash
urirun host add-node crm-api https://api.example.test/v1 \
  --kind api \
  --api-id main \
  --api-kind rest \
  --auth-type bearer \
  --auth-token 'PASTE_ONCE'
```

Token/API key jest przekazywany raz. Host probuje zapisac go w keyring jako:

```text
secret://keyring/urirun-node-api/<node>/<api>#credential
```

W configu zostaje `secretRef`, nie plaintext.

Host potrafi wykonac HTTP-like API bez osobnego connectora:

```text
configured://host/node-api/command/request
configured://host/node-api/query/status
api://crm-api/main/command/request
```

Payload:

```json
{
  "node": "crm-api",
  "apiId": "main",
  "method": "GET",
  "path": "/accounts",
  "query": {"limit": 10}
}
```

Granica: host nie importuje automatycznie OpenAPI do pelnego connectora. To jest
warstwa "configured HTTP call". Dla bogatszego API nadal warto wygenerowac albo
napisac connector.

## Sposob 7: device node

`device` node grupuje kilka interfejsow jednego urzadzenia: panel WWW, RTSP,
SMB/NFS, SSH, ONVIF itd.

Przyklad:

```bash
urirun host add-node rpi-camera http://rpi.local \
  --kind device \
  --api '{"id":"panel","kind":"web","url":"http://rpi.local"}' \
  --api '{"id":"stream","kind":"rtsp","role":"camera","url":"rtsp://rpi.local/live"}' \
  --api '{"id":"share","kind":"smb","url":"smb://rpi.local/share"}' \
  --api '{"id":"ssh","kind":"ssh","url":"ssh://pi@rpi.local"}'
```

Discovery pokazuje syntetyczne route'y:

```text
device://rpi-camera/panel/query/status
media://rpi-camera/stream/query/stream
camera://rpi-camera/stream/query/snapshot
fs://rpi-camera/share/query/list
ssh://rpi-camera/ssh/command/run
```

Co dziala teraz:

- `device://.../query/status` zwraca metadata interfejsu,
- HTTP-like interfejs `web/rest/openapi/http` moze byc wykonany przez host,
- nie-HTTP interfejsy zwracaja `connector_required`, jesli nie ma connectora.

Co musi przejac connector:

- RTSP/RTMP/HLS/ONVIF stream,
- SMB/NFS/SFTP filesystem,
- SSH shell,
- kamera snapshot bezposrednio z protokolu device.

To jest celowe: discovery pokazuje, co urzadzenie ma, ale wykonanie protokolu
nie jest udawane przez host.

## Sposob 8: URI service

Service to dlugo dzialajaca aplikacja z wlasnym portem/API. Przyklady:

- `urirun-service-chat` - dashboard/chat, domyslnie port `8194`,
- `urirun-service-scanner` - telefoniczny skaner dokumentow, domyslnie port
  `8196`,
- przyszle workery OCR, camera, NAS, webnode.

Service powinien miec URI lifecycle:

```text
service://host/<service>/query/status
service://host/<service>/command/start
service://host/<service>/command/restart
service://host/<service>/command/stop
```

Aktualny dashboard ma juz czesc tej powierzchni dla chat/scanner, ale docelowo
powinna byc konsekwentnie wyniesiona do pakietow `urirun-service-*`.

## Sposob 9: connector/adopt

Connector to paczka zdolnosci URI. Gdy istnieje biblioteka, CLI, Docker, API,
desktop app albo mobile app, najpierw mozna uzyc `adopt://`, zeby rozpoznac
najmniejszy wrapper.

Przyklad:

```bash
urirun run adopt://host/project/query/inspect \
  --entry-points \
  --execute \
  --payload '{"path":"/home/tom/github/wronai/ocr"}'
```

Scenariusz:

```text
inspect project -> plan adapter -> connector/service/widget/artifact boundary
  -> implement route -> verify contract -> publish/install
```

Przyklad opisowy:

```text
/home/tom/github/if-uri/examples/46-connect-anything
```

## Sposob 10: chat/dashboard jako operator

Dashboard na `8194` pokazuje:

- kontakty: host, node, service,
- discovery: obiekt po lewej, route'y po prawej,
- chat: intencja NL -> flow -> timeline -> wynik,
- artifacts: gotowe pliki,
- widgets: zywe widoki/statusy.

Operator powinien widziec kazda komende i odpowiedz jako wiadomosc:

```text
user prompt
system generated flow
URI / JSON
timeline
attachments/artifacts/widgets
verification/recovery
```

W URL powinny byc jawne wybrane targety, prompt i tryb:

```text
/?view=chat&targets=host,node:lenovo,service:phone-scanner&execute=1&prompt=...
```

## Co zostalo ostatnio zrobione

Landed w ostatniej serii zmian:

- dodane typy node: `server`, `pc`, `rdp`, `smartphone`, `browser-debug`,
  `browser-chrome-plugin`, `browser-firefox-plugin`, `webpage`, `api`, `device`,
- API/device node sa widoczne w dashboardzie i `GET /api/node-types`,
- `node_add()` zapisuje `apis[]`, `capabilities`, `kind:*` tags,
- tokeny API ida do keyring, w configu zostaje `secretRef`,
- discovery tworzy syntetyczne route'y dla API/device,
- host wykonuje HTTP-like API przez `configured://host/node-api/...`,
- direct `api://.../command/request` dziala jako wygodny alias,
- direct `device://.../query/status` zwraca metadata bez niepotrzebnego HTTP,
- non-HTTP device routes zwracaja `connector_required`,
- CLI `urirun host add-node` dostal `--kind`, `--api`, `--api-id`,
  `--api-kind`, `--auth-*`, `--capability`,
- dodany przyklad:
  `/home/tom/github/if-uri/examples/48-api-device-node`,
- zaktualizowane:
  `docs/COMPONENTS.md`, `docs/URI_OBJECTS.md`, wbudowane `/docs/nodes`,
- testy pokrywaja:
  zapis API/device node,
  keyring/secretRef,
  direct `api://` call,
  `device://.../query/status`,
  `connector_required` dla non-HTTP device routes,
  parser CLI.

Ostatni zielony zakres testow:

```text
166 passed, 1 warning
```

Pelny suite w obecnym sandboxie nie jest miarodajny, bo testy socketowe wpadaja
w `PermissionError: Operation not permitted`, a zwykly `pytest -q` ma import
mismatch przez duplikaty nazw testow w `tests/` i `adapters/python/tests/`.

## Co wczesniej nie bylo jasno udokumentowane

Brakowalo jednego miejsca opisujacego:

- roznice miedzy realnym urirun node a konfiguracyjnym API/device node,
- kiedy syntetyczna route z discovery jest wykonywalna, a kiedy wymaga
  connectora,
- ze `api://...` moze byc aliasem do hostowego configured request,
- ze `device://.../query/status` jest metadata/status, nie dowodem wykonania
  protokolu,
- jak dodawac API/device node z CLI, bez dashboardu,
- gdzie zapisuje sie sekret (`secretRef`/keyring),
- jak service, widget i artifact maja sie do node,
- ktore elementy sa juz zaimplementowane, a ktore sa tylko kontraktem/planem.

Ten dokument domyka te luki.

## Plan zadan

### P0 - domknac niezawodnosc wykonania

- [x] Wykonanie HTTP-like API z configu hosta przez `configured://`.
- [x] CLI do dodawania API/device node bez recznej edycji JSON.
- [x] `connector_required` dla nie-HTTP device routes.
- [ ] Dodac structured recovery dla `connector_required`: proponowany connector,
  komenda instalacji i retry payload.
- [ ] Dodac verification contract do kazdej side-effect route w dashboardzie:
  expected/actual, checks, retryable, recoveryUri.
- [ ] Rozszerzyc `urifix://` o przypadki: missing connector, missing API auth,
  missing node URL, service stopped, port busy, failed verification.

### P1 - doprowadzic discovery do jednego modelu

- [x] `summary.objects` i `/api/objects` dla `host`, `node:*`, `service:*`.
- [x] Discovery UI pokazuje obiekty i route'y.
- [ ] Wszystkie widoki dashboardu powinny uzywac URI object jako zrodla prawdy,
  bez lokalnych list fallbackowych tam, gdzie obiekty sa dostepne.
- [ ] `urirun host routes` powinien jasno oznaczac route jako:
  `executable`, `metadata`, `connector_required`, `external`.
- [ ] Dla API/device dodac `capability doctor`: auth, health/status endpoint,
  wymagany connector, znany owner.

### P1 - service lifecycle

- [x] Oddzielone pakiety `urirun-service-chat` i `urirun-service-scanner`.
- [x] Dashboard potrafi pokazywac service contacts i czesc lifecycle.
- [ ] Ujednolicic route'y:
  `service://.../query/status`,
  `service://.../command/start`,
  `service://.../command/restart`,
  `service://.../command/stop`.
- [ ] Restart po tym samym porcie powinien miec jeden wspolny helper:
  detect owner -> graceful stop -> kill fallback -> start -> health check.
- [ ] Chat powinien wyswietlac restart/start jako flow z verification, nie tylko
  jako tekst.

### P1 - non-HTTP device connectory

- [ ] `urirun-connector-rtsp` albo camera/media connector:
  `media://.../query/stream`, `camera://.../query/snapshot`.
- [ ] `urirun-connector-ssh-device`:
  `ssh://.../command/run` dla device node z auth/known_hosts.
- [ ] `urirun-connector-fileshare`:
  `fs://.../query/list`, copy/sync dla SMB/NFS/SFTP.
- [ ] ONVIF/IP-camera profile dla device node.

### P2 - uproszczenie boilerplate

- [ ] Wyniesc z `host_dashboard.py` kolejne moduly:
  API node handling, node forms docs, URI invoke routing, HTML widgets.
- [ ] Dodac wspolny SDK dla service/widget/artifact descriptorow.
- [ ] Connectory powinny zwracac artifact descriptors, a host/service ma je
  rejestrowac w jednym registry.
- [ ] Zmniejszyc powielanie w examples: helper do `intent -> flow -> result ->
  verification`.

### P2 - testy i CI

- [ ] Rozdzielic/zmienic nazwy zdublowanych testow powodujacych import mismatch.
- [ ] Oznaczyc testy wymagajace socketow markerem, zeby w sandboxie mozna bylo
  uruchamiac bez falszywych porazek.
- [ ] Dodac testy e2e dla przykładu `48-api-device-node` bez zewnetrznej sieci.
- [ ] Dodac smoke test dashboard `/api/nodes/api/request`.

## Najprostsza sciezka operatorska

1. Jesli to komputer z urirun runtime:

```bash
urirun host add-node NAME http://HOST:8765 --kind pc
urirun host probe NAME
```

2. Jesli to zewnetrzne HTTP API:

```bash
urirun host add-node NAME https://api.example/v1 \
  --kind api --api-id main --api-kind rest --auth-type bearer --auth-token TOKEN
```

3. Jesli to urzadzenie z kilkoma protokolami:

```bash
urirun host add-node NAME http://device.local \
  --kind device \
  --api '{"id":"panel","kind":"web","url":"http://device.local"}' \
  --api '{"id":"stream","kind":"rtsp","url":"rtsp://device.local/live"}'
```

4. Jesli brakuje route:

```text
connector_required -> connectors resolve/install -> verify routes -> retry
```

5. Jesli operacja ma skutki uboczne:

```text
preflight -> execute -> verification contract -> urifix/retry albo done
```
