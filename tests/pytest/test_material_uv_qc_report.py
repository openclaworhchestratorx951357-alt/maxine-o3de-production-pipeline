import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validator_script() -> Path:
    return _repo_root() / "tools" / "material-uv-qc" / "validate_material_uv_qc_report.py"


def _report_path(name: str) -> Path:
    return _repo_root() / "examples" / "material-uv-qc" / name


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
    result = _run_validator(_report_path("max_biped_v1_material_uv_pass.json"))
    assert result.returncode == 0, f"Unexpected failure:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "pass"


def test_warn_report_returns_warn_and_exit_zero_with_allow_warn():
    result = _run_validator(_report_path("max_biped_v1_material_uv_warn.json"), allow_warn=True)
    assert result.returncode == 0, f"Warn should pass with --allow-warn:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_warn_report_returns_nonzero_without_allow_warn():
    result = _run_validator(_report_path("max_biped_v1_material_uv_warn.json"), allow_warn=False)
    assert result.returncode != 0, "Warn should return nonzero without --allow-warn"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_fail_report_returns_fail_and_nonzero():
    result = _run_validator(_report_path("max_biped_v1_material_uv_fail.json"))
    assert result.returncode != 0, "Fail report must return nonzero"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "fail"


def test_missing_required_uv_set_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_material_uv_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["uv_summary"]["required_uv_sets"] = ["UV0", "UV1"]
    report["uv_summary"]["present_uv_sets"] = ["UV0"]
    report["uv_summary"]["missing_uv_sets"] = ["UV1"]
    test_file = tmp_path / "missing-required-uv.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    assert any(item.get("id") == "missing_required_uv_sets" for item in payload["findings"])


def test_missing_required_texture_or_material_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_material_uv_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["material_summary"]["missing_materials"] = ["body"]
    report["material_summary"]["missing_textures"] = ["textures/char/body_albedo.png"]
    test_file = tmp_path / "missing-material-texture.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    ids = {item.get("id") for item in payload["findings"]}
    assert "missing_required_materials" in ids
    assert "missing_required_textures" in ids


def test_material_slot_budget_overflow_warns_by_schema_rule(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_material_uv_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "warn"
    report["material_summary"]["material_slot_count"] = 12
    report["material_summary"]["material_slot_budget"] = 10
    report["material_summary"]["slot_budget_exceeded_severity"] = "warning"
    report["findings"] = [
        {
            "id": "material_slot_budget_exceeded",
            "severity": "warning",
            "status": "open",
            "message": "Material slot count exceeds budget."
        }
    ]
    test_file = tmp_path / "slot-budget-overflow-warn.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file, allow_warn=True)
    payload = _extract_payload(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "warn"
    assert any(item.get("id") == "material_slot_budget_exceeded" for item in payload["findings"])


def test_output_contains_manifest_attachable_qc_payload():
    result = _run_validator(_report_path("max_biped_v1_material_uv_pass.json"))
    payload = _extract_payload(result.stdout)
    assert "manifest_attachment" in payload
    assert "qc_check" in payload["manifest_attachment"]
    assert payload["manifest_attachment"]["qc_check"]["check_id"] == "material_uv_qc_v1"


def test_output_target_path_is_qc_gates():
    result = _run_validator(_report_path("max_biped_v1_material_uv_pass.json"))
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["target_path"] == "qc.gates[]"


def test_output_future_target_path_is_qc_checks():
    result = _run_validator(_report_path("max_biped_v1_material_uv_pass.json"))
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["future_target_path"] == "qc.checks[]"
