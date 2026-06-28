# URI Objects: Connectors, Services, Widgets and Artifacts

<!-- docs-nav -->
📖 **Dokumentacja urirun:** [← README](../README.md) · [Architektura](ARCHITECTURE.md) · [Komponenty](COMPONENTS.md) · **URI Objects** · [Łączenie node](NODE_CONNECTIONS.md) · [Dashboard & chat](HOST_DASHBOARD_CHAT.md) · [Host↔Node](HOST_NODE_COMMUNICATION.md) · [Sekrety](SECRETS.md) · [Archiwum dok.](DOCUMENT_ARCHIVE.md) · [Decision Loop](DECISION_LOOP.md) · [Roadmap](REFACTOR_ROADMAP.md) · [Podział paczek](URIRUN_PACKAGE_SPLIT_PLAN.md) · [Planfile](PLANFILE_HOST_INTEGRATION_PLAN.md)
<!-- /docs-nav -->

This is the working contract for object boundaries in urirun. It exists to keep
new `urirun-connector-*` and `urirun-service-*` packages small and predictable.

For the current end-to-end architecture, see `docs/ARCHITECTURE.md`. For a
Polish operator/developer overview of the same component model, see
`docs/COMPONENTS.md`.

## Object Types

## Runtime URI Object Envelope

Runtime objects are the controllable surfaces that own a group of URI routes.
The host dashboard currently emits them in `summary.objects` and through
`GET /api/objects` for:

- `host`
- `node:*`
- `service:*`

Node subtype metadata is emitted separately from object `kind`. A runtime object
for a laptop still has `kind: "node"`, while `type` / `nodeType` can be `pc`,
`server`, `rdp`, `smartphone`, `browser-debug`, `browser-chrome-plugin`,
`browser-firefox-plugin`, `webpage`, `api` or `device`. The canonical list is exposed
by `GET /api/node-types` and `GET /api/summary -> nodeTypes`.

Compatibility aliases remain accepted: `browser` normalizes to `browser-debug`,
and `web` / `webnode` normalize to `webpage`.

Shape:

```json
{
  "id": "node:lenovo",
  "kind": "node",
  "label": "urirun node: lenovo",
  "status": "up",
  "reachable": true,
  "url": "http://192.168.188.201:8765",
  "type": "pc",
  "nodeType": "pc",
  "integrationLevel": "desktop",
  "transport": "http",
  "runtime": "urirun-node",
  "apis": [],
  "capabilities": [],
  "routes": [
    {
      "uri": "env://lenovo/runtime/query/health",
      "kind": "query",
      "adapter": "remote-node",
      "target": "lenovo",
      "ownerId": "node:lenovo",
      "ownerKind": "node"
    }
  ]
}
```

For `api` and `device` nodes, `apis[]` describes one or more configured
interfaces. These nodes may be external and may not expose native urirun
`/health` or `/routes`; discovery can still expose configured routes such as
`api://.../command/request`, `media://.../query/stream`, `camera://.../query/snapshot`,
`ssh://.../command/run` and `fs://.../query/list`.

Only HTTP-like configured interfaces are directly executable by the host:

```text
configured://host/node-api/command/request
configured://host/node-api/query/status
api://<node>/<api>/command/request
device://<node>/<api>/command/request
```

The host resolves the node config, loads auth from `secretRef` via keyring, sends
the HTTP request, and returns the response as portable JSON. Non-HTTP protocols
advertised by a device node, such as RTSP, SMB/NFS, SSH or camera snapshot
routes, intentionally return `connector_required` unless a dedicated connector
or service owns that scheme. This keeps discovery useful without turning route
metadata into fake execution.

Artifacts and widgets are related but not the same thing. A widget is a live
view owned by a host/service/node object. An artifact is a finished result owned
by the artifact registry. They may be shown under an object, but they should not
replace the object model.

### Connector

A connector is a URI capability provider. It declares routes, input schemas and
handler code for one domain, for example `ocr://`, `smartcrop://`, `fs://`,
`invoice://` or `artifact://`.

A connector should:

- expose URI routes through `urirun.bindings`,
- execute one bounded domain operation,
- return portable JSON,
- return artifact descriptors for files it produced,
- avoid owning dashboard UI state.

A connector may write a file when the route's job is to produce a file. It should
not invent its own dashboard artifact registry when the host already exposes
`artifact://host/artifact/command/register`.

### Service

A service is a long-running runtime with its own lifecycle and usually its own
HTTP surface. Examples are `urirun-service-chat` and
`urirun-service-scanner`.

A service should:

- own process lifecycle, port binding and restart behavior,
- expose service control routes such as `service://.../command/restart`,
- expose live state for the dashboard,
- register final artifacts through the host artifact store,
- render or proxy widgets when it owns the live runtime.

