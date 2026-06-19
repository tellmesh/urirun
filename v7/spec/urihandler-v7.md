# urihandler v7

`urihandler v7` makes real tools easy to drive: ffmpeg, kubectl, git, docker.

v6 made routes executable behind a policy gate, but `spawn`/`shell-template`
could only receive **positional** arguments taken from URI path segments —
payload and query were dropped. Real command-line tools need *named* flags and
values, so v7 adds parameter binding, a string shorthand, Docker adapters, and
uniform process options. It runs on the same `urihandler.registry.v4` document
and the same v6 policy gate.

## Parameter binding

`{name}` placeholders are filled from four sources (later wins):

1. URI query string — `media://local/video/transcode?input=a.mp4`
2. payload object — `--payload '{"input":"a.mp4"}'`
3. positional args — `{0}`, `{1}` from trailing URI segments
4. the target — `{target}`

```json
"media://local/video/transcode": {
  "kind": "cli", "adapter": "spawn",
  "command": ["ffmpeg", "-i", "{input}", "-vf", "scale={width}:{height}", "{output}"],
  "params": { "input": {"required": true}, "output": {"required": true},
              "width": {"default": 1280}, "height": {"default": 720} }
}
```

```bash
urihandler run media://local/video/transcode bindings.json \
  --payload '{"input":"a.mp4","output":"b.mp4"}'
# dry-run result.command -> ["ffmpeg","-i","a.mp4","-vf","scale=1280:720","b.mp4"]
```

Each command element is rendered separately, so values keep the argv structure
(no shell splitting, no injection). `params` adds `default` and `required`; a
missing required param or an unresolved `{placeholder}` is a `params` error — and
because dry-run renders the same way, you catch it **before** executing.

Backward compatible: a command with no `{...}` keeps v6 behaviour and appends the
trailing URI segments as positional args.

## String shorthand

A binding can be just a command string:

```json
{ "bindings": {
  "cli://local/git/status": "git status",
  "media://local/audio/extract": "ffmpeg -i {input} -vn -acodec copy {output}"
}}
```

The compiler infers `kind: cli`, `adapter: spawn`, and tokenizes the command
(quotes respected). This is the tersest way to register a tool.

## Docker adapters

Docker becomes a first-class execution surface, not just a discovery source.

| adapter | builds | use |
|---------|--------|-----|
| `docker-exec` | `docker exec <target> <command>` | run inside a running container (target = container) |
| `docker-run`  | `docker run --rm [-v mount:/work -w /work] <image> <command>` | one-shot from an image (e.g. ffmpeg with no local install) |

```json
"container://api/db/backup": { "kind": "docker", "adapter": "docker-exec",
  "command": ["pg_dump", "-U", "{user}", "{database}"],
  "params": { "user": {"default": "postgres"}, "database": {"required": true} } }

"img://ffmpeg/video/thumbnail": { "kind": "docker", "adapter": "docker-run",
  "image": "jrottenberg/ffmpeg", "mount": ".",
  "command": ["-i", "{input}", "-ss", "{at}", "-vframes", "1", "{output}"] }
```

## Uniform process options

`env`, `stdin`, `cwd`, `timeout` work for `spawn`, `shell-template`,
`docker-exec` and `docker-run`. `env` values are templated too, so a shell script
can read named inputs without parsing arguments:

```json
"script://local/deploy/run": { "kind": "cli", "adapter": "spawn",
  "command": ["sh", "deploy.sh"], "cwd": ".",
  "env": { "RELEASE": "{release}", "TARGET": "{target}" },
  "params": { "release": {"required": true} } }
```

For `docker-exec`/`docker-run`, `env` is passed as `-e KEY=VALUE`.

## CLI

```bash
urihandler compile bindings.v7.json --out .urihandler/registry.merged.json
urihandler list ./project --allow 'media://**'
urihandler run media://local/video/transcode bindings.v7.json --payload '{"input":"a.mp4","output":"b.mp4"}'
urihandler run media://local/video/transcode bindings.v7.json --payload '{"input":"a.mp4","output":"b.mp4"}' --allow 'media://**' --execute
```

`compile` understands the string shorthand and the top-level process keys;
`scan`, `discover`, `build-registry` and `call` are delegated to v5/v4. Like v6,
the policy gate is default-deny in execute mode and dry-run is the default.
