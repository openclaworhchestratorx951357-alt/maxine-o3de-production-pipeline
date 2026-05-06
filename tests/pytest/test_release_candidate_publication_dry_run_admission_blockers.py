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
    / "maxine_release_candidate_publication_dry_run_admission_blockers.schema.json"
)
CHECKLIST_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "release_candidate_package_publish_dry_run_admission_blockers_v1.json"
)
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_release_candidate_publication_dry_run_admission_blockers.py"
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
    return copy.deepcopy(_load(CHECKLIST_EXAMPLE))


def _finding_ids(payload: dict) -> set[str]:
    return {
        str(item.get("id", "")).strip()
        for item in payload.get("findings", [])
        if isinstance(item, dict)
    }


def test_admission_blockers_example_validates_and_reports_blocked_posture():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    payload = _load(CHECKLIST_EXAMPLE)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, [f"{'.'.join(str(p) for p in err.path)}: {err.message}" for err in errors]

    code, report = _run_validator(CHECKLIST_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["release_candidate_publication_dry_run_admission_blockers_present"] is True
    assert report["planned_candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert report["candidate_type"] == "dry_run"
    assert report["checklist_status"] == "static_checklist_valid_blocked"
    assert report["admission_status"] == "unadmitted"
    assert report["approval_review_ready"] is False
    assert report["ready_to_request_approval"] is False
    assert report["dry_run_admitted"] is False
    assert report["receipt_issued"] is False
    assert report["publication_admitted"] is False
    assert report["real_execution_admitted"] is False
    assert report["production_ready_claimed"] is False
    assert (
        report["approval_phrase_required"]
        == "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
    )
    assert len(report["admission_blockers"]) > 0
    assert len(report["approval_blockers"]) > 0
    assert len(report["evidence_blockers"]) > 0
    assert len(report["receipt_blockers"]) > 0
    assert len(report["rollback_or_cleanup_blockers"]) > 0
    assert len(report["publication_blockers"]) > 0
    assert len(report["execution_blockers"]) > 0


def test_validator_cross_checks_matrix_contracts_proof_rollup_plan_and_receipt():
    code, report = _run_validator(CHECKLIST_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    source_status = report["computed_source_artifact_validation_status"]
    assert source_status["candidate_matrix_status"] == "pass"
    assert source_status["preflight_contracts_status"] == "pass"
    assert source_status["preflight_proof_packages_status"] == "pass"
    assert source_status["readiness_rollup_status"] == "pass"
    assert source_status["dry_run_plan_status"] == "pass"
    assert source_status["dry_run_receipt_contract_status"] == "pass"
    assert source_status["blocked_unissued_receipt_status"] == "pass"
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


def test_validator_rejects_checklist_status_or_admission_status_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    payload["checklist_status"] = "static_checklist_invalid"
    payload["admission_status"] = "admitted"
    path = tmp_path / "invalid-checklist-status-and-admission-status.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "checklist_status_not_static_checklist_valid_blocked" in finding_ids
    assert "admission_status_not_unadmitted" in finding_ids


def test_validator_rejects_approval_review_ready_or_ready_to_request_approval_true(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    payload["approval_review_ready"] = True
    payload["ready_to_request_approval"] = True
    path = tmp_path / "invalid-approval-readiness-flags.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "approval_review_ready_not_allowed" in finding_ids
    assert "ready_to_request_approval_not_allowed" in finding_ids


def test_validator_rejects_admitted_receipt_or_production_ready_flags(tmp_path: Path):
    payload = _clone_base_payload()
    payload["dry_run_admitted"] = True
    payload["receipt_issued"] = True
    payload["publication_admitted"] = True
    payload["real_execution_admitted"] = True
    payload["production_ready_claimed"] = True
    path = tmp_path / "invalid-admitted-receipt-production-flags.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "dry_run_admitted_not_allowed" in finding_ids
    assert "receipt_issued_not_allowed" in finding_ids
    assert "publication_admitted_not_allowed" in finding_ids
    assert "real_execution_admitted_not_allowed" in finding_ids
    assert "production_ready_claim_not_allowed" in finding_ids


def test_validator_rejects_approval_phrase_or_decision_reference_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    payload["approval_phrase_required"] = "APPROVE EXECUTION ADMISSION wrong_id"
    payload["approval_decision_reference"] = "approved::decision"
    path = tmp_path / "invalid-approval-phrase-and-decision-reference.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "approval_phrase_required_mismatch" in finding_ids
    assert "approval_decision_reference_not_allowed" in finding_ids


def test_validator_rejects_missing_prerequisite_checklist_entries(tmp_path: Path):
    payload = _clone_base_payload()
    del payload["prerequisite_checklist"]["dry_run_executed"]
    path = tmp_path / "invalid-missing-prerequisite-entry.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "prerequisite_checklist_missing_key" in _finding_ids(report)


def test_validator_rejects_inconsistent_prerequisite_values(tmp_path: Path):
    payload = _clone_base_payload()
    payload["prerequisite_checklist"]["source_artifact_validations_pass"] = False
    payload["prerequisite_checklist"]["publication_surfaces_blocked"] = False
    path = tmp_path / "invalid-prerequisite-values.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "prerequisite_checklist_value_mismatch" in _finding_ids(report)


def test_validator_rejects_empty_blocker_lists(tmp_path: Path):
    payload = _clone_base_payload()
    payload["admission_blockers"] = []
    payload["approval_blockers"] = []
    payload["evidence_blockers"] = []
    payload["receipt_blockers"] = []
    payload["rollback_or_cleanup_blockers"] = []
    payload["publication_blockers"] = []
    payload["execution_blockers"] = []
    path = tmp_path / "invalid-empty-blocker-lists.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "blocker_list_missing_or_empty" in _finding_ids(report)


def test_validator_rejects_admission_blockers_missing_required_tokens(tmp_path: Path):
    payload = _clone_base_payload()
    payload["admission_blockers"] = ["missing_approval_decision"]
    path = tmp_path / "invalid-admission-blockers-missing-tokens.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "admission_blockers_missing_required_token" in _finding_ids(report)


def test_validator_rejects_source_artifact_validation_status_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    payload["source_artifact_validation_status"]["candidate_matrix_status"] = "fail"
    path = tmp_path / "invalid-source-artifact-validation-status.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "source_artifact_validation_status_mismatch" in _finding_ids(report)


def test_validator_rejects_unsafe_claims_detected_true(tmp_path: Path):
    payload = _clone_base_payload()
    payload["unsafe_claims_detected"] = True
    path = tmp_path / "invalid-unsafe-claims-detected.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "unsafe_claims_detected_not_allowed" in _finding_ids(report)


def test_validator_rejects_language_that_allows_publish_or_spawn(tmp_path: Path):
    payload = _clone_base_payload()
    payload["safety_notes"].append("publish allowed")
    payload["safety_notes"].append("spawn allowed")
    path = tmp_path / "invalid-language-allows-publish-spawn.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "checklist_allows_publish" in finding_ids
    assert "checklist_allows_spawn" in finding_ids


def test_validator_rejects_language_that_allows_prod_engine_cache_or_authoritative_claims(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    payload["safety_notes"].extend(
        [
            "production path writes allowed",
            "engine path writes allowed",
            "cache/live db access allowed",
            "authoritative source uuid claims allowed",
            "authoritative asset id claims allowed",
            "authoritative product id claims allowed",
        ]
    )
    path = tmp_path / "invalid-language-allows-blocked-surfaces.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "checklist_allows_production_path_writes" in finding_ids
    assert "checklist_allows_engine_path_writes" in finding_ids
    assert "checklist_allows_cache_live_db_access" in finding_ids
    assert "checklist_allows_authoritative_source_uuid_claims" in finding_ids
    assert "checklist_allows_authoritative_asset_id_claims" in finding_ids
    assert "checklist_allows_authoritative_product_id_claims" in finding_ids


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
    path = tmp_path / "invalid-checklist-rollup-target.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "readiness_rollup_validation_failed" in finding_ids
    assert "readiness_rollup_safest_next_candidate_mismatch" in finding_ids


def test_validator_rejects_dry_run_plan_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    plan = _load(
        REPO_ROOT
        / "examples"
        / "execution-admission"
        / "release_candidate_package_publish_dry_run_plan_v1.json"
    )
    plan["candidate_type"] = "publication"
    plan_path = tmp_path / "invalid-plan-type.json"
    _write(plan_path, plan)
    payload["source_artifacts"]["dry_run_plan_ref"] = str(plan_path)
    path = tmp_path / "invalid-checklist-plan-mismatch.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "dry_run_plan_validation_failed" in finding_ids
    assert "dry_run_plan_candidate_type_mismatch" in finding_ids


def test_validator_rejects_receipt_contract_mismatch_or_blocked_receipt_status_mismatch(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    receipt_contract = _load(
        REPO_ROOT
        / "examples"
        / "execution-admission"
        / "release_candidate_package_publish_dry_run_receipt_contract_v1.json"
    )
    blocked_receipt = _load(
        REPO_ROOT
        / "examples"
        / "execution-admission"
        / "release_candidate_package_publish_dry_run_receipt_blocked_v1.json"
    )
    receipt_contract["receipt_issued"] = True
    blocked_receipt["receipt_status"] = "dry_run_completed_no_publication"
    receipt_contract_path = tmp_path / "invalid-receipt-contract.json"
    blocked_receipt_path = tmp_path / "invalid-receipt-blocked.json"
    _write(receipt_contract_path, receipt_contract)
    _write(blocked_receipt_path, blocked_receipt)
    payload["source_artifacts"]["dry_run_receipt_contract_ref"] = str(receipt_contract_path)
    payload["source_artifacts"]["blocked_unissued_receipt_ref"] = str(blocked_receipt_path)
    path = tmp_path / "invalid-checklist-receipt-artifacts.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "dry_run_receipt_contract_validation_failed" in finding_ids
    assert "blocked_unissued_receipt_validation_failed" in finding_ids
