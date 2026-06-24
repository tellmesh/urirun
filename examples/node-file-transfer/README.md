# Node File Transfer

Small-file transfer over URI, used when SSH/SCP is not available on a node.

The example deploys two routes to a node:

```text
fs://host/file/command/write-b64
fs://host/file/query/read-b64
```

The route target is `host` because the connector runs inside the remote node
process. The selected node is the transport URL passed to `urirun host run`.

Deploy:

```bash
urirun host deploy http://192.168.188.201:8766 \
  --bindings examples/node-file-transfer/fs-transfer.bindings.json \
  --code examples/node-file-transfer/fs_transfer.py \
  --allow 'browser://**' \
  --allow 'fs://**' \
  --merge \
  --identity ~/.ssh/id_ed25519
```

Write one file:

```bash
urirun host run http://192.168.188.201:8766 \
  'fs://host/file/command/write-b64' \
  --payload '{"path":"~/Downloads/urirun-scans/2026-06/scan.pdf","bytes_b64":"JVBERi0xLjQK...","overwrite":true}'
```

This route is meant for small artifacts such as scanner PDFs. The current node
HTTP body limit is about 4 MB, so larger files should use a chunked transfer
route or a dedicated file service.
