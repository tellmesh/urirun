# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Small host dashboard for planfile tasks, nodes and urirun activity."""

from __future__ import annotations

import base64
import html
import hashlib
import io
import json
import mimetypes
import os
import urllib.error
import urllib.request
import re
import socket
import ssl
import subprocess
import textwrap
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urirun.node.mesh import EventHub, _sse_initial_cursor, _sse_event_matches, _sse_frame
from .twin_bridge import (
    TWIN_EVENT_HUB,
    flow_has_desktop_step as _flow_has_desktop_step,
    append_twin_widget as _append_twin_widget,
    twin_plan_preview as _twin_plan_preview,
    twin_plan_summary as _twin_plan_summary,
    is_desktop_task_prompt as _is_desktop_task_prompt,
    _DESKTOP_TASK_KEYWORDS,
)
from urllib.parse import parse_qs, parse_qsl, quote, unquote, urlencode, urlparse, urlsplit, urlunsplit

from .document_sync import (
    DOCUMENT_SYNC_URI as _DOCUMENT_SYNC_URI,
    DocumentSyncDeps,
    document_archive_pdfs as _document_archive_pdfs_impl,
    document_archive_root as _document_archive_root,
    document_index_path as _document_index_path,
    load_document_index as _load_document_index,
    save_document_index as _save_document_index,
    prune_orphaned_documents as _prune_orphaned_documents,
    document_sync_auto_retry_enabled as _document_sync_auto_retry_enabled,
    document_sync_default_dest_root as _document_sync_default_dest_root,
    document_sync_default_node as _document_sync_default_node,
    document_sync_dest_from_prompt as _document_sync_dest_from_prompt,
    document_sync_retry_payload_from_urifix as _document_sync_retry_payload_from_urifix,
    document_sync_verification as _document_sync_verification_impl,
    needs_screen_document_capture as _needs_screen_document_capture,
    sync_documents_to_node as _sync_documents_to_node_impl,
    artifact_schema_known as _artifact_schema_known,
    document_schema_fields as _document_schema_fields,
    file_sha256 as _file_sha256,
    docid_for_file as _docid_for_file,
    find_duplicate_document as _find_duplicate_document,
    archive_scanned_document as _archive_scanned_document_impl,
    _DOCUMENT_INDEX_LOCK,
    _transaction_fingerprint,
    _fingerprint_match_count,
    merge_metadata_fields as _merge_metadata_fields,
    enrich_archived_record as _enrich_archived_record,
    backfill_scanned_id_log as _backfill_scanned_id_log,
)
from .discovery import (
    add_node_aliases as _add_node_aliases_impl,
    alias_map_from_dict as _alias_map_from_dict_impl,
    alias_map_from_list as _alias_map_from_list_impl,
    classify_route_run as _classify_route_run_impl,
    host_config as _host_config_impl,
    iter_node_alias_values as _iter_node_alias_values_impl,
    known_nodes_file_data as _known_nodes_file_data_impl,
    known_nodes_file_urls as _known_nodes_file_urls_impl,
    merge_known_nodes_into_config as _merge_known_nodes_into_config_impl,
    node_alias_map_from_config_doc as _node_alias_map_from_config_doc_impl,
    node_alias_map_from_context as _node_alias_map_from_context_impl,
    node_alias_map_from_env as _node_alias_map_from_env_impl,
    node_alias_map_from_known_nodes_file as _node_alias_map_from_known_nodes_file_impl,
    node_alias_map_from_node_urls as _node_alias_map_from_node_urls_impl,
    node_alias_map_from_value as _node_alias_map_from_value_impl,
    node_dicts_from_url_map as _node_dicts_from_url_map_impl,
    node_spec_aliases as _node_spec_aliases_impl,
    node_test_routes as _node_test_routes_impl,
    node_url_map_from_value as _node_url_map_from_value_impl,
    normalize_known_node_url as _normalize_known_node_url_impl,
    prompt_node_match as _prompt_node_match_impl,
    route_inputs_example as _route_inputs_example_impl,
    url_map_from_dict as _url_map_from_dict_impl,
    url_map_from_list as _url_map_from_list_impl,
)
from .fs_transfer import (
    deploy_fs_file_transfer_fallback as _deploy_fs_file_transfer_fallback_impl,
    ensure_node_uri_routes as _ensure_node_uri_routes_impl,
    fs_file_transfer_binding as _fs_file_transfer_binding_impl,
    fs_file_transfer_fallback_bindings as _fs_file_transfer_fallback_bindings_impl,
    node_has_route as _node_has_route_impl,
    route_key as _route_key_impl,

    compact_remote_run as _compact_remote_run,
    remote_write_error as _remote_write_error,
    remote_read_error as _remote_read_error,
    node_client as _node_client,
    node_token_for as _node_token_for,
    run_node_uri as _run_node_uri,
)
from .node_types import (
    annotate_node_types as _annotate_node_types_impl,
    node_type_profile as _node_type_profile_impl,
    node_type_profiles as _node_type_profiles_impl,
    node_type_tags as _node_type_tags_impl,
    normalize_node_type as _normalize_node_type_impl,
)
from .object_registry import (
    annotate_node_tokens as _annotate_node_tokens_impl,
    host_object as _host_object_impl,
    host_registry_routes as _host_registry_routes_impl,
    service_contacts as _service_contacts_impl,
    uri_objects as _uri_objects_impl,
    mirror_node_to_nodes_file as _mirror_node_to_nodes_file,
    uri_action_catalog as _uri_action_catalog,
    node_api_slug as _node_api_slug,
    node_api_secret_ref as _node_api_secret_ref,
    store_node_api_secret as _store_node_api_secret,
    extract_raw_secret as _extract_raw_secret,
    extract_secret_ref as _extract_secret_ref,
    build_auth_extra_fields as _build_auth_extra_fields,
    normalize_node_api_auth as _normalize_node_api_auth,
    default_api_items as _default_api_items,
    api_item_fields as _api_item_fields,
    normalize_api_item as _normalize_api_item,
    normalize_node_apis as _normalize_node_apis,
    derive_node_capabilities as _derive_node_capabilities,
    build_node_entry as _build_node_entry,
    persist_node_to_config as _persist_node_to_config,
    node_remove_from_mirror as _node_remove_from_mirror,
    configured_node_api_parts as _configured_node_api_parts,
    configured_node_api_lookup as _configured_node_api_lookup_impl,
    configured_api_secret as _configured_api_secret,
    apply_auth_header as _apply_auth_header,
    configured_api_headers as _configured_api_headers,
    join_api_url as _join_api_url,
    configured_api_response_body as _configured_api_response_body,
    build_request_body as _build_request_body,
    execute_http_request as _execute_http_request,
    resolve_http_method_and_url as _resolve_http_method_and_url,
    connector_hint as _connector_hint,
    connector_required_response as _connector_required_response,
    configured_api_call as _configured_api_call,
    apply_uri_overrides as _apply_uri_overrides,
    resolve_node_api_identifiers as _resolve_node_api_identifiers,
    _SCHEME_CONNECTOR_PACKAGES,
    node_kinds_path as _node_kinds_path,
    node_kinds as _node_kinds,
    set_node_kind as _set_node_kind,
    node_remove_kind as _node_remove_kind,
    annotate_node_kinds as _annotate_node_kinds,
    node_add as _node_add_impl,
    node_remove as _node_remove_impl,
    node_envelope_error as _node_envelope_error_impl,
    probe_node_token as _probe_node_token_impl,
    node_set_token as _node_set_token_impl,
)
from .connector_admin import (
    CONNECTOR_DOCKER_TIMEOUT as _CONNECTOR_DOCKER_TIMEOUT,
    connector_install as _connector_install_impl,
    _connector_install_node as _connector_install_node_impl,
    connector_pip_tail as _connector_pip_tail,
    refresh_connector_schemes as _refresh_connector_schemes,
    env_check_error as _env_check_error,
    docker_install_target as _docker_install_target,
    run_docker_check as _run_docker_check,
    parse_bindings_output as _parse_bindings_output,
    connector_env_check as connector_env_check,
)
from .artifacts_admin import (
    artifact_delete_roots as _artifact_delete_roots,
    artifact_file_delete_allowed as _artifact_file_delete_allowed,
    payload_bool as _payload_bool,
    global_document_metadata_paths as _global_document_metadata_paths,
    safe_artifact_sidecar_path as _safe_artifact_sidecar_path,
    artifact_delete_candidate_paths as _artifact_delete_candidate_paths,
    delete_one_artifact_file as _delete_one_artifact_file,
    delete_artifact_files as _delete_artifact_files,
    artifact_visual_path as _artifact_visual_path,
    artifact_file_exists as _artifact_file_exists,
    artifact_dedupe_key as _artifact_dedupe_key,
    artifact_dedupe_rank as _artifact_dedupe_rank,
    merge_artifact_group as _merge_artifact_group,
    preview_url as _preview_url,
    public_artifact as _public_artifact,
    public_artifacts as _public_artifacts,
    attachment_visual_path as _attachment_visual_path,
    apply_attachment_file_fields as _apply_attachment_file_fields,
    apply_attachment_visual_fields as _apply_attachment_visual_fields,
    public_chat_attachment as _public_chat_attachment,
    public_chat_attachments as _public_chat_attachments,
    dedupe_public_artifacts as _dedupe_public_artifacts,
    visible_public_artifacts as _visible_public_artifacts,
    collect_attachments as _collect_attachments,
    iter_orphan_candidates as _iter_orphan_candidates,
    cleanup_one_sidecar as _cleanup_one_sidecar,
    artifacts_delete as _artifacts_delete_impl,
    artifacts_dedupe_rows as _artifacts_dedupe_rows_impl,
    artifacts_cleanup_orphan_sidecars as _artifacts_cleanup_orphan_sidecars_impl,
)
from .html_templates import (
    INDEX_HTML, NODE_TYPES_DOC_HTML, SCANNER_HTML,
    docs_nodes_html as _docs_nodes_html_impl,
    service_widget_html as _service_widget_html_impl,
    service_widget_svg as _service_widget_svg_impl,
)
from .scanner_bridge import (
    PAGE_ACTION_LOCK as _SCANNER_PAGE_ACTION_LOCK,
    PAGE_ACTION_QUEUES as _SCANNER_PAGE_ACTION_QUEUES,
    SCANNER_BEST_LOCK as _SCANNER_BEST_LOCK,
    SCANNER_BEST_SESSIONS as _SCANNER_BEST_SESSIONS,
    SCANNER_LIVE_STREAMS as _SCANNER_LIVE_STREAMS,
    ScannerBridgeDeps,
    crop_overlay_attachment as _crop_overlay_attachment_impl,
    page_action_enqueue as _page_action_enqueue_impl,
    page_action_poll as _page_action_poll_impl,
    page_action_result as _page_action_result_impl,
    public_scanner_candidate as _public_scanner_candidate_impl,
    is_autonomous_scanner_prompt as _is_autonomous_scanner_prompt_impl,
    is_camera_start_prompt as _is_camera_start_prompt_impl,
    is_scanner_artifact as _is_scanner_artifact_impl,
    is_phone_scanner_prompt as _is_phone_scanner_prompt_impl,
    latest_scanner_page_status as _latest_scanner_page_status_impl,
    nl_text as _nl_text_impl,
    register_document_artifact as _register_document_artifact_impl,
    scanner_artifact_item as _scanner_artifact_item_impl,
    scanner_artifact_doc_meta as _scanner_artifact_doc_meta_impl,
    bounded as _bounded,
    crop_dimensions as _crop_dimensions,
    crop_geometry_score as _crop_geometry_score,
    crop_quality_score as _crop_quality_score,
    doctype_quality_score as _doctype_quality_score,
    document_frame_quality as _document_frame_quality,
    frame_visual_metrics as _frame_visual_metrics,
    metadata_quality_score as _metadata_quality_score,
    ocr_quality_score as _ocr_quality_score,
    orientation_summary as _orientation_summary,
    scanner_best_take as _scanner_best_take,
    scanner_best_update as _scanner_best_update,
    scanner_staging_dir as _scanner_staging_dir,
    staging_keep_paths as _staging_keep_paths,
    prune_scanner_staging as _prune_scanner_staging_impl,
    visual_quality_score as _visual_quality_score,
    scanner_live_state_from_streams as _scanner_live_state_from_streams_impl,
    scanner_live_store_locked as _scanner_live_store_locked,
    scanner_public_candidate_for_live as _scanner_public_candidate_for_live_impl,
    scanner_status_from_log as _scanner_status_from_log_impl,
    scanner_session as _scanner_session_impl,
    scanner_result_content as _scanner_result_content_impl,
    scanner_service_live_views as _scanner_service_live_views_impl,
    scanner_flow_result as _scanner_flow_result_impl,
    torch_enabled_from_prompt as _torch_enabled_from_prompt_impl,
    uri_event as _uri_event_impl,
    best_candidate_paths as _best_candidate_paths,
    best_crop_and_ocr as _best_crop_and_ocr,
    best_finish_store_failure as _best_finish_store_failure_impl,
    best_quality_rejected as _best_quality_rejected,
    best_series_not_found as _best_series_not_found,
    capture_display_path as _capture_display_path,
    capture_quality_ok as _capture_quality_ok,
    cleanup_duplicate_scan_files as _cleanup_duplicate_scan_files,
    decode_capture_image as _decode_capture_image,
    resolve_best_candidate as _resolve_best_candidate,
    store_best_finish as _store_best_finish,
    capture_candidate_result as _capture_candidate_result_impl,
    capture_reject_result as _capture_reject_result_impl,
    scanner_live_state as _scanner_live_state_impl,
    draw_crop_box as _draw_crop_box,
    draw_overlay_label as _draw_overlay_label,
    scanner_crop_overlay as _scanner_crop_overlay,
    auto_crop_receipt as _auto_crop_receipt,
    capture_ocr_and_detect as _capture_ocr_and_detect_impl,
    refresh_best_ocr as _refresh_best_ocr_impl,
    ensure_best_overlay as _ensure_best_overlay_impl,
    scanner_capture as _scanner_capture_impl,
    scanner_best_finish as _scanner_best_finish_impl,
    register_scanner_result as _register_scanner_result_impl,
)
# Backward-compat alias — tests and older callers used _PAGE_ACTION_QUEUES.
_PAGE_ACTION_QUEUES = _SCANNER_PAGE_ACTION_QUEUES
from .service_control import (
    chat_service_restart_argv as _chat_service_restart_argv_impl,
    free_port_from_matching_processes as _free_port_from_matching_processes_impl,
    free_port_from_old_dashboard as _free_port_from_old_dashboard_impl,
    is_android_node_process as _is_android_node_process_impl,
    is_chat_process as _is_chat_process_impl,
    is_dashboard_process as _is_dashboard_process_impl,
    is_scanner_process as _is_scanner_process_impl,
    port_holder_pids as _port_holder_pids_impl,
    port_holder_pids as _port_holder_pids,  # monkeypatch-friendly alias  # noqa: F401
    process_cmdline as _process_cmdline_impl,
    process_cmdline as _process_cmdline,  # monkeypatch-friendly alias  # noqa: F401
    restart_chat_service as _restart_chat_service_impl,
    schedule_restart_command as _schedule_restart_command_impl,
    service_lifecycle_aliases as _service_lifecycle_aliases_impl,
    service_restart_argv as _service_restart_argv_impl,
    service_status as _service_status_impl,
    stop_service_pids as _stop_service_pids_impl,
)
from .widgets import (
    query_value as _widget_query_value,
    scanner_stream_summary as _scanner_stream_summary_impl,
    select_service_view as _select_service_view_impl,
    service_widget_summary as _service_widget_summary_impl,
)