### Artifact

An artifact is a finished, immutable result: PDF, image, JSON report, text file,
CSV export, screenshot, QR code or captured scan. It has `live: false` even when
it was created from a live stream.

Canonical storage is the host artifact registry:

```text
artifact://host/artifact/command/register
artifact://host/artifacts/query/list
```

The current implementation is backed by `urirun.host.host_db` and exposed by
`urirun-connector-sqlite-context`.

Recommended descriptor shape:

```json
{
  "kind": "document-pdf",
  "uri": "document://host/DOC-PAR-123",
  "path": "/home/tom/.urirun/documents/2026-06/example.pdf",
  "mime": "application/pdf",
  "live": false,
  "meta": {
    "sourceCaptureUri": "scanner://host/capture/abc",
    "displayImage": "/home/tom/.urirun/host-dashboard/scans/example-crop.jpg"
  }
}
```

If a connector returns this descriptor, the host or service can register it. The
connector does not need to know how the dashboard stores, deduplicates or renders
artifacts.

### Widget

A widget is a live view. It is not a file and should not be listed as an artifact.
Examples are scanner live preview, service status, a node health panel, a table
that refreshes from an API, or a stream of OCR frames.

Recommended descriptor shape:

```json
{
  "kind": "scanner-stream",
  "target": "service:phone-scanner",
  "view": "scanner-stream",
  "live": true,
  "refreshMs": 1000,
  "dataUri": "dashboard://host/services/query/live",
  "supportedViews": ["cards", "table"]
}
```

The deciding line is not media type. A recorded video file is an artifact. A live
camera preview is a widget.

## Should Connectors Use Artifacts?

Yes, but only at the descriptor level by default.

Good connector behavior:

```json
{
  "ok": true,
  "connector": "ocr",
  "text": "Invoice ...",
  "artifact": {
    "kind": "ocr-json",
    "path": "/tmp/ocr-result.json",
    "live": false
  }
}
```

Good service/host behavior:

1. receive connector output,
2. validate the artifact descriptor,
3. register it with `artifact://host/artifact/command/register`,
4. show it in chat and the artifact grid.

Avoid this in connectors:

- separate SQLite ledgers that duplicate `host_db`,
- dashboard-specific fields as required outputs,
- long-running polling loops,
- widget rendering,
- hidden side effects that register several records for the same physical file.

## Scanner Boundary

The scanner flow uses all four object types:

- `urirun-service-scanner`: owns the phone scanner runtime and `/scanner` page.
- `urirun-service-chat`: owns the operator dashboard and chat.
- `urirun-connector-smart-crop`, `urirun-connector-ocr`, `urirun-connector-docid`:
  provide bounded document processing capabilities.
- `document-pdf`, `crop-overlay`, `dashboard-qr`: artifacts.
- `scanner-stream` and `scanner-status`: widgets.

The final PDF should be registered once as `document-pdf`. Intermediate frames
can be shown as live widget state or chat attachments, but they should not create
extra artifact rows that point to the same final PDF.

## Current Gaps

- `urirun.host.host_dashboard` still owns too many concerns: chat UI, scanner
  API, artifact API, fallback HTML/CSS and some document archive logic. Artifact
  and chat-message rendering now have a reusable browser path through
  `urirun-widgets` (`renderDashboardWidget`), but the inline fallback and shared
  styles are still duplicated in the host dashboard.
- `urirun-connector-camera` has local artifact persistence logic. It should move
  toward returning descriptors and letting the host/service register final
  artifacts.
- `domain_monitor` and provider connectors can produce files. They should return
  artifact descriptors consistently instead of each inventing artifact metadata.
- Artifact list deduplication exists in the dashboard, but the better model is to
  avoid duplicate records at write time when the same path and semantic artifact
  are already known.

## Migration Plan

1. Keep `host_db.register_artifact` as the implementation source of truth.
2. Treat `urirun-connector-sqlite-context` as the canonical URI surface for
   data, logs, checks and artifacts.
3. Update services to register final files through the artifact route or the same
   host DB facade.
4. Update connectors to return artifact descriptors and remove local dashboard
   registry logic.
5. Keep widgets service-owned. A widget can link to artifacts, but it should not
   be an artifact.
6. Move scanner-specific live state out of `host_dashboard` into
   `urirun-service-scanner` once the service boundary is fully stable.

## Naming

Use these names consistently:

- `URI Node`: a controllable machine/runtime such as the Lenovo laptop.
- `URI Service`: a long-running app exposed and controlled through URI.
- `Connector`: a packaged URI capability provider.
- `Artifact`: a static output.
- `Widget`: a live view/control surface.
- `Runtime`: the execution boundary for routes, processes and transports.
