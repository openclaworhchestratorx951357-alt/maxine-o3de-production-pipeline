#!/usr/bin/env python3
"""Validate release-candidate publication dry-run admission blockers v1."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


TARGET_CANDIDATE_ID = "release_candidate_package_publish_dry_run_v1"
TARGET_CANDIDATE_TYPE = "dry_run"
NOOP_CANDIDATE_ID = "release_candidate_package_receipt_noop_v1"
EXPECTED_APPROVAL_PHRASE = (
    "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
)
EXPECTED_CHECKLIST_STATUS = "static_checklist_valid_blocked"
EXPECTED_ROLLUP_STATUS = "static_rollup_valid_blocked"
EXPECTED_DRY_RUN_PLAN_STATUS = "static_plan_valid_blocked"
EXPECTED_RECEIPT_CONTRACT_STATUS = "static_contract_valid_blocked"
EXPECTED_NEXT_SLICE_ID = "candidate_specific_dry_run_planning_v1"
EXPECTED_BLOCKED_RECEIPT_STATUS = "blocked_unissued_contract_only"

REQUIRED_ADMISSION_BLOCKERS = (
    "missing_approval_decision",
    "dry_run_not_admitted",
    "dry_run_not_executed",
    "receipt_not_issued",
    "rollback_cleanup_evidence_missing",
    "publication_surfaces_blocked_by_policy",
)

REQUIRED_PREREQUISITE_VALUES = {
    "candidate_matrix_entry_present": True,
    "preflight_contract_present": True,
    "preflight_proof_package_present": True,
    "readiness_rollup_present": True,
    "dry_run_plan_present": True,
    "dry_run_receipt_contract_present": True,
    "blocked_unissued_receipt_example_present": True,
    "production_readiness_report_present": True,
    "noop_receipt_status_present": True,
    "source_artifact_validations_pass": True,
    "approval_decision_present": False,
    "dry_run_runner_admitted": False,
    "dry_run_executed": False,
    "dry_run_receipt_issued": False,
    "rollback_cleanup_evidence_present": False,
    "publication_surfaces_blocked": True,
    "execution_surfaces_blocked": True,
    "production_ready_claimed": False,
}

DEFAULT_CHECKLIST_REL = Path(
    "examples/execution-admission/release_candidate_package_publish_dry_run_admission_blockers_v1.json"
)
DEFAULT_SCHEMA_REL = Path(
    "schemas/maxine_release_candidate_publication_dry_run_admission_blockers.schema.json"
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

SOURCE_STATUS_KEYS = (
    "candidate_matrix_status",
    "preflight_contracts_status",
    "preflight_proof_packages_status",
    "readiness_rollup_status",
    "dry_run_plan_status",
    "dry_run_receipt_contract_status",
    "blocked_unissued_receipt_status",
    "production_readiness_status",
    "noop_receipt_status",
)

BLOCKER_LIST_KEYS = (
    "admission_blockers",
    "approval_blockers",
    "evidence_blockers",
    "receipt_blockers",
    "rollback_or_cleanup_blockers",
    "publication_blockers",
    "execution_blockers",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate release-candidate publication dry-run admission blockers v1."
    )
    parser.add_argument(
        "checklist_path",
        nargs="?",
        default=str(DEFAULT_CHECKLIST_REL),
        help="Path to release-candidate publication dry-run admission blockers JSON.",
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
    output: List[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            output.append(text)
    return output


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


def _list_has_token(items: List[str], token: str) -> bool:
    token_lower = token.lower()
    return any(token_lower in str(item).lower() for item in items)


def _check_non_empty_string_list(
    checklist: Dict[str, Any],
    key: str,
    findings: List[Dict[str, Any]],
) -> List[str]:
    values = as_string_list(checklist.get(key))
    if not values:
        add_finding(
            findings,
            "blocker_list_missing_or_empty",
            "error",
            "Checklist blocker list must be present and non-empty.",
            {"field": key},
        )
    return values


def _check_forbidden_claim_language(
    payload: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    checks = (
        ("publish allowed", "checklist_allows_publish"),
        ("spawn allowed", "checklist_allows_spawn"),
        ("production path writes allowed", "checklist_allows_production_path_writes"),
        ("engine path writes allowed", "checklist_allows_engine_path_writes"),
        ("cache/live db access allowed", "checklist_allows_cache_live_db_access"),
        ("cache live db access allowed", "checklist_allows_cache_live_db_access"),
        (
            "authoritative source uuid claims allowed",
            "checklist_allows_authoritative_source_uuid_claims",
        ),
        (
            "authoritative asset id claims allowed",
            "checklist_allows_authoritative_asset_id_claims",
        ),
        (
            "authoritative product id claims allowed",
            "checklist_allows_authoritative_product_id_claims",
        ),
    )
    for needle, finding_id in checks:
        if needle in text:
            add_finding(
                findings,
                finding_id,
                "error",
                "Checklist text must not allow blocked publication/execution surfaces.",
                {"needle": needle},
            )


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    checklist_path = (
        Path(args.checklist_path).resolve()
        if Path(args.checklist_path).is_absolute()
        else (repo_root / args.checklist_path).resolve()
    )
    schema_path = (repo_root / DEFAULT_SCHEMA_REL).resolve()

    if not checklist_path.exists():
        print(
            json.dumps(
                {"status": "fail", "error": f"admission blockers checklist not found: {checklist_path}"},
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

    checklist = load_json(checklist_path)
    schema = load_json(schema_path)
    findings: List[Dict[str, Any]] = []

    ok, schema_errors = validate_schema(checklist, schema)
    if not ok:
        for message in schema_errors:
            add_finding(
                findings,
                "schema_validation_error",
                "error",
                "Admission blockers checklist failed schema validation.",
                {"error": message},
            )

    source_artifacts = (
        checklist.get("source_artifacts")
        if isinstance(checklist.get("source_artifacts"), dict)
        else {}
    )

    matrix_path = resolve_ref_path(
        repo_root,
        str(source_artifacts.get("candidate_matrix_ref", "")).strip()
        or str(DEFAULT_MATRIX_REL),
    )
    preflight_path = resolve_ref_path(
        repo_root,
        str(source_artifacts.get("preflight_contracts_ref", "")).strip()
        or str(DEFAULT_PREFLIGHT_REL),
    )
    preflight_proof_path = resolve_ref_path(
        repo_root,
        str(source_artifacts.get("preflight_proof_packages_ref", "")).strip()
        or str(DEFAULT_PREFLIGHT_PROOF_REL),
    )
    rollup_path = resolve_ref_path(
        repo_root,
        str(source_artifacts.get("readiness_rollup_ref", "")).strip()
        or str(DEFAULT_ROLLUP_REL),
    )
    dry_run_plan_path = resolve_ref_path(
        repo_root,
        str(source_artifacts.get("dry_run_plan_ref", "")).strip()
        or str(DEFAULT_DRY_RUN_PLAN_REL),
    )
    dry_run_receipt_contract_path = resolve_ref_path(
        repo_root,
        str(source_artifacts.get("dry_run_receipt_contract_ref", "")).strip()
        or str(DEFAULT_DRY_RUN_RECEIPT_CONTRACT_REL),
    )
    dry_run_receipt_blocked_path = resolve_ref_path(
        repo_root,
        str(source_artifacts.get("blocked_unissued_receipt_ref", "")).strip()
        or str(DEFAULT_DRY_RUN_RECEIPT_BLOCKED_REL),
    )
    production_readiness_path = resolve_ref_path(
        repo_root,
        str(source_artifacts.get("production_readiness_report_ref", "")).strip()
        or str(DEFAULT_PRODUCTION_READINESS_REL),
    )
    noop_decision_path = resolve_ref_path(
        repo_root,
        str(source_artifacts.get("noop_receipt_status_ref", "")).strip()
        or str(DEFAULT_NOOP_DECISION_REL),
    )

    for label, path in (
        ("candidate_matrix", matrix_path),
        ("preflight_contracts", preflight_path),
        ("preflight_proof_packages", preflight_proof_path),
        ("readiness_rollup", rollup_path),
        ("dry_run_plan", dry_run_plan_path),
        ("dry_run_receipt_contract", dry_run_receipt_contract_path),
        ("blocked_unissued_receipt", dry_run_receipt_blocked_path),
        ("production_readiness_report", production_readiness_path),
        ("noop_receipt_status", noop_decision_path),
    ):
        if not path.exists():
            add_finding(
                findings,
                "source_artifact_missing",
                "error",
                "Source artifact reference is missing.",
                {"artifact": label, "path": str(path)},
            )

    matrix_payload = load_json(matrix_path) if matrix_path.exists() else {}
    preflight_payload = load_json(preflight_path) if preflight_path.exists() else {}
    preflight_proof_payload = load_json(preflight_proof_path) if preflight_proof_path.exists() else {}
    rollup_payload = load_json(rollup_path) if rollup_path.exists() else {}
    dry_run_plan_payload = load_json(dry_run_plan_path) if dry_run_plan_path.exists() else {}
    dry_run_receipt_contract_payload = (
        load_json(dry_run_receipt_contract_path) if dry_run_receipt_contract_path.exists() else {}
    )
    dry_run_receipt_blocked_payload = (
        load_json(dry_run_receipt_blocked_path) if dry_run_receipt_blocked_path.exists() else {}
    )
    production_readiness_payload = (
        load_json(production_readiness_path) if production_readiness_path.exists() else {}
    )
    noop_decision_payload = load_json(noop_decision_path) if noop_decision_path.exists() else {}

    matrix_code, matrix_report, matrix_parse_error = run_validator(
        repo_root,
        MATRIX_VALIDATOR_REL,
        [str(matrix_path)],
    )
    if matrix_report is None:
        add_finding(
            findings,
            "candidate_matrix_validator_output_invalid",
            "error",
            "Candidate matrix validator did not return parseable JSON.",
            {"error": matrix_parse_error or "unknown parse error"},
        )
    elif matrix_code != 0 or str(matrix_report.get("status", "")).strip() != "pass":
        add_finding(
            findings,
            "candidate_matrix_validation_failed",
            "error",
            "Candidate matrix validation must pass.",
            {"return_code": matrix_code, "status": matrix_report.get("status")},
        )

    preflight_code, preflight_report, preflight_parse_error = run_validator(
        repo_root,
        PREFLIGHT_VALIDATOR_REL,
        [str(preflight_path), "--matrix-path", str(matrix_path)],
    )
    if preflight_report is None:
        add_finding(
            findings,
            "preflight_contracts_validator_output_invalid",
            "error",
            "Preflight contracts validator did not return parseable JSON.",
            {"error": preflight_parse_error or "unknown parse error"},
        )
    elif preflight_code != 0 or str(preflight_report.get("status", "")).strip() != "pass":
        add_finding(
            findings,
            "preflight_contracts_validation_failed",
            "error",
            "Preflight contracts validation must pass.",
            {"return_code": preflight_code, "status": preflight_report.get("status")},
        )

    preflight_proof_code, preflight_proof_report, preflight_proof_parse_error = run_validator(
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
    if preflight_proof_report is None:
        add_finding(
            findings,
            "preflight_proof_packages_validator_output_invalid",
            "error",
            "Preflight proof packages validator did not return parseable JSON.",
            {"error": preflight_proof_parse_error or "unknown parse error"},
        )
    elif preflight_proof_code != 0 or str(preflight_proof_report.get("status", "")).strip() != "pass":
        add_finding(
            findings,
            "preflight_proof_packages_validation_failed",
            "error",
            "Preflight proof packages validation must pass.",
            {"return_code": preflight_proof_code, "status": preflight_proof_report.get("status")},
        )

    rollup_code, rollup_report, rollup_parse_error = run_validator(
        repo_root,
        READINESS_ROLLUP_VALIDATOR_REL,
        [str(rollup_path)],
    )
    if rollup_report is None:
        add_finding(
            findings,
            "readiness_rollup_validator_output_invalid",
            "error",
            "Readiness rollup validator did not return parseable JSON.",
            {"error": rollup_parse_error or "unknown parse error"},
        )
    elif rollup_code != 0 or str(rollup_report.get("status", "")).strip() != "pass":
        add_finding(
            findings,
            "readiness_rollup_validation_failed",
            "error",
            "Readiness rollup validation must pass.",
            {"return_code": rollup_code, "status": rollup_report.get("status")},
        )

    dry_run_plan_code, dry_run_plan_report, dry_run_plan_parse_error = run_validator(
        repo_root,
        DRY_RUN_PLAN_VALIDATOR_REL,
        [str(dry_run_plan_path)],
    )
    if dry_run_plan_report is None:
        add_finding(
            findings,
            "dry_run_plan_validator_output_invalid",
            "error",
            "Dry-run plan validator did not return parseable JSON.",
            {"error": dry_run_plan_parse_error or "unknown parse error"},
        )
    elif dry_run_plan_code != 0 or str(dry_run_plan_report.get("status", "")).strip() != "pass":
        add_finding(
            findings,
            "dry_run_plan_validation_failed",
            "error",
            "Dry-run plan validation must pass.",
            {"return_code": dry_run_plan_code, "status": dry_run_plan_report.get("status")},
        )

    dry_run_receipt_contract_code, dry_run_receipt_contract_report, dry_run_receipt_contract_parse_error = run_validator(
        repo_root,
        DRY_RUN_RECEIPT_VALIDATOR_REL,
        [str(dry_run_receipt_contract_path)],
    )
    if dry_run_receipt_contract_report is None:
        add_finding(
            findings,
            "dry_run_receipt_contract_validator_output_invalid",
            "error",
            "Dry-run receipt contract validator did not return parseable JSON.",
            {"error": dry_run_receipt_contract_parse_error or "unknown parse error"},
        )
    elif (
        dry_run_receipt_contract_code != 0
        or str(dry_run_receipt_contract_report.get("status", "")).strip() != "pass"
    ):
        add_finding(
            findings,
            "dry_run_receipt_contract_validation_failed",
            "error",
            "Dry-run receipt contract validation must pass.",
            {
                "return_code": dry_run_receipt_contract_code,
                "status": dry_run_receipt_contract_report.get("status"),
            },
        )

    blocked_receipt_code, blocked_receipt_report, blocked_receipt_parse_error = run_validator(
        repo_root,
        DRY_RUN_RECEIPT_VALIDATOR_REL,
        [str(dry_run_receipt_blocked_path)],
    )
    if blocked_receipt_report is None:
        add_finding(
            findings,
            "blocked_unissued_receipt_validator_output_invalid",
            "error",
            "Blocked/unissued dry-run receipt validator did not return parseable JSON.",
            {"error": blocked_receipt_parse_error or "unknown parse error"},
        )
    elif blocked_receipt_code != 0 or str(blocked_receipt_report.get("status", "")).strip() != "pass":
        add_finding(
            findings,
            "blocked_unissued_receipt_validation_failed",
            "error",
            "Blocked/unissued dry-run receipt validation must pass.",
            {"return_code": blocked_receipt_code, "status": blocked_receipt_report.get("status")},
        )

    source_status_expected: Dict[str, str] = {
        "candidate_matrix_status": (
            "pass"
            if matrix_report is not None and matrix_code == 0 and matrix_report.get("status") == "pass"
            else "fail"
        ),
        "preflight_contracts_status": (
            "pass"
            if preflight_report is not None and preflight_code == 0 and preflight_report.get("status") == "pass"
            else "fail"
        ),
        "preflight_proof_packages_status": (
            "pass"
            if preflight_proof_report is not None
            and preflight_proof_code == 0
            and preflight_proof_report.get("status") == "pass"
            else "fail"
        ),
        "readiness_rollup_status": (
            "pass"
            if rollup_report is not None and rollup_code == 0 and rollup_report.get("status") == "pass"
            else "fail"
        ),
        "dry_run_plan_status": (
            "pass"
            if dry_run_plan_report is not None
            and dry_run_plan_code == 0
            and dry_run_plan_report.get("status") == "pass"
            else "fail"
        ),
        "dry_run_receipt_contract_status": (
            "pass"
            if dry_run_receipt_contract_report is not None
            and dry_run_receipt_contract_code == 0
            and dry_run_receipt_contract_report.get("status") == "pass"
            else "fail"
        ),
        "blocked_unissued_receipt_status": (
            "pass"
            if blocked_receipt_report is not None
            and blocked_receipt_code == 0
            and blocked_receipt_report.get("status") == "pass"
            else "fail"
        ),
        "production_readiness_status": _validate_production_readiness_report(
            production_readiness_payload, findings
        ),
        "noop_receipt_status": _validate_noop_decision_record(noop_decision_payload, findings),
    }

    reported_source_status = (
        checklist.get("source_artifact_validation_status")
        if isinstance(checklist.get("source_artifact_validation_status"), dict)
        else {}
    )
    for key in SOURCE_STATUS_KEYS:
        if str(reported_source_status.get(key, "")).strip() != source_status_expected[key]:
            add_finding(
                findings,
                "source_artifact_validation_status_mismatch",
                "error",
                "source_artifact_validation_status does not match computed status.",
                {
                    "field": key,
                    "expected": source_status_expected[key],
                    "actual": reported_source_status.get(key),
                },
            )

    checklist_candidate_id = str(checklist.get("candidate_id", "")).strip()
    if checklist_candidate_id != TARGET_CANDIDATE_ID:
        add_finding(
            findings,
            "candidate_id_mismatch",
            "error",
            "candidate_id must match release_candidate_package_publish_dry_run_v1.",
            {"actual": checklist_candidate_id},
        )
    checklist_candidate_type = str(checklist.get("candidate_type", "")).strip()
    if checklist_candidate_type != TARGET_CANDIDATE_TYPE:
        add_finding(
            findings,
            "candidate_type_mismatch",
            "error",
            "candidate_type must be dry_run.",
            {"actual": checklist_candidate_type},
        )

    checklist_status = str(checklist.get("checklist_status", "")).strip()
    if checklist_status != EXPECTED_CHECKLIST_STATUS:
        add_finding(
            findings,
            "checklist_status_not_static_checklist_valid_blocked",
            "error",
            "checklist_status must be static_checklist_valid_blocked.",
            {"actual": checklist_status},
        )
    admission_status = str(checklist.get("admission_status", "")).strip()
    if admission_status != "unadmitted":
        add_finding(
            findings,
            "admission_status_not_unadmitted",
            "error",
            "admission_status must remain unadmitted.",
            {"actual": admission_status},
        )

    approval_review_ready = checklist.get("approval_review_ready")
    if approval_review_ready is True or str(approval_review_ready).strip().lower() == "true":
        add_finding(
            findings,
            "approval_review_ready_not_allowed",
            "error",
            "approval_review_ready must remain false or blocked.",
            {"actual": approval_review_ready},
        )
    if bool(checklist.get("ready_to_request_approval", False)):
        add_finding(
            findings,
            "ready_to_request_approval_not_allowed",
            "error",
            "ready_to_request_approval must remain false.",
        )

    for field, finding_id in (
        ("dry_run_admitted", "dry_run_admitted_not_allowed"),
        ("receipt_issued", "receipt_issued_not_allowed"),
        ("publication_admitted", "publication_admitted_not_allowed"),
        ("real_execution_admitted", "real_execution_admitted_not_allowed"),
        ("production_ready_claimed", "production_ready_claim_not_allowed"),
    ):
        if checklist.get(field) is not False:
            add_finding(
                findings,
                finding_id,
                "error",
                "Checklist admission/production-ready flags must remain false.",
                {"field": field, "actual": checklist.get(field)},
            )

    approval_phrase = str(checklist.get("approval_phrase_required", "")).strip()
    if approval_phrase != EXPECTED_APPROVAL_PHRASE:
        add_finding(
            findings,
            "approval_phrase_required_mismatch",
            "error",
            "approval_phrase_required must match exact candidate-specific phrase.",
            {"actual": approval_phrase},
        )

    approval_decision_reference = checklist.get("approval_decision_reference")
    if isinstance(approval_decision_reference, str):
        text = approval_decision_reference.strip()
        if text:
            add_finding(
                findings,
                "approval_decision_reference_not_allowed",
                "error",
                "approval_decision_reference must be null/empty while candidate is unadmitted.",
                {"actual": approval_decision_reference},
            )
    elif approval_decision_reference not in (None, ""):
        add_finding(
            findings,
            "approval_decision_reference_not_allowed",
            "error",
            "approval_decision_reference must be null/empty while candidate is unadmitted.",
            {"actual": approval_decision_reference},
        )

    prerequisite_checklist = (
        checklist.get("prerequisite_checklist")
        if isinstance(checklist.get("prerequisite_checklist"), dict)
        else {}
    )
    for key, expected in REQUIRED_PREREQUISITE_VALUES.items():
        if key not in prerequisite_checklist:
            add_finding(
                findings,
                "prerequisite_checklist_missing_key",
                "error",
                "prerequisite_checklist is missing required key.",
                {"key": key},
            )
            continue
        actual = prerequisite_checklist.get(key)
        if actual is not expected:
            add_finding(
                findings,
                "prerequisite_checklist_value_mismatch",
                "error",
                "prerequisite_checklist value does not match blocked baseline posture.",
                {"key": key, "expected": expected, "actual": actual},
            )

    blocker_values: Dict[str, List[str]] = {}
    for key in BLOCKER_LIST_KEYS:
        blocker_values[key] = _check_non_empty_string_list(checklist, key, findings)

    admission_blockers = blocker_values.get("admission_blockers", [])
    for token in REQUIRED_ADMISSION_BLOCKERS:
        if token not in admission_blockers:
            add_finding(
                findings,
                "admission_blockers_missing_required_token",
                "error",
                "admission_blockers is missing required blocker token.",
                {"token": token},
            )

    if bool(checklist.get("unsafe_claims_detected", False)):
        add_finding(
            findings,
            "unsafe_claims_detected_not_allowed",
            "error",
            "unsafe_claims_detected must remain false.",
        )

    _check_forbidden_claim_language(checklist, findings)

    matrix_map = _candidate_map(matrix_payload, "candidates")
    preflight_map = _candidate_map(preflight_payload, "contracts")
    preflight_proof_map = _candidate_map(preflight_proof_payload, "proof_packages")
    rollup_map = _candidate_map(rollup_payload, "candidate_rollups")

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
                "Candidate type must match candidate matrix.",
                {"actual": matrix_entry.get("candidate_type")},
            )
        if str(matrix_entry.get("current_status", "")).strip() == "admitted":
            add_finding(
                findings,
                "dry_run_admitted_not_allowed",
                "error",
                "Target dry-run candidate must remain unadmitted in candidate matrix.",
            )

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
                "Candidate type must match preflight contracts.",
                {"actual": preflight_entry.get("candidate_type")},
            )
        if str(preflight_entry.get("admission_status", "")).strip() != "unadmitted":
            add_finding(
                findings,
                "admission_status_mismatch_with_preflight_contracts",
                "error",
                "Target dry-run candidate must remain unadmitted in preflight contracts.",
                {"actual": preflight_entry.get("admission_status")},
            )

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
                "Candidate type must match preflight proof packages.",
                {"actual": preflight_proof_entry.get("candidate_type")},
            )
        if str(preflight_proof_entry.get("admission_status", "")).strip() != "unadmitted":
            add_finding(
                findings,
                "admission_status_mismatch_with_preflight_proof_packages",
                "error",
                "Target dry-run candidate must remain unadmitted in preflight proof packages.",
                {"actual": preflight_proof_entry.get("admission_status")},
            )
        if bool(preflight_proof_entry.get("preflight_passed", False)):
            add_finding(
                findings,
                "dry_run_preflight_passed_not_allowed",
                "error",
                "Target dry-run candidate must keep preflight_passed=false in preflight proof packages.",
            )

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
                "Candidate type must match readiness rollup.",
                {"actual": rollup_entry.get("candidate_type")},
            )
        if str(rollup_entry.get("admission_status", "")).strip() != "unadmitted":
            add_finding(
                findings,
                "admission_status_mismatch_with_readiness_rollup",
                "error",
                "Target dry-run candidate must remain unadmitted in readiness rollup.",
                {"actual": rollup_entry.get("admission_status")},
            )
        if bool(rollup_entry.get("preflight_passed", False)):
            add_finding(
                findings,
                "dry_run_preflight_passed_not_allowed",
                "error",
                "Target dry-run candidate must keep preflight_passed=false in readiness rollup.",
            )

    if str(rollup_payload.get("overall_readiness_rollup_status", "")).strip() != EXPECTED_ROLLUP_STATUS:
        add_finding(
            findings,
            "readiness_rollup_status_not_expected",
            "error",
            "Referenced readiness rollup must keep overall_readiness_rollup_status=static_rollup_valid_blocked.",
            {"actual": rollup_payload.get("overall_readiness_rollup_status")},
        )
    blocked_dry_run_ids = set(as_string_list(rollup_payload.get("blocked_dry_run_candidate_ids", [])))
    if TARGET_CANDIDATE_ID not in blocked_dry_run_ids:
        add_finding(
            findings,
            "dry_run_candidate_missing_from_blocked_list",
            "error",
            "Readiness rollup must include target candidate in blocked_dry_run_candidate_ids.",
        )

    next_slice = (
        rollup_payload.get("safest_next_preparation_slice")
        if isinstance(rollup_payload.get("safest_next_preparation_slice"), dict)
        else {}
    )
    if str(next_slice.get("slice_id", "")).strip() != EXPECTED_NEXT_SLICE_ID:
        add_finding(
            findings,
            "readiness_rollup_safest_next_slice_id_mismatch",
            "error",
            "Readiness rollup safest next slice id must remain candidate_specific_dry_run_planning_v1.",
            {"actual": next_slice.get("slice_id")},
        )
    if str(next_slice.get("candidate_id", "")).strip() != TARGET_CANDIDATE_ID:
        add_finding(
            findings,
            "readiness_rollup_safest_next_candidate_mismatch",
            "error",
            "Readiness rollup safest next candidate must be release_candidate_package_publish_dry_run_v1.",
            {"actual": next_slice.get("candidate_id")},
        )

    if str(dry_run_plan_payload.get("plan_status", "")).strip() != EXPECTED_DRY_RUN_PLAN_STATUS:
        add_finding(
            findings,
            "dry_run_plan_status_not_expected",
            "error",
            "Referenced dry-run plan must keep plan_status=static_plan_valid_blocked.",
            {"actual": dry_run_plan_payload.get("plan_status")},
        )
    if str(dry_run_plan_payload.get("candidate_id", "")).strip() != TARGET_CANDIDATE_ID:
        add_finding(
            findings,
            "dry_run_plan_candidate_id_mismatch",
            "error",
            "Referenced dry-run plan candidate_id must match target candidate.",
            {"actual": dry_run_plan_payload.get("candidate_id")},
        )
    if str(dry_run_plan_payload.get("candidate_type", "")).strip() != TARGET_CANDIDATE_TYPE:
        add_finding(
            findings,
            "dry_run_plan_candidate_type_mismatch",
            "error",
            "Referenced dry-run plan candidate_type must be dry_run.",
            {"actual": dry_run_plan_payload.get("candidate_type")},
        )
    if str(dry_run_plan_payload.get("admission_status", "")).strip() != "unadmitted":
        add_finding(
            findings,
            "dry_run_plan_admission_status_not_unadmitted",
            "error",
            "Referenced dry-run plan admission_status must remain unadmitted.",
            {"actual": dry_run_plan_payload.get("admission_status")},
        )
    for field in (
        "dry_run_admitted",
        "publication_admitted",
        "real_execution_admitted",
        "production_ready_claimed",
    ):
        if dry_run_plan_payload.get(field) is not False:
            add_finding(
                findings,
                "dry_run_plan_admitted_or_ready_flag_not_false",
                "error",
                "Referenced dry-run plan admission/ready flags must remain false.",
                {"field": field, "actual": dry_run_plan_payload.get(field)},
            )

    if str(dry_run_receipt_contract_payload.get("receipt_contract_status", "")).strip() != EXPECTED_RECEIPT_CONTRACT_STATUS:
        add_finding(
            findings,
            "dry_run_receipt_contract_status_not_expected",
            "error",
            "Referenced dry-run receipt contract must keep receipt_contract_status=static_contract_valid_blocked.",
            {"actual": dry_run_receipt_contract_payload.get("receipt_contract_status")},
        )
    for payload_name, receipt_payload in (
        ("dry_run_receipt_contract", dry_run_receipt_contract_payload),
        ("blocked_unissued_receipt", dry_run_receipt_blocked_payload),
    ):
        if str(receipt_payload.get("candidate_id", "")).strip() != TARGET_CANDIDATE_ID:
            add_finding(
                findings,
                "dry_run_receipt_candidate_id_mismatch",
                "error",
                "Dry-run receipt artifacts must target release_candidate_package_publish_dry_run_v1.",
                {"artifact": payload_name, "actual": receipt_payload.get("candidate_id")},
            )
        if str(receipt_payload.get("candidate_type", "")).strip() != TARGET_CANDIDATE_TYPE:
            add_finding(
                findings,
                "dry_run_receipt_candidate_type_mismatch",
                "error",
                "Dry-run receipt artifacts must keep candidate_type=dry_run.",
                {"artifact": payload_name, "actual": receipt_payload.get("candidate_type")},
            )
        for field in (
            "receipt_issued",
            "dry_run_admitted",
            "publication_admitted",
            "real_execution_admitted",
            "production_ready_claimed",
        ):
            if receipt_payload.get(field) is not False:
                add_finding(
                    findings,
                    "dry_run_receipt_admission_flag_not_false",
                    "error",
                    "Dry-run receipt artifacts must keep blocked/unadmitted posture.",
                    {"artifact": payload_name, "field": field, "actual": receipt_payload.get(field)},
                )

    if str(dry_run_receipt_blocked_payload.get("receipt_status", "")).strip() != EXPECTED_BLOCKED_RECEIPT_STATUS:
        add_finding(
            findings,
            "blocked_unissued_receipt_status_mismatch",
            "error",
            "Blocked/unissued receipt example must keep receipt_status=blocked_unissued_contract_only.",
            {"actual": dry_run_receipt_blocked_payload.get("receipt_status")},
        )

    severity_set = {str(item.get("severity", "")).strip() for item in findings}
    status = "fail" if "error" in severity_set else "pass"

    report_payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_ADMISSION_BLOCKERS_VALIDATION_v1_REPORT",
        "status": status,
        "release_candidate_publication_dry_run_admission_blockers_present": True,
        "release_candidate_publication_dry_run_admission_blockers_path": str(checklist_path),
        "candidate_matrix_path": str(matrix_path),
        "preflight_contracts_path": str(preflight_path),
        "preflight_proof_packages_path": str(preflight_proof_path),
        "readiness_rollup_path": str(rollup_path),
        "dry_run_plan_path": str(dry_run_plan_path),
        "dry_run_receipt_contract_path": str(dry_run_receipt_contract_path),
        "blocked_unissued_receipt_path": str(dry_run_receipt_blocked_path),
        "production_readiness_report_path": str(production_readiness_path),
        "noop_receipt_status_path": str(noop_decision_path),
        "source_artifact_validation_status": reported_source_status,
        "computed_source_artifact_validation_status": source_status_expected,
        "planned_candidate_id": checklist_candidate_id,
        "candidate_type": checklist_candidate_type,
        "checklist_status": checklist_status,
        "admission_status": admission_status,
        "approval_review_ready": approval_review_ready,
        "ready_to_request_approval": bool(checklist.get("ready_to_request_approval", False)),
        "dry_run_admitted": bool(checklist.get("dry_run_admitted", False)),
        "receipt_issued": bool(checklist.get("receipt_issued", False)),
        "publication_admitted": bool(checklist.get("publication_admitted", False)),
        "real_execution_admitted": bool(checklist.get("real_execution_admitted", False)),
        "production_ready_claimed": bool(checklist.get("production_ready_claimed", False)),
        "prerequisite_checklist": prerequisite_checklist,
        "admission_blockers": blocker_values.get("admission_blockers", []),
        "approval_blockers": blocker_values.get("approval_blockers", []),
        "evidence_blockers": blocker_values.get("evidence_blockers", []),
        "receipt_blockers": blocker_values.get("receipt_blockers", []),
        "rollback_or_cleanup_blockers": blocker_values.get("rollback_or_cleanup_blockers", []),
        "publication_blockers": blocker_values.get("publication_blockers", []),
        "execution_blockers": blocker_values.get("execution_blockers", []),
        "approval_phrase_required": approval_phrase,
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
