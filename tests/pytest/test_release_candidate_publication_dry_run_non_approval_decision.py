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
    / "maxine_release_candidate_publication_dry_run_non_approval_decision.schema.json"
)
DECISION_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "release_candidate_package_publish_dry_run_non_approval_decision_v1.json"
)
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_release_candidate_publication_dry_run_non_approval_decision.py"
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
    return copy.deepcopy(_load(DECISION_EXAMPLE))


def _finding_ids(payload: dict) -> set[str]:
    return {
        str(item.get("id", "")).strip()
        for item in payload.get("findings", [])
        if isinstance(item, dict)
    }


def test_non_approval_decision_example_validates_and_reports_blocked_posture():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    payload = _load(DECISION_EXAMPLE)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, [f"{'.'.join(str(p) for p in err.path)}: {err.message}" for err in errors]

    code, report = _run_validator(DECISION_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["release_candidate_publication_dry_run_non_approval_decision_present"] is True
    assert report["planned_candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert report["candidate_type"] == "dry_run"
    assert report["decision_type"] == "non_approval"
    assert report["decision_status"] == "active_non_approval"
    assert report["decision_effect"] == "candidate_remains_blocked_unadmitted"
    assert report["selected_operator_decision"] == "do_not_approve"
    assert report["next_recommended_action"] == "continue_hardening_no_execution"
    assert report["approval_request_ready"] is False
    assert report["operator_approval_granted"] is False
    assert report["approval_phrase_present"] is False
    assert report["dry_run_admitted"] is False
    assert report["dry_run_executed"] is False
    assert report["receipt_issued"] is False
    assert report["publication_admitted"] is False
    assert report["real_execution_admitted"] is False
    assert report["production_ready_claimed"] is False
    assert (
        report["approval_phrase_required_for_future_reconsideration"]
        == "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
    )
    assert len(report["non_approval_reason_codes"]) > 0
    assert isinstance(report["continuing_blockers"], dict)
    assert len(report["required_before_reconsideration"]) > 0
    assert len(report["forbidden_actions"]) > 0
    assert len(report["forbidden_outputs"]) > 0
    assert len(report["forbidden_paths"]) > 0


def test_validator_cross_checks_all_required_source_artifacts():
    code, report = _run_validator(DECISION_EXAMPLE)
    assert code == 0
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
    assert source_status["operator_approval_packet_completeness_status"] == "pass"
    assert source_status["approval_request_readiness_status"] == "pass"
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


def test_validator_rejects_decision_type_status_or_effect_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    payload["decision_type"] = "approval"
    payload["decision_status"] = "approved"
    payload["decision_effect"] = "candidate_admitted"
    path = tmp_path / "invalid-decision-type-status-effect.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "decision_type_not_non_approval" in finding_ids
    assert "decision_status_not_active_non_approval" in finding_ids
    assert "decision_effect_not_candidate_remains_blocked_unadmitted" in finding_ids


def test_validator_rejects_approval_or_admission_flags_true(tmp_path: Path):
    payload = _clone_base_payload()
    payload["approval_request_ready"] = True
    payload["operator_approval_granted"] = True
    payload["approval_phrase_present"] = True
    payload["dry_run_admitted"] = True
    payload["dry_run_executed"] = True
    payload["receipt_issued"] = True
    payload["publication_admitted"] = True
    payload["real_execution_admitted"] = True
    payload["production_ready_claimed"] = True
    path = tmp_path / "invalid-flags-true.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "approval_request_ready_not_allowed" in finding_ids
    assert "operator_approval_granted_not_allowed" in finding_ids
    assert "approval_phrase_present_not_allowed" in finding_ids
    assert "dry_run_admitted_not_allowed" in finding_ids
    assert "dry_run_executed_not_allowed" in finding_ids
    assert "receipt_issued_not_allowed" in finding_ids
    assert "publication_admitted_not_allowed" in finding_ids
    assert "real_execution_admitted_not_allowed" in finding_ids
    assert "production_ready_claim_not_allowed" in finding_ids


def test_validator_rejects_selected_decision_next_action_phrase_or_reference(tmp_path: Path):
    payload = _clone_base_payload()
    payload["selected_operator_decision"] = "approve"
    payload["next_recommended_action"] = "execute_now"
    payload["approval_phrase_required_for_future_reconsideration"] = "APPROVE EXECUTION ADMISSION wrong_id"
    payload["approval_decision_reference"] = "approved::decision"
    path = tmp_path / "invalid-selected-decision-next-action-phrase-or-reference.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "selected_operator_decision_not_do_not_approve" in finding_ids
    assert "next_recommended_action_not_continue_hardening_no_execution" in finding_ids
    assert "approval_phrase_required_mismatch" in finding_ids
    assert "approval_decision_reference_not_allowed" in finding_ids


def test_validator_rejects_missing_source_artifact_reference(tmp_path: Path):
    payload = _clone_base_payload()
    del payload["source_artifacts"]["approval_request_readiness_ref"]
    path = tmp_path / "invalid-missing-source-ref.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "source_artifacts_missing_required_reference" in _finding_ids(report)


def test_validator_rejects_non_approval_reason_codes_empty_or_missing_tokens(tmp_path: Path):
    payload = _clone_base_payload()
    payload["non_approval_reason_codes"] = []
    path = tmp_path / "invalid-empty-non-approval-reasons.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "non_approval_reason_codes_missing_or_empty" in _finding_ids(report)

    payload2 = _clone_base_payload()
    payload2["non_approval_reason_codes"] = ["approval_request_not_ready"]
    path2 = tmp_path / "invalid-missing-required-reason-tokens.json"
    _write(path2, payload2)
    code2, report2 = _run_validator(path2)
    assert code2 != 0
    finding_ids2 = _finding_ids(report2)
    assert (
        "non_approval_reason_codes_missing_readiness_report_recommends_do_not_request_approval_yet"
        in finding_ids2
    )
    assert "non_approval_reason_codes_missing_no_operator_approval_decision" in finding_ids2
    assert "non_approval_reason_codes_missing_approval_phrase_not_present" in finding_ids2
    assert "non_approval_reason_codes_missing_dry_run_not_admitted" in finding_ids2
    assert "non_approval_reason_codes_missing_dry_run_not_executed" in finding_ids2
    assert "non_approval_reason_codes_missing_receipt_not_issued" in finding_ids2
    assert "non_approval_reason_codes_missing_rollback_cleanup_evidence_missing" in finding_ids2
    assert (
        "non_approval_reason_codes_missing_publication_surfaces_blocked_by_policy"
        in finding_ids2
    )
    assert "non_approval_reason_codes_missing_publication_not_admitted" in finding_ids2
    assert "non_approval_reason_codes_missing_real_execution_not_admitted" in finding_ids2
    assert "non_approval_reason_codes_missing_production_ready_not_claimed" in finding_ids2


def test_validator_rejects_continuing_blockers_missing_or_missing_required_tokens(tmp_path: Path):
    payload = _clone_base_payload()
    payload["continuing_blockers"] = {}
    path = tmp_path / "invalid-missing-continuing-blockers.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "continuing_blockers_missing_or_empty" in _finding_ids(report)

    payload2 = _clone_base_payload()
    payload2["continuing_blockers"]["approval_blockers"] = ["missing_approval_decision"]
    payload2["continuing_blockers"]["request_readiness_blockers"] = ["approval_request_not_ready"]
    payload2["continuing_blockers"]["execution_blockers"] = ["dry_run_not_admitted"]
    payload2["continuing_blockers"]["receipt_blockers"] = ["receipt_not_issued"]
    payload2["continuing_blockers"]["publication_blockers"] = ["publication_surfaces_blocked_by_policy"]
    payload2["continuing_blockers"]["production_readiness_blockers"] = ["production_ready_not_claimed"]
    path2 = tmp_path / "invalid-continuing-blockers-missing-tokens.json"
    _write(path2, payload2)
    code2, report2 = _run_validator(path2)
    assert code2 != 0
    finding_ids2 = _finding_ids(report2)
    assert (
        "continuing_blockers_approval_blockers_missing_operator_approval_not_granted"
        in finding_ids2
    )
    assert (
        "continuing_blockers_request_readiness_blockers_missing_unresolved_approval_blockers_present"
        in finding_ids2
    )
    assert (
        "continuing_blockers_request_readiness_blockers_missing_no_operator_approval_decision"
        in finding_ids2
    )
    assert (
        "continuing_blockers_request_readiness_blockers_missing_approval_phrase_not_present"
        in finding_ids2
    )
    assert "continuing_blockers_execution_blockers_missing_dry_run_not_executed" in finding_ids2
    assert (
        "continuing_blockers_receipt_blockers_missing_rollback_cleanup_evidence_missing"
        in finding_ids2
    )
    assert "continuing_blockers_publication_blockers_missing_publication_not_admitted" in finding_ids2
    assert (
        "continuing_blockers_production_readiness_blockers_missing_real_execution_not_admitted"
        in finding_ids2
    )
    assert (
        "continuing_blockers_production_readiness_blockers_missing_publication_not_admitted"
        in finding_ids2
    )


def test_validator_rejects_required_before_or_forbidden_lists_empty(tmp_path: Path):
    payload = _clone_base_payload()
    payload["required_before_reconsideration"] = []
    payload["forbidden_actions"] = []
    payload["forbidden_outputs"] = []
    payload["forbidden_paths"] = []
    path = tmp_path / "invalid-required-before-or-forbidden-lists-empty.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "required_before_reconsideration_missing_or_empty" in finding_ids
    assert "forbidden_actions_missing_or_empty" in finding_ids
    assert "forbidden_outputs_missing_or_empty" in finding_ids
    assert "forbidden_paths_missing_or_empty" in finding_ids


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
            "dry-run executed",
        ]
    )
    path = tmp_path / "invalid-language-allows-blocked-surfaces.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "non_approval_record_allows_publish" in finding_ids
    assert "non_approval_record_allows_spawn" in finding_ids
    assert "non_approval_record_allows_production_path_writes" in finding_ids
    assert "non_approval_record_allows_engine_path_writes" in finding_ids
    assert "non_approval_record_allows_cache_live_db_access" in finding_ids
    assert "non_approval_record_allows_authoritative_source_uuid_claims" in finding_ids
    assert "non_approval_record_allows_authoritative_asset_id_claims" in finding_ids
    assert "non_approval_record_allows_authoritative_product_id_claims" in finding_ids
    assert "non_approval_record_claims_dry_run_executed" in finding_ids


def test_validator_rejects_source_artifact_validation_status_not_pass(tmp_path: Path):
    payload = _clone_base_payload()
    payload["source_artifact_validation_status"]["approval_request_readiness_status"] = "fail"
    path = tmp_path / "invalid-source-artifact-validation-status.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "source_artifact_validation_status_not_pass" in _finding_ids(report)


def test_validator_rejects_approval_request_readiness_source_missing_and_cross_validator_fails(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    payload["source_artifacts"]["approval_request_readiness_ref"] = (
        "examples/execution-admission/nonexistent-approval-request-readiness.json"
    )
    path = tmp_path / "invalid-readiness-source-missing.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "source_artifact_missing" in finding_ids
    assert "approval_request_readiness_validation_failed" in finding_ids
