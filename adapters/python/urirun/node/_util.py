# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Foundational primitives shared by the node/host modules. No dependency on mesh —
# extracting these lets mesh.py and its sibling modules (_artifacts, …) share them
# without a circular import. Re-exported from mesh for backwards compatibility.
from __future__ import annotations

import json
import re
import time
from pathlib import Path


def now_id() -> str:
    return str(int(time.time()))


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:64] or "step"


def json_load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def json_write(path: str | Path, data: dict) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
