from urirun.host.contracts import file_transfer_verification


def test_file_transfer_verification_reports_missing_files() -> None:
    result = file_transfer_verification(
        contract="example-sync.v1",
        expected=["2026-03/a.pdf", "2026-03/b.pdf", "2026-04/c.pdf"],
        uploaded=["2026-03/a.pdf", "2026-03/b.pdf"],
        verified=["2026-03/a.pdf"],
        mode="read-back-sha256",
    )

    assert result["contract"] == "example-sync.v1"
    assert result["ok"] is False
    assert result["expectedFiles"] == 3
    assert result["uploadedFiles"] == 2
    assert result["verifiedFiles"] == 1
    assert result["failedFiles"] == 2
    assert result["missing"] == ["2026-03/b.pdf", "2026-04/c.pdf"]
    assert result["checks"] == [
        {
            "check": "write_ack_for_every_expected_file",
            "ok": False,
            "expected": 3,
            "actual": 2,
        },
        {
            "check": "sha256_verified_for_every_expected_file",
            "ok": False,
            "expected": 3,
            "actual": 1,
            "mode": "read-back-sha256",
        },
    ]


def test_file_transfer_verification_accepts_complete_transfer() -> None:
    result = file_transfer_verification(
        contract="example-sync.v1",
        expected=["a.pdf"],
        uploaded=["a.pdf"],
        verified=["a.pdf"],
        mode="write-ack-sha256",
    )

    assert result["ok"] is True
    assert result["failedFiles"] == 0
    assert result["missing"] == []
