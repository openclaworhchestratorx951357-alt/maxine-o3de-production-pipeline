#!/usr/bin/env python3
"""Validate manual hero review reports with controlled-real evidence references."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
ALLOWED_EVIDENCE_CLASS = {"fixture", "imported", "controlled_real", "manual"}
ALLOWED_REVIEWER_IDENTITY = {"fixture_reviewer", "assigned_reviewer", "approved_reviewer"}
ALLOWED_REVIEW_TIER = {"hero", "npc", "prop"}
ALLOWED_RELEASE_RECOMMENDATION = {
    "approve_for_release_candidate",
    "approve_with_warnings",
    "reject",
    "pending_manual_review",
}
EXPECTED_RECOMMENDATION_BY_DECISION = {
    "pass": "approve_for_release_candidate",
    "warn": "approve_with_warnings",
    "fail": "reject",
    "pending_manual": "pending_manual_review",
}
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "MANUAL_HERO_REVIEW_v1_REPORT"
EXPECTED_REVIEW_CONTRACT_ID = "MANUAL_HERO_REVIEW_v1"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "manual_hero_review_v1"
CONTRACT_ID = "MANUAL_HERO_REVIEW_v1"
REQUIRED_HERO_EVIDENCE_REFS = [
    "dcc_conform_v1",
    "max_biped_v1_skeleton_contract",
    "material_uv_qc_v1",
    "animation_smoke_v1",
    "screenshot_evidence_v1",
    "source_product_evidence_resolver_v1",
]
QUALITY_STATUS_FIELDS = [
    "required_evidence_present_status",
    "visual_quality_status",
    "material_quality_status",
    "skeleton_quality_status",
    "animation_quality_status",
    "scale_orientation_status",
    "package_readiness_status",
]
SAFETY_BLOCKED_FIELDS = [
    "execution_status",
    "o3de_execution_status",
    "editor_execution_status",
    "runtime_execution_status",
    "dcc_execution_status",
    "asset_processor_execution_status",
    "production_write_status",
]


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


def _validate_findings_array(
    raw_findings: Any,
    findings: List[Dict[str, Any]],
    field_name: str,
) -> List[Dict[str, Any]]:
    parsed: List[Dict[str, Any]] = []
    if not isinstance(raw_findings, list):
        add_finding(
            findings,
            f"{field_name}_not_array",
            "error",
            "open",
            f"{field_name} must be an array.",
        )
        return parsed

    for idx, item in enumerate(raw_findings):
        if not isinstance(item, dict):
            add_finding(
                findings,
                f"{field_name}_item_invalid",
                "error",
                "open",
                f"{field_name}[{idx}] must be an object.",
            )
            continue
        fid = str(item.get("id", "")).strip()
        sev = str(item.get("severity", "")).strip()
        fstatus = str(item.get("status", "")).strip()
        msg = str(item.get("message", "")).strip()
        if not fid:
            add_finding(
                findings,
                f"{field_name}_id_missing",
                "error",
                "open",
                f"{field_name}[{idx}].id is required.",
            )
        if sev not in ALLOWED_FINDING_SEVERITY:
            add_finding(
                findings,
                f"{field_name}_severity_invalid",
                "error",
                "open",
                f"{field_name}[{idx}].severity must be info|warning|error|manual_review.",
                {"actual": sev},
            )
        if not fstatus:
            add_finding(
                findings,
                f"{field_name}_status_missing",
                "error",
                "open",
                f"{field_name}[{idx}].status is required.",
            )
        if not msg:
            add_finding(
                findings,
                f"{field_name}_message_missing",
                "error",
                "open",
                f"{field_name}[{idx}].message is required.",
            )
        parsed.append(item)
    return parsed


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

    decision = str(report.get("decision", "")).strip()
    if decision not in ALLOWED_STATUS:
        add_finding(
            findings,
            "decision_invalid",
            "error",
            "open",
            "decision must be one of pass|warn|fail|pending_manual.",
            {"actual": decision},
        )

    for required in (
        "job_id",
        "package_id",
        "lane",
        "candidate_id",
        "review_id",
        "review_profile_version",
        "reviewer_name_or_handle",
        "review_timestamp",
    ):
        value = str(report.get(required, "")).strip()
        if not value:
            add_finding(findings, f"{required}_missing", "error", "open", f"{required} is required.")

    review_profile_id = str(report.get("review_profile_id", "")).strip()
    if review_profile_id != EXPECTED_REVIEW_CONTRACT_ID:
        add_finding(
            findings,
            "review_profile_id_invalid",
            "error",
            "open",
            f"review_profile_id must be {EXPECTED_REVIEW_CONTRACT_ID}.",
            {"actual": review_profile_id},
        )

    review_tier = str(report.get("review_tier", "")).strip()
    if review_tier not in ALLOWED_REVIEW_TIER:
        add_finding(
            findings,
            "review_tier_invalid",
            "error",
            "open",
            "review_tier must be hero|npc|prop.",
            {"actual": review_tier},
        )

    evidence_class = str(report.get("evidence_class", "")).strip()
    if evidence_class not in ALLOWED_EVIDENCE_CLASS:
        add_finding(
            findings,
            "evidence_class_invalid",
            "error",
            "open",
            "evidence_class must be fixture|imported|controlled_real|manual.",
            {"actual": evidence_class},
        )

    reviewer_identity_status = str(report.get("reviewer_identity_status", "")).strip()
    if reviewer_identity_status not in ALLOWED_REVIEWER_IDENTITY:
        add_finding(
            findings,
            "reviewer_identity_status_invalid",
            "error",
            "open",
            "reviewer_identity_status must be fixture_reviewer|assigned_reviewer|approved_reviewer.",
            {"actual": reviewer_identity_status},
        )

    release_recommendation = str(report.get("release_recommendation", "")).strip()
    if release_recommendation not in ALLOWED_RELEASE_RECOMMENDATION:
        add_finding(
            findings,
            "release_recommendation_invalid",
            "error",
            "open",
            "release_recommendation must be approve_for_release_candidate|approve_with_warnings|reject|pending_manual_review.",
            {"actual": release_recommendation},
        )

    expected_recommendation = EXPECTED_RECOMMENDATION_BY_DECISION.get(decision)
    if expected_recommendation and release_recommendation != expected_recommendation:
        add_finding(
            findings,
            "release_recommendation_mismatch",
            "error",
            "open",
            "release_recommendation must match decision policy.",
            {"decision": decision, "expected": expected_recommendation, "actual": release_recommendation},
        )

    claim_status = str(report.get("claim_status", "")).strip()
    if claim_status not in {"evidence_only", "not_authoritative"}:
        add_finding(
            findings,
            "claim_status_invalid",
            "error",
            "open",
            "claim_status must be evidence_only|not_authoritative.",
            {"actual": claim_status},
        )

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

    reviewed_evidence_refs_raw = report.get("reviewed_evidence_refs", [])
    if not _is_string_array(reviewed_evidence_refs_raw):
        add_finding(
            findings,
            "reviewed_evidence_refs_invalid",
            "error",
            "open",
            "reviewed_evidence_refs must be a non-empty string array.",
        )
        reviewed_evidence_refs_raw = []
    reviewed_evidence_refs = sorted(
        set(str(x).strip() for x in reviewed_evidence_refs_raw if isinstance(x, str) and str(x).strip())
    )

    quality_status_values: Dict[str, str] = {}
    for field in QUALITY_STATUS_FIELDS:
        value = str(report.get(field, "")).strip()
        quality_status_values[field] = value
        if value not in ALLOWED_STATUS:
            add_finding(
                findings,
                f"{field}_invalid",
                "error",
                "open",
                f"{field} must be one of pass|warn|fail|pending_manual.",
                {"actual": value},
            )

    missing_required_refs: List[str] = []
    if review_tier == "hero":
        missing_required_refs = sorted(set(REQUIRED_HERO_EVIDENCE_REFS) - set(reviewed_evidence_refs))
        if missing_required_refs:
            add_finding(
                findings,
                "required_controlled_real_evidence_refs_missing",
                "error" if decision != "pending_manual" else "manual_review",
                "open",
                "Hero manual review must reference all required controlled-real evidence gates.",
                {
                    "missing_refs": missing_required_refs,
                    "required_refs": REQUIRED_HERO_EVIDENCE_REFS,
                },
            )

    required_evidence_present_status = quality_status_values.get("required_evidence_present_status", "")
    if missing_required_refs and required_evidence_present_status == "pass":
        add_finding(
            findings,
            "required_evidence_present_status_mismatch",
            "error",
            "open",
            "required_evidence_present_status cannot be pass when required refs are missing.",
            {"missing_refs": missing_required_refs},
        )

    failed_quality_fields = sorted(
        [field for field, value in quality_status_values.items() if value == "fail"]
    )
    pending_quality_fields = sorted(
        [field for field, value in quality_status_values.items() if value == "pending_manual"]
    )
    warn_quality_fields = sorted(
        [field for field, value in quality_status_values.items() if value == "warn"]
    )

    waiver_status = str(report.get("waiver_status", "")).strip()
    waiver_reasons_raw = report.get("waiver_reasons", [])
    if waiver_status not in {"none", "waived"}:
        add_finding(
            findings,
            "waiver_status_invalid",
            "error",
            "open",
            "waiver_status must be none|waived.",
            {"actual": waiver_status},
        )
    if not isinstance(waiver_reasons_raw, list):
        add_finding(
            findings,
            "waiver_reasons_invalid",
            "error",
            "open",
            "waiver_reasons must be a string array.",
        )
        waiver_reasons_raw = []
    waiver_reasons = [str(x).strip() for x in waiver_reasons_raw if isinstance(x, str) and str(x).strip()]
    if waiver_status == "waived" and not waiver_reasons:
        add_finding(
            findings,
            "waiver_reasons_required",
            "error",
            "open",
            "waiver_reasons must be provided when waiver_status=waived.",
        )
    if waiver_status == "none" and waiver_reasons:
        add_finding(
            findings,
            "waiver_reasons_present_without_waiver",
            "warning",
            "open",
            "waiver_reasons were provided while waiver_status=none.",
        )

    reviewer_findings = _validate_findings_array(report.get("reviewer_findings", []), findings, "reviewer_findings")
    report_findings = _validate_findings_array(report.get("findings", []), findings, "findings")

    combined_policy_findings = reviewer_findings + report_findings
    combined_policy_severities = {str(item.get("severity", "")) for item in combined_policy_findings}
    has_error_finding = "error" in combined_policy_severities
    has_warning_finding = "warning" in combined_policy_severities
    has_manual_review_finding = "manual_review" in combined_policy_severities

    if decision == "pass":
        if reviewer_identity_status != "approved_reviewer":
            add_finding(
                findings,
                "pass_requires_approved_reviewer",
                "error",
                "open",
                "pass decision requires reviewer_identity_status=approved_reviewer.",
            )
        if failed_quality_fields or pending_quality_fields or warn_quality_fields:
            add_finding(
                findings,
                "pass_requires_all_quality_pass",
                "error",
                "open",
                "pass decision requires all quality status fields to be pass.",
                {
                    "failed_quality_fields": failed_quality_fields,
                    "pending_quality_fields": pending_quality_fields,
                    "warn_quality_fields": warn_quality_fields,
                },
            )
        if missing_required_refs:
            add_finding(
                findings,
                "pass_requires_complete_required_refs",
                "error",
                "open",
                "pass decision requires complete required reviewed evidence refs.",
                {"missing_refs": missing_required_refs},
            )
        if has_error_finding or has_manual_review_finding:
            add_finding(
                findings,
                "pass_has_blocking_findings",
                "error",
                "open",
                "pass decision cannot include error/manual_review findings.",
            )
        if waiver_status == "waived":
            add_finding(
                findings,
                "pass_with_waiver_not_allowed",
                "error",
                "open",
                "waived reviews must not use pass decision; use warn or fail.",
            )

    if decision == "warn":
        if reviewer_identity_status != "approved_reviewer":
            add_finding(
                findings,
                "warn_requires_approved_reviewer",
                "error",
                "open",
                "warn decision requires reviewer_identity_status=approved_reviewer.",
            )
        if failed_quality_fields or has_error_finding:
            add_finding(
                findings,
                "warn_has_blocking_failures",
                "error",
                "open",
                "warn decision cannot include fail quality states or error findings.",
                {"failed_quality_fields": failed_quality_fields},
            )
        if not (warn_quality_fields or has_warning_finding or waiver_status == "waived"):
            add_finding(
                findings,
                "warn_without_warn_signals",
                "warning",
                "open",
                "warn decision should include warn quality status, warning finding, or explicit waiver.",
            )

    if decision == "fail":
        blocking_signals = bool(
            failed_quality_fields
            or missing_required_refs
            or has_error_finding
        )
        if not blocking_signals:
            add_finding(
                findings,
                "fail_without_blocking_signal",
                "error",
                "open",
                "fail decision requires at least one blocking signal.",
            )

    if decision == "pending_manual":
        pending_signals = bool(
            pending_quality_fields
            or missing_required_refs
            or has_manual_review_finding
            or reviewer_identity_status == "assigned_reviewer"
        )
        if not pending_signals:
            add_finding(
                findings,
                "pending_manual_without_pending_signal",
                "manual_review",
                "open",
                "pending_manual decision should include pending/manual-review signals.",
            )

    safety = report.get("safety", {}) if isinstance(report.get("safety"), dict) else {}
    for field in SAFETY_BLOCKED_FIELDS:
        value = str(safety.get(field, "")).strip()
        if value != "blocked":
            add_finding(
                findings,
                f"{field}_must_be_blocked",
                "error",
                "open",
                f"safety.{field} must be blocked.",
                {"actual": value},
            )

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

    combined_findings = findings + reviewer_findings + report_findings
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
        combined_findings = findings + reviewer_findings + report_findings
        computed_status = derive_status(combined_findings)

    if decision in ALLOWED_STATUS and decision != computed_status:
        add_finding(
            findings,
            "decision_mismatch",
            "error",
            "open",
            "decision does not match computed findings severity.",
            {"decision": decision, "computed": computed_status},
        )
        combined_findings = findings + reviewer_findings + report_findings
        computed_status = derive_status(combined_findings)

    qc_severity = status_to_qc_severity(computed_status)
    output_payload: Dict[str, Any] = {
        "status": computed_status,
        "check_id": CHECK_ID,
        "contract_id": CONTRACT_ID,
        "evidence_class": evidence_class if evidence_class in ALLOWED_EVIDENCE_CLASS else "manual",
        "review_tier": review_tier,
        "reviewed_evidence_refs": reviewed_evidence_refs,
        "required_hero_evidence_refs": REQUIRED_HERO_EVIDENCE_REFS,
        "missing_required_evidence_refs": missing_required_refs,
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
                    "review_decision": decision,
                    "release_recommendation": release_recommendation,
                    "review_tier": review_tier,
                    "evidence_class": evidence_class,
                    "reviewed_evidence_refs": reviewed_evidence_refs,
                    "missing_required_evidence_refs": missing_required_refs,
                    "execution_admitted": False,
                    "publication_admitted": False,
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
