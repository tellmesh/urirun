# urirun v2

v2 is schema-first command packaging.

It replaces custom `params.required/default` declarations with standard JSON
Schema and adds Python decorators that generate that schema from function
signatures.

## Decorator

```python
from urirun.v2 import uri_command, uri_shell

@uri_command("media://local/video/transcode")
def transcode(input: str, output: str, width: int = 1280, height: int = 720):
    return ["ffmpeg", "-i", "{input}", "-vf", "scale={width}:{height}", "{output}"]

@uri_shell("shell://local/echo/message")
def echo(text: str):
    return "printf '%s\\n' '{text}'"
```

The decorator creates an `inputSchema` from Pydantic and stores the argv or shell
template as a normal v2 binding. The runtime validates payload/query values
against that schema, applies defaults, renders placeholders, and then runs the
command.

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

## Standards used

- JSON Schema Draft 2020-12 for input validation.
- Pydantic v2 for Python authoring and schema generation.
- OCI image labels/annotations for discoverable image metadata.
- Existing package metadata: `package.json`, `pyproject.toml`, Makefile targets.
