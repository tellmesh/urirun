# urirun v8

`urirun v8` turns command endpoints into schema-first packages.

```txt
function signature -> Pydantic model -> JSON Schema -> URI binding -> shell/argv runtime
existing artifact -> scanner -> URI binding -> registry
```

## Contract

The portable contract is JSON:

```json
{
  "uri": "media://local/video/transcode",
  "kind": "command",
  "adapter": "argv-template",
  "inputSchema": { "type": "object" },
  "argv": ["ffmpeg", "-i", "{input}", "{output}"]
}
```

`inputSchema` is JSON Schema Draft 2020-12. The runtime validates the merged
input object, applies schema defaults, and then renders placeholders.

Parameter sources:

1. URI query string
2. payload object
3. URI target as `{target}`
4. trailing URI args as `{0}`, `{1}`, ...

The schema validates named payload/query fields. `{target}` and numeric
placeholders are runtime values and do not need to be listed in the schema.

## Adapters

| adapter | execution |
|---------|-----------|
| `argv-template` | renders `argv[]` and executes it with `subprocess.run(argv)` |
| `shell-template` | renders a shell string and executes it with `shell=True` |
| `docker-run` | inherited from v7, renders command inside `docker run` |
| `docker-exec` | inherited from v7, renders command inside `docker exec` |

Use `argv-template` by default. `shell-template` is intentionally policy-gated:
execution requires an allow rule plus `allowShellTemplates: true`.

## Decorators

```python
@uri_command("say://local/echo/message")
def echo(text: str):
    return ["python3", "-c", "import sys; print(sys.argv[1])", "{text}"]

@uri_shell("shell://local/echo/message")
def shell_echo(text: str):
    return "printf '%s\\n' '{text}'"
```

The function is not the runtime handler. It is the authoring surface: its
signature creates the schema and its return value creates the command template.
The compiled registry remains JSON.

## Artifact adoption

v8 can scan a project directory and adopt common declarations:

- Dockerfile labels, including `io.tellmesh.urirun.manifest`
- `package.json` scripts
- `pyproject.toml` `project.scripts`
- Makefile targets
- shell scripts
- explicit v8 manifests

For Docker images, the recommended declaration is:

```dockerfile
LABEL org.opencontainers.image.source="https://github.com/org/repo"
LABEL io.tellmesh.urirun.manifest="urirun.manifest.json"
```

The image/build artifact points to the URI manifest; the manifest describes the
actual URI contract.

## Generated Registry Lifecycle

The registry can be generated from artifacts instead of maintained by hand:

```bash
urirun scan ./project \
  --out generated/bindings.v8.json \
  --registry-out generated/registry.json

urirun validate generated/bindings.v8.json
urirun list generated/registry.json
```

This creates two different artifacts:

- `bindings.v8.json` - the schema-first package contract, suitable for review
  and reuse across languages.
- `registry.json` - the compiled route tree used by runtimes and dispatchers.

The scanner is allowed to emit bindings from multiple standards in the same
project. A single registry can therefore contain Docker image routes, package
scripts, shell scripts, Makefile targets, and explicit service manifests. The
compiled registry is still the only source used during dispatch; the generated
binding file is kept so the registry remains reproducible.

## CLI-generated bindings

v8 can append bindings without hand-editing JSON:

```bash
urirun add-pypi sampleproject --out urirun.bindings.v8.json

urirun add-command 'util://local/echo/message' \
  --argv 'python3 -c "import sys; print(sys.argv[1])" {text}' \
  --param text:string:required \
  --out urirun.bindings.v8.json
```

`--param` accepts compact field declarations:

```txt
name
name:string:required
width:integer=1280
enabled:boolean=true
```

The command updates or creates a standard v8 bindings document, so the next
step is still the normal compile/run flow.

## Adopting installed package commands

Decorators cover code you own. `urirun.v8_adopt` covers code you *install* -
the CLI commands PyPI and npm packages ship - by reading their declared entry
points and emitting passthrough bindings (a fixed command prefix plus a
`{...args}` array, schema-described):

