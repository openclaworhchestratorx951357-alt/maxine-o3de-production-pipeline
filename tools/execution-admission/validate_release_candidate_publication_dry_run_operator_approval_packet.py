#!/usr/bin/env python3
"""Validate release-candidate publication dry-run operator approval packet template v1."""

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
EXPECTED_PACKET_STATUS = "static_template_valid_blocked"
EXPECTED_ROLLUP_STATUS = "static_rollup_valid_blocked"
EXPECTED_DRY_RUN_PLAN_STATUS = "static_plan_valid_blocked"
EXPECTED_RECEIPT_CONTRACT_STATUS = "static_contract_valid_blocked"
EXPECTED_ADMISSION_BLOCKER_STATUS = "static_checklist_valid_blocked"
EXPECTED_NEXT_SLICE_ID = "candidate_specific_dry_run_planning_v1"
EXPECTED_BLOCKED_RECEIPT_STATUS = "blocked_unissued_contract_only"
EXPECTED_DEFAULT_OPERATOR_DECISION = "do_not_approve"

DEFAULT_PACKET_REL = Path(
    "examples/execution-admission/"
    "release_candidate_package_publish_dry_run_operator_approval_packet_v1.json"
)
DEFAULT_SCHEMA_REL = Path(
    "schemas/maxine_release_candidate_publication_dry_run_operator_approval_packet.schema.json"
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

REQUIRED_SOURCE_REFERENCE_FIELDS = {
    "candidate_matrix_ref",
    "preflight_contracts_ref",
    "preflight_proof_packages_ref",
    "readiness_rollup_ref",
    "dry_run_plan_ref",
    "dry_run_receipt_contract_ref",
    "blocked_unissued_receipt_ref",
    "admission_blocker_checklist_ref",
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
    "production_readiness_status",
    "noop_receipt_status",
)

REQUIRED_OPERATOR_REVIEW_ITEMS = {
    "candidate_identity_and_candidate_type": "required_operator_review_items_missing_candidate_identity",
    "current_admission_status": "required_operator_review_items_missing_current_admission_status",
    "source_artifact_validation_summary": "required_operator_review_items_missing_source_validation_summary",
    "admission_blocker_checklist_summary": "required_operator_review_items_missing_blocker_checklist_summary",
    "dry_run_plan_summary": "required_operator_review_items_missing_dry_run_plan_summary",
    "dry_run_receipt_contract_summary": "required_operator_review_items_missing_dry_run_receipt_contract_summary",
    "blocked_unissued_receipt_summary": "required_operator_review_items_missing_blocked_receipt_summary",
    "required_approval_phrase": "required_operator_review_items_missing_required_approval_phrase",
    "required_future_validation_commands": "required_operator_review_items_missing_required_validation_commands",
    "rollback_noop_cleanup_expectations": "required_operator_review_items_missing_rollback_expectations",
    "forbidden_surfaces": "required_operator_review_items_missing_forbidden_surfaces",
    "forbidden_outputs": "required_operator_review_items_missing_forbidden_outputs",
    "forbidden_paths": "required_operator_review_items_missing_forbidden_paths",
    "operator_decision_options": "required_operator_review_items_missing_operator_decision_options",
    "post_approval_control_expectations": "required_operator_review_items_missing_post_approval_controls",
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
    "tools/audit/verify_sandbox_writer_safety.py": (
        "required_validation_commands_missing_safety_verifier"
    ),
    "tools/release-lane/prove_pilot_release_chain.py": (
        "required_validation_commands_missing_proof_flow"
    ),
}

REQUIRED_FORBIDDEN_PATH_CATEGORIES = {
    "production_path_category": "forbidden_paths_missing_production_category",
    "engine_path_category": "forbidden_paths_missing_engine_category",
    "cache_live_db_category": "forbidden_paths_missing_cache_live_db_category",
    "destructive_cleanup_category": "forbidden_paths_missing_destructive_cleanup_category",
}

REQUIRED_FORBIDDEN_OUTPUTS = {
    "publish_operation": "packet_allows_publish",
    "spawn_operation": "packet_allows_spawn",
    "production_path_writes": "packet_allows_production_path_writes",
    "engine_path_writes": "packet_allows_engine_path_writes",
    "cache_live_db_access": "packet_allows_cache_live_db_access",
    "authoritative_source_uuid_claims": "packet_allows_authoritative_source_uuid_claims",
    "authoritative_asset_id_claims": "packet_allows_authoritative_asset_id_claims",
    "authoritative_product_id_claims": "packet_allows_authoritative_product_id_claims",
}

REQUIRED_FORBIDDEN_ACTIONS = {
    "publish_operation": "forbidden_actions_missing_publish_category",
    "spawn_operation": "forbidden_actions_missing_spawn_category",
}

REQUIRED_BLOCKED_SURFACE_ATTESTATIONS = {
    "publication_surfaces_blocked_by_policy": "blocked_surface_attestations_missing_publication_block",
    "execution_surfaces_blocked_by_policy": "blocked_surface_attestations_missing_execution_block",
}

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate release-candidate publication dry-run operator approval packet "
            "template v1."
        )
    )
    parser.add_argument(
        "packet_path",
        nargs="?",
        default=str(DEFAULT_PACKET_REL),
        help="Path to release-candidate publication dry-run operator approval packet JSON.",
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
        ("publish allowed", "packet_allows_publish"),
        ("spawn allowed", "packet_allows_spawn"),
        ("production path writes allowed", "packet_allows_production_path_writes"),
        ("engine path writes allowed", "packet_allows_engine_path_writes"),
        ("cache/live db access allowed", "packet_allows_cache_live_db_access"),
        ("cache live db access allowed", "packet_allows_cache_live_db_access"),
        (
            "authoritative source uuid claims allowed",
            "packet_allows_authoritative_source_uuid_claims",
        ),
        (
            "authoritative asset id claims allowed",
            "packet_allows_authoritative_asset_id_claims",
        ),
        (
            "authoritative product id claims allowed",
            "packet_allows_authoritative_product_id_claims",
        ),
    )
    for needle, finding_id in checks:
        if needle in text:
            add_finding(
                findings,
                finding_id,
                "error",
                "Operator approval packet text must not allow blocked surfaces.",
                {"needle": needle},
            )


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    packet_path = (
        Path(args.packet_path).resolve()
        if Path(args.packet_path).is_absolute()
        else (repo_root / args.packet_path).resolve()
    )
    schema_path = (repo_root / DEFAULT_SCHEMA_REL).resolve()

    if not packet_path.exists():
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": f"operator approval packet not found: {packet_path}",
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

    packet = load_json(packet_path)
    schema = load_json(schema_path)
    findings: List[Dict[str, Any]] = []

    ok, schema_errors = validate_schema(packet, schema)
    if not ok:
        for message in schema_errors:
            add_finding(
                findings,
                "schema_validation_error",
                "error",
                "Operator approval packet failed schema validation.",
                {"error": message},
            )

    source_artifacts = (
        packet.get("source_artifacts")
        if isinstance(packet.get("source_artifacts"), dict)
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
    admission_blockers_path = resolve_ref_path(
        repo_root,
        str(source_artifacts.get("admission_blocker_checklist_ref", "")).strip()
        or str(DEFAULT_ADMISSION_BLOCKERS_REL),
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
        ("admission_blocker_checklist", admission_blockers_path),
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
    admission_blockers_payload = (
        load_json(admission_blockers_path) if admission_blockers_path.exists() else {}
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

    (
        dry_run_receipt_contract_code,
        dry_run_receipt_contract_report,
        dry_run_receipt_contract_parse_error,
    ) = run_validator(
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
    elif dry_run_receipt_contract_code != 0 or str(
        dry_run_receipt_contract_report.get("status", "")
    ).strip() != "pass":
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

    (
        blocked_receipt_code,
        blocked_receipt_report,
        blocked_receipt_parse_error,
    ) = run_validator(
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

    (
        admission_blockers_code,
        admission_blockers_report,
        admission_blockers_parse_error,
    ) = run_validator(
        repo_root,
        ADMISSION_BLOCKERS_VALIDATOR_REL,
        [str(admission_blockers_path)],
    )
    if admission_blockers_report is None:
        add_finding(
            findings,
            "admission_blockers_validator_output_invalid",
            "error",
            "Admission blocker checklist validator did not return parseable JSON.",
            {"error": admission_blockers_parse_error or "unknown parse error"},
        )
    elif admission_blockers_code != 0 or str(admission_blockers_report.get("status", "")).strip() != "pass":
        add_finding(
            findings,
            "admission_blockers_validation_failed",
            "error",
            "Admission blocker checklist validation must pass.",
            {"return_code": admission_blockers_code, "status": admission_blockers_report.get("status")},
        )

    source_status_expected = {
        "candidate_matrix_status": (
            "pass"
            if matrix_code == 0 and matrix_report and matrix_report.get("status") == "pass"
            else "fail"
        ),
        "preflight_contracts_status": (
            "pass"
            if preflight_code == 0 and preflight_report and preflight_report.get("status") == "pass"
            else "fail"
        ),
        "preflight_proof_packages_status": (
            "pass"
            if preflight_proof_code == 0
            and preflight_proof_report
            and preflight_proof_report.get("status") == "pass"
            else "fail"
        ),
        "readiness_rollup_status": (
            "pass"
            if rollup_code == 0 and rollup_report and rollup_report.get("status") == "pass"
            else "fail"
        ),
        "dry_run_plan_status": (
            "pass"
            if dry_run_plan_code == 0 and dry_run_plan_report and dry_run_plan_report.get("status") == "pass"
            else "fail"
        ),
        "dry_run_receipt_contract_status": (
            "pass"
            if dry_run_receipt_contract_code == 0
            and dry_run_receipt_contract_report
            and dry_run_receipt_contract_report.get("status") == "pass"
            else "fail"
        ),
        "blocked_unissued_receipt_status": (
            "pass"
            if blocked_receipt_code == 0 and blocked_receipt_report and blocked_receipt_report.get("status") == "pass"
            else "fail"
        ),
        "admission_blocker_checklist_status": (
            "pass"
            if admission_blockers_code == 0
            and admission_blockers_report
            and admission_blockers_report.get("status") == "pass"
            else "fail"
        ),
        "production_readiness_status": _validate_production_readiness_report(
            production_readiness_payload,
            findings,
        ),
        "noop_receipt_status": _validate_noop_decision_record(
            noop_decision_payload,
            findings,
        ),
    }

    source_status_reported = (
        packet.get("source_artifact_validation_status")
        if isinstance(packet.get("source_artifact_validation_status"), dict)
        else {}
    )
    for key in SOURCE_STATUS_KEYS:
        expected = source_status_expected[key]
        actual = str(source_status_reported.get(key, "")).strip()
        if actual != expected:
            add_finding(
                findings,
                "source_artifact_validation_status_mismatch",
                "error",
                "source_artifact_validation_status must match computed source validator statuses.",
                {"field": key, "expected": expected, "actual": actual},
            )

    candidate_id = str(packet.get("candidate_id", "")).strip()
    if candidate_id != TARGET_CANDIDATE_ID:
        add_finding(
            findings,
            "candidate_id_mismatch",
            "error",
            "candidate_id must match release_candidate_package_publish_dry_run_v1.",
            {"actual": candidate_id},
        )
    candidate_type = str(packet.get("candidate_type", "")).strip()
    if candidate_type != TARGET_CANDIDATE_TYPE:
        add_finding(
            findings,
            "candidate_type_mismatch",
            "error",
            "candidate_type must be dry_run.",
            {"actual": candidate_type},
        )

    packet_status = str(packet.get("approval_packet_status", "")).strip()
    if packet_status != EXPECTED_PACKET_STATUS:
        add_finding(
            findings,
            "approval_packet_status_not_static_template_valid_blocked",
            "error",
            "approval_packet_status must be static_template_valid_blocked.",
            {"actual": packet_status},
        )
    admission_status = str(packet.get("admission_status", "")).strip()
    if admission_status != "unadmitted":
        add_finding(
            findings,
            "admission_status_not_unadmitted",
            "error",
            "admission_status must be unadmitted.",
            {"actual": admission_status},
        )

    for field, finding_id in REQUIRED_FLAG_FALSE_FIELDS:
        if packet.get(field) is not False:
            add_finding(
                findings,
                finding_id,
                "error",
                "Operator approval packet blocked posture flags must remain false.",
                {"field": field, "actual": packet.get(field)},
            )

    approval_phrase = str(packet.get("approval_phrase_required", "")).strip()
    if approval_phrase != EXPECTED_APPROVAL_PHRASE:
        add_finding(
            findings,
            "approval_phrase_required_mismatch",
            "error",
            "approval_phrase_required must match exact candidate-specific phrase.",
            {"actual": approval_phrase},
        )

    approval_decision_reference = packet.get("approval_decision_reference")
    if isinstance(approval_decision_reference, str):
        if approval_decision_reference.strip():
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

    approval_decision_fields = (
        packet.get("approval_decision_fields")
        if isinstance(packet.get("approval_decision_fields"), dict)
        else {}
    )
    for field, value in approval_decision_fields.items():
        if isinstance(value, str):
            if value.strip():
                add_finding(
                    findings,
                    "approval_decision_fields_not_empty",
                    "error",
                    "approval_decision_fields must remain null/empty in template-only blocked posture.",
                    {"field": field, "actual": value},
                )
        elif value is not None:
            add_finding(
                findings,
                "approval_decision_fields_not_empty",
                "error",
                "approval_decision_fields must remain null/empty in template-only blocked posture.",
                {"field": field, "actual": value},
            )

    if bool(packet.get("unsafe_claims_detected", False)):
        add_finding(
            findings,
            "unsafe_claims_detected_not_allowed",
            "error",
            "unsafe_claims_detected must remain false.",
        )

    operator_review_summary = _check_non_empty_string_list(
        packet,
        "operator_review_summary",
        findings,
        "operator_review_summary_missing_or_empty",
        "operator_review_summary must be present and non-empty.",
    )
    approval_blocker_summary = _check_non_empty_string_list(
        packet,
        "approval_blocker_summary",
        findings,
        "approval_blocker_summary_missing_or_empty",
        "approval_blocker_summary must be present and non-empty.",
    )
    required_operator_review_items = _check_non_empty_string_list(
        packet,
        "required_operator_review_items",
        findings,
        "required_operator_review_items_missing_or_empty",
        "required_operator_review_items must be present and non-empty.",
    )
    required_validation_commands = _check_non_empty_string_list(
        packet,
        "required_validation_commands",
        findings,
        "required_validation_commands_missing_or_empty",
        "required_validation_commands must be present and non-empty.",
    )
    blocked_surface_attestations = _check_non_empty_string_list(
        packet,
        "blocked_surface_attestations",
        findings,
        "blocked_surface_attestations_missing_or_empty",
        "blocked_surface_attestations must be present and non-empty.",
    )
    forbidden_actions = _check_non_empty_string_list(
        packet,
        "forbidden_actions",
        findings,
        "forbidden_actions_missing_or_empty",
        "forbidden_actions must be present and non-empty.",
    )
    forbidden_outputs = _check_non_empty_string_list(
        packet,
        "forbidden_outputs",
        findings,
        "forbidden_outputs_missing_or_empty",
        "forbidden_outputs must be present and non-empty.",
    )
    forbidden_paths = _check_non_empty_string_list(
        packet,
        "forbidden_paths",
        findings,
        "forbidden_paths_missing_or_empty",
        "forbidden_paths must be present and non-empty.",
    )
    _check_non_empty_string_list(
        packet,
        "rollback_or_cleanup_expectations",
        findings,
        "rollback_or_cleanup_expectations_missing_or_empty",
        "rollback_or_cleanup_expectations must be present and non-empty.",
    )
    _check_non_empty_string_list(
        packet,
        "required_post_approval_controls",
        findings,
        "required_post_approval_controls_missing_or_empty",
        "required_post_approval_controls must be present and non-empty.",
    )

    review_items_set = set(required_operator_review_items)
    for token, finding_id in REQUIRED_OPERATOR_REVIEW_ITEMS.items():
        if token not in review_items_set:
            add_finding(
                findings,
                finding_id,
                "error",
                "required_operator_review_items is missing required token.",
                {"token": token},
            )

    required_commands_set = set(required_validation_commands)
    for token, finding_id in REQUIRED_VALIDATION_COMMANDS.items():
        if token not in required_commands_set:
            add_finding(
                findings,
                finding_id,
                "error",
                "required_validation_commands is missing required validator/proof command.",
                {"token": token},
            )

    blocked_attestations_set = set(blocked_surface_attestations)
    for token, finding_id in REQUIRED_BLOCKED_SURFACE_ATTESTATIONS.items():
        if token not in blocked_attestations_set:
            add_finding(
                findings,
                finding_id,
                "error",
                "blocked_surface_attestations is missing required blocked-surface token.",
                {"token": token},
            )

    forbidden_actions_set = set(forbidden_actions)
    for token, finding_id in REQUIRED_FORBIDDEN_ACTIONS.items():
        if token not in forbidden_actions_set:
            add_finding(
                findings,
                finding_id,
                "error",
                "forbidden_actions is missing required blocked action token.",
                {"token": token},
            )

    forbidden_outputs_set = set(forbidden_outputs)
    for token, finding_id in REQUIRED_FORBIDDEN_OUTPUTS.items():
        if token not in forbidden_outputs_set:
            add_finding(
                findings,
                finding_id,
                "error",
                "forbidden_outputs is missing required blocked output token.",
                {"token": token},
            )

    forbidden_paths_set = set(forbidden_paths)
    for token, finding_id in REQUIRED_FORBIDDEN_PATH_CATEGORIES.items():
        if token not in forbidden_paths_set:
            add_finding(
                findings,
                finding_id,
                "error",
                "forbidden_paths is missing required blocked path category token.",
                {"token": token},
            )

    operator_decision_options = (
        packet.get("operator_decision_options")
        if isinstance(packet.get("operator_decision_options"), dict)
        else {}
    )
    allowed_options = as_string_list(operator_decision_options.get("allowed_options"))
    if not allowed_options:
        add_finding(
            findings,
            "operator_decision_options_missing_allowed_options",
            "error",
            "operator_decision_options.allowed_options must be non-empty.",
        )
    default_option = str(operator_decision_options.get("default_option", "")).strip()
    if default_option != EXPECTED_DEFAULT_OPERATOR_DECISION:
        add_finding(
            findings,
            "operator_decision_default_not_safe_blocked_state",
            "error",
            "operator_decision_options.default_option must remain do_not_approve.",
            {"actual": default_option},
        )
    if default_option in {"approve_later_with_exact_phrase", "approve", "approved"}:
        add_finding(
            findings,
            "operator_decision_default_not_safe_blocked_state",
            "error",
            "operator_decision_options.default_option must not be approving.",
            {"actual": default_option},
        )

    expected_future_receipt_contract = (
        packet.get("expected_future_receipt_contract")
        if isinstance(packet.get("expected_future_receipt_contract"), dict)
        else {}
    )
    if str(expected_future_receipt_contract.get("receipt_type", "")).strip() != TARGET_RECEIPT_TYPE:
        add_finding(
            findings,
            "expected_future_receipt_contract_type_mismatch",
            "error",
            "expected_future_receipt_contract.receipt_type must match target receipt type.",
            {"actual": expected_future_receipt_contract.get("receipt_type")},
        )
    if (
        str(expected_future_receipt_contract.get("receipt_contract_status_expected", "")).strip()
        != EXPECTED_RECEIPT_CONTRACT_STATUS
    ):
        add_finding(
            findings,
            "expected_future_receipt_contract_status_mismatch",
            "error",
            "expected_future_receipt_contract.receipt_contract_status_expected must remain static_contract_valid_blocked.",
            {"actual": expected_future_receipt_contract.get("receipt_contract_status_expected")},
        )

    receipt_contract_ref = str(expected_future_receipt_contract.get("receipt_contract_ref", "")).strip()
    if receipt_contract_ref != str(source_artifacts.get("dry_run_receipt_contract_ref", "")).strip():
        add_finding(
            findings,
            "expected_future_receipt_contract_ref_mismatch",
            "error",
            "expected_future_receipt_contract.receipt_contract_ref must match source_artifacts.dry_run_receipt_contract_ref.",
            {
                "expected_future_receipt_contract_ref": receipt_contract_ref,
                "source_artifacts_ref": source_artifacts.get("dry_run_receipt_contract_ref"),
            },
        )

    safety_posture = (
        packet.get("safety_posture")
        if isinstance(packet.get("safety_posture"), dict)
        else {}
    )
    for field, expected in (
        ("source_uuid_status", "not_authoritative"),
        ("asset_id_status", "not_authoritative"),
        ("product_id_status", "not_authoritative"),
    ):
        if str(safety_posture.get(field, "")).strip() != expected:
            add_finding(
                findings,
                "authoritative_id_claim_not_allowed",
                "error",
                "safety_posture must keep ID claims non-authoritative.",
                {"field": field, "expected": expected, "actual": safety_posture.get(field)},
            )

    _check_forbidden_claim_language(packet, findings)

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
        if bool(rollup_entry.get("preflight_passed", False)):
            add_finding(
                findings,
                "dry_run_preflight_passed_not_allowed",
                "error",
                "Target candidate must keep preflight_passed=false in readiness rollup.",
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
    if bool(next_slice.get("admits_execution", False)):
        add_finding(
            findings,
            "packet_allows_real_execution_admission",
            "error",
            "Readiness rollup safest-next slice must keep admits_execution=false.",
        )
    if bool(next_slice.get("admits_publication", False)):
        add_finding(
            findings,
            "packet_allows_publication_admission",
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
    if str(dry_run_receipt_contract_payload.get("receipt_type", "")).strip() != TARGET_RECEIPT_TYPE:
        add_finding(
            findings,
            "dry_run_receipt_contract_type_mismatch",
            "error",
            "Referenced dry-run receipt contract must keep receipt_type=release_candidate_package_publish_dry_run_receipt_v1.",
            {"actual": dry_run_receipt_contract_payload.get("receipt_type")},
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

    if str(admission_blockers_payload.get("checklist_status", "")).strip() != EXPECTED_ADMISSION_BLOCKER_STATUS:
        add_finding(
            findings,
            "admission_blocker_checklist_status_not_expected",
            "error",
            "Referenced admission blocker checklist must keep checklist_status=static_checklist_valid_blocked.",
            {"actual": admission_blockers_payload.get("checklist_status")},
        )
    if str(admission_blockers_payload.get("admission_status", "")).strip() != "unadmitted":
        add_finding(
            findings,
            "admission_blocker_checklist_admission_status_not_unadmitted",
            "error",
            "Referenced admission blocker checklist must keep admission_status=unadmitted.",
            {"actual": admission_blockers_payload.get("admission_status")},
        )
    if admission_blockers_payload.get("approval_review_ready") is not False:
        add_finding(
            findings,
            "admission_blocker_checklist_approval_review_ready_not_false",
            "error",
            "Referenced admission blocker checklist must keep approval_review_ready=false.",
            {"actual": admission_blockers_payload.get("approval_review_ready")},
        )
    if admission_blockers_payload.get("ready_to_request_approval") is not False:
        add_finding(
            findings,
            "admission_blocker_checklist_ready_to_request_approval_not_false",
            "error",
            "Referenced admission blocker checklist must keep ready_to_request_approval=false.",
            {"actual": admission_blockers_payload.get("ready_to_request_approval")},
        )

    severity_set = {str(item.get("severity", "")).strip() for item in findings}
    status = "fail" if "error" in severity_set else "pass"

    report_payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_OPERATOR_APPROVAL_PACKET_VALIDATION_v1_REPORT",
        "status": status,
        "release_candidate_publication_dry_run_operator_approval_packet_present": True,
        "release_candidate_publication_dry_run_operator_approval_packet_path": str(packet_path),
        "candidate_matrix_path": str(matrix_path),
        "preflight_contracts_path": str(preflight_path),
        "preflight_proof_packages_path": str(preflight_proof_path),
        "readiness_rollup_path": str(rollup_path),
        "dry_run_plan_path": str(dry_run_plan_path),
        "dry_run_receipt_contract_path": str(dry_run_receipt_contract_path),
        "blocked_unissued_receipt_path": str(dry_run_receipt_blocked_path),
        "admission_blocker_checklist_path": str(admission_blockers_path),
        "production_readiness_report_path": str(production_readiness_path),
        "noop_receipt_status_path": str(noop_decision_path),
        "source_artifact_validation_status": source_status_reported,
        "computed_source_artifact_validation_status": source_status_expected,
        "planned_candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "approval_packet_status": packet_status,
        "admission_status": admission_status,
        "approval_request_ready": bool(packet.get("approval_request_ready", False)),
        "operator_approval_granted": bool(packet.get("operator_approval_granted", False)),
        "approval_phrase_present": bool(packet.get("approval_phrase_present", False)),
        "dry_run_admitted": bool(packet.get("dry_run_admitted", False)),
        "receipt_issued": bool(packet.get("receipt_issued", False)),
        "publication_admitted": bool(packet.get("publication_admitted", False)),
        "real_execution_admitted": bool(packet.get("real_execution_admitted", False)),
        "production_ready_claimed": bool(packet.get("production_ready_claimed", False)),
        "approval_phrase_required": approval_phrase,
        "approval_blocker_summary": approval_blocker_summary,
        "required_operator_review_items": required_operator_review_items,
        "required_validation_commands": required_validation_commands,
        "blocked_surface_attestations": blocked_surface_attestations,
        "forbidden_actions": forbidden_actions,
        "forbidden_outputs": forbidden_outputs,
        "forbidden_paths": forbidden_paths,
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
