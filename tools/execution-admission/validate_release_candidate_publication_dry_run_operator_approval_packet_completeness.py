#!/usr/bin/env python3
"""Validate release-candidate publication dry-run operator approval packet completeness v1."""

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
EXPECTED_COMPLETENESS_REVIEW_STATUS = "static_completeness_valid_blocked"
EXPECTED_OPERATOR_PACKET_STATUS = "static_template_valid_blocked"
EXPECTED_ADMISSION_BLOCKERS_STATUS = "static_checklist_valid_blocked"
EXPECTED_RECEIPT_CONTRACT_STATUS = "static_contract_valid_blocked"
EXPECTED_BLOCKED_RECEIPT_STATUS = "blocked_unissued_contract_only"
EXPECTED_DRY_RUN_PLAN_STATUS = "static_plan_valid_blocked"
EXPECTED_ROLLUP_STATUS = "static_rollup_valid_blocked"
EXPECTED_ROLLUP_NEXT_SLICE_ID = "candidate_specific_dry_run_planning_v1"

DEFAULT_REVIEW_REL = Path(
    "examples/execution-admission/"
    "release_candidate_package_publish_dry_run_operator_approval_packet_completeness_v1.json"
)
DEFAULT_SCHEMA_REL = Path(
    "schemas/maxine_release_candidate_publication_dry_run_operator_approval_packet_completeness.schema.json"
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
    "production_readiness_status",
    "noop_receipt_status",
)

REQUIRED_FLAG_FALSE_FIELDS = (
    ("approval_request_ready", "approval_request_ready_not_allowed"),
    ("operator_approval_granted", "operator_approval_granted_not_allowed"),
    ("approval_phrase_present", "approval_phrase_present_not_allowed"),
    ("dry_run_admitted", "dry_run_admitted_not_allowed"),
    ("receipt_issued", "receipt_issued_not_allowed"),
    ("publication_admitted", "publication_admitted_not_allowed"),
    ("real_execution_admitted", "real_execution_admitted_not_allowed"),
    ("production_ready_claimed", "production_ready_claim_not_allowed"),
)

REQUIRED_UNRESOLVED_APPROVAL_BLOCKERS = {
    "missing_approval_decision": "unresolved_approval_blockers_missing_approval_decision",
    "approval_request_not_ready": "unresolved_approval_blockers_missing_approval_request_not_ready",
    "operator_approval_not_granted": "unresolved_approval_blockers_missing_operator_approval_not_granted",
    "approval_phrase_not_present": "unresolved_approval_blockers_missing_approval_phrase_not_present",
}
REQUIRED_UNRESOLVED_EXECUTION_BLOCKERS = {
    "dry_run_not_admitted": "unresolved_execution_blockers_missing_dry_run_not_admitted",
    "dry_run_not_executed": "unresolved_execution_blockers_missing_dry_run_not_executed",
}
REQUIRED_UNRESOLVED_RECEIPT_BLOCKERS = {
    "receipt_not_issued": "unresolved_receipt_blockers_missing_receipt_not_issued",
    "rollback_cleanup_evidence_missing": "unresolved_receipt_blockers_missing_rollback_cleanup_evidence_missing",
}
REQUIRED_UNRESOLVED_PUBLICATION_BLOCKERS = {
    "publication_surfaces_blocked_by_policy": "unresolved_publication_blockers_missing_publication_surfaces_blocked_by_policy",
    "publication_not_admitted": "unresolved_publication_blockers_missing_publication_not_admitted",
}

REQUIRED_VALIDATION_COMMANDS = {
    "tools/execution-admission/validate_execution_admission_candidate_matrix.py": (
        "required_validation_commands_missing_candidate_matrix_validator"
    ),
    "tools/execution-admission/validate_execution_admission_preflight_contracts.py": (
        "required_validation_commands_missing_preflight_contract_validator"
    ),
    "tools/execution-admission/validate_execution_admission_preflight_proof_packages.py": (
        "required_validation_commands_missing_preflight_proof_validator"
    ),
    "tools/execution-admission/validate_execution_admission_readiness_rollup.py": (
        "required_validation_commands_missing_readiness_rollup_validator"
    ),
    "tools/execution-admission/validate_release_candidate_publication_dry_run_plan.py": (
        "required_validation_commands_missing_dry_run_plan_validator"
    ),
    "tools/execution-admission/validate_release_candidate_publication_dry_run_receipt.py": (
        "required_validation_commands_missing_dry_run_receipt_validator"
    ),
    "tools/execution-admission/validate_release_candidate_publication_dry_run_admission_blockers.py": (
        "required_validation_commands_missing_admission_blocker_validator"
    ),
    "tools/execution-admission/validate_release_candidate_publication_dry_run_operator_approval_packet.py": (
        "required_validation_commands_missing_operator_approval_packet_validator"
    ),
    "tools/audit/verify_sandbox_writer_safety.py": (
        "required_validation_commands_missing_safety_verifier"
    ),
    "tools/release-lane/prove_pilot_release_chain.py": (
        "required_validation_commands_missing_proof_flow"
    ),
}

