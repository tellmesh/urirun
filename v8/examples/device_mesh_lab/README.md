# Device mesh lab: NL to URI flow across computers

This example ports the idea from
`/home/tom/github/tellmesh/urisys-automation-lab/flows/*` into the `urirun`
model.

The key difference is that every computer first exposes a small URI interface:

```txt
GET  /device
GET  /routes
GET  /processes
POST /run { "uri": "...", "payload": {} }
```

The controller discovers those agents, compiles a `urirun.v8` registry from
their routes, lets LiteLLM generate a workflow from natural language, validates
the workflow against the registry, and executes only available safe URI routes.

## Run locally

This starts two local agents that simulate two computers:

```bash
cd /home/tom/github/tellmesh/urihandler/v8/examples/device_mesh_lab
make start
```

Open:

```txt
http://127.0.0.1:8193/
```

Local demo agents listen on:

```txt
desktop: http://127.0.0.1:18765
laptop:  http://127.0.0.1:18766
```

The page shows:

- reachable devices,
- process list from each device,
- URI commands each device can execute,
- missing/installable adapters such as KVM, RDP, OCR, STT,
- a natural-language input that generates and runs a URI workflow.

Run the fixed safe flow:

```bash
make flow
```

Stop the demo:

```bash
make stop
```

## LLM

The controller reads `LLM_MODEL` and provider keys from the project root `.env`:

```env
LLM_MODEL=openrouter/...
OPENROUTER_API_KEY=...
```

The browser never receives these values. If LiteLLM is unavailable or the model
fails, the controller falls back to a deterministic workflow.

## Why the old automation lab was brittle

The old flows used URI notation, but many actions assumed a local GUI/RDP/KVM
runtime already existed:

```yaml
- kvm://local/monitor/primary/query/screenshot
- ocr://local/image/latest/query/text
- him://local/keyboard/command/type-text
```

That can work, but only after the target computer has installed and registered
those adapters. In this example the controller does not guess. It asks each
device what it supports. Unsupported capabilities appear as installable items,
not executable routes.

## Safe default capability set

Every agent exposes:

```txt
device://<device>/capabilities/query/list
device://<device>/installable/query/list
env://<device>/runtime/query/health
proc://<device>/process/query/list
proc://<device>/process/query/find
shell://<device>/command/uname
shell://<device>/command/date
shell://<device>/command/which
browser://<device>/page/command/open
note://<device>/operator/command/write
log://<device>/session/command/write
log://<device>/session/query/recent
```

There is intentionally no arbitrary shell route. If you want package install,
KVM, OCR, RDP, browser automation, or STT, add a dedicated adapter and route for
that capability.

## Real two-computer setup

See [docs/LAPTOP_SETUP.md](docs/LAPTOP_SETUP.md).

## Mapping old flows

See [docs/URISYS_AUTOMATION_LAB_MAPPING.md](docs/URISYS_AUTOMATION_LAB_MAPPING.md).
