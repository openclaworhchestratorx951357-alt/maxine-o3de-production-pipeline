#!/usr/bin/env python3
"""Validate evidence-only DCC conform reports for MAX_BIPED_v1 integration."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "DCC_CONFORM_v1_REPORT"
EXPECTED_SKELETON_CONTRACT = "MAX_BIPED_v1"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "dcc_conform_v1"
CONTRACT_ID = "DCC_CONFORM_v1"


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
        description="Validate MAXINE DCC conform report JSON."
    )
    parser.add_argument("report_path", help="Path to DCC conform report JSON")
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


def _is_3_number_array(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 3:
        return False
    return all(isinstance(item, (int, float)) for item in value)


def _contains_unsafe_path_tokens(path_text: str) -> bool:
    blocked = ("..", "|", ";", ">", "<", "&", "`")
    lowered = path_text.lower()
    return any(token in lowered for token in blocked)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    report_path = resolve_path(repo_root, args.report_path)
    schema_path = repo_root / "schemas" / "maxine_dcc_conform_report.schema.json"

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
    if not source_kind:
        add_finding(findings, "source_kind_missing", "error", "open", "source.source_kind is required.")

    target = report.get("target", {}) if isinstance(report.get("target"), dict) else {}
    contract_id = str(target.get("skeleton_contract_id", "")).strip()
    expected_contract_id = str(target.get("expected_skeleton_contract_id", "")).strip()
    package_tier = str(target.get("package_tier", "")).strip()
    if not package_tier:
        add_finding(findings, "package_tier_missing", "error", "open", "target.package_tier is required.")
    if contract_id != EXPECTED_SKELETON_CONTRACT:
        add_finding(
            findings,
            "skeleton_contract_id_invalid",
            "error",
            "open",
            f"target.skeleton_contract_id must be {EXPECTED_SKELETON_CONTRACT}.",
            {"actual": contract_id},
        )
    if expected_contract_id != EXPECTED_SKELETON_CONTRACT:
        add_finding(
            findings,
            "expected_skeleton_contract_id_invalid",
            "error",
            "open",
            f"target.expected_skeleton_contract_id must be {EXPECTED_SKELETON_CONTRACT}.",
            {"actual": expected_contract_id},
        )

    dcc = report.get("dcc", {}) if isinstance(report.get("dcc"), dict) else {}
    tool_name = str(dcc.get("tool_name", "")).strip()
    export_preset = str(dcc.get("export_preset", "")).strip()
    intended_output_path = str(dcc.get("intended_output_path", "")).strip()
    evidence_only = dcc.get("evidence_only")
    if not tool_name:
        add_finding(findings, "tool_name_missing", "error", "open", "dcc.tool_name is required.")
    if not export_preset:
        add_finding(findings, "export_preset_missing", "error", "open", "dcc.export_preset is required.")
    if not intended_output_path:
        add_finding(
            findings,
            "intended_output_path_missing",
            "error",
            "open",
            "dcc.intended_output_path is required.",
        )
    if intended_output_path and _contains_unsafe_path_tokens(intended_output_path):
        add_finding(
            findings,
            "intended_output_path_unsafe",
            "error",
            "open",
            "dcc.intended_output_path contains unsafe traversal or shell tokens.",
            {"path": intended_output_path},
        )
    if evidence_only is not True:
        add_finding(
            findings,
            "evidence_only_required",
            "error",
            "open",
            "dcc.evidence_only must be true in this slice.",
            {"actual": evidence_only},
        )

    transform = report.get("transform", {}) if isinstance(report.get("transform"), dict) else {}
    units = str(transform.get("units", "")).strip()
    if not units:
        add_finding(findings, "units_missing", "error", "open", "transform.units is required.")
    if transform.get("units_normalized") is not True:
        add_finding(
            findings,
            "units_not_normalized",
            "error",
            "open",
            "transform.units_normalized must be true.",
            {"actual": transform.get("units_normalized")},
        )
    if transform.get("origin_centered") is not True:
        add_finding(
            findings,
            "origin_not_centered",
            "error",
            "open",
            "transform.origin_centered must be true.",
            {"actual": transform.get("origin_centered")},
        )
    if str(transform.get("up_axis", "")).strip() != "Z":
        add_finding(
            findings,
            "up_axis_invalid",
            "error",
            "open",
            "transform.up_axis must be Z.",
            {"actual": transform.get("up_axis")},
        )
    if str(transform.get("forward_axis", "")).strip() != "Y":
        add_finding(
            findings,
            "forward_axis_invalid",
            "error",
            "open",
            "transform.forward_axis must be Y.",
            {"actual": transform.get("forward_axis")},
        )
    handedness = str(transform.get("handedness", "")).strip()
    if not handedness:
        add_finding(findings, "handedness_missing", "error", "open", "transform.handedness is required.")

    bounds = transform.get("bounds", {}) if isinstance(transform.get("bounds"), dict) else {}
    for key in ("min", "max", "size"):
        if not _is_3_number_array(bounds.get(key)):
            add_finding(
                findings,
                f"bounds_{key}_invalid",
                "error",
                "open",
                f"transform.bounds.{key} must be an array of three numbers.",
                {"actual": bounds.get(key)},
            )

    skeleton = report.get("skeleton", {}) if isinstance(report.get("skeleton"), dict) else {}
    if "root_bone_present" not in skeleton:
        add_finding(
            findings,
            "root_bone_flag_missing",
            "error",
            "open",
            "skeleton.root_bone_present is required.",
        )
    elif skeleton.get("root_bone_present") is not True:
        add_finding(
            findings,
            "root_bone_not_present",
            "error",
            "open",
            "skeleton.root_bone_present must be true.",
            {"actual": skeleton.get("root_bone_present")},
        )

    skeleton_contract_result = str(skeleton.get("skeleton_contract_result", "")).strip()
    if skeleton_contract_result not in ALLOWED_STATUS:
        add_finding(
            findings,
            "skeleton_contract_result_invalid",
            "error",
            "open",
            "skeleton.skeleton_contract_result must be pass|warn|fail|pending_manual.",
            {"actual": skeleton_contract_result},
        )

    output_ref = str(skeleton.get("skeleton_validator_output_ref", "")).strip()
    if not output_ref and skeleton_contract_result == "pass":
        add_finding(
            findings,
            "skeleton_validator_output_ref_missing",
            "warning",
            "open",
            "skeleton.skeleton_validator_output_ref is recommended when skeleton_contract_result is pass.",
        )

    input_findings = report.get("findings", [])
    if not isinstance(input_findings, list):
        add_finding(findings, "findings_not_array", "error", "open", "findings must be an array.")
    else:
        for idx, item in enumerate(input_findings):
            if not isinstance(item, dict):
                add_finding(
                    findings,
                    "finding_invalid",
                    "error",
                    "open",
                    f"findings[{idx}] must be an object.",
                )
                continue
            fid = str(item.get("id", "")).strip()
            sev = str(item.get("severity", "")).strip()
            fstatus = str(item.get("status", "")).strip()
            msg = str(item.get("message", "")).strip()
            if not fid:
                add_finding(
                    findings,
                    "finding_id_missing",
                    "error",
                    "open",
                    f"findings[{idx}].id is required.",
                )
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
                add_finding(
                    findings,
                    "finding_status_missing",
                    "error",
                    "open",
                    f"findings[{idx}].status is required.",
                )
            if not msg:
                add_finding(
                    findings,
                    "finding_message_missing",
                    "error",
                    "open",
                    f"findings[{idx}].message is required.",
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

    computed_status = derive_status(findings + input_findings if isinstance(input_findings, list) else findings)
    if declared_status in ALLOWED_STATUS and declared_status != computed_status:
        add_finding(
            findings,
            "status_mismatch",
            "error",
            "open",
            "report.status does not match computed findings severity.",
            {"declared": declared_status, "computed": computed_status},
        )
        computed_status = "fail"

    qc_severity = status_to_qc_severity(computed_status)

    output_payload: Dict[str, Any] = {
        "status": computed_status,
        "check_id": CHECK_ID,
        "contract_id": CONTRACT_ID,
        "target_skeleton_contract_id": EXPECTED_SKELETON_CONTRACT,
        "findings": findings + (input_findings if isinstance(input_findings, list) else []),
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
                    "target_skeleton_contract_id": EXPECTED_SKELETON_CONTRACT,
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
