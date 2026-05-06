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


def test_warn_report_returns_nonzero_without_allow_warn():
    result = _run_validator(_report_path("max_biped_v1_manual_hero_review_warn.json"))
    assert result.returncode != 0, "warn should return nonzero without --allow-warn"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_warn_report_returns_zero_with_allow_warn():
    result = _run_validator(_report_path("max_biped_v1_manual_hero_review_warn.json"), allow_warn=True)
    assert result.returncode == 0, f"Unexpected failure:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


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


def test_missing_required_controlled_real_refs_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_manual_hero_review_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["decision"] = "fail"
    report["release_recommendation"] = "reject"
    report["reviewed_evidence_refs"] = [
        "dcc_conform_v1",
        "max_biped_v1_skeleton_contract",
        "material_uv_qc_v1",
    ]
    report["required_evidence_present_status"] = "fail"
    report["reviewer_findings"] = [
        {
            "id": "required_refs_missing",
            "severity": "error",
            "status": "open",
            "message": "Required controlled-real evidence references are missing.",
        }
    ]
    test_file = tmp_path / "missing-required-refs.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "required_controlled_real_evidence_refs_missing" for item in payload["findings"])


def test_pass_decision_with_waiver_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_manual_hero_review_pass.json").read_text(encoding="utf-8-sig"))
    report["waiver_status"] = "waived"
    report["waiver_reasons"] = ["Temporary waiver for review packet formatting."]
    test_file = tmp_path / "pass-with-waiver.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "pass_with_waiver_not_allowed" for item in payload["findings"])


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
