import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO_ROOT
    / "tools"
    / "production-readiness-report"
    / "validate_production_readiness_report.py"
)
BASE_MANIFEST = REPO_ROOT / "examples" / "manifests" / "example-release-character-pilot-chain.manifest.json"
SCHEMA = REPO_ROOT / "schemas" / "maxine_production_readiness_report.schema.json"
PASS_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "production-readiness-report"
    / "max_biped_v1_production_readiness_report_pass.json"
)
WARN_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "production-readiness-report"
    / "max_biped_v1_production_readiness_report_warn.json"
)
FAIL_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "production-readiness-report"
    / "max_biped_v1_production_readiness_report_fail.json"
)


def _run(manifest_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(manifest_path), *extra],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def _parse_payload(stdout: str) -> dict:
    start = stdout.find("{")
    assert start >= 0, f"expected JSON output, got: {stdout}"
    return json.loads(stdout[start:])


def _with_pilot_chain_gate(manifest: dict) -> dict:
    payload = json.loads(json.dumps(manifest))
    gates = payload.setdefault("qc", {}).setdefault("gates", [])
    if not any(isinstance(g, dict) and g.get("check_id") == "pilot_release_chain_v1" for g in gates):
        gates.append(
            {
                "check_id": "pilot_release_chain_v1",
                "result": "pass",
                "severity": "info",
                "details": {
                    "contract_id": "PILOT_RELEASE_CHAIN_v1",
                    "evidence_class": "manual",
                },
            }
        )
    return payload


def test_validator_passes_evidence_ready_manifest_and_blocks_full_production_claim(tmp_path: Path):
    manifest = _with_pilot_chain_gate(json.loads(BASE_MANIFEST.read_text(encoding="utf-8-sig")))
    tmp_manifest = tmp_path / "production-readiness-pass.manifest.json"
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(tmp_manifest)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "pass"
    assert payload["readiness_decision"] == "blocked_for_execution"
    assert payload["production_readiness_level"] == "review_ready"
    assert payload["admitted_noop_receipt_candidate_ids"] == ["release_candidate_package_receipt_noop_v1"]
    assert payload["receipt_backed_candidate_ids"] == ["release_candidate_package_receipt_noop_v1"]
    assert payload["admitted_real_execution_candidate_ids"] == []
    assert payload["admitted_publication_candidate_ids"] == []
    assert payload["execution_admission_status"] == "blocked"
    assert payload["real_execution_admission_status"] == "blocked"
    assert payload["publication_admission_status"] == "blocked"
    assert payload["manifest_attachment"]["qc_check"]["check_id"] == "production_readiness_report_v1"


def test_schema_validates_pass_warn_fail_examples():
    jsonschema = pytest.importorskip("jsonschema")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8-sig"))
    validator = jsonschema.Draft202012Validator(schema)
    for example in (PASS_EXAMPLE, WARN_EXAMPLE, FAIL_EXAMPLE):
        payload = json.loads(example.read_text(encoding="utf-8-sig"))
        errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
        assert not errors, f"{example} schema errors: {[err.message for err in errors]}"


def test_missing_required_gate_chain_summary_fails(tmp_path: Path):
    manifest = _with_pilot_chain_gate(json.loads(BASE_MANIFEST.read_text(encoding="utf-8-sig")))
    manifest["qc"]["gates"] = [
        gate for gate in manifest["qc"]["gates"] if gate.get("check_id") != "manual_hero_review_v1"
    ]
    tmp_manifest = tmp_path / "production-readiness-missing-gate.manifest.json"
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(tmp_manifest)
    assert result.returncode != 0
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "fail"
    assert "manual_hero_review_v1" in payload["missing_required_gate_ids"]
    assert "missing_required_gate_chain_summary" in payload["blocking_findings"]


def test_source_product_authority_false_claim_fails(tmp_path: Path):
    manifest = _with_pilot_chain_gate(json.loads(BASE_MANIFEST.read_text(encoding="utf-8-sig")))
    for gate in manifest["qc"]["gates"]:
        if gate.get("check_id") == "source_product_evidence_resolver_v1":
            gate.setdefault("details", {})
            gate["details"]["source_uuid_claim_status"] = "authoritative"
            break
    tmp_manifest = tmp_path / "production-readiness-source-authority-fail.manifest.json"
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(tmp_manifest)
    assert result.returncode != 0
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "fail"
    assert "source_product_authority_false_claim" in payload["blocking_findings"]


def test_real_execution_admission_without_candidate_reference_fails(tmp_path: Path):
    manifest = _with_pilot_chain_gate(json.loads(BASE_MANIFEST.read_text(encoding="utf-8-sig")))
    for gate in manifest["qc"]["gates"]:
        if gate.get("check_id") == "manual_hero_review_v1":
            gate.setdefault("details", {})
            gate["details"]["real_execution_admission_status"] = "admitted"
            gate["details"]["execution_admission_reference"] = "docs/maxine/execution-admission/example-real-exec.json"
            break
    tmp_manifest = tmp_path / "production-readiness-real-exec-admitted-no-candidate.manifest.json"
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(tmp_manifest)
    assert result.returncode != 0
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "fail"
    assert "real_execution_admission_without_candidate_reference" in payload["blocking_findings"]


