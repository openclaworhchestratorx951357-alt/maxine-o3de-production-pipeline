#!/usr/bin/env python3
"""Validate release-candidate publication dry-run approval request readiness v1."""

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
EXPECTED_READINESS_STATUS = "static_request_readiness_valid_blocked"
EXPECTED_COMPLETENESS_STATUS = "static_completeness_valid_blocked"
EXPECTED_OPERATOR_PACKET_STATUS = "static_template_valid_blocked"
EXPECTED_ADMISSION_BLOCKERS_STATUS = "static_checklist_valid_blocked"
EXPECTED_RECEIPT_CONTRACT_STATUS = "static_contract_valid_blocked"
EXPECTED_BLOCKED_RECEIPT_STATUS = "blocked_unissued_contract_only"
EXPECTED_DRY_RUN_PLAN_STATUS = "static_plan_valid_blocked"
EXPECTED_ROLLUP_STATUS = "static_rollup_valid_blocked"
EXPECTED_ROLLUP_NEXT_SLICE_ID = "candidate_specific_dry_run_planning_v1"
EXPECTED_FINAL_RECOMMENDATION = "do_not_request_approval_yet"

DEFAULT_REPORT_REL = Path(
    "examples/execution-admission/"
    "release_candidate_package_publish_dry_run_approval_request_readiness_v1.json"
)
DEFAULT_SCHEMA_REL = Path(
    "schemas/maxine_release_candidate_publication_dry_run_approval_request_readiness.schema.json"
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

REQUIRED_REQUEST_READINESS_BLOCKERS = {
    "approval_request_not_ready": "request_readiness_blockers_missing_approval_request_not_ready",
    "unresolved_approval_blockers_present": "request_readiness_blockers_missing_unresolved_approval_blockers_present",
    "no_operator_approval_decision": "request_readiness_blockers_missing_no_operator_approval_decision",
    "approval_phrase_not_present": "request_readiness_blockers_missing_approval_phrase_not_present",
}
REQUIRED_APPROVAL_BLOCKERS = {
    "missing_approval_decision": "approval_blockers_missing_missing_approval_decision",
    "operator_approval_not_granted": "approval_blockers_missing_operator_approval_not_granted",
}
REQUIRED_EXECUTION_BLOCKERS = {
    "dry_run_not_admitted": "execution_blockers_missing_dry_run_not_admitted",
    "dry_run_not_executed": "execution_blockers_missing_dry_run_not_executed",
}
REQUIRED_RECEIPT_BLOCKERS = {
    "receipt_not_issued": "receipt_blockers_missing_receipt_not_issued",
    "rollback_cleanup_evidence_missing": "receipt_blockers_missing_rollback_cleanup_evidence_missing",
}
REQUIRED_PUBLICATION_BLOCKERS = {
    "publication_surfaces_blocked_by_policy": "publication_blockers_missing_publication_surfaces_blocked_by_policy",
    "publication_not_admitted": "publication_blockers_missing_publication_not_admitted",
}
REQUIRED_PRODUCTION_READINESS_BLOCKERS = {
    "production_ready_not_claimed": "production_readiness_blockers_missing_production_ready_not_claimed",
    "real_execution_not_admitted": "production_readiness_blockers_missing_real_execution_not_admitted",
    "publication_not_admitted": "production_readiness_blockers_missing_publication_not_admitted",
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
    "tools/execution-admission/validate_release_candidate_publication_dry_run_operator_approval_packet_completeness.py": (
        "required_validation_commands_missing_operator_approval_packet_completeness_validator"
    ),
    "tools/audit/verify_sandbox_writer_safety.py": (
        "required_validation_commands_missing_safety_verifier"
    ),
    "tools/release-lane/prove_pilot_release_chain.py": (
        "required_validation_commands_missing_proof_flow"
    ),
    "tools/production-readiness-report/validate_production_readiness_report.py": (
        "required_validation_commands_missing_production_readiness_generated_manifest_validator"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate release-candidate publication dry-run approval request readiness v1."
        )
    )
    parser.add_argument(
        "report_path",
        nargs="?",
        default=str(DEFAULT_REPORT_REL),
        help="Path to release-candidate publication dry-run approval request readiness JSON.",
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
        ("publish allowed", "readiness_report_allows_publish"),
        ("spawn allowed", "readiness_report_allows_spawn"),
        ("production path writes allowed", "readiness_report_allows_production_path_writes"),
        ("engine path writes allowed", "readiness_report_allows_engine_path_writes"),
        ("cache/live db access allowed", "readiness_report_allows_cache_live_db_access"),
        ("cache live db access allowed", "readiness_report_allows_cache_live_db_access"),
        (
            "authoritative source uuid claims allowed",
            "readiness_report_allows_authoritative_source_uuid_claims",
        ),
        (
            "authoritative asset id claims allowed",
            "readiness_report_allows_authoritative_asset_id_claims",
        ),
        (
            "authoritative product id claims allowed",
            "readiness_report_allows_authoritative_product_id_claims",
        ),
        ("dry-run executed", "readiness_report_claims_dry_run_executed"),
        ("dry run executed", "readiness_report_claims_dry_run_executed"),
    )
    for needle, finding_id in checks:
        if needle in text:
            add_finding(
                findings,
                finding_id,
                "error",
                "Readiness report text must not allow blocked surfaces or claims.",
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
    report_path = (
        Path(args.report_path).resolve()
        if Path(args.report_path).is_absolute()
        else (repo_root / args.report_path).resolve()
    )
    schema_path = (repo_root / DEFAULT_SCHEMA_REL).resolve()

    if not report_path.exists():
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": f"approval request readiness report not found: {report_path}",
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

    report = load_json(report_path)
    schema = load_json(schema_path)
    findings: List[Dict[str, Any]] = []

    ok, schema_errors = validate_schema(report, schema)
    if not ok:
        for message in schema_errors:
            add_finding(
                findings,
                "schema_validation_error",
                "error",
                "Approval request readiness report failed schema validation.",
                {"error": message},
            )

    source_artifacts = (
        report.get("source_artifacts")
        if isinstance(report.get("source_artifacts"), dict)
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
    operator_packet_completeness_path = _path_from_source_artifacts(
        repo_root,
        source_artifacts,
        "operator_approval_packet_completeness_ref",
        DEFAULT_OPERATOR_PACKET_COMPLETENESS_REL,
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

    source_path_pairs = {
        "candidate_matrix": matrix_path,
        "preflight_contracts": preflight_path,
        "preflight_proof_packages": preflight_proof_path,
        "readiness_rollup": rollup_path,
        "dry_run_plan": dry_run_plan_path,
        "dry_run_receipt_contract": dry_run_receipt_contract_path,
        "blocked_unissued_receipt": dry_run_receipt_blocked_path,
        "admission_blocker_checklist": admission_blockers_path,
        "operator_approval_packet": operator_packet_path,
        "operator_approval_packet_completeness": operator_packet_completeness_path,
        "production_readiness_report": production_readiness_path,
        "noop_receipt_status": noop_decision_path,
    }

    for source_name, path in source_path_pairs.items():
        if not path.exists():
            add_finding(
                findings,
                "source_artifact_missing",
                "error",
                "Referenced source artifact is missing.",
                {"source": source_name, "path": str(path)},
            )

    source_status_expected: Dict[str, str] = {key: "pass" for key in SOURCE_STATUS_KEYS}

    matrix_code, matrix_payload, matrix_error = run_validator(
        repo_root,
        MATRIX_VALIDATOR_REL,
        [str(matrix_path)],
    )
    if matrix_code != 0 or not isinstance(matrix_payload, dict):
        source_status_expected["candidate_matrix_status"] = "fail"
        add_finding(
            findings,
            "candidate_matrix_validation_failed",
            "error",
            "Candidate matrix validator failed.",
            {"return_code": matrix_code, "error": matrix_error},
        )

    preflight_code, preflight_payload, preflight_error = run_validator(
        repo_root,
        PREFLIGHT_VALIDATOR_REL,
        [str(preflight_path)],
    )
    if preflight_code != 0 or not isinstance(preflight_payload, dict):
        source_status_expected["preflight_contracts_status"] = "fail"
        add_finding(
            findings,
            "preflight_contracts_validation_failed",
            "error",
            "Preflight contracts validator failed.",
            {"return_code": preflight_code, "error": preflight_error},
        )

    preflight_proof_code, preflight_proof_payload, preflight_proof_error = run_validator(
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
    if preflight_proof_code != 0 or not isinstance(preflight_proof_payload, dict):
        source_status_expected["preflight_proof_packages_status"] = "fail"
        add_finding(
            findings,
            "preflight_proof_packages_validation_failed",
            "error",
            "Preflight proof packages validator failed.",
            {"return_code": preflight_proof_code, "error": preflight_proof_error},
        )

    rollup_code, rollup_payload, rollup_error = run_validator(
        repo_root,
        READINESS_ROLLUP_VALIDATOR_REL,
        [str(rollup_path)],
    )
    if rollup_code != 0 or not isinstance(rollup_payload, dict):
        source_status_expected["readiness_rollup_status"] = "fail"
        add_finding(
            findings,
            "readiness_rollup_validation_failed",
            "error",
            "Readiness rollup validator failed.",
            {"return_code": rollup_code, "error": rollup_error},
        )

    dry_run_plan_code, dry_run_plan_payload, dry_run_plan_error = run_validator(
        repo_root,
        DRY_RUN_PLAN_VALIDATOR_REL,
        [str(dry_run_plan_path)],
    )
    if dry_run_plan_code != 0 or not isinstance(dry_run_plan_payload, dict):
        source_status_expected["dry_run_plan_status"] = "fail"
        add_finding(
            findings,
            "dry_run_plan_validation_failed",
            "error",
            "Dry-run plan validator failed.",
            {"return_code": dry_run_plan_code, "error": dry_run_plan_error},
        )

    dry_run_receipt_contract_code, dry_run_receipt_contract_payload, dry_run_receipt_contract_error = run_validator(
        repo_root,
        DRY_RUN_RECEIPT_VALIDATOR_REL,
        [str(dry_run_receipt_contract_path)],
    )
    if dry_run_receipt_contract_code != 0 or not isinstance(dry_run_receipt_contract_payload, dict):
        source_status_expected["dry_run_receipt_contract_status"] = "fail"
        add_finding(
            findings,
            "dry_run_receipt_contract_validation_failed",
            "error",
            "Dry-run receipt contract validator failed.",
            {
                "return_code": dry_run_receipt_contract_code,
                "error": dry_run_receipt_contract_error,
            },
        )

    dry_run_receipt_blocked_code, dry_run_receipt_blocked_payload, dry_run_receipt_blocked_error = run_validator(
        repo_root,
        DRY_RUN_RECEIPT_VALIDATOR_REL,
        [str(dry_run_receipt_blocked_path)],
    )
    if dry_run_receipt_blocked_code != 0 or not isinstance(dry_run_receipt_blocked_payload, dict):
        source_status_expected["blocked_unissued_receipt_status"] = "fail"
        add_finding(
            findings,
            "blocked_unissued_receipt_validation_failed",
            "error",
            "Blocked/unissued dry-run receipt validator failed.",
            {"return_code": dry_run_receipt_blocked_code, "error": dry_run_receipt_blocked_error},
        )

    admission_blockers_code, admission_blockers_payload, admission_blockers_error = run_validator(
        repo_root,
        ADMISSION_BLOCKERS_VALIDATOR_REL,
        [str(admission_blockers_path)],
    )
    if admission_blockers_code != 0 or not isinstance(admission_blockers_payload, dict):
        source_status_expected["admission_blocker_checklist_status"] = "fail"
        add_finding(
            findings,
            "admission_blockers_validation_failed",
            "error",
            "Admission blocker checklist validator failed.",
            {"return_code": admission_blockers_code, "error": admission_blockers_error},
        )

    operator_packet_code, operator_packet_payload, operator_packet_error = run_validator(
        repo_root,
        OPERATOR_PACKET_VALIDATOR_REL,
        [str(operator_packet_path)],
    )
    if operator_packet_code != 0 or not isinstance(operator_packet_payload, dict):
        source_status_expected["operator_approval_packet_status"] = "fail"
        add_finding(
            findings,
            "operator_approval_packet_validation_failed",
            "error",
            "Operator approval packet validator failed.",
            {"return_code": operator_packet_code, "error": operator_packet_error},
        )

    operator_packet_completeness_code, operator_packet_completeness_payload, operator_packet_completeness_error = run_validator(
        repo_root,
        OPERATOR_PACKET_COMPLETENESS_VALIDATOR_REL,
        [str(operator_packet_completeness_path)],
    )
    if operator_packet_completeness_code != 0 or not isinstance(
        operator_packet_completeness_payload, dict
    ):
        source_status_expected["operator_approval_packet_completeness_status"] = "fail"
        add_finding(
            findings,
            "operator_approval_packet_completeness_validation_failed",
            "error",
            "Operator approval packet completeness validator failed.",
            {
                "return_code": operator_packet_completeness_code,
                "error": operator_packet_completeness_error,
            },
        )

    production_readiness_payload_raw: Dict[str, Any] = {}
    if production_readiness_path.exists():
        production_readiness_payload_raw = load_json(production_readiness_path)
        source_status_expected["production_readiness_status"] = _validate_production_readiness_report(
            production_readiness_payload_raw,
            findings,
        )
    else:
        source_status_expected["production_readiness_status"] = "fail"

    noop_decision_payload_raw: Dict[str, Any] = {}
    if noop_decision_path.exists():
        noop_decision_payload_raw = load_json(noop_decision_path)
        source_status_expected["noop_receipt_status"] = _validate_noop_decision_record(
            noop_decision_payload_raw,
            findings,
        )
    else:
        source_status_expected["noop_receipt_status"] = "fail"

    source_status_reported = (
        report.get("source_artifact_validation_status")
        if isinstance(report.get("source_artifact_validation_status"), dict)
        else {}
    )
    for status_key in SOURCE_STATUS_KEYS:
        if str(source_status_reported.get(status_key, "")).strip() != "pass":
            add_finding(
                findings,
                "source_artifact_validation_status_not_pass",
                "error",
                "source_artifact_validation_status must report pass for all required artifacts.",
                {"key": status_key, "actual": source_status_reported.get(status_key)},
            )
        if source_status_expected.get(status_key) != "pass":
            add_finding(
                findings,
                "computed_source_artifact_status_not_pass",
                "error",
                "Cross-validated source artifact status is not pass.",
                {"key": status_key, "computed": source_status_expected.get(status_key)},
            )

    candidate_id = str(report.get("candidate_id", "")).strip()
    candidate_type = str(report.get("candidate_type", "")).strip()
    readiness_status = str(report.get("approval_request_readiness_status", "")).strip()
    admission_status = str(report.get("admission_status", "")).strip()
    approval_phrase = str(report.get("approval_phrase_required", "")).strip()
    final_recommendation = str(report.get("final_recommendation", "")).strip()

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
            "candidate_type must remain dry_run.",
            {"actual": candidate_type},
        )
    if readiness_status != EXPECTED_READINESS_STATUS:
        add_finding(
            findings,
            "approval_request_readiness_status_not_static_request_readiness_valid_blocked",
            "error",
            "approval_request_readiness_status must remain static_request_readiness_valid_blocked.",
            {"actual": readiness_status},
        )
    if admission_status != "unadmitted":
        add_finding(
            findings,
            "admission_status_not_unadmitted",
            "error",
            "admission_status must remain unadmitted.",
            {"actual": admission_status},
        )
    if report.get("packet_structurally_complete") is not True:
        add_finding(
            findings,
            "packet_structurally_complete_not_true",
            "error",
            "packet_structurally_complete must remain true.",
            {"actual": report.get("packet_structurally_complete")},
        )
    if report.get("packet_complete_for_future_review_template") is not True:
        add_finding(
            findings,
            "packet_complete_for_future_review_template_not_true",
            "error",
            "packet_complete_for_future_review_template must remain true.",
            {"actual": report.get("packet_complete_for_future_review_template")},
        )

    for field, finding_id in REQUIRED_FLAG_FALSE_FIELDS:
        if bool(report.get(field, False)):
            add_finding(
                findings,
                finding_id,
                "error",
                f"{field} must remain false in this milestone.",
                {"actual": report.get(field)},
            )

    if report.get("generated_from_static_artifacts_only") is not True:
        add_finding(
            findings,
            "generated_from_static_artifacts_only_not_true",
            "error",
            "generated_from_static_artifacts_only must be true.",
        )

    if approval_phrase != EXPECTED_APPROVAL_PHRASE:
        add_finding(
            findings,
            "approval_phrase_required_mismatch",
            "error",
            "approval_phrase_required must match the exact candidate-specific phrase.",
            {"actual": approval_phrase},
        )

    approval_decision_reference = report.get("approval_decision_reference")
    if isinstance(approval_decision_reference, str) and approval_decision_reference.strip():
        add_finding(
            findings,
            "approval_decision_reference_not_allowed",
            "error",
            "approval_decision_reference must be null/empty while blocked and unadmitted.",
            {"actual": approval_decision_reference},
        )

    if final_recommendation != EXPECTED_FINAL_RECOMMENDATION:
        add_finding(
            findings,
            "final_recommendation_not_do_not_request_approval_yet",
            "error",
            "final_recommendation must be do_not_request_approval_yet.",
            {"actual": final_recommendation},
        )

    for required_source_field in REQUIRED_SOURCE_REFERENCE_FIELDS:
        if required_source_field not in source_artifacts:
            add_finding(
                findings,
                "source_artifacts_missing_required_reference",
                "error",
                "source_artifacts is missing a required reference field.",
                {"field": required_source_field},
            )

    readiness_summary = str(report.get("readiness_summary", "")).strip()
    structural_completeness_summary = str(
        report.get("structural_completeness_summary", "")
    ).strip()
    if not readiness_summary:
        add_finding(
            findings,
            "readiness_summary_missing_or_empty",
            "error",
            "readiness_summary must be present and non-empty.",
        )
    else:
        lower_summary = readiness_summary.lower()
        if "structural" not in lower_summary and "complete" not in lower_summary:
            add_finding(
                findings,
                "readiness_summary_missing_structural_completeness_reference",
                "error",
                "readiness_summary must reference packet structural completeness context.",
            )
        if "not ready" not in lower_summary and "false" not in lower_summary:
            add_finding(
                findings,
                "readiness_summary_missing_not_ready_statement",
                "error",
                "readiness_summary must clearly state approval request readiness is not ready/false.",
            )
    if not structural_completeness_summary:
        add_finding(
            findings,
            "structural_completeness_summary_missing_or_empty",
            "error",
            "structural_completeness_summary must be present and non-empty.",
        )

    request_readiness_blockers = _check_non_empty_string_list(
        report,
        "request_readiness_blockers",
        findings,
        "request_readiness_blockers_missing_or_empty",
        "request_readiness_blockers must be present and non-empty.",
    )
    approval_blockers = _check_non_empty_string_list(
        report,
        "approval_blockers",
        findings,
        "approval_blockers_missing_or_empty",
        "approval_blockers must be present and non-empty.",
    )
    execution_blockers = _check_non_empty_string_list(
        report,
        "execution_blockers",
        findings,
        "execution_blockers_missing_or_empty",
        "execution_blockers must be present and non-empty.",
    )
    receipt_blockers = _check_non_empty_string_list(
        report,
        "receipt_blockers",
        findings,
        "receipt_blockers_missing_or_empty",
        "receipt_blockers must be present and non-empty.",
    )
    publication_blockers = _check_non_empty_string_list(
        report,
        "publication_blockers",
        findings,
        "publication_blockers_missing_or_empty",
        "publication_blockers must be present and non-empty.",
    )
    production_readiness_blockers = _check_non_empty_string_list(
        report,
        "production_readiness_blockers",
        findings,
        "production_readiness_blockers_missing_or_empty",
        "production_readiness_blockers must be present and non-empty.",
    )
    required_before_requesting_approval = _check_non_empty_string_list(
        report,
        "required_before_requesting_approval",
        findings,
        "required_before_requesting_approval_missing_or_empty",
        "required_before_requesting_approval must be present and non-empty.",
    )
    required_validation_commands = _check_non_empty_string_list(
        report,
        "required_validation_commands",
        findings,
        "required_validation_commands_missing_or_empty",
        "required_validation_commands must be present and non-empty.",
    )

    _check_required_token_set(
        request_readiness_blockers,
        REQUIRED_REQUEST_READINESS_BLOCKERS,
        findings,
        "request_readiness_blockers",
    )
    _check_required_token_set(
        approval_blockers,
        REQUIRED_APPROVAL_BLOCKERS,
        findings,
        "approval_blockers",
    )
    _check_required_token_set(
        execution_blockers,
        REQUIRED_EXECUTION_BLOCKERS,
        findings,
        "execution_blockers",
    )
    _check_required_token_set(
        receipt_blockers,
        REQUIRED_RECEIPT_BLOCKERS,
        findings,
        "receipt_blockers",
    )
    _check_required_token_set(
        publication_blockers,
        REQUIRED_PUBLICATION_BLOCKERS,
        findings,
        "publication_blockers",
    )
    _check_required_token_set(
        production_readiness_blockers,
        REQUIRED_PRODUCTION_READINESS_BLOCKERS,
        findings,
        "production_readiness_blockers",
    )

    required_validation_command_set = {
        item.strip() for item in required_validation_commands if item.strip()
    }
    for command_path, finding_id in REQUIRED_VALIDATION_COMMANDS.items():
        if command_path not in required_validation_command_set:
            add_finding(
                findings,
                finding_id,
                "error",
                "required_validation_commands is missing a required command entry.",
                {"command": command_path},
            )

    if not required_before_requesting_approval:
        add_finding(
            findings,
            "required_before_requesting_approval_missing",
            "error",
            "required_before_requesting_approval must remain non-empty.",
        )

    if bool(report.get("unsafe_claims_detected", False)):
        add_finding(
            findings,
            "unsafe_claims_detected_not_allowed",
            "error",
            "unsafe_claims_detected must remain false.",
        )

    safety_notes = as_string_list(report.get("safety_notes"))
    if not safety_notes:
        add_finding(
            findings,
            "safety_notes_missing_or_empty",
            "error",
            "safety_notes must be present and non-empty.",
        )

    _check_forbidden_claim_language(report, findings)

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

    for payload_name, payload_value in (
        ("dry_run_receipt_contract", dry_run_receipt_contract_payload_raw),
        ("blocked_unissued_receipt", dry_run_receipt_blocked_payload_raw),
        ("admission_blockers", admission_blockers_payload_raw),
        ("operator_approval_packet", operator_packet_payload_raw),
        ("operator_approval_packet_completeness", operator_packet_completeness_payload_raw),
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

    severity_set = {str(item.get("severity", "")).strip() for item in findings}
    status = "fail" if "error" in severity_set else "pass"

    report_payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_APPROVAL_REQUEST_READINESS_VALIDATION_v1_REPORT",
        "status": status,
        "release_candidate_publication_dry_run_approval_request_readiness_present": True,
        "release_candidate_publication_dry_run_approval_request_readiness_path": str(
            report_path
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
        "operator_approval_packet_completeness_path": str(
            operator_packet_completeness_path
        ),
        "production_readiness_report_path": str(production_readiness_path),
        "noop_receipt_status_path": str(noop_decision_path),
        "source_artifact_validation_status": source_status_reported,
        "computed_source_artifact_validation_status": source_status_expected,
        "planned_candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "approval_request_readiness_status": readiness_status,
        "admission_status": admission_status,
        "packet_structurally_complete": bool(
            report.get("packet_structurally_complete", False)
        ),
        "packet_complete_for_future_review_template": bool(
            report.get("packet_complete_for_future_review_template", False)
        ),
        "approval_request_ready": bool(report.get("approval_request_ready", False)),
        "operator_approval_granted": bool(report.get("operator_approval_granted", False)),
        "approval_phrase_present": bool(report.get("approval_phrase_present", False)),
        "dry_run_admitted": bool(report.get("dry_run_admitted", False)),
        "dry_run_executed": bool(report.get("dry_run_executed", False)),
        "receipt_issued": bool(report.get("receipt_issued", False)),
        "publication_admitted": bool(report.get("publication_admitted", False)),
        "real_execution_admitted": bool(report.get("real_execution_admitted", False)),
        "production_ready_claimed": bool(report.get("production_ready_claimed", False)),
        "approval_phrase_required": approval_phrase,
        "final_recommendation": final_recommendation,
        "readiness_summary": readiness_summary,
        "structural_completeness_summary": structural_completeness_summary,
        "request_readiness_blockers": request_readiness_blockers,
        "approval_blockers": approval_blockers,
        "execution_blockers": execution_blockers,
        "receipt_blockers": receipt_blockers,
        "publication_blockers": publication_blockers,
        "production_readiness_blockers": production_readiness_blockers,
        "required_before_requesting_approval": required_before_requesting_approval,
        "required_validation_commands": required_validation_commands,
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
