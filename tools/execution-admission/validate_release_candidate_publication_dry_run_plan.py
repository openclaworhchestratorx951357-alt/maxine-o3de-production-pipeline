#!/usr/bin/env python3
"""Validate release-candidate publication dry-run planning artifact v1."""

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
EXPECTED_PLAN_STATUS = "static_plan_valid_blocked"
EXPECTED_SCOPE = "candidate_specific_publication_dry_run_planning_only"
EXPECTED_NEXT_SLICE_ID = "candidate_specific_dry_run_planning_v1"

DEFAULT_PLAN_REL = Path(
    "examples/execution-admission/release_candidate_package_publish_dry_run_plan_v1.json"
)
DEFAULT_SCHEMA_REL = Path(
    "schemas/maxine_release_candidate_publication_dry_run_plan.schema.json"
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

OUT_OF_SCOPE_GUARDS = {
    "publication_execution": "plan_allows_publish",
    "spawn_execution": "plan_allows_spawn",
    "production_path_write": "plan_allows_production_path_writes",
    "engine_path_write": "plan_allows_engine_path_writes",
    "cache_live_db_access": "plan_allows_cache_live_db_access",
}

REQUIRED_FORBIDDEN_PATH_CATEGORIES = {
    "production_path_category": "forbidden_paths_missing_production_category",
    "engine_path_category": "forbidden_paths_missing_engine_category",
    "cache_live_db_category": "forbidden_paths_missing_cache_live_db_category",
    "destructive_cleanup_category": "forbidden_paths_missing_destructive_cleanup_category",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate release-candidate publication dry-run planning artifact v1."
    )
    parser.add_argument(
        "plan_path",
        nargs="?",
        default=str(DEFAULT_PLAN_REL),
        help="Path to release-candidate publication dry-run plan JSON.",
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


def _list_has_token(items: List[str], token: str) -> bool:
    token_lower = token.lower()
    return any(token_lower in str(item).lower() for item in items)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    plan_path = (
        Path(args.plan_path).resolve()
        if Path(args.plan_path).is_absolute()
        else (repo_root / args.plan_path).resolve()
    )
    schema_path = (repo_root / DEFAULT_SCHEMA_REL).resolve()
    production_readiness_schema_path = (
        repo_root / DEFAULT_PRODUCTION_READINESS_SCHEMA_REL
    ).resolve()

    if not plan_path.exists():
        print(
            json.dumps(
                {"status": "fail", "error": f"dry-run plan not found: {plan_path}"},
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

    plan = load_json(plan_path)
    schema = load_json(schema_path)
    findings: List[Dict[str, Any]] = []

    ok, schema_errors = validate_schema(plan, schema)
    if not ok:
        for message in schema_errors:
            add_finding(
                findings,
                "schema_validation_error",
                "error",
                "Dry-run plan failed schema validation.",
                {"error": message},
            )

    source_artifacts = (
        plan.get("source_artifacts") if isinstance(plan.get("source_artifacts"), dict) else {}
    )
    matrix_path = resolve_ref_path(
        repo_root,
        str(source_artifacts.get("candidate_matrix_ref", "")).strip() or str(DEFAULT_MATRIX_REL),
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
        str(source_artifacts.get("readiness_rollup_ref", "")).strip() or str(DEFAULT_ROLLUP_REL),
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
        plan.get("source_artifact_validation_status")
        if isinstance(plan.get("source_artifact_validation_status"), dict)
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
                "All source artifact validations must be pass for this static planning slice.",
                {"field": key, "actual": expected},
            )

    candidate_id = str(plan.get("candidate_id", "")).strip()
    candidate_type = str(plan.get("candidate_type", "")).strip()
    admission_status = str(plan.get("admission_status", "")).strip()
    plan_status = str(plan.get("plan_status", "")).strip()
    planning_scope = str(plan.get("planning_scope", "")).strip()

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
    if admission_status != "unadmitted":
        add_finding(
            findings,
            "admission_status_not_unadmitted",
            "error",
            "admission_status must remain unadmitted.",
            {"actual": admission_status},
        )

    if bool(plan.get("dry_run_admitted", False)):
        add_finding(
            findings,
            "dry_run_admitted_not_allowed",
            "error",
            "dry_run_admitted must remain false in this slice.",
        )
    if bool(plan.get("publication_admitted", False)):
        add_finding(
            findings,
            "publication_admitted_not_allowed",
            "error",
            "publication_admitted must remain false in this slice.",
        )
    if bool(plan.get("real_execution_admitted", False)):
        add_finding(
            findings,
            "real_execution_admitted_not_allowed",
            "error",
            "real_execution_admitted must remain false in this slice.",
        )
    if bool(plan.get("production_ready_claimed", False)):
        add_finding(
            findings,
            "production_ready_claim_not_allowed",
            "error",
            "production_ready_claimed must remain false in this slice.",
        )

    if plan_status != EXPECTED_PLAN_STATUS:
        add_finding(
            findings,
            "plan_status_not_static_plan_valid_blocked",
            "error",
            "plan_status must remain static_plan_valid_blocked for this slice.",
            {"actual": plan_status},
        )
    if planning_scope != EXPECTED_SCOPE:
        add_finding(
            findings,
            "planning_scope_mismatch",
            "error",
            "planning_scope must remain candidate_specific_publication_dry_run_planning_only.",
            {"actual": planning_scope},
        )

    if plan.get("publication_surfaces_blocked") is not True:
        add_finding(
            findings,
            "publication_surfaces_blocked_false",
            "error",
            "publication_surfaces_blocked must remain true.",
        )
    if plan.get("execution_surfaces_blocked") is not True:
        add_finding(
            findings,
            "execution_surfaces_blocked_false",
            "error",
            "execution_surfaces_blocked must remain true.",
        )

    missing_evidence_items = as_string_list(plan.get("missing_evidence_items", []))
    if not missing_evidence_items:
        add_finding(
            findings,
            "missing_evidence_items_empty",
            "error",
            "missing_evidence_items must be non-empty.",
        )
    blocked_reason_codes = as_string_list(plan.get("blocked_reason_codes", []))
    if not blocked_reason_codes:
        add_finding(
            findings,
            "blocked_reason_codes_empty",
            "error",
            "blocked_reason_codes must be non-empty.",
        )

    approval_phrase = str(plan.get("approval_phrase_required", "")).strip()
    if approval_phrase != EXPECTED_APPROVAL_PHRASE:
        add_finding(
            findings,
            "approval_phrase_required_mismatch",
            "error",
            "approval_phrase_required must exactly match approved phrase format for candidate.",
            {"expected": EXPECTED_APPROVAL_PHRASE, "actual": approval_phrase},
        )

    approval_decision_reference = plan.get("approval_decision_reference")
    if isinstance(approval_decision_reference, str) and approval_decision_reference.strip():
        add_finding(
            findings,
            "approval_decision_reference_not_allowed",
            "error",
            "approval_decision_reference must be null/empty in this unadmitted planning slice.",
            {"actual": approval_decision_reference},
        )

    out_of_scope = set(as_string_list(plan.get("out_of_scope_surfaces", [])))
    for token, finding_id in OUT_OF_SCOPE_GUARDS.items():
        if token not in out_of_scope:
            add_finding(
                findings,
                finding_id,
                "error",
                "out_of_scope_surfaces must keep blocked surface explicitly out of scope.",
                {"missing_surface": token},
            )

    forbidden_paths = set(as_string_list(plan.get("forbidden_paths", [])))
    for category, finding_id in REQUIRED_FORBIDDEN_PATH_CATEGORIES.items():
        if category not in forbidden_paths:
            add_finding(
                findings,
                finding_id,
                "error",
                "forbidden_paths must include required blocked path category.",
                {"missing_category": category},
            )

    allowed_sandbox_paths = as_string_list(plan.get("allowed_sandbox_paths", []))
    for raw_path in allowed_sandbox_paths:
        normalized = raw_path.replace("\\", "/").lower()
        if not normalized.startswith("examples/sandbox/"):
            add_finding(
                findings,
                "allowed_sandbox_paths_outside_sandbox",
                "error",
                "allowed_sandbox_paths entries must remain under examples/sandbox.",
                {"path": raw_path},
            )

    forbidden_outputs = as_string_list(plan.get("forbidden_outputs", []))
    if not _list_has_token(forbidden_outputs, "publish"):
        add_finding(
            findings,
            "plan_allows_publish",
            "error",
            "forbidden_outputs must explicitly block publish outputs.",
        )
    if not _list_has_token(forbidden_outputs, "spawn"):
        add_finding(
            findings,
            "plan_allows_spawn",
            "error",
            "forbidden_outputs must explicitly block spawn outputs.",
        )

    future_outputs = as_string_list(plan.get("future_allowed_sandbox_outputs", []))
    for output in future_outputs:
        normalized = output.replace("\\", "/").lower()
        if "production" in normalized:
            add_finding(
                findings,
                "future_allowed_sandbox_outputs_contains_production_path",
                "error",
                "future_allowed_sandbox_outputs must not include production paths.",
                {"output": output},
            )
        if "engine" in normalized:
            add_finding(
                findings,
                "future_allowed_sandbox_outputs_contains_engine_path",
                "error",
                "future_allowed_sandbox_outputs must not include engine paths.",
                {"output": output},
            )
        if not normalized.startswith("examples/sandbox/"):
            add_finding(
                findings,
                "future_allowed_sandbox_outputs_outside_sandbox",
                "error",
                "future_allowed_sandbox_outputs must remain under examples/sandbox.",
                {"output": output},
            )

    claim_status = plan.get("claim_status") if isinstance(plan.get("claim_status"), dict) else {}
    if str(claim_status.get("source_uuid_status", "")).strip() != "not_authoritative":
        add_finding(
            findings,
            "authoritative_source_uuid_claim_allowed",
            "error",
            "source_uuid_status must remain not_authoritative.",
            {"actual": claim_status.get("source_uuid_status")},
        )
    if str(claim_status.get("asset_id_status", "")).strip() != "not_authoritative":
        add_finding(
            findings,
            "authoritative_asset_id_claim_allowed",
            "error",
            "asset_id_status must remain not_authoritative.",
            {"actual": claim_status.get("asset_id_status")},
        )
    if str(claim_status.get("product_id_status", "")).strip() != "not_authoritative":
        add_finding(
            findings,
            "authoritative_product_id_claim_allowed",
            "error",
            "product_id_status must remain not_authoritative.",
            {"actual": claim_status.get("product_id_status")},
        )

    if bool(plan.get("unsafe_claims_detected", False)):
        add_finding(
            findings,
            "unsafe_claims_detected_not_allowed",
            "error",
            "unsafe_claims_detected must remain false.",
        )

    for required_key in (
        "required_future_receipts",
        "required_future_validators",
        "required_future_tests",
        "required_future_rollback_or_cleanup_evidence",
    ):
        if not as_string_list(plan.get(required_key, [])):
            add_finding(
                findings,
                "required_future_requirements_missing",
                "error",
                "Future requirement arrays must be non-empty.",
                {"field": required_key},
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
                "Target dry-run candidate must not be admitted in matrix in this slice.",
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
                "Target dry-run candidate must keep preflight_passed=false.",
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

    matrix_status_from_matrix = (
        str(matrix_entry.get("current_status", "")).strip()
        if isinstance(matrix_entry, dict)
        else ""
    )
    preflight_matrix_status = (
        str(preflight_entry.get("current_candidate_matrix_status", "")).strip()
        if isinstance(preflight_entry, dict)
        else ""
    )
    proof_matrix_status = (
        str(proof_entry.get("matrix_candidate_status", "")).strip()
        if isinstance(proof_entry, dict)
        else ""
    )
    rollup_matrix_status = (
        str(rollup_entry.get("matrix_status", "")).strip()
        if isinstance(rollup_entry, dict)
        else ""
    )
    if (
        matrix_status_from_matrix
        and preflight_matrix_status
        and matrix_status_from_matrix != preflight_matrix_status
    ):
        add_finding(
            findings,
            "candidate_matrix_status_mismatch_with_preflight_contracts",
            "error",
            "Target candidate matrix status must match preflight contracts.",
            {
                "matrix_current_status": matrix_status_from_matrix,
                "preflight_current_candidate_matrix_status": preflight_matrix_status,
            },
        )
    if matrix_status_from_matrix and proof_matrix_status and matrix_status_from_matrix != proof_matrix_status:
        add_finding(
            findings,
            "candidate_matrix_status_mismatch_with_preflight_proof_packages",
            "error",
            "Target candidate matrix status must match preflight proof packages.",
            {
                "matrix_current_status": matrix_status_from_matrix,
                "preflight_proof_matrix_candidate_status": proof_matrix_status,
            },
        )
    if matrix_status_from_matrix and rollup_matrix_status and matrix_status_from_matrix != rollup_matrix_status:
        add_finding(
            findings,
            "candidate_matrix_status_mismatch_with_readiness_rollup",
            "error",
            "Target candidate matrix status must match readiness rollup.",
            {
                "matrix_current_status": matrix_status_from_matrix,
                "rollup_matrix_status": rollup_matrix_status,
            },
        )

    blocked_dry_run_ids = set(
        as_string_list(rollup_payload.get("blocked_dry_run_candidate_ids", []))
    )
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
            "Readiness rollup safest_next_preparation_slice_id must remain candidate_specific_dry_run_planning_v1.",
            {"actual": next_slice_id},
        )
    if next_slice_candidate != TARGET_CANDIDATE_ID:
        add_finding(
            findings,
            "readiness_rollup_safest_next_candidate_mismatch",
            "error",
            "Readiness rollup safest next preparation candidate must be release_candidate_package_publish_dry_run_v1.",
            {"actual": next_slice_candidate},
        )

    alignment = (
        plan.get("readiness_rollup_alignment")
        if isinstance(plan.get("readiness_rollup_alignment"), dict)
        else {}
    )
    if str(alignment.get("safest_next_preparation_slice_id", "")).strip() != next_slice_id:
        add_finding(
            findings,
            "readiness_rollup_alignment_slice_mismatch",
            "error",
            "readiness_rollup_alignment slice id must match referenced readiness rollup.",
            {
                "plan": alignment.get("safest_next_preparation_slice_id"),
                "rollup": next_slice_id,
            },
        )
    if str(alignment.get("safest_next_preparation_candidate_id", "")).strip() != next_slice_candidate:
        add_finding(
            findings,
            "readiness_rollup_alignment_candidate_mismatch",
            "error",
            "readiness_rollup_alignment candidate id must match referenced readiness rollup.",
            {
                "plan": alignment.get("safest_next_preparation_candidate_id"),
                "rollup": next_slice_candidate,
            },
        )
    if str(alignment.get("alignment_status", "")).strip() != "aligned":
        add_finding(
            findings,
            "readiness_rollup_alignment_status_not_aligned",
            "error",
            "readiness_rollup_alignment must keep alignment_status=aligned.",
        )

    if bool(next_slice.get("admits_publication", False)):
        add_finding(
            findings,
            "plan_allows_publish",
            "error",
            "Readiness rollup safest-next slice must not admit publication.",
        )
    if bool(next_slice.get("admits_execution", False)):
        add_finding(
            findings,
            "real_execution_admitted_not_allowed",
            "error",
            "Readiness rollup safest-next slice must not admit execution.",
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

    severity_set = {str(item.get("severity", "")).strip() for item in findings}
    status = "fail" if "error" in severity_set else "pass"

    report_payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_VALIDATION_v1_REPORT",
        "status": status,
        "release_candidate_publication_dry_run_plan_present": True,
        "dry_run_plan_path": str(plan_path),
        "candidate_matrix_path": str(matrix_path),
        "preflight_contracts_path": str(preflight_path),
        "preflight_proof_packages_path": str(preflight_proof_path),
        "readiness_rollup_path": str(rollup_path),
        "production_readiness_report_path": str(production_readiness_path),
        "noop_receipt_status_path": str(noop_decision_path),
        "source_artifact_validation_status": source_status_reported,
        "computed_source_artifact_validation_status": source_status_expected,
        "planned_candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "plan_status": plan_status,
        "dry_run_admitted": bool(plan.get("dry_run_admitted", False)),
        "publication_admitted": bool(plan.get("publication_admitted", False)),
        "real_execution_admitted": bool(plan.get("real_execution_admitted", False)),
        "production_ready_claimed": bool(plan.get("production_ready_claimed", False)),
        "publication_surfaces_blocked": bool(plan.get("publication_surfaces_blocked", False)),
        "execution_surfaces_blocked": bool(plan.get("execution_surfaces_blocked", False)),
        "readiness_rollup_alignment": alignment,
        "missing_evidence_items_count": len(missing_evidence_items),
        "blocked_reason_codes": blocked_reason_codes,
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
