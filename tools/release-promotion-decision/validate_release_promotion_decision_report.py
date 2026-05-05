#!/usr/bin/env python3
"""Validate evidence-only release promotion decision reports for release-lane integration."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "RELEASE_PROMOTION_DECISION_v1_REPORT"
EXPECTED_CONTRACT_ID = "RELEASE_PROMOTION_DECISION_v1"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "release_promotion_decision_v1"
CONTRACT_ID = "RELEASE_PROMOTION_DECISION_v1"


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
        description="Validate MAXINE release promotion decision report JSON."
    )
    parser.add_argument("report_path", help="Path to release promotion decision report JSON")
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
    blocked = ("..", "|", ";", ">", "<", "&", "`", "\\\\", ":\\")
    lowered = path_text.lower()
    return any(token in lowered for token in blocked)


def _is_string_array(raw: Any) -> bool:
    return isinstance(raw, list) and all(isinstance(x, str) and x.strip() for x in raw)


def _normalize_string_list(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    return sorted(set(str(x).strip() for x in raw if isinstance(x, str) and str(x).strip()))


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    report_path = resolve_path(repo_root, args.report_path)
    schema_path = repo_root / "schemas" / "maxine_release_promotion_decision_report.schema.json"

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

    promotion_policy = report.get("promotion_policy", {}) if isinstance(report.get("promotion_policy"), dict) else {}
    contract_id = str(promotion_policy.get("contract_id", "")).strip()
    required_gate_ids = promotion_policy.get("required_gate_ids", [])
    required_approvals = promotion_policy.get("required_approvals")
    manual_review_required = promotion_policy.get("manual_review_required")
    if contract_id != EXPECTED_CONTRACT_ID:
        add_finding(
            findings,
            "promotion_contract_id_invalid",
            "error",
            "open",
            f"promotion_policy.contract_id must be {EXPECTED_CONTRACT_ID}.",
            {"actual": contract_id},
        )
    if promotion_policy.get("evidence_only") is not True:
        add_finding(
            findings,
            "evidence_only_required",
            "error",
            "open",
            "promotion_policy.evidence_only must be true.",
            {"actual": promotion_policy.get("evidence_only")},
        )
    if promotion_policy.get("runtime_execution_admitted") is not False:
        add_finding(
            findings,
            "runtime_execution_admitted_must_be_false",
            "error",
            "open",
            "promotion_policy.runtime_execution_admitted must be false.",
            {"actual": promotion_policy.get("runtime_execution_admitted")},
        )
    if not _is_string_array(required_gate_ids):
        add_finding(
            findings,
            "required_gate_ids_invalid",
            "error",
            "open",
            "promotion_policy.required_gate_ids must be a non-empty string array.",
        )
        required_gate_ids = []
    required_gate_ids = _normalize_string_list(required_gate_ids)
    if not isinstance(required_approvals, int) or required_approvals < 1:
        add_finding(
            findings,
            "required_approvals_invalid",
            "error",
            "open",
            "promotion_policy.required_approvals must be integer >= 1.",
            {"actual": required_approvals},
        )
        required_approvals = 1
    if not isinstance(manual_review_required, bool):
        add_finding(
            findings,
            "manual_review_required_invalid",
            "error",
            "open",
            "promotion_policy.manual_review_required must be boolean.",
            {"actual": manual_review_required},
        )
        manual_review_required = True
    elif lane == "release_character" and manual_review_required is not True:
        add_finding(
            findings,
            "manual_review_required_for_release",
            "error",
            "open",
            "release_character lane must require manual review.",
        )

    decision = report.get("decision", {}) if isinstance(report.get("decision"), dict) else {}
    promotion_decision = str(decision.get("promotion_decision", "")).strip()
    decision_recorded_utc = str(decision.get("decision_recorded_utc", "")).strip()
    approver_ids = decision.get("approver_ids", [])
    blocked_reason_codes = decision.get("blocked_reason_codes", [])
    rollback_plan_verified = decision.get("rollback_plan_verified")
    cleanup_plan_verified = decision.get("cleanup_plan_verified")
    if promotion_decision not in {"approved", "pending", "rejected"}:
        add_finding(
            findings,
            "promotion_decision_invalid",
            "error",
            "open",
            "decision.promotion_decision must be approved|pending|rejected.",
            {"actual": promotion_decision},
        )
        promotion_decision = "pending"
    if not decision_recorded_utc:
        add_finding(
            findings,
            "decision_recorded_utc_missing",
            "error",
            "open",
            "decision.decision_recorded_utc is required.",
        )
    if not _is_string_array(approver_ids) and approver_ids != []:
        add_finding(
            findings,
            "approver_ids_invalid",
            "error",
            "open",
            "decision.approver_ids must be a string array.",
        )
        approver_ids = []
    if not _is_string_array(blocked_reason_codes) and blocked_reason_codes != []:
        add_finding(
            findings,
            "blocked_reason_codes_invalid",
            "error",
            "open",
            "decision.blocked_reason_codes must be a string array.",
        )
        blocked_reason_codes = []
    approver_ids = _normalize_string_list(approver_ids)
    blocked_reason_codes = _normalize_string_list(blocked_reason_codes)

    for flag_name in (
        "publish_execution_admitted",
        "spawn_execution_admitted",
        "o3de_execution_admitted",
        "asset_processor_execution_admitted",
    ):
        if decision.get(flag_name) is not False:
            add_finding(
                findings,
                f"{flag_name}_must_be_false",
                "error",
                "open",
                f"decision.{flag_name} must be false.",
                {"actual": decision.get(flag_name)},
            )

    if not isinstance(rollback_plan_verified, bool):
        add_finding(
            findings,
            "rollback_plan_verified_invalid",
            "error",
            "open",
            "decision.rollback_plan_verified must be boolean.",
            {"actual": rollback_plan_verified},
        )
        rollback_plan_verified = False
    if not isinstance(cleanup_plan_verified, bool):
        add_finding(
            findings,
            "cleanup_plan_verified_invalid",
            "error",
            "open",
            "decision.cleanup_plan_verified must be boolean.",
            {"actual": cleanup_plan_verified},
        )
        cleanup_plan_verified = False

    readiness = report.get("readiness", {}) if isinstance(report.get("readiness"), dict) else {}
    readiness_required_gate_ids = readiness.get("required_gate_ids", [])
    present_gate_ids = readiness.get("present_gate_ids", [])
    missing_gate_ids = readiness.get("missing_gate_ids", [])
    release_readiness_state = str(readiness.get("release_readiness_state", "")).strip()
    if not _is_string_array(readiness_required_gate_ids):
        add_finding(
            findings,
            "readiness_required_gate_ids_invalid",
            "error",
            "open",
            "readiness.required_gate_ids must be a non-empty string array.",
        )
        readiness_required_gate_ids = []
    if not _is_string_array(present_gate_ids) and present_gate_ids != []:
        add_finding(
            findings,
            "present_gate_ids_invalid",
            "error",
            "open",
            "readiness.present_gate_ids must be a string array.",
        )
        present_gate_ids = []
    if not _is_string_array(missing_gate_ids) and missing_gate_ids != []:
        add_finding(
            findings,
            "missing_gate_ids_invalid",
            "error",
            "open",
            "readiness.missing_gate_ids must be a string array.",
        )
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
            "promotion_policy.required_gate_ids does not match readiness.required_gate_ids.",
            {"policy_required_gate_ids": required_gate_ids, "readiness_required_gate_ids": readiness_required_gate_ids},
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
            "Required release gates are missing.",
            {"missing_gate_ids": computed_missing_gate_ids},
        )

    if release_readiness_state not in {
        "ready_for_manual_release_review",
        "blocked_missing_evidence",
        "blocked_safety_boundary",
    }:
        add_finding(
            findings,
            "release_readiness_state_invalid",
            "error",
            "open",
            "readiness.release_readiness_state is invalid.",
            {"actual": release_readiness_state},
        )
    if release_readiness_state == "ready_for_manual_release_review" and computed_missing_gate_ids:
        add_finding(
            findings,
            "ready_state_with_missing_gates",
            "error",
            "open",
            "ready_for_manual_release_review cannot be set when required gates are missing.",
        )

    if promotion_decision == "approved":
        if len(approver_ids) < required_approvals:
            add_finding(
                findings,
                "insufficient_approvals",
                "error",
                "open",
                "decision.approver_ids count is lower than promotion_policy.required_approvals.",
                {"approver_ids": approver_ids, "required_approvals": required_approvals},
            )
        if blocked_reason_codes:
            add_finding(
                findings,
                "approved_with_blocked_reasons",
                "error",
                "open",
                "approved promotion_decision must not include blocked_reason_codes.",
                {"blocked_reason_codes": blocked_reason_codes},
            )
        if rollback_plan_verified is not True:
            add_finding(
                findings,
                "rollback_plan_not_verified",
                "error",
                "open",
                "approved promotion_decision requires rollback_plan_verified=true.",
            )
        if cleanup_plan_verified is not True:
            add_finding(
                findings,
                "cleanup_plan_not_verified",
                "error",
                "open",
                "approved promotion_decision requires cleanup_plan_verified=true.",
            )
        if release_readiness_state != "ready_for_manual_release_review":
            add_finding(
                findings,
                "approved_without_ready_state",
                "error",
                "open",
                "approved promotion_decision requires readiness.release_readiness_state=ready_for_manual_release_review.",
            )
    elif promotion_decision == "pending":
        add_finding(
            findings,
            "promotion_pending_manual_review",
            "manual_review",
            "open",
            "Promotion decision remains pending manual review.",
        )
    elif promotion_decision == "rejected":
        add_finding(
            findings,
            "promotion_rejected",
            "error",
            "open",
            "Promotion decision is rejected.",
        )
        if not blocked_reason_codes:
            add_finding(
                findings,
                "rejected_without_blocked_reasons",
                "warning",
                "open",
                "Rejected promotion decision should provide blocked_reason_codes.",
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
