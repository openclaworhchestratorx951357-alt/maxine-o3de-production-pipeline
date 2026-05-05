import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validator_script() -> Path:
    return _repo_root() / "tools" / "manual-hero-review" / "validate_manual_hero_review_report.py"


def _report_path(name: str) -> Path:
    return _repo_root() / "examples" / "manual-hero-review" / name


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
    result = _run_validator(_report_path("max_biped_v1_manual_hero_review_pass.json"))
    assert result.returncode == 0, f"Unexpected failure:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "pass"


def test_pending_report_returns_pending_manual_and_nonzero():
    result = _run_validator(_report_path("max_biped_v1_manual_hero_review_pending.json"))
    assert result.returncode != 0, "pending_manual should return nonzero"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "pending_manual"


def test_fail_report_returns_fail_and_nonzero():
    result = _run_validator(_report_path("max_biped_v1_manual_hero_review_fail.json"))
    assert result.returncode != 0, "Fail report must return nonzero"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "fail"


def test_missing_required_evidence_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_manual_hero_review_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["review_decision"]["attached_evidence_ids"] = [
        "max_biped_v1_skeleton_contract",
        "dcc_conform_v1",
        "material_uv_qc_v1"
    ]
    report["review_decision"]["missing_evidence_ids"] = [
        "animation_smoke_v1",
        "screenshot_evidence_v1"
    ]
    report["review_decision"]["review_state"] = "approved"
    test_file = tmp_path / "missing-required-evidence.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "required_evidence_missing" for item in payload["findings"])


def test_insufficient_reviewer_count_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_manual_hero_review_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["review_decision"]["reviewer_count"] = 1
    report["review_decision"]["approver_ids"] = ["ops.lead_a"]
    test_file = tmp_path / "insufficient-reviewers.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    ids = {item.get("id") for item in payload["findings"]}
    assert "insufficient_reviewer_count" in ids
    assert "insufficient_approver_ids" in ids


def test_missing_approved_timestamp_warns_with_allow_warn(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_manual_hero_review_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "warn"
    report["review_decision"].pop("approved_at_utc", None)
    test_file = tmp_path / "approved-without-timestamp.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file, allow_warn=True)
    payload = _extract_payload(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "warn"
    assert any(item.get("id") == "approved_at_utc_missing" for item in payload["findings"])


def test_hero_review_disabled_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_manual_hero_review_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["review_decision"]["review_required"] = False
    report["review_decision"]["review_state"] = "not_required"
    test_file = tmp_path / "hero-review-disabled.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "hero_review_required" for item in payload["findings"])


def test_output_contains_manifest_attachable_qc_payload():
    result = _run_validator(_report_path("max_biped_v1_manual_hero_review_pass.json"))
    payload = _extract_payload(result.stdout)
    attachment = payload.get("manifest_attachment", {})
    qc_check = attachment.get("qc_check", {})
    assert qc_check.get("check_id") == "manual_hero_review_v1"


def test_output_target_path_is_qc_gates():
    result = _run_validator(_report_path("max_biped_v1_manual_hero_review_pass.json"))
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["target_path"] == "qc.gates[]"


def test_output_future_target_path_is_qc_checks():
    result = _run_validator(_report_path("max_biped_v1_manual_hero_review_pass.json"))
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["future_target_path"] == "qc.checks[]"
