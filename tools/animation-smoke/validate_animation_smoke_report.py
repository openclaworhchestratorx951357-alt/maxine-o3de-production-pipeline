#!/usr/bin/env python3
"""Validate evidence-only animation smoke reports for release-lane integration."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_SUMMARY_STATUS = {"pass", "warn", "fail", "unknown"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
ALLOWED_EVIDENCE_CLASS = {"fixture", "imported", "controlled_real"}
ALLOWED_CLAIM_STATUS = {"evidence_only", "not_authoritative"}
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "ANIMATION_SMOKE_v1_REPORT"
EXPECTED_SMOKE_CONTRACT_ID = "ANIMATION_SMOKE_v1"
EXPECTED_ANIMATION_PROFILE_ID = "ANIMATION_SMOKE_v1"
EXPECTED_SKELETON_PROFILE_ID = "MAX_BIPED_v1"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "animation_smoke_v1"
CONTRACT_ID = "ANIMATION_SMOKE_v1"
REQUIRED_STATUS_FIELDS = [
    "skeleton_compatibility_status",
    "root_motion_status",
    "bind_pose_compatibility_status",
    "clip_duration_status",
    "missing_clip_status",
    "retarget_readiness_status",
    "frame_range_status",
    "animation_budget_status",
]
OPTIONAL_STATUS_FIELDS = [
    "loopability_status",
    "motion_event_status",
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


def _collect_component_status(report: Dict[str, Any]) -> str:
    seen: List[str] = []
    for field in REQUIRED_STATUS_FIELDS + OPTIONAL_STATUS_FIELDS:
        value = report.get(field)
        if isinstance(value, str) and value in ALLOWED_STATUS:
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

    for required in (
        "job_id",
        "package_id",
        "lane",
        "candidate_id",
        "source_asset_reference",
        "source_evidence_ref",
        "animation_profile_id",
        "animation_profile_version",
        "actor_asset_reference",
        "motion_asset_reference",
        "skeleton_profile_id",
        "claim_status",
    ):
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
    source_asset_reference = str(report.get("source_asset_reference", "")).strip()
    source_evidence_ref = str(report.get("source_evidence_ref", "")).strip()
    animation_profile_id = str(report.get("animation_profile_id", "")).strip()
    animation_profile_version = str(report.get("animation_profile_version", "")).strip()
    evidence_class = str(report.get("evidence_class", "")).strip()
    actor_asset_reference = str(report.get("actor_asset_reference", "")).strip()
    motion_asset_reference = str(report.get("motion_asset_reference", "")).strip()
    motion_set_reference = str(report.get("motion_set_reference", "")).strip()
    anim_graph_reference = str(report.get("anim_graph_reference", "")).strip()
    skeleton_profile_id = str(report.get("skeleton_profile_id", "")).strip()
    claim_status = str(report.get("claim_status", "")).strip()

    if animation_profile_id and animation_profile_id != EXPECTED_ANIMATION_PROFILE_ID:
        add_finding(
            findings,
            "animation_profile_id_invalid",
            "error",
            "open",
            f"animation_profile_id must be {EXPECTED_ANIMATION_PROFILE_ID}.",
            {"actual": animation_profile_id},
        )
    if not animation_profile_version:
        add_finding(
            findings,
            "animation_profile_version_missing",
            "error",
            "open",
            "animation_profile_version is required.",
        )

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

    if claim_status not in ALLOWED_CLAIM_STATUS:
        add_finding(
            findings,
            "claim_status_invalid",
            "error",
            "open",
            "claim_status must be evidence_only|not_authoritative.",
            {"actual": claim_status},
        )

    if source_evidence_ref and _contains_unsafe_path_tokens(source_evidence_ref):
        add_finding(
            findings,
            "source_evidence_ref_unsafe",
            "error",
            "open",
            "source_evidence_ref contains unsafe traversal or shell tokens.",
            {"source_evidence_ref": source_evidence_ref},
        )

    if skeleton_profile_id and skeleton_profile_id != EXPECTED_SKELETON_PROFILE_ID:
        add_finding(
            findings,
            "skeleton_profile_id_invalid",
            "error",
            "open",
            f"skeleton_profile_id must be {EXPECTED_SKELETON_PROFILE_ID}.",
            {"actual": skeleton_profile_id},
        )

    if source_asset_reference and _contains_unsafe_path_tokens(source_asset_reference):
        add_finding(
            findings,
            "source_asset_reference_unsafe",
            "error",
            "open",
            "source_asset_reference contains unsafe traversal or shell tokens.",
            {"source_asset_reference": source_asset_reference},
        )
    if actor_asset_reference and _contains_unsafe_path_tokens(actor_asset_reference):
        add_finding(
            findings,
            "actor_asset_reference_unsafe",
            "error",
            "open",
            "actor_asset_reference contains unsafe traversal or shell tokens.",
            {"actor_asset_reference": actor_asset_reference},
        )
    if motion_asset_reference and _contains_unsafe_path_tokens(motion_asset_reference):
        add_finding(
            findings,
            "motion_asset_reference_unsafe",
            "error",
            "open",
            "motion_asset_reference contains unsafe traversal or shell tokens.",
            {"motion_asset_reference": motion_asset_reference},
        )
    if motion_set_reference and _contains_unsafe_path_tokens(motion_set_reference):
        add_finding(
            findings,
            "motion_set_reference_unsafe",
            "error",
            "open",
            "motion_set_reference contains unsafe traversal or shell tokens.",
            {"motion_set_reference": motion_set_reference},
        )
    if anim_graph_reference and _contains_unsafe_path_tokens(anim_graph_reference):
        add_finding(
            findings,
            "anim_graph_reference_unsafe",
            "error",
            "open",
            "anim_graph_reference contains unsafe traversal or shell tokens.",
            {"anim_graph_reference": anim_graph_reference},
        )

    for field_name in REQUIRED_STATUS_FIELDS:
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
    for field_name in OPTIONAL_STATUS_FIELDS:
        value = str(report.get(field_name, "")).strip()
        if value and value not in ALLOWED_STATUS:
            add_finding(
                findings,
                f"{field_name}_invalid",
                "error",
                "open",
                f"{field_name} must be pass|warn|fail|pending_manual when present.",
                {"actual": value},
            )

    safety = report.get("safety", {})
    if not isinstance(safety, dict):
        safety = {}
        add_finding(findings, "safety_not_object", "error", "open", "safety must be an object.")
    for safety_field in (
        "dcc_execution_status",
        "blender_execution_status",
        "o3de_execution_status",
        "asset_processor_execution_status",
        "runtime_playback_status",
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
    if target_skeleton_contract_id != EXPECTED_SKELETON_PROFILE_ID:
        add_finding(
            findings,
            "target_skeleton_contract_id_invalid",
            "error",
            "open",
            f"smoke_profile.target_skeleton_contract_id must be {EXPECTED_SKELETON_PROFILE_ID}.",
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

    smoke_clip_names = report.get("smoke_clip_names", [])
    if not isinstance(smoke_clip_names, list) or not all(isinstance(x, str) and x.strip() for x in smoke_clip_names):
        add_finding(
            findings,
            "smoke_clip_names_invalid",
            "error",
            "open",
            "smoke_clip_names must be a non-empty string array.",
        )
        smoke_clip_names = []
    if not smoke_clip_names:
        add_finding(
            findings,
            "smoke_clip_names_missing",
            "error",
            "open",
            "At least one smoke-test clip must be represented.",
        )

    top_clip_count = report.get("clip_count")
    if not isinstance(top_clip_count, int) or top_clip_count < 0:
        add_finding(
            findings,
            "clip_count_invalid",
            "error",
            "open",
            "clip_count must be integer >= 0.",
            {"actual": top_clip_count},
        )
        top_clip_count = 0
    if top_clip_count != len(smoke_clip_names):
        add_finding(
            findings,
            "clip_count_mismatch",
            "warning",
            "open",
            "clip_count does not match smoke_clip_names length.",
            {"clip_count": top_clip_count, "smoke_clip_names_length": len(smoke_clip_names)},
        )

    summary = report.get("animation_summary", {}) if isinstance(report.get("animation_summary"), dict) else {}
    required_clips = summary.get("required_clips", [])
    present_clips = summary.get("present_clips", [])
    reported_missing_clips = summary.get("missing_clips", [])
    summary_clip_count = summary.get("clip_count")
    loop_status = str(summary.get("loop_playback_status", "")).strip()
    pose_status = str(summary.get("pose_stability_status", "")).strip()
    summary_root_motion_status = str(summary.get("root_motion_status", "")).strip()
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
    if not isinstance(summary_clip_count, int) or summary_clip_count < 0:
        add_finding(findings, "summary_clip_count_invalid", "error", "open", "animation_summary.clip_count must be integer >= 0.")
        summary_clip_count = 0
    if summary_clip_count != len(present_clips):
        add_finding(
            findings,
            "summary_clip_count_mismatch",
            "warning",
            "open",
            "animation_summary.clip_count does not match present_clips length.",
            {"clip_count": summary_clip_count, "present_clips_length": len(present_clips)},
        )
    if sorted(smoke_clip_names) != sorted(present_clips):
        add_finding(
            findings,
            "smoke_clip_names_present_clips_mismatch",
            "warning",
            "open",
            "smoke_clip_names and animation_summary.present_clips differ.",
            {"smoke_clip_names": smoke_clip_names, "present_clips": present_clips},
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

    missing_clip_status = str(report.get("missing_clip_status", "")).strip()
    if computed_missing and missing_clip_status == "pass":
        add_finding(
            findings,
            "missing_clip_status_mismatch",
            "error",
            "open",
            "missing_clip_status cannot be pass when required clips are missing.",
            {"missing_clips": computed_missing, "missing_clip_status": missing_clip_status},
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
        ("summary_root_motion_status", summary_root_motion_status),
    ):
        if field_value not in ALLOWED_SUMMARY_STATUS:
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

    top_root_motion_status = str(report.get("root_motion_status", "")).strip()
    if summary_root_motion_status == "fail" and top_root_motion_status != "fail":
        add_finding(
            findings,
            "root_motion_status_inconsistent_with_summary",
            "error",
            "open",
            "top-level root_motion_status must be fail when summary root motion reports fail.",
            {
                "root_motion_status": top_root_motion_status,
                "summary_root_motion_status": summary_root_motion_status,
            },
        )

    if declared_status == "pass":
        for field_name in (
            "skeleton_compatibility_status",
            "bind_pose_compatibility_status",
            "clip_duration_status",
            "missing_clip_status",
            "retarget_readiness_status",
            "frame_range_status",
            "animation_budget_status",
        ):
            value = str(report.get(field_name, "")).strip()
            if value != "pass":
                add_finding(
                    findings,
                    f"{field_name}_must_pass_when_report_pass",
                    "error",
                    "open",
                    f"{field_name} must be pass when report.status is pass.",
                    {"actual": value},
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

    component_status = _collect_component_status(report)
    findings_status = derive_status(findings + input_findings)
    computed_status = _merge_status(component_status, findings_status)
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
        "evidence_class": evidence_class,
        "claim_status": claim_status,
        "candidate_id": candidate_id,
        "source_asset_reference": source_asset_reference,
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
                    "candidate_id": candidate_id,
                    "source_asset_reference": source_asset_reference,
                    "source_evidence_ref": source_evidence_ref,
                    "animation_profile_id": animation_profile_id,
                    "animation_profile_version": animation_profile_version,
                    "evidence_class": evidence_class,
                    "actor_asset_reference": actor_asset_reference,
                    "motion_asset_reference": motion_asset_reference,
                    "motion_set_reference": motion_set_reference,
                    "anim_graph_reference": anim_graph_reference,
                    "skeleton_profile_id": skeleton_profile_id,
                    "skeleton_compatibility_status": str(report.get("skeleton_compatibility_status", "")).strip(),
                    "root_motion_status": top_root_motion_status,
                    "bind_pose_compatibility_status": str(report.get("bind_pose_compatibility_status", "")).strip(),
                    "clip_count": top_clip_count,
                    "smoke_clip_names": smoke_clip_names,
                    "clip_duration_status": str(report.get("clip_duration_status", "")).strip(),
                    "missing_clip_status": missing_clip_status,
                    "retarget_readiness_status": str(report.get("retarget_readiness_status", "")).strip(),
                    "loopability_status": str(report.get("loopability_status", "")).strip(),
                    "motion_event_status": str(report.get("motion_event_status", "")).strip(),
                    "frame_range_status": str(report.get("frame_range_status", "")).strip(),
                    "animation_budget_status": str(report.get("animation_budget_status", "")).strip(),
                    "claim_status": claim_status,
                    "safety": {
                        "dcc_execution_status": str(safety.get("dcc_execution_status", "")).strip(),
                        "blender_execution_status": str(safety.get("blender_execution_status", "")).strip(),
                        "o3de_execution_status": str(safety.get("o3de_execution_status", "")).strip(),
                        "asset_processor_execution_status": str(safety.get("asset_processor_execution_status", "")).strip(),
                        "runtime_playback_status": str(safety.get("runtime_playback_status", "")).strip(),
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