try:
    import docid.dedup as _docid_dedup_check  # noqa: F401
    _DOCID_DEDUP_IMPORT_ERROR = None
except Exception as _err:  # noqa: BLE001
    _DOCID_DEDUP_IMPORT_ERROR = _err

from .scanner_service import (
    _SERVICE_LOCK,
    _SERVICE_SERVERS,
    _SERVICE_THREADS,
    phone_scanner_service_id as _phone_scanner_service_id,
    startup_phone_qr as _startup_phone_qr_impl,
    phone_node_qr as _phone_node_qr_impl,
    ensure_phone_scanner_service as _ensure_phone_scanner_service_impl,
    restart_phone_scanner_service as _restart_phone_scanner_service_impl,
)
# Monkeypatch-friendly aliases (auto-sync moved these to scanner_bridge with _impl suffix)
_is_phone_scanner_prompt = _is_phone_scanner_prompt_impl  # noqa: F401
_torch_enabled_from_prompt = _torch_enabled_from_prompt_impl  # noqa: F401
page_action_poll = _page_action_poll_impl  # noqa: F401
_LAST_STAGING_PRUNE: float = 0.0


def _prune_scanner_staging(*, min_interval: float = 60.0) -> int:
    """Wrapper: injects _scanner_staging_dir; owns throttle via module-level _LAST_STAGING_PRUNE."""
    global _LAST_STAGING_PRUNE
    import time as _time
    now = _time.time()
    if now - _LAST_STAGING_PRUNE < min_interval:
        return 0
    _LAST_STAGING_PRUNE = now
    return _prune_scanner_staging_impl(_scanner_staging_dir, min_interval=0.0)


def _archive_scanned_document(**kwargs):
    """Wrapper: injects the patchable _docid_for_file so tests can monkeypatch it."""
    return _archive_scanned_document_impl(**kwargs, docid_fn=_docid_for_file)


def artifacts_delete(project, artifact_dir, payload, db=None):
    return _artifacts_delete_impl(_host_db(), project, db, payload)


def artifacts_dedupe_rows(project, artifact_dir, payload, db=None):
    return _artifacts_dedupe_rows_impl(_host_db(), project, db, payload)


def artifacts_cleanup_orphan_sidecars(project, artifact_dir, payload, db=None):
    return _artifacts_cleanup_orphan_sidecars_impl(_host_db(), project, db, payload)


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler: BaseHTTPRequestHandler, html: str = INDEX_HTML) -> None:
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _docs_nodes_html() -> str:
    return _docs_nodes_html_impl(_node_type_profiles_impl())


