#!/usr/bin/env python3
"""Validate release-candidate publication dry-run non-approval decision v1."""

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

DEFAULT_DECISION_REL = Path(
    "examples/execution-admission/"
    "release_candidate_package_publish_dry_run_non_approval_decision_v1.json"
)
DEFAULT_SCHEMA_REL = Path(
    "schemas/maxine_release_candidate_publication_dry_run_non_approval_decision.schema.json"
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

REQUIRED_NON_APPROVAL_REASON_CODES = {
    "approval_request_not_ready": "non_approval_reason_codes_missing_approval_request_not_ready",
    "readiness_report_recommends_do_not_request_approval_yet": "non_approval_reason_codes_missing_readiness_report_recommends_do_not_request_approval_yet",
    "no_operator_approval_decision": "non_approval_reason_codes_missing_no_operator_approval_decision",
    "approval_phrase_not_present": "non_approval_reason_codes_missing_approval_phrase_not_present",
    "dry_run_not_admitted": "non_approval_reason_codes_missing_dry_run_not_admitted",
    "dry_run_not_executed": "non_approval_reason_codes_missing_dry_run_not_executed",
    "receipt_not_issued": "non_approval_reason_codes_missing_receipt_not_issued",
    "rollback_cleanup_evidence_missing": "non_approval_reason_codes_missing_rollback_cleanup_evidence_missing",
    "publication_surfaces_blocked_by_policy": "non_approval_reason_codes_missing_publication_surfaces_blocked_by_policy",
    "publication_not_admitted": "non_approval_reason_codes_missing_publication_not_admitted",
    "real_execution_not_admitted": "non_approval_reason_codes_missing_real_execution_not_admitted",
    "production_ready_not_claimed": "non_approval_reason_codes_missing_production_ready_not_claimed",
}

REQUIRED_CONTINUING_BLOCKER_GROUPS: Dict[str, Dict[str, str]] = {
    "approval_blockers": {
        "missing_approval_decision": "continuing_blockers_approval_blockers_missing_missing_approval_decision",
        "operator_approval_not_granted": "continuing_blockers_approval_blockers_missing_operator_approval_not_granted",
    },
    "request_readiness_blockers": {
        "approval_request_not_ready": "continuing_blockers_request_readiness_blockers_missing_approval_request_not_ready",
        "unresolved_approval_blockers_present": "continuing_blockers_request_readiness_blockers_missing_unresolved_approval_blockers_present",
        "no_operator_approval_decision": "continuing_blockers_request_readiness_blockers_missing_no_operator_approval_decision",
        "approval_phrase_not_present": "continuing_blockers_request_readiness_blockers_missing_approval_phrase_not_present",
    },
    "execution_blockers": {
        "dry_run_not_admitted": "continuing_blockers_execution_blockers_missing_dry_run_not_admitted",
        "dry_run_not_executed": "continuing_blockers_execution_blockers_missing_dry_run_not_executed",
    },
    "receipt_blockers": {
        "receipt_not_issued": "continuing_blockers_receipt_blockers_missing_receipt_not_issued",
        "rollback_cleanup_evidence_missing": "continuing_blockers_receipt_blockers_missing_rollback_cleanup_evidence_missing",
    },
    "publication_blockers": {
        "publication_surfaces_blocked_by_policy": "continuing_blockers_publication_blockers_missing_publication_surfaces_blocked_by_policy",
        "publication_not_admitted": "continuing_blockers_publication_blockers_missing_publication_not_admitted",
    },
    "production_readiness_blockers": {
        "production_ready_not_claimed": "continuing_blockers_production_readiness_blockers_missing_production_ready_not_claimed",
        "real_execution_not_admitted": "continuing_blockers_production_readiness_blockers_missing_real_execution_not_admitted",
        "publication_not_admitted": "continuing_blockers_production_readiness_blockers_missing_publication_not_admitted",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate release-candidate publication dry-run non-approval decision v1."
        )
    )
    parser.add_argument(
        "decision_path",
        nargs="?",
        default=str(DEFAULT_DECISION_REL),
        help=(
            "Path to release-candidate publication dry-run non-approval "
            "decision JSON."
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
        ("publish allowed", "non_approval_record_allows_publish"),
        ("spawn allowed", "non_approval_record_allows_spawn"),
        (
            "production path writes allowed",
            "non_approval_record_allows_production_path_writes",
        ),
        (
            "engine path writes allowed",
            "non_approval_record_allows_engine_path_writes",
        ),
        (
            "cache/live db access allowed",
            "non_approval_record_allows_cache_live_db_access",
        ),
        (
            "cache live db access allowed",
            "non_approval_record_allows_cache_live_db_access",
        ),
        (
            "authoritative source uuid claims allowed",
            "non_approval_record_allows_authoritative_source_uuid_claims",
        ),
        (
            "authoritative asset id claims allowed",
            "non_approval_record_allows_authoritative_asset_id_claims",
        ),
        (
            "authoritative product id claims allowed",
            "non_approval_record_allows_authoritative_product_id_claims",
        ),
        (
            "non-approval decision record equals approval",
            "non_approval_record_equals_approval_claim",
        ),
        (
            "non-approval decision record equals approval-ready",
            "non_approval_record_equals_approval_ready_claim",
        ),
        (
            "non-approval decision record equals dry-run admission",
            "non_approval_record_equals_dry_run_admission_claim",
        ),
        (
            "non-approval decision record equals receipt issuance",
            "non_approval_record_equals_receipt_issuance_claim",
        ),
        (
            "non-approval decision record equals execution admission",
            "non_approval_record_equals_execution_admission_claim",
        ),
        (
            "non-approval decision record equals publication admission",
            "non_approval_record_equals_publication_admission_claim",
        ),
        (
            "non-approval decision record equals production_ready",
            "non_approval_record_equals_production_ready_claim",
        ),
        ("dry-run executed", "non_approval_record_claims_dry_run_executed"),
    )
    for needle, finding_id in checks:
        if needle in text:
            add_finding(
                findings,
                finding_id,
                "error",
                "Non-approval decision text must not allow blocked surfaces or imply admission.",
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
    decision_path = (
        Path(args.decision_path).resolve()
        if Path(args.decision_path).is_absolute()
        else (repo_root / args.decision_path).resolve()
    )
    schema_path = (repo_root / DEFAULT_SCHEMA_REL).resolve()

    if not decision_path.exists():
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": f"non-approval decision record not found: {decision_path}",
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

    decision = load_json(decision_path)
    schema = load_json(schema_path)
    findings: List[Dict[str, Any]] = []

    ok, schema_errors = validate_schema(decision, schema)
    if not ok:
        for message in schema_errors:
            add_finding(
                findings,
                "schema_validation_error",
                "error",
                "Non-approval decision record failed schema validation.",
                {"error": message},
            )

    source_artifacts = (
        decision.get("source_artifacts")
        if isinstance(decision.get("source_artifacts"), dict)
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

    matrix_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "candidate_matrix_ref",
        DEFAULT_MATRIX_REL,
    )
    preflight_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "preflight_contracts_ref",
        DEFAULT_PREFLIGHT_REL,
    )
    preflight_proof_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "preflight_proof_packages_ref",
        DEFAULT_PREFLIGHT_PROOF_REL,
    )
    rollup_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "readiness_rollup_ref",
        DEFAULT_ROLLUP_REL,
    )
    dry_run_plan_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "dry_run_plan_ref",
        DEFAULT_DRY_RUN_PLAN_REL,
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
    operator_packet_completeness_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "operator_approval_packet_completeness_ref",
        DEFAULT_OPERATOR_PACKET_COMPLETENESS_REL,
    )
    approval_request_readiness_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "approval_request_readiness_ref",
        DEFAULT_APPROVAL_REQUEST_READINESS_REL,
    )
    production_readiness_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "production_readiness_report_ref",
        DEFAULT_PRODUCTION_READINESS_REL,
    )
    noop_decision_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "noop_receipt_status_ref",
        DEFAULT_NOOP_DECISION_REL,
    )

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

    source_status_expected: Dict[str, str] = {key: "fail" for key in SOURCE_STATUS_KEYS}

    if matrix_path.exists():
        code, payload, raw_error = run_validator(
            repo_root,
            MATRIX_VALIDATOR_REL,
            [str(matrix_path)],
        )
        if code == 0 and payload and payload.get("status") == "pass":
            source_status_expected["candidate_matrix_status"] = "pass"
        else:
            add_finding(
                findings,
                "candidate_matrix_validation_failed",
                "error",
                "Candidate matrix validator must pass.",
                {"return_code": code, "raw_error": raw_error},
            )

    if preflight_path.exists():
        code, payload, raw_error = run_validator(
            repo_root,
            PREFLIGHT_VALIDATOR_REL,
            [str(preflight_path)],
        )
        if code == 0 and payload and payload.get("status") == "pass":
            source_status_expected["preflight_contracts_status"] = "pass"
        else:
            add_finding(
                findings,
                "preflight_contracts_validation_failed",
                "error",
                "Preflight contracts validator must pass.",
                {"return_code": code, "raw_error": raw_error},
            )

    if preflight_proof_path.exists():
        code, payload, raw_error = run_validator(
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
        if code == 0 and payload and payload.get("status") == "pass":
            source_status_expected["preflight_proof_packages_status"] = "pass"
        else:
            add_finding(
                findings,
                "preflight_proof_packages_validation_failed",
                "error",
                "Preflight proof packages validator must pass.",
                {"return_code": code, "raw_error": raw_error},
            )

    if rollup_path.exists():
        code, payload, raw_error = run_validator(
            repo_root,
            READINESS_ROLLUP_VALIDATOR_REL,
            [str(rollup_path)],
        )
        if code == 0 and payload and payload.get("status") == "pass":
            source_status_expected["readiness_rollup_status"] = "pass"
        else:
            add_finding(
                findings,
                "readiness_rollup_validation_failed",
                "error",
                "Readiness rollup validator must pass.",
                {"return_code": code, "raw_error": raw_error},
            )

    if dry_run_plan_path.exists():
        code, payload, raw_error = run_validator(
            repo_root,
            DRY_RUN_PLAN_VALIDATOR_REL,
            [str(dry_run_plan_path)],
        )
        if code == 0 and payload and payload.get("status") == "pass":
            source_status_expected["dry_run_plan_status"] = "pass"
        else:
            add_finding(
                findings,
                "dry_run_plan_validation_failed",
                "error",
                "Dry-run plan validator must pass.",
                {"return_code": code, "raw_error": raw_error},
            )

    if dry_run_receipt_contract_path.exists():
        code, payload, raw_error = run_validator(
            repo_root,
            DRY_RUN_RECEIPT_VALIDATOR_REL,
            [str(dry_run_receipt_contract_path)],
        )
        if code == 0 and payload and payload.get("status") == "pass":
            source_status_expected["dry_run_receipt_contract_status"] = "pass"
        else:
            add_finding(
                findings,
                "dry_run_receipt_contract_validation_failed",
                "error",
                "Dry-run receipt contract validator must pass.",
                {"return_code": code, "raw_error": raw_error},
            )

    if dry_run_receipt_blocked_path.exists():
        code, payload, raw_error = run_validator(
            repo_root,
            DRY_RUN_RECEIPT_VALIDATOR_REL,
            [str(dry_run_receipt_blocked_path)],
        )
        if code == 0 and payload and payload.get("status") == "pass":
            source_status_expected["blocked_unissued_receipt_status"] = "pass"
        else:
            add_finding(
                findings,
                "blocked_unissued_receipt_validation_failed",
                "error",
                "Blocked/unissued dry-run receipt validator must pass.",
                {"return_code": code, "raw_error": raw_error},
            )

    if admission_blockers_path.exists():
        code, payload, raw_error = run_validator(
            repo_root,
            ADMISSION_BLOCKERS_VALIDATOR_REL,
            [str(admission_blockers_path)],
        )
        if code == 0 and payload and payload.get("status") == "pass":
            source_status_expected["admission_blocker_checklist_status"] = "pass"
        else:
            add_finding(
                findings,
                "admission_blockers_validation_failed",
                "error",
                "Dry-run admission blocker checklist validator must pass.",
                {"return_code": code, "raw_error": raw_error},
            )

    if operator_packet_path.exists():
        code, payload, raw_error = run_validator(
            repo_root,
            OPERATOR_PACKET_VALIDATOR_REL,
            [str(operator_packet_path)],
        )
        if code == 0 and payload and payload.get("status") == "pass":
            source_status_expected["operator_approval_packet_status"] = "pass"
        else:
            add_finding(
                findings,
                "operator_approval_packet_validation_failed",
                "error",
                "Operator approval packet validator must pass.",
                {"return_code": code, "raw_error": raw_error},
            )

    if operator_packet_completeness_path.exists():
        code, payload, raw_error = run_validator(
            repo_root,
            OPERATOR_PACKET_COMPLETENESS_VALIDATOR_REL,
            [str(operator_packet_completeness_path)],
        )
        if code == 0 and payload and payload.get("status") == "pass":
            source_status_expected["operator_approval_packet_completeness_status"] = "pass"
        else:
            add_finding(
                findings,
                "operator_approval_packet_completeness_validation_failed",
                "error",
                "Operator approval packet completeness validator must pass.",
                {"return_code": code, "raw_error": raw_error},
            )

    if approval_request_readiness_path.exists():
        code, payload, raw_error = run_validator(
            repo_root,
            APPROVAL_REQUEST_READINESS_VALIDATOR_REL,
            [str(approval_request_readiness_path)],
        )
        if code == 0 and payload and payload.get("status") == "pass":
            source_status_expected["approval_request_readiness_status"] = "pass"
        else:
            add_finding(
                findings,
                "approval_request_readiness_validation_failed",
                "error",
                "Approval request readiness validator must pass.",
                {"return_code": code, "raw_error": raw_error},
            )
    else:
        add_finding(
            findings,
            "approval_request_readiness_validation_failed",
            "error",
            "Approval request readiness validator must pass.",
            {
                "reason": "source_artifact_missing",
                "path": str(approval_request_readiness_path),
            },
        )

    if production_readiness_path.exists():
        try:
            production_readiness = load_json(production_readiness_path)
            source_status_expected["production_readiness_status"] = _validate_production_readiness_report(
                production_readiness,
                findings,
            )
        except Exception as exc:  # pragma: no cover - defensive
            add_finding(
                findings,
                "production_readiness_parse_failed",
                "error",
                "Failed to load referenced production readiness report.",
                {"error": str(exc)},
            )

    if noop_decision_path.exists():
        try:
            noop_payload = load_json(noop_decision_path)
            source_status_expected["noop_receipt_status"] = _validate_noop_decision_record(
                noop_payload,
                findings,
            )
        except Exception as exc:  # pragma: no cover - defensive
            add_finding(
                findings,
                "noop_receipt_status_parse_failed",
                "error",
                "Failed to load referenced no-op receipt status decision record.",
                {"error": str(exc)},
            )

    source_status_reported = (
        decision.get("source_artifact_validation_status")
        if isinstance(decision.get("source_artifact_validation_status"), dict)
        else {}
    )
    for key in SOURCE_STATUS_KEYS:
        if str(source_status_reported.get(key, "")).strip() != "pass":
            add_finding(
                findings,
                "source_artifact_validation_status_not_pass",
                "error",
                "source_artifact_validation_status must report pass for required source artifacts.",
                {"field": key, "actual": source_status_reported.get(key)},
            )
        if source_status_expected.get(key) != "pass":
            add_finding(
                findings,
                "computed_source_artifact_validation_status_not_pass",
                "error",
                "Computed source artifact validation status did not pass.",
                {"field": key, "actual": source_status_expected.get(key)},
            )

    candidate_id = str(decision.get("candidate_id", "")).strip()
    candidate_type = str(decision.get("candidate_type", "")).strip()
    decision_type = str(decision.get("decision_type", "")).strip()
    decision_status = str(decision.get("decision_status", "")).strip()
    decision_effect = str(decision.get("decision_effect", "")).strip()
    selected_operator_decision = str(decision.get("selected_operator_decision", "")).strip()
    next_recommended_action = str(decision.get("next_recommended_action", "")).strip()
    approval_phrase = str(
        decision.get("approval_phrase_required_for_future_reconsideration", "")
    ).strip()

    if candidate_id != TARGET_CANDIDATE_ID:
        add_finding(
            findings,
            "candidate_id_mismatch",
            "error",
            "candidate_id must be release_candidate_package_publish_dry_run_v1.",
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
    if decision_type != EXPECTED_NON_APPROVAL_DECISION_TYPE:
        add_finding(
            findings,
            "decision_type_not_non_approval",
            "error",
            "decision_type must be non_approval.",
            {"actual": decision_type},
        )
    if decision_status != EXPECTED_NON_APPROVAL_DECISION_STATUS:
        add_finding(
            findings,
            "decision_status_not_active_non_approval",
            "error",
            "decision_status must be active_non_approval.",
            {"actual": decision_status},
        )
    if decision_effect != EXPECTED_NON_APPROVAL_DECISION_EFFECT:
        add_finding(
            findings,
            "decision_effect_not_candidate_remains_blocked_unadmitted",
            "error",
            "decision_effect must be candidate_remains_blocked_unadmitted.",
            {"actual": decision_effect},
        )

    if decision.get("generated_from_static_artifacts_only") is not True:
        add_finding(
            findings,
            "generated_from_static_artifacts_only_not_true",
            "error",
            "generated_from_static_artifacts_only must be true.",
            {"actual": decision.get("generated_from_static_artifacts_only")},
        )

    for field, finding_id in REQUIRED_FLAG_FALSE_FIELDS:
        if bool(decision.get(field, False)):
            add_finding(
                findings,
                finding_id,
                "error",
                f"{field} must remain false for non-approval posture.",
                {"field": field, "actual": decision.get(field)},
            )

    if selected_operator_decision != EXPECTED_SELECTED_OPERATOR_DECISION:
        add_finding(
            findings,
            "selected_operator_decision_not_do_not_approve",
            "error",
            "selected_operator_decision must be do_not_approve.",
            {"actual": selected_operator_decision},
        )

    if next_recommended_action != EXPECTED_NEXT_RECOMMENDED_ACTION:
        add_finding(
            findings,
            "next_recommended_action_not_continue_hardening_no_execution",
            "error",
            "next_recommended_action must be continue_hardening_no_execution.",
            {"actual": next_recommended_action},
        )

    if approval_phrase != EXPECTED_APPROVAL_PHRASE:
        add_finding(
            findings,
            "approval_phrase_required_mismatch",
            "error",
            "approval_phrase_required_for_future_reconsideration must match exact candidate-specific phrase.",
            {"actual": approval_phrase},
        )

    approval_decision_reference = decision.get("approval_decision_reference")
    if isinstance(approval_decision_reference, str) and approval_decision_reference.strip():
        add_finding(
            findings,
            "approval_decision_reference_not_allowed",
            "error",
            "approval_decision_reference must be null/empty for active non-approval posture.",
            {"actual": approval_decision_reference},
        )

    non_approval_reason_codes = _check_non_empty_string_list(
        decision,
        "non_approval_reason_codes",
        findings,
        "non_approval_reason_codes_missing_or_empty",
        "non_approval_reason_codes must be present and non-empty.",
    )
    _check_required_token_set(
        non_approval_reason_codes,
        REQUIRED_NON_APPROVAL_REASON_CODES,
        findings,
        "non_approval_reason_codes",
    )

    continuing_blockers = (
        decision.get("continuing_blockers")
        if isinstance(decision.get("continuing_blockers"), dict)
        else {}
    )
    if not continuing_blockers:
        add_finding(
            findings,
            "continuing_blockers_missing_or_empty",
            "error",
            "continuing_blockers must be present and non-empty.",
        )

    for group, required_tokens in REQUIRED_CONTINUING_BLOCKER_GROUPS.items():
        values = as_string_list(continuing_blockers.get(group))
        if not values:
            add_finding(
                findings,
                f"continuing_blockers_{group}_missing_or_empty",
                "error",
                f"continuing_blockers.{group} must be present and non-empty.",
            )
            continue
        _check_required_token_set(
            values,
            required_tokens,
            findings,
            f"continuing_blockers.{group}",
        )

    required_before_reconsideration = _check_non_empty_string_list(
        decision,
        "required_before_reconsideration",
        findings,
        "required_before_reconsideration_missing_or_empty",
        "required_before_reconsideration must be present and non-empty.",
    )
    if not required_before_reconsideration:
        add_finding(
            findings,
            "required_before_reconsideration_missing",
            "error",
            "required_before_reconsideration must remain non-empty.",
        )

    forbidden_actions = _check_non_empty_string_list(
        decision,
        "forbidden_actions",
        findings,
        "forbidden_actions_missing_or_empty",
        "forbidden_actions must be present and non-empty.",
    )
    forbidden_outputs = _check_non_empty_string_list(
        decision,
        "forbidden_outputs",
        findings,
        "forbidden_outputs_missing_or_empty",
        "forbidden_outputs must be present and non-empty.",
    )
    forbidden_paths = _check_non_empty_string_list(
        decision,
        "forbidden_paths",
        findings,
        "forbidden_paths_missing_or_empty",
        "forbidden_paths must be present and non-empty.",
    )

    if not forbidden_actions:
        add_finding(
            findings,
            "forbidden_actions_missing",
            "error",
            "forbidden_actions must remain non-empty.",
        )
    if not forbidden_outputs:
        add_finding(
            findings,
            "forbidden_outputs_missing",
            "error",
            "forbidden_outputs must remain non-empty.",
        )
    if not forbidden_paths:
        add_finding(
            findings,
            "forbidden_paths_missing",
            "error",
            "forbidden_paths must remain non-empty.",
        )

    if bool(decision.get("unsafe_claims_detected", False)):
        add_finding(
            findings,
            "unsafe_claims_detected_not_allowed",
            "error",
            "unsafe_claims_detected must remain false.",
        )

    safety_notes = as_string_list(decision.get("safety_notes"))
    if not safety_notes:
        add_finding(
            findings,
            "safety_notes_missing_or_empty",
            "error",
            "safety_notes must be present and non-empty.",
        )

    _check_forbidden_claim_language(decision, findings)

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
    operator_packet_completeness_payload_raw = (
        load_json(operator_packet_completeness_path)
        if operator_packet_completeness_path.exists()
        else {}
    )
    approval_request_readiness_payload_raw = (
        load_json(approval_request_readiness_path)
        if approval_request_readiness_path.exists()
        else {}
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

    if (
        str(
            operator_packet_completeness_payload_raw.get("completeness_review_status", "")
        ).strip()
        != EXPECTED_COMPLETENESS_STATUS
    ):
        add_finding(
            findings,
            "operator_approval_packet_completeness_status_not_expected",
            "error",
            "Operator approval packet completeness must keep completeness_review_status=static_completeness_valid_blocked.",
            {
                "actual": operator_packet_completeness_payload_raw.get(
                    "completeness_review_status"
                )
            },
        )

    if (
        str(
            approval_request_readiness_payload_raw.get(
                "approval_request_readiness_status", ""
            )
        ).strip()
        != EXPECTED_APPROVAL_REQUEST_READINESS_STATUS
    ):
        add_finding(
            findings,
            "approval_request_readiness_status_not_expected",
            "error",
            "Approval request readiness report must keep approval_request_readiness_status=static_request_readiness_valid_blocked.",
            {
                "actual": approval_request_readiness_payload_raw.get(
                    "approval_request_readiness_status"
                )
            },
        )

    if (
        str(
            approval_request_readiness_payload_raw.get("final_recommendation", "")
        ).strip()
        != EXPECTED_APPROVAL_REQUEST_READINESS_FINAL_RECOMMENDATION
    ):
        add_finding(
            findings,
            "approval_request_readiness_final_recommendation_not_expected",
            "error",
            "Approval request readiness report must keep final_recommendation=do_not_request_approval_yet.",
            {
                "actual": approval_request_readiness_payload_raw.get(
                    "final_recommendation"
                )
            },
        )

    for payload_name, payload_value in (
        ("dry_run_plan", dry_run_plan_payload_raw),
        ("dry_run_receipt_contract", dry_run_receipt_contract_payload_raw),
        ("blocked_unissued_receipt", dry_run_receipt_blocked_payload_raw),
        ("admission_blockers", admission_blockers_payload_raw),
        ("operator_approval_packet", operator_packet_payload_raw),
        ("operator_approval_packet_completeness", operator_packet_completeness_payload_raw),
        ("approval_request_readiness", approval_request_readiness_payload_raw),
    ):
        if str(payload_value.get("candidate_id", "")).strip() != TARGET_CANDIDATE_ID:
            add_finding(
                findings,
                "candidate_id_mismatch_with_source_artifact",
                "error",
                "Source artifacts must target release_candidate_package_publish_dry_run_v1.",
                {"artifact": payload_name, "actual": payload_value.get("candidate_id")},
            )
        if str(payload_value.get("candidate_type", "")).strip() != TARGET_CANDIDATE_TYPE:
            add_finding(
                findings,
                "candidate_type_mismatch_with_source_artifact",
                "error",
                "Source artifacts must keep candidate_type=dry_run.",
                {"artifact": payload_name, "actual": payload_value.get("candidate_type")},
            )

    if (
        str(dry_run_receipt_contract_payload_raw.get("receipt_type", "")).strip()
        != TARGET_RECEIPT_TYPE
    ):
        add_finding(
            findings,
            "dry_run_receipt_type_mismatch",
            "error",
            "Dry-run receipt contract must keep receipt_type=release_candidate_package_publish_dry_run_receipt_v1.",
        )

    if (
        str(approval_request_readiness_payload_raw.get("final_recommendation", "")).strip()
        != EXPECTED_APPROVAL_REQUEST_READINESS_FINAL_RECOMMENDATION
    ):
        add_finding(
            findings,
            "readiness_report_final_recommendation_not_do_not_request_approval_yet",
            "error",
            "Referenced approval request readiness report must keep final_recommendation=do_not_request_approval_yet.",
        )

    severity_set = {str(item.get("severity", "")).strip() for item in findings}
    status = "fail" if "error" in severity_set else "pass"

    report_payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_NON_APPROVAL_DECISION_VALIDATION_v1_REPORT",
        "status": status,
        "release_candidate_publication_dry_run_non_approval_decision_present": True,
        "release_candidate_publication_dry_run_non_approval_decision_path": str(decision_path),
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
        "production_readiness_report_path": str(production_readiness_path),
        "noop_receipt_status_path": str(noop_decision_path),
        "source_artifact_validation_status": source_status_reported,
        "computed_source_artifact_validation_status": source_status_expected,
        "planned_candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "decision_type": decision_type,
        "decision_status": decision_status,
        "decision_effect": decision_effect,
        "selected_operator_decision": selected_operator_decision,
        "next_recommended_action": next_recommended_action,
        "approval_request_ready": bool(decision.get("approval_request_ready", False)),
        "operator_approval_granted": bool(decision.get("operator_approval_granted", False)),
        "approval_phrase_present": bool(decision.get("approval_phrase_present", False)),
        "dry_run_admitted": bool(decision.get("dry_run_admitted", False)),
        "dry_run_executed": bool(decision.get("dry_run_executed", False)),
        "receipt_issued": bool(decision.get("receipt_issued", False)),
        "publication_admitted": bool(decision.get("publication_admitted", False)),
        "real_execution_admitted": bool(decision.get("real_execution_admitted", False)),
        "production_ready_claimed": bool(decision.get("production_ready_claimed", False)),
        "approval_phrase_required_for_future_reconsideration": approval_phrase,
        "non_approval_reason_codes": non_approval_reason_codes,
        "continuing_blockers": continuing_blockers,
        "required_before_reconsideration": required_before_reconsideration,
        "forbidden_actions": forbidden_actions,
        "forbidden_outputs": forbidden_outputs,
        "forbidden_paths": forbidden_paths,
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
