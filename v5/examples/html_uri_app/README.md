# HTML URI app

Static HTML + JS example that uses v5 URI bindings as the application contract.

The app does not create one JavaScript handler per button. Buttons and links only carry URI addresses:

```html
<a href="#device://device-01/led/set/on">LED on</a>
<button data-uri="service://api/user/create/basic">Create user</button>
```

One delegated click handler calls:

```js
runtime.dispatch(uri, payload)
```

The runtime resolves the URI through `bindings.json`, picks the adapter and executes a local demo adapter.

The visible action list is generated from `runtime.listRoutes()`. To add another UI action, add a binding and optional `meta.label`, `meta.payload`, or `meta.uri` in `bindings.json`; no extra HTML button is needed.

The Python backend serves the static files and handles backend-addressed URI calls:

- `POST /api/dispatch` - execute a URI from the frontend
- `POST /api/logs/write` - append a backend log entry
- `GET /api/logs/recent` - read backend logs
- `POST /api/users` - simulated service endpoint

Shell commands are simulated by default. Set `HTML_URI_APP_ALLOW_SHELL=true` only in a safe local environment if you want the backend to execute the rendered shell command.

## Run

```bash
bash v5/examples/html_uri_app/run.sh
```

Open:

```txt
http://127.0.0.1:41810/
```

Port and host are loaded from `.env`:

```env
HTML_URI_APP_HOST=127.0.0.1
HTML_URI_APP_PORT=41810
HTML_URI_APP_ALLOW_SHELL=false
```

If the configured port is busy, the backend automatically tries the next free port and prints the actual URL.

## Test

```bash
node v5/examples/html_uri_app/test.mjs
```

## Files

- `bindings.json` - URI to adapter map
- `uri-runtime.js` - small browser-safe dispatcher with `listRoutes()` and `dispatchEnvelope()`
- `app.js` - demo adapters, generated UI wiring, and backend log refresh
- `index.html` - static shell with an empty action list generated from bindings
