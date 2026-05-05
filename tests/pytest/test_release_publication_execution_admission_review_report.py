import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validator_script() -> Path:
    return (
        _repo_root()
        / "tools"
        / "release-publication-execution-admission-review"
        / "validate_release_publication_execution_admission_review_report.py"
    )


def _report_path(name: str) -> Path:
    return _repo_root() / "examples" / "release-publication-execution-admission-review" / name


def _run_validator(report_path: Path, allow_warn: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(_validator_script()), str(report_path)]
    if allow_warn:
        cmd.append("--allow-warn")
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))


def _extract_payload(stdout: str) -> dict:
    start = stdout.find("{")
    assert start >= 0, f"Validator stdout did not include JSON payload:\n{stdout}"
    return json.loads(stdout[start:])


def _load_pass() -> dict:
    return json.loads(
        _report_path("max_biped_v1_release_publication_execution_admission_review_pass.json").read_text(
            encoding="utf-8-sig"
        )
    )


def test_pass_report_returns_pass_and_exit_zero():
    result = _run_validator(
        _report_path("max_biped_v1_release_publication_execution_admission_review_pass.json")
    )
    assert result.returncode == 0, f"Unexpected failure:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "pass"


def test_warn_report_returns_warn_and_exit_zero_with_allow_warn():
    result = _run_validator(
        _report_path("max_biped_v1_release_publication_execution_admission_review_warn.json"),
        allow_warn=True,
    )
    assert result.returncode == 0, f"Warn should pass with --allow-warn:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_warn_report_returns_nonzero_without_allow_warn():
    result = _run_validator(
        _report_path("max_biped_v1_release_publication_execution_admission_review_warn.json"),
        allow_warn=False,
    )
    assert result.returncode != 0, "Warn should return nonzero without --allow-warn"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_fail_report_returns_fail_and_nonzero():
    result = _run_validator(
        _report_path("max_biped_v1_release_publication_execution_admission_review_fail.json")
    )
    assert result.returncode != 0, "Fail report must return nonzero"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "fail"


def test_missing_required_report_artifact_hash_fails(tmp_path: Path):
    report = _load_pass()
    report["status"] = "fail"
    report["execution_admission_review"]["admission_review_verification_status"] = "fail"
    report["execution_admission_review"]["admission_review_artifact_hashes"].pop(
        "release_publication_execution_receipt", None
    )
    report["execution_admission_review"]["artifact_count"] = len(
        report["execution_admission_review"]["admission_review_artifact_hashes"]
    )
    report["execution_admission_review"]["missing_admission_review_artifact_ids"] = [
        "release_publication_execution_receipt"
    ]
    report["approval_state"]["decision"] = "rejected"
    report["approval_state"]["blocked_reason_codes"] = ["missing_report_artifact_hash"]
    report["readiness"]["present_gate_ids"] = ["max_biped_v1_skeleton_contract"]
    report["readiness"]["missing_gate_ids"] = sorted(
        list(
            set(report["readiness"]["required_gate_ids"])
            - set(report["readiness"]["present_gate_ids"])
        )
    )
    report["readiness"]["execution_admission_review_readiness_state"] = "blocked_missing_evidence"
    test_file = tmp_path / "missing-report-artifact-hash.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(
        item.get("id") == "required_admission_review_artifacts_missing"
        for item in payload["findings"]
    )


def test_unsafe_admission_review_path_fails(tmp_path: Path):
    report = _load_pass()
    report["status"] = "fail"
    report["execution_admission_review"]["admission_review_verification_status"] = "fail"
    report["execution_admission_review"]["admission_review_path"] = "..\\outside\\audit-bundle.json"
    report["approval_state"]["decision"] = "rejected"
    report["approval_state"]["blocked_reason_codes"] = ["unsafe_bundle_path"]
    report["readiness"]["execution_admission_review_readiness_state"] = "blocked_safety_boundary"
    test_file = tmp_path / "unsafe-audit-bundle-path.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "admission_review_path_unsafe" for item in payload["findings"])


def test_publish_execution_admitted_true_fails(tmp_path: Path):
    report = _load_pass()
    report["status"] = "fail"
    report["execution_admission_review"]["admission_review_verification_status"] = "fail"
    report["approval_state"]["decision"] = "rejected"
    report["approval_state"]["publish_execution_admitted"] = True
    report["approval_state"]["blocked_reason_codes"] = ["publish_admission_not_allowed"]
    report["readiness"]["execution_admission_review_readiness_state"] = "blocked_safety_boundary"
    test_file = tmp_path / "publish-admitted-true.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(
        item.get("id") == "publish_execution_admitted_must_be_false"
        for item in payload["findings"]
    )


def test_source_execution_admission_request_reference_must_point_to_admission_request_packet(tmp_path: Path):
    report = _load_pass()
    report["status"] = "fail"
    report["execution_admission_review"]["admission_review_verification_status"] = "fail"
    report["execution_admission_review"]["source_execution_admission_request_packet_id"] = (
        "ready-for-execution-request-20260505-0001"
    )
    report["execution_admission_review"]["source_execution_admission_request_packet_path"] = (
        "evidence/jobs/job-maxine-release-001/qc/release-publication-ready-for-execution-request-report.json"
    )
    report["approval_state"]["decision"] = "rejected"
    report["approval_state"]["blocked_reason_codes"] = ["invalid_source_admission_request_reference"]
    report["readiness"]["execution_admission_review_readiness_state"] = "blocked_safety_boundary"
    test_file = tmp_path / "invalid-source-admission-request-reference.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "source_execution_admission_request_packet_id_invalid" for item in payload["findings"])


def test_required_execution_admission_request_packet_gate_must_be_declared(tmp_path: Path):
    report = _load_pass()
    report["status"] = "fail"
    report["execution_admission_review"]["admission_review_verification_status"] = "fail"
    report["readiness_contract"]["required_gate_ids"] = [
        x for x in report["readiness_contract"]["required_gate_ids"] if x != "release_publication_execution_admission_request_packet_v1"
    ]
    report["approval_state"]["decision"] = "rejected"
    report["approval_state"]["blocked_reason_codes"] = ["missing_required_execution_admission_request_packet_gate"]
    report["readiness"]["execution_admission_review_readiness_state"] = "blocked_safety_boundary"
    test_file = tmp_path / "missing-required-execution-admission-request-packet-gate.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "required_execution_admission_request_packet_gate_missing" for item in payload["findings"])


def test_output_contains_manifest_attachable_qc_payload():
    result = _run_validator(
        _report_path("max_biped_v1_release_publication_execution_admission_review_pass.json")
    )
    payload = _extract_payload(result.stdout)
    attachment = payload.get("manifest_attachment", {})
    qc_check = attachment.get("qc_check", {})
    assert qc_check.get("check_id") == "release_publication_execution_admission_review_v1"


def test_output_target_path_is_qc_gates():
    result = _run_validator(
        _report_path("max_biped_v1_release_publication_execution_admission_review_pass.json")
    )
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["target_path"] == "qc.gates[]"


def test_output_future_target_path_is_qc_checks():
    result = _run_validator(
        _report_path("max_biped_v1_release_publication_execution_admission_review_pass.json")
    )
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["future_target_path"] == "qc.checks[]"

