#!/usr/bin/env python3
"""Validate execution-admission candidate matrix v1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


NOOP_CANDIDATE_ID = "release_candidate_package_receipt_noop_v1"
DEFAULT_MATRIX_REL = Path("examples/execution-admission/execution_admission_candidate_matrix_v1.json")
DEFAULT_SCHEMA_REL = Path("schemas/maxine_execution_admission_candidate_matrix.schema.json")

REAL_EXECUTION_TYPE = "real_execution"
PUBLICATION_TYPE = "publication"
DRY_RUN_TYPE = "dry_run"

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
        description="Validate execution-admission candidate matrix v1."
    )
    parser.add_argument(
        "matrix_path",
        nargs="?",
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
    except Exception as exc:
        # Optional dependency in this repo environment; semantic checks below remain mandatory.
        _ = exc
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


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    matrix_path = (
        Path(args.matrix_path).resolve()
        if Path(args.matrix_path).is_absolute()
        else (repo_root / args.matrix_path).resolve()
    )
    schema_path = (repo_root / DEFAULT_SCHEMA_REL).resolve()

    if not matrix_path.exists():
        print(json.dumps({"status": "fail", "error": f"matrix not found: {matrix_path}"}, indent=2))
        return 2
    if not schema_path.exists():
        print(json.dumps({"status": "fail", "error": f"schema not found: {schema_path}"}, indent=2))
        return 2

    matrix = load_json(matrix_path)
    schema = load_json(schema_path)
    findings: List[Dict[str, Any]] = []

    ok, schema_errors = validate_schema(matrix, schema)
    if not ok:
        for message in schema_errors:
            add_finding(
                findings,
                "schema_validation_error",
                "error",
                "Candidate matrix failed schema validation.",
                {"error": message},
            )

    real_status = str(matrix.get("real_execution_admission_status", "")).strip()
    publication_status = str(matrix.get("publication_admission_status", "")).strip()
    production_ready_claimed = bool(matrix.get("production_ready_claimed", False))

    admitted_noop_ids = sorted(set(as_string_list(matrix.get("admitted_noop_receipt_candidate_ids", []))))
    receipt_backed_ids = sorted(set(as_string_list(matrix.get("receipt_backed_candidate_ids", []))))
    admitted_real_ids = sorted(set(as_string_list(matrix.get("admitted_real_execution_candidate_ids", []))))
    admitted_publication_ids = sorted(set(as_string_list(matrix.get("admitted_publication_candidate_ids", []))))

    candidates_value = matrix.get("candidates", [])
    candidates = candidates_value if isinstance(candidates_value, list) else []

    candidate_ids_seen: Set[str] = set()
    noop_candidate: Dict[str, Any] | None = None
    proposed_or_blocked_real_execution_ids: List[str] = []
    proposed_or_blocked_publication_ids: List[str] = []
    proposed_or_blocked_dry_run_ids: List[str] = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            add_finding(
                findings,
                "candidate_entry_invalid",
                "error",
                "Each candidates[] entry must be an object.",
            )
            continue

        candidate_id = str(candidate.get("candidate_id", "")).strip()
        candidate_type = str(candidate.get("candidate_type", "")).strip()
        current_status = str(candidate.get("current_status", "")).strip()
        approval_phrase = str(candidate.get("approval_phrase", "")).strip()
        explicit_ref = str(candidate.get("explicit_admission_decision_ref", "")).strip()
        blocked_surfaces = set(as_string_list(candidate.get("blocked_surfaces", [])))

        if not candidate_id:
            add_finding(
                findings,
                "candidate_id_missing",
                "error",
                "Each candidate must include candidate_id.",
            )
            continue
        if candidate_id in candidate_ids_seen:
            add_finding(
                findings,
                "candidate_id_duplicate",
                "error",
                "Candidate IDs must be unique.",
                {"candidate_id": candidate_id},
            )
        candidate_ids_seen.add(candidate_id)

        expected_phrase = f"APPROVE EXECUTION ADMISSION {candidate_id}"
        if approval_phrase != expected_phrase:
            add_finding(
                findings,
                "approval_phrase_mismatch",
                "error",
                "Candidate approval_phrase must exactly match candidate_id.",
                {"candidate_id": candidate_id, "expected": expected_phrase, "actual": approval_phrase},
            )

        if candidate_id == NOOP_CANDIDATE_ID:
            noop_candidate = candidate
            if candidate_type != "no_op_receipt":
                if candidate_type == REAL_EXECUTION_TYPE:
                    finding_id = "noop_candidate_misclassified_as_real_execution"
                elif candidate_type == PUBLICATION_TYPE:
                    finding_id = "noop_candidate_misclassified_as_publication"
                else:
                    finding_id = "noop_candidate_misclassified_type"
                add_finding(
                    findings,
                    finding_id,
                    "error",
                    "release_candidate_package_receipt_noop_v1 must be candidate_type=no_op_receipt only.",
                    {"actual_candidate_type": candidate_type},
                )
            if current_status != "admitted":
                add_finding(
                    findings,
                    "noop_candidate_not_admitted",
                    "error",
                    "release_candidate_package_receipt_noop_v1 must remain admitted in matrix v1.",
                    {"actual_current_status": current_status},
                )

        if candidate_type == REAL_EXECUTION_TYPE:
            if current_status != "admitted":
                proposed_or_blocked_real_execution_ids.append(candidate_id)
            if candidate.get("requires_explicit_approval") is not True:
                add_finding(
                    findings,
                    "real_execution_requires_explicit_approval_false",
                    "error",
                    "Future real_execution candidates must keep requires_explicit_approval=true.",
                    {"candidate_id": candidate_id},
                )
            for flag_key, finding_id in (
                ("receipt_required", "real_execution_receipt_required_false"),
                ("rollback_plan_required", "real_execution_rollback_plan_required_false"),
                ("validator_required", "real_execution_validator_required_false"),
                ("tests_required", "real_execution_tests_required_false"),
            ):
                if candidate.get(flag_key) is not True:
                    add_finding(
                        findings,
                        finding_id,
                        "error",
                        f"Future real_execution candidates must keep {flag_key}=true.",
                        {"candidate_id": candidate_id},
                    )
            missing_blocked = sorted(REQUIRED_BLOCKED_SURFACES - blocked_surfaces)
            if missing_blocked:
                add_finding(
                    findings,
                    "real_execution_missing_blocked_surfaces",
                    "error",
                    "Real execution candidate is missing required blocked surfaces.",
                    {"candidate_id": candidate_id, "missing_blocked_surfaces": missing_blocked},
                )
            if current_status == "admitted" and not explicit_ref:
                add_finding(
                    findings,
                    "real_execution_admitted_missing_decision_reference",
                    "error",
                    "Admitted real_execution candidates require explicit_admission_decision_ref.",
                    {"candidate_id": candidate_id},
                )

        if candidate_type == PUBLICATION_TYPE:
            if current_status != "admitted":
                proposed_or_blocked_publication_ids.append(candidate_id)
            if candidate.get("requires_explicit_approval") is not True:
                add_finding(
                    findings,
                    "publication_requires_explicit_approval_false",
                    "error",
                    "Future publication candidates must keep requires_explicit_approval=true.",
                    {"candidate_id": candidate_id},
                )
            for flag_key, finding_id in (
                ("receipt_required", "publication_receipt_required_false"),
                ("rollback_plan_required", "publication_rollback_plan_required_false"),
                ("validator_required", "publication_validator_required_false"),
                ("tests_required", "publication_tests_required_false"),
            ):
                if candidate.get(flag_key) is not True:
                    add_finding(
                        findings,
                        finding_id,
                        "error",
                        f"Future publication candidates must keep {flag_key}=true.",
                        {"candidate_id": candidate_id},
                    )
            missing_blocked = sorted(REQUIRED_BLOCKED_SURFACES - blocked_surfaces)
            if missing_blocked:
                add_finding(
                    findings,
                    "publication_missing_blocked_surfaces",
                    "error",
                    "Publication candidate is missing required blocked surfaces.",
                    {"candidate_id": candidate_id, "missing_blocked_surfaces": missing_blocked},
                )
            if current_status == "admitted" and not explicit_ref:
                add_finding(
                    findings,
                    "publication_admitted_missing_decision_reference",
                    "error",
                    "Admitted publication candidates require explicit_admission_decision_ref.",
                    {"candidate_id": candidate_id},
                )

        if candidate_type == DRY_RUN_TYPE and current_status != "admitted":
            proposed_or_blocked_dry_run_ids.append(candidate_id)

        if candidate_id != NOOP_CANDIDATE_ID and current_status == "admitted":
            add_finding(
                findings,
                "unexpected_admitted_candidate_for_v1",
                "error",
                "Only release_candidate_package_receipt_noop_v1 may be admitted in matrix v1.",
                {"candidate_id": candidate_id, "candidate_type": candidate_type},
            )

    if noop_candidate is None:
        add_finding(
            findings,
            "noop_candidate_missing",
            "error",
            "Matrix must include release_candidate_package_receipt_noop_v1.",
        )

    if NOOP_CANDIDATE_ID not in admitted_noop_ids:
        add_finding(
            findings,
            "noop_candidate_missing_from_admitted_noop_ids",
            "error",
            "Matrix admitted_noop_receipt_candidate_ids must include release_candidate_package_receipt_noop_v1.",
        )
    if NOOP_CANDIDATE_ID not in receipt_backed_ids:
        add_finding(
            findings,
            "noop_candidate_missing_from_receipt_backed_ids",
            "error",
            "Matrix receipt_backed_candidate_ids must include release_candidate_package_receipt_noop_v1.",
        )
    if NOOP_CANDIDATE_ID in admitted_real_ids:
        add_finding(
            findings,
            "noop_candidate_misclassified_real_execution_slot",
            "error",
            "No-op receipt candidate must not appear in admitted_real_execution_candidate_ids.",
        )
    if NOOP_CANDIDATE_ID in admitted_publication_ids:
        add_finding(
            findings,
            "noop_candidate_misclassified_publication_slot",
            "error",
            "No-op receipt candidate must not appear in admitted_publication_candidate_ids.",
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
            "real_execution_admission_status=blocked cannot include admitted_real_execution_candidate_ids.",
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
            "publication_admission_status=blocked cannot include admitted_publication_candidate_ids.",
            {"admitted_publication_candidate_ids": admitted_publication_ids},
        )

    if production_ready_claimed:
        add_finding(
            findings,
            "production_ready_claim_not_allowed",
            "error",
            "production_ready must not be claimed through candidate matrix v1.",
        )

    severity_set = {str(item.get("severity", "")).strip() for item in findings}
    status = "fail" if "error" in severity_set else "pass"

    payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": "EXECUTION_ADMISSION_CANDIDATE_MATRIX_VALIDATION_v1_REPORT",
        "status": status,
        "candidate_matrix_present": True,
        "matrix_path": str(matrix_path),
        "admitted_noop_receipt_candidate_ids": admitted_noop_ids,
        "receipt_backed_candidate_ids": receipt_backed_ids,
        "admitted_real_execution_candidate_ids": admitted_real_ids,
        "admitted_publication_candidate_ids": admitted_publication_ids,
        "proposed_or_blocked_real_execution_candidate_ids": sorted(set(proposed_or_blocked_real_execution_ids)),
        "proposed_or_blocked_publication_candidate_ids": sorted(set(proposed_or_blocked_publication_ids)),
        "proposed_or_blocked_dry_run_candidate_ids": sorted(set(proposed_or_blocked_dry_run_ids)),
        "real_execution_admission_status": real_status or "blocked",
        "publication_admission_status": publication_status or "blocked",
        "findings": findings,
    }
    print(json.dumps(payload, indent=2))

    if payload["status"] == "pass":
        return 0
    if payload["status"] == "warn" and args.allow_warn:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