def _asset_response(handler: BaseHTTPRequestHandler, body: bytes, content_type: str) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _service_view_from_query(project: str, query: dict[str, list[str]]) -> dict:
    target = _widget_query_value(query, "target") or _widget_query_value(query, "service") or "service:phone-scanner"
    view_id = _widget_query_value(query, "id")
    data = service_live_views(project, limit=int(_first(query, "limit", "8") or 8))
    return _select_service_view_impl(data, target=target, view_id=view_id, utc_now=_utc_now)


def _service_widget_html(project: str, query: dict[str, list[str]]) -> str:
    return _service_widget_html_impl(_service_view_from_query(project, query))


def _service_widget_svg(project: str, query: dict[str, list[str]]) -> str:
    view = _service_view_from_query(project, query)
    summary = _service_widget_summary_impl(view)
    width = max(320, min(1200, int(_first(query, "width", "720") or 720)))
    height = max(120, min(600, int(_first(query, "height", "180") or 180)))
    return _service_widget_svg_impl(view, summary, width=width, height=height)


def _js_sdk_response(handler: BaseHTTPRequestHandler, project: str) -> None:
    configured = os.environ.get("URIRUN_JS_SDK")
    roots = []
    if configured:
        roots.append(Path(configured).expanduser())
    project_path = Path(project).expanduser().resolve()
    roots.extend([
        project_path.parent / "js-urirun-com" / "urirun.js",
        project_path.parent / "js-urirun-com" / "src" / "urirun.js",
        Path("/home/tom/github/if-uri/js-urirun-com/urirun.js"),
        Path("/home/tom/github/if-uri/js-urirun-com/src/urirun.js"),
    ])
    for source in roots:
        try:
            resolved = source.expanduser().resolve()
            if resolved.is_file():
                _asset_response(handler, resolved.read_bytes(), "application/javascript; charset=utf-8")
                return
        except Exception:  # noqa: BLE001
            continue
    _json_response(handler, 404, {"ok": False, "error": "urirun JS SDK not found"})


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8") or "{}")


def _file_response(handler: BaseHTTPRequestHandler, path: str, project: str) -> None:
    import tempfile  # noqa: PLC0415
    source = Path(path).expanduser().resolve()
    allowed_roots = [
        Path(project).expanduser().resolve(),
        Path("~/.urirun").expanduser().resolve(),
        Path(os.environ.get("URIRUN_ARTIFACT_DIR", "~/.urirun/artifacts")).expanduser().resolve(),
    ]
    in_temp = source.parent == Path(tempfile.gettempdir()) and source.name.startswith("urirun-")
    if not in_temp and not any(source == root or source.is_relative_to(root) for root in allowed_roots):
        _json_response(handler, 403, {"ok": False, "error": "file is outside dashboard preview roots"})
        return
    if not source.is_file():
        _json_response(handler, 404, {"ok": False, "error": "file not found"})
        return
    mime = mimetypes.guess_type(str(source))[0] or "application/octet-stream"
    body = source.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _chat_message(role: str, content: str, *, detail: dict | None = None, attachments: list[dict] | None = None) -> dict:
    return {
        "role": role,
        "content": content,
        "detail": detail or {},
        "attachments": attachments or [],
    }


def _add_chat_message(db: str | None, message: dict) -> dict | None:
    try:
        return _host_db().add_log(db, "chat", "message", message)
    except Exception:  # noqa: BLE001
        return None





from . import document_metadata as _document_metadata
from .document_metadata import (  # noqa: F401,E402 - re-export shim placed where the funcs were
    _LLM_DOC_TYPES,
    _LLM_FIELDS_SPEC,
    _coerce_amount,
    _document_type,
    _extract_document_metadata,
    _llm_api_key_ref,
    _llm_complete_metadata,
    _llm_env_file,
    _llm_extract_metadata,
    _llm_model,
    _load_env_file,
    _local_image_ocr,
    _local_image_ocr_llm,
    _local_image_ocr_tesseract,
    _normalize_llm_doc_fields,
    _normalized_document_text,
    _ocr_connector_envelope,
    _ocr_text_ok,
    _parse_amount,
    _parse_contractor,
    _parse_document_date,
    _parse_llm_json_object,
    _truthy_env,
    shutil_which,
)


def _sync_document_metadata_hooks() -> None:
    for name in (
        "_llm_extract_metadata",
        "_llm_model",
        "_llm_api_key_ref",
        "_llm_complete_metadata",
        "_local_image_ocr_tesseract",
        "_local_image_ocr_llm",
        "_ocr_connector_envelope",
        "_ocr_text_ok",
        "_truthy_env",
        "shutil_which",
    ):
        setattr(_document_metadata, name, globals()[name])


def _extract_document_metadata(ocr_text: str, *, captured_at: str | None = None,
                               image_path: str | None = None, use_llm: bool = True) -> dict:
    _sync_document_metadata_hooks()
    return _document_metadata._extract_document_metadata(
        ocr_text,
        captured_at=captured_at,
        image_path=image_path,
        use_llm=use_llm,
    )


def _local_image_ocr(path: str, backend: str | None = None) -> dict:
    _sync_document_metadata_hooks()
    return _document_metadata._local_image_ocr(path, backend=backend)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _node_alias_map_from_context(config: str | None, node_urls: list[str] | None = None) -> dict[str, str]:
    try:
        config_doc = _host_config(config, node_urls)
    except Exception:
        config_doc = None
    return _node_alias_map_from_context_impl(
        config_doc,
        node_urls,
        default_node=_document_sync_default_node(),
    )
def _node_url_from_config(config: str | None, node_urls: list[str] | None, node: str) -> str | None:
    try:
        return str(_mesh().node_url(_host_config(config, node_urls), node)).rstrip("/")
    except (Exception, SystemExit):  # mesh.node_url exits for unknown nodes.
        return None


def node_test_routes(project: str, db: str | None, config: str | None, payload: dict, *,
                     node_urls: list[str] | None = None, token: str | None = None,
                     identity: str | None = None) -> dict:
    return _node_test_routes_impl(
        payload,
        node_url_from_config=lambda node: _node_url_from_config(config, node_urls, node),
        node_token_for=lambda node: _node_token_for(node, token),
        node_client=_node_client,
        token=token,
        identity=identity,
    )


def _ensure_node_uri_routes(
    node_url: str,
    required_uris: list[str],
    *,
    node: str,
    token: str | None = None,
    identity: str | None = None,
    timeout: float = 120.0,
    roots: Any = None,
) -> dict:
    return _ensure_node_uri_routes_impl(
        node_url,
        required_uris,
        node=node,
        node_client=_node_client,
        token=token,
        identity=identity,
        timeout=timeout,
        roots=roots,
    )


def _document_sync_deps() -> DocumentSyncDeps:
    return DocumentSyncDeps(
        document_archive_root=_document_archive_root,
        default_node=_document_sync_default_node,
        default_dest_root=_document_sync_default_dest_root,
        node_url_from_config=_node_url_from_config,
        archive_pdfs=_document_archive_pdfs_impl,
        verification=lambda files, results, source_root, read_back: _document_sync_verification_impl(
            files, results, source_root=source_root, read_back=read_back
        ),
        ensure_node_uri_routes=_ensure_node_uri_routes,
        run_node_uri=_run_node_uri,
        compact_remote_run=_compact_remote_run,
        remote_write_error=_remote_write_error,
        remote_read_error=_remote_read_error,
        utc_now=_utc_now,
        host_db=_host_db,
        chat_message=_chat_message,
        add_chat_message=_add_chat_message,
    )


def sync_documents_to_node(
    project: str,
    db: str | None,
    config: str | None,
    payload: dict,
    *,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
) -> dict:
    # Use the per-node management token (set via the dashboard Nodes view, stored in keyring) when
    # present, so node:// route provisioning on the target is authorized; else the host-wide token.
    node_name = str((payload or {}).get("node") or (payload or {}).get("targetNode") or "").strip()
    token = _node_token_for(node_name, token)
    return _sync_documents_to_node_impl(
        project,
        db,
        config,
        payload,
        deps=_document_sync_deps(),
        node_urls=node_urls,
        token=token,
        identity=identity,
    )


from .document_sync import reconcile_document_index  # noqa: F401 - re-export

from .decision_loop import (
    decision_loop_status as _decision_loop_status,
    decision_loop_next_intent as _decision_loop_next_intent,
    decision_loop_observation as _decision_loop_observation,
    decision_loop_for_document_sync as _decision_loop_for_document_sync,
    general_path_next_intent as _general_path_next_intent,
)
from .scanner_net import (  # noqa: F401,E402 - re-export shim placed where the funcs were
    _ensure_tls_cert,
    _lan_host,
    _phone_scanner_external_status,
    _phone_scanner_url,
    _probe_scanner_url,
    _public_base_url,
    _scanner_autonomy_params,
    _scanner_page_url,
    _url_host,
    _write_qr_png,
)


