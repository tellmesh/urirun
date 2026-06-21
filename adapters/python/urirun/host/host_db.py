# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""SQLite context store for urirun host.

Planfile remains the task store.  This database keeps context records,
artifacts, check results and LLM messages that tickets can link to.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from urirun import errors


DEFAULT_DB = "~/.urirun/host.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '',
  schema_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS records (
  id TEXT PRIMARY KEY,
  dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  data_json TEXT NOT NULL,
  source_uri TEXT,
  confidence REAL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(dataset_id, key)
);

CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  uri TEXT NOT NULL UNIQUE,
  path TEXT,
  meta_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checks (
  id TEXT PRIMARY KEY,
  subject TEXT NOT NULL,
  check_uri TEXT NOT NULL,
  status TEXT NOT NULL,
  result_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS logs (
  id TEXT PRIMARY KEY,
  stream TEXT NOT NULL,
  event TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_sessions (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_messages (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES llm_sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  extracted_json TEXT,
  created_at TEXT NOT NULL
);
"""


def db_path(path: str | None = None) -> Path:
    return Path(path or os.getenv("URIRUN_HOST_DB", DEFAULT_DB)).expanduser()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def connect(path: str | None = None) -> sqlite3.Connection:
    resolved = db_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(resolved))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection(path: str | None = None):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    for key in ("schema_json", "data_json", "meta_json", "result_json", "detail_json", "extracted_json"):
        if key in data and data[key] is not None:
            try:
                data[key.removesuffix("_json") if key.endswith("_json") else key] = json.loads(data.pop(key))
            except json.JSONDecodeError:
                pass
    return data


def rows_dict(rows) -> list[dict]:
    return [row_dict(row) for row in rows]


@errors.capture(scheme="data")
def init_db(path: str | None = None) -> dict:
    with connection(path) as conn:
        conn.executescript(SCHEMA)
        try:
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS records_fts "
                "USING fts5(record_id UNINDEXED, dataset_id UNINDEXED, key, data_text, source_uri)"
            )
            fts = True
        except sqlite3.OperationalError:
            fts = False
        return {"ok": True, "path": str(db_path(path)), "fts": fts}


def _schema_json(schema: dict | None) -> str:
    schema = schema or {"type": "object"}
    Draft202012Validator.check_schema(schema)
    return json.dumps(schema, sort_keys=True)


def create_dataset(path: str | None, name: str, description: str = "", schema: dict | None = None) -> dict:
    init_db(path)
    dataset_id = new_id("ds")
    created_at = now_iso()
    with connection(path) as conn:
        conn.execute(
            """
            INSERT INTO datasets(id, name, description, schema_json, created_at)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET description=excluded.description, schema_json=excluded.schema_json
            """,
            (dataset_id, name, description, _schema_json(schema), created_at),
        )
    return get_dataset(path, name)


def list_datasets(path: str | None = None) -> list[dict]:
    init_db(path)
    with connection(path) as conn:
        return rows_dict(conn.execute("SELECT * FROM datasets ORDER BY name").fetchall())


@errors.capture(scheme="data")
def get_dataset(path: str | None, name_or_id: str) -> dict:
    init_db(path)
    with connection(path) as conn:
        row = conn.execute(
            "SELECT * FROM datasets WHERE id = ? OR name = ?",
            (name_or_id, name_or_id),
        ).fetchone()
    if not row:
        raise ValueError(f"dataset not found: {name_or_id}")
    return row_dict(row)


def _validate_record(dataset: dict, data: dict) -> None:
    schema = dataset.get("schema") or {"type": "object"}
    Draft202012Validator(schema).validate(data)


def upsert_record(
    path: str | None,
    dataset: str,
    key: str,
    data: dict,
    *,
    source_uri: str | None = None,
    confidence: float | None = None,
) -> dict:
    init_db(path)
    dataset_row = get_dataset(path, dataset)
    _validate_record(dataset_row, data)
    timestamp = now_iso()
    record_id = new_id("rec")
    data_json = json.dumps(data, sort_keys=True, ensure_ascii=False)
    with connection(path) as conn:
        conn.execute(
            """
            INSERT INTO records(id, dataset_id, key, data_json, source_uri, confidence, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dataset_id, key) DO UPDATE SET
              data_json=excluded.data_json,
              source_uri=excluded.source_uri,
              confidence=excluded.confidence,
              updated_at=excluded.updated_at
            """,
            (record_id, dataset_row["id"], key, data_json, source_uri, confidence, timestamp, timestamp),
        )
        row = conn.execute(
            "SELECT * FROM records WHERE dataset_id = ? AND key = ?",
            (dataset_row["id"], key),
        ).fetchone()
        record = row_dict(row)
        _sync_record_fts(conn, record, dataset_row["id"])
        return record


def _sync_record_fts(conn: sqlite3.Connection, record: dict, dataset_id: str) -> None:
    try:
        conn.execute("DELETE FROM records_fts WHERE record_id = ?", (record["id"],))
        conn.execute(
            "INSERT INTO records_fts(record_id, dataset_id, key, data_text, source_uri) VALUES(?, ?, ?, ?, ?)",
            (
                record["id"],
                dataset_id,
                record["key"],
                json.dumps(record["data"], sort_keys=True, ensure_ascii=False),
                record.get("source_uri") or "",
            ),
        )
    except sqlite3.OperationalError:
        return


def search_records(path: str | None, query: str = "", dataset: str | None = None, limit: int = 20) -> list[dict]:
    init_db(path)
    params: list[Any] = []
    where = []
    if dataset:
        dataset_row = get_dataset(path, dataset)
        where.append("r.dataset_id = ?")
        params.append(dataset_row["id"])

    with connection(path) as conn:
        if query:
            try:
                fts_params = list(params)
                fts_where = list(where)
                fts_where.append("records_fts MATCH ?")
                fts_params.append(query)
                sql = (
                    "SELECT r.*, d.name AS dataset_name FROM records r "
                    "JOIN datasets d ON d.id = r.dataset_id "
                    "JOIN records_fts ON records_fts.record_id = r.id"
                )
                if fts_where:
                    sql += " WHERE " + " AND ".join(fts_where)
                sql += " ORDER BY r.updated_at DESC LIMIT ?"
                fts_params.append(limit)
                return rows_dict(conn.execute(sql, fts_params).fetchall())
            except sqlite3.OperationalError:
                where.append("(r.key LIKE ? OR r.data_json LIKE ? OR COALESCE(r.source_uri, '') LIKE ?)")
                needle = f"%{query}%"
                params.extend([needle, needle, needle])

        sql = "SELECT r.*, d.name AS dataset_name FROM records r JOIN datasets d ON d.id = r.dataset_id"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY r.updated_at DESC LIMIT ?"
        params.append(limit)
        return rows_dict(conn.execute(sql, params).fetchall())


def register_artifact(path: str | None, kind: str, uri: str, artifact_path: str | None = None, meta: dict | None = None) -> dict:
    init_db(path)
    artifact_id = new_id("art")
    with connection(path) as conn:
        conn.execute(
            """
            INSERT INTO artifacts(id, kind, uri, path, meta_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(uri) DO UPDATE SET kind=excluded.kind, path=excluded.path, meta_json=excluded.meta_json
            """,
            (artifact_id, kind, uri, artifact_path, json.dumps(meta or {}, sort_keys=True), now_iso()),
        )
        return row_dict(conn.execute("SELECT * FROM artifacts WHERE uri = ?", (uri,)).fetchone())


def list_artifacts(path: str | None = None, kind: str | None = None, limit: int = 20) -> list[dict]:
    init_db(path)
    params: list[Any] = []
    sql = "SELECT * FROM artifacts"
    if kind:
        sql += " WHERE kind = ?"
        params.append(kind)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with connection(path) as conn:
        return rows_dict(conn.execute(sql, params).fetchall())


def add_check(path: str | None, subject: str, check_uri: str, status: str, result: dict | None = None) -> dict:
    init_db(path)
    check_id = new_id("chk")
    with connection(path) as conn:
        conn.execute(
            "INSERT INTO checks(id, subject, check_uri, status, result_json, created_at) VALUES(?, ?, ?, ?, ?, ?)",
            (check_id, subject, check_uri, status, json.dumps(result or {}, sort_keys=True), now_iso()),
        )
        return row_dict(conn.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone())


def recent_checks(path: str | None = None, subject: str | None = None, limit: int = 20) -> list[dict]:
    init_db(path)
    params: list[Any] = []
    sql = "SELECT * FROM checks"
    if subject:
        sql += " WHERE subject = ?"
        params.append(subject)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with connection(path) as conn:
        return rows_dict(conn.execute(sql, params).fetchall())


def add_log(path: str | None, stream: str, event: str, detail: dict | None = None) -> dict:
    init_db(path)
    log_id = new_id("log")
    with connection(path) as conn:
        conn.execute(
            "INSERT INTO logs(id, stream, event, detail_json, created_at) VALUES(?, ?, ?, ?, ?)",
            (log_id, stream, event, json.dumps(detail or {}, sort_keys=True), now_iso()),
        )
        return row_dict(conn.execute("SELECT * FROM logs WHERE id = ?", (log_id,)).fetchone())


def recent_logs(path: str | None = None, stream: str | None = None, limit: int = 20) -> list[dict]:
    init_db(path)
    params: list[Any] = []
    sql = "SELECT * FROM logs"
    if stream:
        sql += " WHERE stream = ?"
        params.append(stream)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with connection(path) as conn:
        return rows_dict(conn.execute(sql, params).fetchall())


def create_llm_session(path: str | None, title: str) -> dict:
    init_db(path)
    session_id = new_id("llm")
    with connection(path) as conn:
        conn.execute(
            "INSERT INTO llm_sessions(id, title, created_at) VALUES(?, ?, ?)",
            (session_id, title, now_iso()),
        )
        return row_dict(conn.execute("SELECT * FROM llm_sessions WHERE id = ?", (session_id,)).fetchone())


def add_llm_message(path: str | None, session_id: str, role: str, content: str, extracted: dict | None = None) -> dict:
    init_db(path)
    message_id = new_id("msg")
    with connection(path) as conn:
        conn.execute(
            """
            INSERT INTO llm_messages(id, session_id, role, content, extracted_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (message_id, session_id, role, content, json.dumps(extracted, sort_keys=True) if extracted else None, now_iso()),
        )
        return row_dict(conn.execute("SELECT * FROM llm_messages WHERE id = ?", (message_id,)).fetchone())


def read_only_sql(path: str | None, query: str, params: list[Any] | None = None, limit: int = 100) -> list[dict]:
    init_db(path)
    stripped = query.strip().rstrip(";")
    lowered = stripped.lower()
    if not (lowered.startswith("select ") or lowered.startswith("with ")):
        raise ValueError("only SELECT/WITH read-only SQL is allowed")
    if ";" in stripped:
        raise ValueError("multiple SQL statements are not allowed")
    with connection(path) as conn:
        rows = conn.execute(stripped + f" LIMIT {int(limit)}", params or []).fetchall()
        return rows_dict(rows)


def route_db_path(ctx: dict, payload: dict) -> str | None:
    return payload.get("db") or (ctx["routeEntry"].get("config") or {}).get("db")


def run_uri_route(ctx: dict, execute: bool) -> dict:
    payload = dict(ctx.get("payload") or {})
    descriptor = ctx["descriptor"]
    package = descriptor["package"]
    resource = ctx["translation"]["resource"]
    operation = ctx["translation"]["operation"]
    args = ctx["translation"]["args"]
    action = args[0] if args else operation
    path = route_db_path(ctx, payload)

    if package == "data" and resource == "datasets" and operation == "query":
        return {"type": "host-db", "datasets": list_datasets(path)}
    if package == "data" and resource == "records" and operation == "query":
        return {
            "type": "host-db",
            "records": search_records(path, payload.get("query", ""), dataset=payload.get("dataset"), limit=int(payload.get("limit", 20))),
        }
    if package == "data" and resource == "sql" and operation == "query":
        return {"type": "host-db", "rows": read_only_sql(path, str(payload.get("query") or ""), payload.get("params") or [], int(payload.get("limit", 100)))}
    if package == "artifact" and resource == "artifacts" and operation == "query":
        return {"type": "host-db", "artifacts": list_artifacts(path, kind=payload.get("kind"), limit=int(payload.get("limit", 20)))}
    if package == "check" and resource == "checks" and operation == "query":
        return {"type": "host-db", "checks": recent_checks(path, subject=payload.get("subject"), limit=int(payload.get("limit", 20)))}
    if package == "log" and operation == "query":
        return {"type": "host-db", "logs": recent_logs(path, stream=payload.get("stream") or resource, limit=int(payload.get("limit", 20)))}

    if not execute:
        return {"type": "host-db", "simulated": True, "action": action, "payload": payload, "db": str(db_path(path))}

    if package == "data" and resource == "dataset" and operation == "command" and action == "create":
        return {
            "type": "host-db",
            "dataset": create_dataset(path, payload["name"], payload.get("description", ""), payload.get("schema")),
        }
    if package == "data" and resource == "record" and operation == "command" and action == "upsert":
        return {
            "type": "host-db",
            "record": upsert_record(
                path,
                payload["dataset"],
                payload["key"],
                payload.get("data") or {},
                source_uri=payload.get("source_uri"),
                confidence=payload.get("confidence"),
            ),
        }
    if package == "artifact" and resource == "artifact" and operation == "command" and action == "register":
        return {
            "type": "host-db",
            "artifact": register_artifact(path, payload["kind"], payload["uri"], payload.get("path"), payload.get("meta")),
        }
    if package == "check" and resource == "check" and operation == "command" and action in {"add", "create"}:
        return {
            "type": "host-db",
            "check": add_check(path, payload["subject"], payload["check_uri"], payload["status"], payload.get("result")),
        }
    if package == "log" and operation == "command" and action == "write":
        return {
            "type": "host-db",
            "log": add_log(path, payload.get("stream") or resource, payload["event"], payload.get("detail")),
        }

    raise ValueError(f"unsupported host db URI: {descriptor['normalized']}")
