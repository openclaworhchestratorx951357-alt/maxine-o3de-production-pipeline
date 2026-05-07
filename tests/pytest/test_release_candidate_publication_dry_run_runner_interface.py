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
    / "maxine_release_candidate_publication_dry_run_runner_interface.schema.json"
)
INTERFACE_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "release_candidate_package_publish_dry_run_runner_interface_v1.json"
)
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_release_candidate_publication_dry_run_runner_interface.py"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_validator(path: Path, skip_source_validators: bool = False) -> tuple[int, dict]:
    cmd = [sys.executable, str(VALIDATOR), str(path)]
    if skip_source_validators:
        cmd.append("--skip-source-validators")
    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    start = result.stdout.find("{")
    assert (
        start >= 0
    ), f"expected JSON output:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    return result.returncode, json.loads(result.stdout[start:])


def _clone_base_payload() -> dict:
    return copy.deepcopy(_load(INTERFACE_EXAMPLE))


def _finding_ids(payload: dict) -> set[str]:
    return {
        str(item.get("id", "")).strip()
        for item in payload.get("findings", [])
        if isinstance(item, dict)
    }


def test_runner_interface_example_validates_and_reports_blocked_posture():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    payload = _load(INTERFACE_EXAMPLE)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, [f"{'.'.join(str(p) for p in err.path)}: {err.message}" for err in errors]

    code, report = _run_validator(INTERFACE_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["release_candidate_publication_dry_run_runner_interface_present"] is True
    assert report["planned_candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert report["candidate_type"] == "dry_run"
    assert report["runner_interface_status"] == "static_interface_valid_blocked"
    assert report["admission_status"] == "unadmitted"
    assert report["runner_implemented"] is False
    assert report["runner_admitted"] is False
    assert report["runner_executed"] is False
    assert report["approval_request_ready"] is False
    assert report["operator_approval_granted"] is False
    assert report["approval_phrase_present"] is False
    assert report["dry_run_admitted"] is False
    assert report["dry_run_executed"] is False
    assert report["receipt_issued"] is False
    assert report["publication_admitted"] is False
    assert report["real_execution_admitted"] is False
    assert report["production_ready_claimed"] is False
    assert report["current_lifecycle_state"] == "not_started"
    assert len(report["interface_lifecycle_states"]) > 0
    assert len(report["required_inputs"]) > 0
    assert len(report["forbidden_inputs"]) > 0
    assert len(report["required_outputs"]) > 0
    assert report["current_emitted_outputs"] == []
    assert len(report["forbidden_outputs"]) > 0
    assert len(report["boundary_validation_requirements"]) > 0
    assert len(report["receipt_contract_requirements"]) > 0
    assert len(report["fail_closed_requirements"]) > 0
    assert len(report["forbidden_runtime_calls"]) > 0
    assert len(report["forbidden_filesystem_operations"]) > 0
    assert len(report["invalidation_conditions"]) > 0
    assert len(report["allowed_runner_modes"]) > 0
    assert len(report["disallowed_runner_modes"]) > 0


def test_validator_cross_checks_all_required_source_artifacts():
    code, report = _run_validator(INTERFACE_EXAMPLE)
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
    assert source_status["non_approval_decision_status"] == "pass"
    assert source_status["sandbox_boundary_status"] == "pass"
    assert source_status["production_readiness_status"] == "pass"
    assert source_status["noop_receipt_status"] == "pass"


def test_validator_rejects_candidate_type_status_admission_and_runner_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    payload["candidate_id"] = "wrong_candidate_v1"
    payload["candidate_type"] = "publication"
    payload["runner_interface_status"] = "static_interface_invalid"
    payload["admission_status"] = "admitted"
    payload["decision_type"] = "approval"
    payload["runner_implemented"] = True
    payload["runner_admitted"] = True
    payload["runner_executed"] = True
    payload["current_lifecycle_state"] = "running"
    path = tmp_path / "invalid-candidate-status-admission-runner.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "candidate_id_mismatch" in finding_ids
    assert "candidate_type_mismatch" in finding_ids
    assert "runner_interface_status_not_static_interface_valid_blocked" in finding_ids
    assert "admission_status_not_unadmitted" in finding_ids
    assert "decision_type_not_non_approval" in finding_ids
    assert "runner_implemented_not_allowed" in finding_ids
    assert "runner_admitted_not_allowed" in finding_ids
    assert "runner_executed_not_allowed" in finding_ids
    assert "current_lifecycle_state_not_safe_not_started" in finding_ids


def test_validator_rejects_approval_admission_execution_receipt_publication_flags_true(
    tmp_path: Path,
):
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
    code, report = _run_validator(path, skip_source_validators=True)
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


def test_validator_rejects_missing_source_reference(tmp_path: Path):
    payload = _clone_base_payload()
    del payload["source_artifacts"]["sandbox_boundary_ref"]
    path = tmp_path / "invalid-missing-source-reference.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    assert "source_artifacts_missing_required_reference" in _finding_ids(report)


def test_validator_rejects_empty_interface_lists_and_missing_structural_fields(tmp_path: Path):
    payload = _clone_base_payload()
    payload["interface_lifecycle_states"] = []
    payload["required_inputs"] = []
    payload["forbidden_inputs"] = []
    payload["required_outputs"] = []
    payload["forbidden_outputs"] = []
    payload["boundary_validation_requirements"] = []
    payload["receipt_contract_requirements"] = []
    payload["fail_closed_requirements"] = []
    payload["pre_run_validation_requirements"] = []
    payload["post_run_validation_requirements"] = []
    payload["required_safety_attestations"] = []
    payload["forbidden_runtime_calls"] = []
    payload["forbidden_filesystem_operations"] = []
    payload["invalidation_conditions"] = []
    payload["required_receipt_fields"] = []
    payload["required_log_report_fields"] = []
    payload["allowed_runner_modes"] = []
    payload["disallowed_runner_modes"] = []
    payload["future_admission_requirements"] = []
    payload["safety_notes"] = []
    payload["current_emitted_outputs"] = ["future_dry_run_receipt"]
    path = tmp_path / "invalid-empty-lists-and-objects.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "interface_lifecycle_states_missing_or_empty" in finding_ids
    assert "required_inputs_missing_or_empty" in finding_ids
    assert "forbidden_inputs_missing_or_empty" in finding_ids
    assert "required_outputs_missing_or_empty" in finding_ids
    assert "forbidden_outputs_missing_or_empty" in finding_ids
    assert "boundary_validation_requirements_missing_or_empty" in finding_ids
    assert "receipt_contract_requirements_missing_or_empty" in finding_ids
    assert "fail_closed_requirements_missing_or_empty" in finding_ids
    assert "forbidden_runtime_calls_missing_or_empty" in finding_ids
    assert "forbidden_filesystem_operations_missing_or_empty" in finding_ids
    assert "invalidation_conditions_missing_or_empty" in finding_ids
    assert "allowed_runner_modes_missing_or_empty" in finding_ids
    assert "disallowed_runner_modes_missing_or_empty" in finding_ids
    assert "future_admission_requirements_missing_or_empty" in finding_ids
    assert "safety_notes_missing_or_empty" in finding_ids
    assert "current_emitted_outputs_not_empty" in finding_ids


def test_validator_rejects_missing_token_coverage_for_inputs_outputs_and_lifecycle(tmp_path: Path):
    payload = _clone_base_payload()
    payload["interface_lifecycle_states"] = ["validating_sources"]
    payload["required_inputs"] = ["candidate_matrix"]
    payload["forbidden_inputs"] = ["live_o3de_runtime_state"]
    payload["required_outputs"] = ["dry_run_validation_report"]
    payload["forbidden_outputs"] = ["production_publication_output"]
    path = tmp_path / "invalid-token-coverage-core.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "interface_lifecycle_states_missing_not_started" in finding_ids
    assert "required_inputs_missing_preflight_contracts" in finding_ids
    assert "required_inputs_missing_sandbox_boundary" in finding_ids
    assert "forbidden_inputs_missing_editor_runtime_state" in finding_ids
    assert "forbidden_inputs_missing_authoritative_id_claims" in finding_ids
    assert "required_outputs_must_be_future_only" in finding_ids
    assert "forbidden_outputs_missing_spawn_output" in finding_ids
    assert "forbidden_outputs_missing_engine_writes" in finding_ids
    assert "forbidden_outputs_missing_cache_live_db_writes" in finding_ids
    assert "forbidden_outputs_missing_authoritative_product_id_claims" in finding_ids


def test_validator_rejects_missing_boundary_receipt_fail_closed_tokens(tmp_path: Path):
    payload = _clone_base_payload()
    payload["boundary_validation_requirements"] = ["load_sandbox_boundary_contract"]
    payload["receipt_contract_requirements"] = ["load_receipt_contract"]
    payload["fail_closed_requirements"] = ["fail_before_write_on_invalid_boundary"]
    path = tmp_path / "invalid-boundary-receipt-failclosed.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "boundary_validation_requirements_missing_path_normalization" in finding_ids
    assert "boundary_validation_requirements_missing_fail_closed_behavior" in finding_ids
    assert "receipt_contract_requirements_missing_receipt_type" in finding_ids
    assert "fail_closed_requirements_missing_missing_admission_failure" in finding_ids
    assert "fail_closed_requirements_missing_live_invocation_failure" in finding_ids
    assert "fail_closed_requirements_missing_publish_spawn_failure" in finding_ids
    assert "fail_closed_requirements_missing_cache_live_db_failure" in finding_ids


def test_validator_rejects_missing_runtime_filesystem_invalidation_and_modes_tokens(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    payload["forbidden_runtime_calls"] = ["o3de_execution"]
    payload["forbidden_filesystem_operations"] = ["production_writes"]
    payload["invalidation_conditions"] = ["write_outside_allowed_sandbox_root"]
    payload["allowed_runner_modes"] = ["execution_mode"]
    payload["disallowed_runner_modes"] = ["execution_mode"]
    path = tmp_path / "invalid-runtime-fs-invalidation-modes.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "forbidden_runtime_calls_missing_editor_runtime_execution" in finding_ids
    assert "forbidden_runtime_calls_missing_asset_processor_execution" in finding_ids
    assert "forbidden_runtime_calls_missing_blender_dcc_execution" in finding_ids
    assert "forbidden_runtime_calls_missing_spawn_publish" in finding_ids
    assert "forbidden_filesystem_operations_missing_engine_writes" in finding_ids
    assert "forbidden_filesystem_operations_missing_cache_live_db_writes" in finding_ids
    assert "invalidation_conditions_missing_live_tool_invocation" in finding_ids
    assert "invalidation_conditions_missing_spawn_publish_attempt" in finding_ids
    assert "invalidation_conditions_missing_receipt_without_admission" in finding_ids
    assert "invalidation_conditions_missing_authoritative_id_claim" in finding_ids
    assert "allowed_runner_modes_not_static_contract_only" in finding_ids
    assert "allowed_runner_modes_include_execution_or_admission" in finding_ids
    assert "disallowed_runner_modes_missing_admission_mode" in finding_ids
    assert "disallowed_runner_modes_missing_publication_mode" in finding_ids
    assert "disallowed_runner_modes_missing_spawn_mode" in finding_ids
    assert "disallowed_runner_modes_missing_live_runtime_mode" in finding_ids
    assert "disallowed_runner_modes_missing_receipt_emission_mode" in finding_ids


def test_validator_rejects_forbidden_claim_language_and_unsafe_claims(tmp_path: Path):
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
            "runner implemented",
            "runner admitted",
            "runner executed",
            "dry-run executed",
        ]
    )
    payload["unsafe_claims_detected"] = True
    path = tmp_path / "invalid-language-allows-blocked-surfaces.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "runner_interface_allows_publish" in finding_ids
    assert "runner_interface_allows_spawn" in finding_ids
    assert "runner_interface_allows_production_path_writes" in finding_ids
    assert "runner_interface_allows_engine_path_writes" in finding_ids
    assert "runner_interface_allows_cache_live_db_access" in finding_ids
    assert "runner_interface_allows_authoritative_source_uuid_claims" in finding_ids
    assert "runner_interface_allows_authoritative_asset_id_claims" in finding_ids
    assert "runner_interface_allows_authoritative_product_id_claims" in finding_ids
    assert "runner_interface_claims_runner_implemented" in finding_ids
    assert "runner_interface_claims_runner_admitted" in finding_ids
    assert "runner_interface_claims_runner_executed" in finding_ids
    assert "runner_interface_claims_dry_run_executed" in finding_ids
    assert "unsafe_claims_detected_not_allowed" in finding_ids


def test_validator_rejects_source_artifact_validation_status_not_pass(tmp_path: Path):
    payload = _clone_base_payload()
    payload["source_artifact_validation_status"]["sandbox_boundary_status"] = "fail"
    path = tmp_path / "invalid-source-artifact-validation-status.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    assert "source_artifact_validation_status_not_pass" in _finding_ids(report)


def test_validator_rejects_missing_sandbox_boundary_source_and_cross_validator_failure(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    payload["source_artifacts"]["sandbox_boundary_ref"] = (
        "examples/execution-admission/nonexistent-sandbox-boundary.json"
    )
    path = tmp_path / "invalid-sandbox-boundary-source-path.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "source_artifact_missing" in finding_ids
    assert "sandbox_boundary_validation_failed" in finding_ids
