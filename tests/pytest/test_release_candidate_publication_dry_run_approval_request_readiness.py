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
    / "maxine_release_candidate_publication_dry_run_approval_request_readiness.schema.json"
)
REPORT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "release_candidate_package_publish_dry_run_approval_request_readiness_v1.json"
)
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_release_candidate_publication_dry_run_approval_request_readiness.py"
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
    return copy.deepcopy(_load(REPORT_EXAMPLE))


def _finding_ids(payload: dict) -> set[str]:
    return {
        str(item.get("id", "")).strip()
        for item in payload.get("findings", [])
        if isinstance(item, dict)
    }


def test_approval_request_readiness_example_validates_and_reports_blocked_posture():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    payload = _load(REPORT_EXAMPLE)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, [f"{'.'.join(str(p) for p in err.path)}: {err.message}" for err in errors]

    code, report = _run_validator(REPORT_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert (
        report["release_candidate_publication_dry_run_approval_request_readiness_present"]
        is True
    )
    assert report["planned_candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert report["candidate_type"] == "dry_run"
    assert report["approval_request_readiness_status"] == "static_request_readiness_valid_blocked"
    assert report["admission_status"] == "unadmitted"
    assert report["packet_structurally_complete"] is True
    assert report["packet_complete_for_future_review_template"] is True
    assert report["approval_request_ready"] is False
    assert report["operator_approval_granted"] is False
    assert report["approval_phrase_present"] is False
    assert report["dry_run_admitted"] is False
    assert report["dry_run_executed"] is False
    assert report["receipt_issued"] is False
    assert report["publication_admitted"] is False
    assert report["real_execution_admitted"] is False
    assert report["production_ready_claimed"] is False
    assert report["final_recommendation"] == "do_not_request_approval_yet"
    assert (
        report["approval_phrase_required"]
        == "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
    )
    assert len(report["request_readiness_blockers"]) > 0
    assert len(report["approval_blockers"]) > 0
    assert len(report["execution_blockers"]) > 0
    assert len(report["receipt_blockers"]) > 0
    assert len(report["publication_blockers"]) > 0
    assert len(report["production_readiness_blockers"]) > 0
    assert len(report["required_before_requesting_approval"]) > 0
    assert len(report["required_validation_commands"]) > 0


def test_validator_cross_checks_all_required_source_artifacts():
    code, report = _run_validator(REPORT_EXAMPLE)
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
    assert source_status["operator_approval_packet_completeness_status"] == "pass"
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


def test_validator_rejects_readiness_or_admission_status_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    payload["approval_request_readiness_status"] = "static_request_readiness_invalid"
    payload["admission_status"] = "admitted"
    path = tmp_path / "invalid-readiness-and-admission-status.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert (
        "approval_request_readiness_status_not_static_request_readiness_valid_blocked"
        in finding_ids
    )
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


def test_validator_rejects_admission_execution_receipt_or_ready_flags(tmp_path: Path):
    payload = _clone_base_payload()
    payload["dry_run_admitted"] = True
    payload["dry_run_executed"] = True
    payload["receipt_issued"] = True
    payload["publication_admitted"] = True
    payload["real_execution_admitted"] = True
    payload["production_ready_claimed"] = True
    path = tmp_path / "invalid-admission-execution-receipt-production-flags.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "dry_run_admitted_not_allowed" in finding_ids
    assert "dry_run_executed_not_allowed" in finding_ids
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
    del payload["source_artifacts"]["operator_approval_packet_completeness_ref"]
    path = tmp_path / "invalid-missing-source-ref.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "source_artifacts_missing_required_reference" in _finding_ids(report)


def test_validator_rejects_missing_readiness_or_structural_summary(tmp_path: Path):
    payload = _clone_base_payload()
    payload["readiness_summary"] = ""
    payload["structural_completeness_summary"] = ""
    path = tmp_path / "invalid-missing-readiness-and-structural-summary.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "readiness_summary_missing_or_empty" in finding_ids
    assert "structural_completeness_summary_missing_or_empty" in finding_ids


def test_validator_rejects_empty_blocker_lists(tmp_path: Path):
    payload = _clone_base_payload()
    payload["request_readiness_blockers"] = []
    payload["approval_blockers"] = []
    payload["execution_blockers"] = []
    payload["receipt_blockers"] = []
    payload["publication_blockers"] = []
    payload["production_readiness_blockers"] = []
    path = tmp_path / "invalid-empty-blocker-lists.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "request_readiness_blockers_missing_or_empty" in finding_ids
    assert "approval_blockers_missing_or_empty" in finding_ids
    assert "execution_blockers_missing_or_empty" in finding_ids
    assert "receipt_blockers_missing_or_empty" in finding_ids
    assert "publication_blockers_missing_or_empty" in finding_ids
    assert "production_readiness_blockers_missing_or_empty" in finding_ids


def test_validator_rejects_required_blocker_tokens_missing(tmp_path: Path):
    payload = _clone_base_payload()
    payload["request_readiness_blockers"] = ["approval_request_not_ready"]
    payload["approval_blockers"] = ["missing_approval_decision"]
    payload["execution_blockers"] = ["dry_run_not_admitted"]
    payload["receipt_blockers"] = ["receipt_not_issued"]
    payload["publication_blockers"] = ["publication_surfaces_blocked_by_policy"]
    payload["production_readiness_blockers"] = ["production_ready_not_claimed"]
    path = tmp_path / "invalid-blocker-tokens-missing.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "request_readiness_blockers_missing_unresolved_approval_blockers_present" in finding_ids
    assert "request_readiness_blockers_missing_no_operator_approval_decision" in finding_ids
    assert "request_readiness_blockers_missing_approval_phrase_not_present" in finding_ids
    assert "approval_blockers_missing_operator_approval_not_granted" in finding_ids
    assert "execution_blockers_missing_dry_run_not_executed" in finding_ids
    assert "receipt_blockers_missing_rollback_cleanup_evidence_missing" in finding_ids
    assert "publication_blockers_missing_publication_not_admitted" in finding_ids
    assert "production_readiness_blockers_missing_real_execution_not_admitted" in finding_ids
    assert "production_readiness_blockers_missing_publication_not_admitted" in finding_ids


def test_validator_rejects_empty_required_before_or_validation_commands(tmp_path: Path):
    payload = _clone_base_payload()
    payload["required_before_requesting_approval"] = []
    payload["required_validation_commands"] = []
    path = tmp_path / "invalid-empty-required-before-or-validation-commands.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "required_before_requesting_approval_missing_or_empty" in finding_ids
    assert "required_validation_commands_missing_or_empty" in finding_ids


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
    assert "required_validation_commands_missing_operator_approval_packet_validator" in finding_ids
    assert "required_validation_commands_missing_operator_approval_packet_completeness_validator" in finding_ids
    assert "required_validation_commands_missing_safety_verifier" in finding_ids
    assert "required_validation_commands_missing_proof_flow" in finding_ids
    assert (
        "required_validation_commands_missing_production_readiness_generated_manifest_validator"
        in finding_ids
    )


def test_validator_rejects_final_recommendation_other_than_do_not_request_approval_yet(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    payload["final_recommendation"] = "request_more_evidence"
    path = tmp_path / "invalid-final-recommendation.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "final_recommendation_not_do_not_request_approval_yet" in _finding_ids(report)


def test_validator_rejects_language_that_allows_blocked_surfaces_or_execution_claims(
    tmp_path: Path,
):
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
    assert "readiness_report_allows_publish" in finding_ids
    assert "readiness_report_allows_spawn" in finding_ids
    assert "readiness_report_allows_production_path_writes" in finding_ids
    assert "readiness_report_allows_engine_path_writes" in finding_ids
    assert "readiness_report_allows_cache_live_db_access" in finding_ids
    assert "readiness_report_allows_authoritative_source_uuid_claims" in finding_ids
    assert "readiness_report_allows_authoritative_asset_id_claims" in finding_ids
    assert "readiness_report_allows_authoritative_product_id_claims" in finding_ids
    assert "readiness_report_claims_dry_run_executed" in finding_ids


def test_validator_rejects_source_artifact_status_not_pass(tmp_path: Path):
    payload = _clone_base_payload()
    payload["source_artifact_validation_status"]["operator_approval_packet_completeness_status"] = "fail"
    path = tmp_path / "invalid-source-artifact-validation-status.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "source_artifact_validation_status_not_pass" in _finding_ids(report)


def test_validator_rejects_operator_packet_completeness_path_mismatch_and_cross_validator_fails(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    payload["source_artifacts"]["operator_approval_packet_completeness_ref"] = (
        "examples/execution-admission/nonexistent-operator-packet-completeness.json"
    )
    path = tmp_path / "invalid-source-path.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "source_artifact_missing" in finding_ids
    assert "operator_approval_packet_completeness_validation_failed" in finding_ids


def test_validator_rejects_packet_completeness_flags_false(tmp_path: Path):
    payload = _clone_base_payload()
    payload["packet_structurally_complete"] = False
    payload["packet_complete_for_future_review_template"] = False
    path = tmp_path / "invalid-packet-completeness-flags.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "packet_structurally_complete_not_true" in finding_ids
    assert "packet_complete_for_future_review_template_not_true" in finding_ids
