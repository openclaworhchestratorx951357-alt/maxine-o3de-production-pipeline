import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "maxine_release_candidate_publication_dry_run_receipt.schema.json"
)
RECEIPT_CONTRACT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "release_candidate_package_publish_dry_run_receipt_contract_v1.json"
)
RECEIPT_BLOCKED_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "release_candidate_package_publish_dry_run_receipt_blocked_v1.json"
)
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_release_candidate_publication_dry_run_receipt.py"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_validator(path: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    start = result.stdout.find("{")
    assert start >= 0, f"expected JSON output:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    return result.returncode, json.loads(result.stdout[start:])


def _clone_base_payload() -> dict:
    return copy.deepcopy(_load(RECEIPT_CONTRACT_EXAMPLE))


def _finding_ids(payload: dict) -> set[str]:
    return {
        str(item.get("id", "")).strip()
        for item in payload.get("findings", [])
        if isinstance(item, dict)
    }


def _remove_token(items: list[str], token: str) -> list[str]:
    token_lower = token.lower()
    return [item for item in items if token_lower not in str(item).lower()]


def test_receipt_contract_example_validates_and_reports_blocked_unissued_posture():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    payload = _load(RECEIPT_CONTRACT_EXAMPLE)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, [f"{'.'.join(str(p) for p in err.path)}: {err.message}" for err in errors]

    code, report = _run_validator(RECEIPT_CONTRACT_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["release_candidate_publication_dry_run_receipt_contract_present"] is True
    assert report["planned_candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert report["candidate_type"] == "dry_run"
    assert report["receipt_type"] == "release_candidate_package_publish_dry_run_receipt_v1"
    assert report["receipt_contract_status"] == "static_contract_valid_blocked"
    assert report["receipt_issued"] is False
    assert report["dry_run_admitted"] is False
    assert report["publication_admitted"] is False
    assert report["real_execution_admitted"] is False
    assert report["production_ready_claimed"] is False
    assert report["publication_surfaces_blocked"] is True
    assert report["execution_surfaces_blocked"] is True
    assert report["cache_live_db_access_blocked"] is True
    assert report["authoritative_id_claims_blocked"] is True
    assert report["missing_evidence_items_count"] > 0
    assert len(report["blocked_reason_codes"]) > 0


def test_blocked_unissued_receipt_example_validates():
    code, report = _run_validator(RECEIPT_BLOCKED_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["receipt_issued"] is False
    assert report["receipt_status"] == "blocked_unissued_contract_only"


def test_validator_cross_checks_matrix_contracts_proof_rollup_and_plan():
    code, report = _run_validator(RECEIPT_CONTRACT_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    source_status = report["computed_source_artifact_validation_status"]
    assert source_status["candidate_matrix_status"] == "pass"
    assert source_status["preflight_contracts_status"] == "pass"
    assert source_status["preflight_proof_packages_status"] == "pass"
    assert source_status["readiness_rollup_status"] == "pass"
    assert source_status["dry_run_plan_status"] == "pass"
    assert source_status["production_readiness_status"] == "pass"
    assert source_status["noop_receipt_status"] == "pass"


def test_validator_rejects_candidate_id_not_target(tmp_path: Path):
    payload = _clone_base_payload()
    payload["candidate_id"] = "wrong_candidate_v1"
    path = tmp_path / "invalid-candidate-id.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "candidate_id_mismatch" in _finding_ids(report)


def test_validator_rejects_candidate_type_not_dry_run(tmp_path: Path):
    payload = _clone_base_payload()
    payload["candidate_type"] = "publication"
    path = tmp_path / "invalid-candidate-type.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "candidate_type_mismatch" in _finding_ids(report)


def test_validator_rejects_receipt_type_not_expected(tmp_path: Path):
    payload = _clone_base_payload()
    payload["receipt_type"] = "wrong_receipt_type"
    path = tmp_path / "invalid-receipt-type.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "receipt_type_mismatch" in _finding_ids(report)


def test_validator_rejects_receipt_issued_true(tmp_path: Path):
    payload = _clone_base_payload()
    payload["receipt_issued"] = True
    path = tmp_path / "invalid-receipt-issued-true.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "receipt_issued_not_allowed" in _finding_ids(report)


def test_validator_rejects_admitted_flags_and_production_ready_claim(tmp_path: Path):
    payload = _clone_base_payload()
    payload["dry_run_admitted"] = True
    payload["publication_admitted"] = True
    payload["real_execution_admitted"] = True
    payload["production_ready_claimed"] = True
    path = tmp_path / "invalid-admitted-flags.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "dry_run_admitted_not_allowed" in finding_ids
    assert "publication_admitted_not_allowed" in finding_ids
    assert "real_execution_admitted_not_allowed" in finding_ids
    assert "production_ready_claim_not_allowed" in finding_ids


def test_validator_rejects_approval_fields_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    payload["approval_phrase_required"] = "APPROVE EXECUTION ADMISSION wrong_id"
    payload["required_approval_decision_reference"] = False
    payload["approval_decision_reference"] = "admitted::decision"
    path = tmp_path / "invalid-approval-fields.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "approval_phrase_required_mismatch" in finding_ids
    assert "required_approval_decision_reference_false" in finding_ids
    assert "approval_decision_reference_not_allowed" in finding_ids


def test_validator_rejects_contract_status_missing_evidence_and_blocked_codes(tmp_path: Path):
    payload = _clone_base_payload()
    payload["receipt_contract_status"] = "static_contract_invalid"
    payload["missing_evidence_items"] = []
    payload["blocked_reason_codes"] = []
    path = tmp_path / "invalid-contract-status-and-missing-items.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "receipt_contract_status_not_static_contract_valid_blocked" in finding_ids
    assert "required_array_missing_or_empty" in finding_ids


def test_validator_rejects_blocking_flags_false(tmp_path: Path):
    payload = _clone_base_payload()
    payload["publication_surfaces_blocked"] = False
    payload["execution_surfaces_blocked"] = False
    payload["cache_live_db_access_blocked"] = False
    payload["authoritative_id_claims_blocked"] = False
    path = tmp_path / "invalid-blocking-flags.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "publication_surfaces_blocked_false" in finding_ids
    assert "execution_surfaces_blocked_false" in finding_ids
    assert "cache_live_db_access_blocked_false" in finding_ids
    assert "authoritative_id_claims_blocked_false" in finding_ids


def test_validator_rejects_forbidden_paths_missing_categories(tmp_path: Path):
    payload = _clone_base_payload()
    payload["forbidden_paths"] = []
    path = tmp_path / "invalid-forbidden-path-categories.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "forbidden_paths_missing_production_category" in finding_ids
    assert "forbidden_paths_missing_engine_category" in finding_ids
    assert "forbidden_paths_missing_cache_live_db_category" in finding_ids
    assert "forbidden_paths_missing_destructive_cleanup_category" in finding_ids


def test_validator_rejects_forbidden_outputs_missing_publish_spawn_and_write_categories(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    payload["forbidden_outputs"] = []
    path = tmp_path / "invalid-forbidden-output-categories.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "forbidden_outputs_missing_publish_category" in finding_ids
    assert "forbidden_outputs_missing_spawn_category" in finding_ids
    assert "forbidden_outputs_missing_production_write_category" in finding_ids
    assert "forbidden_outputs_missing_engine_write_category" in finding_ids
    assert "contract_allows_cache_live_db_access" in finding_ids
    assert "contract_allows_authoritative_source_uuid_claims" in finding_ids
    assert "contract_allows_authoritative_asset_id_claims" in finding_ids
    assert "contract_allows_authoritative_product_id_claims" in finding_ids


def test_validator_rejects_required_receipt_fields_missing_tokens(tmp_path: Path):
    payload = _clone_base_payload()
    payload["required_receipt_fields"] = []
    path = tmp_path / "invalid-required-receipt-fields.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "required_receipt_fields_missing" in finding_ids
    assert "required_receipt_fields_missing_candidate_id" in finding_ids
    assert "required_receipt_fields_missing_receipt_status" in finding_ids
    assert "required_receipt_fields_missing_approval_decision_reference" in finding_ids
    assert "required_receipt_fields_missing_source_artifact_references" in finding_ids
    assert "required_receipt_fields_missing_sandbox_output_index" in finding_ids
    assert "required_receipt_fields_missing_blocked_surface_attestations" in finding_ids
    assert "required_receipt_fields_missing_rollback_or_cleanup_evidence" in finding_ids
    assert "required_receipt_fields_missing_hashes" in finding_ids
    assert "required_receipt_fields_missing_safety_posture" in finding_ids


def test_validator_rejects_receipt_status_that_implies_emitted_receipt(tmp_path: Path):
    payload = _clone_base_payload()
    payload["receipt_status"] = "dry_run_completed_no_publication"
    path = tmp_path / "invalid-receipt-status-emitted.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "receipt_status_emitted_not_allowed" in _finding_ids(report)


def test_validator_rejects_allowed_output_scope_outside_sandbox_or_prod_engine(tmp_path: Path):
    payload = _clone_base_payload()
    payload["allowed_receipt_output_scope"] = [
        "outside-sandbox/output",
        "examples/sandbox/production/output",
        "examples/sandbox/engine/output",
    ]
    path = tmp_path / "invalid-output-scope-paths.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "allowed_receipt_output_scope_outside_sandbox" in finding_ids
    assert "contract_allows_production_path_writes" in finding_ids
    assert "contract_allows_engine_path_writes" in finding_ids


def test_validator_rejects_safety_posture_authoritative_claims(tmp_path: Path):
    payload = _clone_base_payload()
    payload["safety_posture"]["source_uuid_status"] = "authoritative"
    payload["safety_posture"]["asset_id_status"] = "authoritative"
    payload["safety_posture"]["product_id_status"] = "authoritative"
    path = tmp_path / "invalid-authoritative-claims.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "source_uuid_status_authoritative_claim_allowed" in finding_ids
    assert "asset_id_status_authoritative_claim_allowed" in finding_ids
    assert "product_id_status_authoritative_claim_allowed" in finding_ids


def test_validator_rejects_forbidden_receipt_claims_missing_guard_tokens(tmp_path: Path):
    payload = _clone_base_payload()
    payload["forbidden_receipt_claims"] = []
    path = tmp_path / "invalid-forbidden-receipt-claims.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "contract_allows_dry_run_admission" in finding_ids
    assert "contract_allows_publication_admission" in finding_ids
    assert "contract_allows_real_execution_admission" in finding_ids
    assert "contract_allows_production_ready_claim" in finding_ids
    assert "contract_allows_receipt_issued_claim" in finding_ids


def test_validator_rejects_readiness_rollup_mismatch_target_candidate(tmp_path: Path):
    payload = _clone_base_payload()
    rollup = _load(
        REPO_ROOT
        / "examples"
        / "execution-admission"
        / "execution_admission_readiness_rollup_v1.json"
    )
    rollup["safest_next_preparation_slice"]["candidate_id"] = "release_candidate_package_publication_v1"
    rollup_path = tmp_path / "invalid-rollup-target.json"
    _write(rollup_path, rollup)
    payload["source_artifacts"]["readiness_rollup_ref"] = str(rollup_path)
    payload["readiness_rollup_alignment"]["readiness_rollup_ref"] = str(rollup_path)
    path = tmp_path / "invalid-contract-rollup-target-mismatch.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "readiness_rollup_validation_failed" in finding_ids
    assert "readiness_rollup_safest_next_candidate_mismatch" in finding_ids


def test_validator_rejects_readiness_rollup_safest_next_if_it_admits_execution_or_publication(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    rollup = _load(
        REPO_ROOT
        / "examples"
        / "execution-admission"
        / "execution_admission_readiness_rollup_v1.json"
    )
    rollup["safest_next_preparation_slice"]["admits_execution"] = True
    rollup["safest_next_preparation_slice"]["admits_publication"] = True
    rollup_path = tmp_path / "invalid-rollup-admission-flags.json"
    _write(rollup_path, rollup)
    payload["source_artifacts"]["readiness_rollup_ref"] = str(rollup_path)
    payload["readiness_rollup_alignment"]["readiness_rollup_ref"] = str(rollup_path)
    path = tmp_path / "invalid-contract-rollup-admission-flags.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "readiness_rollup_validation_failed" in finding_ids
    assert "contract_allows_real_execution_admission" in finding_ids
    assert "contract_allows_publication_admission" in finding_ids


def test_validator_rejects_source_artifact_status_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    payload["source_artifact_validation_status"]["candidate_matrix_status"] = "fail"
    path = tmp_path / "invalid-source-artifact-status.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "source_artifact_validation_status_mismatch" in _finding_ids(report)


def test_validator_rejects_empty_required_source_references(tmp_path: Path):
    payload = _clone_base_payload()
    payload["required_source_references"] = []
    path = tmp_path / "invalid-required-source-references.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "required_source_references_missing_field" in _finding_ids(report)
