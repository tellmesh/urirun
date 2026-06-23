# urirun v2

v2 is schema-first command packaging.

It replaces custom `params.required/default` declarations with standard JSON
Schema and adds Python decorators that generate that schema from function
signatures.

## Decorator

```python
import urirun

@urirun.command("media://local/video/transcode")
def transcode(input: str, output: str, width: int = 1280, height: int = 720):
    return ["ffmpeg", "-i", "{input}", "-vf", "scale={width}:{height}", "{output}"]

@urirun.shell("shell://local/echo/message")
def echo(text: str):
    return "printf '%s\\n' '{text}'"
```

The decorator creates an `inputSchema` from Pydantic and stores the argv or shell
template as a normal v2 binding. The runtime validates payload/query values
against that schema, applies defaults, renders placeholders, and then runs the
command.

`urirun.v2.uri_command(...)` and `urirun.v2.uri_shell(...)` remain supported for
older code, but new connector packages should prefer the top-level
`@urirun.command(...)` and `@urirun.shell(...)` API.

The same top-level API also exposes registry helpers, so simple connector smoke
tests do not need versioned imports:

```python
bindings = urirun.connector_bindings(connector="media-tools")
registry = urirun.compile_registry(bindings)
routes = urirun.list_routes(registry)
result = urirun.run("media://local/video/transcode", registry, {"input": "a.mp4", "output": "b.mp4"})
```

Shell routes are real shell execution, but they stay behind the policy gate:
execution needs both an allow rule and `allowShellTemplates: true`.

## JSON binding

```json
{
  "bindings": {
    "media://local/video/transcode": {
      "kind": "command",
      "adapter": "argv-template",
      "inputSchema": {
        "type": "object",
        "required": ["input", "output"],
        "properties": {
          "input": { "type": "string" },
          "output": { "type": "string" },
          "width": { "type": "integer", "default": 1280 },
          "height": { "type": "integer", "default": 720 }
        },
        "additionalProperties": false
      },
      "argv": ["ffmpeg", "-i", "{input}", "-vf", "scale={width}:{height}", "{output}"]
    }
  }
}
```

## Artifact adoption

`urirun.v2 scan ./project` adopts common package standards:

- Dockerfile with `io.tellmesh.urirun.manifest=...`
- OCI-compatible labels such as `org.opencontainers.image.source`
- `package.json` scripts
- `pyproject.toml` `[project.scripts]`
- `Makefile` targets
- `*.sh` scripts
- explicit `urirun.manifest.json` / `bindings.v2.json`

This makes existing repositories behave like URI packages without manually
writing every endpoint.

The generated registry workflow is:

```bash
# scan artifacts and write a binding document
urirun scan ./project --out generated/bindings.v2.json

# scan and compile the registry in one command
urirun scan ./project \
  --out generated/bindings.v2.json \
  --registry-out generated/registry.json

# check the binding contract, then list the runtime routes
urirun validate generated/bindings.v2.json
urirun list generated/registry.json
```

The binding document is the portable package contract. The registry is the
runtime lookup tree used by dispatchers, orchestrators, HTTP backends, shell
clients, MCP servers, or Docker services.

## HTML app

```bash
git clone https://github.com/if-uri/examples.git
cd examples/06-html_uri_app
bash run.sh
```

The app renders routes and forms from `bindings.json`, then calls the Python v2
runtime through `POST /api/run`.

Execution is disabled by default. Use `06-html_uri_app/.env.example`
as the local `.env` template when you want to enable real argv or shell
execution.

## Docker URI flow

`if-uri/examples/09-docker_uri_flow` demonstrates multiple Docker services
communicating through URI-addressed resources:

- `python://python-worker/text/normalize`
- `node://node-worker/text/slugify`
- `shell://shell-worker/report/write`
- `python://python-worker/report/summary`

Generate the registry from supplied Docker/package/script artifacts:

```bash
git clone https://github.com/if-uri/examples.git
cd examples/09-docker_uri_flow
make registry
```

That command runs `urirun scan`, validates the generated bindings, and
writes a route listing to `generated/routes.txt`. It discovers service contracts
referenced by Dockerfile labels, worker `bindings.json` manifests, image build
routes, shell scripts, and Makefile targets.

