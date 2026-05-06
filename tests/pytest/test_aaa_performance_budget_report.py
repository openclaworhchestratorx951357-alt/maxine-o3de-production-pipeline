import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validator_script() -> Path:
    return _repo_root() / "tools" / "aaa-performance-budget" / "validate_aaa_performance_budget_report.py"


def _report_path(name: str) -> Path:
    return _repo_root() / "examples" / "aaa-performance-budget" / name


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
    result = _run_validator(_report_path("max_biped_v1_aaa_performance_budget_pass.json"))
    assert result.returncode == 0, f"Unexpected failure:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "pass"


def test_warn_report_returns_nonzero_without_allow_warn():
    result = _run_validator(_report_path("max_biped_v1_aaa_performance_budget_warn.json"))
    assert result.returncode != 0, "warn should return nonzero without --allow-warn"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_warn_report_returns_zero_with_allow_warn():
    result = _run_validator(_report_path("max_biped_v1_aaa_performance_budget_warn.json"), allow_warn=True)
    assert result.returncode == 0, f"Unexpected failure:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_fail_report_returns_fail_and_nonzero():
    result = _run_validator(_report_path("max_biped_v1_aaa_performance_budget_fail.json"))
    assert result.returncode != 0, "Fail report must return nonzero"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "fail"


def test_missing_required_metric_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_aaa_performance_budget_pass.json").read_text(encoding="utf-8-sig"))
    del report["triangle_count"]
    report["status"] = "fail"
    report["triangle_budget_status"] = "fail"
    test_file = tmp_path / "missing-triangle-count.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    finding_ids = {str(item.get("id", "")).strip() for item in payload["findings"]}
    assert "schema_validation_error" in finding_ids or "triangle_count_invalid" in finding_ids


def test_fail_threshold_exceeded_without_waiver_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_aaa_performance_budget_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["triangle_count"] = 200001
    report["triangle_budget_status"] = "fail"
    test_file = tmp_path / "triangle-fail-threshold.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "triangle_count_fail_threshold_exceeded" for item in payload["findings"])


def test_waived_fail_threshold_is_visible_warning(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_aaa_performance_budget_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "warn"
    report["triangle_count"] = 200001
    report["triangle_budget_status"] = "warn"
    report["waiver_status"] = "waived"
    report["waiver_ids"] = ["waiver-triangles-002"]
    report["waiver_reasons"] = ["Silhouette-preservation pilot waiver for controlled evidence slice."]
    report["findings"] = [
        {
            "id": "waiver_note",
            "severity": "warning",
            "status": "open",
            "message": "Triangle fail threshold exceeded under approved waiver."
        }
    ]
    test_file = tmp_path / "triangle-fail-threshold-waived.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file, allow_warn=True)
    payload = _extract_payload(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "warn"
    assert any(item.get("id") == "triangle_count_fail_threshold_waived" for item in payload["findings"])


def test_output_contains_manifest_attachable_qc_payload():
    result = _run_validator(_report_path("max_biped_v1_aaa_performance_budget_pass.json"))
    payload = _extract_payload(result.stdout)
    attachment = payload.get("manifest_attachment", {})
    qc_check = attachment.get("qc_check", {})
    assert qc_check.get("check_id") == "aaa_performance_budget_v1"


def test_output_target_paths_are_correct():
    result = _run_validator(_report_path("max_biped_v1_aaa_performance_budget_pass.json"))
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["target_path"] == "qc.gates[]"
    assert payload["manifest_attachment"]["future_target_path"] == "qc.checks[]"
