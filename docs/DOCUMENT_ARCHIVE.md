# Document Archive

<!-- docs-nav -->
📖 **Dokumentacja urirun:** [← README](../README.md) · [Architektura](ARCHITECTURE.md) · [Komponenty](COMPONENTS.md) · [URI Objects](URI_OBJECTS.md) · [Łączenie node](NODE_CONNECTIONS.md) · [Dashboard & chat](HOST_DASHBOARD_CHAT.md) · [Host↔Node](HOST_NODE_COMMUNICATION.md) · [Sekrety](SECRETS.md) · **Archiwum dok.** · [Decision Loop](DECISION_LOOP.md) · [Roadmap](REFACTOR_ROADMAP.md) · [Podział paczek](URIRUN_PACKAGE_SPLIT_PLAN.md) · [Planfile](PLANFILE_HOST_INTEGRATION_PLAN.md)
<!-- /docs-nav -->

The host dashboard phone scanner writes scanned receipts and invoices into a
document archive. By default the archive root is:

```bash
~/.urirun/documents
```

The root can be changed with:

```bash
export URIRUN_DOCUMENT_DIR=~/.urirun/documents
export URIRUN_DOCUMENT_INDEX=~/.urirun/documents/index.json
export URIRUN_SCANNED_ID_LOG=~/.urirun/documents/scanned.id.jsonl
```

## Capture pipeline

A single phone capture (`scanner://host/capture/command/run`) runs end to end:

1. **Stage** — the raw frame is written to `URIRUN_SCANNER_DIR`
   (`~/.urirun/host-dashboard/scans` by default) as `…-phone-scan-<sha>.jpg`.
2. **Crop** — `smartcrop://host/document/query/crop` crops to the document. It
   prefers a Tesseract **text-boundary** crop (the union of detected word boxes,
   expanded to the background-contrast paper edge) and falls back to a geometric
   cascade (OpenCV perspective, bright-sheet fill-ratio, connected components)
   when no text is found. The crop is saved as `…-receipt-crop.jpg`.
3. **OCR** — the crop is read by the local OCR engine (Tesseract).
4. **Quality gate** — a low-confidence frame (blurry, partial, non-document) is
   **rejected** rather than archived (see below).
5. **Identify** — `docid://` extracts a transaction fingerprint + perceptual
   hashes and assigns a `docId`.
6. **Deduplicate / supersede** — the scan is matched against the archive; a
   genuine new document is archived as a PDF, a re-scan is dropped or fuses into
   the existing record (see *Identity & Deduplication*).
7. **Feedback** — the scanner UI plays a short tone (and vibrates) so the user
   knows the result without looking: distinct cues for *saved*, *already saved*
   (duplicate), *updated* (superseded) and *error / discarded*.

## Quality gate

Single captures are gated so mis-scans never reach the archive or the UI. A frame
is archived only when it is document-like and scores at least
`URIRUN_PHONE_SCANNER_MIN_SCORE` (default `45`), matching the best-frame path:

```bash
export URIRUN_PHONE_SCANNER_MIN_SCORE=45
```

A rejected capture returns `{"ok": true, "rejected": true, "reason": "low-quality scan"}`,
its staged scan + crop files are deleted, and no document/artifact/chat message is
created. Pass `"force": true` in the capture payload to archive regardless of score.

## Staging retention

The best-frame scanner stages several candidate frames per capture and archives
only the chosen one, so `URIRUN_SCANNER_DIR` (`~/.urirun/host-dashboard/scans`)
would grow without bound. A throttled prune runs on each capture and removes
orphaned frames, but **never** deletes:

- files of an archived document (referenced by the index),
- files of an active, not-yet-finished best series,
- any file newer than `URIRUN_SCANNER_KEEP_RECENT` seconds (default `90`).

The recent-file window is deliberate: while scanning, a frame may still be needed
if image manipulation/capture errors and the user retries within the minute.

