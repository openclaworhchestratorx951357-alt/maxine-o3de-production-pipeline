#!/usr/bin/env python3
"""Validate release-candidate publication dry-run receipt contract artifacts v1."""

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
EXPECTED_CONTRACT_STATUS = "static_contract_valid_blocked"
EXPECTED_ROLLUP_STATUS = "static_rollup_valid_blocked"
EXPECTED_DRY_RUN_PLAN_STATUS = "static_plan_valid_blocked"
EXPECTED_NEXT_SLICE_ID = "candidate_specific_dry_run_planning_v1"
SAFE_RECEIPT_STATUSES = {
    "receipt_not_issued_contract_only",
    "blocked_unissued_contract_only",
}

DEFAULT_RECEIPT_CONTRACT_REL = Path(
    "examples/execution-admission/release_candidate_package_publish_dry_run_receipt_contract_v1.json"
)
DEFAULT_SCHEMA_REL = Path(
    "schemas/maxine_release_candidate_publication_dry_run_receipt.schema.json"
)
DEFAULT_PRODUCTION_READINESS_SCHEMA_REL = Path(
    "schemas/maxine_production_readiness_report.schema.json"
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

REQUIRED_FORBIDDEN_PATH_CATEGORIES = {
    "production_path_category": "forbidden_paths_missing_production_category",
    "engine_path_category": "forbidden_paths_missing_engine_category",
    "cache_live_db_category": "forbidden_paths_missing_cache_live_db_category",
    "destructive_cleanup_category": "forbidden_paths_missing_destructive_cleanup_category",
}

REQUIRED_FORBIDDEN_OUTPUTS = {
    "publish_operation": "forbidden_outputs_missing_publish_category",
    "spawn_operation": "forbidden_outputs_missing_spawn_category",
    "production_path_writes": "forbidden_outputs_missing_production_write_category",
    "engine_path_writes": "forbidden_outputs_missing_engine_write_category",
    "cache_live_db_access": "contract_allows_cache_live_db_access",
    "authoritative_source_uuid_claims": "contract_allows_authoritative_source_uuid_claims",
    "authoritative_asset_id_claims": "contract_allows_authoritative_asset_id_claims",
    "authoritative_product_id_claims": "contract_allows_authoritative_product_id_claims",
}

REQUIRED_RECEIPT_FIELDS = {
    "candidate_id": "required_receipt_fields_missing_candidate_id",
    "receipt_type": "required_receipt_fields_missing_receipt_type",
    "receipt_status": "required_receipt_fields_missing_receipt_status",
    "approval_decision_reference": "required_receipt_fields_missing_approval_decision_reference",
    "source_artifact_references": "required_receipt_fields_missing_source_artifact_references",
    "input_evidence_references": "required_receipt_fields_missing_input_evidence_references",
    "sandbox_output_index": "required_receipt_fields_missing_sandbox_output_index",
    "validation_summary": "required_receipt_fields_missing_validation_summary",
    "blocked_surface_attestations": "required_receipt_fields_missing_blocked_surface_attestations",
    "rollback_or_cleanup_evidence": "required_receipt_fields_missing_rollback_or_cleanup_evidence",
    "hashes": "required_receipt_fields_missing_hashes",
    "safety_posture": "required_receipt_fields_missing_safety_posture",
}

REQUIRED_SOURCE_REFERENCE_FIELDS = {
    "candidate_matrix_ref",
    "preflight_contracts_ref",
    "preflight_proof_packages_ref",
    "readiness_rollup_ref",
    "dry_run_plan_ref",
    "production_readiness_report_ref",
    "noop_receipt_status_ref",
}

REQUIRED_FORBIDDEN_RECEIPT_CLAIMS = {
    "dry_run_admitted": "contract_allows_dry_run_admission",
    "publication_admitted": "contract_allows_publication_admission",
    "real_execution_admitted": "contract_allows_real_execution_admission",
    "production_ready": "contract_allows_production_ready_claim",
    "receipt_issued": "contract_allows_receipt_issued_claim",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate release-candidate publication dry-run receipt contract artifacts v1."
    )
    parser.add_argument(
        "receipt_contract_path",
        nargs="?",
        default=str(DEFAULT_RECEIPT_CONTRACT_REL),
        help="Path to release-candidate publication dry-run receipt contract JSON.",
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
    if payload.get("status") != "pass":
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


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    receipt_path = (
        Path(args.receipt_contract_path).resolve()
        if Path(args.receipt_contract_path).is_absolute()
        else (repo_root / args.receipt_contract_path).resolve()
    )
    schema_path = (repo_root / DEFAULT_SCHEMA_REL).resolve()
    production_readiness_schema_path = (
        repo_root / DEFAULT_PRODUCTION_READINESS_SCHEMA_REL
    ).resolve()

    if not receipt_path.exists():
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": f"dry-run receipt contract not found: {receipt_path}",
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

    receipt = load_json(receipt_path)
    schema = load_json(schema_path)
    findings: List[Dict[str, Any]] = []

    ok, schema_errors = validate_schema(receipt, schema)
    if not ok:
        for message in schema_errors:
            add_finding(
                findings,
                "schema_validation_error",
                "error",
                "Dry-run receipt contract failed schema validation.",
                {"error": message},
            )

    source_artifacts = (
        receipt.get("source_artifacts")
        if isinstance(receipt.get("source_artifacts"), dict)
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
    preflight_proof_payload = (
        load_json(preflight_proof_path) if preflight_proof_path.exists() else {}
    )
    rollup_payload = load_json(rollup_path) if rollup_path.exists() else {}
    dry_run_plan_payload = load_json(dry_run_plan_path) if dry_run_plan_path.exists() else {}
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

    (
        preflight_proof_code,
        preflight_proof_report,
        preflight_proof_parse_error,
    ) = run_validator(
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

    production_readiness_local_status = "pass"
    if production_readiness_payload:
        production_readiness_local_status = _validate_production_readiness_report(
            production_readiness_payload, findings
        )
        if production_readiness_schema_path.exists():
            production_schema = load_json(production_readiness_schema_path)
            schema_ok, schema_errors = validate_schema(
                production_readiness_payload, production_schema
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

    source_status_reported = (
        receipt.get("source_artifact_validation_status")
        if isinstance(receipt.get("source_artifact_validation_status"), dict)
        else {}
    )
    source_status_expected: Dict[str, str] = {
        "candidate_matrix_status": str((matrix_report or {}).get("status", "fail")).strip()
        or "fail",
        "preflight_contracts_status": str((preflight_report or {}).get("status", "fail")).strip()
        or "fail",
        "preflight_proof_packages_status": str(
            (preflight_proof_report or {}).get("status", "fail")
        ).strip()
        or "fail",
        "readiness_rollup_status": str((rollup_report or {}).get("status", "fail")).strip()
        or "fail",
        "dry_run_plan_status": str((dry_run_plan_report or {}).get("status", "fail")).strip()
        or "fail",
        "production_readiness_status": production_readiness_local_status,
        "noop_receipt_status": noop_decision_local_status,
    }
    for key, expected in source_status_expected.items():
        actual = str(source_status_reported.get(key, "")).strip()
        if actual != expected:
            add_finding(
                findings,
                "source_artifact_validation_status_mismatch",
                "error",
                "source_artifact_validation_status must match computed validator/report status.",
                {"field": key, "expected": expected, "actual": actual},
            )
        if expected != "pass":
            add_finding(
                findings,
                "source_artifact_validation_status_not_pass",
                "error",
                "All source artifact validations must be pass for this static receipt-contract slice.",
                {"field": key, "actual": expected},
            )

    candidate_id = str(receipt.get("candidate_id", "")).strip()
    candidate_type = str(receipt.get("candidate_type", "")).strip()
    receipt_type = str(receipt.get("receipt_type", "")).strip()
    receipt_contract_status = str(receipt.get("receipt_contract_status", "")).strip()
    receipt_status = str(receipt.get("receipt_status", "")).strip()

    if candidate_id != TARGET_CANDIDATE_ID:
        add_finding(
            findings,
            "candidate_id_mismatch",
            "error",
            "candidate_id must match release_candidate_package_publish_dry_run_v1.",
            {"expected": TARGET_CANDIDATE_ID, "actual": candidate_id},
        )

    if candidate_type != TARGET_CANDIDATE_TYPE:
        add_finding(
            findings,
            "candidate_type_mismatch",
            "error",
            "candidate_type must be dry_run.",
            {"expected": TARGET_CANDIDATE_TYPE, "actual": candidate_type},
        )

    if receipt_type != TARGET_RECEIPT_TYPE:
        add_finding(
            findings,
            "receipt_type_mismatch",
            "error",
            "receipt_type must be release_candidate_package_publish_dry_run_receipt_v1.",
            {"expected": TARGET_RECEIPT_TYPE, "actual": receipt_type},
        )

    if str(receipt.get("admission_status", "")).strip() != "unadmitted":
        add_finding(
            findings,
            "dry_run_admitted_not_allowed",
            "error",
            "admission_status must remain unadmitted for this slice.",
            {"actual": receipt.get("admission_status")},
        )

    if receipt.get("receipt_issued") is not False:
        add_finding(
            findings,
            "receipt_issued_not_allowed",
            "error",
            "receipt_issued must remain false in this static contract slice.",
            {"actual": receipt.get("receipt_issued")},
        )

    if receipt.get("dry_run_admitted") is not False:
        add_finding(
            findings,
            "dry_run_admitted_not_allowed",
            "error",
            "dry_run_admitted must remain false.",
        )

    if receipt.get("publication_admitted") is not False:
        add_finding(
            findings,
            "publication_admitted_not_allowed",
            "error",
            "publication_admitted must remain false.",
        )

    if receipt.get("real_execution_admitted") is not False:
        add_finding(
            findings,
            "real_execution_admitted_not_allowed",
            "error",
            "real_execution_admitted must remain false.",
        )

    if receipt.get("production_ready_claimed") is not False:
        add_finding(
            findings,
            "production_ready_claim_not_allowed",
            "error",
            "production_ready_claimed must remain false.",
        )

    if receipt.get("generated_from_static_artifacts_only") is not True:
        add_finding(
            findings,
            "generated_from_static_artifacts_only_false",
            "error",
            "generated_from_static_artifacts_only must remain true.",
        )

    if receipt_contract_status != EXPECTED_CONTRACT_STATUS:
        add_finding(
            findings,
            "receipt_contract_status_not_static_contract_valid_blocked",
            "error",
            "receipt_contract_status must be static_contract_valid_blocked.",
            {"actual": receipt_contract_status},
        )

    if receipt_status not in SAFE_RECEIPT_STATUSES:
        add_finding(
            findings,
            "receipt_status_emitted_not_allowed",
            "error",
            "receipt_status must remain a blocked/unissued contract-only status in this slice.",
            {"actual": receipt_status},
        )

    allowed_receipt_status_values = as_string_list(receipt.get("allowed_receipt_status_values", []))
    if not allowed_receipt_status_values:
        add_finding(
            findings,
            "allowed_receipt_status_values_missing",
            "error",
            "allowed_receipt_status_values must be non-empty.",
        )

    for required_safe_status in SAFE_RECEIPT_STATUSES:
        if required_safe_status not in allowed_receipt_status_values:
            add_finding(
                findings,
                "allowed_receipt_status_values_missing_safe_status",
                "error",
                "allowed_receipt_status_values must include blocked/unissued statuses.",
                {"missing_status": required_safe_status},
            )

    for required_array_field in (
        "allowed_receipt_output_scope",
        "required_source_references",
        "required_input_evidence",
        "required_rollback_or_cleanup_evidence",
        "required_blocked_surface_attestations",
        "forbidden_receipt_claims",
        "forbidden_outputs",
        "forbidden_paths",
        "blocked_reason_codes",
        "missing_evidence_items",
    ):
        if not as_string_list(receipt.get(required_array_field, [])):
            add_finding(
                findings,
                "required_array_missing_or_empty",
                "error",
                "Required receipt contract arrays must be non-empty.",
                {"field": required_array_field},
            )

    if not as_string_list(receipt.get("required_receipt_fields", [])):
        add_finding(
            findings,
            "required_receipt_fields_missing",
            "error",
            "required_receipt_fields must be non-empty.",
        )

    required_receipt_fields = set(as_string_list(receipt.get("required_receipt_fields", [])))
    for field, finding_id in REQUIRED_RECEIPT_FIELDS.items():
        if field not in required_receipt_fields:
            add_finding(
                findings,
                finding_id,
                "error",
                "required_receipt_fields is missing required token.",
                {"missing_field": field},
            )

    required_source_references = set(as_string_list(receipt.get("required_source_references", [])))
    for field in REQUIRED_SOURCE_REFERENCE_FIELDS:
        if field not in required_source_references:
            add_finding(
                findings,
                "required_source_references_missing_field",
                "error",
                "required_source_references must include all source artifact fields.",
                {"missing_field": field},
            )

    required_approval_decision_reference = receipt.get("required_approval_decision_reference")
    if required_approval_decision_reference is not True:
        add_finding(
            findings,
            "required_approval_decision_reference_false",
            "error",
            "required_approval_decision_reference must be true.",
            {"actual": required_approval_decision_reference},
        )

    approval_phrase = str(receipt.get("approval_phrase_required", "")).strip()
    if approval_phrase != EXPECTED_APPROVAL_PHRASE:
        add_finding(
            findings,
            "approval_phrase_required_mismatch",
            "error",
            "approval_phrase_required must exactly match candidate-specific phrase.",
            {"expected": EXPECTED_APPROVAL_PHRASE, "actual": approval_phrase},
        )

    approval_decision_reference = receipt.get("approval_decision_reference")
    if isinstance(approval_decision_reference, str) and approval_decision_reference.strip():
        add_finding(
            findings,
            "approval_decision_reference_not_allowed",
            "error",
            "approval_decision_reference must be null/empty in this unadmitted contract slice.",
            {"actual": approval_decision_reference},
        )

    for field in (
        "publication_surfaces_blocked",
        "execution_surfaces_blocked",
        "cache_live_db_access_blocked",
        "authoritative_id_claims_blocked",
    ):
        if receipt.get(field) is not True:
            add_finding(
                findings,
                f"{field}_false",
                "error",
                f"{field} must remain true.",
                {"actual": receipt.get(field)},
            )

    forbidden_paths = set(as_string_list(receipt.get("forbidden_paths", [])))
    for category, finding_id in REQUIRED_FORBIDDEN_PATH_CATEGORIES.items():
        if category not in forbidden_paths:
            add_finding(
                findings,
                finding_id,
                "error",
                "forbidden_paths must include required blocked path category.",
                {"missing_category": category},
            )

    forbidden_outputs = set(as_string_list(receipt.get("forbidden_outputs", [])))
    for token, finding_id in REQUIRED_FORBIDDEN_OUTPUTS.items():
        if token not in forbidden_outputs:
            add_finding(
                findings,
                finding_id,
                "error",
                "forbidden_outputs must include required blocked output category.",
                {"missing_output": token},
            )

    forbidden_receipt_claims = set(as_string_list(receipt.get("forbidden_receipt_claims", [])))
    for token, finding_id in REQUIRED_FORBIDDEN_RECEIPT_CLAIMS.items():
        if token not in forbidden_receipt_claims:
            add_finding(
                findings,
                finding_id,
                "error",
                "forbidden_receipt_claims must include required blocked claim.",
                {"missing_claim": token},
            )

    allowed_receipt_output_scope = as_string_list(receipt.get("allowed_receipt_output_scope", []))
    if not allowed_receipt_output_scope:
        add_finding(
            findings,
            "allowed_receipt_output_scope_missing",
            "error",
            "allowed_receipt_output_scope must be non-empty.",
        )
    for output_scope in allowed_receipt_output_scope:
        normalized_scope = output_scope.replace("\\", "/").strip().lower()
        if not normalized_scope.startswith("examples/sandbox/"):
            add_finding(
                findings,
                "allowed_receipt_output_scope_outside_sandbox",
                "error",
                "allowed_receipt_output_scope entries must remain under examples/sandbox/.",
                {"scope": output_scope},
            )
        if "production" in normalized_scope:
            add_finding(
                findings,
                "contract_allows_production_path_writes",
                "error",
                "allowed_receipt_output_scope must not include production paths.",
                {"scope": output_scope},
            )
        if "engine" in normalized_scope:
            add_finding(
                findings,
                "contract_allows_engine_path_writes",
                "error",
                "allowed_receipt_output_scope must not include engine paths.",
                {"scope": output_scope},
            )

    required_sandbox_output_index = (
        receipt.get("required_sandbox_output_index")
        if isinstance(receipt.get("required_sandbox_output_index"), dict)
        else {}
    )
    output_root = str(required_sandbox_output_index.get("output_root", "")).strip()
    if not output_root:
        add_finding(
            findings,
            "required_sandbox_output_index_missing_output_root",
            "error",
            "required_sandbox_output_index.output_root must be present.",
        )
    else:
        normalized_output_root = output_root.replace("\\", "/").lower()
        if not normalized_output_root.startswith("examples/sandbox/"):
            add_finding(
                findings,
                "required_sandbox_output_index_outside_sandbox",
                "error",
                "required_sandbox_output_index.output_root must remain under examples/sandbox/.",
                {"output_root": output_root},
            )
        if "production" in normalized_output_root:
            add_finding(
                findings,
                "contract_allows_production_path_writes",
                "error",
                "required_sandbox_output_index.output_root must not include production paths.",
                {"output_root": output_root},
            )
        if "engine" in normalized_output_root:
            add_finding(
                findings,
                "contract_allows_engine_path_writes",
                "error",
                "required_sandbox_output_index.output_root must not include engine paths.",
                {"output_root": output_root},
            )

    required_hashes = (
        receipt.get("required_hashes")
        if isinstance(receipt.get("required_hashes"), dict)
        else {}
    )
    if not as_string_list(required_hashes.get("algorithms", [])):
        add_finding(
            findings,
            "required_hashes_algorithms_missing",
            "error",
            "required_hashes.algorithms must be non-empty.",
        )
    if not as_string_list(required_hashes.get("required_fields", [])):
        add_finding(
            findings,
            "required_hashes_fields_missing",
            "error",
            "required_hashes.required_fields must be non-empty.",
        )

    required_validation_summary = (
        receipt.get("required_validation_summary")
        if isinstance(receipt.get("required_validation_summary"), dict)
        else {}
    )
    if not as_string_list(required_validation_summary.get("required_fields", [])):
        add_finding(
            findings,
            "required_validation_summary_fields_missing",
            "error",
            "required_validation_summary.required_fields must be non-empty.",
        )
    if not as_string_list(required_validation_summary.get("required_status_fields", [])):
        add_finding(
            findings,
            "required_validation_summary_status_fields_missing",
            "error",
            "required_validation_summary.required_status_fields must be non-empty.",
        )

    safety_posture = (
        receipt.get("safety_posture") if isinstance(receipt.get("safety_posture"), dict) else {}
    )
    for field, expected in (
        ("source_uuid_status", "not_authoritative"),
        ("asset_id_status", "not_authoritative"),
        ("product_id_status", "not_authoritative"),
    ):
        if str(safety_posture.get(field, "")).strip() != expected:
            add_finding(
                findings,
                f"{field}_authoritative_claim_allowed",
                "error",
                "safety_posture must keep IDs non-authoritative.",
                {"field": field, "expected": expected, "actual": safety_posture.get(field)},
            )

    if bool(receipt.get("unsafe_claims_detected", False)):
        add_finding(
            findings,
            "unsafe_claims_detected_not_allowed",
            "error",
            "unsafe_claims_detected must remain false.",
        )

    matrix_map = _candidate_map(matrix_payload, "candidates")
    preflight_map = _candidate_map(preflight_payload, "contracts")
    proof_map = _candidate_map(preflight_proof_payload, "proof_packages")
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
                "Target candidate type must match candidate matrix.",
                {"actual": matrix_entry.get("candidate_type")},
            )
        if str(matrix_entry.get("current_status", "")).strip() == "admitted":
            add_finding(
                findings,
                "dry_run_admitted_not_allowed",
                "error",
                "Target dry-run candidate must remain unadmitted in matrix.",
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
                "Target candidate type must match preflight contracts.",
            )
        if str(preflight_entry.get("admission_status", "")).strip() != "unadmitted":
            add_finding(
                findings,
                "dry_run_admitted_not_allowed",
                "error",
                "Target dry-run candidate must remain unadmitted in preflight contracts.",
            )

    proof_entry = proof_map.get(TARGET_CANDIDATE_ID)
    if not isinstance(proof_entry, dict):
        add_finding(
            findings,
            "candidate_missing_in_preflight_proof_packages",
            "error",
            "Target candidate must exist in preflight proof packages.",
        )
    else:
        if str(proof_entry.get("candidate_type", "")).strip() != TARGET_CANDIDATE_TYPE:
            add_finding(
                findings,
                "candidate_type_mismatch_with_preflight_proof_packages",
                "error",
                "Target candidate type must match preflight proof packages.",
            )
        if str(proof_entry.get("admission_status", "")).strip() != "unadmitted":
            add_finding(
                findings,
                "dry_run_admitted_not_allowed",
                "error",
                "Target dry-run candidate must remain unadmitted in preflight proof packages.",
            )
        if bool(proof_entry.get("preflight_passed", False)):
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
                "Target candidate type must match readiness rollup.",
            )
        if str(rollup_entry.get("admission_status", "")).strip() != "unadmitted":
            add_finding(
                findings,
                "dry_run_admitted_not_allowed",
                "error",
                "Target dry-run candidate must remain unadmitted in readiness rollup.",
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
    next_slice_id = str(next_slice.get("slice_id", "")).strip()
    next_slice_candidate = str(next_slice.get("candidate_id", "")).strip()
    if next_slice_id != EXPECTED_NEXT_SLICE_ID:
        add_finding(
            findings,
            "readiness_rollup_safest_next_slice_id_mismatch",
            "error",
            "Readiness rollup safest next slice id must remain candidate_specific_dry_run_planning_v1.",
            {"actual": next_slice_id},
        )
    if next_slice_candidate != TARGET_CANDIDATE_ID:
        add_finding(
            findings,
            "readiness_rollup_safest_next_candidate_mismatch",
            "error",
            "Readiness rollup safest next candidate must be release_candidate_package_publish_dry_run_v1.",
            {"actual": next_slice_candidate},
        )

    if bool(next_slice.get("admits_execution", False)):
        add_finding(
            findings,
            "contract_allows_real_execution_admission",
            "error",
            "Readiness rollup safest-next slice must keep admits_execution=false.",
        )
    if bool(next_slice.get("admits_publication", False)):
        add_finding(
            findings,
            "contract_allows_publication_admission",
            "error",
            "Readiness rollup safest-next slice must keep admits_publication=false.",
        )

    if next_slice.get("requires_future_pr") is not True:
        add_finding(
            findings,
            "readiness_rollup_safest_next_requires_future_pr_false",
            "error",
            "Readiness rollup safest-next slice must keep requires_future_pr=true.",
        )
    if next_slice.get("requires_explicit_approval_before_admission") is not True:
        add_finding(
            findings,
            "readiness_rollup_safest_next_requires_explicit_approval_false",
            "error",
            "Readiness rollup safest-next slice must keep requires_explicit_approval_before_admission=true.",
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

    if str(dry_run_plan_payload.get("approval_phrase_required", "")).strip() != EXPECTED_APPROVAL_PHRASE:
        add_finding(
            findings,
            "dry_run_plan_approval_phrase_mismatch",
            "error",
            "Referenced dry-run plan must keep exact candidate-specific approval phrase.",
            {"actual": dry_run_plan_payload.get("approval_phrase_required")},
        )

    dry_run_plan_alignment = (
        receipt.get("dry_run_plan_alignment")
        if isinstance(receipt.get("dry_run_plan_alignment"), dict)
        else {}
    )
    if str(dry_run_plan_alignment.get("planned_candidate_id", "")).strip() != TARGET_CANDIDATE_ID:
        add_finding(
            findings,
            "dry_run_plan_alignment_candidate_mismatch",
            "error",
            "dry_run_plan_alignment.planned_candidate_id must match target candidate.",
            {"actual": dry_run_plan_alignment.get("planned_candidate_id")},
        )
    if str(dry_run_plan_alignment.get("alignment_status", "")).strip() != "aligned":
        add_finding(
            findings,
            "dry_run_plan_alignment_status_not_aligned",
            "error",
            "dry_run_plan_alignment.alignment_status must be aligned.",
        )
    if str(dry_run_plan_alignment.get("dry_run_plan_ref", "")).strip() != str(
        source_artifacts.get("dry_run_plan_ref", "")
    ).strip():
        add_finding(
            findings,
            "dry_run_plan_alignment_ref_mismatch",
            "error",
            "dry_run_plan_alignment.dry_run_plan_ref must match source_artifacts.dry_run_plan_ref.",
            {
                "alignment_ref": dry_run_plan_alignment.get("dry_run_plan_ref"),
                "source_ref": source_artifacts.get("dry_run_plan_ref"),
            },
        )

    readiness_alignment = (
        receipt.get("readiness_rollup_alignment")
        if isinstance(receipt.get("readiness_rollup_alignment"), dict)
        else {}
    )
    if str(readiness_alignment.get("safest_next_preparation_slice_id", "")).strip() != next_slice_id:
        add_finding(
            findings,
            "readiness_rollup_alignment_slice_mismatch",
            "error",
            "readiness_rollup_alignment slice id must match referenced readiness rollup.",
            {
                "contract": readiness_alignment.get("safest_next_preparation_slice_id"),
                "rollup": next_slice_id,
            },
        )
    if str(readiness_alignment.get("safest_next_preparation_candidate_id", "")).strip() != next_slice_candidate:
        add_finding(
            findings,
            "readiness_rollup_alignment_candidate_mismatch",
            "error",
            "readiness_rollup_alignment candidate id must match referenced readiness rollup.",
            {
                "contract": readiness_alignment.get("safest_next_preparation_candidate_id"),
                "rollup": next_slice_candidate,
            },
        )
    if str(readiness_alignment.get("alignment_status", "")).strip() != "aligned":
        add_finding(
            findings,
            "readiness_rollup_alignment_status_not_aligned",
            "error",
            "readiness_rollup_alignment alignment status must be aligned.",
        )

    if str(readiness_alignment.get("readiness_rollup_ref", "")).strip() != str(
        source_artifacts.get("readiness_rollup_ref", "")
    ).strip():
        add_finding(
            findings,
            "readiness_rollup_alignment_ref_mismatch",
            "error",
            "readiness_rollup_alignment.readiness_rollup_ref must match source_artifacts.readiness_rollup_ref.",
            {
                "alignment_ref": readiness_alignment.get("readiness_rollup_ref"),
                "source_ref": source_artifacts.get("readiness_rollup_ref"),
            },
        )

    severity_set = {str(item.get("severity", "")).strip() for item in findings}
    status = "fail" if "error" in severity_set else "pass"

    report_payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_CONTRACT_VALIDATION_v1_REPORT",
        "status": status,
        "release_candidate_publication_dry_run_receipt_contract_present": True,
        "release_candidate_publication_dry_run_receipt_contract_path": str(receipt_path),
        "candidate_matrix_path": str(matrix_path),
        "preflight_contracts_path": str(preflight_path),
        "preflight_proof_packages_path": str(preflight_proof_path),
        "readiness_rollup_path": str(rollup_path),
        "dry_run_plan_path": str(dry_run_plan_path),
        "production_readiness_report_path": str(production_readiness_path),
        "noop_receipt_status_path": str(noop_decision_path),
        "source_artifact_validation_status": source_status_reported,
        "computed_source_artifact_validation_status": source_status_expected,
        "planned_candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "receipt_type": receipt_type,
        "receipt_contract_status": receipt_contract_status,
        "receipt_status": receipt_status,
        "receipt_issued": bool(receipt.get("receipt_issued", False)),
        "dry_run_admitted": bool(receipt.get("dry_run_admitted", False)),
        "publication_admitted": bool(receipt.get("publication_admitted", False)),
        "real_execution_admitted": bool(receipt.get("real_execution_admitted", False)),
        "production_ready_claimed": bool(receipt.get("production_ready_claimed", False)),
        "publication_surfaces_blocked": bool(receipt.get("publication_surfaces_blocked", False)),
        "execution_surfaces_blocked": bool(receipt.get("execution_surfaces_blocked", False)),
        "cache_live_db_access_blocked": bool(receipt.get("cache_live_db_access_blocked", False)),
        "authoritative_id_claims_blocked": bool(receipt.get("authoritative_id_claims_blocked", False)),
        "dry_run_plan_alignment": dry_run_plan_alignment,
        "readiness_rollup_alignment": readiness_alignment,
        "missing_evidence_items_count": len(as_string_list(receipt.get("missing_evidence_items", []))),
        "blocked_reason_codes": as_string_list(receipt.get("blocked_reason_codes", [])),
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