Run the full Docker flow with:

```bash
cd examples/09-docker_uri_flow
make run
```

The orchestrator reads a compact YAML flow similar to
`uri2flow/examples/33_office_workflows`, resolves `_from` references between
steps, validates every referenced URI against `generated/registry.json`, and
dispatches each URI to the service named by the URI target.

## Generators from other languages

`if-uri/examples/05-generators` contains small generators for:

- plain JavaScript,
- Node.js scripts,
- TypeScript decorator-style declarations,
- PHP 8 attributes.

All of them produce the same v2 JSON contract. The runtime consumes the JSON,
not the source language.

## One-line binding generation

Append a PyPI install binding to a v2 binding document:

```bash
urirun add-pypi sampleproject --out urirun.bindings.v2.json
```

Append a generic command binding:

```bash
urirun add-command 'util://local/echo/message' \
  --argv 'python3 -c "import sys; print(sys.argv[1])" {text}' \
  --param text:string:required \
  --out urirun.bindings.v2.json
```

## CLI

```bash
git clone https://github.com/if-uri/examples.git
urirun scan examples/03-artifacts --out /tmp/v2.bindings.json
urirun validate /tmp/v2.bindings.json
urirun compile /tmp/v2.bindings.json --out /tmp/v2.registry.json
urirun run tool://local/report/render --registry /tmp/v2.registry.json --payload '{"name":"Ada"}'
```

## Host / Node mesh

The v2 CLI can also act as a small URI mesh coordinator.

On a node, serve a registry over HTTP:

```bash
urirun node init --name pc1 --registry .urirun/registry.merged.json --port 8765
urirun node serve --execute
```

The node exposes:

- `GET /health`  (also reports `kind` + `runtime` + `serviceCount`)
- `GET /routes`
- `GET /services`  (long-running apps the node manages — a URI Service)
- `GET /mcp/tools`
- `GET /a2a/card`
- `POST /run`
- `POST /deploy`  (admin-gated; `--persist` survives a restart)

Every urirun endpoint is the same object — a **URI Node** — be it a laptop, a VM, or a
container. A containerised node is just a node with `runtime.type: docker` (a "capsule"),
not a separate kind. See the README's *URI Node model* section.

On a host, register nodes and ask for work in natural language:

```bash
urirun host init --name operator
urirun host add-node pc1 http://pc1.local:8765
urirun host add-node pc2 http://pc2.local:8765

urirun host agents   # A2A cards, MCP tools, URI processes
urirun host routes   # URI routes from all reachable nodes

URIRUN_LLM_MODEL=openrouter/qwen/qwen3-coder-next \
urirun host ask "sprawdź procesy na wszystkich komputerach" --execute
```

If the LLM is unavailable, `host ask` falls back to a deterministic heuristic
for common requests such as process listing, logs, browser open, `which python3`,
`date` and `uname`.

## Host tasks through planfile

Install the optional dependency when the host should manage work items:

```bash
pip install "urirun[planfile] @ git+https://github.com/if-uri/urirun.git@v0.3.12#subdirectory=adapters/python"
```

`urirun host task` keeps tasks in planfile's `.planfile/` store and uses
planfile status/execution models. A ticket can carry `inputs.prompt`; `task run`
uses that prompt to build the same URI flow that `host ask` would build.

```bash
urirun host task create "Check lenovo daily" \
  --project . \
  --queue daily \
  --prompt "sprawdz stan lenovo i procesy"

urirun host task list --project .
urirun host task next --project . --queue daily

# dry-run by default
urirun host task run PLF-001 --project . --config ~/.urirun/mesh.json --no-llm

# execute and write result back to planfile outputs/history
urirun host task run PLF-001 --project . --config ~/.urirun/mesh.json --no-llm --execute
urirun host task loop --project . --config ~/.urirun/mesh.json --queue daily --execute
```

Serve the local host dashboard:

```bash
urirun host dashboard serve \
  --project . \
  --db ~/.urirun/host.db \
  --config ~/.urirun/mesh.json \
  --port 8194
```

Generate a daily scheduler:

```bash
urirun host task schedule \
  --project . \
  --config ~/.urirun/mesh.json \
  --queue daily \
  --time 07:30 \
  --run-execute \
  --no-llm
```