```bash
export URIRUN_SCANNER_KEEP_RECENT=90   # seconds; 0 disables pruning
```

## Files

Final documents are stored by month:

```text
~/.urirun/documents/
  2026-03/
    paragon_2026-03-15_allegro-sp-z-o-o_123.45-pln_doc-par-c6704d4790bb9cc4.pdf
    paragon_2026-03-15_allegro-sp-z-o-o_123.45-pln_doc-par-c6704d4790bb9cc4.json
  index.json
  scanned.id.jsonl
```

The `docId` suffix is intentional. It makes the file traceable even if it is
moved outside the archive or the dashboard database is rebuilt.

## `index.json`

`index.json` is the mutable catalog used by dashboard views and APIs. It stores
the latest known state for each document:

- `docId`
- `uri`
- `pdfPath`
- `jsonPath`
- source/crop paths
- OCR backend and character count
- content hashes (`sourceSha256`, `textSha256`)
- identity signals: `fingerprint` (transaction tokens), `dhash`, `phash`
- `supersededOf` when this record replaced an earlier, less-complete scan
- extracted type, date, contractor, amount and currency

This file is optimized for reading the current document list.

## `scanned.id.jsonl`

`scanned.id.jsonl` is the append-only identity ledger. It records one JSON object
per line. Events include:

- `scan` for a newly archived document
- `duplicate` for a re-scan dropped as already archived
- `superseded` for a re-scan that replaced a less-complete existing document
- `indexed` for documents backfilled from an existing `index.json`

Duplicate entries carry the `matchReason` and the `removedScanFiles` that were
cleaned from the staging dir.

Because it is append-only, it keeps duplicate history even if a PDF is renamed,
moved, deleted, or a dashboard catalog entry is later edited.

## Identity & Deduplication

Identity and dedup live in the `docid://` connector (`urirun-connector-docid`).
The same physical receipt photographed several times yields a different image and
drifting OCR (`amount → nieznana`, merchant misread), so exact fingerprints alone
treat every scan as new. A scan is considered the **same document** when any of
these hold:

- exact `docId`, source-image SHA-256, or normalized-OCR-text SHA-256, or
- **transaction fingerprint** — at least two distinctive, OCR-stable tokens agree
  (receipt/invoice number, authorization code, transaction time, card suffix).
  Terminal-constant tokens (POS ID / MID / AID) are ignored, since they are the
  same for every transaction at a terminal, or
- **fingerprint + visual** — one token agrees and the difference hash (dHash) is
  near, or
- **visual-strong** — both perceptual channels agree (dHash *and* DCT pHash) even
  with no usable OCR token, for badly garbled re-scans.

On a match the more complete scan wins: if the new capture reads strictly more
metadata than the archived one it **supersedes** it (old PDF/JSON removed, index
entry replaced) and missing fields are fused from both scans; otherwise the new
capture is dropped as a `duplicate` and its staged files are cleaned. See
`docid://host/document/query/{identify,evaluate,reconcile}`.

## Why Two Files

Keep both files.

`scanned.id.jsonl` should be treated as the durable identity/audit record.
`index.json` should be treated as a materialized catalog for the UI and URI API.

Using only `index.json` would make duplicate detection depend on a mutable file
whose paths may be edited manually. Using only `scanned.id.jsonl` would be
possible, but the dashboard would need to rebuild a current-state catalog for
every listing or maintain a derived cache anyway.

The clean future model is:

```text
scanned.id.jsonl  -> source identity ledger
index.json        -> rebuildable materialized view
```

That keeps manual operations safe while avoiding unnecessary complexity in the
dashboard read path.

## Sync To A Node

Archived PDFs can be copied to a URI node through the host dashboard URI API:

```text
document://host/archive/command/sync-to-node
```

The host reads local files from `URIRUN_DOCUMENT_DIR` and writes them on the node
with:

```text
fs://host/file/command/write-b64
fs://host/file/query/read-b64
```

