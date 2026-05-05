#!/usr/bin/env python3
"""Validate evidence-only animation smoke reports for release-lane integration."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "ANIMATION_SMOKE_v1_REPORT"
EXPECTED_SMOKE_CONTRACT_ID = "ANIMATION_SMOKE_v1"
EXPECTED_SKELETON_CONTRACT_ID = "MAX_BIPED_v1"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "animation_smoke_v1"
CONTRACT_ID = "ANIMATION_SMOKE_v1"


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
        description="Validate MAXINE animation smoke report JSON."
    )
    parser.add_argument("report_path", help="Path to animation smoke report JSON")
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
    blocked = ("..", "|", ";", ">", "<", "&", "`")
    lowered = path_text.lower()
    return any(token in lowered for token in blocked)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    report_path = resolve_path(repo_root, args.report_path)
    schema_path = repo_root / "schemas" / "maxine_animation_smoke_report.schema.json"

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
            add_finding(
                findings,
                f"{required}_missing",
                "error",
                "open",
                f"{required} is required.",
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
            "source.source_path contains unsafe traversal or shell tokens.",
            {"path": source_path},
        )
    if not source_kind:
        add_finding(findings, "source_kind_missing", "error", "open", "source.source_kind is required.")

    profile = report.get("smoke_profile", {}) if isinstance(report.get("smoke_profile"), dict) else {}
    smoke_contract_id = str(profile.get("smoke_contract_id", "")).strip()
    target_skeleton_contract_id = str(profile.get("target_skeleton_contract_id", "")).strip()
    if smoke_contract_id != EXPECTED_SMOKE_CONTRACT_ID:
        add_finding(
            findings,
            "smoke_contract_id_invalid",
            "error",
            "open",
            f"smoke_profile.smoke_contract_id must be {EXPECTED_SMOKE_CONTRACT_ID}.",
            {"actual": smoke_contract_id},
        )
    if target_skeleton_contract_id != EXPECTED_SKELETON_CONTRACT_ID:
        add_finding(
            findings,
            "target_skeleton_contract_id_invalid",
            "error",
            "open",
            f"smoke_profile.target_skeleton_contract_id must be {EXPECTED_SKELETON_CONTRACT_ID}.",
            {"actual": target_skeleton_contract_id},
        )
    if profile.get("evidence_only") is not True:
        add_finding(
            findings,
            "evidence_only_required",
            "error",
            "open",
            "smoke_profile.evidence_only must be true.",
            {"actual": profile.get("evidence_only")},
        )
    if profile.get("runtime_execution_admitted") is not False:
        add_finding(
            findings,
            "runtime_execution_admitted_must_be_false",
            "error",
            "open",
            "smoke_profile.runtime_execution_admitted must be false.",
            {"actual": profile.get("runtime_execution_admitted")},
        )

    summary = report.get("animation_summary", {}) if isinstance(report.get("animation_summary"), dict) else {}
    required_clips = summary.get("required_clips", [])
    present_clips = summary.get("present_clips", [])
    reported_missing_clips = summary.get("missing_clips", [])
    clip_count = summary.get("clip_count")
    loop_status = str(summary.get("loop_playback_status", "")).strip()
    pose_status = str(summary.get("pose_stability_status", "")).strip()
    root_motion_status = str(summary.get("root_motion_status", "")).strip()
    warning_status_values = summary.get("warning_status_values", ["warn", "unknown"])

    if not isinstance(required_clips, list) or not all(isinstance(x, str) and x.strip() for x in required_clips):
        add_finding(findings, "required_clips_invalid", "error", "open", "required_clips must be a non-empty string array.")
        required_clips = []
    if not required_clips:
        add_finding(findings, "required_clips_missing", "error", "open", "required_clips must not be empty.")

    if not isinstance(present_clips, list) or not all(isinstance(x, str) and x.strip() for x in present_clips):
        add_finding(findings, "present_clips_invalid", "error", "open", "present_clips must be a string array.")
        present_clips = []
    if not isinstance(reported_missing_clips, list) or not all(isinstance(x, str) and x.strip() for x in reported_missing_clips):
        add_finding(findings, "missing_clips_invalid", "error", "open", "missing_clips must be a string array.")
        reported_missing_clips = []
    if not isinstance(clip_count, int) or clip_count < 0:
        add_finding(findings, "clip_count_invalid", "error", "open", "clip_count must be integer >= 0.")
        clip_count = 0
    if clip_count != len(present_clips):
        add_finding(
            findings,
            "clip_count_mismatch",
            "warning",
            "open",
            "clip_count does not match present_clips length.",
            {"clip_count": clip_count, "present_clips_length": len(present_clips)},
        )

    computed_missing = sorted(set(required_clips) - set(present_clips))
    if computed_missing:
        add_finding(
            findings,
            "missing_required_clips",
            "error",
            "open",
            "Required clips are missing from present_clips.",
            {"required_clips": required_clips, "present_clips": present_clips, "missing_clips": computed_missing},
        )
    if sorted(set(reported_missing_clips)) != computed_missing:
        add_finding(
            findings,
            "missing_clips_mismatch",
            "warning",
            "open",
            "reported missing_clips does not match computed missing clips.",
            {"reported": reported_missing_clips, "computed": computed_missing},
        )

    if not isinstance(warning_status_values, list) or not all(isinstance(x, str) and x.strip() for x in warning_status_values):
        add_finding(
            findings,
            "warning_status_values_invalid",
            "error",
            "open",
            "warning_status_values must be a string array.",
        )
        warning_status_values = ["warn", "unknown"]

    for field_name, field_value in (
        ("loop_playback_status", loop_status),
        ("pose_stability_status", pose_status),
        ("root_motion_status", root_motion_status),
    ):
        if field_value not in {"pass", "warn", "fail", "unknown"}:
            add_finding(
                findings,
                f"{field_name}_invalid",
                "error",
                "open",
                f"{field_name} must be pass|warn|fail|unknown.",
                {"actual": field_value},
            )
            continue
        if field_value == "fail":
            add_finding(
                findings,
                f"{field_name}_failed",
                "error",
                "open",
                f"{field_name} reported fail.",
            )
        elif field_value in warning_status_values:
            add_finding(
                findings,
                f"{field_name}_warning_state",
                "warning",
                "open",
                f"{field_name} reported warning-level state '{field_value}'.",
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
                    "validated_at_utc": utc_now()
                }
            }
        }
    }

    print(json.dumps(output_payload, indent=2))

    if computed_status == "pass":
        return 0
    if computed_status == "warn" and args.allow_warn:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