```bash
# expose a PyPI package's console_scripts as URIs
python -m urirun.v8_adopt add-python-package black --out urirun.bindings.v8.json
#   -> cli://black/black/run   argv: ["black", "{...args}"]

# expose an installed npm package's bin commands
python -m urirun.v8_adopt add-npm-package prettier --out urirun.bindings.v8.json
#   -> cli://prettier/prettier/run   argv: ["npx", "--no-install", "prettier", "{...args}"]

# one-command project onboarding: scan + write bindings + registry
python -m urirun.v8_adopt init . --out urirun.bindings.v8.json --registry-out .urirun/registry.merged.json
```

Then call it like any other URI, passing arbitrary arguments through the array:

```bash
urirun run 'cli://black/black/run' --payload '{"args":["--check","src/"]}'
```

The `{...name}` spread placeholder expands an array param in place inside an
`argv-template`; it is what makes passthrough adoption possible while keeping the
argv structure (no shell, no injection).

## Language generators

The examples under `v8/examples/generators` show native declaration styles:

- JavaScript helper functions,
- Node.js generator scripts,
- TypeScript decorator-style declarations,
- PHP attributes and reflection.

These are authoring conveniences only. Each generator emits the same
`urirun.bindings.v8` JSON document.

## Interop: MCP and A2A (agent discovery)

Because a v8 binding already carries a JSON Schema (`inputSchema`), the registry
projects cleanly to the two formats agents use to discover and call tools:

```txt
urirun registry        ->  MCP tools/list   (LLM tool calling)
                       ->  A2A agent card    (agent-to-agent discovery)
                       ->  tools/call        ->  v8 policy gate -> run
```

`urirun.v8_mcp` provides the projection and a minimal MCP server:

```bash
python -m urirun.v8_mcp tools bindings.v8.example.json     # MCP tool manifest
python -m urirun.v8_mcp card  bindings.v8.example.json     # A2A agent card
python -m urirun.v8_mcp serve registry.json               # MCP stdio server (dry-run)
python -m urirun.v8_mcp serve registry.json --execute --policy policy.json
```

An LLM (via MCP) or another agent (via the A2A card) **discovers** the endpoints
and **calls** them by tool name; every `tools/call` goes through the same
same policy gate, so discovery never implies permission to execute. The
`html_uri_app` backend exposes the same over HTTP: `GET /api/mcp/tools`,
`GET /api/a2a/card`, `POST /api/mcp/call`.

MCP and A2A are complementary: MCP standardises *LLM -> tool* calls (one tool
per URI, schema-validated arguments); A2A standardises *agent -> agent*
discovery (the card advertises skills at a URL). urirun keeps one registry
as the source of truth and projects to both, so the contract and the safety gate
stay in one place.

## Docker Service Flows

In a Docker Compose network, the URI target can be the service DNS name:

```yaml
steps:
  - id: normalize_text
    uri: python://python-worker/text/normalize
    payload:
      text: "Supplier Report June 2026"

  - id: slugify_text
    uri: node://node-worker/text/slugify
    depends_on:
      - normalize_text
    payload:
      text_from: normalize_text.result.normalized
```

The orchestrator maps `python://python-worker/...` to
`http://python-worker:8080/run`. Every service exposes its own `/routes`
manifest and `/run` endpoint. The flow sees URI resources only; the backing
implementation can be Python, Node.js, a shell script, a PyPI package entry
point, an npm script, or another Docker image.

The registry can be generated from supplied artifacts before the flow starts:

```bash
urirun scan . --out generated/bindings.v8.json --registry-out generated/registry.json
urirun validate generated/bindings.v8.json
urirun list generated/registry.json
```

For Dockerfiles, an image-level label such as
`io.tellmesh.urirun.manifest=/app/bindings.json` points the scanner to the
service URI contract. If the label points to a container path, the scanner also
checks the Dockerfile directory for a file with the same basename.

A Docker flow should validate its flow document against the generated registry
before making network calls. The recommended runtime sequence is:

1. scan artifacts into `generated/bindings.v8.json`;
2. compile `generated/registry.json`;
3. validate every `steps[].uri` from the flow against the registry;
4. dispatch each URI through the transport adapter selected by its target.