def startup_phone_qr(project: str, db: str | None, *, scheme: str, host: str, port: int,
                     qr_url: str | None = None, content_prefix: str = "Phone scanner QR ready") -> dict:
    return _startup_phone_qr_impl(
        project, db,
        scheme=scheme, host=host, port=port, qr_url=qr_url, content_prefix=content_prefix,
        host_db_fn=_host_db,
        preview_url_fn=_preview_url,
        chat_message_fn=_chat_message,
        add_chat_message_fn=_add_chat_message,
    )


def ensure_phone_scanner_service(
    project: str,
    db: str | None,
    config: str | None = None,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
    *,
    host: str | None = None,
    port: int | None = None,
    tls_cert: str | None = None,
    tls_key: str | None = None,
) -> dict:
    return _ensure_phone_scanner_service_impl(
        project, db, config, node_urls, token, identity,
        host=host, port=port, tls_cert=tls_cert, tls_key=tls_key,
        serve_fn=serve,
        startup_phone_qr_fn=startup_phone_qr,
        host_db_fn=_host_db,
    )


def _latest_scanner_page_status(db: str | None) -> dict:
    try:
        logs = _host_db().recent_logs(db, stream="page-action", limit=80)
    except Exception:  # noqa: BLE001
        return {}
    return _latest_scanner_page_status_impl(logs)


def _recent_scanner_artifacts(db: str | None, project: str, limit: int = 6) -> list[dict]:
    try:
        artifacts = _host_db().list_artifacts(db, limit=80)
    except Exception:  # noqa: BLE001
        return []
    out: list[dict] = []
    for artifact in artifacts:
        kind = str(artifact.get("kind") or "")
        uri = str(artifact.get("uri") or "")
        meta = artifact.get("meta") if isinstance(artifact.get("meta"), dict) else {}
        if not _is_scanner_artifact_impl(kind, uri, meta):
            continue
        path = str(artifact.get("path") or "")
        display_path = str(meta.get("displayImage") or meta.get("displayPath") or path)
        if not _artifact_file_exists(path) and not _artifact_file_exists(display_path):
            continue
        doc = _scanner_artifact_doc_meta_impl(artifact)
        out.append(_scanner_artifact_item_impl(artifact, kind, uri, path, display_path, doc, project, preview_url=_preview_url))
        if len(out) >= max(1, int(limit or 6)):
            break
    return out


def service_live_views(project: str, db: str | None = None, limit: int = 8) -> dict:
    scanner = _scanner_live_state_impl(project, limit=limit, preview_url=_preview_url)
    service = next((item for item in _service_contacts() if item.get("id") == "service:phone-scanner"), {})
    recent_artifacts = _recent_scanner_artifacts(db, project, limit=6)
    camera_status = _latest_scanner_page_status(db)
    return _scanner_service_live_views_impl(
        scanner,
        service,
        recent_artifacts,
        camera_status,
        utc_now=_utc_now,
    )


def _scanner_bridge_deps() -> ScannerBridgeDeps:
    return ScannerBridgeDeps(
        preview_url=_preview_url,
        register_artifact=lambda db, kind, uri, path, meta: _host_db().register_artifact(
            db, kind, uri, path, meta
        ),
        chat_message=_chat_message,
        add_chat_message=_add_chat_message,
        add_log=lambda db, stream, event, detail: _host_db().add_log(db, stream, event, detail),
    )


def uri_event(db: str | None, query: dict) -> dict:
    """Thin wrapper: injects _scanner_bridge_deps() for tests that patch _host_db."""
    return _uri_event_impl(_scanner_bridge_deps(), db, query)


def _register_scanner_result(project: str, db: "str | None", **kwargs) -> dict:
    """Wrapper so tests can monkeypatch host_dashboard._register_scanner_result."""
    return _register_scanner_result_impl(_scanner_bridge_deps(), project, db, **kwargs)


def scanner_capture(project: str, db: str | None, payload: dict) -> dict:
    return _scanner_capture_impl(
        project, db, payload,
        deps=_scanner_bridge_deps(),
        archive_fn=_archive_scanned_document,
        local_image_ocr_fn=_local_image_ocr,
        extract_document_metadata_fn=_extract_document_metadata,
        truthy_env_fn=_truthy_env,
        auto_crop_receipt_fn=_auto_crop_receipt,
    )


def scanner_best_finish(project: str, db: str | None, payload: dict) -> dict:
    return _scanner_best_finish_impl(
        project, db, payload,
        deps=_scanner_bridge_deps(),
        archive_fn=_archive_scanned_document,
        local_image_ocr_fn=_local_image_ocr,
        truthy_env_fn=_truthy_env,
    )


def page_action_enqueue(
    db: str | None,
    *,
    target: str,
    uri: str,
    payload: dict | None = None,
    mode: str = "execute",
    source: str = "host",
) -> dict:
    return _page_action_enqueue_impl(
        _scanner_bridge_deps(),
        db,
        target=target,
        uri=uri,
        payload=payload,
        mode=mode,
        source=source,
        uri_mode=_uri_mode,
        utc_now=_utc_now,
    )


def _uri_action_lookup(uri: str) -> dict | None:
    for item in _uri_action_catalog():
        if item["uri"] == uri:
            return item
    aliases = {
        "scanner://host/capture": "scanner://host/capture/command/run",
        "scanner://host/best/finish": "scanner://host/best/command/finish",
        "scanner://host/session": "scanner://host/session/command/log",
        "scanner://page/start-button": "scanner://page/ui/button/start-camera/command/click",
        "scanner://page/torch": "scanner://page/camera/command/torch",
        "scanner://page/torch-button": "scanner://page/ui/button/torch/command/click",
        "dashboard://host/actions/query/list": "scanner://host/actions/query/list",
        **_service_lifecycle_aliases_impl("phone-scanner"),
        "scanner://host/service/command/restart": "dashboard://host/service/phone-scanner/command/restart",
        **_service_lifecycle_aliases_impl("chat"),
        **_service_lifecycle_aliases_impl("android-node"),
        "webpage://host/service/command/restart": "dashboard://host/service/android-node/command/restart",
        "document://host/archive/sync": "document://host/archive/command/sync-to-node",
        "api://host/node-api/command/request": "configured://host/node-api/command/request",
        "api://host/node-api/query/status": "configured://host/node-api/query/status",
    }
    target = aliases.get(uri)
    if target:
        return _uri_action_lookup(target)
    return None


def _uri_mode(value: Any) -> str:
    mode = str(value or "execute").strip().lower()
    if mode in {"execute", "exec", "run"}:
        return "execute"
    return "dry-run"


def _service_restart_argv(payload: dict, *, service: str, env_prefix: str, default_unit: str) -> tuple[list[str] | None, dict]:
    return _service_restart_argv_impl(
        payload,
        service=service,
        env_prefix=env_prefix,
        default_unit=default_unit,
    )


def restart_chat_service(
    payload: dict,
    *,
    project: str = ".",
    db: str | None = None,
    config: str | None = None,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
) -> dict:
    return _restart_chat_service_impl(
        payload,
        project=project,
        db=db,
        config=config,
        node_urls=node_urls,
        token=token,
        identity=identity,
    )


def restart_phone_scanner_service(
    project: str,
    db: str | None,
    config: str | None = None,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
    payload: dict | None = None,
) -> dict:
    return _restart_phone_scanner_service_impl(
        project, db, config, node_urls, token, identity, payload=payload,
        ensure_fn=ensure_phone_scanner_service,
        free_port_fn=_free_port_from_old_scanner,
        external_status_fn=_phone_scanner_external_status,
    )


def _uri_simulated_result(uri: str, mode: str, action_payload: dict, action: dict | None) -> dict:
    return {
        "ok": True,
        "uri": uri,
        "invokedUri": uri,
        "mode": mode,
        "simulated": True,
        "dryRun": True,
        "action": action or {"uri": uri},
        "payload": action_payload,
        "wouldRun": {
            "uri": uri,
            "layer": (action or {}).get("layer"),
            "kind": (action or {}).get("kind"),
            "sideEffects": (action or {}).get("sideEffects", []),
        },
    }


_INPROCESS_BINDINGS_GROUP = "urirun.bindings"


def _result_artifact_class(value: Any) -> str | None:
    """Classify a connector result via the shared ``urirun.tag`` contract.

    Returns ``"widget"`` for a live view (``live=True``), ``"artifact"`` for a frozen
    output (``live=False``), or ``None`` when the result is untagged (no ``live`` key) so
    the host falls back to its own taxonomy. This is how the host *consumes* the contract:
    a live view is routed to the chat-stream (never the frozen artifact store) and a frozen
    output to the artifact catalogue, by the connector's own declaration rather than a guess.
    """
    if not isinstance(value, dict) or "live" not in value:
        return None
    return "widget" if value.get("live") else "artifact"