REQUIRED_FORBIDDEN_SURFACE_TOKENS = {
    "publication_surfaces_blocked_by_policy": "required_forbidden_surface_status_missing_publication_surface_token",
    "execution_surfaces_blocked_by_policy": "required_forbidden_surface_status_missing_execution_surface_token",
    "cache_live_db_access_blocked_by_policy": "required_forbidden_surface_status_missing_cache_live_db_surface_token",
    "production_engine_write_blocked_by_policy": "required_forbidden_surface_status_missing_production_engine_surface_token",
    "authoritative_id_claims_blocked_by_policy": "required_forbidden_surface_status_missing_authoritative_id_surface_token",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate release-candidate publication dry-run operator approval packet "
            "completeness v1."
        )
    )
    parser.add_argument(
        "review_path",
        nargs="?",
        default=str(DEFAULT_REVIEW_REL),
        help=(
            "Path to release-candidate publication dry-run operator approval "
            "packet completeness JSON."
        ),
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


def _check_forbidden_claim_language(
    payload: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    checks = (
        ("publish allowed", "completeness_review_allows_publish"),
        ("spawn allowed", "completeness_review_allows_spawn"),
        (
            "production path writes allowed",
            "completeness_review_allows_production_path_writes",
        ),
        (
            "engine path writes allowed",
            "completeness_review_allows_engine_path_writes",
        ),
        (
            "cache/live db access allowed",
            "completeness_review_allows_cache_live_db_access",
        ),
        (
            "cache live db access allowed",
            "completeness_review_allows_cache_live_db_access",
        ),
        (
            "authoritative source uuid claims allowed",
            "completeness_review_allows_authoritative_source_uuid_claims",
        ),
        (
            "authoritative asset id claims allowed",
            "completeness_review_allows_authoritative_asset_id_claims",
        ),
        (
            "authoritative product id claims allowed",
            "completeness_review_allows_authoritative_product_id_claims",
        ),
    )
    for needle, finding_id in checks:
        if needle in text:
            add_finding(
                findings,
                finding_id,
                "error",
                "Completeness review text must not allow blocked surfaces.",
                {"needle": needle},
            )


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
    review_path = (
        Path(args.review_path).resolve()
        if Path(args.review_path).is_absolute()
        else (repo_root / args.review_path).resolve()
    )
    schema_path = (repo_root / DEFAULT_SCHEMA_REL).resolve()

    if not review_path.exists():
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": f"operator approval packet completeness review not found: {review_path}",
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

    review = load_json(review_path)
    schema = load_json(schema_path)
    findings: List[Dict[str, Any]] = []

    ok, schema_errors = validate_schema(review, schema)
    if not ok:
        for message in schema_errors:
            add_finding(
                findings,
                "schema_validation_error",
                "error",
                "Operator approval packet completeness review failed schema validation.",
                {"error": message},
            )

    source_artifacts = (
        review.get("source_artifacts")
        if isinstance(review.get("source_artifacts"), dict)
        else {}
    )

    matrix_path = _path_from_source_artifacts(
        repo_root, source_artifacts, "candidate_matrix_ref", DEFAULT_MATRIX_REL
    )
    preflight_path = _path_from_source_artifacts(
        repo_root, source_artifacts, "preflight_contracts_ref", DEFAULT_PREFLIGHT_REL
    )
    preflight_proof_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "preflight_proof_packages_ref",
        DEFAULT_PREFLIGHT_PROOF_REL,
    )
    rollup_path = _path_from_source_artifacts(
        repo_root, source_artifacts, "readiness_rollup_ref", DEFAULT_ROLLUP_REL
    )
    dry_run_plan_path = _path_from_source_artifacts(
        repo_root, source_artifacts, "dry_run_plan_ref", DEFAULT_DRY_RUN_PLAN_REL
    )
    dry_run_receipt_contract_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "dry_run_receipt_contract_ref",
        DEFAULT_DRY_RUN_RECEIPT_CONTRACT_REL,
    )
    dry_run_receipt_blocked_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "blocked_unissued_receipt_ref",
        DEFAULT_DRY_RUN_RECEIPT_BLOCKED_REL,
    )
    admission_blockers_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "admission_blocker_checklist_ref",
        DEFAULT_ADMISSION_BLOCKERS_REL,
    )
    operator_packet_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "operator_approval_packet_ref",
        DEFAULT_OPERATOR_PACKET_REL,
    )
    production_readiness_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "production_readiness_report_ref",
        DEFAULT_PRODUCTION_READINESS_REL,
    )
    noop_decision_path = _path_from_source_artifacts(
        repo_root, source_artifacts, "noop_receipt_status_ref", DEFAULT_NOOP_DECISION_REL
    )

    source_paths = {
        "candidate_matrix_ref": matrix_path,
        "preflight_contracts_ref": preflight_path,
        "preflight_proof_packages_ref": preflight_proof_path,
        "readiness_rollup_ref": rollup_path,
        "dry_run_plan_ref": dry_run_plan_path,
        "dry_run_receipt_contract_ref": dry_run_receipt_contract_path,
        "blocked_unissued_receipt_ref": dry_run_receipt_blocked_path,
        "admission_blocker_checklist_ref": admission_blockers_path,
        "operator_approval_packet_ref": operator_packet_path,
        "production_readiness_report_ref": production_readiness_path,
        "noop_receipt_status_ref": noop_decision_path,
    }
    for key, path in source_paths.items():
        if not path.exists():
            add_finding(
                findings,
                "source_artifact_missing",
                "error",
                "Referenced source artifact path does not exist.",
                {"field": key, "path": str(path)},
            )

    matrix_code, matrix_payload, matrix_parse_error = run_validator(
        repo_root, MATRIX_VALIDATOR_REL, [str(matrix_path)]
    )
    preflight_code, preflight_payload, preflight_parse_error = run_validator(
        repo_root, PREFLIGHT_VALIDATOR_REL, [str(preflight_path)]
    )
    preflight_proof_code, preflight_proof_payload, preflight_proof_parse_error = run_validator(
        repo_root,
        PREFLIGHT_PROOF_VALIDATOR_REL,
        [
            str(preflight_proof_path),
            "--matrix-path",
            str(matrix_path),
            "--preflight-path",
            str(preflight_path),
        ],
    )
    rollup_code, rollup_payload, rollup_parse_error = run_validator(
        repo_root, READINESS_ROLLUP_VALIDATOR_REL, [str(rollup_path)]
    )
    dry_run_plan_code, dry_run_plan_payload, dry_run_plan_parse_error = run_validator(
        repo_root, DRY_RUN_PLAN_VALIDATOR_REL, [str(dry_run_plan_path)]
    )
    (
        dry_run_receipt_contract_code,
        dry_run_receipt_contract_payload,
        dry_run_receipt_contract_parse_error,
    ) = run_validator(
        repo_root,
        DRY_RUN_RECEIPT_VALIDATOR_REL,
        [str(dry_run_receipt_contract_path)],
    )
    (
        dry_run_receipt_blocked_code,
        dry_run_receipt_blocked_payload,
        dry_run_receipt_blocked_parse_error,
    ) = run_validator(
        repo_root,
        DRY_RUN_RECEIPT_VALIDATOR_REL,
        [str(dry_run_receipt_blocked_path)],
    )
    (
        admission_blockers_code,
        admission_blockers_payload,
        admission_blockers_parse_error,
    ) = run_validator(
        repo_root, ADMISSION_BLOCKERS_VALIDATOR_REL, [str(admission_blockers_path)]
    )
    (
        operator_packet_code,
        operator_packet_payload,
        operator_packet_parse_error,
    ) = run_validator(
        repo_root, OPERATOR_PACKET_VALIDATOR_REL, [str(operator_packet_path)]
    )

    validator_runs = (
        (
            "candidate_matrix_validation_failed",
            "Candidate matrix validator must pass for completeness review.",
            matrix_code,
            matrix_payload,
            matrix_parse_error,
        ),
        (
            "preflight_contracts_validation_failed",
            "Preflight contracts validator must pass for completeness review.",
            preflight_code,
            preflight_payload,
            preflight_parse_error,
        ),
        (
            "preflight_proof_packages_validation_failed",
            "Preflight proof packages validator must pass for completeness review.",
            preflight_proof_code,
            preflight_proof_payload,
            preflight_proof_parse_error,
        ),
        (
            "readiness_rollup_validation_failed",
            "Readiness rollup validator must pass for completeness review.",
            rollup_code,
            rollup_payload,
            rollup_parse_error,
        ),
        (
            "dry_run_plan_validation_failed",
            "Dry-run plan validator must pass for completeness review.",
            dry_run_plan_code,
            dry_run_plan_payload,
            dry_run_plan_parse_error,
        ),
        (
            "dry_run_receipt_contract_validation_failed",
            "Dry-run receipt contract validator must pass for completeness review.",
            dry_run_receipt_contract_code,
            dry_run_receipt_contract_payload,
            dry_run_receipt_contract_parse_error,
        ),
        (
            "blocked_unissued_receipt_validation_failed",
            "Blocked/unissued dry-run receipt validator must pass for completeness review.",
            dry_run_receipt_blocked_code,
            dry_run_receipt_blocked_payload,
            dry_run_receipt_blocked_parse_error,
        ),
        (
            "admission_blockers_validation_failed",
            "Admission blockers validator must pass for completeness review.",
            admission_blockers_code,
            admission_blockers_payload,
            admission_blockers_parse_error,
        ),
        (
            "operator_approval_packet_validation_failed",
            "Operator approval packet validator must pass for completeness review.",
            operator_packet_code,
            operator_packet_payload,
            operator_packet_parse_error,
        ),
    )
    for finding_id, message, code, payload, parse_error in validator_runs:
        if parse_error:
            add_finding(
                findings,
                finding_id,
                "error",
                message,
                {"parse_error": parse_error},
            )
            continue
        if code != 0 or not isinstance(payload, dict):
            add_finding(
                findings,
                finding_id,
                "error",
                message,
                {"return_code": code},
            )
            continue
        if str(payload.get("status", "")).strip() != "pass":
            add_finding(
                findings,
                finding_id,
                "error",
                message,
                {"validator_status": payload.get("status"), "return_code": code},
            )

    matrix_source_status = (
        "pass"
        if isinstance(matrix_payload, dict) and matrix_code == 0 and matrix_payload.get("status") == "pass"
        else "fail"
    )
    preflight_source_status = (
        "pass"
        if isinstance(preflight_payload, dict)
        and preflight_code == 0
        and preflight_payload.get("status") == "pass"
        else "fail"
    )
    preflight_proof_source_status = (
        "pass"
        if isinstance(preflight_proof_payload, dict)
        and preflight_proof_code == 0
        and preflight_proof_payload.get("status") == "pass"
        else "fail"
    )
    rollup_source_status = (
        "pass"
        if isinstance(rollup_payload, dict) and rollup_code == 0 and rollup_payload.get("status") == "pass"
        else "fail"
    )
    dry_run_plan_source_status = (
        "pass"
        if isinstance(dry_run_plan_payload, dict)
        and dry_run_plan_code == 0
        and dry_run_plan_payload.get("status") == "pass"
        else "fail"
    )
    dry_run_receipt_contract_source_status = (
        "pass"
        if isinstance(dry_run_receipt_contract_payload, dict)
        and dry_run_receipt_contract_code == 0
        and dry_run_receipt_contract_payload.get("status") == "pass"
        else "fail"
    )
    dry_run_receipt_blocked_source_status = (
        "pass"
        if isinstance(dry_run_receipt_blocked_payload, dict)
        and dry_run_receipt_blocked_code == 0
        and dry_run_receipt_blocked_payload.get("status") == "pass"
        else "fail"
    )
    admission_blockers_source_status = (
        "pass"
        if isinstance(admission_blockers_payload, dict)
        and admission_blockers_code == 0
        and admission_blockers_payload.get("status") == "pass"
        else "fail"
    )
    operator_packet_source_status = (
        "pass"
        if isinstance(operator_packet_payload, dict)
        and operator_packet_code == 0
        and operator_packet_payload.get("status") == "pass"
        else "fail"
    )

    production_readiness_payload = (
        load_json(production_readiness_path)
        if production_readiness_path.exists()
        else {}
    )
    noop_decision_payload = (
        load_json(noop_decision_path)
        if noop_decision_path.exists()
        else {}
    )
    production_readiness_source_status = _validate_production_readiness_report(
        production_readiness_payload, findings
    )
    noop_source_status = _validate_noop_decision_record(noop_decision_payload, findings)

    source_status_reported = (
        review.get("source_artifact_validation_status")
        if isinstance(review.get("source_artifact_validation_status"), dict)
        else {}
    )
    source_status_expected = {
        "candidate_matrix_status": matrix_source_status,
        "preflight_contracts_status": preflight_source_status,
        "preflight_proof_packages_status": preflight_proof_source_status,
        "readiness_rollup_status": rollup_source_status,
        "dry_run_plan_status": dry_run_plan_source_status,
        "dry_run_receipt_contract_status": dry_run_receipt_contract_source_status,
        "blocked_unissued_receipt_status": dry_run_receipt_blocked_source_status,
        "admission_blocker_checklist_status": admission_blockers_source_status,
        "operator_approval_packet_status": operator_packet_source_status,
        "production_readiness_status": production_readiness_source_status,
        "noop_receipt_status": noop_source_status,
    }
    for key in SOURCE_STATUS_KEYS:
        if key not in source_status_reported:
            add_finding(
                findings,
                "source_artifact_validation_status_missing_key",
                "error",
                "source_artifact_validation_status is missing required key.",
                {"key": key},
            )
            continue
        reported = str(source_status_reported.get(key, "")).strip()
        if reported != "pass":
            add_finding(
                findings,
                "source_artifact_validation_status_not_pass",
                "error",
                "source_artifact_validation_status must keep required sources at pass.",
                {"key": key, "actual": reported},
            )
        expected = source_status_expected.get(key, "fail")
        if reported != expected:
            add_finding(
                findings,
                "source_artifact_validation_status_mismatch",
                "error",
                "source_artifact_validation_status does not match computed source validation status.",
                {"key": key, "reported": reported, "computed": expected},
            )

    review_id = str(review.get("review_id", "")).strip()
    review_version = str(review.get("review_version", "")).strip()
    candidate_id = str(review.get("candidate_id", "")).strip()
    candidate_type = str(review.get("candidate_type", "")).strip()
    completeness_review_status = str(review.get("completeness_review_status", "")).strip()
    admission_status = str(review.get("admission_status", "")).strip()
    approval_phrase = str(review.get("approval_phrase_required", "")).strip()

    if candidate_id != TARGET_CANDIDATE_ID:
        add_finding(
            findings,
            "candidate_id_mismatch",
            "error",
            "candidate_id must match release_candidate_package_publish_dry_run_v1.",
            {"actual": candidate_id},
        )
    if candidate_type != TARGET_CANDIDATE_TYPE:
        add_finding(
            findings,
            "candidate_type_mismatch",
            "error",
            "candidate_type must be dry_run.",
            {"actual": candidate_type},
        )
    if completeness_review_status != EXPECTED_COMPLETENESS_REVIEW_STATUS:
        add_finding(
            findings,
            "completeness_review_status_not_static_completeness_valid_blocked",
            "error",
            "completeness_review_status must be static_completeness_valid_blocked.",
            {"actual": completeness_review_status},
        )
    if admission_status != "unadmitted":
        add_finding(
            findings,
            "admission_status_not_unadmitted",
            "error",
            "admission_status must remain unadmitted.",
            {"actual": admission_status},
        )

    for field, finding_id in (
        ("packet_structurally_complete", "packet_structurally_complete_not_true"),
        ("packet_internally_consistent", "packet_internally_consistent_not_true"),
        (
            "packet_complete_for_future_review_template",
            "packet_complete_for_future_review_template_not_true",
        ),
    ):
        if review.get(field) is not True:
            add_finding(
                findings,
                finding_id,
                "error",
                f"{field} must remain true for the static completeness template posture.",
                {"actual": review.get(field)},
            )

    for field, finding_id in REQUIRED_FLAG_FALSE_FIELDS:
        if review.get(field) is not False:
            add_finding(
                findings,
                finding_id,
                "error",
                f"{field} must remain false for blocked/static completeness posture.",
                {"actual": review.get(field)},
            )
    if review.get("generated_from_static_artifacts_only") is not True:
        add_finding(
            findings,
            "generated_from_static_artifacts_only_not_true",
            "error",
            "generated_from_static_artifacts_only must be true.",
            {"actual": review.get("generated_from_static_artifacts_only")},
        )

    if approval_phrase != EXPECTED_APPROVAL_PHRASE:
        add_finding(
            findings,
            "approval_phrase_required_mismatch",
            "error",
            "approval_phrase_required must exactly match the candidate-specific phrase.",
            {"actual": approval_phrase},
        )
    approval_decision_reference = review.get("approval_decision_reference")
    if isinstance(approval_decision_reference, str) and approval_decision_reference.strip():
        add_finding(
            findings,
            "approval_decision_reference_not_allowed",
            "error",
            "approval_decision_reference must be null or empty while unadmitted.",
            {"actual": approval_decision_reference},
        )

    source_ref_keys = set(source_artifacts.keys())
    for required_source_field in REQUIRED_SOURCE_REFERENCE_FIELDS:
        if required_source_field not in source_ref_keys:
            add_finding(
                findings,
                "source_artifacts_missing_required_reference",
                "error",
                "source_artifacts is missing required reference field.",
                {"field": required_source_field},
            )

    completeness_checks = _check_non_empty_string_list(
        review,
        "completeness_checks",
        findings,
        "completeness_checks_missing_or_empty",
        "completeness_checks must be present and non-empty.",
    )
    consistency_checks = _check_non_empty_string_list(
        review,
        "consistency_checks",
        findings,
        "consistency_checks_missing_or_empty",
        "consistency_checks must be present and non-empty.",
    )
    safety_notes = _check_non_empty_string_list(
        review,
        "safety_notes",
        findings,
        "safety_notes_missing_or_empty",
        "safety_notes must be present and non-empty.",
    )

    required_packet_sections_status = (
        review.get("required_packet_sections_status")
        if isinstance(review.get("required_packet_sections_status"), dict)
        else {}
    )
    if required_packet_sections_status.get("all_required_sections_present") is not True:
        add_finding(
            findings,
            "required_packet_sections_not_complete",
            "error",
            "required_packet_sections_status.all_required_sections_present must be true.",
            {"actual": required_packet_sections_status.get("all_required_sections_present")},
        )
    if as_string_list(required_packet_sections_status.get("missing_sections")):
        add_finding(
            findings,
            "required_packet_sections_missing_entries",
            "error",
            "required_packet_sections_status.missing_sections must be empty.",
        )

    required_cross_references_status = (
        review.get("required_cross_references_status")
        if isinstance(review.get("required_cross_references_status"), dict)
        else {}
    )
    if required_cross_references_status.get("all_required_cross_references_present") is not True:
        add_finding(
            findings,
            "required_cross_references_not_complete",
            "error",
            "required_cross_references_status.all_required_cross_references_present must be true.",
            {
                "actual": required_cross_references_status.get(
                    "all_required_cross_references_present"
                )
            },
        )
    if as_string_list(required_cross_references_status.get("missing_cross_references")):
        add_finding(
            findings,
            "required_cross_references_missing_entries",
            "error",
            "required_cross_references_status.missing_cross_references must be empty.",
        )

    required_validation_commands_status = (
        review.get("required_validation_commands_status")
        if isinstance(review.get("required_validation_commands_status"), dict)
        else {}
    )
    if required_validation_commands_status.get("all_required_validation_commands_present") is not True:
        add_finding(
            findings,
            "required_validation_commands_not_complete",
            "error",
            "required_validation_commands_status.all_required_validation_commands_present must be true.",
            {
                "actual": required_validation_commands_status.get(
                    "all_required_validation_commands_present"
                )
            },
        )
    if as_string_list(required_validation_commands_status.get("missing_validation_commands")):
        add_finding(
            findings,
            "required_validation_commands_has_missing_entries",
            "error",
            "required_validation_commands_status.missing_validation_commands must be empty.",
        )
    required_validation_commands = as_string_list(
        required_validation_commands_status.get("required_validation_commands")
    )
    if not required_validation_commands:
        add_finding(
            findings,
            "required_validation_commands_missing_or_empty",
            "error",
            "required_validation_commands_status.required_validation_commands must be non-empty.",
        )
    _check_required_token_set(
        required_validation_commands,
        REQUIRED_VALIDATION_COMMANDS,
        findings,
        "required_validation_commands_status.required_validation_commands",
    )

    required_forbidden_surface_status = (
        review.get("required_forbidden_surface_status")
        if isinstance(review.get("required_forbidden_surface_status"), dict)
        else {}
    )
    if required_forbidden_surface_status.get("forbidden_surfaces_represented") is not True:
        add_finding(
            findings,
            "required_forbidden_surface_status_not_represented",
            "error",
            "required_forbidden_surface_status.forbidden_surfaces_represented must be true.",
            {
                "actual": required_forbidden_surface_status.get(
                    "forbidden_surfaces_represented"
                )
            },
        )
    if required_forbidden_surface_status.get("blocked_surfaces_confirmed") is not True:
        add_finding(
            findings,
            "required_forbidden_surface_status_not_blocked",
            "error",
            "required_forbidden_surface_status.blocked_surfaces_confirmed must be true.",
            {
                "actual": required_forbidden_surface_status.get(
                    "blocked_surfaces_confirmed"
                )
            },
        )
    forbidden_surface_tokens = as_string_list(
        required_forbidden_surface_status.get("forbidden_surface_tokens")
    )
    if not forbidden_surface_tokens:
        add_finding(
            findings,
            "required_forbidden_surface_status_tokens_missing_or_empty",
            "error",
            "required_forbidden_surface_status.forbidden_surface_tokens must be non-empty.",
        )
    _check_required_token_set(
        forbidden_surface_tokens,
        REQUIRED_FORBIDDEN_SURFACE_TOKENS,
        findings,
        "required_forbidden_surface_status.forbidden_surface_tokens",
    )

    required_operator_decision_fields_status = (
        review.get("required_operator_decision_fields_status")
        if isinstance(review.get("required_operator_decision_fields_status"), dict)
        else {}
    )
    if required_operator_decision_fields_status.get("decision_fields_present") is not True:
        add_finding(
            findings,
            "required_operator_decision_fields_not_present",
            "error",
            "required_operator_decision_fields_status.decision_fields_present must be true.",
            {"actual": required_operator_decision_fields_status.get("decision_fields_present")},
        )
    if required_operator_decision_fields_status.get("decision_fields_populated") is not False:
        add_finding(
            findings,
            "required_operator_decision_fields_populated_not_allowed",
            "error",
            "required_operator_decision_fields_status.decision_fields_populated must be false.",
            {"actual": required_operator_decision_fields_status.get("decision_fields_populated")},
        )
    if required_operator_decision_fields_status.get("approval_decision_reference_present") is not False:
        add_finding(
            findings,
            "required_operator_decision_fields_approval_reference_present_not_allowed",
            "error",
            "required_operator_decision_fields_status.approval_decision_reference_present must be false.",
            {
                "actual": required_operator_decision_fields_status.get(
                    "approval_decision_reference_present"
                )
            },
        )

    required_rollback_cleanup_status = (
        review.get("required_rollback_cleanup_status")
        if isinstance(review.get("required_rollback_cleanup_status"), dict)
        else {}
    )
    if required_rollback_cleanup_status.get("rollback_or_cleanup_required") is not True:
        add_finding(
            findings,
            "required_rollback_cleanup_not_required",
            "error",
            "required_rollback_cleanup_status.rollback_or_cleanup_required must be true.",
            {"actual": required_rollback_cleanup_status.get("rollback_or_cleanup_required")},
        )
    if required_rollback_cleanup_status.get("rollback_or_cleanup_evidence_present") is not False:
        add_finding(
            findings,
            "required_rollback_cleanup_evidence_present_not_allowed",
            "error",
            "required_rollback_cleanup_status.rollback_or_cleanup_evidence_present must be false.",
            {
                "actual": required_rollback_cleanup_status.get(
                    "rollback_or_cleanup_evidence_present"
                )
            },
        )
    if required_rollback_cleanup_status.get("rollback_or_cleanup_blocked") is not True:
        add_finding(
            findings,
            "required_rollback_cleanup_not_blocked",
            "error",
            "required_rollback_cleanup_status.rollback_or_cleanup_blocked must be true.",
            {"actual": required_rollback_cleanup_status.get("rollback_or_cleanup_blocked")},
        )

    unresolved_approval_blockers = _check_non_empty_string_list(
        review,
        "unresolved_approval_blockers",
        findings,
        "unresolved_approval_blockers_missing_or_empty",
        "unresolved_approval_blockers must be present and non-empty.",
    )
    unresolved_execution_blockers = _check_non_empty_string_list(
        review,
        "unresolved_execution_blockers",
        findings,
        "unresolved_execution_blockers_missing_or_empty",
        "unresolved_execution_blockers must be present and non-empty.",
    )
    unresolved_receipt_blockers = _check_non_empty_string_list(
        review,
        "unresolved_receipt_blockers",
        findings,
        "unresolved_receipt_blockers_missing_or_empty",
        "unresolved_receipt_blockers must be present and non-empty.",
    )
    unresolved_publication_blockers = _check_non_empty_string_list(
        review,
        "unresolved_publication_blockers",
        findings,
        "unresolved_publication_blockers_missing_or_empty",
        "unresolved_publication_blockers must be present and non-empty.",
    )
    _check_required_token_set(
        unresolved_approval_blockers,
        REQUIRED_UNRESOLVED_APPROVAL_BLOCKERS,
        findings,
        "unresolved_approval_blockers",
    )
    _check_required_token_set(
        unresolved_execution_blockers,
        REQUIRED_UNRESOLVED_EXECUTION_BLOCKERS,
        findings,
        "unresolved_execution_blockers",
    )
    _check_required_token_set(
        unresolved_receipt_blockers,
        REQUIRED_UNRESOLVED_RECEIPT_BLOCKERS,
        findings,
        "unresolved_receipt_blockers",
    )
    _check_required_token_set(
        unresolved_publication_blockers,
        REQUIRED_UNRESOLVED_PUBLICATION_BLOCKERS,
        findings,
        "unresolved_publication_blockers",
    )

    if bool(review.get("unsafe_claims_detected", False)):
        add_finding(
            findings,
            "unsafe_claims_detected_not_allowed",
            "error",
            "unsafe_claims_detected must remain false.",
        )

    _check_forbidden_claim_language(review, findings)

    matrix_payload_raw = load_json(matrix_path) if matrix_path.exists() else {}
    preflight_payload_raw = load_json(preflight_path) if preflight_path.exists() else {}
    preflight_proof_payload_raw = (
        load_json(preflight_proof_path) if preflight_proof_path.exists() else {}
    )
    rollup_payload_raw = load_json(rollup_path) if rollup_path.exists() else {}
    dry_run_plan_payload_raw = (
        load_json(dry_run_plan_path) if dry_run_plan_path.exists() else {}
    )
    dry_run_receipt_contract_payload_raw = (
        load_json(dry_run_receipt_contract_path)
        if dry_run_receipt_contract_path.exists()
        else {}
    )
    dry_run_receipt_blocked_payload_raw = (
        load_json(dry_run_receipt_blocked_path)
        if dry_run_receipt_blocked_path.exists()
        else {}
    )
    admission_blockers_payload_raw = (
        load_json(admission_blockers_path) if admission_blockers_path.exists() else {}
    )
    operator_packet_payload_raw = (
        load_json(operator_packet_path) if operator_packet_path.exists() else {}
    )

    matrix_map = _candidate_map(matrix_payload_raw, "candidates")
    matrix_entry = matrix_map.get(TARGET_CANDIDATE_ID)
    if not isinstance(matrix_entry, dict):
        add_finding(
            findings,
            "candidate_missing_in_matrix",
            "error",
            "Target candidate must exist in candidate matrix.",
        )
    else:
        if str(matrix_entry.get("candidate_type", "")).strip() != TARGET_CANDIDATE_TYPE:
            add_finding(
                findings,
                "candidate_type_mismatch_with_matrix",
                "error",
                "Target candidate type must match candidate matrix.",
                {"actual": matrix_entry.get("candidate_type")},
            )
        if str(matrix_entry.get("current_status", "")).strip() == "admitted":
            add_finding(
                findings,
                "dry_run_admitted_not_allowed",
                "error",
                "Target candidate must remain unadmitted in candidate matrix.",
            )

    preflight_map = _candidate_map(preflight_payload_raw, "contracts")
    preflight_entry = preflight_map.get(TARGET_CANDIDATE_ID)
    if not isinstance(preflight_entry, dict):
        add_finding(
            findings,
            "candidate_missing_in_preflight_contracts",
            "error",
            "Target candidate must exist in preflight contracts.",
        )
    else:
        if str(preflight_entry.get("candidate_type", "")).strip() != TARGET_CANDIDATE_TYPE:
            add_finding(
                findings,
                "candidate_type_mismatch_with_preflight_contracts",
                "error",
                "Target candidate type must match preflight contracts.",
                {"actual": preflight_entry.get("candidate_type")},
            )
        if str(preflight_entry.get("admission_status", "")).strip() != "unadmitted":
            add_finding(
                findings,
                "admission_status_mismatch_with_preflight_contracts",
                "error",
                "Target candidate must remain unadmitted in preflight contracts.",
                {"actual": preflight_entry.get("admission_status")},
            )

    preflight_proof_map = _candidate_map(preflight_proof_payload_raw, "proof_packages")
    preflight_proof_entry = preflight_proof_map.get(TARGET_CANDIDATE_ID)
    if not isinstance(preflight_proof_entry, dict):
        add_finding(
            findings,
            "candidate_missing_in_preflight_proof_packages",
            "error",
            "Target candidate must exist in preflight proof packages.",
        )
    else:
        if str(preflight_proof_entry.get("candidate_type", "")).strip() != TARGET_CANDIDATE_TYPE:
            add_finding(
                findings,
                "candidate_type_mismatch_with_preflight_proof_packages",
                "error",
                "Target candidate type must match preflight proof packages.",
                {"actual": preflight_proof_entry.get("candidate_type")},
            )
        if str(preflight_proof_entry.get("admission_status", "")).strip() != "unadmitted":
            add_finding(
                findings,
                "admission_status_mismatch_with_preflight_proof_packages",
                "error",
                "Target candidate must remain unadmitted in preflight proof packages.",
                {"actual": preflight_proof_entry.get("admission_status")},
            )
        if bool(preflight_proof_entry.get("preflight_passed", False)):
            add_finding(
                findings,
                "dry_run_preflight_passed_not_allowed",
                "error",
                "Target candidate must keep preflight_passed=false in preflight proof packages.",
            )

    rollup_map = _candidate_map(rollup_payload_raw, "candidate_rollups")
    rollup_entry = rollup_map.get(TARGET_CANDIDATE_ID)
    if not isinstance(rollup_entry, dict):
        add_finding(
            findings,
            "candidate_missing_in_readiness_rollup",
            "error",
            "Target candidate must exist in readiness rollup.",
        )
    else:
        if str(rollup_entry.get("candidate_type", "")).strip() != TARGET_CANDIDATE_TYPE:
            add_finding(
                findings,
                "candidate_type_mismatch_with_readiness_rollup",
                "error",
                "Target candidate type must match readiness rollup.",
                {"actual": rollup_entry.get("candidate_type")},
            )
        if str(rollup_entry.get("admission_status", "")).strip() != "unadmitted":
            add_finding(
                findings,
                "admission_status_mismatch_with_readiness_rollup",
                "error",
                "Target candidate must remain unadmitted in readiness rollup.",
                {"actual": rollup_entry.get("admission_status")},
            )
    if (
        str(rollup_payload_raw.get("overall_readiness_rollup_status", "")).strip()
        != EXPECTED_ROLLUP_STATUS
    ):
        add_finding(
            findings,
            "readiness_rollup_status_not_expected",
            "error",
            "Readiness rollup must keep overall_readiness_rollup_status=static_rollup_valid_blocked.",
            {"actual": rollup_payload_raw.get("overall_readiness_rollup_status")},
        )
    next_slice = (
        rollup_payload_raw.get("safest_next_preparation_slice")
        if isinstance(rollup_payload_raw.get("safest_next_preparation_slice"), dict)
        else {}
    )
    if str(next_slice.get("slice_id", "")).strip() != EXPECTED_ROLLUP_NEXT_SLICE_ID:
        add_finding(
            findings,
            "readiness_rollup_next_slice_id_mismatch",
            "error",
            "Readiness rollup must keep safest_next_preparation_slice.slice_id=candidate_specific_dry_run_planning_v1.",
            {"actual": next_slice.get("slice_id")},
        )
    if str(next_slice.get("candidate_id", "")).strip() != TARGET_CANDIDATE_ID:
        add_finding(
            findings,
            "readiness_rollup_next_slice_candidate_mismatch",
            "error",
            "Readiness rollup safest next candidate must be release_candidate_package_publish_dry_run_v1.",
            {"actual": next_slice.get("candidate_id")},
        )

    if (
        str(dry_run_plan_payload_raw.get("plan_status", "")).strip()
        != EXPECTED_DRY_RUN_PLAN_STATUS
    ):
        add_finding(
            findings,
            "dry_run_plan_status_not_expected",
            "error",
            "Dry-run plan must keep plan_status=static_plan_valid_blocked.",
            {"actual": dry_run_plan_payload_raw.get("plan_status")},
        )
    if (
        str(dry_run_receipt_contract_payload_raw.get("receipt_contract_status", "")).strip()
        != EXPECTED_RECEIPT_CONTRACT_STATUS
    ):
        add_finding(
            findings,
            "dry_run_receipt_contract_status_not_expected",
            "error",
            "Dry-run receipt contract must keep receipt_contract_status=static_contract_valid_blocked.",
            {"actual": dry_run_receipt_contract_payload_raw.get("receipt_contract_status")},
        )
    if (
        str(dry_run_receipt_blocked_payload_raw.get("receipt_status", "")).strip()
        != EXPECTED_BLOCKED_RECEIPT_STATUS
    ):
        add_finding(
            findings,
            "blocked_unissued_receipt_status_mismatch",
            "error",
            "Blocked/unissued receipt example must keep receipt_status=blocked_unissued_contract_only.",
            {"actual": dry_run_receipt_blocked_payload_raw.get("receipt_status")},
        )
    if (
        str(admission_blockers_payload_raw.get("checklist_status", "")).strip()
        != EXPECTED_ADMISSION_BLOCKERS_STATUS
    ):
        add_finding(
            findings,
            "admission_blockers_status_not_expected",
            "error",
            "Admission blockers checklist must keep checklist_status=static_checklist_valid_blocked.",
            {"actual": admission_blockers_payload_raw.get("checklist_status")},
        )
    if (
        str(operator_packet_payload_raw.get("approval_packet_status", "")).strip()
        != EXPECTED_OPERATOR_PACKET_STATUS
    ):
        add_finding(
            findings,
            "operator_approval_packet_status_not_expected",
            "error",
            "Operator approval packet must keep approval_packet_status=static_template_valid_blocked.",
            {"actual": operator_packet_payload_raw.get("approval_packet_status")},
        )

    if str(dry_run_receipt_contract_payload_raw.get("candidate_id", "")).strip() != TARGET_CANDIDATE_ID:
        add_finding(
            findings,
            "candidate_id_mismatch_with_receipt_contract",
            "error",
            "Dry-run receipt contract candidate_id must match target candidate.",
            {"actual": dry_run_receipt_contract_payload_raw.get("candidate_id")},
        )
    if str(admission_blockers_payload_raw.get("candidate_id", "")).strip() != TARGET_CANDIDATE_ID:
        add_finding(
            findings,
            "candidate_id_mismatch_with_admission_blockers",
            "error",
            "Admission blocker checklist candidate_id must match target candidate.",
            {"actual": admission_blockers_payload_raw.get("candidate_id")},
        )
    if str(operator_packet_payload_raw.get("candidate_id", "")).strip() != TARGET_CANDIDATE_ID:
        add_finding(
            findings,
            "candidate_id_mismatch_with_operator_approval_packet",
            "error",
            "Operator approval packet candidate_id must match target candidate.",
            {"actual": operator_packet_payload_raw.get("candidate_id")},
        )

    severity_set = {str(item.get("severity", "")).strip() for item in findings}
    status = "fail" if "error" in severity_set else "pass"

    report_payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_OPERATOR_APPROVAL_PACKET_COMPLETENESS_VALIDATION_v1_REPORT",
        "status": status,
        "release_candidate_publication_dry_run_operator_approval_packet_completeness_present": True,
        "release_candidate_publication_dry_run_operator_approval_packet_completeness_path": str(
            review_path
        ),
        "candidate_matrix_path": str(matrix_path),
        "preflight_contracts_path": str(preflight_path),
        "preflight_proof_packages_path": str(preflight_proof_path),
        "readiness_rollup_path": str(rollup_path),
        "dry_run_plan_path": str(dry_run_plan_path),
        "dry_run_receipt_contract_path": str(dry_run_receipt_contract_path),
        "blocked_unissued_receipt_path": str(dry_run_receipt_blocked_path),
        "admission_blocker_checklist_path": str(admission_blockers_path),
        "operator_approval_packet_path": str(operator_packet_path),
        "production_readiness_report_path": str(production_readiness_path),
        "noop_receipt_status_path": str(noop_decision_path),
        "source_artifact_validation_status": source_status_reported,
        "computed_source_artifact_validation_status": source_status_expected,
        "planned_candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "completeness_review_status": completeness_review_status,
        "admission_status": admission_status,
        "packet_structurally_complete": bool(review.get("packet_structurally_complete", False)),
        "packet_internally_consistent": bool(review.get("packet_internally_consistent", False)),
        "packet_complete_for_future_review_template": bool(
            review.get("packet_complete_for_future_review_template", False)
        ),
        "approval_request_ready": bool(review.get("approval_request_ready", False)),
        "operator_approval_granted": bool(review.get("operator_approval_granted", False)),
        "approval_phrase_present": bool(review.get("approval_phrase_present", False)),
        "dry_run_admitted": bool(review.get("dry_run_admitted", False)),
        "receipt_issued": bool(review.get("receipt_issued", False)),
        "publication_admitted": bool(review.get("publication_admitted", False)),
        "real_execution_admitted": bool(review.get("real_execution_admitted", False)),
        "production_ready_claimed": bool(review.get("production_ready_claimed", False)),
        "approval_phrase_required": approval_phrase,
        "completeness_checks": completeness_checks,
        "consistency_checks": consistency_checks,
        "unresolved_approval_blockers": unresolved_approval_blockers,
        "unresolved_execution_blockers": unresolved_execution_blockers,
        "unresolved_receipt_blockers": unresolved_receipt_blockers,
        "unresolved_publication_blockers": unresolved_publication_blockers,
        "required_validation_commands": required_validation_commands,
        "forbidden_surface_tokens": forbidden_surface_tokens,
        "safety_notes": safety_notes,
        "review_id": review_id,
        "review_version": review_version,
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
