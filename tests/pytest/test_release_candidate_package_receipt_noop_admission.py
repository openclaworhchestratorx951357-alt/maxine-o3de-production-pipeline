import json
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _generator_script() -> Path:
    return (
        _repo_root()
        / "tools"
        / "execution-admission"
        / "generate_release_candidate_package_receipt_noop.py"
    )


def _validator_script() -> Path:
    return (
        _repo_root()
        / "tools"
        / "execution-admission"
        / "validate_release_candidate_package_receipt_noop_report.py"
    )


def _decision_record() -> Path:
    return (
        _repo_root()
        / "examples"
        / "execution-admission"
        / "release_candidate_package_receipt_noop_execution_admission_decision_approved.json"
    )


def _package_report() -> Path:
    return (
        _repo_root()
        / "examples"
        / "real-pilot-release-candidate-package"
        / "max_biped_v1_real_pilot_release_candidate_package_pass.json"
    )


def _extract_payload(stdout: str) -> dict:
    start = stdout.find("{")
    assert start >= 0, f"stdout did not include JSON payload:\n{stdout}"
    return json.loads(stdout[start:])


@pytest.fixture()
def sandbox_output_dir() -> Path:
    base = (
        _repo_root()
        / "examples"
        / "sandbox"
        / "execution-receipts"
        / "release-candidate-package-receipt-noop"
        / "_pytest"
    )
    run_dir = base / uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_generator_passes_and_writes_receipt_under_approved_path(sandbox_output_dir: Path):
    output_path = sandbox_output_dir / "receipt.json"
    cmd = [
        sys.executable,
        str(_generator_script()),
        "--decision-record",
        str(_decision_record()),
        "--release-candidate-package-report",
        str(_package_report()),
        "--output",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "pass"
    assert payload["candidate_id"] == "release_candidate_package_receipt_noop_v1"
    assert payload["approval_phrase"] == "APPROVE EXECUTION ADMISSION release_candidate_package_receipt_noop_v1"
    assert payload["command_mode"] == "noop"
    assert payload["external_execution_performed"] is False
    assert payload["publication_performed"] is False
    assert payload["manifest_attachment"]["qc_check"]["check_id"] == "release_candidate_package_receipt_noop_v1"
    assert output_path.exists()
    assert "examples/sandbox/execution-receipts/release-candidate-package-receipt-noop/" in str(
        output_path.as_posix()
    )


def test_generator_fails_when_approval_phrase_is_missing(sandbox_output_dir: Path):
    bad_decision = json.loads(_decision_record().read_text(encoding="utf-8-sig"))
    bad_decision["approval"]["approval_received"] = False
    bad_decision["approval"]["approval_phrase_received"] = ""
    decision_path = sandbox_output_dir / "decision-missing-approval.json"
    decision_path.write_text(json.dumps(bad_decision, indent=2) + "\n", encoding="utf-8")

    output_path = sandbox_output_dir / "receipt-fail-approval.json"
    cmd = [
        sys.executable,
        str(_generator_script()),
        "--decision-record",
        str(decision_path),
        "--release-candidate-package-report",
        str(_package_report()),
        "--output",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))
    assert result.returncode != 0
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "fail"
    finding_ids = {item["id"] for item in payload["findings"]}
    assert "operator_approval_missing" in finding_ids
    assert "approval_phrase_mismatch" in finding_ids


def test_generator_fails_for_wrong_candidate_id(sandbox_output_dir: Path):
    bad_decision = json.loads(_decision_record().read_text(encoding="utf-8-sig"))
    bad_decision["candidate_id"] = "wrong_candidate"
    bad_decision["approval"]["approval_phrase_received"] = "APPROVE EXECUTION ADMISSION wrong_candidate"
    decision_path = sandbox_output_dir / "decision-wrong-candidate.json"
    decision_path.write_text(json.dumps(bad_decision, indent=2) + "\n", encoding="utf-8")

    output_path = sandbox_output_dir / "receipt-fail-candidate.json"
    cmd = [
        sys.executable,
        str(_generator_script()),
        "--decision-record",
        str(decision_path),
        "--release-candidate-package-report",
        str(_package_report()),
        "--output",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))
    assert result.returncode != 0
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "fail"
    finding_ids = {item["id"] for item in payload["findings"]}
    assert "candidate_id_mismatch" in finding_ids


def test_generator_rejects_output_outside_approved_receipt_root(tmp_path: Path):
    output_path = tmp_path / "outside-approved-path.json"
    cmd = [
        sys.executable,
        str(_generator_script()),
        "--decision-record",
        str(_decision_record()),
        "--release-candidate-package-report",
        str(_package_report()),
        "--output",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))
    assert result.returncode != 0
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "fail"
    assert any(item["id"] == "receipt_generation_failed" for item in payload["findings"])


def test_validator_fails_for_false_execution_or_publication_claims(sandbox_output_dir: Path):
    output_path = sandbox_output_dir / "receipt.json"
    gen_cmd = [
        sys.executable,
        str(_generator_script()),
        "--decision-record",
        str(_decision_record()),
        "--release-candidate-package-report",
        str(_package_report()),
        "--output",
        str(output_path),
    ]
    gen_result = subprocess.run(gen_cmd, capture_output=True, text=True, cwd=str(_repo_root()))
    assert gen_result.returncode == 0, f"{gen_result.stdout}\n{gen_result.stderr}"

    payload = json.loads(output_path.read_text(encoding="utf-8-sig"))
    payload["external_execution_performed"] = True
    payload["publication_performed"] = True
    payload["source_uuid_claim_status"] = "authoritative"
    payload["spawn_publish_status"] = "admitted"
    bad_report = sandbox_output_dir / "receipt-invalid-claims.json"
    bad_report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    val_cmd = [sys.executable, str(_validator_script()), str(bad_report)]
    val_result = subprocess.run(val_cmd, capture_output=True, text=True, cwd=str(_repo_root()))
    assert val_result.returncode != 0
    val_payload = _extract_payload(val_result.stdout)
    assert val_payload["status"] == "fail"
    finding_ids = {item["id"] for item in val_payload["findings"]}
    assert "external_execution_not_allowed" in finding_ids
    assert "publication_not_allowed" in finding_ids
    assert "authoritative_claim_not_allowed" in finding_ids
    assert "blocked_surface_widened" in finding_ids
