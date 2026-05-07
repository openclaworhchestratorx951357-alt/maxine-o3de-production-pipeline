#!/usr/bin/env python3
"""Validate release-candidate publication dry-run runner interface v1."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


TARGET_CANDIDATE_ID = "release_candidate_package_publish_dry_run_v1"
TARGET_CANDIDATE_TYPE = "dry_run"
TARGET_RECEIPT_TYPE = "release_candidate_package_publish_dry_run_receipt_v1"
NOOP_CANDIDATE_ID = "release_candidate_package_receipt_noop_v1"
EXPECTED_APPROVAL_PHRASE = (
    "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
)
EXPECTED_RUNNER_INTERFACE_STATUS = "static_interface_valid_blocked"
EXPECTED_SANDBOX_BOUNDARY_STATUS = "static_boundary_valid_blocked"
EXPECTED_NON_APPROVAL_DECISION_TYPE = "non_approval"
EXPECTED_NON_APPROVAL_DECISION_STATUS = "active_non_approval"
EXPECTED_NON_APPROVAL_DECISION_EFFECT = "candidate_remains_blocked_unadmitted"
EXPECTED_SELECTED_OPERATOR_DECISION = "do_not_approve"
EXPECTED_NEXT_RECOMMENDED_ACTION = "continue_hardening_no_execution"
EXPECTED_APPROVAL_REQUEST_READINESS_FINAL_RECOMMENDATION = (
    "do_not_request_approval_yet"
)
EXPECTED_APPROVAL_REQUEST_READINESS_STATUS = "static_request_readiness_valid_blocked"
EXPECTED_COMPLETENESS_STATUS = "static_completeness_valid_blocked"
EXPECTED_OPERATOR_PACKET_STATUS = "static_template_valid_blocked"
EXPECTED_ADMISSION_BLOCKERS_STATUS = "static_checklist_valid_blocked"
EXPECTED_RECEIPT_CONTRACT_STATUS = "static_contract_valid_blocked"
EXPECTED_BLOCKED_RECEIPT_STATUS = "blocked_unissued_contract_only"
EXPECTED_DRY_RUN_PLAN_STATUS = "static_plan_valid_blocked"
EXPECTED_ROLLUP_STATUS = "static_rollup_valid_blocked"
EXPECTED_ROLLUP_NEXT_SLICE_ID = "candidate_specific_dry_run_planning_v1"
EXPECTED_SAFE_LIFECYCLE_STATES = {"not_started", "blocked_failed_safe", "invalidated_failed_safe"}

DEFAULT_INTERFACE_REL = Path(
    "examples/execution-admission/"
    "release_candidate_package_publish_dry_run_runner_interface_v1.json"
)
DEFAULT_SCHEMA_REL = Path(
    "schemas/maxine_release_candidate_publication_dry_run_runner_interface.schema.json"
)
DEFAULT_MATRIX_REL = Path(
    "examples/execution-admission/execution_admission_candidate_matrix_v1.json"
)
DEFAULT_PREFLIGHT_REL = Path(
    "examples/execution-admission/execution_admission_preflight_contracts_v1.json"
)
DEFAULT_PREFLIGHT_PROOF_REL = Path(
    "examples/execution-admission/execution_admission_preflight_proof_packages_v1.json"
)
DEFAULT_ROLLUP_REL = Path(
    "examples/execution-admission/execution_admission_readiness_rollup_v1.json"
)
DEFAULT_DRY_RUN_PLAN_REL = Path(
    "examples/execution-admission/release_candidate_package_publish_dry_run_plan_v1.json"
)
DEFAULT_DRY_RUN_RECEIPT_CONTRACT_REL = Path(
    "examples/execution-admission/release_candidate_package_publish_dry_run_receipt_contract_v1.json"
)
DEFAULT_DRY_RUN_RECEIPT_BLOCKED_REL = Path(
    "examples/execution-admission/release_candidate_package_publish_dry_run_receipt_blocked_v1.json"
)
DEFAULT_ADMISSION_BLOCKERS_REL = Path(
    "examples/execution-admission/release_candidate_package_publish_dry_run_admission_blockers_v1.json"
)
DEFAULT_OPERATOR_PACKET_REL = Path(
    "examples/execution-admission/release_candidate_package_publish_dry_run_operator_approval_packet_v1.json"
)
DEFAULT_OPERATOR_PACKET_COMPLETENESS_REL = Path(
    "examples/execution-admission/release_candidate_package_publish_dry_run_operator_approval_packet_completeness_v1.json"
)
DEFAULT_APPROVAL_REQUEST_READINESS_REL = Path(
    "examples/execution-admission/release_candidate_package_publish_dry_run_approval_request_readiness_v1.json"
)
DEFAULT_NON_APPROVAL_DECISION_REL = Path(
    "examples/execution-admission/release_candidate_package_publish_dry_run_non_approval_decision_v1.json"
)
DEFAULT_SANDBOX_BOUNDARY_REL = Path(
    "examples/execution-admission/release_candidate_package_publish_dry_run_sandbox_boundary_v1.json"
)
DEFAULT_PRODUCTION_READINESS_REL = Path(
    "examples/production-readiness-report/max_biped_v1_production_readiness_report_pass.json"
)
DEFAULT_NOOP_DECISION_REL = Path(
    "examples/execution-admission/"
    "release_candidate_package_receipt_noop_execution_admission_decision_approved.json"
)

MATRIX_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_execution_admission_candidate_matrix.py"
)
PREFLIGHT_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_execution_admission_preflight_contracts.py"
)
PREFLIGHT_PROOF_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_execution_admission_preflight_proof_packages.py"
)
READINESS_ROLLUP_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_execution_admission_readiness_rollup.py"
)
DRY_RUN_PLAN_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_release_candidate_publication_dry_run_plan.py"
)
DRY_RUN_RECEIPT_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_release_candidate_publication_dry_run_receipt.py"
)
ADMISSION_BLOCKERS_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_release_candidate_publication_dry_run_admission_blockers.py"
)
OPERATOR_PACKET_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_release_candidate_publication_dry_run_operator_approval_packet.py"
)
OPERATOR_PACKET_COMPLETENESS_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_release_candidate_publication_dry_run_operator_approval_packet_completeness.py"
)
APPROVAL_REQUEST_READINESS_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_release_candidate_publication_dry_run_approval_request_readiness.py"
)
NON_APPROVAL_DECISION_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_release_candidate_publication_dry_run_non_approval_decision.py"
)
SANDBOX_BOUNDARY_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_release_candidate_publication_dry_run_sandbox_boundary.py"
)

REQUIRED_SOURCE_REFERENCE_FIELDS = {
    "candidate_matrix_ref",
    "preflight_contracts_ref",
    "preflight_proof_packages_ref",
    "readiness_rollup_ref",
    "dry_run_plan_ref",
    "dry_run_receipt_contract_ref",
    "blocked_unissued_receipt_ref",
    "admission_blocker_checklist_ref",
    "operator_approval_packet_ref",
    "operator_approval_packet_completeness_ref",
    "approval_request_readiness_ref",
    "non_approval_decision_ref",
    "sandbox_boundary_ref",
    "production_readiness_report_ref",
    "noop_receipt_status_ref",
}

SOURCE_STATUS_KEYS = (
    "candidate_matrix_status",
    "preflight_contracts_status",
    "preflight_proof_packages_status",
    "readiness_rollup_status",
    "dry_run_plan_status",
    "dry_run_receipt_contract_status",
    "blocked_unissued_receipt_status",
    "admission_blocker_checklist_status",
    "operator_approval_packet_status",
    "operator_approval_packet_completeness_status",
    "approval_request_readiness_status",
    "non_approval_decision_status",
    "sandbox_boundary_status",
    "production_readiness_status",
    "noop_receipt_status",
)

REQUIRED_FALSE_FIELDS = (
    ("approval_request_ready", "approval_request_ready_not_allowed"),
    ("operator_approval_granted", "operator_approval_granted_not_allowed"),
    ("approval_phrase_present", "approval_phrase_present_not_allowed"),
    ("dry_run_admitted", "dry_run_admitted_not_allowed"),
    ("dry_run_executed", "dry_run_executed_not_allowed"),
    ("receipt_issued", "receipt_issued_not_allowed"),
    ("publication_admitted", "publication_admitted_not_allowed"),
    ("real_execution_admitted", "real_execution_admitted_not_allowed"),
    ("production_ready_claimed", "production_ready_claim_not_allowed"),
)

REQUIRED_INPUT_TOKENS = {
    "candidate_matrix": "required_inputs_missing_candidate_matrix",
    "preflight_contracts": "required_inputs_missing_preflight_contracts",
    "preflight_proof_packages": "required_inputs_missing_preflight_proof_packages",
    "readiness_rollup": "required_inputs_missing_readiness_rollup",
    "dry_run_plan": "required_inputs_missing_dry_run_plan",
    "dry_run_receipt_contract": "required_inputs_missing_dry_run_receipt_contract",
    "blocked_unissued_receipt": "required_inputs_missing_blocked_unissued_receipt",
    "admission_blocker_checklist": "required_inputs_missing_admission_blocker_checklist",
    "operator_approval_packet": "required_inputs_missing_operator_approval_packet",
    "operator_approval_packet_completeness": "required_inputs_missing_operator_approval_packet_completeness",
    "approval_request_readiness": "required_inputs_missing_approval_request_readiness",
    "non_approval_decision": "required_inputs_missing_non_approval_decision",
    "sandbox_boundary": "required_inputs_missing_sandbox_boundary",
    "production_readiness_report": "required_inputs_missing_production_readiness_report",
    "noop_receipt_status": "required_inputs_missing_noop_receipt_status",
}

REQUIRED_FORBIDDEN_INPUT_TOKENS = {
    "live_o3de_runtime_state": "forbidden_inputs_missing_live_o3de_runtime_state",
    "editor_runtime_state": "forbidden_inputs_missing_editor_runtime_state",
    "asset_processor_live_state": "forbidden_inputs_missing_asset_processor_live_state",
    "blender_dcc_live_state": "forbidden_inputs_missing_blender_dcc_live_state",
    "cache_live_db_state": "forbidden_inputs_missing_cache_live_db_state",
    "production_deployment_state": "forbidden_inputs_missing_production_state",
    "publish_export_destination_state": "forbidden_inputs_missing_publish_export_state",
    "authoritative_live_id_claims": "forbidden_inputs_missing_authoritative_id_claims",
}

REQUIRED_FORBIDDEN_OUTPUT_TOKENS = {
    "production_publication_output": "forbidden_outputs_missing_production_publication_output",
    "spawn_output": "forbidden_outputs_missing_spawn_output",
    "engine_writes": "forbidden_outputs_missing_engine_writes",
    "production_path_writes": "forbidden_outputs_missing_production_path_writes",
    "cache_live_db_writes": "forbidden_outputs_missing_cache_live_db_writes",
    "executable_binary_outputs": "forbidden_outputs_missing_executable_binary_outputs",
    "authoritative_source_uuid_claims": "forbidden_outputs_missing_authoritative_source_uuid_claims",
    "authoritative_asset_id_claims": "forbidden_outputs_missing_authoritative_asset_id_claims",
    "authoritative_product_id_claims": "forbidden_outputs_missing_authoritative_product_id_claims",
}

REQUIRED_BOUNDARY_VALIDATION_TOKENS = {
    "normalize_paths_before_access": "boundary_validation_requirements_missing_path_normalization",
    "fail_closed_before_write_on_boundary_violation": "boundary_validation_requirements_missing_fail_closed_behavior",
}

REQUIRED_RECEIPT_REQUIREMENT_TOKENS = {
    "receipt_type_must_equal_release_candidate_package_publish_dry_run_receipt_v1": (
        "receipt_contract_requirements_missing_receipt_type"
    ),
}

REQUIRED_FAIL_CLOSED_TOKENS = {
    "fail_before_write_on_missing_approval_or_admission": "fail_closed_requirements_missing_missing_admission_failure",
    "fail_before_write_on_invalid_boundary": "fail_closed_requirements_missing_invalid_boundary_failure",
    "fail_before_write_on_live_tool_invocation": "fail_closed_requirements_missing_live_invocation_failure",
    "fail_before_write_on_publish_or_spawn_attempt": "fail_closed_requirements_missing_publish_spawn_failure",
    "fail_before_write_on_cache_live_db_access": "fail_closed_requirements_missing_cache_live_db_failure",
}

REQUIRED_FORBIDDEN_RUNTIME_CALLS = {
    "o3de_execution": "forbidden_runtime_calls_missing_o3de_execution",
    "editor_runtime_execution": "forbidden_runtime_calls_missing_editor_runtime_execution",
    "asset_processor_execution": "forbidden_runtime_calls_missing_asset_processor_execution",
    "blender_dcc_execution": "forbidden_runtime_calls_missing_blender_dcc_execution",
    "spawn": "forbidden_runtime_calls_missing_spawn_publish",
    "publish_export": "forbidden_runtime_calls_missing_spawn_publish",
}

REQUIRED_FORBIDDEN_FILESYSTEM_OPERATIONS = {
    "production_writes": "forbidden_filesystem_operations_missing_production_writes",
    "engine_writes": "forbidden_filesystem_operations_missing_engine_writes",
    "cache_live_db_writes": "forbidden_filesystem_operations_missing_cache_live_db_writes",
}

REQUIRED_INVALIDATION_CONDITIONS = {
    "live_tool_runtime_invocation_attempt": "invalidation_conditions_missing_live_tool_invocation",
    "spawn_publish_attempt": "invalidation_conditions_missing_spawn_publish_attempt",
    "receipt_issued_without_explicit_admission": "invalidation_conditions_missing_receipt_without_admission",
    "authoritative_id_claim_attempt": "invalidation_conditions_missing_authoritative_id_claim",
    "write_outside_allowed_sandbox_root": "invalidation_conditions_missing_write_outside_sandbox",
}

REQUIRED_DISALLOWED_MODES = {
    "execution_mode": "disallowed_runner_modes_missing_execution_mode",
    "admission_mode": "disallowed_runner_modes_missing_admission_mode",
    "publication_mode": "disallowed_runner_modes_missing_publication_mode",
    "spawn_mode": "disallowed_runner_modes_missing_spawn_mode",
    "live_runtime_mode": "disallowed_runner_modes_missing_live_runtime_mode",
    "receipt_emission_mode": "disallowed_runner_modes_missing_receipt_emission_mode",
}

REQUIRED_ALLOWED_MODE_TOKENS = {"static_contract_review_only"}
DISALLOWED_ALLOWED_MODE_TOKENS = set(REQUIRED_DISALLOWED_MODES.keys())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate release-candidate publication dry-run runner interface v1."
        )
    )
    parser.add_argument(
        "interface_path",
        nargs="?",
        default=str(DEFAULT_INTERFACE_REL),
        help="Path to release-candidate publication dry-run runner interface JSON.",
    )
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Return zero when status is warn.",
    )
    parser.add_argument(
        "--skip-source-validators",
        action="store_true",
        help="Skip nested source-validator subprocess calls (used for fast negative tests).",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_schema(payload: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return True, []

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    if not errors:
        return True, []

    messages: List[str] = []
    for err in errors:
        location = ".".join(str(p) for p in err.absolute_path) or "<root>"
        messages.append(f"{location}: {err.message}")
    return False, messages


def add_finding(
    findings: List[Dict[str, Any]],
    finding_id: str,
    severity: str,
    message: str,
    details: Dict[str, Any] | None = None,
) -> None:
    finding: Dict[str, Any] = {
        "id": finding_id,
        "severity": severity,
        "message": message,
    }
    if details:
        finding["details"] = details
    findings.append(finding)


def as_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    values: List[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            values.append(text)
    return values


def resolve_ref_path(repo_root: Path, raw_path: str) -> Path:
    candidate = Path(str(raw_path).strip())
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root / candidate).resolve()


def parse_payload_from_stdout(stdout: str) -> Dict[str, Any]:
    start = stdout.find("{")
    if start < 0:
        raise ValueError("validator output did not include JSON payload")
    return json.loads(stdout[start:])


def run_validator(
    repo_root: Path,
    script_rel: Path,
    args: List[str],
) -> Tuple[int, Dict[str, Any] | None, str | None]:
    cmd = [sys.executable, str((repo_root / script_rel).resolve()), *args]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    try:
        payload = parse_payload_from_stdout(proc.stdout)
    except Exception:
        stderr = proc.stderr or ""
        return proc.returncode, None, proc.stdout + ("\n" + stderr if stderr else "")
    return proc.returncode, payload, None


def _candidate_map(payload: Dict[str, Any], key: str) -> Dict[str, Dict[str, Any]]:
    values = payload.get(key, [])
    output: Dict[str, Dict[str, Any]] = {}
    if isinstance(values, list):
        for entry in values:
            if isinstance(entry, dict):
                candidate_id = str(entry.get("candidate_id", "")).strip()
                if candidate_id:
                    output[candidate_id] = entry
    return output


def _validate_production_readiness_report(
    payload: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> str:
    status = "pass"
    if str(payload.get("report_type", "")).strip() != "PRODUCTION_READINESS_REPORT_v1_REPORT":
        add_finding(
            findings,
            "production_readiness_report_type_mismatch",
            "error",
            "Referenced production readiness report must be PRODUCTION_READINESS_REPORT_v1_REPORT.",
        )
        status = "fail"
    if str(payload.get("status", "")).strip() != "pass":
        add_finding(
            findings,
            "production_readiness_status_not_pass",
            "error",
            "Referenced production readiness report must keep status=pass.",
        )
        status = "fail"
    if str(payload.get("real_execution_admission_status", "")).strip() != "blocked":
        add_finding(
            findings,
            "production_readiness_real_execution_status_not_blocked",
            "error",
            "Referenced production readiness report must keep real_execution_admission_status=blocked.",
        )
        status = "fail"
    if str(payload.get("publication_admission_status", "")).strip() != "blocked":
        add_finding(
            findings,
            "production_readiness_publication_status_not_blocked",
            "error",
            "Referenced production readiness report must keep publication_admission_status=blocked.",
        )
        status = "fail"
    if bool(payload.get("production_ready_claimed", False)):
        add_finding(
            findings,
            "production_ready_claim_not_allowed",
            "error",
            "Referenced production readiness report must not claim production_ready.",
        )
        status = "fail"
    return status


def _validate_noop_decision_record(
    payload: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> str:
    status = "pass"
    if str(payload.get("candidate_id", "")).strip() != NOOP_CANDIDATE_ID:
        add_finding(
            findings,
            "noop_decision_record_candidate_id_mismatch",
            "error",
            "No-op decision record candidate_id must match release_candidate_package_receipt_noop_v1.",
        )
        status = "fail"
    if str(payload.get("decision_state", "")).strip() != "approved":
        add_finding(
            findings,
            "noop_decision_record_state_not_approved",
            "error",
            "No-op decision record must keep decision_state=approved.",
        )
        status = "fail"
    approval = payload.get("approval") if isinstance(payload.get("approval"), dict) else {}
    if approval.get("approval_received") is not True:
        add_finding(
            findings,
            "noop_decision_record_approval_missing",
            "error",
            "No-op decision record must keep approval.approval_received=true.",
        )
        status = "fail"
    return status


def _check_non_empty_string_list(
    payload: Dict[str, Any],
    key: str,
    findings: List[Dict[str, Any]],
    finding_id: str,
    message: str,
) -> List[str]:
    values = as_string_list(payload.get(key))
    if not values:
        add_finding(
            findings,
            finding_id,
            "error",
            message,
            {"field": key},
        )
    return values


def _check_required_token_set(
    values: List[str],
    required_map: Dict[str, str],
    findings: List[Dict[str, Any]],
    list_name: str,
) -> None:
    current = {item.strip() for item in values if item.strip()}
    for token, finding_id in required_map.items():
        if token not in current:
            add_finding(
                findings,
                finding_id,
                "error",
                f"{list_name} must include required token: {token}",
            )


def _check_forbidden_claim_language(
    payload: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    checks = (
        ("publish allowed", "runner_interface_allows_publish"),
        ("spawn allowed", "runner_interface_allows_spawn"),
        ("production path writes allowed", "runner_interface_allows_production_path_writes"),
        ("engine path writes allowed", "runner_interface_allows_engine_path_writes"),
        ("cache/live db access allowed", "runner_interface_allows_cache_live_db_access"),
        ("cache live db access allowed", "runner_interface_allows_cache_live_db_access"),
        (
            "authoritative source uuid claims allowed",
            "runner_interface_allows_authoritative_source_uuid_claims",
        ),
        (
            "authoritative asset id claims allowed",
            "runner_interface_allows_authoritative_asset_id_claims",
        ),
        (
            "authoritative product id claims allowed",
            "runner_interface_allows_authoritative_product_id_claims",
        ),
        (
            "runner interface contract equals runner implementation",
            "runner_interface_equals_runner_implementation_claim",
        ),
        (
            "runner interface contract equals runner admission",
            "runner_interface_equals_runner_admission_claim",
        ),
        ("runner interface contract equals approval", "runner_interface_equals_approval_claim"),
        (
            "runner interface contract equals approval-ready",
            "runner_interface_equals_approval_ready_claim",
        ),
        (
            "runner interface contract equals dry-run admission",
            "runner_interface_equals_dry_run_admission_claim",
        ),
        (
            "runner interface contract equals receipt issuance",
            "runner_interface_equals_receipt_issuance_claim",
        ),
        (
            "runner interface contract equals execution admission",
            "runner_interface_equals_execution_admission_claim",
        ),
        (
            "runner interface contract equals publication admission",
            "runner_interface_equals_publication_admission_claim",
        ),
        (
            "runner interface contract equals production_ready",
            "runner_interface_equals_production_ready_claim",
        ),
        ("runner implemented", "runner_interface_claims_runner_implemented"),
        ("runner admitted", "runner_interface_claims_runner_admitted"),
        ("runner executed", "runner_interface_claims_runner_executed"),
        ("dry-run executed", "runner_interface_claims_dry_run_executed"),
    )
    for needle, finding_id in checks:
        if needle in text:
            add_finding(
                findings,
                finding_id,
                "error",
                "Runner interface text must not allow blocked surfaces or claims.",
                {"needle": needle},
            )


def _path_from_source_artifacts(
    repo_root: Path,
    source_artifacts: Dict[str, Any],
    field: str,
    default_rel: Path,
) -> Path:
    raw = str(source_artifacts.get(field, "")).strip()
    if raw:
        return resolve_ref_path(repo_root, raw)
    return (repo_root / default_rel).resolve()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    interface_path = resolve_ref_path(repo_root, args.interface_path)
    schema_path = (repo_root / DEFAULT_SCHEMA_REL).resolve()

    findings: List[Dict[str, Any]] = []

    if not interface_path.exists():
        add_finding(
            findings,
            "runner_interface_missing",
            "error",
            "release-candidate publication dry-run runner interface JSON was not found.",
            {"path": str(interface_path)},
        )
        report_payload = {
            "schema_version": "1.0.0",
            "report_type": "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RUNNER_INTERFACE_VALIDATION_v1_REPORT",
            "status": "fail",
            "release_candidate_publication_dry_run_runner_interface_present": False,
            "release_candidate_publication_dry_run_runner_interface_path": str(interface_path),
            "findings": findings,
        }
        print(json.dumps(report_payload, indent=2))
        return 1

    interface = load_json(interface_path)

    if not schema_path.exists():
        add_finding(
            findings,
            "runner_interface_schema_missing",
            "error",
            "Runner interface schema file was not found.",
            {"path": str(schema_path)},
        )
    else:
        schema = load_json(schema_path)
        schema_ok, schema_errors = validate_schema(interface, schema)
        if not schema_ok:
            for message in schema_errors:
                add_finding(
                    findings,
                    "schema_validation_failed",
                    "error",
                    "Runner interface failed schema validation.",
                    {"error": message},
                )

    source_artifacts = (
        interface.get("source_artifacts")
        if isinstance(interface.get("source_artifacts"), dict)
        else {}
    )

    source_paths: Dict[str, Path] = {
        "candidate_matrix_ref": _path_from_source_artifacts(repo_root, source_artifacts, "candidate_matrix_ref", DEFAULT_MATRIX_REL),
        "preflight_contracts_ref": _path_from_source_artifacts(repo_root, source_artifacts, "preflight_contracts_ref", DEFAULT_PREFLIGHT_REL),
        "preflight_proof_packages_ref": _path_from_source_artifacts(repo_root, source_artifacts, "preflight_proof_packages_ref", DEFAULT_PREFLIGHT_PROOF_REL),
        "readiness_rollup_ref": _path_from_source_artifacts(repo_root, source_artifacts, "readiness_rollup_ref", DEFAULT_ROLLUP_REL),
        "dry_run_plan_ref": _path_from_source_artifacts(repo_root, source_artifacts, "dry_run_plan_ref", DEFAULT_DRY_RUN_PLAN_REL),
        "dry_run_receipt_contract_ref": _path_from_source_artifacts(repo_root, source_artifacts, "dry_run_receipt_contract_ref", DEFAULT_DRY_RUN_RECEIPT_CONTRACT_REL),
        "blocked_unissued_receipt_ref": _path_from_source_artifacts(repo_root, source_artifacts, "blocked_unissued_receipt_ref", DEFAULT_DRY_RUN_RECEIPT_BLOCKED_REL),
        "admission_blocker_checklist_ref": _path_from_source_artifacts(repo_root, source_artifacts, "admission_blocker_checklist_ref", DEFAULT_ADMISSION_BLOCKERS_REL),
        "operator_approval_packet_ref": _path_from_source_artifacts(repo_root, source_artifacts, "operator_approval_packet_ref", DEFAULT_OPERATOR_PACKET_REL),
        "operator_approval_packet_completeness_ref": _path_from_source_artifacts(repo_root, source_artifacts, "operator_approval_packet_completeness_ref", DEFAULT_OPERATOR_PACKET_COMPLETENESS_REL),
        "approval_request_readiness_ref": _path_from_source_artifacts(repo_root, source_artifacts, "approval_request_readiness_ref", DEFAULT_APPROVAL_REQUEST_READINESS_REL),
        "non_approval_decision_ref": _path_from_source_artifacts(repo_root, source_artifacts, "non_approval_decision_ref", DEFAULT_NON_APPROVAL_DECISION_REL),
        "sandbox_boundary_ref": _path_from_source_artifacts(repo_root, source_artifacts, "sandbox_boundary_ref", DEFAULT_SANDBOX_BOUNDARY_REL),
        "production_readiness_report_ref": _path_from_source_artifacts(repo_root, source_artifacts, "production_readiness_report_ref", DEFAULT_PRODUCTION_READINESS_REL),
        "noop_receipt_status_ref": _path_from_source_artifacts(repo_root, source_artifacts, "noop_receipt_status_ref", DEFAULT_NOOP_DECISION_REL),
    }

    for field in REQUIRED_SOURCE_REFERENCE_FIELDS:
        raw = str(source_artifacts.get(field, "")).strip()
        if not raw:
            add_finding(
                findings,
                "source_artifacts_missing_required_reference",
                "error",
                "source_artifacts is missing required reference.",
                {"field": field},
            )

    for field, value in source_paths.items():
        if not value.exists():
            add_finding(
                findings,
                "source_artifact_missing",
                "error",
                "Referenced source artifact path does not exist.",
                {"field": field, "path": str(value)},
            )

    source_status_expected: Dict[str, str] = {key: "fail" for key in SOURCE_STATUS_KEYS}

    if args.skip_source_validators:
        for key in SOURCE_STATUS_KEYS:
            source_status_expected[key] = "pass"
    else:
        validator_jobs = [
            ("candidate_matrix_status", MATRIX_VALIDATOR_REL, [str(source_paths["candidate_matrix_ref"])], "candidate_matrix_validation_failed"),
            ("preflight_contracts_status", PREFLIGHT_VALIDATOR_REL, [str(source_paths["preflight_contracts_ref"])], "preflight_contracts_validation_failed"),
            (
                "preflight_proof_packages_status",
                PREFLIGHT_PROOF_VALIDATOR_REL,
                [
                    str(source_paths["preflight_proof_packages_ref"]),
                    "--matrix-path",
                    str(source_paths["candidate_matrix_ref"]),
                    "--preflight-path",
                    str(source_paths["preflight_contracts_ref"]),
                ],
                "preflight_proof_packages_validation_failed",
            ),
            ("readiness_rollup_status", READINESS_ROLLUP_VALIDATOR_REL, [str(source_paths["readiness_rollup_ref"])], "readiness_rollup_validation_failed"),
            ("dry_run_plan_status", DRY_RUN_PLAN_VALIDATOR_REL, [str(source_paths["dry_run_plan_ref"])], "dry_run_plan_validation_failed"),
            ("dry_run_receipt_contract_status", DRY_RUN_RECEIPT_VALIDATOR_REL, [str(source_paths["dry_run_receipt_contract_ref"])], "dry_run_receipt_contract_validation_failed"),
            ("blocked_unissued_receipt_status", DRY_RUN_RECEIPT_VALIDATOR_REL, [str(source_paths["blocked_unissued_receipt_ref"])], "blocked_unissued_receipt_validation_failed"),
            ("admission_blocker_checklist_status", ADMISSION_BLOCKERS_VALIDATOR_REL, [str(source_paths["admission_blocker_checklist_ref"])], "admission_blocker_checklist_validation_failed"),
            ("operator_approval_packet_status", OPERATOR_PACKET_VALIDATOR_REL, [str(source_paths["operator_approval_packet_ref"])], "operator_approval_packet_validation_failed"),
            ("operator_approval_packet_completeness_status", OPERATOR_PACKET_COMPLETENESS_VALIDATOR_REL, [str(source_paths["operator_approval_packet_completeness_ref"])], "operator_approval_packet_completeness_validation_failed"),
            ("approval_request_readiness_status", APPROVAL_REQUEST_READINESS_VALIDATOR_REL, [str(source_paths["approval_request_readiness_ref"])], "approval_request_readiness_validation_failed"),
            ("non_approval_decision_status", NON_APPROVAL_DECISION_VALIDATOR_REL, [str(source_paths["non_approval_decision_ref"])], "non_approval_decision_validation_failed"),
            ("sandbox_boundary_status", SANDBOX_BOUNDARY_VALIDATOR_REL, [str(source_paths["sandbox_boundary_ref"])], "sandbox_boundary_validation_failed"),
        ]

        for status_key, validator_rel, validator_args, finding_id in validator_jobs:
            code, payload, raw_error = run_validator(repo_root, validator_rel, validator_args)
            if code != 0 or not payload or payload.get("status") != "pass":
                source_status_expected[status_key] = "fail"
                add_finding(
                    findings,
                    finding_id,
                    "error",
                    "Nested source validator did not pass.",
                    {
                        "script": str(validator_rel),
                        "args": validator_args,
                        "return_code": code,
                        "report_status": payload.get("status") if payload else None,
                        "raw_output": raw_error,
                    },
                )
            else:
                source_status_expected[status_key] = "pass"

    production_payload = load_json(source_paths["production_readiness_report_ref"]) if source_paths["production_readiness_report_ref"].exists() else {}
    noop_payload = load_json(source_paths["noop_receipt_status_ref"]) if source_paths["noop_receipt_status_ref"].exists() else {}
    source_status_expected["production_readiness_status"] = _validate_production_readiness_report(production_payload, findings)
    source_status_expected["noop_receipt_status"] = _validate_noop_decision_record(noop_payload, findings)

    source_status_reported = (
        interface.get("source_artifact_validation_status")
        if isinstance(interface.get("source_artifact_validation_status"), dict)
        else {}
    )
    for key in SOURCE_STATUS_KEYS:
        if str(source_status_reported.get(key, "")).strip() != "pass":
            add_finding(
                findings,
                "source_artifact_validation_status_not_pass",
                "error",
                "source_artifact_validation_status must report pass for every required source.",
                {"field": key, "actual": source_status_reported.get(key)},
            )
        if source_status_expected.get(key) != "pass":
            add_finding(
                findings,
                "computed_source_artifact_validation_status_not_pass",
                "error",
                "Computed source artifact validation status must pass for every required source.",
                {"field": key, "actual": source_status_expected.get(key)},
            )

    candidate_id = str(interface.get("candidate_id", "")).strip()
    candidate_type = str(interface.get("candidate_type", "")).strip()
    if candidate_id != TARGET_CANDIDATE_ID:
        add_finding(findings, "candidate_id_mismatch", "error", "candidate_id must be release_candidate_package_publish_dry_run_v1.", {"actual": candidate_id})
    if candidate_type != TARGET_CANDIDATE_TYPE:
        add_finding(findings, "candidate_type_mismatch", "error", "candidate_type must be dry_run.", {"actual": candidate_type})
    if str(interface.get("runner_interface_status", "")).strip() != EXPECTED_RUNNER_INTERFACE_STATUS:
        add_finding(findings, "runner_interface_status_not_static_interface_valid_blocked", "error", "runner_interface_status must be static_interface_valid_blocked.")
    if str(interface.get("admission_status", "")).strip() != "unadmitted":
        add_finding(findings, "admission_status_not_unadmitted", "error", "admission_status must be unadmitted.")
    if str(interface.get("decision_type", "")).strip() != "non_approval":
        add_finding(findings, "decision_type_not_non_approval", "error", "decision_type must be non_approval.")
    if bool(interface.get("runner_implemented", False)):
        add_finding(findings, "runner_implemented_not_allowed", "error", "runner_implemented must remain false.")
    if bool(interface.get("runner_admitted", False)):
        add_finding(findings, "runner_admitted_not_allowed", "error", "runner_admitted must remain false.")
    if bool(interface.get("runner_executed", False)):
        add_finding(findings, "runner_executed_not_allowed", "error", "runner_executed must remain false.")

    for field, finding_id in REQUIRED_FALSE_FIELDS:
        if bool(interface.get(field, False)):
            add_finding(findings, finding_id, "error", f"{field} must remain false.")

    interface_lifecycle_states = _check_non_empty_string_list(interface, "interface_lifecycle_states", findings, "interface_lifecycle_states_missing_or_empty", "interface_lifecycle_states must be present and non-empty.")
    current_lifecycle_state = str(interface.get("current_lifecycle_state", "")).strip()
    if current_lifecycle_state not in EXPECTED_SAFE_LIFECYCLE_STATES:
        add_finding(findings, "current_lifecycle_state_not_safe_not_started", "error", "current_lifecycle_state must be not_started or equivalent safe blocked state.", {"actual": current_lifecycle_state})
    if interface_lifecycle_states and "not_started" not in set(interface_lifecycle_states):
        add_finding(findings, "interface_lifecycle_states_missing_not_started", "error", "interface_lifecycle_states must include not_started.")

    required_inputs = _check_non_empty_string_list(interface, "required_inputs", findings, "required_inputs_missing_or_empty", "required_inputs must be present and non-empty.")
    forbidden_inputs = _check_non_empty_string_list(interface, "forbidden_inputs", findings, "forbidden_inputs_missing_or_empty", "forbidden_inputs must be present and non-empty.")
    required_outputs = _check_non_empty_string_list(interface, "required_outputs", findings, "required_outputs_missing_or_empty", "required_outputs must be present and non-empty.")
    forbidden_outputs = _check_non_empty_string_list(interface, "forbidden_outputs", findings, "forbidden_outputs_missing_or_empty", "forbidden_outputs must be present and non-empty.")
    current_emitted_outputs = interface.get("current_emitted_outputs")
    if not isinstance(current_emitted_outputs, list):
        add_finding(findings, "current_emitted_outputs_not_list", "error", "current_emitted_outputs must be a list and must remain empty.")
    elif len(current_emitted_outputs) != 0:
        add_finding(findings, "current_emitted_outputs_not_empty", "error", "current_emitted_outputs must remain empty in this milestone.")

    _check_required_token_set(required_inputs, REQUIRED_INPUT_TOKENS, findings, "required_inputs")
    _check_required_token_set(forbidden_inputs, REQUIRED_FORBIDDEN_INPUT_TOKENS, findings, "forbidden_inputs")
    _check_required_token_set(forbidden_outputs, REQUIRED_FORBIDDEN_OUTPUT_TOKENS, findings, "forbidden_outputs")
    for item in required_outputs:
        if not item.startswith("future_"):
            add_finding(findings, "required_outputs_must_be_future_only", "error", "required_outputs entries must be future-only outputs.", {"value": item})

    boundary_validation_requirements = _check_non_empty_string_list(interface, "boundary_validation_requirements", findings, "boundary_validation_requirements_missing_or_empty", "boundary_validation_requirements must be present and non-empty.")
    receipt_contract_requirements = _check_non_empty_string_list(interface, "receipt_contract_requirements", findings, "receipt_contract_requirements_missing_or_empty", "receipt_contract_requirements must be present and non-empty.")
    fail_closed_requirements = _check_non_empty_string_list(interface, "fail_closed_requirements", findings, "fail_closed_requirements_missing_or_empty", "fail_closed_requirements must be present and non-empty.")
    pre_run_validation_requirements = _check_non_empty_string_list(interface, "pre_run_validation_requirements", findings, "pre_run_validation_requirements_missing_or_empty", "pre_run_validation_requirements must be present and non-empty.")
    post_run_validation_requirements = _check_non_empty_string_list(interface, "post_run_validation_requirements", findings, "post_run_validation_requirements_missing_or_empty", "post_run_validation_requirements must be present and non-empty.")
    required_safety_attestations = _check_non_empty_string_list(interface, "required_safety_attestations", findings, "required_safety_attestations_missing_or_empty", "required_safety_attestations must be present and non-empty.")
    forbidden_runtime_calls = _check_non_empty_string_list(interface, "forbidden_runtime_calls", findings, "forbidden_runtime_calls_missing_or_empty", "forbidden_runtime_calls must be present and non-empty.")
    forbidden_filesystem_operations = _check_non_empty_string_list(interface, "forbidden_filesystem_operations", findings, "forbidden_filesystem_operations_missing_or_empty", "forbidden_filesystem_operations must be present and non-empty.")
    invalidation_conditions = _check_non_empty_string_list(interface, "invalidation_conditions", findings, "invalidation_conditions_missing_or_empty", "invalidation_conditions must be present and non-empty.")
    required_receipt_fields = _check_non_empty_string_list(interface, "required_receipt_fields", findings, "required_receipt_fields_missing_or_empty", "required_receipt_fields must be present and non-empty.")
    required_log_report_fields = _check_non_empty_string_list(interface, "required_log_report_fields", findings, "required_log_report_fields_missing_or_empty", "required_log_report_fields must be present and non-empty.")
    allowed_runner_modes = _check_non_empty_string_list(interface, "allowed_runner_modes", findings, "allowed_runner_modes_missing_or_empty", "allowed_runner_modes must be present and non-empty.")
    disallowed_runner_modes = _check_non_empty_string_list(interface, "disallowed_runner_modes", findings, "disallowed_runner_modes_missing_or_empty", "disallowed_runner_modes must be present and non-empty.")

    _check_required_token_set(boundary_validation_requirements, REQUIRED_BOUNDARY_VALIDATION_TOKENS, findings, "boundary_validation_requirements")
    _check_required_token_set(receipt_contract_requirements, REQUIRED_RECEIPT_REQUIREMENT_TOKENS, findings, "receipt_contract_requirements")
    _check_required_token_set(fail_closed_requirements, REQUIRED_FAIL_CLOSED_TOKENS, findings, "fail_closed_requirements")
    _check_required_token_set(forbidden_runtime_calls, REQUIRED_FORBIDDEN_RUNTIME_CALLS, findings, "forbidden_runtime_calls")
    _check_required_token_set(forbidden_filesystem_operations, REQUIRED_FORBIDDEN_FILESYSTEM_OPERATIONS, findings, "forbidden_filesystem_operations")
    _check_required_token_set(invalidation_conditions, REQUIRED_INVALIDATION_CONDITIONS, findings, "invalidation_conditions")
    _check_required_token_set(disallowed_runner_modes, REQUIRED_DISALLOWED_MODES, findings, "disallowed_runner_modes")

    allowed_modes = {item.strip() for item in allowed_runner_modes if item.strip()}
    if not REQUIRED_ALLOWED_MODE_TOKENS.issubset(allowed_modes):
        add_finding(findings, "allowed_runner_modes_not_static_contract_only", "error", "allowed_runner_modes must be static/contract-only in this milestone.", {"actual": sorted(allowed_modes)})
    if allowed_modes & DISALLOWED_ALLOWED_MODE_TOKENS:
        add_finding(findings, "allowed_runner_modes_include_execution_or_admission", "error", "allowed_runner_modes must not include execution/admission/publication/spawn/live/receipt modes.", {"actual": sorted(allowed_modes)})

    future_admission_requirements = _check_non_empty_string_list(interface, "future_admission_requirements", findings, "future_admission_requirements_missing_or_empty", "future_admission_requirements must be present and non-empty.")
    if not any(EXPECTED_APPROVAL_PHRASE in item for item in future_admission_requirements):
        add_finding(findings, "required_approval_phrase_missing_from_future_requirements", "error", "future_admission_requirements must include the exact candidate-specific approval phrase.")

    if bool(interface.get("unsafe_claims_detected", False)):
        add_finding(findings, "unsafe_claims_detected_not_allowed", "error", "unsafe_claims_detected must remain false.")

    safety_notes = as_string_list(interface.get("safety_notes"))
    if not safety_notes:
        add_finding(findings, "safety_notes_missing_or_empty", "error", "safety_notes must be present and non-empty.")

    _check_forbidden_claim_language(interface, findings)

    approval_request_readiness_payload = load_json(source_paths["approval_request_readiness_ref"]) if source_paths["approval_request_readiness_ref"].exists() else {}
    non_approval_decision_payload = load_json(source_paths["non_approval_decision_ref"]) if source_paths["non_approval_decision_ref"].exists() else {}
    sandbox_boundary_payload = load_json(source_paths["sandbox_boundary_ref"]) if source_paths["sandbox_boundary_ref"].exists() else {}
    rollup_payload = load_json(source_paths["readiness_rollup_ref"]) if source_paths["readiness_rollup_ref"].exists() else {}
    dry_run_plan_payload = load_json(source_paths["dry_run_plan_ref"]) if source_paths["dry_run_plan_ref"].exists() else {}
    dry_run_receipt_contract_payload = load_json(source_paths["dry_run_receipt_contract_ref"]) if source_paths["dry_run_receipt_contract_ref"].exists() else {}
    dry_run_receipt_blocked_payload = load_json(source_paths["blocked_unissued_receipt_ref"]) if source_paths["blocked_unissued_receipt_ref"].exists() else {}
    admission_blockers_payload = load_json(source_paths["admission_blocker_checklist_ref"]) if source_paths["admission_blocker_checklist_ref"].exists() else {}
    operator_packet_payload = load_json(source_paths["operator_approval_packet_ref"]) if source_paths["operator_approval_packet_ref"].exists() else {}
    operator_packet_completeness_payload = load_json(source_paths["operator_approval_packet_completeness_ref"]) if source_paths["operator_approval_packet_completeness_ref"].exists() else {}
    matrix_payload = load_json(source_paths["candidate_matrix_ref"]) if source_paths["candidate_matrix_ref"].exists() else {}
    preflight_payload = load_json(source_paths["preflight_contracts_ref"]) if source_paths["preflight_contracts_ref"].exists() else {}
    preflight_proof_payload = load_json(source_paths["preflight_proof_packages_ref"]) if source_paths["preflight_proof_packages_ref"].exists() else {}

    matrix_map = _candidate_map(matrix_payload, "candidates")
    matrix_entry = matrix_map.get(TARGET_CANDIDATE_ID)
    if not isinstance(matrix_entry, dict):
        add_finding(findings, "candidate_missing_in_matrix", "error", "Target candidate must exist in candidate matrix.")
    elif str(matrix_entry.get("current_status", "")).strip() == "admitted":
        add_finding(findings, "dry_run_admitted_not_allowed", "error", "Target candidate must remain unadmitted in candidate matrix.")

    preflight_map = _candidate_map(preflight_payload, "contracts")
    preflight_entry = preflight_map.get(TARGET_CANDIDATE_ID)
    if not isinstance(preflight_entry, dict):
        add_finding(findings, "candidate_missing_in_preflight_contracts", "error", "Target candidate must exist in preflight contracts.")
    elif str(preflight_entry.get("admission_status", "")).strip() != "unadmitted":
        add_finding(findings, "admission_status_mismatch_with_preflight_contracts", "error", "Target candidate must remain unadmitted in preflight contracts.")

    preflight_proof_map = _candidate_map(preflight_proof_payload, "proof_packages")
    preflight_proof_entry = preflight_proof_map.get(TARGET_CANDIDATE_ID)
    if not isinstance(preflight_proof_entry, dict):
        add_finding(findings, "candidate_missing_in_preflight_proof_packages", "error", "Target candidate must exist in preflight proof packages.")
    elif str(preflight_proof_entry.get("admission_status", "")).strip() != "unadmitted":
        add_finding(findings, "admission_status_mismatch_with_preflight_proof_packages", "error", "Target candidate must remain unadmitted in preflight proof packages.")

    if str(rollup_payload.get("overall_readiness_rollup_status", "")).strip() != EXPECTED_ROLLUP_STATUS:
        add_finding(findings, "readiness_rollup_status_not_expected", "error", "Readiness rollup must keep overall_readiness_rollup_status=static_rollup_valid_blocked.")
    next_slice = rollup_payload.get("safest_next_preparation_slice") if isinstance(rollup_payload.get("safest_next_preparation_slice"), dict) else {}
    if str(next_slice.get("slice_id", "")).strip() != EXPECTED_ROLLUP_NEXT_SLICE_ID:
        add_finding(findings, "readiness_rollup_next_slice_id_mismatch", "error", "Readiness rollup must keep safest_next_preparation_slice.slice_id=candidate_specific_dry_run_planning_v1.")

    if str(dry_run_plan_payload.get("plan_status", "")).strip() != EXPECTED_DRY_RUN_PLAN_STATUS:
        add_finding(findings, "dry_run_plan_status_not_expected", "error", "Dry-run plan must keep plan_status=static_plan_valid_blocked.")
    if str(dry_run_receipt_contract_payload.get("receipt_contract_status", "")).strip() != EXPECTED_RECEIPT_CONTRACT_STATUS:
        add_finding(findings, "dry_run_receipt_contract_status_not_expected", "error", "Dry-run receipt contract must keep receipt_contract_status=static_contract_valid_blocked.")
    if str(dry_run_receipt_contract_payload.get("receipt_type", "")).strip() != TARGET_RECEIPT_TYPE:
        add_finding(findings, "dry_run_receipt_type_mismatch", "error", "Dry-run receipt contract must keep receipt_type=release_candidate_package_publish_dry_run_receipt_v1.")
    if str(dry_run_receipt_blocked_payload.get("receipt_status", "")).strip() != EXPECTED_BLOCKED_RECEIPT_STATUS:
        add_finding(findings, "blocked_unissued_receipt_status_mismatch", "error", "Blocked/unissued receipt example must keep receipt_status=blocked_unissued_contract_only.")
    if str(admission_blockers_payload.get("checklist_status", "")).strip() != EXPECTED_ADMISSION_BLOCKERS_STATUS:
        add_finding(findings, "admission_blockers_status_not_expected", "error", "Admission blockers checklist must keep checklist_status=static_checklist_valid_blocked.")
    if str(operator_packet_payload.get("approval_packet_status", "")).strip() != EXPECTED_OPERATOR_PACKET_STATUS:
        add_finding(findings, "operator_approval_packet_status_not_expected", "error", "Operator approval packet must keep approval_packet_status=static_template_valid_blocked.")
    if str(operator_packet_completeness_payload.get("completeness_review_status", "")).strip() != EXPECTED_COMPLETENESS_STATUS:
        add_finding(findings, "operator_approval_packet_completeness_status_not_expected", "error", "Operator approval packet completeness must keep completeness_review_status=static_completeness_valid_blocked.")
    if str(approval_request_readiness_payload.get("approval_request_readiness_status", "")).strip() != EXPECTED_APPROVAL_REQUEST_READINESS_STATUS:
        add_finding(findings, "approval_request_readiness_status_not_expected", "error", "Approval request readiness report must keep approval_request_readiness_status=static_request_readiness_valid_blocked.")
    if str(approval_request_readiness_payload.get("final_recommendation", "")).strip() != EXPECTED_APPROVAL_REQUEST_READINESS_FINAL_RECOMMENDATION:
        add_finding(findings, "approval_request_readiness_final_recommendation_not_expected", "error", "Approval request readiness report must keep final_recommendation=do_not_request_approval_yet.")
    if str(non_approval_decision_payload.get("decision_type", "")).strip() != EXPECTED_NON_APPROVAL_DECISION_TYPE:
        add_finding(findings, "non_approval_decision_type_not_expected", "error", "Non-approval decision record must keep decision_type=non_approval.")
    if str(non_approval_decision_payload.get("decision_status", "")).strip() != EXPECTED_NON_APPROVAL_DECISION_STATUS:
        add_finding(findings, "non_approval_decision_status_not_expected", "error", "Non-approval decision record must keep decision_status=active_non_approval.")
    if str(non_approval_decision_payload.get("decision_effect", "")).strip() != EXPECTED_NON_APPROVAL_DECISION_EFFECT:
        add_finding(findings, "non_approval_decision_effect_not_expected", "error", "Non-approval decision record must keep decision_effect=candidate_remains_blocked_unadmitted.")
    if str(non_approval_decision_payload.get("selected_operator_decision", "")).strip() != EXPECTED_SELECTED_OPERATOR_DECISION:
        add_finding(findings, "non_approval_selected_operator_decision_not_expected", "error", "Non-approval decision record must keep selected_operator_decision=do_not_approve.")
    if str(non_approval_decision_payload.get("next_recommended_action", "")).strip() != EXPECTED_NEXT_RECOMMENDED_ACTION:
        add_finding(findings, "non_approval_next_recommended_action_not_expected", "error", "Non-approval decision record must keep next_recommended_action=continue_hardening_no_execution.")
    if str(sandbox_boundary_payload.get("sandbox_boundary_status", "")).strip() != EXPECTED_SANDBOX_BOUNDARY_STATUS:
        add_finding(findings, "sandbox_boundary_status_not_expected", "error", "Sandbox boundary record must keep sandbox_boundary_status=static_boundary_valid_blocked.")
    if bool(sandbox_boundary_payload.get("runner_implemented", False)):
        add_finding(findings, "sandbox_boundary_runner_implemented_not_false", "error", "Sandbox boundary record must keep runner_implemented=false.")

    for payload_name, payload_value in (
        ("dry_run_plan", dry_run_plan_payload),
        ("dry_run_receipt_contract", dry_run_receipt_contract_payload),
        ("blocked_unissued_receipt", dry_run_receipt_blocked_payload),
        ("admission_blockers", admission_blockers_payload),
        ("operator_approval_packet", operator_packet_payload),
        ("operator_approval_packet_completeness", operator_packet_completeness_payload),
        ("approval_request_readiness", approval_request_readiness_payload),
        ("non_approval_decision", non_approval_decision_payload),
        ("sandbox_boundary", sandbox_boundary_payload),
    ):
        if str(payload_value.get("candidate_id", "")).strip() != TARGET_CANDIDATE_ID:
            add_finding(findings, "candidate_id_mismatch_with_source_artifact", "error", "Source artifacts must target release_candidate_package_publish_dry_run_v1.", {"artifact": payload_name})
        if str(payload_value.get("candidate_type", "")).strip() != TARGET_CANDIDATE_TYPE:
            add_finding(findings, "candidate_type_mismatch_with_source_artifact", "error", "Source artifacts must keep candidate_type=dry_run.", {"artifact": payload_name})

    severity_set = {str(item.get("severity", "")).strip() for item in findings}
    status = "fail" if "error" in severity_set else "pass"

    report_payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RUNNER_INTERFACE_VALIDATION_v1_REPORT",
        "status": status,
        "release_candidate_publication_dry_run_runner_interface_present": True,
        "release_candidate_publication_dry_run_runner_interface_path": str(interface_path),
        "candidate_matrix_path": str(source_paths["candidate_matrix_ref"]),
        "preflight_contracts_path": str(source_paths["preflight_contracts_ref"]),
        "preflight_proof_packages_path": str(source_paths["preflight_proof_packages_ref"]),
        "readiness_rollup_path": str(source_paths["readiness_rollup_ref"]),
        "dry_run_plan_path": str(source_paths["dry_run_plan_ref"]),
        "dry_run_receipt_contract_path": str(source_paths["dry_run_receipt_contract_ref"]),
        "blocked_unissued_receipt_path": str(source_paths["blocked_unissued_receipt_ref"]),
        "admission_blocker_checklist_path": str(source_paths["admission_blocker_checklist_ref"]),
        "operator_approval_packet_path": str(source_paths["operator_approval_packet_ref"]),
        "operator_approval_packet_completeness_path": str(source_paths["operator_approval_packet_completeness_ref"]),
        "approval_request_readiness_path": str(source_paths["approval_request_readiness_ref"]),
        "non_approval_decision_path": str(source_paths["non_approval_decision_ref"]),
        "sandbox_boundary_path": str(source_paths["sandbox_boundary_ref"]),
        "production_readiness_report_path": str(source_paths["production_readiness_report_ref"]),
        "noop_receipt_status_path": str(source_paths["noop_receipt_status_ref"]),
        "source_artifact_validation_status": source_status_reported,
        "computed_source_artifact_validation_status": source_status_expected,
        "planned_candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "runner_interface_status": str(interface.get("runner_interface_status", "")).strip(),
        "admission_status": str(interface.get("admission_status", "")).strip(),
        "runner_implemented": bool(interface.get("runner_implemented", False)),
        "runner_admitted": bool(interface.get("runner_admitted", False)),
        "runner_executed": bool(interface.get("runner_executed", False)),
        "approval_request_ready": bool(interface.get("approval_request_ready", False)),
        "operator_approval_granted": bool(interface.get("operator_approval_granted", False)),
        "approval_phrase_present": bool(interface.get("approval_phrase_present", False)),
        "dry_run_admitted": bool(interface.get("dry_run_admitted", False)),
        "dry_run_executed": bool(interface.get("dry_run_executed", False)),
        "receipt_issued": bool(interface.get("receipt_issued", False)),
        "publication_admitted": bool(interface.get("publication_admitted", False)),
        "real_execution_admitted": bool(interface.get("real_execution_admitted", False)),
        "production_ready_claimed": bool(interface.get("production_ready_claimed", False)),
        "interface_lifecycle_states": interface_lifecycle_states,
        "current_lifecycle_state": current_lifecycle_state,
        "required_inputs": required_inputs,
        "forbidden_inputs": forbidden_inputs,
        "required_outputs": required_outputs,
        "current_emitted_outputs": current_emitted_outputs if isinstance(current_emitted_outputs, list) else [],
        "forbidden_outputs": forbidden_outputs,
        "boundary_validation_requirements": boundary_validation_requirements,
        "receipt_contract_requirements": receipt_contract_requirements,
        "fail_closed_requirements": fail_closed_requirements,
        "pre_run_validation_requirements": pre_run_validation_requirements,
        "post_run_validation_requirements": post_run_validation_requirements,
        "required_safety_attestations": required_safety_attestations,
        "forbidden_runtime_calls": forbidden_runtime_calls,
        "forbidden_filesystem_operations": forbidden_filesystem_operations,
        "invalidation_conditions": invalidation_conditions,
        "required_receipt_fields": required_receipt_fields,
        "required_log_report_fields": required_log_report_fields,
        "allowed_runner_modes": allowed_runner_modes,
        "disallowed_runner_modes": disallowed_runner_modes,
        "future_admission_requirements": future_admission_requirements,
        "safety_notes": safety_notes,
        "findings": findings,
    }
    print(json.dumps(report_payload, indent=2))

    if status == "pass":
        return 0
    if status == "warn" and args.allow_warn:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