The node is selected by the `node_url` transport. The `fs://host/...` target is
intentional: it means "run the filesystem connector in that remote node
process". Do not rewrite it to `fs://<node>/...` unless the remote node has
explicitly exposed the connector under that target.

Before copying, the host preflights the exact remote routes. This is route-level,
not only scheme-level: `fs://host/duplicates/query/find` does not prove that
`fs://host/file/command/write-b64` is available. When the node misses the file
transfer route, the sync is blocked before per-file uploads and the result
contains:

```json
{
  "preflight": {
    "ok": false,
    "requiredRoutes": [
      "fs://host/file/command/write-b64",
      "fs://host/file/query/read-b64"
    ],
    "missingAfter": [
      "fs://host/file/command/write-b64"
    ]
  }
}
```

Set `ensure_routes: false` only for tests or for a deliberately unmanaged node.

If node-side `ensure` reports `no installed bindings or local source for scheme`,
the host attempts a narrow fallback deployment over `/deploy`: it pushes
`urirun_fs_file_transfer.py` and only the two required `fs://.../file/...`
bindings. The result appears under `preflight.hostFallback`. This avoids SSH and
does not require `pip install` on the node, but the node still needs deploy/admin
authorization.

Default target settings:

```bash
export URIRUN_DOCUMENT_SYNC_NODE=my-node
export URIRUN_DOCUMENT_SYNC_DEST='~/Downloads/urirun-scans'
```

`URIRUN_DOCUMENT_SYNC_NODE` is intentionally configuration, not code. The
dashboard does not hardcode local machine names. A natural-language prompt is
matched against selected node targets and configured node names/aliases from the
host config, `~/.urirun/nodes.json` (`URIRUN_NODES_FILE`), `URIRUN_NODES`,
`URIRUN_NODE_URL_*`, or `URIRUN_NODE_ALIASES`.

Example aliases:

```bash
printf '{"office-laptop":"http://192.168.1.20:8766"}\n' > ~/.urirun/nodes.json
export URIRUN_NODES='office-laptop=http://192.168.1.20:8766'
export URIRUN_NODE_ALIASES='office-laptop=notebook|work laptop'
```

Example payload:

```json
{
  "uri": "document://host/archive/command/sync-to-node",
  "payload": {
    "node_url": "http://192.168.188.201:8766",
    "node": "laptop",
    "dest_root": "~/Downloads/urirun-scans",
    "overwrite": true
  }
}
```

The sync is intentionally visible in two places:

- `logs` stream `document-sync`, event `sync-to-node`
- chat stream as a system message with copied/failed counts

Each copied file is verified by a realization contract. By default the host
writes the file, then reads it back from the node and compares SHA-256. The
summary fields mean:

- `total` — local PDFs selected from the archive
- `uploaded` — remote write commands that returned the expected SHA-256
- `copied` — files verified by the final read-back contract
- `failed` — `total - copied`
- `verification` — machine-readable contract result, currently
  `document-sync.v1`

Example successful contract:

```json
{
  "verification": {
    "contract": "document-sync.v1",
    "mode": "read-back-sha256",
    "expectedFiles": 11,
    "uploadedFiles": 11,
    "verifiedFiles": 11,
    "failedFiles": 0,
    "ok": true
  }
}
```

Set `verify: false` or `verify_read_back: false` in the payload only when the
caller intentionally accepts write-ack verification instead of read-back.
The destination layout mirrors the archive month folders:

```text
~/Downloads/urirun-scans/
  2026-06/
    rachunek_2026-06-19_duo-cafe-hanna-gruba_30.26-pln_doc-fv-877312030cff5231.pdf
```

If the sync was requested from chat and the selected node has no URL in the host
config, the dashboard asks `urifix://host/chain/command/repair` for recovery.
With a known transient node URL, `urifix://` returns a retry payload containing
`node_url`. Without one it returns a manual `provide-node-url` action. This keeps
the sync deterministic without letting the planner invent a node address.
