import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validator_script() -> Path:
    return _repo_root() / "tools" / "release-publication-execution-request-ledger" / "validate_release_publication_execution_request_ledger_report.py"


def _report_path(name: str) -> Path:
    return _repo_root() / "examples" / "release-publication-execution-request-ledger" / name


def _run_validator(report_path: Path, allow_warn: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(_validator_script()), str(report_path)]
    if allow_warn:
        cmd.append("--allow-warn")
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))


def _extract_payload(stdout: str) -> dict:
    start = stdout.find("{")
    assert start >= 0, f"Validator stdout did not include JSON payload:\n{stdout}"
    return json.loads(stdout[start:])


def test_pass_report_returns_pass_and_exit_zero():
    result = _run_validator(_report_path("max_biped_v1_release_publication_execution_request_ledger_pass.json"))
    assert result.returncode == 0, f"Unexpected failure:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "pass"


def test_warn_report_returns_warn_and_exit_zero_with_allow_warn():
    result = _run_validator(_report_path("max_biped_v1_release_publication_execution_request_ledger_warn.json"), allow_warn=True)
    assert result.returncode == 0, f"Warn should pass with --allow-warn:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_warn_report_returns_nonzero_without_allow_warn():
    result = _run_validator(_report_path("max_biped_v1_release_publication_execution_request_ledger_warn.json"), allow_warn=False)
    assert result.returncode != 0, "Warn should return nonzero without --allow-warn"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_fail_report_returns_fail_and_nonzero():
    result = _run_validator(_report_path("max_biped_v1_release_publication_execution_request_ledger_fail.json"))
    assert result.returncode != 0, "Fail report must return nonzero"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "fail"


def test_missing_required_gates_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_release_publication_execution_request_ledger_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["readiness"]["present_gate_ids"] = ["max_biped_v1_skeleton_contract", "release_promotion_decision_v1"]
    report["readiness"]["missing_gate_ids"] = [
        "dcc_conform_v1",
        "material_uv_qc_v1",
        "animation_smoke_v1",
        "screenshot_evidence_v1",
        "manual_hero_review_v1",
        "ci_artifact_retention_v1",
        "release_package_bundle_v1",
        "release_publication_preflight_v1",
        "release_publication_request_approval_v1",
        "release_publication_execution_admission_gate_v1"
    ]
    report["readiness"]["release_readiness_state"] = "blocked_missing_evidence"
    test_file = tmp_path / "missing-gates.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "required_gates_missing" for item in payload["findings"])


def test_insufficient_approvals_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_release_publication_execution_request_ledger_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["approval_state"]["approver_ids"] = ["ops.release_lead"]
    test_file = tmp_path / "insufficient-approvals.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "insufficient_approvals" for item in payload["findings"])


def test_pending_decision_returns_pending_manual(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_release_publication_execution_request_ledger_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "pending_manual"
    report["approval_state"]["decision"] = "pending_manual_review"
    report["approval_state"]["approver_ids"] = []
    report["approval_state"]["blocked_reason_codes"] = ["waiting_manual_review"]
    test_file = tmp_path / "pending-decision.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "pending_manual"
    assert any(item.get("id") == "request_ledger_pending_manual_review" for item in payload["findings"])


def test_unsafe_publish_command_token_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_release_publication_execution_request_ledger_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["execution_request_ledger"]["publish_command_display"] = "DisplayOnly Execution Request: release_bundle publish --manifest a.json | invoke-expression"
    report["readiness"]["release_readiness_state"] = "blocked_safety_boundary"
    test_file = tmp_path / "unsafe-command.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "publish_command_display_unsafe" for item in payload["findings"])


def test_publish_execution_admitted_true_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_release_publication_execution_request_ledger_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["approval_state"]["publish_execution_admitted"] = True
    report["readiness"]["release_readiness_state"] = "blocked_safety_boundary"
    test_file = tmp_path / "publish-admitted-true.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "publish_execution_admitted_must_be_false" for item in payload["findings"])


def test_output_contains_manifest_attachable_qc_payload():
    result = _run_validator(_report_path("max_biped_v1_release_publication_execution_request_ledger_pass.json"))
    payload = _extract_payload(result.stdout)
    attachment = payload.get("manifest_attachment", {})
    qc_check = attachment.get("qc_check", {})
    assert qc_check.get("check_id") == "release_publication_execution_request_ledger_v1"


def test_output_target_path_is_qc_gates():
    result = _run_validator(_report_path("max_biped_v1_release_publication_execution_request_ledger_pass.json"))
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["target_path"] == "qc.gates[]"


def test_output_future_target_path_is_qc_checks():
    result = _run_validator(_report_path("max_biped_v1_release_publication_execution_request_ledger_pass.json"))
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["future_target_path"] == "qc.checks[]"
