from __future__ import annotations

from typing import Any


def verification_check(name: str, *, ok: bool, expected: int, actual: int, **meta: Any) -> dict[str, Any]:
    """Build one normalized verification check row for URI side-effect contracts."""
    row: dict[str, Any] = {
        "check": name,
        "ok": bool(ok),
        "expected": int(expected),
        "actual": int(actual),
    }
    row.update({key: value for key, value in meta.items() if value is not None})
    return row


def file_transfer_verification(
    *,
    contract: str,
    expected: list[str],
    uploaded: list[str],
    verified: list[str],
    mode: str,
    missing_limit: int = 50,
) -> dict[str, Any]:
    """Return the standard verification contract for file-copy style URI flows.

    `uploaded` means the remote write acknowledged the file. `verified` means the
    final contract check passed, usually a read-back sha256 or a trusted write sha.
    """
    expected_set = list(expected)
    uploaded_set = set(uploaded)
    verified_set = set(verified)
    missing = [rel for rel in expected_set if rel not in verified_set]
    checks = [
        verification_check(
            "write_ack_for_every_expected_file",
            ok=len(uploaded_set) == len(expected_set),
            expected=len(expected_set),
            actual=len(uploaded_set),
        ),
        verification_check(
            "sha256_verified_for_every_expected_file",
            ok=len(verified_set) == len(expected_set),
            expected=len(expected_set),
            actual=len(verified_set),
            mode=mode,
        ),
    ]
    return {
        "contract": contract,
        "ok": all(check["ok"] for check in checks),
        "mode": mode,
        "expectedFiles": len(expected_set),
        "uploadedFiles": len(uploaded_set),
        "verifiedFiles": len(verified_set),
        "failedFiles": len(missing),
        "missing": missing[:missing_limit],
        "truncatedMissing": max(0, len(missing) - missing_limit),
        "checks": checks,
    }
