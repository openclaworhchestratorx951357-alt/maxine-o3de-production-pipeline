#!/usr/bin/env python3
"""Validate execution-admission preflight proof packages v1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


NOOP_CANDIDATE_ID = "release_candidate_package_receipt_noop_v1"
REAL_EXECUTION_TYPE = "real_execution"
PUBLICATION_TYPE = "publication"
DRY_RUN_TYPE = "dry_run"
NOOP_TYPE = "no_op_receipt"

DEFAULT_PROOF_PACKAGES_REL = Path(
    "examples/execution-admission/execution_admission_preflight_proof_packages_v1.json"
)
DEFAULT_MATRIX_REL = Path(
    "examples/execution-admission/execution_admission_candidate_matrix_v1.json"
)
DEFAULT_PREFLIGHT_REL = Path(
    "examples/execution-admission/execution_admission_preflight_contracts_v1.json"
)
DEFAULT_SCHEMA_REL = Path(
    "schemas/maxine_execution_admission_preflight_proof_packages.schema.json"
)

FULL_SATISFACTION_STATUSES: Set[str] = {
    "satisfied_no_op_only",
    "satisfied_non_execution_only",
}
UNSAFE_BLOCKED_SURFACE_STATUS = {"unsafe_allowed", "missing_blocked_surface"}
UNSAFE_FORBIDDEN_PATHS_STATUS = {"unsafe", "missing"}
UNSAFE_ALLOWED_SANDBOX_STATUS = {"unsafe", "missing"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate execution-admission preflight proof packages v1."
    )
    parser.add_argument(
        "proof_packages_path",
        nargs="?",
        default=str(DEFAULT_PROOF_PACKAGES_REL),
        help="Path to execution-admission preflight proof packages JSON.",
    )
    parser.add_argument(
        "--matrix-path",
        default=str(DEFAULT_MATRIX_REL),
        help="Path to execution-admission candidate matrix JSON.",
    )
    parser.add_argument(
        "--preflight-path",
        default=str(DEFAULT_PREFLIGHT_REL),
        help="Path to execution-admission preflight contracts JSON.",
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


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    proof_packages_path = (
        Path(args.proof_packages_path).resolve()
        if Path(args.proof_packages_path).is_absolute()
        else (repo_root / args.proof_packages_path).resolve()
    )
    matrix_path = (
        Path(args.matrix_path).resolve()
        if Path(args.matrix_path).is_absolute()
        else (repo_root / args.matrix_path).resolve()
    )
    preflight_path = (
        Path(args.preflight_path).resolve()
        if Path(args.preflight_path).is_absolute()
        else (repo_root / args.preflight_path).resolve()
    )
    schema_path = (repo_root / DEFAULT_SCHEMA_REL).resolve()

    if not proof_packages_path.exists():
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": f"preflight proof packages not found: {proof_packages_path}",
                },
                indent=2,
            )
        )
        return 2
    if not matrix_path.exists():
        print(
            json.dumps(
                {"status": "fail", "error": f"candidate matrix not found: {matrix_path}"},
                indent=2,
            )
        )
        return 2
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
    if not schema_path.exists():
        print(
            json.dumps(
                {"status": "fail", "error": f"schema not found: {schema_path}"},
                indent=2,
            )
        )
        return 2

    proof_packages = load_json(proof_packages_path)
    matrix = load_json(matrix_path)
    preflight_contracts = load_json(preflight_path)
    schema = load_json(schema_path)
    findings: List[Dict[str, Any]] = []

    ok, schema_errors = validate_schema(proof_packages, schema)
    if not ok:
        for message in schema_errors:
            add_finding(
                findings,
                "schema_validation_error",
                "error",
                "Preflight proof packages failed schema validation.",
                {"error": message},
            )

    proof_packages_raw = proof_packages.get("proof_packages", [])
    proof_entries = proof_packages_raw if isinstance(proof_packages_raw, list) else []
    proof_map: Dict[str, Dict[str, Any]] = {}
    duplicate_proof_ids: Set[str] = set()
    for entry in proof_entries:
        if not isinstance(entry, dict):
            add_finding(
                findings,
                "proof_package_entry_invalid",
                "error",
                "Each proof_packages[] entry must be an object.",
            )
            continue
        candidate_id = str(entry.get("candidate_id", "")).strip()
        if not candidate_id:
            add_finding(
                findings,
                "proof_package_candidate_id_missing",
                "error",
                "Each proof package must include candidate_id.",
            )
            continue
        if candidate_id in proof_map:
            duplicate_proof_ids.add(candidate_id)
        proof_map[candidate_id] = entry
    for candidate_id in sorted(duplicate_proof_ids):
        add_finding(
            findings,
            "proof_package_candidate_id_duplicate",
            "error",
            "Proof package candidate IDs must be unique.",
            {"candidate_id": candidate_id},
        )

    matrix_candidates_raw = matrix.get("candidates", [])
    matrix_map: Dict[str, Dict[str, Any]] = {}
    if isinstance(matrix_candidates_raw, list):
        for entry in matrix_candidates_raw:
            if isinstance(entry, dict):
                candidate_id = str(entry.get("candidate_id", "")).strip()
                if candidate_id:
                    matrix_map[candidate_id] = entry

    preflight_contracts_raw = preflight_contracts.get("contracts", [])
    preflight_map: Dict[str, Dict[str, Any]] = {}
    if isinstance(preflight_contracts_raw, list):
        for entry in preflight_contracts_raw:
            if isinstance(entry, dict):
                candidate_id = str(entry.get("candidate_id", "")).strip()
                if candidate_id:
                    preflight_map[candidate_id] = entry

    proof_ids = set(proof_map)
    matrix_ids = set(matrix_map)
    preflight_ids = set(preflight_map)

    for candidate_id in sorted(matrix_ids - proof_ids):
        add_finding(
            findings,
            "matrix_candidate_missing_preflight_proof_package",
            "error",
            "Every candidate matrix entry must have a preflight proof package.",
            {"candidate_id": candidate_id},
        )
    for candidate_id in sorted(proof_ids - matrix_ids):
        add_finding(
            findings,
            "preflight_proof_package_candidate_missing_from_matrix",
            "error",
            "Every preflight proof package candidate must exist in candidate matrix.",
            {"candidate_id": candidate_id},
        )
    for candidate_id in sorted(preflight_ids - proof_ids):
        add_finding(
            findings,
            "preflight_contract_candidate_missing_preflight_proof_package",
            "error",
            "Every preflight contract candidate must have a preflight proof package.",
            {"candidate_id": candidate_id},
        )
    for candidate_id in sorted(proof_ids - preflight_ids):
        add_finding(
            findings,
            "preflight_proof_package_candidate_missing_from_preflight_contracts",
            "error",
            "Every preflight proof package candidate must exist in preflight contracts.",
            {"candidate_id": candidate_id},
        )

    admitted_noop_ids = sorted(
        set(as_string_list(proof_packages.get("admitted_noop_receipt_candidate_ids", [])))
    )
    admitted_real_ids = sorted(
        set(as_string_list(proof_packages.get("admitted_real_execution_candidate_ids", [])))
    )
    admitted_publication_ids = sorted(
        set(as_string_list(proof_packages.get("admitted_publication_candidate_ids", [])))
    )
    real_preflight_passed_ids = sorted(
        set(as_string_list(proof_packages.get("real_execution_preflight_passed_candidate_ids", [])))
    )
    publication_preflight_passed_ids = sorted(
        set(
            as_string_list(
                proof_packages.get("publication_preflight_passed_candidate_ids", [])
            )
        )
    )
    blocked_real_preflight_ids = sorted(
        set(
            as_string_list(
                proof_packages.get("blocked_real_execution_preflight_candidate_ids", [])
            )
        )
    )
    blocked_publication_preflight_ids = sorted(
        set(
            as_string_list(
                proof_packages.get("blocked_publication_preflight_candidate_ids", [])
            )
        )
    )
    blocked_dry_run_preflight_ids = sorted(
        set(
            as_string_list(proof_packages.get("blocked_dry_run_preflight_candidate_ids", []))
        )
    )

    real_status = str(proof_packages.get("real_execution_admission_status", "")).strip()
    publication_status = str(proof_packages.get("publication_admission_status", "")).strip()
    production_ready_claimed = bool(proof_packages.get("production_ready_claimed", False))
    publication_admitted_claimed = bool(
        proof_packages.get("publication_admitted_claimed", False)
    )

    if admitted_noop_ids != [NOOP_CANDIDATE_ID]:
        add_finding(
            findings,
            "noop_candidate_top_level_mismatch",
            "error",
            "admitted_noop_receipt_candidate_ids must contain only release_candidate_package_receipt_noop_v1.",
            {"actual": admitted_noop_ids},
        )
    if admitted_real_ids:
        add_finding(
            findings,
            "real_execution_admitted_claim_not_allowed",
            "error",
            "No real execution candidate may be admitted in this proof package slice.",
            {"admitted_real_execution_candidate_ids": admitted_real_ids},
        )
    if admitted_publication_ids:
        add_finding(
            findings,
            "publication_admitted_claim_not_allowed",
            "error",
            "No publication candidate may be admitted in this proof package slice.",
            {"admitted_publication_candidate_ids": admitted_publication_ids},
        )
    if real_preflight_passed_ids:
        add_finding(
            findings,
            "real_execution_preflight_passed_candidates_not_allowed",
            "error",
            "real_execution_preflight_passed_candidate_ids must remain empty in this slice.",
            {"real_execution_preflight_passed_candidate_ids": real_preflight_passed_ids},
        )
    if publication_preflight_passed_ids:
        add_finding(
            findings,
            "publication_preflight_passed_candidates_not_allowed",
            "error",
            "publication_preflight_passed_candidate_ids must remain empty in this slice.",
            {"publication_preflight_passed_candidate_ids": publication_preflight_passed_ids},
        )
    if real_status == "admitted" and not admitted_real_ids:
        add_finding(
            findings,
            "real_execution_status_admitted_without_candidates",
            "error",
            "real_execution_admission_status=admitted requires admitted_real_execution_candidate_ids.",
        )
    if publication_status == "admitted" and not admitted_publication_ids:
        add_finding(
            findings,
            "publication_status_admitted_without_candidates",
            "error",
            "publication_admission_status=admitted requires admitted_publication_candidate_ids.",
        )
    if production_ready_claimed:
        add_finding(
            findings,
            "production_ready_claim_not_allowed",
            "error",
            "Preflight proof packages must not claim production_ready in this slice.",
        )
    if publication_admitted_claimed:
        add_finding(
            findings,
            "publication_admitted_claim_not_allowed",
            "error",
            "Preflight proof packages must not claim publication admitted in this slice.",
        )

    real_candidate_ids = sorted(
        [
            candidate_id
            for candidate_id, matrix_entry in matrix_map.items()
            if str(matrix_entry.get("candidate_type", "")).strip() == REAL_EXECUTION_TYPE
        ]
    )
    publication_candidate_ids = sorted(
        [
            candidate_id
            for candidate_id, matrix_entry in matrix_map.items()
            if str(matrix_entry.get("candidate_type", "")).strip() == PUBLICATION_TYPE
        ]
    )
    dry_run_candidate_ids = sorted(
        [
            candidate_id
            for candidate_id, matrix_entry in matrix_map.items()
            if str(matrix_entry.get("candidate_type", "")).strip() == DRY_RUN_TYPE
        ]
    )
    if sorted(set(blocked_real_preflight_ids)) != real_candidate_ids:
        add_finding(
            findings,
            "blocked_real_execution_preflight_candidate_ids_mismatch",
            "error",
            "blocked_real_execution_preflight_candidate_ids must match matrix real execution candidate IDs.",
            {
                "expected": real_candidate_ids,
                "actual": sorted(set(blocked_real_preflight_ids)),
            },
        )
    if sorted(set(blocked_publication_preflight_ids)) != publication_candidate_ids:
        add_finding(
            findings,
            "blocked_publication_preflight_candidate_ids_mismatch",
            "error",
            "blocked_publication_preflight_candidate_ids must match matrix publication candidate IDs.",
            {
                "expected": publication_candidate_ids,
                "actual": sorted(set(blocked_publication_preflight_ids)),
            },
        )
    if sorted(set(blocked_dry_run_preflight_ids)) != dry_run_candidate_ids:
        add_finding(
            findings,
            "blocked_dry_run_preflight_candidate_ids_mismatch",
            "error",
            "blocked_dry_run_preflight_candidate_ids must match matrix dry-run candidate IDs.",
            {
                "expected": dry_run_candidate_ids,
                "actual": sorted(set(blocked_dry_run_preflight_ids)),
            },
        )

    noop_entry = proof_map.get(NOOP_CANDIDATE_ID)
    if not isinstance(noop_entry, dict):
        add_finding(
            findings,
            "noop_candidate_proof_package_missing",
            "error",
            "Preflight proof packages must include release_candidate_package_receipt_noop_v1.",
        )

    for candidate_id in sorted(proof_ids):
        entry = proof_map[candidate_id]
        matrix_entry = matrix_map.get(candidate_id)
        preflight_entry = preflight_map.get(candidate_id)

        candidate_type = str(entry.get("candidate_type", "")).strip()
        admission_status = str(entry.get("admission_status", "")).strip()
        proof_package_status = str(entry.get("proof_package_status", "")).strip()
        preflight_passed = entry.get("preflight_passed")
        preflight_contract_status = str(entry.get("preflight_contract_status", "")).strip()
        approval_phrase_required = str(entry.get("approval_phrase_required", "")).strip()

        if isinstance(matrix_entry, dict):
            matrix_candidate_type = str(matrix_entry.get("candidate_type", "")).strip()
            matrix_status = str(matrix_entry.get("current_status", "")).strip()
            entry_matrix_status = str(entry.get("matrix_candidate_status", "")).strip()
            if candidate_type != matrix_candidate_type:
                add_finding(
                    findings,
                    "candidate_type_mismatch_with_matrix",
                    "error",
                    "candidate_type must match candidate matrix.",
                    {
                        "candidate_id": candidate_id,
                        "matrix_candidate_type": matrix_candidate_type,
                        "proof_package_candidate_type": candidate_type,
                    },
                )
            if entry_matrix_status != matrix_status:
                add_finding(
                    findings,
                    "candidate_status_mismatch_with_matrix",
                    "error",
                    "matrix_candidate_status must match matrix current_status.",
                    {
                        "candidate_id": candidate_id,
                        "matrix_current_status": matrix_status,
                        "proof_package_matrix_candidate_status": entry_matrix_status,
                    },
                )

        if isinstance(preflight_entry, dict):
            preflight_candidate_type = str(preflight_entry.get("candidate_type", "")).strip()
            contract_status = str(preflight_entry.get("preflight_status", "")).strip()
            if candidate_type != preflight_candidate_type:
                add_finding(
                    findings,
                    "candidate_type_mismatch_with_preflight_contract",
                    "error",
                    "candidate_type must match preflight contracts.",
                    {
                        "candidate_id": candidate_id,
                        "preflight_candidate_type": preflight_candidate_type,
                        "proof_package_candidate_type": candidate_type,
                    },
                )
            if preflight_contract_status != contract_status:
                add_finding(
                    findings,
                    "preflight_contract_status_mismatch",
                    "error",
                    "preflight_contract_status must match preflight contracts preflight_status.",
                    {
                        "candidate_id": candidate_id,
                        "preflight_contract_status": contract_status,
                        "proof_package_preflight_contract_status": preflight_contract_status,
                    },
                )

        expected_phrase = _exact_approval_phrase(candidate_id)
        if candidate_type in {REAL_EXECUTION_TYPE, PUBLICATION_TYPE, DRY_RUN_TYPE}:
            if not approval_phrase_required:
                if candidate_type == REAL_EXECUTION_TYPE:
                    finding_id = "real_execution_missing_approval_phrase_required"
                elif candidate_type == PUBLICATION_TYPE:
                    finding_id = "publication_missing_approval_phrase_required"
                else:
                    finding_id = "dry_run_missing_approval_phrase_required"
                add_finding(
                    findings,
                    finding_id,
                    "error",
                    "approval_phrase_required must be present.",
                    {"candidate_id": candidate_id},
                )
            elif approval_phrase_required != expected_phrase:
                if candidate_type == REAL_EXECUTION_TYPE:
                    finding_id = "real_execution_approval_phrase_mismatch"
                elif candidate_type == PUBLICATION_TYPE:
                    finding_id = "publication_approval_phrase_mismatch"
                else:
                    finding_id = "dry_run_approval_phrase_mismatch"
                add_finding(
                    findings,
                    finding_id,
                    "error",
                    "approval_phrase_required must exactly match candidate_id.",
                    {
                        "candidate_id": candidate_id,
                        "expected": expected_phrase,
                        "actual": approval_phrase_required,
                    },
                )

        if candidate_id == NOOP_CANDIDATE_ID:
            if candidate_type != NOOP_TYPE:
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
                    "release_candidate_package_receipt_noop_v1 must remain candidate_type=no_op_receipt.",
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
            if proof_package_status not in FULL_SATISFACTION_STATUSES:
                add_finding(
                    findings,
                    "noop_candidate_invalid_proof_package_status",
                    "error",
                    "No-op candidate proof_package_status must be a no-op-only satisfied status.",
                    {"actual_proof_package_status": proof_package_status},
                )
            if str(entry.get("publication_effect", "")).strip() == "publication_admitted":
                add_finding(
                    findings,
                    "publication_admitted_claim_not_allowed",
                    "error",
                    "No-op candidate must not imply publication admitted.",
                    {"candidate_id": candidate_id},
                )
            if str(entry.get("production_readiness_effect", "")).strip() == "production_ready":
                add_finding(
                    findings,
                    "production_ready_claim_not_allowed",
                    "error",
                    "No-op candidate must not imply production_ready.",
                    {"candidate_id": candidate_id},
                )
            continue

        missing_evidence_items = as_string_list(entry.get("missing_evidence_items", []))
        blocked_reason_codes = as_string_list(entry.get("blocked_reason_codes", []))
        required_validator = str(entry.get("required_validator", "")).strip()
        required_receipt_schema = str(entry.get("required_receipt_schema", "")).strip()
        unsafe_claims_detected = bool(entry.get("unsafe_claims_detected", False))
        blocked_surfaces_status = str(entry.get("blocked_surfaces_status", "")).strip()
        forbidden_paths_status = str(entry.get("forbidden_paths_status", "")).strip()
        allowed_sandbox_paths_status = str(entry.get("allowed_sandbox_paths_status", "")).strip()
        production_readiness_effect = str(entry.get("production_readiness_effect", "")).strip()
        publication_effect = str(entry.get("publication_effect", "")).strip()

        if candidate_type == REAL_EXECUTION_TYPE:
            if admission_status == "admitted_real_execution":
                add_finding(
                    findings,
                    "real_execution_candidate_admitted_not_allowed",
                    "error",
                    "Future real execution candidates must remain unadmitted in this slice.",
                    {"candidate_id": candidate_id},
                )
            if preflight_passed is True:
                add_finding(
                    findings,
                    "real_execution_candidate_preflight_passed_not_allowed",
                    "error",
                    "Future real execution candidates must keep preflight_passed=false in this slice.",
                    {"candidate_id": candidate_id},
                )
            if proof_package_status in FULL_SATISFACTION_STATUSES:
                add_finding(
                    findings,
                    "real_execution_candidate_full_satisfaction_not_allowed",
                    "error",
                    "Future real execution candidates must not use fully satisfied proof statuses in this slice.",
                    {"candidate_id": candidate_id, "proof_package_status": proof_package_status},
                )
            if not missing_evidence_items:
                add_finding(
                    findings,
                    "real_execution_missing_evidence_items_empty",
                    "error",
                    "Future real execution candidates must declare missing_evidence_items in this slice.",
                    {"candidate_id": candidate_id},
                )
            if not blocked_reason_codes:
                add_finding(
                    findings,
                    "real_execution_missing_blocked_reason_codes",
                    "error",
                    "Future real execution candidates must include blocked_reason_codes.",
                    {"candidate_id": candidate_id},
                )
            if not required_validator:
                add_finding(
                    findings,
                    "real_execution_missing_required_validator",
                    "error",
                    "Future real execution candidates must include required_validator.",
                    {"candidate_id": candidate_id},
                )
            if not required_receipt_schema:
                add_finding(
                    findings,
                    "real_execution_missing_required_receipt_schema",
                    "error",
                    "Future real execution candidates must include required_receipt_schema.",
                    {"candidate_id": candidate_id},
                )
            if unsafe_claims_detected:
                add_finding(
                    findings,
                    "real_execution_unsafe_claims_detected",
                    "error",
                    "unsafe_claims_detected must remain false for future real execution candidates.",
                    {"candidate_id": candidate_id},
                )
            if blocked_surfaces_status in UNSAFE_BLOCKED_SURFACE_STATUS:
                add_finding(
                    findings,
                    "real_execution_blocked_surfaces_status_invalid",
                    "error",
                    "blocked_surfaces_status must preserve blocked surfaces.",
                    {"candidate_id": candidate_id, "blocked_surfaces_status": blocked_surfaces_status},
                )
            if forbidden_paths_status in UNSAFE_FORBIDDEN_PATHS_STATUS:
                add_finding(
                    findings,
                    "real_execution_forbidden_paths_status_invalid",
                    "error",
                    "forbidden_paths_status must preserve production/engine/cache blocking.",
                    {"candidate_id": candidate_id, "forbidden_paths_status": forbidden_paths_status},
                )
            if allowed_sandbox_paths_status in UNSAFE_ALLOWED_SANDBOX_STATUS:
                add_finding(
                    findings,
                    "real_execution_allowed_sandbox_paths_status_invalid",
                    "error",
                    "allowed_sandbox_paths_status must remain sandbox_only.",
                    {
                        "candidate_id": candidate_id,
                        "allowed_sandbox_paths_status": allowed_sandbox_paths_status,
                    },
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
            if preflight_passed is True:
                add_finding(
                    findings,
                    "publication_candidate_preflight_passed_not_allowed",
                    "error",
                    "Future publication candidates must keep preflight_passed=false in this slice.",
                    {"candidate_id": candidate_id},
                )
            if proof_package_status in FULL_SATISFACTION_STATUSES:
                add_finding(
                    findings,
                    "publication_candidate_full_satisfaction_not_allowed",
                    "error",
                    "Future publication candidates must not use fully satisfied proof statuses in this slice.",
                    {"candidate_id": candidate_id, "proof_package_status": proof_package_status},
                )
            if not missing_evidence_items:
                add_finding(
                    findings,
                    "publication_missing_evidence_items_empty",
                    "error",
                    "Future publication candidates must declare missing_evidence_items in this slice.",
                    {"candidate_id": candidate_id},
                )
            if not blocked_reason_codes:
                add_finding(
                    findings,
                    "publication_missing_blocked_reason_codes",
                    "error",
                    "Future publication candidates must include blocked_reason_codes.",
                    {"candidate_id": candidate_id},
                )
            if not required_validator:
                add_finding(
                    findings,
                    "publication_missing_required_validator",
                    "error",
                    "Future publication candidates must include required_validator.",
                    {"candidate_id": candidate_id},
                )
            if not required_receipt_schema:
                add_finding(
                    findings,
                    "publication_missing_required_receipt_schema",
                    "error",
                    "Future publication candidates must include required_receipt_schema.",
                    {"candidate_id": candidate_id},
                )
            if unsafe_claims_detected:
                add_finding(
                    findings,
                    "publication_unsafe_claims_detected",
                    "error",
                    "unsafe_claims_detected must remain false for future publication candidates.",
                    {"candidate_id": candidate_id},
                )
            if blocked_surfaces_status in UNSAFE_BLOCKED_SURFACE_STATUS:
                add_finding(
                    findings,
                    "publication_blocked_surfaces_status_invalid",
                    "error",
                    "blocked_surfaces_status must preserve blocked surfaces.",
                    {"candidate_id": candidate_id, "blocked_surfaces_status": blocked_surfaces_status},
                )
            if forbidden_paths_status in UNSAFE_FORBIDDEN_PATHS_STATUS:
                add_finding(
                    findings,
                    "publication_forbidden_paths_status_invalid",
                    "error",
                    "forbidden_paths_status must preserve production/engine/cache blocking.",
                    {"candidate_id": candidate_id, "forbidden_paths_status": forbidden_paths_status},
                )
            if allowed_sandbox_paths_status in UNSAFE_ALLOWED_SANDBOX_STATUS:
                add_finding(
                    findings,
                    "publication_allowed_sandbox_paths_status_invalid",
                    "error",
                    "allowed_sandbox_paths_status must remain sandbox_only.",
                    {
                        "candidate_id": candidate_id,
                        "allowed_sandbox_paths_status": allowed_sandbox_paths_status,
                    },
                )

        elif candidate_type == DRY_RUN_TYPE:
            if admission_status != "unadmitted":
                add_finding(
                    findings,
                    "dry_run_candidate_admitted_not_allowed",
                    "error",
                    "Dry-run candidates must remain unadmitted in this slice.",
                    {"candidate_id": candidate_id, "actual_admission_status": admission_status},
                )
            if preflight_passed is True:
                add_finding(
                    findings,
                    "dry_run_candidate_preflight_passed_not_allowed",
                    "error",
                    "Dry-run candidates must keep preflight_passed=false in this slice.",
                    {"candidate_id": candidate_id},
                )
            if not required_validator:
                add_finding(
                    findings,
                    "dry_run_missing_required_validator",
                    "error",
                    "Dry-run candidates must include required_validator.",
                    {"candidate_id": candidate_id},
                )
            if not missing_evidence_items:
                add_finding(
                    findings,
                    "dry_run_missing_evidence_items_empty",
                    "error",
                    "Dry-run candidates must declare missing_evidence_items in this slice.",
                    {"candidate_id": candidate_id},
                )

        if production_readiness_effect == "production_ready":
            add_finding(
                findings,
                "production_ready_claim_not_allowed",
                "error",
                "production_readiness_effect must not claim production_ready.",
                {"candidate_id": candidate_id},
            )
        if publication_effect == "publication_admitted":
            add_finding(
                findings,
                "publication_admitted_claim_not_allowed",
                "error",
                "publication_effect must not claim publication_admitted.",
                {"candidate_id": candidate_id},
            )
        if admission_status == "admitted_real_execution":
            add_finding(
                findings,
                "real_execution_admitted_claim_not_allowed",
                "error",
                "Proof packages must not claim admitted_real_execution in this slice.",
                {"candidate_id": candidate_id},
            )
        if forbidden_paths_status == "unsafe":
            add_finding(
                findings,
                "production_path_write_allowed_claim",
                "error",
                "Unsafe forbidden_paths_status implies production path writes might be allowed.",
                {"candidate_id": candidate_id},
            )
            add_finding(
                findings,
                "engine_path_write_allowed_claim",
                "error",
                "Unsafe forbidden_paths_status implies engine path writes might be allowed.",
                {"candidate_id": candidate_id},
            )
        if forbidden_paths_status == "unsafe":
            add_finding(
                findings,
                "cache_live_db_access_allowed_claim",
                "error",
                "Unsafe forbidden_paths_status implies cache/live DB access might be allowed.",
                {"candidate_id": candidate_id},
            )

    severity_set = {str(item.get("severity", "")).strip() for item in findings}
    status = "fail" if "error" in severity_set else "pass"

    payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": "EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_VALIDATION_v1_REPORT",
        "status": status,
        "preflight_proof_packages_present": True,
        "preflight_proof_packages_path": str(proof_packages_path),
        "candidate_matrix_path": str(matrix_path),
        "preflight_contracts_path": str(preflight_path),
        "preflight_proof_package_count": len(proof_map),
        "preflight_proof_package_candidate_ids": sorted(proof_ids),
        "admitted_noop_receipt_candidate_ids": admitted_noop_ids,
        "admitted_real_execution_candidate_ids": admitted_real_ids,
        "admitted_publication_candidate_ids": admitted_publication_ids,
        "real_execution_preflight_passed_candidate_ids": real_preflight_passed_ids,
        "publication_preflight_passed_candidate_ids": publication_preflight_passed_ids,
        "blocked_real_execution_preflight_candidate_ids": blocked_real_preflight_ids,
        "blocked_publication_preflight_candidate_ids": blocked_publication_preflight_ids,
        "blocked_dry_run_preflight_candidate_ids": blocked_dry_run_preflight_ids,
        "real_execution_admission_status": real_status or "blocked",
        "publication_admission_status": publication_status or "blocked",
        "production_ready_claimed": production_ready_claimed,
        "publication_admitted_claimed": publication_admitted_claimed,
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
