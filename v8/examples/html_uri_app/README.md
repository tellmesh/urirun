# HTML URI app v8

Schema-first HTML app for `urirun.v8`.

The frontend renders routes and input forms from `bindings.json`. The backend
uses the Python v8 runtime, so the same URI contract drives dry-runs, real argv
execution, and policy-gated shell execution.

## Run

```bash
bash v8/examples/html_uri_app/run.sh
```

Open:

```txt
http://127.0.0.1:41880/
```

Real execution is disabled by default. Copy `.env.example` to `.env` and set:

```env
HTML_URI_APP_ALLOW_EXECUTE=true
HTML_URI_APP_ALLOW_SHELL=true
```

Shell routes still require the in-app `Shell` toggle.
