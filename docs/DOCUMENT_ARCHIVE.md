# Document Archive

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
- content hashes
- extracted type, date, contractor, amount and currency

This file is optimized for reading the current document list.

## `scanned.id.jsonl`

`scanned.id.jsonl` is the append-only identity ledger. It records one JSON object
per line. Events include:

- `scan` for a newly archived document
- `duplicate` for a rejected duplicate scan
- `indexed` for documents backfilled from an existing `index.json`

The ledger is used to detect duplicates by:

- `docId`
- source image SHA-256
- normalized OCR text SHA-256

Because it is append-only, it keeps duplicate history even if a PDF is renamed,
moved, deleted, or a dashboard catalog entry is later edited.

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
