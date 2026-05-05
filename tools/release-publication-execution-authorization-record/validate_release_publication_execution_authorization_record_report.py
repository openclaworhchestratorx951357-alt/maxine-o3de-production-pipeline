#!/usr/bin/env python3
"""Validate evidence-only release publication execution authorization record reports."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "RELEASE_PUBLICATION_EXECUTION_AUTHORIZATION_RECORD_v1_REPORT"
EXPECTED_CONTRACT_ID = "RELEASE_PUBLICATION_EXECUTION_AUTHORIZATION_RECORD_v1"
EXPECTED_REQUEST_ACTION = "record_release_publication_execution_authorization"
EXPECTED_REVIEW_SCOPE = "release_publication_chain"
EXPECTED_READY_DECISION = "execution_authorization_recorded_for_future_manual_execution_window"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "release_publication_execution_authorization_record_v1"
CONTRACT_ID = "RELEASE_PUBLICATION_EXECUTION_AUTHORIZATION_RECORD_v1"

REQUIRED_ARTIFACT_HINTS = {
    "manifest": "manifest.json",
    "release_package_bundle": "release-package-bundle",
    "release_promotion_decision": "release-promotion-decision",
    "release_publication_execution_admission_review": "release-publication-execution-admission-review",
    "release_publication_preflight": "release-publication-preflight",
    "release_publication_request_approval": "release-publication-request-approval",
    "release_publication_execution_admission_gate": "release-publication-execution-admission-gate",
    "release_publication_execution_request_ledger": "release-publication-execution-request-ledger",
    "release_publication_execution_receipt": "release-publication-execution-receipt",
    "release_publication_rollback_drill": "release-publication-rollback-drill",
    "release_publication_evidence_integrity_index": "release-publication-evidence-integrity-index",
    "publication_log": "publication-manual.log",
    "rollback_drill_log": "rollback-drill-manual.log",
    "post_rollback_validation_log": "post-rollback-validation.log",
}

DISALLOWED_ARTIFACT_TOKENS = (
    "cache/",
    "cache\\",
    "assetdb.sqlite",
    ".fbx",
    ".gltf",
    ".glb",
    ".obj",
    ".png",
    ".jpg",
    ".jpeg",
    ".exe",
    ".dll",
    ".bin",
    ".sqlite",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"Failed to parse JSON: {path} ({exc})") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate MAXINE release publication execution authorization record report JSON."
    )
    parser.add_argument("report_path", help="Path to release publication execution authorization record report JSON")
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Return zero exit code for warn status",
    )
    return parser.parse_args()


def add_finding(
    findings: List[Dict[str, Any]],
    finding_id: str,
    severity: str,
    status: str,
    message: str,
    details: Dict[str, Any] | None = None,
) -> None:
    item: Dict[str, Any] = {
        "id": finding_id,
        "severity": severity,
        "status": status,
        "message": message,
    }
    if details:
        item["details"] = details
    findings.append(item)


def validate_schema_with_jsonschema(report: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    try:
        from jsonschema import Draft202012Validator
    except Exception as exc:
        return False, [f"jsonschema import failed: {exc}"]

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(report), key=lambda err: list(err.path))
    if not errors:
        return True, []

    messages: List[str] = []
    for err in errors:
        location = ".".join(str(p) for p in err.absolute_path) or "<root>"
        messages.append(f"{location}: {err.message}")
    return False, messages


def derive_status(findings: List[Dict[str, Any]]) -> str:
    severities = {str(item.get("severity", "")) for item in findings}
    if "error" in severities:
        return "fail"
    if "manual_review" in severities:
        return "pending_manual"
    if "warning" in severities:
        return "warn"
    return "pass"


def status_to_qc_severity(status: str) -> str:
    if status == "pass":
        return "info"
    if status == "warn":
        return "warning"
    if status == "pending_manual":
        return "manual_review"
    return "error"


def _contains_unsafe_path_tokens(path_text: str) -> bool:
    blocked = ("..", "|", ";", ">", "<", "&", "`", "\\", ":\\")
    lowered = path_text.lower()
    return any(token in lowered for token in blocked)


def _is_string_array(raw: Any) -> bool:
    return isinstance(raw, list) and all(isinstance(x, str) and x.strip() for x in raw)


def _normalize_string_list(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    return sorted(set(str(x).strip() for x in raw if isinstance(x, str) and str(x).strip()))


def _is_likely_sha256(value: str) -> bool:
    text = value.strip().lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    report_path = resolve_path(repo_root, args.report_path)
    schema_path = repo_root / "schemas" / "maxine_release_publication_execution_authorization_record_report.schema.json"

    if not report_path.exists():
        print(f"FAIL: report not found: {report_path}")
        return 2
    if not schema_path.exists():
        print(f"FAIL: schema not found: {schema_path}")
        return 2

    try:
        report = load_json(report_path)
        schema = load_json(schema_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    findings: List[Dict[str, Any]] = []

    has_jsonschema = False
    try:
        import jsonschema  # noqa: F401

        has_jsonschema = True
    except Exception:
        has_jsonschema = False

    if has_jsonschema:
        ok, errors = validate_schema_with_jsonschema(report, schema)
        if not ok:
            for err in errors:
                add_finding(
                    findings,
                    "schema_validation_error",
                    "error",
                    "open",
                    "Report failed JSON schema validation.",
                    {"error": err},
                )
    else:
        print("INFO: jsonschema not available; using rule-based validation.")

    schema_version = str(report.get("schema_version", "")).strip()
    if schema_version != EXPECTED_SCHEMA_VERSION:
        add_finding(
            findings,
            "schema_version_mismatch",
            "error",
            "open",
            f"schema_version must be {EXPECTED_SCHEMA_VERSION}.",
            {"actual": schema_version},
        )

    report_type = str(report.get("report_type", "")).strip()
    if report_type != EXPECTED_REPORT_TYPE:
        add_finding(
            findings,
            "report_type_mismatch",
            "error",
            "open",
            f"report_type must be {EXPECTED_REPORT_TYPE}.",
            {"actual": report_type},
        )

    declared_status = str(report.get("status", "")).strip()
    if declared_status not in ALLOWED_STATUS:
        add_finding(
            findings,
            "status_invalid",
            "error",
            "open",
            "status must be one of pass|warn|fail|pending_manual.",
            {"actual": declared_status},
        )

    lane = str(report.get("lane", "")).strip()
    for required in ("job_id", "package_id"):
        value = str(report.get(required, "")).strip()
        if not value:
            add_finding(findings, f"{required}_missing", "error", "open", f"{required} is required.")
    if not lane:
        add_finding(findings, "lane_missing", "error", "open", "lane is required.")

    source = report.get("source", {}) if isinstance(report.get("source"), dict) else {}
    source_path = str(source.get("source_path", "")).strip()
    source_kind = str(source.get("source_kind", "")).strip()
    if not source_path:
        add_finding(findings, "source_path_missing", "error", "open", "source.source_path is required.")
    if source_path and _contains_unsafe_path_tokens(source_path):
        add_finding(
            findings,
            "source_path_unsafe",
            "error",
            "open",
            "source.source_path contains unsafe traversal or absolute-path tokens.",
            {"path": source_path},
        )
    if not source_kind:
        add_finding(findings, "source_kind_missing", "error", "open", "source.source_kind is required.")

    readiness_contract = report.get("readiness_contract", {}) if isinstance(report.get("readiness_contract"), dict) else {}
    contract_id = str(readiness_contract.get("contract_id", "")).strip()
    required_gate_ids = readiness_contract.get("required_gate_ids", [])
    required_authorization_artifact_ids = readiness_contract.get("required_authorization_artifact_ids", [])
    required_approvals = readiness_contract.get("required_approvals")
    manual_review_required = readiness_contract.get("manual_review_required")

    if contract_id != EXPECTED_CONTRACT_ID:
        add_finding(
            findings,
            "contract_id_invalid",
            "error",
            "open",
            f"readiness_contract.contract_id must be {EXPECTED_CONTRACT_ID}.",
            {"actual": contract_id},
        )
    if not _is_string_array(required_gate_ids):
        add_finding(
            findings,
            "required_gate_ids_invalid",
            "error",
            "open",
            "readiness_contract.required_gate_ids must be a non-empty string array.",
        )
        required_gate_ids = []
    if not _is_string_array(required_authorization_artifact_ids):
        add_finding(
            findings,
            "required_authorization_artifact_ids_invalid",
            "error",
            "open",
            "readiness_contract.required_authorization_artifact_ids must be a non-empty string array.",
        )
        required_authorization_artifact_ids = []

    required_gate_ids = _normalize_string_list(required_gate_ids)
    required_authorization_artifact_ids = _normalize_string_list(required_authorization_artifact_ids)

    if "release_publication_execution_admission_review_v1" not in required_gate_ids:
        add_finding(
            findings,
            "required_execution_admission_review_gate_missing",
            "error",
            "open",
            "readiness_contract.required_gate_ids must include release_publication_execution_admission_review_v1.",
        )
    if "release_publication_execution_admission_review" not in required_authorization_artifact_ids:
        add_finding(
            findings,
            "required_execution_admission_review_artifact_missing",
            "error",
            "open",
            "readiness_contract.required_authorization_artifact_ids must include release_publication_execution_admission_review.",
        )

    if not isinstance(required_approvals, int) or required_approvals < 1:
        add_finding(
            findings,
            "required_approvals_invalid",
            "error",
            "open",
            "readiness_contract.required_approvals must be integer >= 1.",
            {"actual": required_approvals},
        )
        required_approvals = 1

    if not isinstance(manual_review_required, bool):
        add_finding(
            findings,
            "manual_review_required_invalid",
            "error",
            "open",
            "readiness_contract.manual_review_required must be boolean.",
            {"actual": manual_review_required},
        )
    elif lane == "release_character" and manual_review_required is not True:
        add_finding(
            findings,
            "manual_review_required_for_release",
            "error",
            "open",
            "release_character lane must require manual review.",
        )

    if readiness_contract.get("immutable_authorization_record_required") is not True:
        add_finding(
            findings,
            "immutable_authorization_record_required",
            "error",
            "open",
            "readiness_contract.immutable_authorization_record_required must be true.",
            {"actual": readiness_contract.get("immutable_authorization_record_required")},
        )
    if readiness_contract.get("hash_verification_required") is not True:
        add_finding(
            findings,
            "hash_verification_required",
            "error",
            "open",
            "readiness_contract.hash_verification_required must be true.",
            {"actual": readiness_contract.get("hash_verification_required")},
        )
    if readiness_contract.get("evidence_only") is not True:
        add_finding(
            findings,
            "evidence_only_required",
            "error",
            "open",
            "readiness_contract.evidence_only must be true.",
            {"actual": readiness_contract.get("evidence_only")},
        )
    if readiness_contract.get("execution_admitted") is not False:
        add_finding(
            findings,
            "execution_admitted_must_be_false",
            "error",
            "open",
            "readiness_contract.execution_admitted must be false.",
            {"actual": readiness_contract.get("execution_admitted")},
        )

    authorization_data = report.get("execution_authorization_record", {}) if isinstance(report.get("execution_authorization_record"), dict) else {}
    authorization_action = str(authorization_data.get("authorization_action", "")).strip()
    authorization_scope = str(authorization_data.get("authorization_scope", "")).strip()
    hash_algorithm = str(authorization_data.get("hash_algorithm", "")).strip()
    verification_status = str(authorization_data.get("authorization_verification_status", "")).strip()
    chain_manifest_path = str(authorization_data.get("chain_manifest_path", "")).strip()
    authorization_record_path = str(authorization_data.get("authorization_record_path", "")).strip()
    authorization_record_sha = str(authorization_data.get("authorization_record_sha256", "")).strip()
    source_ready_packet_path = str(
        authorization_data.get("source_execution_admission_review_path", "")
    ).strip()
    source_ready_packet_sha = str(
        authorization_data.get("source_execution_admission_review_sha256", "")
    ).strip()
    authorization_artifacts = authorization_data.get("authorization_artifacts", [])

    if authorization_action != EXPECTED_REQUEST_ACTION:
        add_finding(
            findings,
            "authorization_action_invalid",
            "error",
            "open",
            f"execution_authorization_record.authorization_action must be {EXPECTED_REQUEST_ACTION}.",
            {"actual": authorization_action},
        )
    if authorization_scope != EXPECTED_REVIEW_SCOPE:
        add_finding(
            findings,
            "authorization_scope_invalid",
            "error",
            "open",
            f"execution_authorization_record.authorization_scope must be {EXPECTED_REVIEW_SCOPE}.",
            {"actual": authorization_scope},
        )

    source_ready_request_id = str(
        authorization_data.get("source_execution_admission_review_id", "")
    ).strip()
    if not source_ready_request_id:
        add_finding(
            findings,
            "source_execution_admission_review_id_missing",
            "error",
            "open",
            "execution_authorization_record.source_execution_admission_review_id is required.",
        )
    elif "execution-admission-review" not in source_ready_request_id.lower():
        add_finding(
            findings,
            "source_execution_admission_review_id_invalid",
            "error",
            "open",
            "execution_authorization_record.source_execution_admission_review_id must reference an execution-admission-review id.",
            {"actual": source_ready_request_id},
        )

    if hash_algorithm != "sha256":
        add_finding(
            findings,
            "hash_algorithm_invalid",
            "error",
            "open",
            "execution_authorization_record.hash_algorithm must be sha256.",
            {"actual": hash_algorithm},
        )

    if verification_status not in ALLOWED_STATUS:
        add_finding(
            findings,
            "authorization_verification_status_invalid",
            "error",
            "open",
            "execution_authorization_record.authorization_verification_status must be pass|warn|fail|pending_manual.",
            {"actual": verification_status},
        )

    for label, path_text in (
        ("chain_manifest_path", chain_manifest_path),
        ("authorization_record_path", authorization_record_path),
        ("source_execution_admission_review_path", source_ready_packet_path),
    ):
        if not path_text:
            add_finding(findings, f"{label}_missing", "error", "open", f"execution_authorization_record.{label} is required.")
            continue
        if _contains_unsafe_path_tokens(path_text):
            add_finding(
                findings,
                f"{label}_unsafe",
                "error",
                "open",
                f"execution_authorization_record.{label} contains unsafe traversal or absolute-path tokens.",
                {"path": path_text},
            )

    if not _is_likely_sha256(authorization_record_sha):
        add_finding(
            findings,
            "authorization_record_sha256_invalid",
            "error",
            "open",
            "execution_authorization_record.authorization_record_sha256 must look like sha256 hex.",
            {"actual": authorization_record_sha},
        )

    if not _is_likely_sha256(source_ready_packet_sha):
        add_finding(
            findings,
            "source_execution_admission_review_sha256_invalid",
            "error",
            "open",
            "execution_authorization_record.source_execution_admission_review_sha256 must look like sha256 hex.",
            {"actual": source_ready_packet_sha},
        )
    if source_ready_packet_path and "release-publication-execution-admission-review" not in source_ready_packet_path.lower():
        add_finding(
            findings,
            "source_execution_admission_review_path_invalid",
            "error",
            "open",
            "execution_authorization_record.source_execution_admission_review_path must reference execution-admission-review evidence.",
            {"actual": source_ready_packet_path},
        )

    if authorization_data.get("no_command_execution_recorded") is not True:
        add_finding(
            findings,
            "no_command_execution_recorded_required",
            "error",
            "open",
            "execution_authorization_record.no_command_execution_recorded must be true.",
            {"actual": authorization_data.get("no_command_execution_recorded")},
        )

    artifact_hashes = authorization_data.get("authorization_artifact_hashes", {})
    if not isinstance(artifact_hashes, dict) or not artifact_hashes:
        add_finding(
            findings,
            "authorization_artifact_hashes_invalid",
            "error",
            "open",
            "execution_authorization_record.authorization_artifact_hashes must be a non-empty object.",
        )
        artifact_hashes = {}

    normalized_hashes: Dict[str, str] = {}
    for key, value in artifact_hashes.items():
        key_text = str(key).strip()
        value_text = str(value).strip()
        if not key_text:
            add_finding(findings, "artifact_hash_key_missing", "error", "open", "authorization_artifact_hashes keys must be non-empty.")
            continue
        normalized_hashes[key_text] = value_text
        if not _is_likely_sha256(value_text):
            add_finding(
                findings,
                "artifact_hash_value_invalid",
                "error",
                "open",
                "authorization_artifact_hashes values must look like sha256 hex.",
                {"artifact_id": key_text, "value": value_text},
            )

    artifact_count = authorization_data.get("artifact_count")
    if not isinstance(artifact_count, int) or artifact_count < 1:
        add_finding(
            findings,
            "artifact_count_invalid",
            "error",
            "open",
            "execution_authorization_record.artifact_count must be integer >= 1.",
            {"actual": artifact_count},
        )
    elif artifact_count != len(normalized_hashes):
        add_finding(
            findings,
            "artifact_count_mismatch",
            "error",
            "open",
            "artifact_count must equal the number of authorization_artifact_hashes entries.",
            {"declared": artifact_count, "computed": len(normalized_hashes)},
        )

    missing_ids = authorization_data.get("missing_authorization_artifact_ids", [])
    mismatch_ids = authorization_data.get("hash_mismatch_authorization_artifact_ids", [])
    if not _is_string_array(missing_ids) and missing_ids != []:
        add_finding(findings, "missing_authorization_artifact_ids_invalid", "error", "open", "missing_authorization_artifact_ids must be a string array.")
        missing_ids = []
    if not _is_string_array(mismatch_ids) and mismatch_ids != []:
        add_finding(findings, "hash_mismatch_authorization_artifact_ids_invalid", "error", "open", "hash_mismatch_authorization_artifact_ids must be a string array.")
        mismatch_ids = []

    missing_ids = _normalize_string_list(missing_ids)
    mismatch_ids = _normalize_string_list(mismatch_ids)

    computed_missing_ids = sorted(set(required_authorization_artifact_ids) - set(normalized_hashes.keys()))
    if computed_missing_ids != missing_ids:
        add_finding(
            findings,
            "missing_authorization_artifact_ids_mismatch",
            "warning",
            "open",
            "missing_authorization_artifact_ids does not match required-vs-present hash-index computation.",
            {"reported": missing_ids, "computed": computed_missing_ids},
        )

    if computed_missing_ids:
        add_finding(
            findings,
            "required_authorization_artifacts_missing",
            "error",
            "open",
            "Required authorization record artifacts are missing from authorization_artifact_hashes.",
            {"missing_authorization_artifact_ids": computed_missing_ids},
        )

    unexpected_mismatch_ids = [item for item in mismatch_ids if item not in required_authorization_artifact_ids]
    if unexpected_mismatch_ids:
        add_finding(
            findings,
            "hash_mismatch_ids_unexpected",
            "error",
            "open",
            "hash_mismatch_authorization_artifact_ids includes values not present in required_authorization_artifact_ids.",
            {"unexpected_ids": unexpected_mismatch_ids},
        )

    if verification_status == "pass":
        if computed_missing_ids:
            add_finding(findings, "pass_with_missing_authorization_artifacts", "error", "open", "authorization_verification_status=pass is invalid when required authorization record artifacts are missing.")
        if mismatch_ids:
            add_finding(findings, "pass_with_hash_mismatch", "error", "open", "authorization_verification_status=pass is invalid when hash_mismatch_authorization_artifact_ids is not empty.")

    if verification_status in {"fail", "pending_manual"} and not (computed_missing_ids or mismatch_ids):
        add_finding(
            findings,
            "nonpass_without_failure_evidence",
            "warning",
            "open",
            "authorization_verification_status is non-pass but no missing/mismatch evidence is recorded.",
        )

    if not _is_string_array(authorization_artifacts):
        add_finding(
            findings,
            "authorization_artifacts_invalid",
            "error",
            "open",
            "execution_authorization_record.authorization_artifacts must be a non-empty string array.",
        )
        authorization_artifacts = []
    authorization_artifacts = _normalize_string_list(authorization_artifacts)

    if isinstance(artifact_count, int) and artifact_count > 0 and len(authorization_artifacts) != artifact_count:
        add_finding(
            findings,
            "authorization_artifacts_count_mismatch",
            "warning",
            "open",
            "authorization_artifacts count differs from artifact_count.",
            {"artifact_count": artifact_count, "artifact_path_count": len(authorization_artifacts)},
        )

    for artifact_path in authorization_artifacts:
        if _contains_unsafe_path_tokens(artifact_path):
            add_finding(
                findings,
                "authorization_artifact_path_unsafe",
                "error",
                "open",
                "authorization_artifacts contains unsafe path tokens.",
                {"path": artifact_path},
            )
        lowered = artifact_path.lower()
        if any(token in lowered for token in DISALLOWED_ARTIFACT_TOKENS):
            add_finding(
                findings,
                "authorization_artifact_disallowed",
                "error",
                "open",
                "authorization_artifacts includes disallowed binary/runtime/cache/database artifact.",
                {"path": artifact_path},
            )

    for hint_id, hint_token in REQUIRED_ARTIFACT_HINTS.items():
        if hint_id in required_authorization_artifact_ids and not any(hint_token in item.lower() for item in authorization_artifacts):
            add_finding(
                findings,
                f"required_artifact_missing_{hint_id}",
                "error",
                "open",
                "authorization_artifacts is missing a required admission-review evidence artifact.",
                {"required_hint": hint_token},
            )

    if authorization_data.get("authorization_record_immutable") is not True:
        add_finding(
            findings,
            "authorization_record_immutable_required",
            "error",
            "open",
            "execution_authorization_record.authorization_record_immutable must be true.",
            {"actual": authorization_data.get("authorization_record_immutable")},
        )

    approval_state = report.get("approval_state", {}) if isinstance(report.get("approval_state"), dict) else {}
    decision = str(approval_state.get("decision", "")).strip()
    approver_ids = approval_state.get("approver_ids", [])
    blocked_reason_codes = approval_state.get("blocked_reason_codes", [])
    rollback_plan_verified = approval_state.get("rollback_plan_verified")
    cleanup_plan_verified = approval_state.get("cleanup_plan_verified")

    if decision not in {EXPECTED_READY_DECISION, "pending_manual_review", "rejected"}:
        add_finding(
            findings,
            "approval_decision_invalid",
            "error",
            "open",
            "approval_state.decision must be execution_authorization_recorded_for_future_manual_execution_window|pending_manual_review|rejected.",
            {"actual": decision},
        )
        decision = "pending_manual_review"

    if not _is_string_array(approver_ids) and approver_ids != []:
        add_finding(findings, "approver_ids_invalid", "error", "open", "approval_state.approver_ids must be a string array.")
        approver_ids = []
    if not _is_string_array(blocked_reason_codes) and blocked_reason_codes != []:
        add_finding(findings, "blocked_reason_codes_invalid", "error", "open", "approval_state.blocked_reason_codes must be a string array.")
        blocked_reason_codes = []

    approver_ids = _normalize_string_list(approver_ids)
    blocked_reason_codes = _normalize_string_list(blocked_reason_codes)

    for flag_name in (
        "publish_execution_admitted",
        "o3de_execution_admitted",
        "asset_processor_execution_admitted",
        "spawn_execution_admitted",
    ):
        if approval_state.get(flag_name) is not False:
            add_finding(
                findings,
                f"{flag_name}_must_be_false",
                "error",
                "open",
                f"approval_state.{flag_name} must be false.",
                {"actual": approval_state.get(flag_name)},
            )

    if not isinstance(rollback_plan_verified, bool):
        add_finding(
            findings,
            "rollback_plan_verified_invalid",
            "error",
            "open",
            "approval_state.rollback_plan_verified must be boolean.",
            {"actual": rollback_plan_verified},
        )
        rollback_plan_verified = False
    if not isinstance(cleanup_plan_verified, bool):
        add_finding(
            findings,
            "cleanup_plan_verified_invalid",
            "error",
            "open",
            "approval_state.cleanup_plan_verified must be boolean.",
            {"actual": cleanup_plan_verified},
        )
        cleanup_plan_verified = False

    readiness = report.get("readiness", {}) if isinstance(report.get("readiness"), dict) else {}
    readiness_required_gate_ids = readiness.get("required_gate_ids", [])
    present_gate_ids = readiness.get("present_gate_ids", [])
    missing_gate_ids = readiness.get("missing_gate_ids", [])
    readiness_state = str(readiness.get("execution_authorization_record_readiness_state", "")).strip()

    if not _is_string_array(readiness_required_gate_ids):
        add_finding(findings, "readiness_required_gate_ids_invalid", "error", "open", "readiness.required_gate_ids must be a non-empty string array.")
        readiness_required_gate_ids = []
    if not _is_string_array(present_gate_ids) and present_gate_ids != []:
        add_finding(findings, "present_gate_ids_invalid", "error", "open", "readiness.present_gate_ids must be a string array.")
        present_gate_ids = []
    if not _is_string_array(missing_gate_ids) and missing_gate_ids != []:
        add_finding(findings, "missing_gate_ids_invalid", "error", "open", "readiness.missing_gate_ids must be a string array.")
        missing_gate_ids = []

    readiness_required_gate_ids = _normalize_string_list(readiness_required_gate_ids)
    present_gate_ids = _normalize_string_list(present_gate_ids)
    missing_gate_ids = _normalize_string_list(missing_gate_ids)

    if required_gate_ids and readiness_required_gate_ids and required_gate_ids != readiness_required_gate_ids:
        add_finding(
            findings,
            "required_gate_ids_mismatch",
            "warning",
            "open",
            "readiness_contract.required_gate_ids does not match readiness.required_gate_ids.",
            {
                "contract_required_gate_ids": required_gate_ids,
                "readiness_required_gate_ids": readiness_required_gate_ids,
            },
        )

    effective_required_gates = readiness_required_gate_ids if readiness_required_gate_ids else required_gate_ids
    computed_missing_gate_ids = sorted(set(effective_required_gates) - set(present_gate_ids))

    if computed_missing_gate_ids != missing_gate_ids:
        add_finding(
            findings,
            "missing_gate_ids_mismatch",
            "warning",
            "open",
            "readiness.missing_gate_ids does not match required-vs-present computation.",
            {"reported": missing_gate_ids, "computed": computed_missing_gate_ids},
        )

    if computed_missing_gate_ids:
        add_finding(
            findings,
            "required_gates_missing",
            "error",
            "open",
            "Required release-publication readiness gates are missing.",
            {"missing_gate_ids": computed_missing_gate_ids},
        )

    if readiness_state not in {
        "execution_authorization_recorded_for_future_manual_execution_window",
        "blocked_missing_evidence",
        "blocked_safety_boundary",
    }:
        add_finding(
            findings,
            "execution_authorization_record_readiness_state_invalid",
            "error",
            "open",
            "readiness.execution_authorization_record_readiness_state is invalid.",
            {"actual": readiness_state},
        )

    if readiness_state == "execution_authorization_recorded_for_future_manual_execution_window" and computed_missing_gate_ids:
        add_finding(
            findings,
            "ready_state_with_missing_gates",
            "error",
            "open",
            "execution_authorization_recorded_for_future_manual_execution_window cannot be set when required gates are missing.",
        )

    if decision == EXPECTED_READY_DECISION:
        if len(approver_ids) < required_approvals:
            add_finding(
                findings,
                "insufficient_approvals",
                "error",
                "open",
                "approval_state.approver_ids count is lower than readiness_contract.required_approvals.",
                {"approver_ids": approver_ids, "required_approvals": required_approvals},
            )
        if blocked_reason_codes:
            add_finding(
                findings,
                "ready_with_blocked_reasons",
                "error",
                "open",
                "execution_authorization_recorded_for_future_manual_execution_window must not include blocked_reason_codes.",
                {"blocked_reason_codes": blocked_reason_codes},
            )
        if rollback_plan_verified is not True:
            add_finding(
                findings,
                "rollback_plan_not_verified",
                "error",
                "open",
                "execution_authorization_recorded_for_future_manual_execution_window requires rollback_plan_verified=true.",
            )
        if cleanup_plan_verified is not True:
            add_finding(
                findings,
                "cleanup_plan_not_verified",
                "error",
                "open",
                "execution_authorization_recorded_for_future_manual_execution_window requires cleanup_plan_verified=true.",
            )
        if readiness_state != "execution_authorization_recorded_for_future_manual_execution_window":
            add_finding(
                findings,
                "ready_without_ready_state",
                "error",
                "open",
                "execution_authorization_recorded_for_future_manual_execution_window requires readiness.execution_authorization_record_readiness_state=execution_authorization_recorded_for_future_manual_execution_window.",
            )
    elif decision == "pending_manual_review":
        add_finding(
            findings,
            "execution_authorization_record_pending_manual_review",
            "manual_review",
            "open",
            "Release publication execution authorization record remains pending manual review.",
        )
    elif decision == "rejected":
        add_finding(
            findings,
            "execution_authorization_record_rejected",
            "error",
            "open",
            "Release publication execution authorization record decision is rejected.",
        )

    if verification_status == "pass" and declared_status != "pass":
        add_finding(
            findings,
            "status_should_be_pass_for_authorization_pass",
            "error",
            "open",
            "authorization_verification_status=pass requires report.status=pass.",
        )
    elif verification_status == "warn" and declared_status != "warn":
        add_finding(
            findings,
            "status_should_be_warn_for_authorization_warn",
            "error",
            "open",
            "authorization_verification_status=warn requires report.status=warn.",
        )
    elif verification_status == "fail" and declared_status != "fail":
        add_finding(
            findings,
            "status_should_be_fail_for_authorization_fail",
            "error",
            "open",
            "authorization_verification_status=fail requires report.status=fail.",
        )
    elif verification_status == "pending_manual" and declared_status != "pending_manual":
        add_finding(
            findings,
            "status_should_be_pending_for_authorization_pending",
            "error",
            "open",
            "authorization_verification_status=pending_manual requires report.status=pending_manual.",
        )

    input_findings = report.get("findings", [])
    if not isinstance(input_findings, list):
        add_finding(findings, "findings_not_array", "error", "open", "findings must be an array.")
        input_findings = []
    else:
        for idx, item in enumerate(input_findings):
            if not isinstance(item, dict):
                add_finding(findings, "finding_invalid", "error", "open", f"findings[{idx}] must be an object.")
                continue
            fid = str(item.get("id", "")).strip()
            sev = str(item.get("severity", "")).strip()
            fstatus = str(item.get("status", "")).strip()
            msg = str(item.get("message", "")).strip()
            if not fid:
                add_finding(findings, "finding_id_missing", "error", "open", f"findings[{idx}].id is required.")
            if sev not in ALLOWED_FINDING_SEVERITY:
                add_finding(
                    findings,
                    "finding_severity_invalid",
                    "error",
                    "open",
                    f"findings[{idx}].severity must be info|warning|error|manual_review.",
                    {"actual": sev},
                )
            if not fstatus:
                add_finding(findings, "finding_status_missing", "error", "open", f"findings[{idx}].status is required.")
            if not msg:
                add_finding(findings, "finding_message_missing", "error", "open", f"findings[{idx}].message is required.")

    attachment = report.get("manifest_attachment", {}) if isinstance(report.get("manifest_attachment"), dict) else {}
    target_path = str(attachment.get("target_path", "")).strip()
    future_target_path = str(attachment.get("future_target_path", "")).strip()

    if target_path != TARGET_PATH:
        add_finding(
            findings,
            "manifest_target_path_invalid",
            "error",
            "open",
            f"manifest_attachment.target_path must be {TARGET_PATH}.",
            {"actual": target_path},
        )
    if future_target_path != FUTURE_TARGET_PATH:
        add_finding(
            findings,
            "manifest_future_target_path_invalid",
            "error",
            "open",
            f"manifest_attachment.future_target_path must be {FUTURE_TARGET_PATH}.",
            {"actual": future_target_path},
        )

    combined_findings = findings + input_findings
    computed_status = derive_status(combined_findings)

    if declared_status in ALLOWED_STATUS and declared_status != computed_status:
        add_finding(
            findings,
            "status_mismatch",
            "error",
            "open",
            "report.status does not match computed findings severity.",
            {"declared": declared_status, "computed": computed_status},
        )
        combined_findings = findings + input_findings
        computed_status = derive_status(combined_findings)

    qc_severity = status_to_qc_severity(computed_status)
    output_payload: Dict[str, Any] = {
        "status": computed_status,
        "check_id": CHECK_ID,
        "contract_id": CONTRACT_ID,
        "findings": combined_findings,
        "manifest_attachment": {
            "target_path": TARGET_PATH,
            "future_target_path": FUTURE_TARGET_PATH,
            "qc_check": {
                "check_id": CHECK_ID,
                "result": computed_status,
                "severity": qc_severity,
                "details": {
                    "report_path": str(report_path),
                    "report_status": declared_status,
                    "validated_at_utc": utc_now(),
                },
            },
        },
    }

    print(json.dumps(output_payload, indent=2))

    if computed_status == "pass":
        return 0
    if computed_status == "warn" and args.allow_warn:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
