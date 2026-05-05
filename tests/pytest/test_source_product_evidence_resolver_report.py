import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validator_script() -> Path:
    return _repo_root() / "tools" / "source-product-evidence-resolver" / "validate_source_product_evidence_resolver_report.py"


def _report_path(name: str) -> Path:
    return _repo_root() / "examples" / "source-product-evidence-resolver" / name


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
    result = _run_validator(_report_path("max_biped_v1_source_product_resolver_pass.json"))
    assert result.returncode == 0, f"Unexpected failure:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "pass"


def test_warn_report_returns_warn_and_exit_zero_with_allow_warn():
    result = _run_validator(_report_path("max_biped_v1_source_product_resolver_warn.json"), allow_warn=True)
    assert result.returncode == 0, f"Warn should pass with --allow-warn:\n{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_warn_report_returns_nonzero_without_allow_warn():
    result = _run_validator(_report_path("max_biped_v1_source_product_resolver_warn.json"), allow_warn=False)
    assert result.returncode != 0, "Warn should return nonzero without --allow-warn"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "warn"


def test_fail_report_returns_fail_and_nonzero():
    result = _run_validator(_report_path("max_biped_v1_source_product_resolver_fail.json"))
    assert result.returncode != 0, "Fail report must return nonzero"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "fail"


def test_missing_required_expected_product_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_source_product_resolver_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["observed_products"] = [
        item for item in report["observed_products"] if item.get("product_type") != "actor"
    ]
    test_file = tmp_path / "missing-required-actor.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    ids = {item.get("id") for item in payload["findings"]}
    assert "required_expected_product_missing" in ids


def test_non_admitted_claim_status_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_source_product_resolver_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["source_uuid_claim_status"] = "future_admitted"
    test_file = tmp_path / "future-admitted-claims.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    ids = {item.get("id") for item in payload["findings"]}
    assert "source_uuid_claim_status_not_admitted" in ids


def test_cache_or_live_db_not_blocked_fails(tmp_path: Path):
    report = json.loads(_report_path("max_biped_v1_source_product_resolver_pass.json").read_text(encoding="utf-8-sig"))
    report["status"] = "fail"
    report["cache_access_status"] = "admitted"
    report["live_db_access_status"] = "admitted"
    test_file = tmp_path / "cache-live-db-not-blocked.json"
    test_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run_validator(test_file)
    payload = _extract_payload(result.stdout)
    assert result.returncode != 0
    assert payload["status"] == "fail"
    ids = {item.get("id") for item in payload["findings"]}
    assert "cache_access_not_blocked" in ids
    assert "live_db_access_not_blocked" in ids


def test_output_contains_manifest_attachable_qc_payload():
    result = _run_validator(_report_path("max_biped_v1_source_product_resolver_pass.json"))
    payload = _extract_payload(result.stdout)
    attachment = payload.get("manifest_attachment", {})
    qc_check = attachment.get("qc_check", {})
    assert qc_check.get("check_id") == "source_product_evidence_resolver_v1"


def test_output_target_path_is_qc_gates():
    result = _run_validator(_report_path("max_biped_v1_source_product_resolver_pass.json"))
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["target_path"] == "qc.gates[]"


def test_output_future_target_path_is_qc_checks():
    result = _run_validator(_report_path("max_biped_v1_source_product_resolver_pass.json"))
    payload = _extract_payload(result.stdout)
    assert payload["manifest_attachment"]["future_target_path"] == "qc.checks[]"
