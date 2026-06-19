# urihandler v8

v8 is schema-first command packaging.

It replaces custom `params.required/default` declarations with standard JSON
Schema and adds Python decorators that generate that schema from function
signatures.

## Decorator

```python
from urihandler.v8 import uri_command, uri_shell

@uri_command("media://local/video/transcode")
def transcode(input: str, output: str, width: int = 1280, height: int = 720):
    return ["ffmpeg", "-i", "{input}", "-vf", "scale={width}:{height}", "{output}"]

@uri_shell("shell://local/echo/message")
def echo(text: str):
    return "printf '%s\\n' '{text}'"
```

The decorator creates an `inputSchema` from Pydantic and stores the argv or shell
template as a normal v8 binding. The runtime validates payload/query values
against that schema, applies defaults, renders placeholders, and then runs the
command.

Shell routes are real shell execution, but they stay behind the v6 policy gate:
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

`urihandler.v8 scan ./project` adopts common package standards:

- Dockerfile with `io.tellmesh.urihandler.manifest=...`
- OCI-compatible labels such as `org.opencontainers.image.source`
- `package.json` scripts
- `pyproject.toml` `[project.scripts]`
- `Makefile` targets
- `*.sh` scripts
- explicit `urihandler.manifest.json` / `bindings.v8.json`

This makes existing repositories behave like URI packages without manually
writing every endpoint.

## HTML app

```bash
bash v8/examples/html_uri_app/run.sh
```

The app renders routes and forms from `bindings.json`, then calls the Python v8
runtime through `POST /api/run`.

Execution is disabled by default. Use `v8/examples/html_uri_app/.env.example`
as the local `.env` template when you want to enable real argv or shell
execution.

## Docker URI flow

`v8/examples/docker_uri_flow` demonstrates multiple Docker services
communicating through URI-addressed resources:

- `python://python-worker/text/normalize`
- `node://node-worker/text/slugify`
- `shell://shell-worker/report/write`
- `python://python-worker/report/summary`

Run it with:

```bash
bash v8/examples/docker_uri_flow/run.sh
```

Generate only the registry from supplied Docker/package/script artifacts:

```bash
cd v8/examples/docker_uri_flow
make registry
```

The orchestrator reads a compact YAML flow similar to
`uri2flow/examples/33_office_workflows`, resolves `_from` references between
steps, validates every referenced URI against `generated/registry.json`, and
dispatches each URI to the service named by the URI target.

## Generators from other languages

`v8/examples/generators` contains small generators for:

- plain JavaScript,
- Node.js scripts,
- TypeScript decorator-style declarations,
- PHP 8 attributes.

All of them produce the same v8 JSON contract. The runtime consumes the JSON,
not the source language.

## One-line binding generation

Append a PyPI install binding to a v8 binding document:

```bash
PYTHONPATH=adapters/python python -m urihandler.v8 add-pypi urihandler \
  --out urihandler.bindings.v8.json
```

Append a generic command binding:

```bash
PYTHONPATH=adapters/python python -m urihandler.v8 add-command 'util://local/echo/message' \
  --argv 'python3 -c "import sys; print(sys.argv[1])" {text}' \
  --param text:string:required \
  --out urihandler.bindings.v8.json
```

## CLI

```bash
PYTHONPATH=adapters/python python -m urihandler.v8 scan v8/examples/artifacts --out /tmp/v8.bindings.json
PYTHONPATH=adapters/python python -m urihandler.v8 validate /tmp/v8.bindings.json
PYTHONPATH=adapters/python python -m urihandler.v8 compile /tmp/v8.bindings.json --out /tmp/v8.registry.json
PYTHONPATH=adapters/python python -m urihandler.v8 run tool://local/report/render --registry /tmp/v8.registry.json --payload '{"name":"Ada"}'
```

## Standards used

- JSON Schema Draft 2020-12 for input validation.
- Pydantic v2 for Python authoring and schema generation.
- OCI image labels/annotations for discoverable image metadata.
- Existing package metadata: `package.json`, `pyproject.toml`, Makefile targets.