def register_tagged_artifact(db: str | None, *, uri: str, result: Any, meta: dict | None = None) -> dict | None:
    """Route a tagged connector result per the shared ``urirun.tag`` contract.

    * frozen **artifact** (``live=False``) pointing at an on-disk ``path`` -> cataloged in
      the artifact store under its connector-declared ``kind``;
    * live **widget** (``live=True``) -> never stored (it is a self-updating view);
    * untagged result -> left alone (the host's own taxonomy decides elsewhere).

    Returns the registered artifact row, or ``None`` when nothing was stored. Best-effort:
    never raises, so a catalog hiccup cannot fail the connector call.
    """
    if _result_artifact_class(result) != "artifact":
        return None
    path = str((result or {}).get("path") or "")
    if not path or not Path(path).expanduser().is_file():
        return None
    kind = str(result.get("kind") or "artifact")
    try:
        return _host_db().register_artifact(db, kind, uri, path, meta or {})
    except Exception:  # noqa: BLE001
        return None


def _run_inprocess_connector_uri(uri: str, action_payload: dict, db: str | None = None) -> dict | None:
    """Execute an installed in-process connector URI (widget://, artifact://, …) through the
    urirun runtime and return its unwrapped handler value. Returns None when no connector owns
    the route, so :func:`uri_invoke` can fall back to its legacy "unsupported URI action" error.

    This is what lets the dashboard pull connector output over a URI request rather than baking
    it into the page — e.g. the chat-stream widgets are loaded from
    ``widget://host/bundle/query/js`` instead of being inlined in INDEX_HTML."""
    try:
        import urirun
        from urirun.runtime import discovery

        registry = discovery.registry_for_uri(uri, _INPROCESS_BINDINGS_GROUP)
        env = urirun.run(uri, registry, payload=dict(action_payload or {}),
                         mode="execute", policy={"allowExecute": True})
    except Exception as exc:  # noqa: BLE001 - a connector error must not crash the API
        return {"ok": False, "invokedUri": uri, "error": str(exc)}
    if not env.get("ok") and (env.get("error") or {}).get("category") == "NOT_FOUND":
        return None  # no connector owns this route → let the caller raise the legacy error
    try:
        value = urirun.result_data(env)
    except Exception:  # noqa: BLE001
        value = (env.get("result") or {}).get("value") if isinstance(env.get("result"), dict) else None
    # Route by the tag contract: a frozen artifact with a path gets cataloged under its
    # declared kind; a live widget never does. No-op for today's in-process traffic
    # (widget://, artifact:// registry/schema queries are untagged), correct for any
    # connector that returns a frozen file artifact over this path.
    registered = register_tagged_artifact(db, uri=uri, result=value) if db else None
    return {"ok": bool(env.get("ok")), "invokedUri": uri,
            "result": value if value is not None else env.get("result"),
            "artifactClass": _result_artifact_class(value),
            "registeredArtifact": registered,
            "error": (env.get("error") or {}).get("message") if not env.get("ok") else None}


from .dispatch import make_local_dispatch_uri as _make_local_dispatch_uri


_UNROUTED = object()  # sentinel: _uri_invoke_route matched no built-in route (distinct from a handler returning None)

_SVC_PORT_MAP = {"phone-scanner": 8196, "chat": 8194, "android-node": 8195}
_SVC_IS_MAP: dict = {}  # populated lazily to avoid circular imports at module load


def _svc_port(name: str) -> int:
    env_key = f"URIRUN_{name.replace('-', '_').upper()}_PORT"
    return int(os.environ.get(env_key, str(_SVC_PORT_MAP[name])))


def _svc_is_map() -> dict:
    if not _SVC_IS_MAP:
        _SVC_IS_MAP.update({
            "phone-scanner": _is_scanner_process_impl,
            "chat": _is_chat_process_impl,
            "android-node": _is_android_node_process_impl,
        })
    return _SVC_IS_MAP


def _svc_start_fn(name: str, project: str, db, config, node_urls, token, identity, payload: dict):
    """Start a named host service (no-op if already running).
    Each service has its own start/ensure implementation; this dispatches to it."""
    if name == "phone-scanner":
        return ensure_phone_scanner_service(project, db, config,
                                            node_urls=node_urls, token=token, identity=identity)
    if name == "chat":
        return restart_chat_service(payload, project=project, db=db, config=config,
                                    node_urls=node_urls, token=token, identity=identity)
    if name == "android-node":
        return restart_android_node_service(payload)
    return {"ok": False, "service": name, "error": f"no start handler for service '{name}'"}


def _svc_restart_fn(name: str, project: str, db, config, node_urls, token, identity, payload: dict):
    """Restart a named host service (stop then start, regardless of running state)."""
    if name == "phone-scanner":
        return restart_phone_scanner_service(project, db, config,
                                             node_urls=node_urls, token=token, identity=identity,
                                             payload=payload)
    if name == "chat":
        return restart_chat_service(payload, project=project, db=db, config=config,
                                    node_urls=node_urls, token=token, identity=identity)
    if name == "android-node":
        return restart_android_node_service(payload)
    return {"ok": False, "service": name, "error": f"no restart handler for service '{name}'"}


def _service_lifecycle_dispatch(
    uri: str, project: str, db, config, node_urls, token, identity, payload: dict
):
    """Handle all four standard lifecycle verbs for the three named host services:
    query/status, command/start, command/stop, command/restart."""
    for svc in _SVC_PORT_MAP:
        if uri == f"dashboard://host/service/{svc}/query/status":
            status = _service_status_impl(_svc_port(svc), _svc_is_map()[svc])
            return {"ok": True, "service": svc, **status}
        if uri == f"dashboard://host/service/{svc}/command/stop":
            result = _stop_service_pids_impl(_svc_port(svc), _svc_is_map()[svc])
            return {"ok": True, "service": svc, **result}
        if uri == f"dashboard://host/service/{svc}/command/start":
            status = _service_status_impl(_svc_port(svc), _svc_is_map()[svc])
            if status["running"]:
                return {"ok": True, "service": svc, "started": False,
                        "detail": f"{svc} is already running", **status}
            return _svc_start_fn(svc, project, db, config, node_urls, token, identity, payload)
        if uri == f"dashboard://host/service/{svc}/command/restart":
            return _svc_restart_fn(svc, project, db, config, node_urls, token, identity, payload)
    return _UNROUTED


def _uri_invoke_route(effective_uri: str, *, project: str, db: str | None, config: str | None,
                      action_payload: dict, node_urls: list[str] | None, token: str | None,
                      identity: str | None):
    """Route a concrete (execute-mode, non-page) dashboard/scanner URI to its handler.

    Returns the handler's result, or None when the URI is not a built-in dashboard action (the
    caller then tries an in-process connector)."""
    if effective_uri in {"scanner://host/capture/command/run", "scanner://host/capture"}:
        return scanner_capture(project, db, action_payload)
    if effective_uri in {"scanner://host/best/command/finish", "scanner://host/best/finish"}:
        return scanner_best_finish(project, db, action_payload)
    if effective_uri in {"scanner://host/session/command/log", "scanner://host/session"}:
        return _scanner_session_impl(_scanner_bridge_deps(), db, action_payload)
    # Legacy alias: dashboard://host/phone-scanner/command/start → canonical start URI
    if effective_uri == "dashboard://host/phone-scanner/command/start":
        effective_uri = "dashboard://host/service/phone-scanner/command/start"
    lifecycle = _service_lifecycle_dispatch(effective_uri, project, db, config,
                                            node_urls, token, identity, action_payload)
    if lifecycle is not _UNROUTED:
        return lifecycle
    if effective_uri == "configured://host/node-api/command/request":
        return configured_node_api_request(config, node_urls, action_payload, uri=effective_uri)
    if effective_uri == "configured://host/node-api/query/status":
        return configured_node_api_request(config, node_urls, action_payload, uri=effective_uri, status_only=True)
    if effective_uri.startswith(("api://", "device://")):
        return configured_node_api_request(config, node_urls, action_payload, uri=effective_uri)
    if effective_uri in {"document://host/archive/command/sync-to-node", "document://host/archive/sync"}:
        return sync_documents_to_node(
            project,
            db,
            config,
            action_payload,
            node_urls=node_urls,
            token=token,
            identity=identity,
        )
    return _UNROUTED


def _uri_invoke_page_action(uri: str, mode: str, payload: dict, action_payload: dict, db: str | None) -> dict:
    """Enqueue a `layer=page` URI action for the scanner page (or reject if it must run locally)."""
    source = str(payload.get("source") or action_payload.get("source") or "").strip().lower()
    if source in {"page", "scanner-page"}:
        raise ValueError(f"page URI action must be handled locally by the scanner page: {uri}")
    return page_action_enqueue(
        db,
        target=str(action_payload.get("target") or "scanner"),
        uri=uri,
        payload=action_payload,
        mode=mode,
        source=str(payload.get("source") or "uri-invoke"),
    )


def _finalize_uri_result(result, uri: str) -> dict:
    """Annotate a handler result with invokedUri and the urirun.tag artifact class."""
    if isinstance(result, dict):
        result.setdefault("invokedUri", uri)
        # Surface the artifact/widget class when the result carries the urirun.tag contract.
        tag_class = _result_artifact_class(result)
        if tag_class is not None:
            result.setdefault("artifactClass", tag_class)
        return result
    return {"ok": True, "invokedUri": uri, "result": result}