Chat/NL planning is a dry-run by default and writes only with `--create`:

```bash
urirun host task plan \
  "Dodaj codzienne sprawdzanie ifuri.com, z screenshotem gdy strona nie odpowiada." \
  --project . \
  --no-llm

urirun host task plan \
  "Dodaj codzienne sprawdzanie ifuri.com, z screenshotem gdy strona nie odpowiada." \
  --project . \
  --create
```

Ambiguous prompts produce a `waiting_input` ticket. Destructive prompts are
planned into the `review` queue with `executor.mode=interactive`.

Host context data lives in SQLite, separate from planfile tasks:

```bash
urirun host data init
urirun host data dataset-create domains \
  --schema '{"type":"object","required":["domain"],"properties":{"domain":{"type":"string"}}}'
urirun host data record-upsert domains ifuri.com --data '{"domain":"ifuri.com"}'
urirun host data records --query ifuri
```

Generate data URI bindings when the same store should be called through
`urirun run`:

```bash
urirun host data bindings \
  --out .urirun/data.bindings.v2.json \
  --registry-out .urirun/data.registry.json

urirun run 'data://host/records/query/search' .urirun/data.registry.json \
  --payload '{"query":"ifuri"}'
```

Domain monitoring builds on that store:

```bash
urirun host monitor domain ifuri.com \
  --url https://ifuri.com \
  --expected-a 217.160.250.222 \
  --execute

urirun host monitor bindings \
  --project . \
  --out .urirun/monitor.bindings.v2.json \
  --registry-out .urirun/monitor.registry.json

urirun run 'flow://host/domain/command/check' .urirun/monitor.registry.json \
  --payload '{"domain":"ifuri.com","url":"https://ifuri.com","expected_a":["217.160.250.222"],"project":"."}' \
  --execute
```

HTTP/DNS failures are recorded as checks and logs. DNS mismatch creates a review
ticket; it does not apply DNS changes.

Namecheap DNS apply is available as an explicit reviewed flow. The adapter can
read `NAMECHEAP_API_USER`, `NAMECHEAP_API_KEY`, `NAMECHEAP_USERNAME`,
`NAMECHEAP_CLIENT_IP` and optional `NAMECHEAP_SANDBOX=true` from the
environment.

```bash
# generate a diff; no write
urirun run 'dns://host/records/command/plan' .urirun/monitor.registry.json \
  --payload '{"provider":"namecheap","domain":"example.com","ensure_records":[{"Name":"www","Type":"CNAME","Address":"example.com"}]}'

# create a backup artifact of the current Namecheap host records
urirun run 'dns://host/records/command/backup' .urirun/monitor.registry.json \
  --payload '{"provider":"namecheap","domain":"example.com"}' \
  --execute

# apply only with a reviewed full desiredRecords set, backup_uri and confirm=true
urirun run 'dns://host/records/command/apply' .urirun/monitor.registry.json \
  --payload '{"provider":"namecheap","domain":"example.com","plan":{"desiredRecords":[{"Name":"www","Type":"CNAME","Address":"example.com"}]},"backup_uri":"artifact://host/namecheap/dns-backup/example.com/REVIEWED","confirm":true}' \
  --execute
```

To use planfile through the regular URI runtime, generate task bindings:

```bash
urirun host task bindings \
  --project . \
  --out .urirun/planfile.bindings.v2.json \
  --registry-out .urirun/planfile.registry.json

urirun run 'task://host/ticket/command/create' .urirun/planfile.registry.json \
  --payload '{"name":"Daily domain check","prompt":"sprawdz domeny","queue":"daily"}' \
  --execute

urirun run 'task://host/tickets/query/list' .urirun/planfile.registry.json \
  --payload '{"queue":"daily"}'
```

The implementation plan lives in
`docs/PLANFILE_HOST_INTEGRATION_PLAN.md`.

## Standards used

- JSON Schema Draft 2020-12 for input validation.
- Pydantic v2 for Python authoring and schema generation.
- OCI image labels/annotations for discoverable image metadata.
- Existing package metadata: `package.json`, `pyproject.toml`, Makefile targets.
