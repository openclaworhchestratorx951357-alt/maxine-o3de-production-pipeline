import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validator_script() -> Path:
    return _repo_root() / "tools" / "dcc-conform" / "validate_dcc_conform_report.py"


def _report_path(name: str) -> Path:
    return _repo_root() / "examples" / "dcc-conform" / name


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
    result = _run_validator(_report_path("max_biped_v1_conform_pass.json"))
    assert result.returncode == 0, f"Unexpected failure:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "pass"
    assert payload["check_id"] == "dcc_conform_v1"


def test_warn_report_returns_warn_and_allow_warn_controls_exit():
    strict = _run_validator(_report_path("max_biped_v1_conform_warn.json"), allow_warn=False)
    assert strict.returncode != 0, "Warn must be nonzero without --allow-warn"
    strict_payload = _extract_payload(strict.stdout)
    assert strict_payload["status"] == "warn"

    allowed = _run_validator(_report_path("max_biped_v1_conform_warn.json"), allow_warn=True)
    assert allowed.returncode == 0, f"Warn should pass with --allow-warn:\n{allowed.stdout}\n{allowed.stderr}"
    allowed_payload = _extract_payload(allowed.stdout)
    assert allowed_payload["status"] == "warn"


def test_fail_report_returns_fail_and_nonzero():
    result = _run_validator(_report_path("max_biped_v1_conform_fail.json"))
    assert result.returncode != 0, "Fail report must return nonzero"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "fail"


def test_missing_skeleton_contract_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_conform_pass.json").read_text(encoding="utf-8-sig"))
    report["target"]["skeleton_contract_id"] = ""
    test_file = tmp_path / "missing-skeleton-contract.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "skeleton_contract_id_invalid" for item in payload["findings"])


def test_missing_units_data_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_conform_pass.json").read_text(encoding="utf-8-sig"))
    del report["transform"]["units"]
    test_file = tmp_path / "missing-units.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "units_missing" for item in payload["findings"])


def test_missing_origin_facing_data_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_conform_pass.json").read_text(encoding="utf-8-sig"))
    del report["transform"]["origin_centered"]
    del report["transform"]["forward_axis"]
    test_file = tmp_path / "missing-origin-facing.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    ids = {item.get("id") for item in payload["findings"]}
    assert "origin_not_centered" in ids
    assert "forward_axis_invalid" in ids


def test_missing_root_bone_flag_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_conform_pass.json").read_text(encoding="utf-8-sig"))
    del report["skeleton"]["root_bone_present"]
    test_file = tmp_path / "missing-root-flag.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "root_bone_flag_missing" for item in payload["findings"])


def test_output_contains_manifest_attachable_qc_payload():
    result = _run_validator(_report_path("max_biped_v1_conform_pass.json"))
    payload = _extract_payload(result.stdout)
    attachment = payload.get("manifest_attachment", {})
    qc_check = attachment.get("qc_check", {})

    assert attachment.get("target_path") == "qc.gates[]"
    assert attachment.get("future_target_path") == "qc.checks[]"
    assert qc_check.get("check_id") == "dcc_conform_v1"
    assert qc_check.get("result") == "pass"