def _uri_invoke_fallback(effective_uri: str, uri: str, *, config: str | None,
                         node_urls: list[str] | None, action_payload: dict, db: str | None) -> dict:
    """Unrouted URI: try an in-process connector, then a configured node-API, else raise."""
    dispatched = _run_inprocess_connector_uri(effective_uri, action_payload, db=db)
    if dispatched is not None:
        return dispatched
    if effective_uri.startswith(("media://", "camera://", "ssh://", "fs://")):
        configured = configured_node_api_request(config, node_urls, action_payload, uri=effective_uri)
        if configured.get("error") not in {"node is required", "configured API not found"}:
            return _finalize_uri_result(configured, uri)
    raise ValueError(f"unsupported URI action: {uri}")


def uri_invoke(
    project: str,
    db: str | None,
    config: str | None,
    payload: dict,
    *,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
) -> dict:
    uri = str(payload.get("uri") or "").strip()
    action_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    mode = _uri_mode(payload.get("mode") or payload.get("runMode") or action_payload.get("mode"))
    if not uri:
        raise ValueError("uri is required")
    action = _uri_action_lookup(uri)
    effective_uri = str(action.get("uri") if action else uri)

    if uri in {"scanner://host/actions/query/list", "dashboard://host/actions/query/list"}:
        return {"ok": True, "mode": mode, "actions": _uri_action_catalog(), "invokedUri": uri}

    if mode != "execute":
        return _uri_simulated_result(uri, mode, action_payload, action)

    if action and action.get("layer") == "page":
        return _uri_invoke_page_action(uri, mode, payload, action_payload, db)

    result = _uri_invoke_route(
        effective_uri, project=project, db=db, config=config, action_payload=action_payload,
        node_urls=node_urls, token=token, identity=identity,
    )
    if result is _UNROUTED:
        return _uri_invoke_fallback(effective_uri, uri, config=config, node_urls=node_urls,
                                    action_payload=action_payload, db=db)
    return _finalize_uri_result(result, uri)


from .dashboard_api import (  # noqa: E402,F401
    _first,
    _host_db,
    _mesh,
    _planfile_adapter,
    _host_config,
    _safe_tickets,
    _task_counts,
    _lan_qr_profile,
    chat_history,
    chat_delete_messages,
    task_create,
    _api_summary,
    _api_objects,
    _api_node_types,
    _api_tasks,
    _api_checks,
    _api_logs,
    _api_artifacts,
    _api_chat_history,
    _api_services_live,
    _api_scanner_live,
    _api_nodes_or_routes,
    _api_twin_flows,
    _api_twin_state,
    _API_ROUTES,
    _dashboard_api_response,
)


def _service_contacts() -> list[dict]:
    scanner_port = int(os.environ.get("URIRUN_PHONE_SCANNER_PORT", "8196"))
    scanner_state = _phone_scanner_external_status(scanner_port)
    service_entries: list[dict] = []
    with _SERVICE_LOCK:
        for service_id, server in _SERVICE_SERVERS.items():
            thread = _SERVICE_THREADS.get(service_id)
            service_entries.append({
                "service_id": service_id,
                "alive": bool(thread is not None and thread.is_alive()),
                "server_name": getattr(server, "server_name", ""),
            })
    return _service_contacts_impl(
        scanner_port=scanner_port,
        scanner_state=scanner_state,
        service_entries=service_entries,
        phone_scanner_url=_phone_scanner_url,
        phone_scanner_status=_phone_scanner_external_status,
    )


def summary(project: str, db: str | None, config: str | None, node_urls: list[str] | None = None) -> dict:
    tickets, task_error = _safe_tickets(project, sprint="all")
    host_db = _host_db()
    mesh = _mesh()
    try:
        discovered = mesh.discover_mesh(_host_config(config, node_urls))
    except Exception as exc:  # noqa: BLE001
        discovered = {"nodes": [], "routes": [], "serviceMap": {}, "error": str(exc)}
    checks = host_db.recent_checks(db, limit=10)
    artifacts = _public_artifacts(host_db.list_artifacts(db, limit=10), project)
    logs = host_db.recent_logs(db, limit=10)
    nodes = discovered.get("nodes") or []
    _annotate_node_tokens_impl(nodes, _node_token_for)
    _annotate_node_kinds(nodes)
    _annotate_node_types_impl(nodes)
    _merge_live_webpage_nodes(nodes)
    routes = discovered.get("routes") or []
    services = _service_contacts()
    host_routes = _host_registry_routes_impl(_uri_action_catalog())
    host = _host_object_impl(project, host_routes)
    objects = _uri_objects_impl(
        project=project,
        host_routes=host_routes,
        nodes=nodes,
        services=services,
        routes=routes,
    )
    return {
        "ok": True,
        "project": str(Path(project).expanduser().resolve()),
        "db": str(host_db.db_path(db)),
        "config": str(mesh.host_config_path(config)),
        "taskError": task_error,
        "taskCounts": _task_counts(tickets),
        "ticketCount": len(tickets),
        "nodeCount": len(nodes),
        "nodesOnline": len([node for node in nodes if node.get("reachable")]),
        "routeCount": len(routes),
        "serviceCount": len(services),
        "host": host,
        "hostRoutes": host_routes,
        "lan": _lan_qr_profile(),
        "nodeTypes": _node_type_profiles_impl(),
        "objects": objects,
        "nodes": nodes,
        "services": services,
        "routes": routes,
        "checks": checks,
        "artifacts": artifacts,
        "logs": logs,
    }


from .chat_orchestrator import chat_ask as _chat_ask_impl, ChatDeps


def node_add(config: str | None, payload: dict) -> dict:
    return _node_add_impl(config, payload, normalize_node_type=_normalize_node_type_impl, node_type_tags=_node_type_tags_impl)


def node_remove(config: str | None, payload: dict) -> dict:
    return _node_remove_impl(config, payload, forget_webpage=_node_forget_webpage)


def configured_node_api_request(config: str | None, node_urls: list[str] | None, payload: dict,
                                *, uri: str | None = None, status_only: bool = False) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    scheme, node_name, api_id, uri_status_only = _resolve_node_api_identifiers(payload, uri)
    status_only = status_only or uri_status_only
    if not node_name:
        return {"ok": False, "error": "node is required"}
    _hc = _host_config(config, node_urls)
    node, api, error = _configured_node_api_lookup_impl(_hc, node_name=node_name, api_id=api_id)
    if error or node is None or api is None:
        return {"ok": False, "error": error or "configured API not found"}
    safe_api = {k: v for k, v in api.items() if k != "auth"}
    if status_only:
        return {"ok": True, "node": node_name, "api": safe_api, "authConfigured": bool((api.get("auth") or {}).get("secretRef"))}
    if scheme in {"media", "camera", "ssh", "fs"}:
        return _connector_required_response(scheme, node_name, safe_api)
    return _configured_api_call(node, api, payload)


from .android_node import (
    android_node_service_url as _android_node_service_url,
    node_forget_webpage as _node_forget_webpage,
    start_android_node_service,
    restart_android_node_service as _restart_android_node_service_impl,
    merge_live_webpage_nodes as _merge_live_webpage_nodes_impl,
    phone_web_nodes,
)


def restart_android_node_service(payload: dict | None = None) -> dict:
    return _restart_android_node_service_impl(payload, free_port_fn=_free_port_from_matching_processes)


def _merge_live_webpage_nodes(nodes: list) -> None:
    """Wrapper so tests can monkeypatch host_dashboard.phone_web_nodes."""
    import urirun.host.android_node as _an
    _orig = _an.phone_web_nodes
    _an.phone_web_nodes = phone_web_nodes
    try:
        _merge_live_webpage_nodes_impl(nodes)
    finally:
        _an.phone_web_nodes = _orig


def phone_node_qr(project: str, db: str | None, payload: dict) -> dict:
    return _phone_node_qr_impl(
        project, db, payload,
        host_db_fn=_host_db,
        preview_url_fn=_preview_url,
        chat_message_fn=_chat_message,
        add_chat_message_fn=_add_chat_message,
    )


def _node_envelope_error(envelope: dict) -> str:
    return _node_envelope_error_impl(envelope)


def _probe_node_token(name: str, config: str | None, *, token: str | None = None,
                      identity: str | None = None, node_urls: list[str] | None = None,
                      timeout: float = 8.0) -> dict:
    return _probe_node_token_impl(
        name,
        node_url_fn=lambda n: _node_url_from_config(config, node_urls, n),
        token=token, identity=identity, timeout=timeout,
    )


def node_set_token(config: str | None, payload: dict, *, identity: str | None = None,
                   node_urls: list[str] | None = None) -> dict:
    return _node_set_token_impl(
        config, payload,
        node_url_fn=lambda n: _node_url_from_config(config, node_urls, n),
        identity=identity,
    )


def chat_ask(project: str, db: str | None, config: str | None, payload: dict, node_urls: list[str] | None = None,
             token: str | None = None, identity: str | None = None) -> dict:
    return _chat_ask_impl(project, db, config, payload, node_urls, token, identity, deps=ChatDeps(
        host_db_fn=_host_db,
        mesh_fn=_mesh,
        host_config_fn=_host_config,
        node_alias_map_fn=_node_alias_map_from_context,
        add_chat_message_fn=_add_chat_message,
        page_action_enqueue_fn=page_action_enqueue,
        ensure_phone_scanner_fn=ensure_phone_scanner_service,
        sync_documents_fn=sync_documents_to_node,
    ))


