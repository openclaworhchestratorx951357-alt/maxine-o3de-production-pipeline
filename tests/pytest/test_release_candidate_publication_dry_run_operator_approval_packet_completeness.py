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
    / "maxine_release_candidate_publication_dry_run_operator_approval_packet_completeness.schema.json"
)
REVIEW_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "release_candidate_package_publish_dry_run_operator_approval_packet_completeness_v1.json"
)
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_release_candidate_publication_dry_run_operator_approval_packet_completeness.py"
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
    return copy.deepcopy(_load(REVIEW_EXAMPLE))


def _finding_ids(payload: dict) -> set[str]:
    return {
        str(item.get("id", "")).strip()
        for item in payload.get("findings", [])
        if isinstance(item, dict)
    }


def test_operator_approval_packet_completeness_example_validates_and_reports_blocked_posture():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    payload = _load(REVIEW_EXAMPLE)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, [f"{'.'.join(str(p) for p in err.path)}: {err.message}" for err in errors]

    code, report = _run_validator(REVIEW_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert (
        report["release_candidate_publication_dry_run_operator_approval_packet_completeness_present"]
        is True
    )
    assert report["planned_candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert report["candidate_type"] == "dry_run"
    assert report["completeness_review_status"] == "static_completeness_valid_blocked"
    assert report["admission_status"] == "unadmitted"
    assert report["packet_structurally_complete"] is True
    assert report["packet_internally_consistent"] is True
    assert report["packet_complete_for_future_review_template"] is True
    assert report["approval_request_ready"] is False
    assert report["operator_approval_granted"] is False
    assert report["approval_phrase_present"] is False
    assert report["dry_run_admitted"] is False
    assert report["receipt_issued"] is False
    assert report["publication_admitted"] is False
    assert report["real_execution_admitted"] is False
    assert report["production_ready_claimed"] is False
    assert (
        report["approval_phrase_required"]
        == "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
    )
    assert len(report["completeness_checks"]) > 0
    assert len(report["consistency_checks"]) > 0
    assert len(report["unresolved_approval_blockers"]) > 0
    assert len(report["unresolved_execution_blockers"]) > 0
    assert len(report["unresolved_receipt_blockers"]) > 0
    assert len(report["unresolved_publication_blockers"]) > 0


def test_validator_cross_checks_all_required_source_artifacts():
    code, report = _run_validator(REVIEW_EXAMPLE)
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
    assert source_status["admission_blocker_checklist_status"] == "pass"
    assert source_status["operator_approval_packet_status"] == "pass"
    assert source_status["production_readiness_status"] == "pass"
    assert source_status["noop_receipt_status"] == "pass"


def test_validator_rejects_candidate_id_or_type_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    payload["candidate_id"] = "wrong_candidate_v1"
    payload["candidate_type"] = "publication"
    path = tmp_path / "invalid-candidate-id-and-type.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "candidate_id_mismatch" in finding_ids
    assert "candidate_type_mismatch" in finding_ids


def test_validator_rejects_completeness_or_admission_status_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    payload["completeness_review_status"] = "static_completeness_invalid"
    payload["admission_status"] = "admitted"
    path = tmp_path / "invalid-completeness-and-admission-status.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "completeness_review_status_not_static_completeness_valid_blocked" in finding_ids
    assert "admission_status_not_unadmitted" in finding_ids


def test_validator_rejects_approval_flags_true(tmp_path: Path):
    payload = _clone_base_payload()
    payload["approval_request_ready"] = True
    payload["operator_approval_granted"] = True
    payload["approval_phrase_present"] = True
    path = tmp_path / "invalid-approval-flags.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "approval_request_ready_not_allowed" in finding_ids
    assert "operator_approval_granted_not_allowed" in finding_ids
    assert "approval_phrase_present_not_allowed" in finding_ids


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


def test_validator_rejects_missing_source_artifact_reference(tmp_path: Path):
    payload = _clone_base_payload()
    del payload["source_artifacts"]["operator_approval_packet_ref"]
    path = tmp_path / "invalid-missing-source-ref.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "source_artifacts_missing_required_reference" in _finding_ids(report)


def test_validator_rejects_empty_completeness_or_consistency_checks(tmp_path: Path):
    payload = _clone_base_payload()
    payload["completeness_checks"] = []
    payload["consistency_checks"] = []
    path = tmp_path / "invalid-empty-completeness-consistency-checks.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "completeness_checks_missing_or_empty" in finding_ids
    assert "consistency_checks_missing_or_empty" in finding_ids


def test_validator_rejects_missing_required_status_blocks(tmp_path: Path):
    payload = _clone_base_payload()
    del payload["required_packet_sections_status"]
    del payload["required_cross_references_status"]
    del payload["required_validation_commands_status"]
    del payload["required_forbidden_surface_status"]
    del payload["required_operator_decision_fields_status"]
    del payload["required_rollback_cleanup_status"]
    path = tmp_path / "invalid-missing-required-status-blocks.json"
    _write(path, payload)
    code, _ = _run_validator(path)
    assert code != 0


def test_validator_rejects_required_validation_commands_missing_tokens(tmp_path: Path):
    payload = _clone_base_payload()
    payload["required_validation_commands_status"]["required_validation_commands"] = [
        "tools/execution-admission/validate_execution_admission_candidate_matrix.py"
    ]
    path = tmp_path / "invalid-required-validation-commands-missing-tokens.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "required_validation_commands_missing_preflight_contract_validator" in finding_ids
    assert "required_validation_commands_missing_preflight_proof_validator" in finding_ids
    assert "required_validation_commands_missing_readiness_rollup_validator" in finding_ids
    assert "required_validation_commands_missing_dry_run_plan_validator" in finding_ids
    assert "required_validation_commands_missing_dry_run_receipt_validator" in finding_ids
    assert "required_validation_commands_missing_admission_blocker_validator" in finding_ids
    assert "required_validation_commands_missing_operator_approval_packet_validator" in finding_ids
    assert "required_validation_commands_missing_safety_verifier" in finding_ids
    assert "required_validation_commands_missing_proof_flow" in finding_ids


def test_validator_rejects_required_forbidden_surface_tokens_missing(tmp_path: Path):
    payload = _clone_base_payload()
    payload["required_forbidden_surface_status"]["forbidden_surface_tokens"] = [
        "publication_surfaces_blocked_by_policy"
    ]
    path = tmp_path / "invalid-required-forbidden-surface-tokens.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "required_forbidden_surface_status_missing_execution_surface_token" in finding_ids
    assert "required_forbidden_surface_status_missing_cache_live_db_surface_token" in finding_ids
    assert "required_forbidden_surface_status_missing_production_engine_surface_token" in finding_ids
    assert "required_forbidden_surface_status_missing_authoritative_id_surface_token" in finding_ids


def test_validator_rejects_required_operator_decision_fields_status_values(tmp_path: Path):
    payload = _clone_base_payload()
    payload["required_operator_decision_fields_status"]["decision_fields_populated"] = True
    payload["required_operator_decision_fields_status"][
        "approval_decision_reference_present"
    ] = True
    path = tmp_path / "invalid-required-operator-decision-fields-status.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "required_operator_decision_fields_populated_not_allowed" in finding_ids
    assert (
        "required_operator_decision_fields_approval_reference_present_not_allowed"
        in finding_ids
    )


def test_validator_rejects_required_rollback_cleanup_status_values(tmp_path: Path):
    payload = _clone_base_payload()
    payload["required_rollback_cleanup_status"]["rollback_or_cleanup_required"] = False
    payload["required_rollback_cleanup_status"]["rollback_or_cleanup_evidence_present"] = True
    payload["required_rollback_cleanup_status"]["rollback_or_cleanup_blocked"] = False
    path = tmp_path / "invalid-required-rollback-cleanup-status.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "required_rollback_cleanup_not_required" in finding_ids
    assert "required_rollback_cleanup_evidence_present_not_allowed" in finding_ids
    assert "required_rollback_cleanup_not_blocked" in finding_ids


def test_validator_rejects_unresolved_blockers_missing_required_tokens(tmp_path: Path):
    payload = _clone_base_payload()
    payload["unresolved_approval_blockers"] = ["missing_approval_decision"]
    payload["unresolved_execution_blockers"] = ["dry_run_not_admitted"]
    payload["unresolved_receipt_blockers"] = ["receipt_not_issued"]
    payload["unresolved_publication_blockers"] = ["publication_surfaces_blocked_by_policy"]
    path = tmp_path / "invalid-unresolved-blockers-missing-required-tokens.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "unresolved_approval_blockers_missing_approval_request_not_ready" in finding_ids
    assert "unresolved_approval_blockers_missing_operator_approval_not_granted" in finding_ids
    assert "unresolved_approval_blockers_missing_approval_phrase_not_present" in finding_ids
    assert "unresolved_execution_blockers_missing_dry_run_not_executed" in finding_ids
    assert "unresolved_receipt_blockers_missing_rollback_cleanup_evidence_missing" in finding_ids
    assert "unresolved_publication_blockers_missing_publication_not_admitted" in finding_ids


def test_validator_rejects_empty_unresolved_blocker_lists(tmp_path: Path):
    payload = _clone_base_payload()
    payload["unresolved_approval_blockers"] = []
    payload["unresolved_execution_blockers"] = []
    payload["unresolved_receipt_blockers"] = []
    payload["unresolved_publication_blockers"] = []
    path = tmp_path / "invalid-empty-unresolved-blocker-lists.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "unresolved_approval_blockers_missing_or_empty" in finding_ids
    assert "unresolved_execution_blockers_missing_or_empty" in finding_ids
    assert "unresolved_receipt_blockers_missing_or_empty" in finding_ids
    assert "unresolved_publication_blockers_missing_or_empty" in finding_ids


def test_validator_rejects_language_that_allows_blocked_surfaces(tmp_path: Path):
    payload = _clone_base_payload()
    payload["safety_notes"].extend(
        [
            "publish allowed",
            "spawn allowed",
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
    assert "completeness_review_allows_publish" in finding_ids
    assert "completeness_review_allows_spawn" in finding_ids
    assert "completeness_review_allows_production_path_writes" in finding_ids
    assert "completeness_review_allows_engine_path_writes" in finding_ids
    assert "completeness_review_allows_cache_live_db_access" in finding_ids
    assert "completeness_review_allows_authoritative_source_uuid_claims" in finding_ids
    assert "completeness_review_allows_authoritative_asset_id_claims" in finding_ids
    assert "completeness_review_allows_authoritative_product_id_claims" in finding_ids


def test_validator_rejects_source_artifact_status_not_pass(tmp_path: Path):
    payload = _clone_base_payload()
    payload["source_artifact_validation_status"]["operator_approval_packet_status"] = "fail"
    path = tmp_path / "invalid-source-artifact-validation-status.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "source_artifact_validation_status_not_pass" in _finding_ids(report)


def test_validator_rejects_mismatched_source_artifact_path_and_cross_validator_fails(tmp_path: Path):
    payload = _clone_base_payload()
    payload["source_artifacts"]["operator_approval_packet_ref"] = "examples/execution-admission/nonexistent-operator-packet.json"
    path = tmp_path / "invalid-source-path.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "source_artifact_missing" in finding_ids
    assert "operator_approval_packet_validation_failed" in finding_ids


def test_validator_rejects_rollup_mismatch_target_candidate(tmp_path: Path):
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
    path = tmp_path / "invalid-review-rollup-target.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "readiness_rollup_validation_failed" in finding_ids
    assert "readiness_rollup_next_slice_candidate_mismatch" in finding_ids


def test_validator_rejects_packet_structural_truth_fields_false(tmp_path: Path):
    payload = _clone_base_payload()
    payload["packet_structurally_complete"] = False
    payload["packet_internally_consistent"] = False
    payload["packet_complete_for_future_review_template"] = False
    path = tmp_path / "invalid-packet-structural-truth-fields.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "packet_structurally_complete_not_true" in finding_ids
    assert "packet_internally_consistent_not_true" in finding_ids
    assert "packet_complete_for_future_review_template_not_true" in finding_ids