def test_real_execution_candidate_without_reference_fails(tmp_path: Path):
    manifest = _with_pilot_chain_gate(json.loads(BASE_MANIFEST.read_text(encoding="utf-8-sig")))
    for gate in manifest["qc"]["gates"]:
        if gate.get("check_id") == "manual_hero_review_v1":
            gate.setdefault("details", {})
            gate["details"]["admitted_real_execution_candidate_ids"] = [
                "max_biped_v1_real_execution_candidate_001"
            ]
            gate["details"]["real_execution_admission_status"] = "admitted"
            gate["details"].pop("execution_admission_reference", None)
            break
    tmp_manifest = tmp_path / "production-readiness-real-exec-candidate-no-ref.manifest.json"
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(tmp_manifest)
    assert result.returncode != 0
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "fail"
    assert "execution_admission_without_reference" in payload["blocking_findings"]


def test_noop_candidate_misclassified_as_real_execution_fails(tmp_path: Path):
    manifest = _with_pilot_chain_gate(json.loads(BASE_MANIFEST.read_text(encoding="utf-8-sig")))
    for gate in manifest["qc"]["gates"]:
        if gate.get("check_id") == "manual_hero_review_v1":
            gate.setdefault("details", {})
            gate["details"]["admitted_real_execution_candidate_ids"] = [
                "release_candidate_package_receipt_noop_v1"
            ]
            gate["details"]["real_execution_admission_status"] = "admitted"
            gate["details"]["execution_admission_reference"] = (
                "docs/maxine/execution-admission/example-real-exec-approval.json"
            )
            break
    tmp_manifest = tmp_path / "production-readiness-noop-misclassified-as-real.manifest.json"
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(tmp_manifest)
    assert result.returncode != 0
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "fail"
    assert "noop_candidate_misclassified_as_real_execution" in payload["blocking_findings"]


def test_publication_admission_without_candidate_reference_fails(tmp_path: Path):
    manifest = _with_pilot_chain_gate(json.loads(BASE_MANIFEST.read_text(encoding="utf-8-sig")))
    for gate in manifest["qc"]["gates"]:
        if gate.get("check_id") == "manual_hero_review_v1":
            gate.setdefault("details", {})
            gate["details"]["publication_admission_status"] = "admitted"
            gate["details"]["publication_admission_reference"] = (
                "docs/maxine/execution-admission/example-publication-approval.json"
            )
            break
    tmp_manifest = tmp_path / "production-readiness-publication-admitted-no-candidate.manifest.json"
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(tmp_manifest)
    assert result.returncode != 0
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "fail"
    assert "publication_admission_without_candidate_reference" in payload["blocking_findings"]


def test_publication_candidate_without_reference_fails(tmp_path: Path):
    manifest = _with_pilot_chain_gate(json.loads(BASE_MANIFEST.read_text(encoding="utf-8-sig")))
    for gate in manifest["qc"]["gates"]:
        if gate.get("check_id") == "manual_hero_review_v1":
            gate.setdefault("details", {})
            gate["details"]["admitted_publication_candidate_ids"] = [
                "max_biped_v1_publication_candidate_001"
            ]
            gate["details"]["publication_admission_status"] = "admitted"
            gate["details"].pop("publication_admission_reference", None)
            break
    tmp_manifest = tmp_path / "production-readiness-publication-candidate-no-ref.manifest.json"
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(tmp_manifest)
    assert result.returncode != 0
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "fail"
    assert "publication_admission_without_reference" in payload["blocking_findings"]


def test_production_ready_claim_while_real_execution_blocked_fails(tmp_path: Path):
    manifest = _with_pilot_chain_gate(json.loads(BASE_MANIFEST.read_text(encoding="utf-8-sig")))
    manifest["qc"]["gates"].append(
        {
            "check_id": "production_readiness_report_v1",
            "result": "pass",
            "severity": "info",
            "details": {
                "production_readiness_level": "production_ready",
                "real_execution_admission_status": "blocked",
                "publication_admission_status": "blocked",
            },
        }
    )
    tmp_manifest = tmp_path / "production-readiness-false-claim.manifest.json"
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(tmp_manifest)
    assert result.returncode != 0
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "fail"
    assert "production_ready_claim_while_blocked" in payload["blocking_findings"]


def test_production_ready_claim_while_publication_blocked_fails(tmp_path: Path):
    manifest = _with_pilot_chain_gate(json.loads(BASE_MANIFEST.read_text(encoding="utf-8-sig")))
    manifest["qc"]["gates"].append(
        {
            "check_id": "production_readiness_report_v1",
            "result": "pass",
            "severity": "info",
            "details": {
                "production_readiness_level": "production_ready",
                "real_execution_admission_status": "admitted",
                "admitted_real_execution_candidate_ids": ["max_biped_v1_real_execution_candidate_001"],
                "execution_admission_reference": "docs/maxine/execution-admission/example-real-exec-approval.json",
                "publication_admission_status": "blocked",
            },
        }
    )
    tmp_manifest = tmp_path / "production-readiness-false-claim-publication-blocked.manifest.json"
    tmp_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = _run(tmp_manifest)
    assert result.returncode != 0
    payload = _parse_payload(result.stdout)
    assert payload["status"] == "fail"
    assert "production_ready_claim_while_blocked" in payload["blocking_findings"]