def task_action(project: str, ticket_id: str, action: str, payload: dict) -> dict:
    planfile_adapter = _planfile_adapter()
    if action == "start":
        ticket = planfile_adapter.start_ticket(project, ticket_id, assigned_to=payload.get("assigned_to"))
    elif action == "complete":
        ticket = planfile_adapter.complete_ticket(project, ticket_id, note=payload.get("note"), result=payload.get("result"), artifacts=payload.get("artifacts"))
    elif action == "block":
        ticket = planfile_adapter.update_ticket(project, ticket_id, {"status": "blocked", "description": str(payload.get("reason") or "Blocked from dashboard")})
    elif action == "ready":
        ticket = planfile_adapter.ready_ticket(project, ticket_id, note=payload.get("note"))
    elif action == "fail":
        ticket = planfile_adapter.fail_ticket(project, ticket_id, str(payload.get("error") or "failed from dashboard"))
    else:
        raise ValueError(f"unsupported task action: {action}")
    return {"ok": True, "ticket": ticket}







def connector_test(project: str, db: str | None, config: str | None, payload: dict, *,
                   node_urls: list[str] | None = None, token: str | None = None,
                   identity: str | None = None) -> dict:
    """Smoke-test a connector route on the host by really invoking it (mode=execute) through the
    same uri_invoke dispatch a chat/URI run uses. Use a read-only query route for a safe probe.
    Testing on a remote node/docker uses the dedicated /api/nodes/test-routes path instead."""
    payload = payload if isinstance(payload, dict) else {}
    uri = str(payload.get("uri") or "").strip()
    if not uri:
        return {"ok": False, "error": "test uri is required (e.g. uuid://host/id/query/v4)"}
    invoke_payload = {
        "uri": uri,
        "mode": payload.get("mode") or "execute",
        "payload": payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
        "source": "connector-test",
    }
    try:
        return uri_invoke(project, db, config, invoke_payload,
                          node_urls=node_urls, token=token, identity=identity)
    except Exception as exc:  # noqa: BLE001 - surface route/handler errors to the UI as a failed test
        return {"ok": False, "invokedUri": uri, "error": str(exc)}
def documents_reconcile(project: str, db: str | None, payload: dict | None = None) -> dict:
    """Prune document-index entries whose artifacts are gone from disk.

    Index-only and non-destructive: existing files are never touched. Returns the
    summary report from :func:`reconcile_document_index` and logs it.
    """
    result = reconcile_document_index()
    try:
        _host_db().add_log(db, "documents", "reconcile-index", result)
    except Exception:  # noqa: BLE001
        pass
    return result


def _handle_events_sse(handler, parsed):
    import queue
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    schemes = {s for s in (params.get("scheme", "").split(",")) if s}
    runs = {r for r in (params.get("run", "").split(",")) if r}
    last_id = _sse_initial_cursor(TWIN_EVENT_HUB, params, handler.headers)
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        handler.wfile.write(b": connected\n\n")
        for ev in TWIN_EVENT_HUB.replay_since(last_id):
            if _sse_event_matches(ev, schemes, runs):
                handler.wfile.write(_sse_frame(ev))
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return
    q = TWIN_EVENT_HUB.subscribe()
    try:
        while True:
            try:
                ev = q.get(timeout=15)
            except queue.Empty:
                handler.wfile.write(b": keep-alive\n\n")
                handler.wfile.flush()
                continue
            if _sse_event_matches(ev, schemes, runs):
                handler.wfile.write(_sse_frame(ev))
                handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        TWIN_EVENT_HUB.unsubscribe(q)


def create_handler(
    project: str,
    db: str | None = None,
    config: str | None = None,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
):
    class Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            _json_response(self, 200, {"ok": True})

        def do_GET(self):
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/health":
                    _json_response(self, 200, {"ok": True})
                    return
                if parsed.path == "/events":
                    _handle_events_sse(self, parsed)
                    return
                if parsed.path in {"/", "/index.html"}:
                    _html_response(self)
                    return
                if parsed.path == "/favicon.ico":
                    self.send_response(204)
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.end_headers()
                    return
                if parsed.path == "/scanner":
                    _html_response(self, SCANNER_HTML)
                    return
                if parsed.path in {"/docs/nodes", "/docs/nodes/"}:
                    _html_response(self, NODE_TYPES_DOC_HTML)
                    return
                if parsed.path in {"/docs/node-types", "/docs/node-types/"}:
                    _html_response(self, _docs_nodes_html())
                    return
                if parsed.path == "/api/nodes/phone-web":
                    _json_response(self, 200, phone_web_nodes(parse_qs(parsed.query)))
                    return
                if parsed.path == "/api/nodes/qr":
                    target = _first(parse_qs(parsed.query), "url") or ""
                    if not target:
                        _json_response(self, 400, {"ok": False, "error": "url is required"})
                        return
                    try:
                        digest = hashlib.sha256(target.encode("utf-8")).hexdigest()[:16]
                        root = Path(os.environ.get("URIRUN_DASHBOARD_QR_DIR", "~/.urirun/host-dashboard/qr")).expanduser()
                        qr_path = root / f"endpoint-{digest}.png"
                        if not qr_path.exists():
                            _write_qr_png(target, qr_path)
                        _asset_response(self, qr_path.read_bytes(), "image/png")
                    except Exception as exc:  # noqa: BLE001
                        _json_response(self, 500, {"ok": False, "error": str(exc)})
                    return
                if parsed.path == "/services/view":
                    _html_response(self, _service_widget_html(project, parse_qs(parsed.query)))
                    return
                if parsed.path == "/services/view.svg":
                    _asset_response(
                        self,
                        _service_widget_svg(project, parse_qs(parsed.query)).encode("utf-8"),
                        "image/svg+xml; charset=utf-8",
                    )
                    return
                if parsed.path == "/assets/urirun.js":
                    _js_sdk_response(self, project)
                    return
                if parsed.path in {"/twin", "/twin/"}:
                    widget = Path(__file__).parent / "twin_monitor_widget.html"
                    _asset_response(self, widget.read_bytes(), "text/html; charset=utf-8")
                    return
                if parsed.path == "/api/uri/event":
                    _json_response(self, 200, _uri_event_impl(_scanner_bridge_deps(), db, parse_qs(parsed.query)))
                    return
                if parsed.path == "/api/page/actions/poll":
                    query = parse_qs(parsed.query)
                    _json_response(
                        self,
                        200,
                        _page_action_poll_impl(_first(query, "target", "scanner") or "scanner", int(_first(query, "limit", "4") or 4)),
                    )
                    return
                if parsed.path == "/api/file":
                    path = _first(parse_qs(parsed.query), "path")
                    if not path:
                        _json_response(self, 400, {"ok": False, "error": "path is required"})
                        return
                    _file_response(self, unquote(path), project)
                    return
                status, payload = _dashboard_api_response(parsed.path, project, db, config, parse_qs(parsed.query), node_urls=node_urls)
                _json_response(self, status, payload)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return
            except Exception as exc:  # noqa: BLE001
                try:
                    _json_response(self, 500, {"ok": False, "error": str(exc)})
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return

        def do_POST(self):
            parsed = urlparse(self.path)
            parts = [part for part in parsed.path.split("/") if part]
            try:
                if parsed.path == "/api/tasks/create":
                    payload = _read_json(self)
                    _json_response(self, 200, task_create(project, payload))
                    return
                if parsed.path == "/api/connectors/install":
                    payload = _read_json(self)
                    _json_response(self, 200, _connector_install_impl(project, payload, config=config, node_urls=node_urls, token=token, identity=identity,
                                                                    node_url_from_config=_node_url_from_config, node_token_for=_node_token_for, node_client=_node_client))
                    return
                if parsed.path == "/api/connectors/docker-check":
                    payload = _read_json(self)
                    _json_response(self, 200, connector_env_check(payload))
                    return
                if parsed.path == "/api/connectors/test":
                    payload = _read_json(self)
                    _json_response(self, 200, connector_test(project, db, config, payload,
                                                             node_urls=node_urls, token=token, identity=identity))
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "tasks":
                    payload = _read_json(self)
                    _json_response(self, 200, task_action(project, parts[2], parts[3], payload))
                    return
                if parsed.path == "/api/chat/ask":
                    payload = _read_json(self)
                    _json_response(self, 200, chat_ask(project, db, config, payload, node_urls=node_urls,
                                                       token=token, identity=identity))
                    return
                if parsed.path == "/api/chat/messages/delete":
                    payload = _read_json(self)
                    _json_response(self, 200, chat_delete_messages(db, payload))
                    return
                if parsed.path == "/api/artifacts/delete":
                    payload = _read_json(self)
                    _json_response(self, 200, _artifacts_delete_impl(_host_db(), project, db, payload))
                    return
                if parsed.path == "/api/artifacts/dedupe":
                    payload = _read_json(self)
                    _json_response(self, 200, _artifacts_dedupe_rows_impl(_host_db(), project, db, payload))
                    return
                if parsed.path == "/api/artifacts/cleanup-orphans":
                    payload = _read_json(self)
                    _json_response(self, 200, _artifacts_cleanup_orphan_sidecars_impl(_host_db(), project, db, payload))
                    return
                if parsed.path == "/api/documents/reconcile":
                    payload = _read_json(self)
                    _json_response(self, 200, documents_reconcile(project, db, payload))
                    return
                if parsed.path == "/api/nodes/test-routes":
                    payload = _read_json(self)
                    _json_response(self, 200, node_test_routes(project, db, config, payload,
                                                               node_urls=node_urls, token=token, identity=identity))
                    return
                if parsed.path in {"/api/nodes/add", "/api/nodes/api/add"}:
                    payload = _read_json(self)
                    _json_response(self, 200, _node_add_impl(config, payload, normalize_node_type=_normalize_node_type_impl, node_type_tags=_node_type_tags_impl))
                    return
                if parsed.path in {"/api/nodes/remove", "/api/nodes/delete"}:
                    payload = _read_json(self)
                    _json_response(self, 200, _node_remove_impl(config, payload, forget_webpage=_node_forget_webpage))
                    return
                if parsed.path == "/api/nodes/api/request":
                    payload = _read_json(self)
                    _json_response(self, 200, configured_node_api_request(config, node_urls, payload))
                    return
                if parsed.path == "/api/nodes/phone-qr":
                    payload = _read_json(self)
                    _json_response(self, 200, phone_node_qr(project, db, payload))
                    return
                if parsed.path == "/api/nodes/phone-service/start":
                    payload = _read_json(self)
                    _json_response(self, 200, start_android_node_service(payload))
                    return
                if parsed.path == "/api/nodes/token":
                    payload = _read_json(self)
                    _json_response(self, 200, node_set_token(config, payload, identity=identity, node_urls=node_urls))
                    return
                if parsed.path == "/api/uri/invoke":
                    payload = _read_json(self)
                    if not payload.get("source"):
                        ref_path = urlparse(self.headers.get("Referer", "") or "").path
                        if ref_path == "/scanner":
                            payload["source"] = "scanner-page"
                    _json_response(
                        self,
                        200,
                        uri_invoke(project, db, config, payload, node_urls=node_urls, token=token, identity=identity),
                    )
                    return
                if parsed.path == "/api/page/actions/result":
                    payload = _read_json(self)
                    _json_response(self, 200, _page_action_result_impl(_scanner_bridge_deps(), db, payload, utc_now=_utc_now))
                    return
                if parsed.path == "/api/scanner/capture":
                    payload = _read_json(self)
                    _json_response(self, 200, scanner_capture(project, db, payload))
                    return
                if parsed.path == "/api/scanner/best/finish":
                    payload = _read_json(self)
                    _json_response(self, 200, scanner_best_finish(project, db, payload))
                    return
                if parsed.path == "/api/scanner/session":
                    payload = _read_json(self)
                    _json_response(self, 200, _scanner_session_impl(_scanner_bridge_deps(), db, payload))
                    return
                _json_response(self, 404, {"ok": False, "error": "not found"})
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return
            except Exception as exc:  # noqa: BLE001
                try:
                    _json_response(self, 400, {"ok": False, "error": str(exc)})
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return

        def log_message(self, fmt, *args: Any):
            return

    return Handler


