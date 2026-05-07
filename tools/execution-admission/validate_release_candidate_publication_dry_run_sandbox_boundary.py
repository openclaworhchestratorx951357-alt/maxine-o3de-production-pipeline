#!/usr/bin/env python3
"""Validate release-candidate publication dry-run sandbox boundary v1."""

from __future__ import annotations

import argparse
import json
import re
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
EXPECTED_SANDBOX_BOUNDARY_STATUS = "static_boundary_valid_blocked"
EXPECTED_NON_APPROVAL_DECISION_STATUS = "active_non_approval"
EXPECTED_NON_APPROVAL_DECISION_EFFECT = "candidate_remains_blocked_unadmitted"
EXPECTED_NON_APPROVAL_DECISION_TYPE = "non_approval"
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

DEFAULT_BOUNDARY_REL = Path(
    "examples/execution-admission/"
    "release_candidate_package_publish_dry_run_sandbox_boundary_v1.json"
)
DEFAULT_SCHEMA_REL = Path(
    "schemas/maxine_release_candidate_publication_dry_run_sandbox_boundary.schema.json"
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
    "production_readiness_status",
    "noop_receipt_status",
)

REQUIRED_FLAG_FALSE_FIELDS = (
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

REQUIRED_FORBIDDEN_ROOT_TOKENS = {
    "engine_root_paths": "forbidden_roots_missing_engine_category",
    "production_deployment_paths": "forbidden_roots_missing_production_category",
    "o3de_cache_paths": "forbidden_roots_missing_cache_live_db_category",
    "publish_export_destinations": "forbidden_roots_missing_publish_export_category",
    "destructive_cleanup_targets": "forbidden_roots_missing_destructive_cleanup_category",
}

REQUIRED_FORBIDDEN_PATH_PATTERNS = {
    "parent_traversal": "forbidden_path_patterns_missing_parent_traversal",
    "absolute_path_escape": "forbidden_path_patterns_missing_absolute_path_escape",
}

REQUIRED_PATH_NORMALIZATION_TOKENS = {
    "no_parent_traversal": "required_path_normalization_missing_no_parent_traversal",
    "no_symlink_traversal": "required_path_normalization_missing_no_symlink_escape",
    "no_junction_traversal": "required_path_normalization_missing_no_junction_escape",
    "canonical_path_must_remain_within_allowed_sandbox_root": (
        "required_path_normalization_missing_canonical_sandbox_containment"
    ),
}

REQUIRED_LIVE_SURFACE_BLOCKS = {
    "o3de_execution": "live_surface_blocks_missing_o3de_execution",
    "editor_runtime_execution": "live_surface_blocks_missing_editor_runtime_execution",
    "asset_processor_execution": "live_surface_blocks_missing_asset_processor_execution",
    "blender_dcc_execution": "live_surface_blocks_missing_blender_dcc_execution",
    "spawn": "live_surface_blocks_missing_spawn_publish",
    "publish_export": "live_surface_blocks_missing_spawn_publish",
    "cache_live_db_access": "live_surface_blocks_missing_cache_live_db_access",
    "production_path_writes": "live_surface_blocks_missing_production_engine_writes",
    "engine_path_writes": "live_surface_blocks_missing_production_engine_writes",
}

REQUIRED_INVALIDATION_CONDITIONS = {
    "write_outside_allowed_sandbox_root": "invalidation_conditions_missing_write_outside_sandbox",
    "live_tool_or_runtime_invocation_attempt": "invalidation_conditions_missing_live_runtime_tool_invocation",
    "spawn_or_publish_attempt": "invalidation_conditions_missing_spawn_publish_attempt",
    "receipt_issued_without_explicit_admission": "invalidation_conditions_missing_receipt_without_admission",
    "authoritative_id_claim_attempt": "invalidation_conditions_missing_authoritative_id_claim",
}

REQUIRED_ALLOWED_EXTENSIONS = {".json", ".md", ".txt", ".sha256"}
REQUIRED_FORBIDDEN_EXTENSION_CLASSES = {
    ".exe",
    ".dll",
    ".bat",
    ".cmd",
    ".ps1",
    ".db",
    ".sqlite",
    ".cache",
}
EXECUTABLE_EXTENSIONS = {".exe", ".dll", ".bat", ".cmd", ".ps1", ".py"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate release-candidate publication dry-run sandbox boundary v1."
        )
    )
    parser.add_argument(
        "boundary_path",
        nargs="?",
        default=str(DEFAULT_BOUNDARY_REL),
        help="Path to release-candidate publication dry-run sandbox boundary JSON.",
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
        ("publish allowed", "sandbox_boundary_allows_publish"),
        ("spawn allowed", "sandbox_boundary_allows_spawn"),
        ("production path writes allowed", "sandbox_boundary_allows_production_path_writes"),
        ("engine path writes allowed", "sandbox_boundary_allows_engine_path_writes"),
        ("cache/live db access allowed", "sandbox_boundary_allows_cache_live_db_access"),
        ("cache live db access allowed", "sandbox_boundary_allows_cache_live_db_access"),
        (
            "authoritative source uuid claims allowed",
            "sandbox_boundary_allows_authoritative_source_uuid_claims",
        ),
        (
            "authoritative asset id claims allowed",
            "sandbox_boundary_allows_authoritative_asset_id_claims",
        ),
        (
            "authoritative product id claims allowed",
            "sandbox_boundary_allows_authoritative_product_id_claims",
        ),
        ("runner implemented", "sandbox_boundary_claims_runner_implemented"),
        ("dry-run executed", "sandbox_boundary_claims_dry_run_executed"),
    )
    for needle, finding_id in checks:
        if needle in text:
            add_finding(
                findings,
                finding_id,
                "error",
                "Sandbox boundary text must not allow blocked surfaces or claims.",
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


def _validate_root_path_value(
    raw: str,
    require_sandbox_prefix: bool,
) -> Tuple[bool, str]:
    normalized = raw.strip().replace("\\", "/")
    if not normalized:
        return False, "empty"
    if re.match(r"^[A-Za-z]:[/\\]", raw.strip()) or normalized.startswith("/") or normalized.startswith("//"):
        return False, "absolute_or_uncontrolled"
    if "/../" in f"/{normalized}/" or "\\..\\" in f"\\{raw.strip()}\\":  # defensive
        return False, "parent_traversal"
    if normalized.startswith("../") or normalized.startswith("..\\"):
        return False, "parent_traversal"
    if require_sandbox_prefix and not normalized.lower().startswith("examples/sandbox/"):
        return False, "outside_sandbox"
    return True, normalized


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    boundary_path = (
        Path(args.boundary_path).resolve()
        if Path(args.boundary_path).is_absolute()
        else (repo_root / args.boundary_path).resolve()
    )
    schema_path = (repo_root / DEFAULT_SCHEMA_REL).resolve()

    if not boundary_path.exists():
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": f"sandbox boundary contract not found: {boundary_path}",
                },
                indent=2,
            )
        )
        return 2
    if not schema_path.exists():
        print(
            json.dumps(
                {"status": "fail", "error": f"schema not found: {schema_path}"},
                indent=2,
            )
        )
        return 2

    boundary = load_json(boundary_path)
    schema = load_json(schema_path)
    findings: List[Dict[str, Any]] = []

    ok, schema_errors = validate_schema(boundary, schema)
    if not ok:
        for message in schema_errors:
            add_finding(
                findings,
                "schema_validation_error",
                "error",
                "Sandbox boundary contract failed schema validation.",
                {"error": message},
            )

    source_artifacts = (
        boundary.get("source_artifacts")
        if isinstance(boundary.get("source_artifacts"), dict)
        else {}
    )
    missing_ref_fields = sorted(
        field for field in REQUIRED_SOURCE_REFERENCE_FIELDS if field not in source_artifacts
    )
    if missing_ref_fields:
        add_finding(
            findings,
            "source_artifacts_missing_required_reference",
            "error",
            "source_artifacts is missing one or more required source references.",
            {"missing_fields": missing_ref_fields},
        )

    matrix_path = _path_from_source_artifacts(repo_root, source_artifacts, "candidate_matrix_ref", DEFAULT_MATRIX_REL)
    preflight_path = _path_from_source_artifacts(repo_root, source_artifacts, "preflight_contracts_ref", DEFAULT_PREFLIGHT_REL)
    preflight_proof_path = _path_from_source_artifacts(repo_root, source_artifacts, "preflight_proof_packages_ref", DEFAULT_PREFLIGHT_PROOF_REL)
    rollup_path = _path_from_source_artifacts(repo_root, source_artifacts, "readiness_rollup_ref", DEFAULT_ROLLUP_REL)
    dry_run_plan_path = _path_from_source_artifacts(repo_root, source_artifacts, "dry_run_plan_ref", DEFAULT_DRY_RUN_PLAN_REL)
    dry_run_receipt_contract_path = _path_from_source_artifacts(repo_root, source_artifacts, "dry_run_receipt_contract_ref", DEFAULT_DRY_RUN_RECEIPT_CONTRACT_REL)
    dry_run_receipt_blocked_path = _path_from_source_artifacts(repo_root, source_artifacts, "blocked_unissued_receipt_ref", DEFAULT_DRY_RUN_RECEIPT_BLOCKED_REL)
    admission_blockers_path = _path_from_source_artifacts(repo_root, source_artifacts, "admission_blocker_checklist_ref", DEFAULT_ADMISSION_BLOCKERS_REL)
    operator_packet_path = _path_from_source_artifacts(repo_root, source_artifacts, "operator_approval_packet_ref", DEFAULT_OPERATOR_PACKET_REL)
    operator_packet_completeness_path = _path_from_source_artifacts(repo_root, source_artifacts, "operator_approval_packet_completeness_ref", DEFAULT_OPERATOR_PACKET_COMPLETENESS_REL)
    approval_request_readiness_path = _path_from_source_artifacts(repo_root, source_artifacts, "approval_request_readiness_ref", DEFAULT_APPROVAL_REQUEST_READINESS_REL)
    non_approval_decision_path = _path_from_source_artifacts(repo_root, source_artifacts, "non_approval_decision_ref", DEFAULT_NON_APPROVAL_DECISION_REL)
    production_readiness_path = _path_from_source_artifacts(repo_root, source_artifacts, "production_readiness_report_ref", DEFAULT_PRODUCTION_READINESS_REL)
    noop_decision_path = _path_from_source_artifacts(repo_root, source_artifacts, "noop_receipt_status_ref", DEFAULT_NOOP_DECISION_REL)

    artifact_paths: Dict[str, Path] = {
        "candidate_matrix_ref": matrix_path,
        "preflight_contracts_ref": preflight_path,
        "preflight_proof_packages_ref": preflight_proof_path,
        "readiness_rollup_ref": rollup_path,
        "dry_run_plan_ref": dry_run_plan_path,
        "dry_run_receipt_contract_ref": dry_run_receipt_contract_path,
        "blocked_unissued_receipt_ref": dry_run_receipt_blocked_path,
        "admission_blocker_checklist_ref": admission_blockers_path,
        "operator_approval_packet_ref": operator_packet_path,
        "operator_approval_packet_completeness_ref": operator_packet_completeness_path,
        "approval_request_readiness_ref": approval_request_readiness_path,
        "non_approval_decision_ref": non_approval_decision_path,
        "production_readiness_report_ref": production_readiness_path,
        "noop_receipt_status_ref": noop_decision_path,
    }
    for field, path in artifact_paths.items():
        if not path.exists():
            add_finding(
                findings,
                "source_artifact_missing",
                "error",
                "Referenced source artifact does not exist.",
                {"field": field, "path": str(path)},
            )
            if field == "non_approval_decision_ref":
                add_finding(
                    findings,
                    "non_approval_decision_validation_failed",
                    "error",
                    "Non-approval decision validator must pass.",
                    {"reason": "missing_source_artifact", "path": str(path)},
                )

    source_status_reported = (
        boundary.get("source_artifact_validation_status")
        if isinstance(boundary.get("source_artifact_validation_status"), dict)
        else {}
    )
    source_status_expected: Dict[str, str] = {key: "fail" for key in SOURCE_STATUS_KEYS}

    if args.skip_source_validators:
        for key in SOURCE_STATUS_KEYS:
            source_status_expected[key] = str(source_status_reported.get(key, "")).strip() or "fail"
    else:
        if matrix_path.exists():
            code, payload, raw_error = run_validator(repo_root, MATRIX_VALIDATOR_REL, [str(matrix_path)])
            if code == 0 and payload and payload.get("status") == "pass":
                source_status_expected["candidate_matrix_status"] = "pass"
            else:
                add_finding(findings, "candidate_matrix_validation_failed", "error", "Candidate matrix validator must pass.", {"return_code": code, "raw_error": raw_error})

        if preflight_path.exists():
            code, payload, raw_error = run_validator(repo_root, PREFLIGHT_VALIDATOR_REL, [str(preflight_path)])
            if code == 0 and payload and payload.get("status") == "pass":
                source_status_expected["preflight_contracts_status"] = "pass"
            else:
                add_finding(findings, "preflight_contracts_validation_failed", "error", "Preflight contracts validator must pass.", {"return_code": code, "raw_error": raw_error})

        if preflight_proof_path.exists():
            code, payload, raw_error = run_validator(
                repo_root,
                PREFLIGHT_PROOF_VALIDATOR_REL,
                [str(preflight_proof_path), "--matrix-path", str(matrix_path), "--preflight-path", str(preflight_path)],
            )
            if code == 0 and payload and payload.get("status") == "pass":
                source_status_expected["preflight_proof_packages_status"] = "pass"
            else:
                add_finding(findings, "preflight_proof_packages_validation_failed", "error", "Preflight proof package validator must pass.", {"return_code": code, "raw_error": raw_error})

        if rollup_path.exists():
            code, payload, raw_error = run_validator(repo_root, READINESS_ROLLUP_VALIDATOR_REL, [str(rollup_path)])
            if code == 0 and payload and payload.get("status") == "pass":
                source_status_expected["readiness_rollup_status"] = "pass"
            else:
                add_finding(findings, "readiness_rollup_validation_failed", "error", "Readiness rollup validator must pass.", {"return_code": code, "raw_error": raw_error})

        if dry_run_plan_path.exists():
            code, payload, raw_error = run_validator(repo_root, DRY_RUN_PLAN_VALIDATOR_REL, [str(dry_run_plan_path)])
            if code == 0 and payload and payload.get("status") == "pass":
                source_status_expected["dry_run_plan_status"] = "pass"
            else:
                add_finding(findings, "dry_run_plan_validation_failed", "error", "Dry-run plan validator must pass.", {"return_code": code, "raw_error": raw_error})

        if dry_run_receipt_contract_path.exists():
            code, payload, raw_error = run_validator(repo_root, DRY_RUN_RECEIPT_VALIDATOR_REL, [str(dry_run_receipt_contract_path)])
            if code == 0 and payload and payload.get("status") == "pass":
                source_status_expected["dry_run_receipt_contract_status"] = "pass"
            else:
                add_finding(findings, "dry_run_receipt_contract_validation_failed", "error", "Dry-run receipt contract validator must pass.", {"return_code": code, "raw_error": raw_error})

        if dry_run_receipt_blocked_path.exists():
            code, payload, raw_error = run_validator(repo_root, DRY_RUN_RECEIPT_VALIDATOR_REL, [str(dry_run_receipt_blocked_path)])
            if code == 0 and payload and payload.get("status") == "pass":
                source_status_expected["blocked_unissued_receipt_status"] = "pass"
            else:
                add_finding(findings, "blocked_unissued_receipt_validation_failed", "error", "Blocked/unissued receipt validator must pass.", {"return_code": code, "raw_error": raw_error})

        if admission_blockers_path.exists():
            code, payload, raw_error = run_validator(repo_root, ADMISSION_BLOCKERS_VALIDATOR_REL, [str(admission_blockers_path)])
            if code == 0 and payload and payload.get("status") == "pass":
                source_status_expected["admission_blocker_checklist_status"] = "pass"
            else:
                add_finding(findings, "admission_blocker_checklist_validation_failed", "error", "Admission blocker checklist validator must pass.", {"return_code": code, "raw_error": raw_error})

        if operator_packet_path.exists():
            code, payload, raw_error = run_validator(repo_root, OPERATOR_PACKET_VALIDATOR_REL, [str(operator_packet_path)])
            if code == 0 and payload and payload.get("status") == "pass":
                source_status_expected["operator_approval_packet_status"] = "pass"
            else:
                add_finding(findings, "operator_approval_packet_validation_failed", "error", "Operator approval packet validator must pass.", {"return_code": code, "raw_error": raw_error})

        if operator_packet_completeness_path.exists():
            code, payload, raw_error = run_validator(repo_root, OPERATOR_PACKET_COMPLETENESS_VALIDATOR_REL, [str(operator_packet_completeness_path)])
            if code == 0 and payload and payload.get("status") == "pass":
                source_status_expected["operator_approval_packet_completeness_status"] = "pass"
            else:
                add_finding(findings, "operator_approval_packet_completeness_validation_failed", "error", "Operator approval packet completeness validator must pass.", {"return_code": code, "raw_error": raw_error})

        if approval_request_readiness_path.exists():
            code, payload, raw_error = run_validator(repo_root, APPROVAL_REQUEST_READINESS_VALIDATOR_REL, [str(approval_request_readiness_path)])
            if code == 0 and payload and payload.get("status") == "pass":
                source_status_expected["approval_request_readiness_status"] = "pass"
            else:
                add_finding(findings, "approval_request_readiness_validation_failed", "error", "Approval request readiness validator must pass.", {"return_code": code, "raw_error": raw_error})

        if non_approval_decision_path.exists():
            code, payload, raw_error = run_validator(repo_root, NON_APPROVAL_DECISION_VALIDATOR_REL, [str(non_approval_decision_path)])
            if code == 0 and payload and payload.get("status") == "pass":
                source_status_expected["non_approval_decision_status"] = "pass"
            else:
                add_finding(findings, "non_approval_decision_validation_failed", "error", "Non-approval decision validator must pass.", {"return_code": code, "raw_error": raw_error})

    production_payload_raw = load_json(production_readiness_path) if production_readiness_path.exists() else {}
    if production_payload_raw:
        source_status_expected["production_readiness_status"] = _validate_production_readiness_report(production_payload_raw, findings)

    noop_payload_raw = load_json(noop_decision_path) if noop_decision_path.exists() else {}
    if noop_payload_raw:
        source_status_expected["noop_receipt_status"] = _validate_noop_decision_record(noop_payload_raw, findings)

    for key in SOURCE_STATUS_KEYS:
        if str(source_status_reported.get(key, "")).strip() != "pass":
            add_finding(findings, "source_artifact_validation_status_not_pass", "error", "source_artifact_validation_status must report pass for all required sources.", {"field": key, "actual": source_status_reported.get(key)})
        if source_status_expected.get(key) != "pass":
            add_finding(findings, "computed_source_artifact_validation_status_not_pass", "error", "Computed source artifact validation status must pass for all required sources.", {"field": key, "actual": source_status_expected.get(key)})

    candidate_id = str(boundary.get("candidate_id", "")).strip()
    candidate_type = str(boundary.get("candidate_type", "")).strip()
    if candidate_id != TARGET_CANDIDATE_ID:
        add_finding(findings, "candidate_id_mismatch", "error", "candidate_id must be release_candidate_package_publish_dry_run_v1.")
    if candidate_type != TARGET_CANDIDATE_TYPE:
        add_finding(findings, "candidate_type_mismatch", "error", "candidate_type must be dry_run.")

    if str(boundary.get("decision_type", "")).strip() != EXPECTED_NON_APPROVAL_DECISION_TYPE:
        add_finding(findings, "decision_type_not_non_approval", "error", "decision_type must remain non_approval.")
    if str(boundary.get("sandbox_boundary_status", "")).strip() != EXPECTED_SANDBOX_BOUNDARY_STATUS:
        add_finding(findings, "sandbox_boundary_status_not_static_boundary_valid_blocked", "error", "sandbox_boundary_status must be static_boundary_valid_blocked.")
    if str(boundary.get("admission_status", "")).strip() != "unadmitted":
        add_finding(findings, "admission_status_not_unadmitted", "error", "admission_status must remain unadmitted.")
    if bool(boundary.get("runner_implemented", False)):
        add_finding(findings, "runner_implemented_not_allowed", "error", "runner_implemented must remain false.")

    for field, finding_id in REQUIRED_FLAG_FALSE_FIELDS:
        if bool(boundary.get(field, False)):
            add_finding(findings, finding_id, "error", f"{field} must remain false.")

    allowed_read_roots = _check_non_empty_string_list(boundary, "allowed_read_roots", findings, "allowed_read_roots_missing_or_empty", "allowed_read_roots must be present and non-empty.")
    allowed_write_roots = _check_non_empty_string_list(boundary, "allowed_write_roots", findings, "allowed_write_roots_missing_or_empty", "allowed_write_roots must be present and non-empty.")
    allowed_receipt_roots = _check_non_empty_string_list(boundary, "allowed_receipt_roots", findings, "allowed_receipt_roots_missing_or_empty", "allowed_receipt_roots must be present and non-empty.")
    allowed_report_roots = _check_non_empty_string_list(boundary, "allowed_report_roots", findings, "allowed_report_roots_missing_or_empty", "allowed_report_roots must be present and non-empty.")
    allowed_temp_roots = _check_non_empty_string_list(boundary, "allowed_temp_roots", findings, "allowed_temp_roots_missing_or_empty", "allowed_temp_roots must be present and non-empty.")
    forbidden_roots = _check_non_empty_string_list(boundary, "forbidden_roots", findings, "forbidden_roots_missing_or_empty", "forbidden_roots must be present and non-empty.")
    forbidden_path_patterns = _check_non_empty_string_list(boundary, "forbidden_path_patterns", findings, "forbidden_path_patterns_missing_or_empty", "forbidden_path_patterns must be present and non-empty.")
    allowed_file_extensions = _check_non_empty_string_list(boundary, "allowed_file_extensions", findings, "allowed_file_extensions_missing_or_empty", "allowed_file_extensions must be present and non-empty.")
    forbidden_file_extensions = _check_non_empty_string_list(boundary, "forbidden_file_extensions", findings, "forbidden_file_extensions_missing_or_empty", "forbidden_file_extensions must be present and non-empty.")
    required_path_normalization = _check_non_empty_string_list(boundary, "required_path_normalization", findings, "required_path_normalization_missing_or_empty", "required_path_normalization must be present and non-empty.")
    cleanup_rollback_requirements = _check_non_empty_string_list(boundary, "cleanup_rollback_requirements", findings, "cleanup_rollback_requirements_missing_or_empty", "cleanup_rollback_requirements must be present and non-empty.")
    live_surface_blocks = _check_non_empty_string_list(boundary, "live_surface_blocks", findings, "live_surface_blocks_missing_or_empty", "live_surface_blocks must be present and non-empty.")
    invalidation_conditions = _check_non_empty_string_list(boundary, "invalidation_conditions", findings, "invalidation_conditions_missing_or_empty", "invalidation_conditions must be present and non-empty.")

    required_output_index = boundary.get("required_output_index") if isinstance(boundary.get("required_output_index"), dict) else {}
    if not required_output_index:
        add_finding(findings, "required_output_index_missing", "error", "required_output_index must be present.")
    required_hashing = boundary.get("required_hashing") if isinstance(boundary.get("required_hashing"), dict) else {}
    if not required_hashing:
        add_finding(findings, "required_hashing_missing", "error", "required_hashing must be present.")

    runner_interface_constraints = (
        boundary.get("runner_interface_constraints")
        if isinstance(boundary.get("runner_interface_constraints"), dict)
        else {}
    )
    if not runner_interface_constraints:
        add_finding(findings, "runner_interface_constraints_missing", "error", "runner_interface_constraints must be present.")
    if bool(runner_interface_constraints.get("runner_implemented", False)):
        add_finding(findings, "runner_interface_constraints_runner_implemented_not_false", "error", "runner_interface_constraints must keep runner_implemented=false.")
    if runner_interface_constraints.get("future_runner_requires_separate_proposal") is not True:
        add_finding(findings, "runner_interface_constraints_missing_separate_proposal_requirement", "error", "runner_interface_constraints must require a separate future proposal.")

    _check_required_token_set(forbidden_roots, REQUIRED_FORBIDDEN_ROOT_TOKENS, findings, "forbidden_roots")
    _check_required_token_set(forbidden_path_patterns, REQUIRED_FORBIDDEN_PATH_PATTERNS, findings, "forbidden_path_patterns")
    _check_required_token_set(required_path_normalization, REQUIRED_PATH_NORMALIZATION_TOKENS, findings, "required_path_normalization")
    _check_required_token_set(live_surface_blocks, REQUIRED_LIVE_SURFACE_BLOCKS, findings, "live_surface_blocks")
    _check_required_token_set(invalidation_conditions, REQUIRED_INVALIDATION_CONDITIONS, findings, "invalidation_conditions")

    allowed_extension_set = {item.lower() for item in allowed_file_extensions}
    if not REQUIRED_ALLOWED_EXTENSIONS.issubset(allowed_extension_set):
        missing = sorted(REQUIRED_ALLOWED_EXTENSIONS - allowed_extension_set)
        add_finding(findings, "allowed_file_extensions_missing_required_static_formats", "error", "allowed_file_extensions must include required static report/receipt/hash formats.", {"missing": missing})
    if any(ext in EXECUTABLE_EXTENSIONS for ext in allowed_extension_set):
        add_finding(findings, "allowed_file_extensions_include_executable_or_binary", "error", "allowed_file_extensions must not include executable/binary/runtime extensions.")

    forbidden_extension_set = {item.lower() for item in forbidden_file_extensions}
    missing_forbidden = sorted(REQUIRED_FORBIDDEN_EXTENSION_CLASSES - forbidden_extension_set)
    if missing_forbidden:
        add_finding(findings, "forbidden_file_extensions_missing_required_class", "error", "forbidden_file_extensions must include executable/binary/runtime/cache/database classes.", {"missing": missing_forbidden})

    for root in allowed_read_roots:
        ok_root, reason = _validate_root_path_value(root, False)
        if not ok_root:
            add_finding(findings, "allowed_read_root_invalid_path", "error", "allowed_read_roots entries must be safe repo-relative paths.", {"root": root, "reason": reason})

    for root in allowed_write_roots:
        normalized = str(root).replace("\\", "/").strip().lower()
        if "engine" in normalized:
            add_finding(findings, "allowed_write_root_under_engine_path", "error", "allowed_write_roots must not include engine paths.", {"root": root})
        if "production" in normalized:
            add_finding(findings, "allowed_write_root_under_production_path", "error", "allowed_write_roots must not include production paths.", {"root": root})
        if "cache" in normalized or "live-db" in normalized or "livedb" in normalized:
            add_finding(findings, "allowed_write_root_under_cache_live_db_path", "error", "allowed_write_roots must not include Cache/live DB paths.", {"root": root})
        if re.search(r"(^|/)publish(/|$)", normalized) or re.search(r"(^|/)export(/|$)", normalized):
            add_finding(findings, "allowed_write_root_under_publish_export_path", "error", "allowed_write_roots must not include publish/export paths.", {"root": root})

        ok_root, normalized_or_reason = _validate_root_path_value(root, True)
        if not ok_root:
            finding_id = "allowed_write_root_absolute_or_uncontrolled" if normalized_or_reason == "absolute_or_uncontrolled" else "allowed_write_root_outside_sandbox"
            if normalized_or_reason == "parent_traversal":
                finding_id = "allowed_write_root_outside_sandbox"
            add_finding(findings, finding_id, "error", "allowed_write_roots entries must remain under safe sandbox-only relative paths.", {"root": root, "reason": normalized_or_reason})
            continue

    for key, values in (
        ("allowed_receipt_roots", allowed_receipt_roots),
        ("allowed_report_roots", allowed_report_roots),
        ("allowed_temp_roots", allowed_temp_roots),
    ):
        for root in values:
            ok_root, reason = _validate_root_path_value(root, True)
            if not ok_root:
                add_finding(findings, f"{key}_invalid_path", "error", f"{key} entries must remain under safe sandbox-only relative paths.", {"root": root, "reason": reason})

    approval_request_readiness_payload_raw = load_json(approval_request_readiness_path) if approval_request_readiness_path.exists() else {}
    non_approval_decision_payload_raw = load_json(non_approval_decision_path) if non_approval_decision_path.exists() else {}
    rollup_payload_raw = load_json(rollup_path) if rollup_path.exists() else {}
    dry_run_plan_payload_raw = load_json(dry_run_plan_path) if dry_run_plan_path.exists() else {}
    dry_run_receipt_contract_payload_raw = load_json(dry_run_receipt_contract_path) if dry_run_receipt_contract_path.exists() else {}
    dry_run_receipt_blocked_payload_raw = load_json(dry_run_receipt_blocked_path) if dry_run_receipt_blocked_path.exists() else {}
    admission_blockers_payload_raw = load_json(admission_blockers_path) if admission_blockers_path.exists() else {}
    operator_packet_payload_raw = load_json(operator_packet_path) if operator_packet_path.exists() else {}
    operator_packet_completeness_payload_raw = load_json(operator_packet_completeness_path) if operator_packet_completeness_path.exists() else {}
    matrix_payload_raw = load_json(matrix_path) if matrix_path.exists() else {}
    preflight_payload_raw = load_json(preflight_path) if preflight_path.exists() else {}
    preflight_proof_payload_raw = load_json(preflight_proof_path) if preflight_proof_path.exists() else {}

    matrix_map = _candidate_map(matrix_payload_raw, "candidates")
    matrix_entry = matrix_map.get(TARGET_CANDIDATE_ID)
    if not isinstance(matrix_entry, dict):
        add_finding(findings, "candidate_missing_in_matrix", "error", "Target candidate must exist in candidate matrix.")
    elif str(matrix_entry.get("current_status", "")).strip() == "admitted":
        add_finding(findings, "dry_run_admitted_not_allowed", "error", "Target candidate must remain unadmitted in candidate matrix.")

    preflight_map = _candidate_map(preflight_payload_raw, "contracts")
    preflight_entry = preflight_map.get(TARGET_CANDIDATE_ID)
    if not isinstance(preflight_entry, dict):
        add_finding(findings, "candidate_missing_in_preflight_contracts", "error", "Target candidate must exist in preflight contracts.")
    elif str(preflight_entry.get("admission_status", "")).strip() != "unadmitted":
        add_finding(findings, "admission_status_mismatch_with_preflight_contracts", "error", "Target candidate must remain unadmitted in preflight contracts.")

    preflight_proof_map = _candidate_map(preflight_proof_payload_raw, "proof_packages")
    preflight_proof_entry = preflight_proof_map.get(TARGET_CANDIDATE_ID)
    if not isinstance(preflight_proof_entry, dict):
        add_finding(findings, "candidate_missing_in_preflight_proof_packages", "error", "Target candidate must exist in preflight proof packages.")
    elif str(preflight_proof_entry.get("admission_status", "")).strip() != "unadmitted":
        add_finding(findings, "admission_status_mismatch_with_preflight_proof_packages", "error", "Target candidate must remain unadmitted in preflight proof packages.")

    if str(rollup_payload_raw.get("overall_readiness_rollup_status", "")).strip() != EXPECTED_ROLLUP_STATUS:
        add_finding(findings, "readiness_rollup_status_not_expected", "error", "Readiness rollup must keep overall_readiness_rollup_status=static_rollup_valid_blocked.")
    next_slice = rollup_payload_raw.get("safest_next_preparation_slice") if isinstance(rollup_payload_raw.get("safest_next_preparation_slice"), dict) else {}
    if str(next_slice.get("slice_id", "")).strip() != EXPECTED_ROLLUP_NEXT_SLICE_ID:
        add_finding(findings, "readiness_rollup_next_slice_id_mismatch", "error", "Readiness rollup must keep safest_next_preparation_slice.slice_id=candidate_specific_dry_run_planning_v1.")
    if str(dry_run_plan_payload_raw.get("plan_status", "")).strip() != EXPECTED_DRY_RUN_PLAN_STATUS:
        add_finding(findings, "dry_run_plan_status_not_expected", "error", "Dry-run plan must keep plan_status=static_plan_valid_blocked.")
    if str(dry_run_receipt_contract_payload_raw.get("receipt_contract_status", "")).strip() != EXPECTED_RECEIPT_CONTRACT_STATUS:
        add_finding(findings, "dry_run_receipt_contract_status_not_expected", "error", "Dry-run receipt contract must keep receipt_contract_status=static_contract_valid_blocked.")
    if str(dry_run_receipt_contract_payload_raw.get("receipt_type", "")).strip() != TARGET_RECEIPT_TYPE:
        add_finding(findings, "dry_run_receipt_type_mismatch", "error", "Dry-run receipt contract must keep receipt_type=release_candidate_package_publish_dry_run_receipt_v1.")
    if str(dry_run_receipt_blocked_payload_raw.get("receipt_status", "")).strip() != EXPECTED_BLOCKED_RECEIPT_STATUS:
        add_finding(findings, "blocked_unissued_receipt_status_mismatch", "error", "Blocked/unissued receipt example must keep receipt_status=blocked_unissued_contract_only.")
    if str(admission_blockers_payload_raw.get("checklist_status", "")).strip() != EXPECTED_ADMISSION_BLOCKERS_STATUS:
        add_finding(findings, "admission_blockers_status_not_expected", "error", "Admission blockers checklist must keep checklist_status=static_checklist_valid_blocked.")
    if str(operator_packet_payload_raw.get("approval_packet_status", "")).strip() != EXPECTED_OPERATOR_PACKET_STATUS:
        add_finding(findings, "operator_approval_packet_status_not_expected", "error", "Operator approval packet must keep approval_packet_status=static_template_valid_blocked.")
    if str(operator_packet_completeness_payload_raw.get("completeness_review_status", "")).strip() != EXPECTED_COMPLETENESS_STATUS:
        add_finding(findings, "operator_approval_packet_completeness_status_not_expected", "error", "Operator approval packet completeness must keep completeness_review_status=static_completeness_valid_blocked.")

    if str(approval_request_readiness_payload_raw.get("approval_request_readiness_status", "")).strip() != EXPECTED_APPROVAL_REQUEST_READINESS_STATUS:
        add_finding(findings, "approval_request_readiness_status_not_expected", "error", "Approval request readiness report must keep approval_request_readiness_status=static_request_readiness_valid_blocked.")
    if str(approval_request_readiness_payload_raw.get("final_recommendation", "")).strip() != EXPECTED_APPROVAL_REQUEST_READINESS_FINAL_RECOMMENDATION:
        add_finding(findings, "approval_request_readiness_final_recommendation_not_expected", "error", "Approval request readiness report must keep final_recommendation=do_not_request_approval_yet.")

    if str(non_approval_decision_payload_raw.get("decision_type", "")).strip() != EXPECTED_NON_APPROVAL_DECISION_TYPE:
        add_finding(findings, "non_approval_decision_type_not_expected", "error", "Non-approval decision record must keep decision_type=non_approval.")
    if str(non_approval_decision_payload_raw.get("decision_status", "")).strip() != EXPECTED_NON_APPROVAL_DECISION_STATUS:
        add_finding(findings, "non_approval_decision_status_not_expected", "error", "Non-approval decision record must keep decision_status=active_non_approval.")
    if str(non_approval_decision_payload_raw.get("decision_effect", "")).strip() != EXPECTED_NON_APPROVAL_DECISION_EFFECT:
        add_finding(findings, "non_approval_decision_effect_not_expected", "error", "Non-approval decision record must keep decision_effect=candidate_remains_blocked_unadmitted.")
    if str(non_approval_decision_payload_raw.get("selected_operator_decision", "")).strip() != EXPECTED_SELECTED_OPERATOR_DECISION:
        add_finding(findings, "non_approval_selected_operator_decision_not_expected", "error", "Non-approval decision record must keep selected_operator_decision=do_not_approve.")
    if str(non_approval_decision_payload_raw.get("next_recommended_action", "")).strip() != EXPECTED_NEXT_RECOMMENDED_ACTION:
        add_finding(findings, "non_approval_next_recommended_action_not_expected", "error", "Non-approval decision record must keep next_recommended_action=continue_hardening_no_execution.")

    for payload_name, payload_value in (
        ("dry_run_plan", dry_run_plan_payload_raw),
        ("dry_run_receipt_contract", dry_run_receipt_contract_payload_raw),
        ("blocked_unissued_receipt", dry_run_receipt_blocked_payload_raw),
        ("admission_blockers", admission_blockers_payload_raw),
        ("operator_approval_packet", operator_packet_payload_raw),
        ("operator_approval_packet_completeness", operator_packet_completeness_payload_raw),
        ("approval_request_readiness", approval_request_readiness_payload_raw),
        ("non_approval_decision", non_approval_decision_payload_raw),
    ):
        if str(payload_value.get("candidate_id", "")).strip() != TARGET_CANDIDATE_ID:
            add_finding(findings, "candidate_id_mismatch_with_source_artifact", "error", "Source artifacts must target release_candidate_package_publish_dry_run_v1.", {"artifact": payload_name})
        if str(payload_value.get("candidate_type", "")).strip() != TARGET_CANDIDATE_TYPE:
            add_finding(findings, "candidate_type_mismatch_with_source_artifact", "error", "Source artifacts must keep candidate_type=dry_run.", {"artifact": payload_name})

    approval_phrase = str(boundary.get("future_admission_requirements", "")).lower()
    if EXPECTED_APPROVAL_PHRASE.lower() not in approval_phrase:
        add_finding(findings, "required_approval_phrase_missing_from_future_requirements", "error", "future_admission_requirements must include the exact candidate-specific approval phrase.")

    if bool(boundary.get("unsafe_claims_detected", False)):
        add_finding(findings, "unsafe_claims_detected_not_allowed", "error", "unsafe_claims_detected must remain false.")
    safety_notes = as_string_list(boundary.get("safety_notes"))
    if not safety_notes:
        add_finding(findings, "safety_notes_missing_or_empty", "error", "safety_notes must be present and non-empty.")

    _check_forbidden_claim_language(boundary, findings)

    severity_set = {str(item.get("severity", "")).strip() for item in findings}
    status = "fail" if "error" in severity_set else "pass"

    report_payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_SANDBOX_BOUNDARY_VALIDATION_v1_REPORT",
        "status": status,
        "release_candidate_publication_dry_run_sandbox_boundary_present": True,
        "release_candidate_publication_dry_run_sandbox_boundary_path": str(boundary_path),
        "candidate_matrix_path": str(matrix_path),
        "preflight_contracts_path": str(preflight_path),
        "preflight_proof_packages_path": str(preflight_proof_path),
        "readiness_rollup_path": str(rollup_path),
        "dry_run_plan_path": str(dry_run_plan_path),
        "dry_run_receipt_contract_path": str(dry_run_receipt_contract_path),
        "blocked_unissued_receipt_path": str(dry_run_receipt_blocked_path),
        "admission_blocker_checklist_path": str(admission_blockers_path),
        "operator_approval_packet_path": str(operator_packet_path),
        "operator_approval_packet_completeness_path": str(operator_packet_completeness_path),
        "approval_request_readiness_path": str(approval_request_readiness_path),
        "non_approval_decision_path": str(non_approval_decision_path),
        "production_readiness_report_path": str(production_readiness_path),
        "noop_receipt_status_path": str(noop_decision_path),
        "source_artifact_validation_status": source_status_reported,
        "computed_source_artifact_validation_status": source_status_expected,
        "planned_candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "sandbox_boundary_status": str(boundary.get("sandbox_boundary_status", "")).strip(),
        "admission_status": str(boundary.get("admission_status", "")).strip(),
        "runner_implemented": bool(boundary.get("runner_implemented", False)),
        "approval_request_ready": bool(boundary.get("approval_request_ready", False)),
        "operator_approval_granted": bool(boundary.get("operator_approval_granted", False)),
        "approval_phrase_present": bool(boundary.get("approval_phrase_present", False)),
        "dry_run_admitted": bool(boundary.get("dry_run_admitted", False)),
        "dry_run_executed": bool(boundary.get("dry_run_executed", False)),
        "receipt_issued": bool(boundary.get("receipt_issued", False)),
        "publication_admitted": bool(boundary.get("publication_admitted", False)),
        "real_execution_admitted": bool(boundary.get("real_execution_admitted", False)),
        "production_ready_claimed": bool(boundary.get("production_ready_claimed", False)),
        "allowed_read_roots": allowed_read_roots,
        "allowed_write_roots": allowed_write_roots,
        "allowed_receipt_roots": allowed_receipt_roots,
        "allowed_report_roots": allowed_report_roots,
        "allowed_temp_roots": allowed_temp_roots,
        "forbidden_roots": forbidden_roots,
        "forbidden_path_patterns": forbidden_path_patterns,
        "allowed_file_extensions": allowed_file_extensions,
        "forbidden_file_extensions": forbidden_file_extensions,
        "required_path_normalization": required_path_normalization,
        "required_output_index": required_output_index,
        "required_hashing": required_hashing,
        "cleanup_rollback_requirements": cleanup_rollback_requirements,
        "live_surface_blocks": live_surface_blocks,
        "invalidation_conditions": invalidation_conditions,
        "runner_interface_constraints": runner_interface_constraints,
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
