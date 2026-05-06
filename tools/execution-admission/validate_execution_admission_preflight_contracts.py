#!/usr/bin/env python3
"""Validate execution-admission preflight contracts v1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


NOOP_CANDIDATE_ID = "release_candidate_package_receipt_noop_v1"
REAL_EXECUTION_TYPE = "real_execution"
PUBLICATION_TYPE = "publication"
DRY_RUN_TYPE = "dry_run"

DEFAULT_PREFLIGHT_REL = Path(
    "examples/execution-admission/execution_admission_preflight_contracts_v1.json"
)
DEFAULT_MATRIX_REL = Path(
    "examples/execution-admission/execution_admission_candidate_matrix_v1.json"
)
DEFAULT_SCHEMA_REL = Path(
    "schemas/maxine_execution_admission_preflight_contracts.schema.json"
)

REQUIRED_BLOCKED_SURFACES: Set[str] = {
    "o3de_execution",
    "editor_runtime_execution",
    "asset_processor_execution",
    "blender_dcc_execution",
    "profiler_benchmark_execution",
    "live_screenshot_capture",
    "spawn_publish",
    "cache_live_db_access",
    "authoritative_source_uuid_claims",
    "authoritative_asset_id_claims",
    "authoritative_product_id_claims",
    "production_write",
    "engine_write",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate execution-admission preflight contracts v1."
    )
    parser.add_argument(
        "preflight_path",
        nargs="?",
        default=str(DEFAULT_PREFLIGHT_REL),
        help="Path to execution-admission preflight contracts JSON.",
    )
    parser.add_argument(
        "--matrix-path",
        default=str(DEFAULT_MATRIX_REL),
        help="Path to execution-admission candidate matrix JSON.",
    )
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Return zero when status is warn.",
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
    item: Dict[str, Any] = {
        "id": finding_id,
        "severity": severity,
        "message": message,
    }
    if details:
        item["details"] = details
    findings.append(item)


def as_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    output: List[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            output.append(text)
    return output


def _exact_approval_phrase(candidate_id: str) -> str:
    return f"APPROVE EXECUTION ADMISSION {candidate_id}"


def _is_non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _has_token(items: Any, token: str) -> bool:
    if not isinstance(items, list):
        return False
    token_lower = token.lower()
    for item in items:
        if token_lower in str(item).replace("\\", "/").lower():
            return True
    return False


def _sandbox_paths_valid(paths: Any) -> bool:
    if not isinstance(paths, list) or not paths:
        return False
    for item in paths:
        normalized = str(item).replace("\\", "/").strip().lower()
        if not normalized.startswith("examples/sandbox/"):
            return False
    return True


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    preflight_path = (
        Path(args.preflight_path).resolve()
        if Path(args.preflight_path).is_absolute()
        else (repo_root / args.preflight_path).resolve()
    )
    matrix_path = (
        Path(args.matrix_path).resolve()
        if Path(args.matrix_path).is_absolute()
        else (repo_root / args.matrix_path).resolve()
    )
    schema_path = (repo_root / DEFAULT_SCHEMA_REL).resolve()

    if not preflight_path.exists():
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": f"preflight contracts not found: {preflight_path}",
                },
                indent=2,
            )
        )
        return 2
    if not matrix_path.exists():
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": f"candidate matrix not found: {matrix_path}",
                },
                indent=2,
            )
        )
        return 2
    if not schema_path.exists():
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": f"schema not found: {schema_path}",
                },
                indent=2,
            )
        )
        return 2

    preflight = load_json(preflight_path)
    matrix = load_json(matrix_path)
    schema = load_json(schema_path)
    findings: List[Dict[str, Any]] = []

    ok, schema_errors = validate_schema(preflight, schema)
    if not ok:
        for message in schema_errors:
            add_finding(
                findings,
                "schema_validation_error",
                "error",
                "Preflight contracts failed schema validation.",
                {"error": message},
            )

    contracts_raw = preflight.get("contracts", [])
    contracts = contracts_raw if isinstance(contracts_raw, list) else []
    contract_map: Dict[str, Dict[str, Any]] = {}
    duplicate_contract_ids: Set[str] = set()

    for item in contracts:
        if not isinstance(item, dict):
            add_finding(
                findings,
                "contract_entry_invalid",
                "error",
                "Each contracts[] entry must be an object.",
            )
            continue
        candidate_id = str(item.get("candidate_id", "")).strip()
        if not candidate_id:
            add_finding(
                findings,
                "contract_candidate_id_missing",
                "error",
                "Each preflight contract must include candidate_id.",
            )
            continue
        if candidate_id in contract_map:
            duplicate_contract_ids.add(candidate_id)
        contract_map[candidate_id] = item

    for candidate_id in sorted(duplicate_contract_ids):
        add_finding(
            findings,
            "contract_candidate_id_duplicate",
            "error",
            "Preflight contract candidate IDs must be unique.",
            {"candidate_id": candidate_id},
        )

    matrix_candidates_raw = matrix.get("candidates", [])
    matrix_candidates = matrix_candidates_raw if isinstance(matrix_candidates_raw, list) else []
    matrix_map: Dict[str, Dict[str, Any]] = {}
    duplicate_matrix_ids: Set[str] = set()
    for item in matrix_candidates:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        if candidate_id in matrix_map:
            duplicate_matrix_ids.add(candidate_id)
        matrix_map[candidate_id] = item

    for candidate_id in sorted(duplicate_matrix_ids):
        add_finding(
            findings,
            "matrix_candidate_id_duplicate",
            "error",
            "Candidate matrix candidate IDs must be unique.",
            {"candidate_id": candidate_id},
        )

    matrix_ids = set(matrix_map.keys())
    contract_ids = set(contract_map.keys())

    for candidate_id in sorted(matrix_ids - contract_ids):
        add_finding(
            findings,
            "matrix_candidate_missing_preflight_contract",
            "error",
            "Every candidate matrix candidate must have a preflight contract.",
            {"candidate_id": candidate_id},
        )
    for candidate_id in sorted(contract_ids - matrix_ids):
        add_finding(
            findings,
            "preflight_candidate_missing_from_matrix",
            "error",
            "Every preflight contract candidate must exist in candidate matrix.",
            {"candidate_id": candidate_id},
        )

    admitted_noop_ids = sorted(
        set(as_string_list(preflight.get("admitted_noop_receipt_candidate_ids", [])))
    )
    admitted_real_ids = sorted(
        set(as_string_list(preflight.get("admitted_real_execution_candidate_ids", [])))
    )
    admitted_publication_ids = sorted(
        set(as_string_list(preflight.get("admitted_publication_candidate_ids", [])))
    )
    real_preflight_passed_ids = sorted(
        set(as_string_list(preflight.get("real_execution_preflight_passed_candidate_ids", [])))
    )
    publication_preflight_passed_ids = sorted(
        set(as_string_list(preflight.get("publication_preflight_passed_candidate_ids", [])))
    )

    real_status = str(preflight.get("real_execution_admission_status", "")).strip()
    publication_status = str(preflight.get("publication_admission_status", "")).strip()

    if preflight.get("production_ready_claimed") is not False:
        add_finding(
            findings,
            "production_ready_claim_not_allowed",
            "error",
            "Preflight contracts must not claim production_ready in this slice.",
        )
    if preflight.get("publication_admitted_claimed") is not False:
        add_finding(
            findings,
            "publication_admitted_claim_not_allowed",
            "error",
            "Preflight contracts must not claim publication admitted in this slice.",
        )

    if real_status == "admitted" and not admitted_real_ids:
        add_finding(
            findings,
            "real_execution_status_admitted_without_candidates",
            "error",
            "real_execution_admission_status=admitted requires admitted_real_execution_candidate_ids.",
        )
    if real_status == "blocked" and admitted_real_ids:
        add_finding(
            findings,
            "real_execution_status_blocked_with_admitted_candidates",
            "error",
            "real_execution_admission_status=blocked cannot include admitted real execution candidates.",
            {"admitted_real_execution_candidate_ids": admitted_real_ids},
        )
    if publication_status == "admitted" and not admitted_publication_ids:
        add_finding(
            findings,
            "publication_status_admitted_without_candidates",
            "error",
            "publication_admission_status=admitted requires admitted_publication_candidate_ids.",
        )
    if publication_status == "blocked" and admitted_publication_ids:
        add_finding(
            findings,
            "publication_status_blocked_with_admitted_candidates",
            "error",
            "publication_admission_status=blocked cannot include admitted publication candidates.",
            {"admitted_publication_candidate_ids": admitted_publication_ids},
        )

    if real_preflight_passed_ids:
        add_finding(
            findings,
            "real_execution_preflight_passed_candidates_not_allowed",
            "error",
            "Real execution preflight passed candidates must remain empty in this slice.",
            {"real_execution_preflight_passed_candidate_ids": real_preflight_passed_ids},
        )
    if publication_preflight_passed_ids:
        add_finding(
            findings,
            "publication_preflight_passed_candidates_not_allowed",
            "error",
            "Publication preflight passed candidates must remain empty in this slice.",
            {"publication_preflight_passed_candidate_ids": publication_preflight_passed_ids},
        )

    if admitted_noop_ids != [NOOP_CANDIDATE_ID]:
        add_finding(
            findings,
            "noop_candidate_top_level_mismatch",
            "error",
            "admitted_noop_receipt_candidate_ids must contain only release_candidate_package_receipt_noop_v1.",
            {"actual": admitted_noop_ids},
        )
    if NOOP_CANDIDATE_ID in admitted_real_ids:
        add_finding(
            findings,
            "noop_candidate_misclassified_as_real_execution",
            "error",
            "No-op candidate must not appear in admitted_real_execution_candidate_ids.",
        )
    if NOOP_CANDIDATE_ID in admitted_publication_ids:
        add_finding(
            findings,
            "noop_candidate_misclassified_as_publication",
            "error",
            "No-op candidate must not appear in admitted_publication_candidate_ids.",
        )

    noop_contract = contract_map.get(NOOP_CANDIDATE_ID)
    if not isinstance(noop_contract, dict):
        add_finding(
            findings,
            "noop_candidate_contract_missing",
            "error",
            "Preflight contracts must include release_candidate_package_receipt_noop_v1.",
        )

    for candidate_id in sorted(contract_ids):
        contract = contract_map[candidate_id]
        matrix_candidate = matrix_map.get(candidate_id)

        candidate_type = str(contract.get("candidate_type", "")).strip()
        admission_status = str(contract.get("admission_status", "")).strip()
        preflight_status = str(contract.get("preflight_status", "")).strip()
        matrix_status = str(contract.get("current_candidate_matrix_status", "")).strip()

        expected_phrase = _exact_approval_phrase(candidate_id)
        approval_phrase = str(contract.get("approval_phrase", "")).strip()

        if candidate_type in {REAL_EXECUTION_TYPE, PUBLICATION_TYPE, DRY_RUN_TYPE}:
            if approval_phrase != expected_phrase:
                add_finding(
                    findings,
                    "approval_phrase_mismatch",
                    "error",
                    "approval_phrase must exactly match candidate_id.",
                    {
                        "candidate_id": candidate_id,
                        "expected": expected_phrase,
                        "actual": approval_phrase,
                    },
                )

        if isinstance(matrix_candidate, dict):
            matrix_candidate_type = str(matrix_candidate.get("candidate_type", "")).strip()
            matrix_candidate_status = str(matrix_candidate.get("current_status", "")).strip()
            if candidate_type != matrix_candidate_type:
                add_finding(
                    findings,
                    "candidate_type_mismatch_with_matrix",
                    "error",
                    "candidate_type must match candidate matrix.",
                    {
                        "candidate_id": candidate_id,
                        "matrix_candidate_type": matrix_candidate_type,
                        "contract_candidate_type": candidate_type,
                    },
                )
            if matrix_status != matrix_candidate_status:
                add_finding(
                    findings,
                    "candidate_status_mismatch_with_matrix",
                    "error",
                    "current_candidate_matrix_status must match matrix current_status.",
                    {
                        "candidate_id": candidate_id,
                        "matrix_current_status": matrix_candidate_status,
                        "contract_current_candidate_matrix_status": matrix_status,
                    },
                )

        blocked_surfaces = set(as_string_list(contract.get("blocked_surfaces", [])))

        if candidate_id == NOOP_CANDIDATE_ID:
            if candidate_type != "no_op_receipt":
                if candidate_type == REAL_EXECUTION_TYPE:
                    finding_id = "noop_candidate_misclassified_as_real_execution"
                elif candidate_type == PUBLICATION_TYPE:
                    finding_id = "noop_candidate_misclassified_as_publication"
                else:
                    finding_id = "noop_candidate_wrong_candidate_type"
                add_finding(
                    findings,
                    finding_id,
                    "error",
                    "release_candidate_package_receipt_noop_v1 must stay candidate_type=no_op_receipt.",
                    {"actual_candidate_type": candidate_type},
                )
            if admission_status == "admitted_real_execution":
                add_finding(
                    findings,
                    "noop_candidate_marked_admitted_real_execution",
                    "error",
                    "No-op candidate must not be marked admitted_real_execution.",
                )
            elif admission_status == "admitted_publication":
                add_finding(
                    findings,
                    "noop_candidate_marked_admitted_publication",
                    "error",
                    "No-op candidate must not be marked admitted_publication.",
                )
            elif admission_status != "admitted_no_op_only":
                add_finding(
                    findings,
                    "noop_candidate_wrong_admission_status",
                    "error",
                    "No-op candidate must keep admission_status=admitted_no_op_only.",
                    {"actual_admission_status": admission_status},
                )
            continue

        if candidate_type == REAL_EXECUTION_TYPE:
            if admission_status == "admitted_real_execution":
                add_finding(
                    findings,
                    "real_execution_candidate_admitted_not_allowed",
                    "error",
                    "Future real execution candidates must remain unadmitted in this slice.",
                    {"candidate_id": candidate_id},
                )
            if preflight_status == "passed":
                add_finding(
                    findings,
                    "real_execution_candidate_preflight_passed_not_allowed",
                    "error",
                    "Future real execution candidates must not have preflight_status=passed in this slice.",
                    {"candidate_id": candidate_id},
                )
            if contract.get("requires_explicit_approval") is not True:
                add_finding(
                    findings,
                    "real_execution_requires_explicit_approval_false",
                    "error",
                    "Future real execution candidates must keep requires_explicit_approval=true.",
                    {"candidate_id": candidate_id},
                )
            if contract.get("approval_decision_reference_required") is not True:
                add_finding(
                    findings,
                    "real_execution_approval_decision_reference_required_false",
                    "error",
                    "Future real execution candidates must keep approval_decision_reference_required=true.",
                    {"candidate_id": candidate_id},
                )
            if contract.get("receipt_required") is not True:
                add_finding(
                    findings,
                    "real_execution_receipt_required_false",
                    "error",
                    "Future real execution candidates must keep receipt_required=true.",
                    {"candidate_id": candidate_id},
                )
            if contract.get("rollback_plan_required") is not True:
                add_finding(
                    findings,
                    "real_execution_rollback_plan_required_false",
                    "error",
                    "Future real execution candidates must keep rollback_plan_required=true.",
                    {"candidate_id": candidate_id},
                )
            if contract.get("operator_approval_required") is not True:
                add_finding(
                    findings,
                    "real_execution_operator_approval_required_false",
                    "error",
                    "Future real execution candidates must keep operator_approval_required=true.",
                    {"candidate_id": candidate_id},
                )
            if not _is_non_empty_list(contract.get("blocked_surfaces")):
                add_finding(
                    findings,
                    "real_execution_missing_blocked_surfaces",
                    "error",
                    "Future real execution candidates must include blocked_surfaces.",
                    {"candidate_id": candidate_id},
                )
            else:
                missing = sorted(REQUIRED_BLOCKED_SURFACES - blocked_surfaces)
                if missing:
                    add_finding(
                        findings,
                        "real_execution_missing_blocked_surface_tokens",
                        "error",
                        "Future real execution candidates must preserve all blocked surfaces.",
                        {"candidate_id": candidate_id, "missing_blocked_surfaces": missing},
                    )
            if not _is_non_empty_list(contract.get("forbidden_paths")):
                add_finding(
                    findings,
                    "real_execution_missing_forbidden_paths",
                    "error",
                    "Future real execution candidates must include forbidden_paths.",
                    {"candidate_id": candidate_id},
                )
            if not _sandbox_paths_valid(contract.get("allowed_sandbox_paths")):
                add_finding(
                    findings,
                    "real_execution_missing_allowed_sandbox_paths",
                    "error",
                    "Future real execution candidates must keep allowed_sandbox_paths under examples/sandbox/.",
                    {"candidate_id": candidate_id},
                )
            if not _is_non_empty_list(contract.get("failure_conditions")):
                add_finding(
                    findings,
                    "real_execution_missing_failure_conditions",
                    "error",
                    "Future real execution candidates must include failure_conditions.",
                    {"candidate_id": candidate_id},
                )
            if not str(contract.get("expected_validator", "")).strip():
                add_finding(
                    findings,
                    "real_execution_missing_expected_validator",
                    "error",
                    "Future real execution candidates must include expected_validator.",
                    {"candidate_id": candidate_id},
                )
            if not _is_non_empty_list(contract.get("expected_tests")):
                add_finding(
                    findings,
                    "real_execution_missing_expected_tests",
                    "error",
                    "Future real execution candidates must include expected_tests.",
                    {"candidate_id": candidate_id},
                )

        elif candidate_type == PUBLICATION_TYPE:
            if admission_status == "admitted_publication":
                add_finding(
                    findings,
                    "publication_candidate_admitted_not_allowed",
                    "error",
                    "Future publication candidates must remain unadmitted in this slice.",
                    {"candidate_id": candidate_id},
                )
            if preflight_status == "passed":
                add_finding(
                    findings,
                    "publication_candidate_preflight_passed_not_allowed",
                    "error",
                    "Future publication candidates must not have preflight_status=passed in this slice.",
                    {"candidate_id": candidate_id},
                )
            if contract.get("requires_explicit_approval") is not True:
                add_finding(
                    findings,
                    "publication_requires_explicit_approval_false",
                    "error",
                    "Future publication candidates must keep requires_explicit_approval=true.",
                    {"candidate_id": candidate_id},
                )
            if contract.get("approval_decision_reference_required") is not True:
                add_finding(
                    findings,
                    "publication_approval_decision_reference_required_false",
                    "error",
                    "Future publication candidates must keep approval_decision_reference_required=true.",
                    {"candidate_id": candidate_id},
                )
            if contract.get("receipt_required") is not True:
                add_finding(
                    findings,
                    "publication_receipt_required_false",
                    "error",
                    "Future publication candidates must keep receipt_required=true.",
                    {"candidate_id": candidate_id},
                )
            if contract.get("rollback_plan_required") is not True:
                add_finding(
                    findings,
                    "publication_rollback_plan_required_false",
                    "error",
                    "Future publication candidates must keep rollback_plan_required=true.",
                    {"candidate_id": candidate_id},
                )
            if contract.get("operator_approval_required") is not True:
                add_finding(
                    findings,
                    "publication_operator_approval_required_false",
                    "error",
                    "Future publication candidates must keep operator_approval_required=true.",
                    {"candidate_id": candidate_id},
                )
            if not _is_non_empty_list(contract.get("blocked_surfaces")):
                add_finding(
                    findings,
                    "publication_missing_blocked_surfaces",
                    "error",
                    "Future publication candidates must include blocked_surfaces.",
                    {"candidate_id": candidate_id},
                )
            else:
                missing = sorted(REQUIRED_BLOCKED_SURFACES - blocked_surfaces)
                if missing:
                    add_finding(
                        findings,
                        "publication_missing_blocked_surface_tokens",
                        "error",
                        "Future publication candidates must preserve all blocked surfaces.",
                        {"candidate_id": candidate_id, "missing_blocked_surfaces": missing},
                    )
            if not _is_non_empty_list(contract.get("forbidden_paths")):
                add_finding(
                    findings,
                    "publication_missing_forbidden_paths",
                    "error",
                    "Future publication candidates must include forbidden_paths.",
                    {"candidate_id": candidate_id},
                )
            if not _sandbox_paths_valid(contract.get("allowed_sandbox_paths")):
                add_finding(
                    findings,
                    "publication_missing_allowed_sandbox_paths",
                    "error",
                    "Future publication candidates must keep allowed_sandbox_paths under examples/sandbox/.",
                    {"candidate_id": candidate_id},
                )
            if not _is_non_empty_list(contract.get("failure_conditions")):
                add_finding(
                    findings,
                    "publication_missing_failure_conditions",
                    "error",
                    "Future publication candidates must include failure_conditions.",
                    {"candidate_id": candidate_id},
                )
            if not str(contract.get("expected_validator", "")).strip():
                add_finding(
                    findings,
                    "publication_missing_expected_validator",
                    "error",
                    "Future publication candidates must include expected_validator.",
                    {"candidate_id": candidate_id},
                )
            if not _is_non_empty_list(contract.get("expected_tests")):
                add_finding(
                    findings,
                    "publication_missing_expected_tests",
                    "error",
                    "Future publication candidates must include expected_tests.",
                    {"candidate_id": candidate_id},
                )

        elif candidate_type == DRY_RUN_TYPE:
            if admission_status != "unadmitted":
                add_finding(
                    findings,
                    "dry_run_candidate_admission_status_not_unadmitted",
                    "error",
                    "Dry-run candidates must remain unadmitted in this slice.",
                    {"candidate_id": candidate_id, "actual_admission_status": admission_status},
                )
            if contract.get("requires_explicit_approval") is not True:
                add_finding(
                    findings,
                    "dry_run_requires_explicit_approval_false",
                    "error",
                    "Dry-run candidates must keep requires_explicit_approval=true.",
                    {"candidate_id": candidate_id},
                )
            if not str(contract.get("expected_validator", "")).strip():
                add_finding(
                    findings,
                    "dry_run_missing_expected_validator",
                    "error",
                    "Dry-run candidates must include expected_validator.",
                    {"candidate_id": candidate_id},
                )
            if not _is_non_empty_list(contract.get("expected_tests")):
                add_finding(
                    findings,
                    "dry_run_missing_expected_tests",
                    "error",
                    "Dry-run candidates must include expected_tests.",
                    {"candidate_id": candidate_id},
                )

        if candidate_type in {REAL_EXECUTION_TYPE, PUBLICATION_TYPE, DRY_RUN_TYPE}:
            forbidden_paths = contract.get("forbidden_paths")
            if not _has_token(forbidden_paths, "production"):
                add_finding(
                    findings,
                    "forbidden_paths_missing_production_token",
                    "error",
                    "forbidden_paths must include production path blocking.",
                    {"candidate_id": candidate_id},
                )
            if not _has_token(forbidden_paths, "engine"):
                add_finding(
                    findings,
                    "forbidden_paths_missing_engine_token",
                    "error",
                    "forbidden_paths must include engine path blocking.",
                    {"candidate_id": candidate_id},
                )
            if not _has_token(forbidden_paths, "cache"):
                add_finding(
                    findings,
                    "forbidden_paths_missing_cache_token",
                    "error",
                    "forbidden_paths must include Cache/live-db blocking tokens.",
                    {"candidate_id": candidate_id},
                )

        if str(contract.get("production_readiness_effect", "")).strip() == "production_ready":
            add_finding(
                findings,
                "production_ready_effect_not_allowed",
                "error",
                "Preflight contracts must not claim production_ready effects.",
                {"candidate_id": candidate_id},
            )
        if str(contract.get("publication_effect", "")).strip() == "publication_admitted":
            add_finding(
                findings,
                "publication_admitted_effect_not_allowed",
                "error",
                "Preflight contracts must not claim publication admitted effects.",
                {"candidate_id": candidate_id},
            )

    severity_set = {str(item.get("severity", "")).strip() for item in findings}
    status = "fail" if "error" in severity_set else "pass"

    payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": "EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_VALIDATION_v1_REPORT",
        "status": status,
        "preflight_contracts_present": True,
        "preflight_contracts_path": str(preflight_path),
        "candidate_matrix_path": str(matrix_path),
        "preflight_contract_count": len(contract_map),
        "preflight_contract_candidate_ids": sorted(contract_ids),
        "admitted_noop_receipt_candidate_ids": admitted_noop_ids,
        "admitted_real_execution_candidate_ids": admitted_real_ids,
        "admitted_publication_candidate_ids": admitted_publication_ids,
        "real_execution_preflight_passed_candidate_ids": real_preflight_passed_ids,
        "publication_preflight_passed_candidate_ids": publication_preflight_passed_ids,
        "real_execution_admission_status": real_status or "blocked",
        "publication_admission_status": publication_status or "blocked",
        "production_ready_claimed": bool(preflight.get("production_ready_claimed", False)),
        "publication_admitted_claimed": bool(
            preflight.get("publication_admitted_claimed", False)
        ),
        "findings": findings,
    }
    print(json.dumps(payload, indent=2))

    if status == "pass":
        return 0
    if status == "warn" and args.allow_warn:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
