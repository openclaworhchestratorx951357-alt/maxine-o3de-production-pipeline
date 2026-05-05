import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validator_script() -> Path:
    return _repo_root() / "tools" / "ci-artifact-retention" / "validate_ci_artifact_retention_report.py"


def _report_path(name: str) -> Path:
    return _repo_root() / "examples" / "ci-artifact-retention" / name


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
    result = _run_validator(_report_path("max_biped_v1_ci_artifact_retention_pass.json"))
    assert result.returncode == 0, f"Unexpected failure:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "pass"


def test_warn_report_returns_warn_and_exit_zero_with_allow_warn():
    result = _run_validator(_report_path("max_biped_v1_ci_artifact_retention_warn.json"), allow_warn=True)
    assert result.returncode == 0, f"Warn should pass with --allow-warn:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_warn_report_returns_nonzero_without_allow_warn():
    result = _run_validator(_report_path("max_biped_v1_ci_artifact_retention_warn.json"), allow_warn=False)
    assert result.returncode != 0, "Warn should return nonzero without --allow-warn"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_fail_report_returns_fail_and_nonzero():
    result = _run_validator(_report_path("max_biped_v1_ci_artifact_retention_fail.json"))
    assert result.returncode != 0, "Fail report must return nonzero"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "fail"


def test_missing_required_artifacts_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_ci_artifact_retention_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["artifact_inventory"]["present_artifact_paths"] = [
        "artifacts/jobs/job-release-character-retention-pass-001/manifest.json"
    ]
    report["artifact_inventory"]["missing_artifacts"] = [
        "artifacts/jobs/job-release-character-retention-pass-001/logs/pipeline.log"
    ]
    test_file = tmp_path / "missing-artifacts.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "required_artifacts_missing" for item in payload["findings"])


def test_retention_below_required_days_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_ci_artifact_retention_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["retention_policy"]["actual_retention_days"] = 120
    test_file = tmp_path / "retention-too-short.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "retention_below_required_days" for item in payload["findings"])


def test_missing_qc_gates_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_ci_artifact_retention_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["release_validation"]["present_qc_gate_ids"] = ["manual_hero_review_v1"]
    report["release_validation"]["missing_qc_gate_ids"] = [
        "max_biped_v1_skeleton_contract",
        "dcc_conform_v1",
        "material_uv_qc_v1",
        "animation_smoke_v1",
        "screenshot_evidence_v1"
    ]
    report["release_validation"]["release_readiness_state"] = "blocked_missing_evidence"
    test_file = tmp_path / "missing-qc-gates.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "required_qc_gates_missing" for item in payload["findings"])


def test_disallowed_artifact_path_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_ci_artifact_retention_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["artifact_inventory"]["disallowed_artifact_paths"] = [
        "artifacts/jobs/job-release-character-retention-pass-001/cache/assetdb.sqlite"
    ]
    test_file = tmp_path / "disallowed-artifact.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "disallowed_artifacts_present" for item in payload["findings"])


def test_output_contains_manifest_attachable_qc_payload():
    result = _run_validator(_report_path("max_biped_v1_ci_artifact_retention_pass.json"))
    payload = _extract_payload(result.stdout)
    attachment = payload.get("manifest_attachment", {})
    qc_check = attachment.get("qc_check", {})
    assert qc_check.get("check_id") == "ci_artifact_retention_v1"


def test_output_target_path_is_qc_gates():
    result = _run_validator(_report_path("max_biped_v1_ci_artifact_retention_pass.json"))
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["target_path"] == "qc.gates[]"


def test_output_future_target_path_is_qc_checks():
    result = _run_validator(_report_path("max_biped_v1_ci_artifact_retention_pass.json"))
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["future_target_path"] == "qc.checks[]"
