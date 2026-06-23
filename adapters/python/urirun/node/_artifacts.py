# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Base64-artifact materialization: a node keeps returning ordinary JSON, but host
# commands should not dump a full PNG to stdout. These helpers preserve exact bytes
# on disk and leave a small structured reference. Self-contained (no mesh dependency);
# re-exported from mesh for backwards compatibility.
from __future__ import annotations

import argparse
import base64
import hashlib
import os
import time
from pathlib import Path
from typing import Any

from urirun.node._util import slug

DEFAULT_HOST_ARTIFACT_DIR = "~/.urirun/artifacts/host"
BASE64_ARTIFACT_MIN_CHARS = 4096


def _artifact_extension(raw: bytes, mime: str | None = None) -> tuple[str, str]:
    if mime:
        clean = mime.split(";", 1)[0].lower()
        if clean == "image/png":
            return ".png", clean
        if clean in {"image/jpeg", "image/jpg"}:
            return ".jpg", "image/jpeg"
        if clean == "image/gif":
            return ".gif", clean
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if raw.startswith(b"GIF8"):
        return ".gif", "image/gif"
    return ".bin", mime or "application/octet-stream"


def _decode_base64_artifact(value: str) -> tuple[bytes, str | None] | None:
    text = value.strip()
    mime = None
    if text.startswith("data:") and ";base64," in text[:128]:
        head, _, text = text.partition(",")
        mime = head[5:].split(";", 1)[0] or None
    if len(text) < BASE64_ARTIFACT_MIN_CHARS:
        return None
    try:
        return base64.b64decode(text, validate=True), mime
    except Exception:
        return None


def _write_artifact(raw: bytes, *, artifact_dir: str | None, hint: str, mime: str | None = None) -> dict:
    digest = hashlib.sha256(raw).hexdigest()
    ext, detected_mime = _artifact_extension(raw, mime)
    root = Path(os.path.expanduser(artifact_dir or os.environ.get("URIRUN_ARTIFACT_DIR") or DEFAULT_HOST_ARTIFACT_DIR))
    root.mkdir(parents=True, exist_ok=True)
    name = f"{time.strftime('%Y%m%dT%H%M%S')}-{slug(hint)}-{digest[:12]}{ext}"
    path = root / name
    path.write_bytes(raw)
    return {"path": str(path), "bytes": len(raw), "sha256": digest, "mime": detected_mime}


def materialize_base64_artifacts(data: Any, *, artifact_dir: str | None = None,
                                 hint: str = "artifact") -> tuple[Any, list[dict]]:
    """Replace large base64 blobs in a result tree with file artifacts.

    The node keeps returning ordinary JSON, but host commands should not dump a full PNG
    to stdout. We preserve exact bytes on disk and leave a small structured reference.
    """
    artifacts_by_sha: dict[str, dict] = {}

    def walk(value: Any, path_hint: str) -> Any:
        if isinstance(value, dict):
            out = {}
            for key, item in value.items():
                if isinstance(item, str) and key in {"base64", "data", "png", "screenshot", "image"}:
                    decoded = _decode_base64_artifact(item)
                    if decoded:
                        raw, mime = decoded
                        digest = hashlib.sha256(raw).hexdigest()
                        artifact = artifacts_by_sha.get(digest)
                        if artifact is None:
                            artifact = _write_artifact(raw, artifact_dir=artifact_dir, hint=f"{path_hint}-{key}", mime=mime)
                            artifact["fields"] = []
                            artifacts_by_sha[digest] = artifact
                        artifact["fields"].append(f"{path_hint}.{key}")
                        out[key] = {"artifactPath": artifact["path"], "bytes": artifact["bytes"],
                                    "sha256": artifact["sha256"], "mime": artifact["mime"]}
                        continue
                out[key] = walk(item, f"{path_hint}.{key}")
            return out
        if isinstance(value, list):
            return [walk(item, f"{path_hint}.{idx}") for idx, item in enumerate(value)]
        return value

    return walk(data, hint), list(artifacts_by_sha.values())


def compact_result_artifacts(result: dict, args: argparse.Namespace, *, hint: str) -> dict:
    if getattr(args, "inline_artifacts", False):
        return result
    compacted, artifacts = materialize_base64_artifacts(result, artifact_dir=getattr(args, "artifact_dir", None), hint=hint)
    if artifacts:
        compacted = dict(compacted)
        compacted["artifacts"] = artifacts
    return compacted
