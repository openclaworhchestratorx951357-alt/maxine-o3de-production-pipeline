#!/usr/bin/env python3
"""Validate evidence-only manual hero review reports for release-lane integration."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "MANUAL_HERO_REVIEW_v1_REPORT"
EXPECTED_REVIEW_CONTRACT_ID = "MANUAL_HERO_REVIEW_v1"
EXPECTED_TARGET_TIER = "hero"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "manual_hero_review_v1"
CONTRACT_ID = "MANUAL_HERO_REVIEW_v1"


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
        description="Validate MAXINE manual hero review report JSON."
    )
    parser.add_argument("report_path", help="Path to manual hero review report JSON")
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


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    report_path = resolve_path(repo_root, args.report_path)
    schema_path = repo_root / "schemas" / "maxine_manual_hero_review_report.schema.json"

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

    for required in ("job_id", "package_id", "lane"):
        value = str(report.get(required, "")).strip()
        if not value:
            add_finding(findings, f"{required}_missing", "error", "open", f"{required} is required.")

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

    review_scope = report.get("review_scope", {}) if isinstance(report.get("review_scope"), dict) else {}
    review_contract_id = str(review_scope.get("review_contract_id", "")).strip()
    target_tier = str(review_scope.get("target_tier", "")).strip()
    required_reviewers = review_scope.get("required_reviewers")
    required_evidence_ids = review_scope.get("required_evidence_ids", [])

    if review_contract_id != EXPECTED_REVIEW_CONTRACT_ID:
        add_finding(
            findings,
            "review_contract_id_invalid",
            "error",
            "open",
            f"review_scope.review_contract_id must be {EXPECTED_REVIEW_CONTRACT_ID}.",
            {"actual": review_contract_id},
        )
    if target_tier != EXPECTED_TARGET_TIER:
        add_finding(
            findings,
            "target_tier_invalid_for_contract",
            "error",
            "open",
            f"review_scope.target_tier must be {EXPECTED_TARGET_TIER} for this contract.",
            {"actual": target_tier},
        )
    if review_scope.get("evidence_only") is not True:
        add_finding(
            findings,
            "evidence_only_required",
            "error",
            "open",
            "review_scope.evidence_only must be true.",
            {"actual": review_scope.get("evidence_only")},
        )
    if review_scope.get("runtime_execution_admitted") is not False:
        add_finding(
            findings,
            "runtime_execution_admitted_must_be_false",
            "error",
            "open",
            "review_scope.runtime_execution_admitted must be false.",
            {"actual": review_scope.get("runtime_execution_admitted")},
        )
    if not isinstance(required_reviewers, int) or required_reviewers < 1:
        add_finding(
            findings,
            "required_reviewers_invalid",
            "error",
            "open",
            "review_scope.required_reviewers must be integer >= 1.",
            {"actual": required_reviewers},
        )
        required_reviewers = 1
    if not _is_string_array(required_evidence_ids):
        add_finding(
            findings,
            "required_evidence_ids_invalid",
            "error",
            "open",
            "review_scope.required_evidence_ids must be a non-empty string array.",
        )
        required_evidence_ids = []
    if not required_evidence_ids:
        add_finding(
            findings,
            "required_evidence_ids_missing",
            "error",
            "open",
            "review_scope.required_evidence_ids must not be empty.",
        )
    required_evidence_ids = sorted(set(str(x).strip() for x in required_evidence_ids if str(x).strip()))

    decision = report.get("review_decision", {}) if isinstance(report.get("review_decision"), dict) else {}
    review_required = decision.get("review_required")
    review_state = str(decision.get("review_state", "")).strip()
    reviewer_count = decision.get("reviewer_count")
    approver_ids = decision.get("approver_ids", [])
    missing_evidence_ids = decision.get("missing_evidence_ids", [])
    attached_evidence_ids = decision.get("attached_evidence_ids", [])
    rejection_reasons = decision.get("rejection_reasons", [])
    approved_at_utc = str(decision.get("approved_at_utc", "")).strip()

    if not isinstance(review_required, bool):
        add_finding(
            findings,
            "review_required_invalid",
            "error",
            "open",
            "review_decision.review_required must be boolean.",
            {"actual": review_required},
        )
        review_required = True
    if review_state not in {"not_required", "pending", "approved", "rejected"}:
        add_finding(
            findings,
            "review_state_invalid",
            "error",
            "open",
            "review_decision.review_state must be not_required|pending|approved|rejected.",
            {"actual": review_state},
        )
        review_state = "pending"
    if not isinstance(reviewer_count, int) or reviewer_count < 0:
        add_finding(
            findings,
            "reviewer_count_invalid",
            "error",
            "open",
            "review_decision.reviewer_count must be integer >= 0.",
            {"actual": reviewer_count},
        )
        reviewer_count = 0
    for field_name, value in (
        ("approver_ids", approver_ids),
        ("missing_evidence_ids", missing_evidence_ids),
        ("attached_evidence_ids", attached_evidence_ids),
        ("rejection_reasons", rejection_reasons),
    ):
        if not _is_string_array(value) and value != []:
            add_finding(
                findings,
                f"{field_name}_invalid",
                "error",
                "open",
                f"review_decision.{field_name} must be a string array.",
            )
    approver_ids = sorted(set(str(x).strip() for x in approver_ids if isinstance(x, str) and x.strip()))
    missing_evidence_ids = sorted(
        set(str(x).strip() for x in missing_evidence_ids if isinstance(x, str) and x.strip())
    )
    attached_evidence_ids = sorted(
        set(str(x).strip() for x in attached_evidence_ids if isinstance(x, str) and x.strip())
    )
    rejection_reasons = [str(x).strip() for x in rejection_reasons if isinstance(x, str) and str(x).strip()]

    computed_missing = sorted(set(required_evidence_ids) - set(attached_evidence_ids))
    if computed_missing != missing_evidence_ids:
        add_finding(
            findings,
            "missing_evidence_ids_mismatch",
            "warning",
            "open",
            "review_decision.missing_evidence_ids does not match required-vs-attached computation.",
            {"reported": missing_evidence_ids, "computed": computed_missing},
        )
    if computed_missing:
        missing_severity = "manual_review" if review_state == "pending" else "error"
        add_finding(
            findings,
            "required_evidence_missing",
            missing_severity,
            "open",
            "Required review evidence is missing.",
            {"missing_evidence_ids": computed_missing},
        )

    if review_required and review_state == "not_required":
        add_finding(
            findings,
            "review_state_not_required_invalid",
            "error",
            "open",
            "review_state cannot be not_required when review_required=true.",
        )
    if not review_required and target_tier == EXPECTED_TARGET_TIER:
        add_finding(
            findings,
            "hero_review_required",
            "error",
            "open",
            "Hero tier requires manual review gate to be enabled.",
        )

    if review_required:
        if review_state == "pending":
            add_finding(
                findings,
                "manual_review_pending",
                "manual_review",
                "open",
                "Manual hero review is pending.",
            )
        elif review_state == "approved":
            if reviewer_count < required_reviewers:
                add_finding(
                    findings,
                    "insufficient_reviewer_count",
                    "error",
                    "open",
                    "reviewer_count is lower than required_reviewers.",
                    {"reviewer_count": reviewer_count, "required_reviewers": required_reviewers},
                )
            if len(approver_ids) < required_reviewers:
                add_finding(
                    findings,
                    "insufficient_approver_ids",
                    "error",
                    "open",
                    "approver_ids count is lower than required_reviewers.",
                    {"approver_ids": approver_ids, "required_reviewers": required_reviewers},
                )
            if rejection_reasons:
                add_finding(
                    findings,
                    "approved_with_rejection_reasons",
                    "error",
                    "open",
                    "approved review_state must not include rejection_reasons.",
                    {"rejection_reasons": rejection_reasons},
                )
            if not approved_at_utc:
                add_finding(
                    findings,
                    "approved_at_utc_missing",
                    "warning",
                    "open",
                    "approved review_state should include approved_at_utc evidence.",
                )
        elif review_state == "rejected":
            if not rejection_reasons:
                add_finding(
                    findings,
                    "rejection_reasons_missing",
                    "error",
                    "open",
                    "rejected review_state must include rejection_reasons.",
                )
            if approver_ids:
                add_finding(
                    findings,
                    "rejected_with_approver_ids",
                    "warning",
                    "open",
                    "rejected review_state normally leaves approver_ids empty.",
                    {"approver_ids": approver_ids},
                )
    elif review_state != "not_required":
        add_finding(
            findings,
            "review_state_expected_not_required",
            "warning",
            "open",
            "review_state should be not_required when review_required=false.",
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
