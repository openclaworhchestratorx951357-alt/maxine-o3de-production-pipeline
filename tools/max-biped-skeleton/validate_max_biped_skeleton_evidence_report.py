#!/usr/bin/env python3
"""Validate evidence-only controlled-real MAX_BIPED skeleton reports."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
ALLOWED_EVIDENCE_CLASS = {"fixture", "imported", "controlled_real"}
ALLOWED_CLAIM_STATUS = {"evidence_only", "not_authoritative"}
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "MAX_BIPED_SKELETON_CONTRACT_v1_REPORT"
EXPECTED_PROFILE_ID = "MAX_BIPED_v1"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "max_biped_v1_skeleton_contract"

STATUS_FIELDS = [
    "root_bone_status",
    "pelvis_bone_status",
    "spine_chain_status",
    "neck_head_status",
    "left_arm_chain_status",
    "right_arm_chain_status",
    "left_leg_chain_status",
    "right_leg_chain_status",
    "hand_finger_status",
    "naming_convention_status",
    "hierarchy_status",
    "orientation_status",
    "scale_status",
    "bind_pose_status",
    "retarget_readiness_status",
    "animation_smoke_dependency_status",
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
        description="Validate controlled-real MAX_BIPED skeleton evidence report JSON."
    )
    parser.add_argument("report_path", help="Path to MAX_BIPED skeleton evidence report JSON")
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


def _contains_unsafe_path_tokens(path_text: str) -> bool:
    blocked = ("..", "|", ";", ">", "<", "&", "`")
    lowered = path_text.lower()
    return any(token in lowered for token in blocked)


def _status_severity(status: str) -> str:
    if status == "fail":
        return "error"
    if status == "pending_manual":
        return "manual_review"
    if status == "warn":
        return "warning"
    return "info"


def _collect_findings_status(findings: List[Dict[str, Any]]) -> str:
    severities = {str(item.get("severity", "")).strip() for item in findings}
    if "error" in severities:
        return "fail"
    if "manual_review" in severities:
        return "pending_manual"
    if "warning" in severities:
        return "warn"
    return "pass"


def _collect_component_status(report: Dict[str, Any]) -> str:
    seen: List[str] = []
    for field in STATUS_FIELDS:
        value = str(report.get(field, "")).strip()
        if value in ALLOWED_STATUS:
            seen.append(value)
    if "fail" in seen:
        return "fail"
    if "pending_manual" in seen:
        return "pending_manual"
    if "warn" in seen:
        return "warn"
    return "pass"


def _merge_status(a: str, b: str) -> str:
    order = ["pass", "warn", "pending_manual", "fail"]
    return max(a, b, key=lambda value: order.index(value))


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    report_path = resolve_path(repo_root, args.report_path)
    schema_path = repo_root / "schemas" / "maxine_max_biped_skeleton_evidence_report.schema.json"

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

    for required in ("job_id", "package_id", "lane", "candidate_id", "source_asset_reference", "source_evidence_ref"):
        value = str(report.get(required, "")).strip()
        if not value:
            add_finding(findings, f"{required}_missing", "error", "open", f"{required} is required.")

    source_evidence_ref = str(report.get("source_evidence_ref", "")).strip()
    if source_evidence_ref and _contains_unsafe_path_tokens(source_evidence_ref):
        add_finding(
            findings,
            "source_evidence_ref_unsafe",
            "error",
            "open",
            "source_evidence_ref contains unsafe traversal or shell tokens.",
            {"source_evidence_ref": source_evidence_ref},
        )

    skeleton_profile_id = str(report.get("skeleton_profile_id", "")).strip()
    if skeleton_profile_id != EXPECTED_PROFILE_ID:
        add_finding(
            findings,
            "skeleton_profile_id_invalid",
            "error",
            "open",
            f"skeleton_profile_id must be {EXPECTED_PROFILE_ID}.",
            {"actual": skeleton_profile_id},
        )

    skeleton_profile_version = str(report.get("skeleton_profile_version", "")).strip()
    if not skeleton_profile_version:
        add_finding(
            findings,
            "skeleton_profile_version_missing",
            "error",
            "open",
            "skeleton_profile_version is required.",
        )

    skeleton_evidence_class = str(report.get("skeleton_evidence_class", "")).strip()
    if skeleton_evidence_class not in ALLOWED_EVIDENCE_CLASS:
        add_finding(
            findings,
            "skeleton_evidence_class_invalid",
            "error",
            "open",
            "skeleton_evidence_class must be fixture|imported|controlled_real.",
            {"actual": skeleton_evidence_class},
        )
    elif skeleton_evidence_class == "controlled_real":
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

    for field_name in STATUS_FIELDS:
        value = str(report.get(field_name, "")).strip()
        if value not in ALLOWED_STATUS:
            add_finding(
                findings,
                f"{field_name}_invalid",
                "error",
                "open",
                f"{field_name} must be pass|warn|fail|pending_manual.",
                {"actual": value},
            )

    bone_count = report.get("bone_count")
    if not isinstance(bone_count, int) or bone_count < 0:
        add_finding(
            findings,
            "bone_count_invalid",
            "error",
            "open",
            "bone_count must be a non-negative integer.",
            {"actual": bone_count},
        )

    required_bones_present = report.get("required_bones_present")
    if not isinstance(required_bones_present, list):
        required_bones_present = []
        add_finding(
            findings,
            "required_bones_present_not_array",
            "error",
            "open",
            "required_bones_present must be an array.",
        )

    missing_required_bones = report.get("missing_required_bones")
    if not isinstance(missing_required_bones, list):
        missing_required_bones = []
        add_finding(
            findings,
            "missing_required_bones_not_array",
            "error",
            "open",
            "missing_required_bones must be an array.",
        )

    extra_bones = report.get("extra_bones")
    if not isinstance(extra_bones, list):
        extra_bones = []
        add_finding(
            findings,
            "extra_bones_not_array",
            "error",
            "open",
            "extra_bones must be an array.",
        )

    if missing_required_bones:
        add_finding(
            findings,
            "missing_required_bones_present",
            "error",
            "open",
            "missing_required_bones must be empty for contract pass readiness.",
            {"missing_required_bones": missing_required_bones},
        )

    if isinstance(bone_count, int) and isinstance(required_bones_present, list):
        if bone_count < len(required_bones_present):
            add_finding(
                findings,
                "bone_count_too_small",
                "error",
                "open",
                "bone_count cannot be smaller than required_bones_present length.",
                {
                    "bone_count": bone_count,
                    "required_bones_present_count": len(required_bones_present),
                },
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

    safety = report.get("safety", {}) if isinstance(report.get("safety"), dict) else {}
    for safety_field in (
        "dcc_execution_status",
        "blender_execution_status",
        "o3de_execution_status",
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

    declared_status = str(report.get("status", "")).strip()
    if declared_status not in ALLOWED_STATUS:
        add_finding(
            findings,
            "status_invalid",
            "error",
            "open",
            "status must be pass|warn|fail|pending_manual.",
            {"actual": declared_status},
        )

    input_findings = report.get("findings", [])
    if not isinstance(input_findings, list):
        input_findings = []
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

    qc_check = attachment.get("qc_check") if isinstance(attachment.get("qc_check"), dict) else {}
    qc_check_id = str(qc_check.get("check_id", "")).strip()
    if qc_check_id != CHECK_ID:
        add_finding(
            findings,
            "manifest_qc_check_id_invalid",
            "error",
            "open",
            f"manifest_attachment.qc_check.check_id must be {CHECK_ID}.",
            {"actual": qc_check_id},
        )

    computed_from_components = _collect_component_status(report)
    computed_from_findings = _collect_findings_status(findings + input_findings)
    computed_status = _merge_status(computed_from_components, computed_from_findings)

    if declared_status in ALLOWED_STATUS and declared_status != computed_status:
        add_finding(
            findings,
            "status_mismatch",
            "error",
            "open",
            "report.status does not match computed status.",
            {
                "declared": declared_status,
                "computed": computed_status,
            },
        )
        computed_status = "fail"

    qc_severity = _status_severity(computed_status)

    output_payload: Dict[str, Any] = {
        "status": computed_status,
        "check_id": CHECK_ID,
        "contract_id": EXPECTED_PROFILE_ID,
        "evidence_class": skeleton_evidence_class,
        "claim_status": claim_status,
        "candidate_id": str(report.get("candidate_id", "")).strip(),
        "source_asset_reference": str(report.get("source_asset_reference", "")).strip(),
        "source_evidence_ref": source_evidence_ref,
        "findings": findings + input_findings,
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
                    "candidate_id": str(report.get("candidate_id", "")).strip(),
                    "source_asset_reference": str(report.get("source_asset_reference", "")).strip(),
                    "source_evidence_ref": source_evidence_ref,
                    "skeleton_profile_id": skeleton_profile_id,
                    "skeleton_profile_version": skeleton_profile_version,
                    "skeleton_evidence_class": skeleton_evidence_class,
                    "root_bone_status": str(report.get("root_bone_status", "")).strip(),
                    "pelvis_bone_status": str(report.get("pelvis_bone_status", "")).strip(),
                    "spine_chain_status": str(report.get("spine_chain_status", "")).strip(),
                    "neck_head_status": str(report.get("neck_head_status", "")).strip(),
                    "left_arm_chain_status": str(report.get("left_arm_chain_status", "")).strip(),
                    "right_arm_chain_status": str(report.get("right_arm_chain_status", "")).strip(),
                    "left_leg_chain_status": str(report.get("left_leg_chain_status", "")).strip(),
                    "right_leg_chain_status": str(report.get("right_leg_chain_status", "")).strip(),
                    "hand_finger_status": str(report.get("hand_finger_status", "")).strip(),
                    "naming_convention_status": str(report.get("naming_convention_status", "")).strip(),
                    "hierarchy_status": str(report.get("hierarchy_status", "")).strip(),
                    "orientation_status": str(report.get("orientation_status", "")).strip(),
                    "scale_status": str(report.get("scale_status", "")).strip(),
                    "bind_pose_status": str(report.get("bind_pose_status", "")).strip(),
                    "retarget_readiness_status": str(report.get("retarget_readiness_status", "")).strip(),
                    "animation_smoke_dependency_status": str(report.get("animation_smoke_dependency_status", "")).strip(),
                    "bone_count": report.get("bone_count"),
                    "required_bones_present": report.get("required_bones_present"),
                    "missing_required_bones": report.get("missing_required_bones"),
                    "extra_bones": report.get("extra_bones"),
                    "claim_status": claim_status,
                    "safety": {
                        "dcc_execution_status": str(safety.get("dcc_execution_status", "")).strip(),
                        "blender_execution_status": str(safety.get("blender_execution_status", "")).strip(),
                        "o3de_execution_status": str(safety.get("o3de_execution_status", "")).strip(),
                        "production_write_status": str(safety.get("production_write_status", "")).strip(),
                    },
                    "evidence_class": skeleton_evidence_class,
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
