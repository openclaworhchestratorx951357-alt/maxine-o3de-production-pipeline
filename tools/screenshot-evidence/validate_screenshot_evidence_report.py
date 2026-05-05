#!/usr/bin/env python3
"""Validate evidence-only screenshot evidence reports for release-lane integration."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "SCREENSHOT_EVIDENCE_v1_REPORT"
EXPECTED_CAPTURE_CONTRACT_ID = "SCREENSHOT_EVIDENCE_v1"
EXPECTED_SKELETON_CONTRACT_ID = "MAX_BIPED_v1"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "screenshot_evidence_v1"
CONTRACT_ID = "SCREENSHOT_EVIDENCE_v1"


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
        description="Validate MAXINE screenshot evidence report JSON."
    )
    parser.add_argument("report_path", help="Path to screenshot evidence report JSON")
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


def _is_allowed_image_format(fmt: str) -> bool:
    return fmt.lower() in {"png", "jpg", "jpeg"}


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    report_path = resolve_path(repo_root, args.report_path)
    schema_path = repo_root / "schemas" / "maxine_screenshot_evidence_report.schema.json"

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

    profile = report.get("capture_profile", {}) if isinstance(report.get("capture_profile"), dict) else {}
    capture_contract_id = str(profile.get("capture_contract_id", "")).strip()
    target_skeleton_contract_id = str(profile.get("target_skeleton_contract_id", "")).strip()
    required_view_ids = profile.get("required_view_ids", [])
    min_width = profile.get("min_width")
    min_height = profile.get("min_height")
    low_res_severity = str(profile.get("low_resolution_severity", "")).strip()

    if capture_contract_id != EXPECTED_CAPTURE_CONTRACT_ID:
        add_finding(
            findings,
            "capture_contract_id_invalid",
            "error",
            "open",
            f"capture_profile.capture_contract_id must be {EXPECTED_CAPTURE_CONTRACT_ID}.",
            {"actual": capture_contract_id},
        )
    if target_skeleton_contract_id != EXPECTED_SKELETON_CONTRACT_ID:
        add_finding(
            findings,
            "target_skeleton_contract_id_invalid",
            "error",
            "open",
            f"capture_profile.target_skeleton_contract_id must be {EXPECTED_SKELETON_CONTRACT_ID}.",
            {"actual": target_skeleton_contract_id},
        )
    if profile.get("evidence_only") is not True:
        add_finding(
            findings,
            "evidence_only_required",
            "error",
            "open",
            "capture_profile.evidence_only must be true.",
            {"actual": profile.get("evidence_only")},
        )
    if profile.get("runtime_execution_admitted") is not False:
        add_finding(
            findings,
            "runtime_execution_admitted_must_be_false",
            "error",
            "open",
            "capture_profile.runtime_execution_admitted must be false.",
            {"actual": profile.get("runtime_execution_admitted")},
        )

    if not isinstance(required_view_ids, list) or not all(isinstance(x, str) and x.strip() for x in required_view_ids):
        add_finding(
            findings,
            "required_view_ids_invalid",
            "error",
            "open",
            "required_view_ids must be a non-empty string array.",
        )
        required_view_ids = []
    if not required_view_ids:
        add_finding(findings, "required_view_ids_missing", "error", "open", "required_view_ids must not be empty.")

    if not isinstance(min_width, int) or min_width < 1:
        add_finding(findings, "min_width_invalid", "error", "open", "capture_profile.min_width must be integer >= 1.")
        min_width = 1
    if not isinstance(min_height, int) or min_height < 1:
        add_finding(findings, "min_height_invalid", "error", "open", "capture_profile.min_height must be integer >= 1.")
        min_height = 1
    if low_res_severity not in {"warning", "error", "manual_review"}:
        add_finding(
            findings,
            "low_resolution_severity_invalid",
            "error",
            "open",
            "capture_profile.low_resolution_severity must be warning|error|manual_review.",
            {"actual": low_res_severity},
        )
        low_res_severity = "warning"

    summary = report.get("screenshot_summary", {}) if isinstance(report.get("screenshot_summary"), dict) else {}
    captured_view_ids = summary.get("captured_view_ids", [])
    reported_missing_view_ids = summary.get("missing_view_ids", [])
    screenshot_paths = summary.get("screenshot_paths", [])
    invalid_screenshot_paths = summary.get("invalid_screenshot_paths", [])

    if not isinstance(captured_view_ids, list) or not all(isinstance(x, str) and x.strip() for x in captured_view_ids):
        add_finding(findings, "captured_view_ids_invalid", "error", "open", "captured_view_ids must be a string array.")
        captured_view_ids = []
    if not isinstance(reported_missing_view_ids, list) or not all(isinstance(x, str) and x.strip() for x in reported_missing_view_ids):
        add_finding(findings, "missing_view_ids_invalid", "error", "open", "missing_view_ids must be a string array.")
        reported_missing_view_ids = []
    if not isinstance(screenshot_paths, list):
        add_finding(findings, "screenshot_paths_invalid", "error", "open", "screenshot_paths must be an array.")
        screenshot_paths = []

    computed_missing_views = sorted(set(required_view_ids) - set(captured_view_ids))
    if computed_missing_views:
        add_finding(
            findings,
            "missing_required_views",
            "error",
            "open",
            "Required screenshot view ids are missing.",
            {"required_view_ids": required_view_ids, "captured_view_ids": captured_view_ids, "missing_view_ids": computed_missing_views},
        )
    if sorted(set(reported_missing_view_ids)) != computed_missing_views:
        add_finding(
            findings,
            "missing_view_ids_mismatch",
            "warning",
            "open",
            "reported missing_view_ids does not match computed missing views.",
            {"reported": reported_missing_view_ids, "computed": computed_missing_views},
        )

    screenshot_entry_view_ids: List[str] = []
    for idx, shot in enumerate(screenshot_paths):
        if not isinstance(shot, dict):
            add_finding(findings, "screenshot_entry_invalid", "error", "open", f"screenshot_paths[{idx}] must be an object.")
            continue
        view_id = str(shot.get("view_id", "")).strip()
        path = str(shot.get("path", "")).strip()
        width = shot.get("width")
        height = shot.get("height")
        fmt = str(shot.get("format", "")).strip().lower()
        if not view_id:
            add_finding(findings, "screenshot_view_id_missing", "error", "open", f"screenshot_paths[{idx}].view_id is required.")
        else:
            screenshot_entry_view_ids.append(view_id)
        if not path:
            add_finding(findings, "screenshot_path_missing", "error", "open", f"screenshot_paths[{idx}].path is required.")
        else:
            if _contains_unsafe_path_tokens(path):
                add_finding(
                    findings,
                    "screenshot_path_unsafe",
                    "error",
                    "open",
                    "screenshot path contains unsafe traversal or absolute-path tokens.",
                    {"path": path},
                )
        if not isinstance(width, int) or width < 1:
            add_finding(findings, "screenshot_width_invalid", "error", "open", f"screenshot_paths[{idx}].width must be integer >= 1.")
            width = 0
        if not isinstance(height, int) or height < 1:
            add_finding(findings, "screenshot_height_invalid", "error", "open", f"screenshot_paths[{idx}].height must be integer >= 1.")
            height = 0
        if fmt and not _is_allowed_image_format(fmt):
            add_finding(findings, "screenshot_format_invalid", "error", "open", f"screenshot_paths[{idx}].format must be png|jpg|jpeg.")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            if width < min_width or height < min_height:
                add_finding(
                    findings,
                    "screenshot_low_resolution",
                    low_res_severity,
                    "open",
                    "Screenshot resolution is below capture profile minimum.",
                    {"view_id": view_id, "width": width, "height": height, "min_width": min_width, "min_height": min_height},
                )

    if set(captured_view_ids) != set(screenshot_entry_view_ids):
        add_finding(
            findings,
            "captured_view_ids_vs_entries_mismatch",
            "warning",
            "open",
            "captured_view_ids does not match screenshot_paths view ids.",
            {"captured_view_ids": captured_view_ids, "entry_view_ids": sorted(set(screenshot_entry_view_ids))},
        )

    if not isinstance(invalid_screenshot_paths, list) or not all(isinstance(x, str) and x.strip() for x in invalid_screenshot_paths):
        add_finding(
            findings,
            "invalid_screenshot_paths_invalid",
            "error",
            "open",
            "invalid_screenshot_paths must be a string array.",
        )
        invalid_screenshot_paths = []
    if invalid_screenshot_paths:
        add_finding(
            findings,
            "invalid_screenshot_paths_present",
            "error",
            "open",
            "invalid_screenshot_paths must be empty for accepted evidence.",
            {"invalid_screenshot_paths": invalid_screenshot_paths},
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
