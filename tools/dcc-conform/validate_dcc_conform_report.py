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
ALLOWED_EVIDENCE_CLASS = {"fixture", "imported", "controlled_real"}
ALLOWED_CLAIM_STATUS = {"evidence_only", "not_authoritative"}
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


def _validate_status_field(
    findings: List[Dict[str, Any]],
    field_name: str,
    value: str,
) -> None:
    if value not in ALLOWED_STATUS:
        add_finding(
            findings,
            f"{field_name}_invalid",
            "error",
            "open",
            f"{field_name} must be pass|warn|fail|pending_manual.",
            {"actual": value},
        )


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

    candidate_id = str(report.get("candidate_id", "")).strip()
    if not candidate_id:
        add_finding(findings, "candidate_id_missing", "error", "open", "candidate_id is required.")

    source_asset_reference = str(report.get("source_asset_reference", "")).strip()
    if not source_asset_reference:
        add_finding(
            findings,
            "source_asset_reference_missing",
            "error",
            "open",
            "source_asset_reference is required.",
        )

    source_evidence_ref = str(report.get("source_evidence_ref", "")).strip()
    if not source_evidence_ref:
        add_finding(
            findings,
            "source_evidence_ref_missing",
            "error",
            "open",
            "source_evidence_ref is required.",
        )
    elif _contains_unsafe_path_tokens(source_evidence_ref):
        add_finding(
            findings,
            "source_evidence_ref_unsafe",
            "error",
            "open",
            "source_evidence_ref contains unsafe traversal or shell tokens.",
            {"source_evidence_ref": source_evidence_ref},
        )

    dcc_tool_name = str(report.get("dcc_tool_name", "")).strip()
    dcc_tool_version = str(report.get("dcc_tool_version", "")).strip()
    conform_profile_id = str(report.get("conform_profile_id", "")).strip()
    conform_profile_version = str(report.get("conform_profile_version", "")).strip()
    if not dcc_tool_name:
        add_finding(findings, "dcc_tool_name_missing", "error", "open", "dcc_tool_name is required.")
    if not dcc_tool_version:
        add_finding(findings, "dcc_tool_version_missing", "error", "open", "dcc_tool_version is required.")
    if not conform_profile_id:
        add_finding(findings, "conform_profile_id_missing", "error", "open", "conform_profile_id is required.")
    if not conform_profile_version:
        add_finding(
            findings,
            "conform_profile_version_missing",
            "error",
            "open",
            "conform_profile_version is required.",
        )

    unit_scale_status = str(report.get("unit_scale_status", "")).strip()
    orientation_status = str(report.get("orientation_status", "")).strip()
    origin_status = str(report.get("origin_status", "")).strip()
    transform_freeze_status = str(report.get("transform_freeze_status", "")).strip()
    mesh_naming_status = str(report.get("mesh_naming_status", "")).strip()
    material_slot_naming_status = str(report.get("material_slot_naming_status", "")).strip()
    skeleton_reference_status = str(report.get("skeleton_reference_status", "")).strip()
    export_format_status = str(report.get("export_format_status", "")).strip()
    for field_name, value in (
        ("unit_scale_status", unit_scale_status),
        ("orientation_status", orientation_status),
        ("origin_status", origin_status),
        ("transform_freeze_status", transform_freeze_status),
        ("mesh_naming_status", mesh_naming_status),
        ("material_slot_naming_status", material_slot_naming_status),
        ("skeleton_reference_status", skeleton_reference_status),
        ("export_format_status", export_format_status),
    ):
        _validate_status_field(findings, field_name, value)

    required_units = str(report.get("required_units", "")).strip()
    if not required_units:
        add_finding(findings, "required_units_missing", "error", "open", "required_units is required.")

    required_axes = report.get("required_axes", {})
    if not isinstance(required_axes, dict):
        required_axes = {}
        add_finding(findings, "required_axes_not_object", "error", "open", "required_axes must be an object.")
    required_up_axis = str(required_axes.get("up_axis", "")).strip()
    required_forward_axis = str(required_axes.get("forward_axis", "")).strip()
    required_handedness = str(required_axes.get("handedness", "")).strip()
    if not required_up_axis:
        add_finding(findings, "required_up_axis_missing", "error", "open", "required_axes.up_axis is required.")
    if not required_forward_axis:
        add_finding(
            findings,
            "required_forward_axis_missing",
            "error",
            "open",
            "required_axes.forward_axis is required.",
        )
    if not required_handedness:
        add_finding(
            findings,
            "required_handedness_missing",
            "error",
            "open",
            "required_axes.handedness is required.",
        )

    evidence_class = str(report.get("evidence_class", "")).strip()
    if evidence_class not in ALLOWED_EVIDENCE_CLASS:
        add_finding(
            findings,
            "evidence_class_invalid",
            "error",
            "open",
            "evidence_class must be fixture|imported|controlled_real.",
            {"actual": evidence_class},
        )
    elif evidence_class == "controlled_real":
        normalized_ref = source_evidence_ref.replace("\\", "/")
        if not normalized_ref.startswith("examples/sandbox/"):
            add_finding(
                findings,
                "controlled_real_source_evidence_ref_outside_sandbox",
                "error",
                "open",
                "controlled_real evidence must reference sandbox evidence roots.",
                {"source_evidence_ref": source_evidence_ref},
            )

    claim_status = str(report.get("claim_status", "")).strip()
    if claim_status not in ALLOWED_CLAIM_STATUS:
        add_finding(
            findings,
            "claim_status_invalid",
            "error",
            "open",
            "claim_status must be evidence_only|not_authoritative.",
            {"actual": claim_status},
        )

    safety = report.get("safety", {})
    if not isinstance(safety, dict):
        safety = {}
        add_finding(findings, "safety_not_object", "error", "open", "safety must be an object.")
    for safety_field in (
        "dcc_execution_status",
        "blender_execution_status",
        "production_write_status",
    ):
        if str(safety.get(safety_field, "")).strip() != "blocked":
            add_finding(
                findings,
                f"{safety_field}_not_blocked",
                "error",
                "open",
                f"safety.{safety_field} must be blocked.",
                {"actual": safety.get(safety_field)},
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
    tool_version = str(dcc.get("tool_version", "")).strip()
    export_preset = str(dcc.get("export_preset", "")).strip()
    intended_output_path = str(dcc.get("intended_output_path", "")).strip()
    evidence_only = dcc.get("evidence_only")
    if not tool_name:
        add_finding(findings, "tool_name_missing", "error", "open", "dcc.tool_name is required.")
    elif dcc_tool_name and tool_name != dcc_tool_name:
        add_finding(
            findings,
            "dcc_tool_name_mismatch",
            "error",
            "open",
            "dcc_tool_name must match dcc.tool_name.",
            {"dcc_tool_name": dcc_tool_name, "dcc.tool_name": tool_name},
        )
    if not tool_version:
        add_finding(findings, "tool_version_missing", "error", "open", "dcc.tool_version is required.")
    elif dcc_tool_version and tool_version != dcc_tool_version:
        add_finding(
            findings,
            "dcc_tool_version_mismatch",
            "error",
            "open",
            "dcc_tool_version must match dcc.tool_version.",
            {"dcc_tool_version": dcc_tool_version, "dcc.tool_version": tool_version},
        )
    if not export_preset:
        add_finding(findings, "export_preset_missing", "error", "open", "dcc.export_preset is required.")
    elif conform_profile_id and export_preset != conform_profile_id:
        add_finding(
            findings,
            "conform_profile_mismatch",
            "error",
            "open",
            "conform_profile_id must match dcc.export_preset.",
            {"conform_profile_id": conform_profile_id, "dcc.export_preset": export_preset},
        )
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
    elif required_units and units.lower() != required_units.lower():
        add_finding(
            findings,
            "required_units_mismatch",
            "error",
            "open",
            "transform.units must match required_units.",
            {"required_units": required_units, "transform.units": units},
        )
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
    if required_up_axis and str(transform.get("up_axis", "")).strip() != required_up_axis:
        add_finding(
            findings,
            "required_up_axis_mismatch",
            "error",
            "open",
            "transform.up_axis must match required_axes.up_axis.",
            {"required_axes.up_axis": required_up_axis, "transform.up_axis": transform.get("up_axis")},
        )
    if required_forward_axis and str(transform.get("forward_axis", "")).strip() != required_forward_axis:
        add_finding(
            findings,
            "required_forward_axis_mismatch",
            "error",
            "open",
            "transform.forward_axis must match required_axes.forward_axis.",
            {
                "required_axes.forward_axis": required_forward_axis,
                "transform.forward_axis": transform.get("forward_axis"),
            },
        )
    if required_handedness and handedness and handedness != required_handedness:
        add_finding(
            findings,
            "required_handedness_mismatch",
            "error",
            "open",
            "transform.handedness must match required_axes.handedness.",
            {"required_axes.handedness": required_handedness, "transform.handedness": handedness},
        )

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

    if declared_status == "pass":
        for field_name, value in (
            ("unit_scale_status", unit_scale_status),
            ("orientation_status", orientation_status),
            ("origin_status", origin_status),
            ("transform_freeze_status", transform_freeze_status),
            ("mesh_naming_status", mesh_naming_status),
            ("material_slot_naming_status", material_slot_naming_status),
            ("skeleton_reference_status", skeleton_reference_status),
            ("export_format_status", export_format_status),
        ):
            if value != "pass":
                add_finding(
                    findings,
                    f"{field_name}_must_pass_when_report_pass",
                    "error",
                    "open",
                    f"{field_name} must be pass when report.status is pass.",
                    {"actual": value},
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
    if skeleton_reference_status == "pass" and skeleton_contract_result != "pass":
        add_finding(
            findings,
            "skeleton_reference_status_mismatch",
            "error",
            "open",
            "skeleton_reference_status cannot be pass when skeleton.skeleton_contract_result is not pass.",
            {
                "skeleton_reference_status": skeleton_reference_status,
                "skeleton_contract_result": skeleton_contract_result,
            },
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
        "evidence_class": evidence_class,
        "claim_status": claim_status,
        "candidate_id": candidate_id,
        "source_asset_reference": source_asset_reference,
        "source_evidence_ref": source_evidence_ref,
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
                    "candidate_id": candidate_id,
                    "source_asset_reference": source_asset_reference,
                    "source_evidence_ref": source_evidence_ref,
                    "dcc_tool_name": dcc_tool_name,
                    "dcc_tool_version": dcc_tool_version,
                    "conform_profile_id": conform_profile_id,
                    "conform_profile_version": conform_profile_version,
                    "required_axes": {
                        "up_axis": required_up_axis,
                        "forward_axis": required_forward_axis,
                        "handedness": required_handedness,
                    },
                    "required_units": required_units,
                    "evidence_class": evidence_class,
                    "claim_status": claim_status,
                    "safety": {
                        "dcc_execution_status": str(safety.get("dcc_execution_status", "")).strip(),
                        "blender_execution_status": str(safety.get("blender_execution_status", "")).strip(),
                        "production_write_status": str(safety.get("production_write_status", "")).strip(),
                    },
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
