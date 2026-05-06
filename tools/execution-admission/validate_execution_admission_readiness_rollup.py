#!/usr/bin/env python3
"""Validate execution-admission readiness rollup v1."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


NOOP_CANDIDATE_ID = "release_candidate_package_receipt_noop_v1"
REAL_EXECUTION_TYPE = "real_execution"
PUBLICATION_TYPE = "publication"
DRY_RUN_TYPE = "dry_run"
NOOP_TYPE = "no_op_receipt"

DEFAULT_ROLLUP_REL = Path(
    "examples/execution-admission/execution_admission_readiness_rollup_v1.json"
)
DEFAULT_SCHEMA_REL = Path(
    "schemas/maxine_execution_admission_readiness_rollup.schema.json"
)
DEFAULT_PRODUCTION_READINESS_SCHEMA_REL = Path(
    "schemas/maxine_production_readiness_report.schema.json"
)

DEFAULT_MATRIX_REL = Path(
    "examples/execution-admission/execution_admission_candidate_matrix_v1.json"
)
DEFAULT_PREFLIGHT_CONTRACTS_REL = Path(
    "examples/execution-admission/execution_admission_preflight_contracts_v1.json"
)
DEFAULT_PREFLIGHT_PROOF_PACKAGES_REL = Path(
    "examples/execution-admission/execution_admission_preflight_proof_packages_v1.json"
)
DEFAULT_PRODUCTION_READINESS_REL = Path(
    "examples/production-readiness-report/max_biped_v1_production_readiness_report_pass.json"
)
DEFAULT_NOOP_DECISION_REL = Path(
    "examples/execution-admission/release_candidate_package_receipt_noop_execution_admission_decision_approved.json"
)

MATRIX_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_execution_admission_candidate_matrix.py"
)
PREFLIGHT_CONTRACTS_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_execution_admission_preflight_contracts.py"
)
PREFLIGHT_PROOF_PACKAGES_VALIDATOR_REL = Path(
    "tools/execution-admission/validate_execution_admission_preflight_proof_packages.py"
)

NOOP_SATISFIED_PROOF_STATUSES = {"satisfied_no_op_only", "satisfied_non_execution_only"}
REAL_OR_PUBLICATION_FORBIDDEN_STATUSES = NOOP_SATISFIED_PROOF_STATUSES

EXPECTED_ROLLUP_STATUS = "static_rollup_valid_blocked"
EXPECTED_APPROVAL_PHRASE_FORMAT = "APPROVE EXECUTION ADMISSION <candidate_id>"
EXPECTED_NEXT_SLICE_ID = "candidate_specific_dry_run_planning_v1"
EXPECTED_NEXT_SLICE_CANDIDATE_ID = "release_candidate_package_publish_dry_run_v1"

PRODUCTION_READY_TERMS = {"production_ready", "real_execution_admitted", "publication_admitted"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate execution-admission readiness rollup v1."
    )
    parser.add_argument(
        "rollup_path",
        nargs="?",
        default=str(DEFAULT_ROLLUP_REL),
        help="Path to execution-admission readiness rollup JSON.",
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


def resolve_ref_path(repo_root: Path, raw_path: str) -> Path:
    path = Path(str(raw_path).strip())
    if path.is_absolute():
        return path.resolve()
    return (repo_root / path).resolve()


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
        return proc.returncode, None, proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, payload, None


def expected_phrase(candidate_id: str) -> str:
    return f"APPROVE EXECUTION ADMISSION {candidate_id}"


def matrix_status_to_admission(candidate_id: str, candidate_type: str, current_status: str) -> str:
    if candidate_id == NOOP_CANDIDATE_ID and current_status == "admitted":
        return "admitted_no_op_only"
    if current_status != "admitted":
        return "unadmitted"
    if candidate_type == REAL_EXECUTION_TYPE:
        return "admitted_real_execution"
    if candidate_type == PUBLICATION_TYPE:
        return "admitted_publication"
    return "unadmitted"


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
            "No-op decision record decision_state must be approved.",
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
    approval_phrase = str(approval.get("approval_phrase_received", "")).strip()
    if approval_phrase != expected_phrase(NOOP_CANDIDATE_ID):
        add_finding(
            findings,
            "noop_decision_record_approval_phrase_mismatch",
            "error",
            "No-op decision record approval phrase must match approved no-op candidate.",
            {
                "expected": expected_phrase(NOOP_CANDIDATE_ID),
                "actual": approval_phrase,
            },
        )
        status = "fail"

    return status


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

    if bool(payload.get("production_ready_claimed", False)):
        add_finding(
            findings,
            "production_ready_claim_not_allowed",
            "error",
            "Referenced production readiness report must not claim production_ready.",
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

    admitted_noop = sorted(
        set(as_string_list(payload.get("admitted_noop_receipt_candidate_ids", [])))
    )
    admitted_real = sorted(
        set(as_string_list(payload.get("admitted_real_execution_candidate_ids", [])))
    )
    admitted_publication = sorted(
        set(as_string_list(payload.get("admitted_publication_candidate_ids", [])))
    )

    if admitted_noop != [NOOP_CANDIDATE_ID]:
        add_finding(
            findings,
            "production_readiness_admitted_noop_mismatch",
            "error",
            "Referenced production readiness report must keep admitted_noop_receipt_candidate_ids limited to release_candidate_package_receipt_noop_v1.",
            {"actual": admitted_noop},
        )
        status = "fail"
    if admitted_real:
        add_finding(
            findings,
            "production_readiness_admitted_real_execution_not_allowed",
            "error",
            "Referenced production readiness report must keep admitted_real_execution_candidate_ids empty.",
            {"actual": admitted_real},
        )
        status = "fail"
    if admitted_publication:
        add_finding(
            findings,
            "production_readiness_admitted_publication_not_allowed",
            "error",
            "Referenced production readiness report must keep admitted_publication_candidate_ids empty.",
            {"actual": admitted_publication},
        )
        status = "fail"
    return status


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    rollup_path = (
        Path(args.rollup_path).resolve()
        if Path(args.rollup_path).is_absolute()
        else (repo_root / args.rollup_path).resolve()
    )
    schema_path = (repo_root / DEFAULT_SCHEMA_REL).resolve()
    production_readiness_schema_path = (
        repo_root / DEFAULT_PRODUCTION_READINESS_SCHEMA_REL
    ).resolve()

    if not rollup_path.exists():
        print(
            json.dumps(
                {"status": "fail", "error": f"readiness rollup not found: {rollup_path}"},
                indent=2,
            )
        )
        return 2
    if not schema_path.exists():
        print(
            json.dumps({"status": "fail", "error": f"schema not found: {schema_path}"}, indent=2)
        )
        return 2

    rollup = load_json(rollup_path)
    schema = load_json(schema_path)
    findings: List[Dict[str, Any]] = []

    ok, schema_errors = validate_schema(rollup, schema)
    if not ok:
        for message in schema_errors:
            add_finding(
                findings,
                "schema_validation_error",
                "error",
                "Readiness rollup failed schema validation.",
                {"error": message},
            )

    source_artifacts = (
        rollup.get("source_artifacts") if isinstance(rollup.get("source_artifacts"), dict) else {}
    )
    raw_matrix_ref = str(source_artifacts.get("candidate_matrix_ref", "")).strip() or str(
        DEFAULT_MATRIX_REL
    )
    raw_preflight_ref = str(source_artifacts.get("preflight_contracts_ref", "")).strip() or str(
        DEFAULT_PREFLIGHT_CONTRACTS_REL
    )
    raw_preflight_proof_ref = str(source_artifacts.get("preflight_proof_packages_ref", "")).strip() or str(
        DEFAULT_PREFLIGHT_PROOF_PACKAGES_REL
    )
    raw_production_readiness_ref = str(
        source_artifacts.get("production_readiness_report_ref", "")
    ).strip() or str(DEFAULT_PRODUCTION_READINESS_REL)
    raw_noop_decision_ref = str(source_artifacts.get("noop_receipt_admission_ref", "")).strip() or str(
        DEFAULT_NOOP_DECISION_REL
    )

    matrix_path = resolve_ref_path(repo_root, raw_matrix_ref)
    preflight_path = resolve_ref_path(repo_root, raw_preflight_ref)
    preflight_proof_path = resolve_ref_path(repo_root, raw_preflight_proof_ref)
    production_readiness_path = resolve_ref_path(repo_root, raw_production_readiness_ref)
    noop_decision_path = resolve_ref_path(repo_root, raw_noop_decision_ref)

    for label, path in (
        ("candidate_matrix", matrix_path),
        ("preflight_contracts", preflight_path),
        ("preflight_proof_packages", preflight_proof_path),
        ("production_readiness_report", production_readiness_path),
        ("noop_receipt_admission", noop_decision_path),
    ):
        if not path.exists():
            add_finding(
                findings,
                "source_artifact_missing",
                "error",
                "Source artifact reference is missing.",
                {"artifact": label, "path": str(path)},
            )

    matrix_payload: Dict[str, Any] = {}
    preflight_payload: Dict[str, Any] = {}
    preflight_proof_payload: Dict[str, Any] = {}
    production_readiness_payload: Dict[str, Any] = {}
    noop_decision_payload: Dict[str, Any] = {}
    matrix_report: Dict[str, Any] | None = None
    preflight_report: Dict[str, Any] | None = None
    preflight_proof_report: Dict[str, Any] | None = None

    if matrix_path.exists():
        matrix_payload = load_json(matrix_path)
    if preflight_path.exists():
        preflight_payload = load_json(preflight_path)
    if preflight_proof_path.exists():
        preflight_proof_payload = load_json(preflight_proof_path)
    if production_readiness_path.exists():
        production_readiness_payload = load_json(production_readiness_path)
    if noop_decision_path.exists():
        noop_decision_payload = load_json(noop_decision_path)

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
            "Candidate matrix validator did not return a parseable JSON payload.",
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
        PREFLIGHT_CONTRACTS_VALIDATOR_REL,
        [str(preflight_path), "--matrix-path", str(matrix_path)],
    )
    if preflight_report is None:
        add_finding(
            findings,
            "preflight_contracts_validator_output_invalid",
            "error",
            "Preflight contracts validator did not return a parseable JSON payload.",
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

    (
        preflight_proof_code,
        preflight_proof_report,
        preflight_proof_parse_error,
    ) = run_validator(
        repo_root,
        PREFLIGHT_PROOF_PACKAGES_VALIDATOR_REL,
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
            "Preflight proof packages validator did not return a parseable JSON payload.",
            {"error": preflight_proof_parse_error or "unknown parse error"},
        )
    elif preflight_proof_code != 0 or str(preflight_proof_report.get("status", "")).strip() != "pass":
        add_finding(
            findings,
            "preflight_proof_packages_validation_failed",
            "error",
            "Preflight proof packages validation must pass.",
            {
                "return_code": preflight_proof_code,
                "status": preflight_proof_report.get("status"),
            },
        )

    production_readiness_local_status = "pass"
    if production_readiness_payload:
        production_readiness_local_status = _validate_production_readiness_report(
            production_readiness_payload, findings
        )
        if production_readiness_schema_path.exists():
            production_readiness_schema = load_json(production_readiness_schema_path)
            schema_ok, schema_errors = validate_schema(
                production_readiness_payload, production_readiness_schema
            )
            if not schema_ok:
                production_readiness_local_status = "fail"
                for message in schema_errors:
                    add_finding(
                        findings,
                        "production_readiness_schema_validation_error",
                        "error",
                        "Referenced production readiness report failed schema validation.",
                        {"error": message},
                    )

    noop_decision_local_status = "pass"
    if noop_decision_payload:
        noop_decision_local_status = _validate_noop_decision_record(
            noop_decision_payload, findings
        )

    source_validation_status_reported = (
        rollup.get("source_artifact_validation_status")
        if isinstance(rollup.get("source_artifact_validation_status"), dict)
        else {}
    )
    source_validation_status_expected: Dict[str, str] = {
        "candidate_matrix_status": str((matrix_report or {}).get("status", "fail")).strip() or "fail",
        "preflight_contracts_status": str((preflight_report or {}).get("status", "fail")).strip() or "fail",
        "preflight_proof_packages_status": str((preflight_proof_report or {}).get("status", "fail")).strip()
        or "fail",
        "production_readiness_status": production_readiness_local_status,
        "noop_receipt_status": noop_decision_local_status,
    }
    for key, expected in source_validation_status_expected.items():
        actual = str(source_validation_status_reported.get(key, "")).strip()
        if actual != expected:
            add_finding(
                findings,
                "source_artifact_validation_status_mismatch",
                "error",
                "source_artifact_validation_status must match referenced artifact validation results.",
                {"field": key, "expected": expected, "actual": actual},
            )

    if str(rollup.get("overall_readiness_rollup_status", "")).strip() != EXPECTED_ROLLUP_STATUS:
        add_finding(
            findings,
            "overall_readiness_rollup_status_invalid",
            "error",
            "overall_readiness_rollup_status must remain static_rollup_valid_blocked in this slice.",
            {"actual": rollup.get("overall_readiness_rollup_status")},
        )

    if bool(rollup.get("production_ready_claimed", False)):
        add_finding(
            findings,
            "production_ready_claim_not_allowed",
            "error",
            "Readiness rollup must keep production_ready_claimed=false.",
        )

    if str(rollup.get("real_execution_admission_status", "")).strip() != "blocked":
        add_finding(
            findings,
            "real_execution_admission_status_not_blocked",
            "error",
            "Readiness rollup must keep real_execution_admission_status=blocked.",
        )
    if str(rollup.get("publication_admission_status", "")).strip() != "blocked":
        add_finding(
            findings,
            "publication_admission_status_not_blocked",
            "error",
            "Readiness rollup must keep publication_admission_status=blocked.",
        )

    if bool(rollup.get("unsafe_claims_detected", False)):
        add_finding(
            findings,
            "unsafe_claims_detected_not_allowed",
            "error",
            "Readiness rollup must keep unsafe_claims_detected=false.",
        )

    approval_phrase_required = str(rollup.get("approval_phrase_required", "")).strip()
    if approval_phrase_required != EXPECTED_APPROVAL_PHRASE_FORMAT:
        add_finding(
            findings,
            "approval_phrase_format_mismatch",
            "error",
            "approval_phrase_required must remain APPROVE EXECUTION ADMISSION <candidate_id> format.",
            {"actual": approval_phrase_required},
        )

    admitted_noop_ids = sorted(
        set(as_string_list(rollup.get("admitted_noop_receipt_candidate_ids", [])))
    )
    admitted_real_ids = sorted(
        set(as_string_list(rollup.get("admitted_real_execution_candidate_ids", [])))
    )
    admitted_publication_ids = sorted(
        set(as_string_list(rollup.get("admitted_publication_candidate_ids", [])))
    )
    blocked_real_ids = sorted(
        set(as_string_list(rollup.get("blocked_real_execution_candidate_ids", [])))
    )
    blocked_publication_ids = sorted(
        set(as_string_list(rollup.get("blocked_publication_candidate_ids", [])))
    )
    blocked_dry_run_ids = sorted(
        set(as_string_list(rollup.get("blocked_dry_run_candidate_ids", [])))
    )
    real_preflight_passed_ids = sorted(
        set(as_string_list(rollup.get("real_execution_preflight_passed_candidate_ids", [])))
    )
    publication_preflight_passed_ids = sorted(
        set(as_string_list(rollup.get("publication_preflight_passed_candidate_ids", [])))
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
            "admitted_real_execution_candidate_ids_not_empty",
            "error",
            "admitted_real_execution_candidate_ids must remain empty in this slice.",
            {"actual": admitted_real_ids},
        )
    if admitted_publication_ids:
        add_finding(
            findings,
            "admitted_publication_candidate_ids_not_empty",
            "error",
            "admitted_publication_candidate_ids must remain empty in this slice.",
            {"actual": admitted_publication_ids},
        )
    if real_preflight_passed_ids:
        add_finding(
            findings,
            "real_execution_preflight_passed_candidate_ids_not_empty",
            "error",
            "real_execution_preflight_passed_candidate_ids must remain empty in this slice.",
            {"actual": real_preflight_passed_ids},
        )
    if publication_preflight_passed_ids:
        add_finding(
            findings,
            "publication_preflight_passed_candidate_ids_not_empty",
            "error",
            "publication_preflight_passed_candidate_ids must remain empty in this slice.",
            {"actual": publication_preflight_passed_ids},
        )

    matrix_map: Dict[str, Dict[str, Any]] = {}
    preflight_map: Dict[str, Dict[str, Any]] = {}
    preflight_proof_map: Dict[str, Dict[str, Any]] = {}
    rollup_map: Dict[str, Dict[str, Any]] = {}

    matrix_raw = matrix_payload.get("candidates", [])
    if isinstance(matrix_raw, list):
        for entry in matrix_raw:
            if isinstance(entry, dict):
                cid = str(entry.get("candidate_id", "")).strip()
                if cid:
                    matrix_map[cid] = entry

    preflight_raw = preflight_payload.get("contracts", [])
    if isinstance(preflight_raw, list):
        for entry in preflight_raw:
            if isinstance(entry, dict):
                cid = str(entry.get("candidate_id", "")).strip()
                if cid:
                    preflight_map[cid] = entry

    preflight_proof_raw = preflight_proof_payload.get("proof_packages", [])
    if isinstance(preflight_proof_raw, list):
        for entry in preflight_proof_raw:
            if isinstance(entry, dict):
                cid = str(entry.get("candidate_id", "")).strip()
                if cid:
                    preflight_proof_map[cid] = entry

    rollup_raw = rollup.get("candidate_rollups", [])
    if not isinstance(rollup_raw, list):
        add_finding(
            findings,
            "candidate_rollups_not_array",
            "error",
            "candidate_rollups must be an array.",
        )
        rollup_raw = []
    for entry in rollup_raw:
        if not isinstance(entry, dict):
            add_finding(
                findings,
                "candidate_rollup_entry_invalid",
                "error",
                "Each candidate_rollups[] entry must be an object.",
            )
            continue
        cid = str(entry.get("candidate_id", "")).strip()
        if not cid:
            add_finding(
                findings,
                "candidate_rollup_candidate_id_missing",
                "error",
                "Each candidate rollup entry must include candidate_id.",
            )
            continue
        if cid in rollup_map:
            add_finding(
                findings,
                "candidate_rollup_candidate_id_duplicate",
                "error",
                "candidate_rollups candidate_id values must be unique.",
                {"candidate_id": cid},
            )
        rollup_map[cid] = entry

    matrix_ids = set(matrix_map)
    preflight_ids = set(preflight_map)
    preflight_proof_ids = set(preflight_proof_map)
    rollup_ids = set(rollup_map)

    for candidate_id in sorted(matrix_ids - rollup_ids):
        add_finding(
            findings,
            "matrix_candidate_missing_readiness_rollup",
            "error",
            "Every matrix candidate must appear in candidate_rollups.",
            {"candidate_id": candidate_id},
        )
    for candidate_id in sorted(preflight_ids - rollup_ids):
        add_finding(
            findings,
            "preflight_contract_candidate_missing_readiness_rollup",
            "error",
            "Every preflight contract candidate must appear in candidate_rollups.",
            {"candidate_id": candidate_id},
        )
    for candidate_id in sorted(preflight_proof_ids - rollup_ids):
        add_finding(
            findings,
            "preflight_proof_package_candidate_missing_readiness_rollup",
            "error",
            "Every preflight proof package candidate must appear in candidate_rollups.",
            {"candidate_id": candidate_id},
        )
    for candidate_id in sorted(rollup_ids - matrix_ids):
        add_finding(
            findings,
            "readiness_rollup_candidate_missing_from_matrix",
            "error",
            "Every readiness rollup candidate must exist in matrix.",
            {"candidate_id": candidate_id},
        )
    for candidate_id in sorted(rollup_ids - preflight_ids):
        add_finding(
            findings,
            "readiness_rollup_candidate_missing_from_preflight_contracts",
            "error",
            "Every readiness rollup candidate must exist in preflight contracts.",
            {"candidate_id": candidate_id},
        )
    for candidate_id in sorted(rollup_ids - preflight_proof_ids):
        add_finding(
            findings,
            "readiness_rollup_candidate_missing_from_preflight_proof_packages",
            "error",
            "Every readiness rollup candidate must exist in preflight proof packages.",
            {"candidate_id": candidate_id},
        )

    expected_real_candidate_ids = sorted(
        candidate_id
        for candidate_id, entry in matrix_map.items()
        if str(entry.get("candidate_type", "")).strip() == REAL_EXECUTION_TYPE
    )
    expected_publication_candidate_ids = sorted(
        candidate_id
        for candidate_id, entry in matrix_map.items()
        if str(entry.get("candidate_type", "")).strip() == PUBLICATION_TYPE
    )
    expected_dry_run_candidate_ids = sorted(
        candidate_id
        for candidate_id, entry in matrix_map.items()
        if str(entry.get("candidate_type", "")).strip() == DRY_RUN_TYPE
    )

    if sorted(set(blocked_real_ids)) != expected_real_candidate_ids:
        add_finding(
            findings,
            "blocked_real_execution_candidate_ids_mismatch",
            "error",
            "blocked_real_execution_candidate_ids must match matrix real execution candidates.",
            {"expected": expected_real_candidate_ids, "actual": sorted(set(blocked_real_ids))},
        )
    if sorted(set(blocked_publication_ids)) != expected_publication_candidate_ids:
        add_finding(
            findings,
            "blocked_publication_candidate_ids_mismatch",
            "error",
            "blocked_publication_candidate_ids must match matrix publication candidates.",
            {"expected": expected_publication_candidate_ids, "actual": sorted(set(blocked_publication_ids))},
        )
    if sorted(set(blocked_dry_run_ids)) != expected_dry_run_candidate_ids:
        add_finding(
            findings,
            "blocked_dry_run_candidate_ids_mismatch",
            "error",
            "blocked_dry_run_candidate_ids must match matrix dry-run candidates.",
            {"expected": expected_dry_run_candidate_ids, "actual": sorted(set(blocked_dry_run_ids))},
        )

    missing_summary_map: Dict[str, Dict[str, Any]] = {}
    missing_summary_raw = rollup.get("missing_evidence_summary", [])
    if not isinstance(missing_summary_raw, list):
        add_finding(
            findings,
            "missing_evidence_summary_not_array",
            "error",
            "missing_evidence_summary must be an array.",
        )
        missing_summary_raw = []
    for item in missing_summary_raw:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("candidate_id", "")).strip()
        if cid:
            missing_summary_map[cid] = item

    for candidate_id, rollup_entry in rollup_map.items():
        matrix_entry = matrix_map.get(candidate_id, {})
        preflight_entry = preflight_map.get(candidate_id, {})
        preflight_proof_entry = preflight_proof_map.get(candidate_id, {})

        candidate_type = str(rollup_entry.get("candidate_type", "")).strip()
        rollup_admission_status = str(rollup_entry.get("admission_status", "")).strip()
        rollup_preflight_passed = bool(rollup_entry.get("preflight_passed", False))
        rollup_proof_status = str(rollup_entry.get("proof_package_status", "")).strip()
        matrix_status = str(rollup_entry.get("matrix_status", "")).strip()
        contract_status = str(rollup_entry.get("preflight_contract_status", "")).strip()
        preflight_proof_status = str(rollup_entry.get("preflight_proof_package_status", "")).strip()
        approval_phrase = str(rollup_entry.get("approval_phrase_required", "")).strip()
        missing_count = int(rollup_entry.get("missing_evidence_count", 0))
        missing_item_ids = as_string_list(rollup_entry.get("missing_evidence_item_ids", []))
        blocker_reason_codes = as_string_list(rollup_entry.get("blocker_reason_codes", []))
        can_advance_without_explicit_approval = bool(
            rollup_entry.get("can_advance_without_explicit_approval", True)
        )

        matrix_candidate_type = str(matrix_entry.get("candidate_type", "")).strip()
        matrix_current_status = str(matrix_entry.get("current_status", "")).strip()
        expected_admission_from_matrix = matrix_status_to_admission(
            candidate_id, matrix_candidate_type, matrix_current_status
        )
        contract_candidate_type = str(preflight_entry.get("candidate_type", "")).strip()
        contract_admission_status = str(preflight_entry.get("admission_status", "")).strip()
        contract_preflight_status = str(preflight_entry.get("preflight_status", "")).strip()
        preflight_proof_candidate_type = str(preflight_proof_entry.get("candidate_type", "")).strip()
        preflight_proof_admission_status = str(
            preflight_proof_entry.get("admission_status", "")
        ).strip()
        preflight_proof_preflight_passed = bool(
            preflight_proof_entry.get("preflight_passed", False)
        )
        preflight_proof_package_status = str(
            preflight_proof_entry.get("proof_package_status", "")
        ).strip()

        if candidate_type != matrix_candidate_type:
            add_finding(
                findings,
                "candidate_type_mismatch_with_matrix",
                "error",
                "candidate_type must match matrix candidate_type.",
                {
                    "candidate_id": candidate_id,
                    "matrix_candidate_type": matrix_candidate_type,
                    "rollup_candidate_type": candidate_type,
                },
            )
        if candidate_type != contract_candidate_type:
            add_finding(
                findings,
                "candidate_type_mismatch_with_preflight_contracts",
                "error",
                "candidate_type must match preflight contracts candidate_type.",
                {
                    "candidate_id": candidate_id,
                    "preflight_contract_candidate_type": contract_candidate_type,
                    "rollup_candidate_type": candidate_type,
                },
            )
        if candidate_type != preflight_proof_candidate_type:
            add_finding(
                findings,
                "candidate_type_mismatch_with_preflight_proof_packages",
                "error",
                "candidate_type must match preflight proof packages candidate_type.",
                {
                    "candidate_id": candidate_id,
                    "preflight_proof_candidate_type": preflight_proof_candidate_type,
                    "rollup_candidate_type": candidate_type,
                },
            )
        if matrix_status != matrix_current_status:
            add_finding(
                findings,
                "matrix_status_mismatch",
                "error",
                "matrix_status must match matrix current_status.",
                {
                    "candidate_id": candidate_id,
                    "matrix_current_status": matrix_current_status,
                    "rollup_matrix_status": matrix_status,
                },
            )
        if contract_status != contract_preflight_status:
            add_finding(
                findings,
                "preflight_contract_status_mismatch",
                "error",
                "preflight_contract_status must match preflight contracts preflight_status.",
                {
                    "candidate_id": candidate_id,
                    "preflight_contract_status": contract_preflight_status,
                    "rollup_preflight_contract_status": contract_status,
                },
            )
        if preflight_proof_status != preflight_proof_package_status:
            add_finding(
                findings,
                "preflight_proof_package_status_mismatch",
                "error",
                "preflight_proof_package_status must match preflight proof packages proof_package_status.",
                {
                    "candidate_id": candidate_id,
                    "preflight_proof_package_status": preflight_proof_package_status,
                    "rollup_preflight_proof_package_status": preflight_proof_status,
                },
            )
        if rollup_proof_status != preflight_proof_package_status:
            add_finding(
                findings,
                "proof_package_status_mismatch",
                "error",
                "proof_package_status must match preflight proof package status.",
                {
                    "candidate_id": candidate_id,
                    "preflight_proof_package_status": preflight_proof_package_status,
                    "rollup_proof_package_status": rollup_proof_status,
                },
            )
        if rollup_preflight_passed != preflight_proof_preflight_passed:
            add_finding(
                findings,
                "preflight_passed_mismatch",
                "error",
                "preflight_passed must match preflight proof package preflight_passed.",
                {
                    "candidate_id": candidate_id,
                    "preflight_proof_preflight_passed": preflight_proof_preflight_passed,
                    "rollup_preflight_passed": rollup_preflight_passed,
                },
            )
        if rollup_admission_status != expected_admission_from_matrix:
            add_finding(
                findings,
                "admission_status_mismatch_with_matrix",
                "error",
                "admission_status must match matrix-derived admission posture.",
                {
                    "candidate_id": candidate_id,
                    "expected_from_matrix": expected_admission_from_matrix,
                    "actual": rollup_admission_status,
                },
            )
        if contract_admission_status and rollup_admission_status != contract_admission_status:
            add_finding(
                findings,
                "admission_status_mismatch_with_preflight_contracts",
                "error",
                "admission_status must match preflight contracts admission_status.",
                {
                    "candidate_id": candidate_id,
                    "preflight_contract_admission_status": contract_admission_status,
                    "rollup_admission_status": rollup_admission_status,
                },
            )
        if preflight_proof_admission_status and rollup_admission_status != preflight_proof_admission_status:
            add_finding(
                findings,
                "admission_status_mismatch_with_preflight_proof_packages",
                "error",
                "admission_status must match preflight proof packages admission_status.",
                {
                    "candidate_id": candidate_id,
                    "preflight_proof_admission_status": preflight_proof_admission_status,
                    "rollup_admission_status": rollup_admission_status,
                },
            )

        summary_entry = missing_summary_map.get(candidate_id)
        if not isinstance(summary_entry, dict):
            add_finding(
                findings,
                "missing_evidence_summary_entry_missing",
                "error",
                "missing_evidence_summary must include each rollup candidate.",
                {"candidate_id": candidate_id},
            )
        else:
            summary_count = int(summary_entry.get("missing_evidence_count", 0))
            summary_items = as_string_list(summary_entry.get("missing_evidence_item_ids", []))
            if summary_count != missing_count:
                add_finding(
                    findings,
                    "missing_evidence_count_mismatch",
                    "error",
                    "missing_evidence_count must match missing_evidence_summary.",
                    {
                        "candidate_id": candidate_id,
                        "rollup_missing_evidence_count": missing_count,
                        "summary_missing_evidence_count": summary_count,
                    },
                )
            if sorted(set(summary_items)) != sorted(set(missing_item_ids)):
                add_finding(
                    findings,
                    "missing_evidence_item_ids_mismatch",
                    "error",
                    "missing_evidence_item_ids must match missing_evidence_summary.",
                    {
                        "candidate_id": candidate_id,
                        "rollup_missing_evidence_item_ids": sorted(set(missing_item_ids)),
                        "summary_missing_evidence_item_ids": sorted(set(summary_items)),
                    },
                )

        if candidate_id == NOOP_CANDIDATE_ID:
            if candidate_type != NOOP_TYPE:
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
                    "No-op candidate must remain candidate_type=no_op_receipt.",
                    {"actual_candidate_type": candidate_type},
                )
            if rollup_admission_status == "admitted_real_execution":
                add_finding(
                    findings,
                    "noop_candidate_marked_admitted_real_execution",
                    "error",
                    "No-op candidate must not be marked admitted_real_execution.",
                )
            elif rollup_admission_status == "admitted_publication":
                add_finding(
                    findings,
                    "noop_candidate_marked_admitted_publication",
                    "error",
                    "No-op candidate must not be marked admitted_publication.",
                )
            elif rollup_admission_status != "admitted_no_op_only":
                add_finding(
                    findings,
                    "noop_candidate_wrong_admission_status",
                    "error",
                    "No-op candidate must keep admission_status=admitted_no_op_only.",
                    {"actual": rollup_admission_status},
                )
            if rollup_proof_status not in NOOP_SATISFIED_PROOF_STATUSES:
                add_finding(
                    findings,
                    "noop_candidate_wrong_proof_package_status",
                    "error",
                    "No-op candidate proof_package_status must be no-op-only satisfied.",
                    {"actual": rollup_proof_status},
                )
            if candidate_id in admitted_real_ids:
                add_finding(
                    findings,
                    "noop_candidate_listed_as_admitted_real_execution",
                    "error",
                    "No-op candidate must not appear in admitted_real_execution_candidate_ids.",
                )
            if candidate_id in admitted_publication_ids:
                add_finding(
                    findings,
                    "noop_candidate_listed_as_admitted_publication",
                    "error",
                    "No-op candidate must not appear in admitted_publication_candidate_ids.",
                )
            continue

        if candidate_type == REAL_EXECUTION_TYPE:
            if rollup_admission_status != "unadmitted":
                add_finding(
                    findings,
                    "future_real_execution_candidate_admitted_not_allowed",
                    "error",
                    "Future real execution candidates must remain unadmitted.",
                    {"candidate_id": candidate_id, "actual": rollup_admission_status},
                )
            if rollup_preflight_passed:
                add_finding(
                    findings,
                    "future_real_execution_candidate_preflight_passed_not_allowed",
                    "error",
                    "Future real execution candidates must keep preflight_passed=false.",
                    {"candidate_id": candidate_id},
                )
            if rollup_proof_status in REAL_OR_PUBLICATION_FORBIDDEN_STATUSES:
                add_finding(
                    findings,
                    "future_real_execution_candidate_full_satisfaction_not_allowed",
                    "error",
                    "Future real execution candidates must not use full-satisfaction proof statuses.",
                    {"candidate_id": candidate_id, "proof_package_status": rollup_proof_status},
                )
            if candidate_id not in blocked_real_ids:
                add_finding(
                    findings,
                    "future_real_execution_candidate_missing_from_blocked_list",
                    "error",
                    "Future real execution candidate must be listed in blocked_real_execution_candidate_ids.",
                    {"candidate_id": candidate_id},
                )
            if candidate_id in admitted_real_ids:
                add_finding(
                    findings,
                    "future_real_execution_candidate_listed_in_admitted_real_execution_ids",
                    "error",
                    "Future real execution candidate must not be listed in admitted_real_execution_candidate_ids.",
                    {"candidate_id": candidate_id},
                )
            if missing_count <= 0 or not missing_item_ids:
                add_finding(
                    findings,
                    "future_real_execution_candidate_missing_evidence_not_recorded",
                    "error",
                    "Future real execution candidate must include missing evidence.",
                    {"candidate_id": candidate_id},
                )
            if not blocker_reason_codes:
                add_finding(
                    findings,
                    "future_real_execution_candidate_missing_blocker_reason_codes",
                    "error",
                    "Future real execution candidate must include blocker_reason_codes.",
                    {"candidate_id": candidate_id},
                )
            if not str(rollup_entry.get("required_validator", "")).strip():
                add_finding(
                    findings,
                    "future_real_execution_candidate_missing_required_validator",
                    "error",
                    "Future real execution candidate must include required_validator.",
                    {"candidate_id": candidate_id},
                )
            if not str(rollup_entry.get("required_receipt_schema", "")).strip():
                add_finding(
                    findings,
                    "future_real_execution_candidate_missing_required_receipt_schema",
                    "error",
                    "Future real execution candidate must include required_receipt_schema.",
                    {"candidate_id": candidate_id},
                )
            if not approval_phrase:
                add_finding(
                    findings,
                    "future_real_execution_candidate_missing_approval_phrase_required",
                    "error",
                    "Future real execution candidate must include approval_phrase_required.",
                    {"candidate_id": candidate_id},
                )
            elif approval_phrase != expected_phrase(candidate_id):
                add_finding(
                    findings,
                    "future_real_execution_candidate_approval_phrase_mismatch",
                    "error",
                    "approval_phrase_required must match candidate_id.",
                    {
                        "candidate_id": candidate_id,
                        "expected": expected_phrase(candidate_id),
                        "actual": approval_phrase,
                    },
                )
            if can_advance_without_explicit_approval:
                add_finding(
                    findings,
                    "future_real_execution_candidate_can_advance_without_explicit_approval_not_allowed",
                    "error",
                    "Future real execution candidates must keep can_advance_without_explicit_approval=false.",
                    {"candidate_id": candidate_id},
                )

        elif candidate_type == PUBLICATION_TYPE:
            if rollup_admission_status != "unadmitted":
                add_finding(
                    findings,
                    "future_publication_candidate_admitted_not_allowed",
                    "error",
                    "Future publication candidates must remain unadmitted.",
                    {"candidate_id": candidate_id, "actual": rollup_admission_status},
                )
            if rollup_preflight_passed:
                add_finding(
                    findings,
                    "future_publication_candidate_preflight_passed_not_allowed",
                    "error",
                    "Future publication candidates must keep preflight_passed=false.",
                    {"candidate_id": candidate_id},
                )
            if rollup_proof_status in REAL_OR_PUBLICATION_FORBIDDEN_STATUSES:
                add_finding(
                    findings,
                    "future_publication_candidate_full_satisfaction_not_allowed",
                    "error",
                    "Future publication candidates must not use full-satisfaction proof statuses.",
                    {"candidate_id": candidate_id, "proof_package_status": rollup_proof_status},
                )
            if candidate_id not in blocked_publication_ids:
                add_finding(
                    findings,
                    "future_publication_candidate_missing_from_blocked_list",
                    "error",
                    "Future publication candidate must be listed in blocked_publication_candidate_ids.",
                    {"candidate_id": candidate_id},
                )
            if candidate_id in admitted_publication_ids:
                add_finding(
                    findings,
                    "future_publication_candidate_listed_in_admitted_publication_ids",
                    "error",
                    "Future publication candidate must not be listed in admitted_publication_candidate_ids.",
                    {"candidate_id": candidate_id},
                )
            if missing_count <= 0 or not missing_item_ids:
                add_finding(
                    findings,
                    "future_publication_candidate_missing_evidence_not_recorded",
                    "error",
                    "Future publication candidate must include missing evidence.",
                    {"candidate_id": candidate_id},
                )
            if not blocker_reason_codes:
                add_finding(
                    findings,
                    "future_publication_candidate_missing_blocker_reason_codes",
                    "error",
                    "Future publication candidate must include blocker_reason_codes.",
                    {"candidate_id": candidate_id},
                )
            if not str(rollup_entry.get("required_validator", "")).strip():
                add_finding(
                    findings,
                    "future_publication_candidate_missing_required_validator",
                    "error",
                    "Future publication candidate must include required_validator.",
                    {"candidate_id": candidate_id},
                )
            if not str(rollup_entry.get("required_receipt_schema", "")).strip():
                add_finding(
                    findings,
                    "future_publication_candidate_missing_required_receipt_schema",
                    "error",
                    "Future publication candidate must include required_receipt_schema.",
                    {"candidate_id": candidate_id},
                )
            if not approval_phrase:
                add_finding(
                    findings,
                    "future_publication_candidate_missing_approval_phrase_required",
                    "error",
                    "Future publication candidate must include approval_phrase_required.",
                    {"candidate_id": candidate_id},
                )
            elif approval_phrase != expected_phrase(candidate_id):
                add_finding(
                    findings,
                    "future_publication_candidate_approval_phrase_mismatch",
                    "error",
                    "approval_phrase_required must match candidate_id.",
                    {
                        "candidate_id": candidate_id,
                        "expected": expected_phrase(candidate_id),
                        "actual": approval_phrase,
                    },
                )
            if can_advance_without_explicit_approval:
                add_finding(
                    findings,
                    "future_publication_candidate_can_advance_without_explicit_approval_not_allowed",
                    "error",
                    "Future publication candidates must keep can_advance_without_explicit_approval=false.",
                    {"candidate_id": candidate_id},
                )

        elif candidate_type == DRY_RUN_TYPE:
            if rollup_admission_status in {"admitted_real_execution", "admitted_publication"}:
                add_finding(
                    findings,
                    "dry_run_candidate_treated_as_real_or_publication_admission",
                    "error",
                    "Dry-run candidate must not be treated as execution/publication admission.",
                    {"candidate_id": candidate_id, "actual_admission_status": rollup_admission_status},
                )
            if can_advance_without_explicit_approval:
                add_finding(
                    findings,
                    "dry_run_candidate_can_advance_without_explicit_approval_not_allowed",
                    "error",
                    "Dry-run candidate must keep can_advance_without_explicit_approval=false.",
                    {"candidate_id": candidate_id},
                )
            if approval_phrase and approval_phrase != expected_phrase(candidate_id):
                add_finding(
                    findings,
                    "dry_run_candidate_approval_phrase_mismatch",
                    "error",
                    "Dry-run candidate approval phrase must match candidate_id when present.",
                    {
                        "candidate_id": candidate_id,
                        "expected": expected_phrase(candidate_id),
                        "actual": approval_phrase,
                    },
                )

        # Safety claim term guardrail for structured fields.
        for key in ("safest_next_action",):
            value = str(rollup_entry.get(key, "")).strip().lower()
            if any(term in value for term in PRODUCTION_READY_TERMS):
                add_finding(
                    findings,
                    "rollup_claims_production_or_admission_not_allowed",
                    "error",
                    "Rollup candidate language must not claim production_ready or admitted execution/publication.",
                    {"candidate_id": candidate_id, "field": key, "value": rollup_entry.get(key)},
                )

    candidate_counts = rollup.get("candidate_counts") if isinstance(rollup.get("candidate_counts"), dict) else {}
    if candidate_counts:
        total_candidates = len(rollup_map)
        no_op_count = sum(
            1 for item in rollup_map.values() if str(item.get("candidate_type", "")).strip() == NOOP_TYPE
        )
        real_execution_count = sum(
            1
            for item in rollup_map.values()
            if str(item.get("candidate_type", "")).strip() == REAL_EXECUTION_TYPE
        )
        publication_count = sum(
            1
            for item in rollup_map.values()
            if str(item.get("candidate_type", "")).strip() == PUBLICATION_TYPE
        )
        dry_run_count = sum(
            1
            for item in rollup_map.values()
            if str(item.get("candidate_type", "")).strip() == DRY_RUN_TYPE
        )
        admitted_noop_only_count = sum(
            1
            for item in rollup_map.values()
            if str(item.get("admission_status", "")).strip() == "admitted_no_op_only"
        )
        blocked_real_count = len(blocked_real_ids)
        blocked_publication_count = len(blocked_publication_ids)
        blocked_dry_run_count = len(blocked_dry_run_ids)

        expected_count_map = {
            "total_candidates": total_candidates,
            "no_op_receipt_candidates": no_op_count,
            "real_execution_candidates": real_execution_count,
            "publication_candidates": publication_count,
            "dry_run_candidates": dry_run_count,
            "admitted_no_op_only_candidates": admitted_noop_only_count,
            "admitted_real_execution_candidates": len(admitted_real_ids),
            "admitted_publication_candidates": len(admitted_publication_ids),
            "blocked_real_execution_candidates": blocked_real_count,
            "blocked_publication_candidates": blocked_publication_count,
            "blocked_dry_run_candidates": blocked_dry_run_count,
        }
        for key, expected in expected_count_map.items():
            actual = candidate_counts.get(key)
            if actual != expected:
                add_finding(
                    findings,
                    "candidate_counts_mismatch",
                    "error",
                    "candidate_counts must match rollup candidate-derived counts.",
                    {"field": key, "expected": expected, "actual": actual},
                )

    safety = rollup.get("safety") if isinstance(rollup.get("safety"), dict) else {}
    safety_blocked_fields = [
        "o3de_execution_status",
        "editor_runtime_execution_status",
        "asset_processor_execution_status",
        "blender_dcc_execution_status",
        "profiler_benchmark_execution_status",
        "live_screenshot_capture_status",
        "spawn_publish_status",
        "cache_live_db_access_status",
        "production_write_status",
        "engine_write_status",
    ]
    for field in safety_blocked_fields:
        value = str(safety.get(field, "")).strip()
        if value != "blocked":
            if field == "production_write_status":
                finding_id = "production_path_write_allowed_claim"
            elif field == "engine_write_status":
                finding_id = "engine_path_write_allowed_claim"
            elif field == "cache_live_db_access_status":
                finding_id = "cache_live_db_access_allowed_claim"
            else:
                finding_id = "blocked_surface_not_blocked"
            add_finding(
                findings,
                finding_id,
                "error",
                "Safety surface must remain blocked in readiness rollup.",
                {"field": field, "actual": value or "<missing>"},
            )

    next_slice = (
        rollup.get("safest_next_preparation_slice")
        if isinstance(rollup.get("safest_next_preparation_slice"), dict)
        else {}
    )
    if str(next_slice.get("slice_id", "")).strip() != EXPECTED_NEXT_SLICE_ID:
        add_finding(
            findings,
            "safest_next_slice_id_mismatch",
            "error",
            "safest_next_preparation_slice.slice_id must remain candidate_specific_dry_run_planning_v1.",
            {"actual": next_slice.get("slice_id")},
        )
    if str(next_slice.get("candidate_id", "")).strip() != EXPECTED_NEXT_SLICE_CANDIDATE_ID:
        add_finding(
            findings,
            "safest_next_slice_candidate_id_mismatch",
            "error",
            "safest_next_preparation_slice.candidate_id must remain release_candidate_package_publish_dry_run_v1.",
            {"actual": next_slice.get("candidate_id")},
        )
    if bool(next_slice.get("admits_execution", False)):
        add_finding(
            findings,
            "safest_next_slice_admits_execution",
            "error",
            "safest_next_preparation_slice must keep admits_execution=false.",
        )
    if bool(next_slice.get("admits_publication", False)):
        add_finding(
            findings,
            "safest_next_slice_admits_publication",
            "error",
            "safest_next_preparation_slice must keep admits_publication=false.",
        )
    if next_slice.get("requires_future_pr") is not True:
        add_finding(
            findings,
            "safest_next_slice_requires_future_pr_false",
            "error",
            "safest_next_preparation_slice must keep requires_future_pr=true.",
        )
    if next_slice.get("requires_explicit_approval_before_admission") is not True:
        add_finding(
            findings,
            "safest_next_slice_requires_explicit_approval_false",
            "error",
            "safest_next_preparation_slice must keep requires_explicit_approval_before_admission=true.",
        )

    # Optional top-level language guardrails.
    for key in ("overall_readiness_rollup_status", "readiness_decision"):
        value = str(rollup.get(key, "")).strip().lower()
        if value in {"production_ready", "publication_admitted", "real_execution_admitted"}:
            add_finding(
                findings,
                "rollup_claims_production_or_admission_not_allowed",
                "error",
                "Rollup must not claim production_ready/publication_admitted/real_execution_admitted.",
                {"field": key, "value": rollup.get(key)},
            )

    severity_set = {str(item.get("severity", "")).strip() for item in findings}
    status = "fail" if "error" in severity_set else "pass"

    report_payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": "EXECUTION_ADMISSION_READINESS_ROLLUP_VALIDATION_v1_REPORT",
        "status": status,
        "execution_admission_readiness_rollup_present": True,
        "readiness_rollup_path": str(rollup_path),
        "candidate_matrix_path": str(matrix_path),
        "preflight_contracts_path": str(preflight_path),
        "preflight_proof_packages_path": str(preflight_proof_path),
        "production_readiness_report_path": str(production_readiness_path),
        "noop_receipt_admission_path": str(noop_decision_path),
        "source_artifact_validation_status": source_validation_status_reported,
        "overall_readiness_rollup_status": str(
            rollup.get("overall_readiness_rollup_status", "")
        ).strip(),
        "admitted_noop_receipt_candidate_ids": admitted_noop_ids,
        "admitted_real_execution_candidate_ids": admitted_real_ids,
        "admitted_publication_candidate_ids": admitted_publication_ids,
        "blocked_real_execution_candidate_ids": blocked_real_ids,
        "blocked_publication_candidate_ids": blocked_publication_ids,
        "blocked_dry_run_candidate_ids": blocked_dry_run_ids,
        "real_execution_preflight_passed_candidate_ids": real_preflight_passed_ids,
        "publication_preflight_passed_candidate_ids": publication_preflight_passed_ids,
        "real_execution_admission_status": str(
            rollup.get("real_execution_admission_status", "")
        ).strip()
        or "blocked",
        "publication_admission_status": str(
            rollup.get("publication_admission_status", "")
        ).strip()
        or "blocked",
        "production_ready_claimed": bool(rollup.get("production_ready_claimed", False)),
        "unsafe_claims_detected": bool(rollup.get("unsafe_claims_detected", False)),
        "safest_next_preparation_slice": next_slice,
        "candidate_rollup_count": len(rollup_map),
        "candidate_rollup_candidate_ids": sorted(rollup_ids),
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
