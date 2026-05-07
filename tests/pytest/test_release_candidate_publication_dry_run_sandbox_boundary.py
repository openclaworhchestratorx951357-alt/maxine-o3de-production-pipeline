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
    / "maxine_release_candidate_publication_dry_run_sandbox_boundary.schema.json"
)
BOUNDARY_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "release_candidate_package_publish_dry_run_sandbox_boundary_v1.json"
)
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_release_candidate_publication_dry_run_sandbox_boundary.py"
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
    assert start >= 0, f"expected JSON output:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    return result.returncode, json.loads(result.stdout[start:])


def _clone_base_payload() -> dict:
    return copy.deepcopy(_load(BOUNDARY_EXAMPLE))


def _finding_ids(payload: dict) -> set[str]:
    return {
        str(item.get("id", "")).strip()
        for item in payload.get("findings", [])
        if isinstance(item, dict)
    }


def test_sandbox_boundary_example_validates_and_reports_blocked_posture():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    payload = _load(BOUNDARY_EXAMPLE)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, [f"{'.'.join(str(p) for p in err.path)}: {err.message}" for err in errors]

    code, report = _run_validator(BOUNDARY_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["release_candidate_publication_dry_run_sandbox_boundary_present"] is True
    assert report["planned_candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert report["candidate_type"] == "dry_run"
    assert report["sandbox_boundary_status"] == "static_boundary_valid_blocked"
    assert report["admission_status"] == "unadmitted"
    assert report["runner_implemented"] is False
    assert report["approval_request_ready"] is False
    assert report["operator_approval_granted"] is False
    assert report["approval_phrase_present"] is False
    assert report["dry_run_admitted"] is False
    assert report["dry_run_executed"] is False
    assert report["receipt_issued"] is False
    assert report["publication_admitted"] is False
    assert report["real_execution_admitted"] is False
    assert report["production_ready_claimed"] is False
    assert len(report["allowed_read_roots"]) > 0
    assert len(report["allowed_write_roots"]) > 0
    assert len(report["allowed_receipt_roots"]) > 0
    assert len(report["allowed_report_roots"]) > 0
    assert len(report["forbidden_roots"]) > 0
    assert len(report["forbidden_path_patterns"]) > 0
    assert len(report["allowed_file_extensions"]) > 0
    assert len(report["forbidden_file_extensions"]) > 0
    assert len(report["required_path_normalization"]) > 0
    assert len(report["cleanup_rollback_requirements"]) > 0
    assert len(report["live_surface_blocks"]) > 0
    assert len(report["invalidation_conditions"]) > 0


def test_validator_cross_checks_all_required_source_artifacts():
    code, report = _run_validator(BOUNDARY_EXAMPLE)
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
    assert source_status["production_readiness_status"] == "pass"
    assert source_status["noop_receipt_status"] == "pass"


def test_validator_rejects_candidate_type_status_admission_or_runner_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    payload["candidate_id"] = "wrong_candidate_v1"
    payload["candidate_type"] = "publication"
    payload["sandbox_boundary_status"] = "static_boundary_invalid"
    payload["admission_status"] = "admitted"
    payload["runner_implemented"] = True
    path = tmp_path / "invalid-candidate-status-admission-runner.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "candidate_id_mismatch" in finding_ids
    assert "candidate_type_mismatch" in finding_ids
    assert "sandbox_boundary_status_not_static_boundary_valid_blocked" in finding_ids
    assert "admission_status_not_unadmitted" in finding_ids
    assert "runner_implemented_not_allowed" in finding_ids


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
    del payload["source_artifacts"]["non_approval_decision_ref"]
    path = tmp_path / "invalid-missing-source-reference.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    assert "source_artifacts_missing_required_reference" in _finding_ids(report)


def test_validator_rejects_empty_boundary_lists_and_missing_structural_objects(tmp_path: Path):
    payload = _clone_base_payload()
    payload["allowed_read_roots"] = []
    payload["allowed_write_roots"] = []
    payload["allowed_receipt_roots"] = []
    payload["allowed_report_roots"] = []
    payload["forbidden_roots"] = []
    payload["forbidden_path_patterns"] = []
    payload["allowed_file_extensions"] = []
    payload["forbidden_file_extensions"] = []
    payload["required_path_normalization"] = []
    payload["cleanup_rollback_requirements"] = []
    payload["live_surface_blocks"] = []
    payload["invalidation_conditions"] = []
    payload["required_output_index"] = {}
    payload["required_hashing"] = {}
    payload["runner_interface_constraints"] = {}
    path = tmp_path / "invalid-empty-lists-and-objects.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "allowed_read_roots_missing_or_empty" in finding_ids
    assert "allowed_write_roots_missing_or_empty" in finding_ids
    assert "allowed_receipt_roots_missing_or_empty" in finding_ids
    assert "allowed_report_roots_missing_or_empty" in finding_ids
    assert "forbidden_roots_missing_or_empty" in finding_ids
    assert "forbidden_path_patterns_missing_or_empty" in finding_ids
    assert "allowed_file_extensions_missing_or_empty" in finding_ids
    assert "forbidden_file_extensions_missing_or_empty" in finding_ids
    assert "required_path_normalization_missing_or_empty" in finding_ids
    assert "cleanup_rollback_requirements_missing_or_empty" in finding_ids
    assert "live_surface_blocks_missing_or_empty" in finding_ids
    assert "invalidation_conditions_missing_or_empty" in finding_ids
    assert "required_output_index_missing" in finding_ids
    assert "required_hashing_missing" in finding_ids
    assert "runner_interface_constraints_missing" in finding_ids


def test_validator_rejects_allowed_write_roots_outside_sandbox_and_blocked_categories(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    payload["allowed_write_roots"] = [
        "engine/output/",
        "production/output/",
        "examples/sandbox/cache/live-db/",
        "examples/sandbox/publish/export/",
        "C:/temp/out/"
    ]
    path = tmp_path / "invalid-allowed-write-roots.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "allowed_write_root_under_engine_path" in finding_ids
    assert "allowed_write_root_under_production_path" in finding_ids
    assert "allowed_write_root_under_cache_live_db_path" in finding_ids
    assert "allowed_write_root_under_publish_export_path" in finding_ids
    assert "allowed_write_root_absolute_or_uncontrolled" in finding_ids


def test_validator_rejects_missing_forbidden_root_and_pattern_tokens(tmp_path: Path):
    payload = _clone_base_payload()
    payload["forbidden_roots"] = ["engine_root_paths"]
    payload["forbidden_path_patterns"] = ["parent_traversal"]
    path = tmp_path / "invalid-forbidden-roots-and-patterns.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "forbidden_roots_missing_production_category" in finding_ids
    assert "forbidden_roots_missing_cache_live_db_category" in finding_ids
    assert "forbidden_roots_missing_publish_export_category" in finding_ids
    assert "forbidden_roots_missing_destructive_cleanup_category" in finding_ids
    assert "forbidden_path_patterns_missing_absolute_path_escape" in finding_ids


def test_validator_rejects_extension_and_normalization_mismatches(tmp_path: Path):
    payload = _clone_base_payload()
    payload["allowed_file_extensions"] = [".json", ".exe"]
    payload["forbidden_file_extensions"] = [".exe"]
    payload["required_path_normalization"] = ["no_parent_traversal"]
    path = tmp_path / "invalid-extensions-and-normalization.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "allowed_file_extensions_missing_required_static_formats" in finding_ids
    assert "allowed_file_extensions_include_executable_or_binary" in finding_ids
    assert "forbidden_file_extensions_missing_required_class" in finding_ids
    assert "required_path_normalization_missing_no_symlink_escape" in finding_ids
    assert "required_path_normalization_missing_no_junction_escape" in finding_ids
    assert "required_path_normalization_missing_canonical_sandbox_containment" in finding_ids


def test_validator_rejects_missing_live_surface_and_invalidation_tokens(tmp_path: Path):
    payload = _clone_base_payload()
    payload["live_surface_blocks"] = ["o3de_execution"]
    payload["invalidation_conditions"] = ["write_outside_allowed_sandbox_root"]
    path = tmp_path / "invalid-live-surface-and-invalidation-tokens.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "live_surface_blocks_missing_editor_runtime_execution" in finding_ids
    assert "live_surface_blocks_missing_asset_processor_execution" in finding_ids
    assert "live_surface_blocks_missing_blender_dcc_execution" in finding_ids
    assert "live_surface_blocks_missing_spawn_publish" in finding_ids
    assert "live_surface_blocks_missing_cache_live_db_access" in finding_ids
    assert "live_surface_blocks_missing_production_engine_writes" in finding_ids
    assert "invalidation_conditions_missing_live_runtime_tool_invocation" in finding_ids
    assert "invalidation_conditions_missing_spawn_publish_attempt" in finding_ids
    assert "invalidation_conditions_missing_receipt_without_admission" in finding_ids
    assert "invalidation_conditions_missing_authoritative_id_claim" in finding_ids


def test_validator_rejects_runner_interface_constraints_that_imply_runner_implemented(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    payload["runner_interface_constraints"]["runner_implemented"] = True
    payload["runner_interface_constraints"]["future_runner_requires_separate_proposal"] = False
    path = tmp_path / "invalid-runner-interface-constraints.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "runner_interface_constraints_runner_implemented_not_false" in finding_ids
    assert "runner_interface_constraints_missing_separate_proposal_requirement" in finding_ids


def test_validator_rejects_language_that_allows_blocked_surfaces_or_claims(tmp_path: Path):
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
            "dry-run executed",
        ]
    )
    path = tmp_path / "invalid-language-allows-blocked-surfaces.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "sandbox_boundary_allows_publish" in finding_ids
    assert "sandbox_boundary_allows_spawn" in finding_ids
    assert "sandbox_boundary_allows_production_path_writes" in finding_ids
    assert "sandbox_boundary_allows_engine_path_writes" in finding_ids
    assert "sandbox_boundary_allows_cache_live_db_access" in finding_ids
    assert "sandbox_boundary_allows_authoritative_source_uuid_claims" in finding_ids
    assert "sandbox_boundary_allows_authoritative_asset_id_claims" in finding_ids
    assert "sandbox_boundary_allows_authoritative_product_id_claims" in finding_ids
    assert "sandbox_boundary_claims_runner_implemented" in finding_ids
    assert "sandbox_boundary_claims_dry_run_executed" in finding_ids


def test_validator_rejects_source_artifact_validation_status_not_pass(tmp_path: Path):
    payload = _clone_base_payload()
    payload["source_artifact_validation_status"]["non_approval_decision_status"] = "fail"
    path = tmp_path / "invalid-source-artifact-validation-status.json"
    _write(path, payload)
    code, report = _run_validator(path, skip_source_validators=True)
    assert code != 0
    assert "source_artifact_validation_status_not_pass" in _finding_ids(report)


def test_validator_rejects_missing_non_approval_source_and_cross_validator_failure(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    payload["source_artifacts"]["non_approval_decision_ref"] = (
        "examples/execution-admission/nonexistent-non-approval-decision.json"
    )
    path = tmp_path / "invalid-non-approval-source-path.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "source_artifact_missing" in finding_ids
    assert "non_approval_decision_validation_failed" in finding_ids
