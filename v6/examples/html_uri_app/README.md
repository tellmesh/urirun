# HTML URI app (v6)

The same static HTML + JS app as `v5/examples/html_uri_app`, rebuilt on the v6
runtime so you can compare the two side by side in practice.

Same idea: buttons and links carry **URI addresses**, not handlers. One
delegated click handler dispatches the URI. What changes in v6 is everything
around the dispatch:

- a **policy gate** decides whether a URI may run,
- a **dry-run / execute** switch (dry-run is the default and never touches
  application state),
- the UI (the whole action list) is **generated from `listRoutes()`** instead of
  being hand-written in `index.html`,
- every call returns the same **result envelope** `{ uri, mode, decision, ok,
  result | error }`.

## What this demonstrates

Open the app and toggle **Execute**:

| URI | dry-run | execute (with `policy.json`) |
|-----|---------|------------------------------|
| `device://device-01/led/set/on` | simulated, LED stays `off` | **allow** → LED really turns `on` |
| `service://api/user/create/basic` | simulated | **allow** → user added to state |
| `service://api/user/delete/basic` | simulated | **confirm** → blocked until "Confirm destructive" is on |
| `shell://local/system/restart/nginx` | simulated | **deny** → blocked (`shell://**` denied + shell templates off) |
| `workflow://office/supplier-report/monthly` | simulated chain | each step runs through the same gate |

Type a glob into the allow box (e.g. `shell://**`) and press **Add allow** to
watch the decisions re-render live. Press **Reset policy** to restore
`policy.json`.

## v5 vs v6, in practice

| | v5 app | v6 app |
|---|--------|--------|
| Action buttons | hand-written in `index.html` (9 `<a>`/`<button>` blocks) | generated from `listRoutes()`; `index.html` has one empty `<nav>` |
| Safety | none — every click runs the adapter | default-deny in execute mode; `policy.json` allow/deny globs |
| Accidental execution | nothing stops it | dry-run is the default; nothing runs until you opt in |
| Destructive actions | same as any other | `requireConfirm` gate (`delete` route) |
| What you see after a click | ad-hoc `{ uri, result }` | uniform envelope with the policy `decision` attached |
| Adding a new action | edit `bindings.json` **and** add markup | edit `bindings.json` only (label/payload live in `meta`) |

The net effect: v6 needs **fewer hand-written declarations** (no per-button
markup) while adding the safety layer the v5 app lacks. The contract
(`bindings.json`) is still the single source of truth — now the UI *and* the
guard rails are derived from it.

## Run

```bash
bash v6/examples/html_uri_app/run.sh
# open http://127.0.0.1:41739/
```

Host and port come from `.env`:

```env
HTML_URI_APP_HOST=127.0.0.1
HTML_URI_APP_PORT=41739
```

## Test

```bash
node v6/examples/html_uri_app/test.mjs
```

## Files

- `bindings.json` - URI to adapter map (with `meta.label` / `meta.payload` for the generated UI)
- `policy.json` - the v6 addition: allow/deny globs + shell/confirm rules
- `uri-runtime-v6.js` - browser-safe v6 runtime (policy gate + envelope), mirrors `urihandler/v6.py`
- `app.js` - mode-aware demo adapters and the generated UI wiring
- `index.html` - controls + an empty action list filled at runtime
