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
    / "maxine_release_candidate_publication_dry_run_operator_approval_packet.schema.json"
)
PACKET_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "release_candidate_package_publish_dry_run_operator_approval_packet_v1.json"
)
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_release_candidate_publication_dry_run_operator_approval_packet.py"
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
    return copy.deepcopy(_load(PACKET_EXAMPLE))


def _finding_ids(payload: dict) -> set[str]:
    return {
        str(item.get("id", "")).strip()
        for item in payload.get("findings", [])
        if isinstance(item, dict)
    }


def test_operator_approval_packet_example_validates_and_reports_blocked_posture():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    payload = _load(PACKET_EXAMPLE)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, [f"{'.'.join(str(p) for p in err.path)}: {err.message}" for err in errors]

    code, report = _run_validator(PACKET_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["release_candidate_publication_dry_run_operator_approval_packet_present"] is True
    assert report["planned_candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert report["candidate_type"] == "dry_run"
    assert report["approval_packet_status"] == "static_template_valid_blocked"
    assert report["admission_status"] == "unadmitted"
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
    assert len(report["approval_blocker_summary"]) > 0
    assert len(report["required_operator_review_items"]) > 0
    assert len(report["required_validation_commands"]) > 0
    assert len(report["blocked_surface_attestations"]) > 0
    assert len(report["forbidden_actions"]) > 0
    assert len(report["forbidden_outputs"]) > 0
    assert len(report["forbidden_paths"]) > 0


def test_validator_cross_checks_all_required_source_artifacts():
    code, report = _run_validator(PACKET_EXAMPLE)
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


def test_validator_rejects_packet_status_or_admission_status_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    payload["approval_packet_status"] = "static_template_invalid"
    payload["admission_status"] = "admitted"
    path = tmp_path / "invalid-packet-status-and-admission-status.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "approval_packet_status_not_static_template_valid_blocked" in finding_ids
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
    del payload["source_artifacts"]["admission_blocker_checklist_ref"]
    path = tmp_path / "invalid-missing-source-ref.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "source_artifacts_missing_required_reference" in _finding_ids(report)


def test_validator_rejects_empty_required_lists(tmp_path: Path):
    payload = _clone_base_payload()
    payload["approval_blocker_summary"] = []
    payload["required_operator_review_items"] = []
    payload["required_validation_commands"] = []
    payload["rollback_or_cleanup_expectations"] = []
    payload["blocked_surface_attestations"] = []
    payload["forbidden_actions"] = []
    payload["forbidden_outputs"] = []
    payload["forbidden_paths"] = []
    path = tmp_path / "invalid-empty-required-lists.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "approval_blocker_summary_missing_or_empty" in finding_ids
    assert "required_operator_review_items_missing_or_empty" in finding_ids
    assert "required_validation_commands_missing_or_empty" in finding_ids
    assert "rollback_or_cleanup_expectations_missing_or_empty" in finding_ids
    assert "blocked_surface_attestations_missing_or_empty" in finding_ids
    assert "forbidden_actions_missing_or_empty" in finding_ids
    assert "forbidden_outputs_missing_or_empty" in finding_ids
    assert "forbidden_paths_missing_or_empty" in finding_ids


def test_validator_rejects_missing_expected_future_receipt_contract(tmp_path: Path):
    payload = _clone_base_payload()
    payload["expected_future_receipt_contract"] = {}
    path = tmp_path / "invalid-missing-expected-future-receipt-contract.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "expected_future_receipt_contract_type_mismatch" in finding_ids
    assert "expected_future_receipt_contract_status_mismatch" in finding_ids
    assert "expected_future_receipt_contract_ref_mismatch" in finding_ids


def test_validator_rejects_operator_decision_default_that_approves(tmp_path: Path):
    payload = _clone_base_payload()
    payload["operator_decision_options"]["default_option"] = "approve_later_with_exact_phrase"
    path = tmp_path / "invalid-approving-default-operator-option.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "operator_decision_default_not_safe_blocked_state" in _finding_ids(report)


def test_validator_rejects_required_validation_commands_missing_tokens(tmp_path: Path):
    payload = _clone_base_payload()
    payload["required_validation_commands"] = [
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
    assert "required_validation_commands_missing_safety_verifier" in finding_ids
    assert "required_validation_commands_missing_proof_flow" in finding_ids


def test_validator_rejects_required_operator_review_items_missing_tokens(tmp_path: Path):
    payload = _clone_base_payload()
    payload["required_operator_review_items"] = ["candidate_identity_and_candidate_type"]
    path = tmp_path / "invalid-required-operator-review-items-missing-tokens.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "required_operator_review_items_missing_current_admission_status" in _finding_ids(report)


def test_validator_rejects_forbidden_lists_missing_categories(tmp_path: Path):
    payload = _clone_base_payload()
    payload["forbidden_paths"] = ["production_path_category"]
    payload["forbidden_outputs"] = ["publish_operation"]
    payload["forbidden_actions"] = ["publish_operation"]
    path = tmp_path / "invalid-forbidden-lists-missing-categories.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "forbidden_paths_missing_engine_category" in finding_ids
    assert "forbidden_paths_missing_cache_live_db_category" in finding_ids
    assert "packet_allows_spawn" in finding_ids
    assert "packet_allows_production_path_writes" in finding_ids
    assert "packet_allows_engine_path_writes" in finding_ids
    assert "packet_allows_cache_live_db_access" in finding_ids
    assert "packet_allows_authoritative_source_uuid_claims" in finding_ids
    assert "packet_allows_authoritative_asset_id_claims" in finding_ids
    assert "packet_allows_authoritative_product_id_claims" in finding_ids
    assert "forbidden_actions_missing_spawn_category" in finding_ids


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
    assert "packet_allows_publish" in finding_ids
    assert "packet_allows_spawn" in finding_ids
    assert "packet_allows_production_path_writes" in finding_ids
    assert "packet_allows_engine_path_writes" in finding_ids
    assert "packet_allows_cache_live_db_access" in finding_ids
    assert "packet_allows_authoritative_source_uuid_claims" in finding_ids
    assert "packet_allows_authoritative_asset_id_claims" in finding_ids
    assert "packet_allows_authoritative_product_id_claims" in finding_ids


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
    path = tmp_path / "invalid-packet-rollup-target.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "readiness_rollup_validation_failed" in finding_ids
    assert "readiness_rollup_safest_next_candidate_mismatch" in finding_ids


def test_validator_rejects_dry_run_receipt_or_blocker_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    receipt_contract = _load(
        REPO_ROOT
        / "examples"
        / "execution-admission"
        / "release_candidate_package_publish_dry_run_receipt_contract_v1.json"
    )
    blockers = _load(
        REPO_ROOT
        / "examples"
        / "execution-admission"
        / "release_candidate_package_publish_dry_run_admission_blockers_v1.json"
    )
    receipt_contract["receipt_issued"] = True
    blockers["approval_review_ready"] = True
    receipt_path = tmp_path / "invalid-receipt-contract.json"
    blockers_path = tmp_path / "invalid-admission-blockers.json"
    _write(receipt_path, receipt_contract)
    _write(blockers_path, blockers)
    payload["source_artifacts"]["dry_run_receipt_contract_ref"] = str(receipt_path)
    payload["source_artifacts"]["admission_blocker_checklist_ref"] = str(blockers_path)
    path = tmp_path / "invalid-packet-receipt-and-blockers.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "dry_run_receipt_contract_validation_failed" in finding_ids
    assert "admission_blockers_validation_failed" in finding_ids
