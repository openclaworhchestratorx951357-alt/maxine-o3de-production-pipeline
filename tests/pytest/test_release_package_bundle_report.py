import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validator_script() -> Path:
    return _repo_root() / "tools" / "release-package-bundle" / "validate_release_package_bundle_report.py"


def _report_path(name: str) -> Path:
    return _repo_root() / "examples" / "release-package-bundle" / name


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
    result = _run_validator(_report_path("max_biped_v1_release_package_bundle_pass.json"))
    assert result.returncode == 0, f"Unexpected failure:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "pass"


def test_warn_report_returns_warn_and_exit_zero_with_allow_warn():
    result = _run_validator(_report_path("max_biped_v1_release_package_bundle_warn.json"), allow_warn=True)
    assert result.returncode == 0, f"Warn should pass with --allow-warn:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_warn_report_returns_nonzero_without_allow_warn():
    result = _run_validator(_report_path("max_biped_v1_release_package_bundle_warn.json"), allow_warn=False)
    assert result.returncode != 0, "Warn should return nonzero without --allow-warn"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_fail_report_returns_fail_and_nonzero():
    result = _run_validator(_report_path("max_biped_v1_release_package_bundle_fail.json"))
    assert result.returncode != 0, "Fail report must return nonzero"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "fail"


def test_missing_required_bundle_path_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_release_package_bundle_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["bundle_inventory"]["included_paths"] = [
        "artifacts/jobs/job-release-package-pass-001/release-bundle/manifest.json"
    ]
    report["bundle_inventory"]["missing_paths"] = [
        "artifacts/jobs/job-release-package-pass-001/release-bundle/artifact-index.json",
        "artifacts/jobs/job-release-package-pass-001/release-bundle/undo/rollback-plan.json",
        "artifacts/jobs/job-release-package-pass-001/release-bundle/cleanup/cleanup-plan.json"
    ]
    report["release_readiness"]["readiness_state"] = "blocked_missing_evidence"
    test_file = tmp_path / "missing-bundle-paths.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "required_bundle_paths_missing" for item in payload["findings"])


def test_missing_rollback_instructions_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_release_package_bundle_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["rollback"]["undo_available"] = False
    report["rollback"]["rollback_step_count"] = 0
    report["rollback"]["rollback_instruction_paths"] = []
    report["rollback"]["cleanup_step_count"] = 0
    report["rollback"]["cleanup_instruction_paths"] = []
    report["release_readiness"]["readiness_state"] = "blocked_missing_evidence"
    test_file = tmp_path / "missing-rollback-instructions.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    ids = {item.get("id") for item in payload["findings"]}
    assert "undo_not_available" in ids
    assert "rollback_instructions_missing" in ids


def test_disallowed_bundle_path_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_release_package_bundle_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["bundle_inventory"]["disallowed_paths"] = [
        "artifacts/jobs/job-release-package-pass-001/release-bundle/cache/assetdb.sqlite"
    ]
    report["release_readiness"]["readiness_state"] = "blocked_safety_boundary"
    test_file = tmp_path / "disallowed-bundle-path.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "disallowed_paths_present" for item in payload["findings"])


def test_output_contains_manifest_attachable_qc_payload():
    result = _run_validator(_report_path("max_biped_v1_release_package_bundle_pass.json"))
    payload = _extract_payload(result.stdout)
    attachment = payload.get("manifest_attachment", {})
    qc_check = attachment.get("qc_check", {})
    assert qc_check.get("check_id") == "release_package_bundle_v1"


def test_output_target_path_is_qc_gates():
    result = _run_validator(_report_path("max_biped_v1_release_package_bundle_pass.json"))
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["target_path"] == "qc.gates[]"


def test_output_future_target_path_is_qc_checks():
    result = _run_validator(_report_path("max_biped_v1_release_package_bundle_pass.json"))
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["future_target_path"] == "qc.checks[]"
