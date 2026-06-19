# HTML URI app (v7)

This console demonstrates the v7 runtime. The key idea is **named parameter
binding**: a URI is a small template. The UI gives every endpoint a **form** and
shows the exact command it will run — live, as you type — before anything
executes.

## What v7 adds to the console

- **Per-endpoint parameter inputs**, generated from the binding's `params` spec
  (with `required` and `default`).
- **Live command preview** (`runtime.preview`) that re-renders on every keystroke
  and flags missing required params *before* you run.
- **Real tools as templates**: `ffmpeg` (spawn), `docker run` / `docker exec`
  (Docker adapters), a GitHub **HTTP GET** that actually fetches, and a string
  shorthand binding (`"cli://local/git/status": "git status"`).
- The safety layer is dry-run by default, default-deny in execute,
  `shell://` denied, `--allow` editable live, destructive confirm.

Open the app, pick **Transcode video (ffmpeg)**, type `input` and `output`, and
watch the preview become `ffmpeg -i a.mp4 -vf scale=1280:720 b.mp4`. Toggle
**Execute** to see the policy decision per endpoint; `shell://` stays denied.

> The browser cannot spawn ffmpeg/docker, so those runs are simulated but show
> the exact command — the same command the `urirun.v7` CLI runs for real.
> The GitHub GET endpoint performs a real request.

## Run

```bash
bash v7/examples/html_uri_app/run.sh
# open http://127.0.0.1:41740/
```

## Test

```bash
node v7/examples/html_uri_app/test.mjs
```

## Files

- `bindings.json` - endpoints with `params` specs (+ string shorthand) and `meta.label`
- `policy.json` - allow/deny globs (shell denied)
- `uri-runtime-v7.js` - browser-safe v7 runtime (param binding + policy + preview), mirrors `urirun/v7.py`
- `app.js` - the form UI, live preview, and demo adapters
- `index.html` - controls + endpoint list + detail form