def _free_port_from_matching_processes(
    port: int,
    *,
    force: bool,
    emit: bool,
    is_target: Any,
    event_prefix: str,
) -> dict:
    # Wrap is_target so it uses the patchable _process_cmdline global (monkeypatch-friendly).
    # All our is_target functions (is_scanner_process, is_chat_process, etc.) accept
    # process_cmdline_fn as a keyword argument.
    def _wrapped_is_target(pid: int) -> bool:
        return is_target(pid, process_cmdline_fn=_process_cmdline)

    return _free_port_from_matching_processes_impl(
        port,
        force=force,
        emit=emit,
        is_target=_wrapped_is_target,
        event_prefix=event_prefix,
        port_holder_pids_fn=_port_holder_pids,
        process_cmdline_fn=_process_cmdline,
        kill_fn=os.kill,
        getpid_fn=os.getpid,
        sleep_fn=time.sleep,
        time_fn=time.time,
        emit_fn=print,
    )


def _is_dashboard_process(pid: int) -> bool:
    """True only when pid is a urirun host dashboard serve process. Monkeypatch-friendly."""
    return _is_dashboard_process_impl(pid, process_cmdline_fn=_process_cmdline)


def _free_port_from_old_dashboard(port: int) -> None:
    """Before binding, terminate a previous dashboard instance still holding `port` so the new
    one can start cleanly. SAFETY: only kills processes whose cmdline is a urirun host
    dashboard serve — never an unrelated service that happens to own the port."""
    _free_port_from_old_dashboard_impl(
        port,
        is_dashboard_process_fn=_is_dashboard_process,
        port_holder_pids_fn=_port_holder_pids,
        kill_fn=os.kill,
        getpid_fn=os.getpid,
        sleep_fn=time.sleep,
        time_fn=time.time,
        emit_fn=print,
    )


# Patchable alias for process-type is_target function used by tests
_is_scanner_process = _is_scanner_process_impl
_is_chat_process = _is_chat_process_impl
_is_android_node_process = _is_android_node_process_impl


def _free_port_from_old_scanner(port: int, *, force: bool = False, emit: bool = False) -> dict:
    """Free a scanner-owned port before rebinding it."""
    return _free_port_from_matching_processes(
        port,
        force=force,
        emit=emit,
        is_target=_is_scanner_process,
        event_prefix="urirun.service_scanner",
    )


def _free_port_from_old_chat(port: int, *, force: bool = False, emit: bool = False) -> dict:
    """Free a chat-service-owned port before rebinding it."""
    return _free_port_from_matching_processes(
        port,
        force=force,
        emit=emit,
        is_target=_is_chat_process,
        event_prefix="urirun.service_chat",
    )


def _free_port_from_old_android_node(port: int, *, force: bool = False, emit: bool = False) -> dict:
    """Free an android-node-service-owned port before rebinding it."""
    return _free_port_from_matching_processes(
        port,
        force=force,
        emit=emit,
        is_target=_is_android_node_process,
        event_prefix="urirun.service_android_node",
    )


def serve(
    project: str = ".",
    db: str | None = None,
    config: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8194,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
    tls_cert: str | None = None,
    tls_key: str | None = None,
    startup_qr: bool = False,
    qr_url: str | None = None,
) -> ThreadingHTTPServer:
    # Load `<project>/.env` so the in-process NL planner sees LLM_MODEL / OPENROUTER_API_KEY
    # without the launcher having to `set -a; . .env`. The real environment always wins
    # (the file never clobbers an already-set variable), mirroring `host ask`.
    from urirun.node.mesh import _maybe_load_dotenv
    loaded_env = _maybe_load_dotenv(os.path.join(os.path.expanduser(project), ".env"))
    if loaded_env:
        print(json.dumps({
            "event": "urirun.host_dashboard.dotenv_loaded",
            "keys": sorted(loaded_env),
        }), flush=True)
    # Starting a new dashboard auto-replaces the old one holding this port (parent+worker), so
    # `serve` never dies on "Address already in use".
    _free_port_from_old_dashboard(int(port))
    server = ThreadingHTTPServer((host, port), create_handler(project, db=db, config=config, node_urls=node_urls,
                                                             token=token, identity=identity))
    scheme = "http"
    if tls_cert and tls_key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(os.path.expanduser(tls_cert), os.path.expanduser(tls_key))
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    qr = startup_phone_qr(project, db, scheme=scheme, host=host, port=server.server_address[1], qr_url=qr_url) if startup_qr else None
    print(json.dumps({
        "event": "urirun.host_dashboard.started",
        "url": f"{scheme}://{host}:{server.server_address[1]}/",
        "qrUrl": qr.get("url") if qr else None,
        "project": str(Path(project).resolve()),
    }), flush=True)
    return server


def command(args) -> int:
    if args.dashboard_command == "serve":
        host = args.host or "127.0.0.1"
        port = int(args.port or 8194)
        startup_qr = bool(getattr(args, "startup_qr", False)) and not bool(getattr(args, "no_startup_qr", False))
        server = serve(project=args.project, db=args.db, config=args.config, host=host, port=port,
                       node_urls=getattr(args, "node_url", None),
                       token=getattr(args, "token", None) or os.environ.get("URIRUN_NODE_TOKEN"),
                       identity=getattr(args, "identity", None),
                       tls_cert=getattr(args, "tls_cert", None),
                       tls_key=getattr(args, "tls_key", None),
                       startup_qr=startup_qr,
                       qr_url=getattr(args, "qr_url", None))
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return 130
        return 0
    if args.dashboard_command == "url":
        host = args.host or "127.0.0.1"
        port = int(args.port or 8194)
        print(f"http://{host}:{port}/")
        return 0
    return 1


def default_host() -> str:
    return socket.gethostbyname(socket.gethostname())
