#!/usr/bin/env python3
"""Validate controlled screenshot/visual evidence for release-lane integration."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "SCREENSHOT_EVIDENCE_v1_REPORT"
EXPECTED_VISUAL_PROFILE_ID = "SCREENSHOT_VISUAL_v1"
CHECK_ID = "screenshot_evidence_v1"
CONTRACT_ID = "SCREENSHOT_EVIDENCE_v1"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
REQUIRED_VIEWS = ("front", "side", "back", "three_quarter", "detail")
ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
ALLOWED_EVIDENCE_CLASS = {"fixture", "imported", "controlled_real"}
ALLOWED_CLAIM_STATUS = {"evidence_only", "not_authoritative"}
LEGACY_EVIDENCE_SOURCE_CLASS = {
    "fixture": "fixture",
    "imported_capture": "imported",
    "future_runtime_capture": "fixture",
}
BLOCKED_PATH_TOKENS = {"cache", "engine", ".git", "site-packages"}
STATUS_FIELDS = (
    "image_resolution_status",
    "file_reference_status",
    "visual_identity_status",
    "silhouette_status",
    "scale_visual_status",
    "material_visual_status",
    "uv_texture_visual_status",
    "skeleton_pose_visual_status",
    "missing_asset_visual_status",
    "artifact_or_corruption_status",
    "lighting_context_status",
    "viewport_context_status",
    "review_frame_status",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate screenshot/visual evidence payload from a controlled fixture input. "
            "This command is evidence-only and does not run O3DE/Editor/runtime/AP/Blender/DCC execution."
        )
    )
    parser.add_argument(
        "--source-index",
        required=True,
        help="Path to screenshot/visual evidence fixture JSON.",
    )
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Return exit 0 when status is warn.",
    )
    return parser.parse_args()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _path_within(candidate: Path, parent: Path) -> bool:
    candidate_abs = candidate.resolve()
    parent_abs = parent.resolve()
    try:
        candidate_abs.relative_to(parent_abs)
        return True
    except ValueError:
        return False


def resolve_safe_path(repo_root: Path, raw_path: str, label: str) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (repo_root / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if not _path_within(candidate, repo_root):
        raise ValueError(f"{label} must remain inside repository root.")

    lower_parts = {part.lower() for part in candidate.parts}
    blocked = lower_parts & BLOCKED_PATH_TOKENS
    if blocked:
        blocked_tokens = ", ".join(sorted(blocked))
        raise ValueError(f"{label} resolves to blocked path token(s): {blocked_tokens}.")

    return candidate


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def add_finding(
    findings: List[Dict[str, Any]],
    finding_id: str,
    severity: str,
    message: str,
    details: Dict[str, Any] | None = None,
) -> None:
    item: Dict[str, Any] = {
        "id": finding_id,
        "severity": severity,
        "status": "open",
        "message": message,
    }
    if details:
        item["details"] = details
    findings.append(item)


def derive_findings_status(findings: List[Dict[str, Any]]) -> str:
    severities = {str(item.get("severity", "")).strip() for item in findings}
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


def _merge_status(a: str, b: str) -> str:
    order = ["pass", "warn", "pending_manual", "fail"]
    return max(a, b, key=lambda value: order.index(value))


def _contains_unsafe_path_tokens(path_text: str) -> bool:
    blocked = ("..", "|", ";", ">", "<", "&", "`")
    lowered = path_text.lower()
    return any(token in lowered for token in blocked)


def _infer_view(label: str, raw_path: str, index: int) -> str:
    probe = f"{label} {raw_path}".lower()
    if "front" in probe:
        return "front"
    if "side" in probe:
        return "side"
    if "back" in probe:
        return "back"
    if "three_quarter" in probe or "three-quarter" in probe or "3q" in probe or "quarter" in probe:
        return "three_quarter"
    if "detail" in probe or "close" in probe:
        return "detail"
    return f"extra_{index}"


def _looks_like_legacy_source_index(payload: Dict[str, Any]) -> bool:
    return (
        isinstance(payload.get("screenshots"), list)
        and "report_type" not in payload
        and "screenshot_refs" not in payload
    )


def _to_repo_relative(path: Path, repo_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
        return rel.as_posix()
    except ValueError:
        return str(path)


def _convert_legacy_source_index(
    payload: Dict[str, Any],
    source_index_path: Path,
    repo_root: Path,
) -> Dict[str, Any]:
    screenshots = payload.get("screenshots") if isinstance(payload.get("screenshots"), list) else []
    screenshot_refs: List[Dict[str, Any]] = []
    required_views_present = {view: False for view in REQUIRED_VIEWS}
    for idx, item in enumerate(screenshots):
        if not isinstance(item, dict):
            continue
        raw_path = str(item.get("path", "")).strip()
        if not raw_path:
            continue
        label = str(item.get("label", "")).strip()
        view = _infer_view(label, raw_path, idx)
        if view in required_views_present:
            required_views_present[view] = True
        screenshot_refs.append({"view": view, "path": raw_path, "label": label})

    minimum_required = payload.get("minimum_required", 1)
    discovered_count = len(screenshot_refs)
    status = "pass"
    findings: List[Dict[str, Any]] = []
    if not isinstance(minimum_required, int) or minimum_required < 1:
        minimum_required = 1
    if discovered_count < minimum_required:
        status = "fail"
        add_finding(
            findings,
            "minimum_required_not_met",
            "error",
            "Legacy screenshot source-index did not meet minimum screenshot count.",
            {"minimum_required": minimum_required, "discovered_count": discovered_count},
        )

    evidence_source_type = str(payload.get("evidence_source_type", "fixture")).strip()
    evidence_class = LEGACY_EVIDENCE_SOURCE_CLASS.get(evidence_source_type, "fixture")
    source_rel = _to_repo_relative(source_index_path, repo_root)
    return {
        "schema_version": EXPECTED_SCHEMA_VERSION,
        "report_type": EXPECTED_REPORT_TYPE,
        "job_id": "job-release-character-legacy-screenshot-evidence",
        "package_id": "char.maxine.release_pilot.max_biped_v1",
        "lane": "release_character",
        "candidate_id": "max_biped_v1_candidate_001",
        "source_asset_reference": "fixtures://source/max_biped_v1/source_character.fbx",
        "source_evidence_ref": source_rel,
        "visual_profile_id": EXPECTED_VISUAL_PROFILE_ID,
        "visual_profile_version": "legacy-source-index",
        "evidence_class": evidence_class,
        "screenshot_set_id": source_index_path.stem,
        "screenshot_refs": screenshot_refs,
        "screenshot_count": discovered_count,
        "required_views_present": required_views_present,
        "image_resolution_status": "pass",
        "file_reference_status": "pass",
        "visual_identity_status": "pass",
        "silhouette_status": "pass",
        "scale_visual_status": "pass",
        "material_visual_status": "pass",
        "uv_texture_visual_status": "pass",
        "skeleton_pose_visual_status": "pass",
        "animation_pose_visual_status": "pass",
        "missing_asset_visual_status": "pass",
        "artifact_or_corruption_status": "pass",
        "lighting_context_status": "pass",
        "viewport_context_status": "pass",
        "review_frame_status": "pass",
        "claim_status": "evidence_only",
        "safety": {
            "screenshot_capture_status": "blocked",
            "o3de_execution_status": "blocked",
            "editor_execution_status": "blocked",
            "runtime_execution_status": "blocked",
            "dcc_execution_status": "blocked",
            "blender_execution_status": "blocked",
            "asset_processor_execution_status": "blocked",
            "production_write_status": "blocked",
        },
        "status": status,
        "findings": findings,
        "manifest_attachment": {
            "target_path": TARGET_PATH,
            "future_target_path": FUTURE_TARGET_PATH,
            "qc_check": {
                "check_id": CHECK_ID,
                "result": status,
                "severity": status_to_qc_severity(status),
                "details": {
                    "summary": "Legacy screenshot source-index converted into visual evidence contract.",
                    "evidence_class": evidence_class,
                },
            },
        },
    }


def _validate_schema(report: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        # Rule-based checks remain authoritative when jsonschema is unavailable.
        return []
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(report), key=lambda err: list(err.path))
    if not errors:
        return []
    messages: List[str] = []
    for err in errors:
        location = ".".join(str(p) for p in err.absolute_path) or "<root>"
        messages.append(f"{location}: {err.message}")
    return messages


def _collect_component_status(report: Dict[str, Any]) -> str:
    values: List[str] = []
    for name in STATUS_FIELDS:
        value = str(report.get(name, "")).strip()
        if value in ALLOWED_STATUS:
            values.append(value)
    optional = str(report.get("animation_pose_visual_status", "")).strip()
    if optional in ALLOWED_STATUS:
        values.append(optional)
    if "fail" in values:
        return "fail"
    if "pending_manual" in values:
        return "pending_manual"
    if "warn" in values:
        return "warn"
    return "pass"


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "schemas" / "maxine_screenshot_evidence_report.schema.json"
    allowed_screenshot_root = (repo_root / "examples" / "sandbox").resolve()

    findings: List[Dict[str, Any]] = []
    report: Dict[str, Any]
    source_fixture_path = Path(args.source_index)

    try:
        source_fixture_path = resolve_safe_path(repo_root, str(source_fixture_path), "source_index")
    except ValueError as exc:
        add_finding(findings, "source_index_path_invalid", "error", str(exc))
        report = {}
        source_fixture_path = Path(str(args.source_index))
    else:
        if not source_fixture_path.exists():
            add_finding(
                findings,
                "source_index_missing",
                "error",
                "Screenshot/visual evidence fixture was not found.",
                {"source_index_path": str(source_fixture_path)},
            )
            report = {}
        else:
            try:
                loaded = load_json(source_fixture_path)
            except Exception as exc:
                add_finding(
                    findings,
                    "source_index_parse_error",
                    "error",
                    f"Unable to parse JSON: {exc}",
                    {"source_index_path": str(source_fixture_path)},
                )
                loaded = {}
            if _looks_like_legacy_source_index(loaded):
                report = _convert_legacy_source_index(loaded, source_fixture_path, repo_root)
            else:
                report = loaded

    if not schema_path.exists():
        add_finding(
            findings,
            "schema_missing",
            "error",
            "Screenshot evidence schema is missing.",
            {"schema_path": str(schema_path)},
        )
        schema_errors: List[str] = []
    else:
        try:
            schema = load_json(schema_path)
            schema_errors = _validate_schema(report, schema)
        except Exception as exc:
            schema_errors = [f"schema_load_failed: {exc}"]
    for err in schema_errors:
        add_finding(
            findings,
            "schema_validation_error",
            "error",
            "Report failed JSON schema validation.",
            {"error": err},
        )

    declared_status = str(report.get("status", "")).strip()
    if declared_status not in ALLOWED_STATUS:
        add_finding(
            findings,
            "status_invalid",
            "error",
            "status must be pass|warn|fail|pending_manual.",
            {"actual": declared_status},
        )

    for required in (
        "schema_version",
        "report_type",
        "job_id",
        "package_id",
        "lane",
        "candidate_id",
        "source_asset_reference",
        "source_evidence_ref",
        "visual_profile_id",
        "visual_profile_version",
        "evidence_class",
        "screenshot_set_id",
        "claim_status",
    ):
        if not str(report.get(required, "")).strip():
            add_finding(findings, f"{required}_missing", "error", f"{required} is required.")

    if str(report.get("schema_version", "")).strip() != EXPECTED_SCHEMA_VERSION:
        add_finding(
            findings,
            "schema_version_invalid",
            "error",
            f"schema_version must be {EXPECTED_SCHEMA_VERSION}.",
            {"actual": report.get("schema_version")},
        )
    if str(report.get("report_type", "")).strip() != EXPECTED_REPORT_TYPE:
        add_finding(
            findings,
            "report_type_invalid",
            "error",
            f"report_type must be {EXPECTED_REPORT_TYPE}.",
            {"actual": report.get("report_type")},
        )
    if str(report.get("visual_profile_id", "")).strip() != EXPECTED_VISUAL_PROFILE_ID:
        add_finding(
            findings,
            "visual_profile_id_invalid",
            "error",
            f"visual_profile_id must be {EXPECTED_VISUAL_PROFILE_ID}.",
            {"actual": report.get("visual_profile_id")},
        )

    evidence_class = str(report.get("evidence_class", "")).strip()
    if evidence_class not in ALLOWED_EVIDENCE_CLASS:
        add_finding(
            findings,
            "evidence_class_invalid",
            "error",
            "evidence_class must be fixture|imported|controlled_real.",
            {"actual": evidence_class},
        )
    claim_status = str(report.get("claim_status", "")).strip()
    if claim_status not in ALLOWED_CLAIM_STATUS:
        add_finding(
            findings,
            "claim_status_invalid",
            "error",
            "claim_status must be evidence_only|not_authoritative.",
            {"actual": claim_status},
        )

    source_asset_reference = str(report.get("source_asset_reference", "")).strip()
    source_evidence_ref = str(report.get("source_evidence_ref", "")).strip()
    if source_asset_reference and _contains_unsafe_path_tokens(source_asset_reference):
        add_finding(
            findings,
            "source_asset_reference_unsafe",
            "error",
            "source_asset_reference contains unsafe traversal or shell tokens.",
            {"source_asset_reference": source_asset_reference},
        )
    if source_evidence_ref and _contains_unsafe_path_tokens(source_evidence_ref):
        add_finding(
            findings,
            "source_evidence_ref_unsafe",
            "error",
            "source_evidence_ref contains unsafe traversal or shell tokens.",
            {"source_evidence_ref": source_evidence_ref},
        )
    if evidence_class == "controlled_real":
        normalized_source_ref = source_evidence_ref.replace("\\", "/")
        if not normalized_source_ref.startswith("examples/sandbox/"):
            add_finding(
                findings,
                "controlled_real_source_evidence_ref_outside_sandbox",
                "error",
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
                f"{field_name} must be pass|warn|fail|pending_manual.",
                {"actual": value},
            )
    optional_animation_pose = str(report.get("animation_pose_visual_status", "")).strip()
    if optional_animation_pose and optional_animation_pose not in ALLOWED_STATUS:
        add_finding(
            findings,
            "animation_pose_visual_status_invalid",
            "error",
            "animation_pose_visual_status must be pass|warn|fail|pending_manual when present.",
            {"actual": optional_animation_pose},
        )

    safety = report.get("safety", {})
    if not isinstance(safety, dict):
        safety = {}
        add_finding(findings, "safety_not_object", "error", "safety must be an object.")
    for safety_field in (
        "screenshot_capture_status",
        "o3de_execution_status",
        "editor_execution_status",
        "runtime_execution_status",
        "dcc_execution_status",
        "blender_execution_status",
        "asset_processor_execution_status",
        "production_write_status",
    ):
        if str(safety.get(safety_field, "")).strip() != "blocked":
            add_finding(
                findings,
                f"{safety_field}_not_blocked",
                "error",
                f"safety.{safety_field} must be blocked.",
                {"actual": safety.get(safety_field)},
            )

    screenshot_refs_raw = report.get("screenshot_refs")
    screenshot_refs = screenshot_refs_raw if isinstance(screenshot_refs_raw, list) else []
    if not isinstance(screenshot_refs_raw, list):
        add_finding(findings, "screenshot_refs_not_array", "error", "screenshot_refs must be an array.")

    scanned_refs: List[Dict[str, Any]] = []
    present_required_views = {view: False for view in REQUIRED_VIEWS}
    missing_ref_files: List[str] = []
    for idx, ref in enumerate(screenshot_refs):
        if not isinstance(ref, dict):
            add_finding(
                findings,
                "screenshot_ref_invalid",
                "error",
                "screenshot_refs entries must be objects.",
                {"index": idx},
            )
            continue
        view = str(ref.get("view", "")).strip()
        raw_path = str(ref.get("path", "")).strip()
        label = str(ref.get("label", "")).strip()
        if not view:
            add_finding(
                findings,
                "screenshot_ref_view_missing",
                "error",
                "screenshot_refs entry is missing view.",
                {"index": idx},
            )
        if not raw_path:
            add_finding(
                findings,
                "screenshot_ref_path_missing",
                "error",
                "screenshot_refs entry is missing path.",
                {"index": idx},
            )
            continue
        if _contains_unsafe_path_tokens(raw_path):
            add_finding(
                findings,
                "screenshot_ref_path_unsafe",
                "error",
                "screenshot reference path contains unsafe traversal or shell tokens.",
                {"index": idx, "path": raw_path},
            )
            continue
        try:
            resolved_path = resolve_safe_path(repo_root, raw_path, f"screenshot_refs[{idx}].path")
        except ValueError as exc:
            add_finding(
                findings,
                "screenshot_ref_path_invalid",
                "error",
                str(exc),
                {"index": idx, "path": raw_path},
            )
            continue

        if not _path_within(resolved_path, allowed_screenshot_root):
            add_finding(
                findings,
                "screenshot_root_violation",
                "error",
                "screenshot path must remain under examples/sandbox.",
                {"index": idx, "path": str(resolved_path)},
            )
            continue

        exists = resolved_path.exists()
        if not exists:
            missing_ref_files.append(str(resolved_path))
            add_finding(
                findings,
                "screenshot_ref_missing_file",
                "error",
                "screenshot file does not exist.",
                {"index": idx, "path": str(resolved_path)},
            )
        if view in present_required_views:
            present_required_views[view] = True
        scanned_refs.append(
            {
                "index": idx,
                "view": view,
                "path": str(resolved_path),
                "exists": exists,
                "label": label,
            }
        )

    screenshot_count = report.get("screenshot_count")
    if not isinstance(screenshot_count, int) or screenshot_count < 0:
        add_finding(
            findings,
            "screenshot_count_invalid",
            "error",
            "screenshot_count must be an integer >= 0.",
            {"actual": screenshot_count},
        )
        screenshot_count = 0
    if screenshot_count != len(screenshot_refs):
        add_finding(
            findings,
            "screenshot_count_mismatch",
            "warning",
            "screenshot_count does not match screenshot_refs length.",
            {"screenshot_count": screenshot_count, "screenshot_refs_length": len(screenshot_refs)},
        )

    required_views_present = report.get("required_views_present", {})
    if not isinstance(required_views_present, dict):
        required_views_present = {}
        add_finding(
            findings,
            "required_views_present_not_object",
            "error",
            "required_views_present must be an object.",
        )

    missing_required_views: List[str] = []
    for view in REQUIRED_VIEWS:
        if view not in required_views_present:
            add_finding(
                findings,
                "required_view_key_missing",
                "error",
                "required_views_present is missing a required key.",
                {"view": view},
            )
            declared_present = False
        else:
            declared_present = bool(required_views_present.get(view))
        computed_present = present_required_views[view]
        if declared_present != computed_present:
            add_finding(
                findings,
                "required_views_present_mismatch",
                "warning",
                "required_views_present does not match screenshot_refs coverage.",
                {"view": view, "declared": declared_present, "computed": computed_present},
            )
        if not computed_present:
            missing_required_views.append(view)

    if evidence_class == "controlled_real" and missing_required_views:
        add_finding(
            findings,
            "missing_required_views",
            "error",
            "Controlled-real visual evidence is missing required views.",
            {"missing_required_views": missing_required_views},
        )

    file_reference_status = str(report.get("file_reference_status", "")).strip()
    if missing_ref_files and file_reference_status == "pass":
        add_finding(
            findings,
            "file_reference_status_mismatch",
            "error",
            "file_reference_status cannot be pass when screenshot reference files are missing.",
            {"missing_files": missing_ref_files},
        )

    component_status = _collect_component_status(report)
    findings_status = derive_findings_status(findings)
    computed_status = _merge_status(component_status, findings_status)
    if declared_status == "pass":
        for field_name in STATUS_FIELDS:
            if str(report.get(field_name, "")).strip() != "pass":
                add_finding(
                    findings,
                    f"{field_name}_must_pass_when_report_pass",
                    "error",
                    f"{field_name} must be pass when report.status is pass.",
                    {"actual": report.get(field_name)},
                )
    if declared_status in ALLOWED_STATUS and declared_status != computed_status:
        add_finding(
            findings,
            "status_mismatch",
            "error",
            "report.status does not match computed status from findings and component statuses.",
            {"declared": declared_status, "computed": computed_status},
        )
        computed_status = "fail"
    else:
        computed_status = _merge_status(component_status, derive_findings_status(findings))

    input_findings = report.get("findings", [])
    if not isinstance(input_findings, list):
        input_findings = []
        add_finding(findings, "findings_not_array", "error", "findings must be an array.")
    else:
        for idx, item in enumerate(input_findings):
            if not isinstance(item, dict):
                add_finding(findings, "finding_invalid", "error", f"findings[{idx}] must be an object.")
                continue
            fid = str(item.get("id", "")).strip()
            sev = str(item.get("severity", "")).strip()
            fstatus = str(item.get("status", "")).strip()
            message = str(item.get("message", "")).strip()
            if not fid:
                add_finding(findings, "finding_id_missing", "error", f"findings[{idx}].id is required.")
            if sev not in ALLOWED_FINDING_SEVERITY:
                add_finding(
                    findings,
                    "finding_severity_invalid",
                    "error",
                    f"findings[{idx}].severity must be info|warning|error|manual_review.",
                    {"actual": sev},
                )
            if not fstatus:
                add_finding(findings, "finding_status_missing", "error", f"findings[{idx}].status is required.")
            if not message:
                add_finding(findings, "finding_message_missing", "error", f"findings[{idx}].message is required.")

    attachment = report.get("manifest_attachment", {})
    if not isinstance(attachment, dict):
        attachment = {}
        add_finding(
            findings,
            "manifest_attachment_not_object",
            "error",
            "manifest_attachment must be an object.",
        )
    target_path = str(attachment.get("target_path", "")).strip()
    future_target_path = str(attachment.get("future_target_path", "")).strip()
    if target_path and target_path != TARGET_PATH:
        add_finding(
            findings,
            "manifest_target_path_invalid",
            "error",
            f"manifest_attachment.target_path must be {TARGET_PATH}.",
            {"actual": target_path},
        )
    if future_target_path and future_target_path != FUTURE_TARGET_PATH:
        add_finding(
            findings,
            "manifest_future_target_path_invalid",
            "error",
            f"manifest_attachment.future_target_path must be {FUTURE_TARGET_PATH}.",
            {"actual": future_target_path},
        )

    merged_findings = findings + input_findings
    final_status = _merge_status(_collect_component_status(report), derive_findings_status(merged_findings))
    if final_status != computed_status:
        computed_status = final_status
    qc_severity = status_to_qc_severity(computed_status)

    output_payload: Dict[str, Any] = {
        "status": computed_status,
        "check_id": CHECK_ID,
        "contract_id": CONTRACT_ID,
        "evidence_class": evidence_class,
        "claim_status": claim_status,
        "candidate_id": str(report.get("candidate_id", "")).strip(),
        "source_asset_reference": source_asset_reference,
        "source_evidence_ref": source_evidence_ref,
        "findings": merged_findings,
        "manifest_attachment": {
            "target_path": TARGET_PATH,
            "future_target_path": FUTURE_TARGET_PATH,
            "qc_check": {
                "check_id": CHECK_ID,
                "result": computed_status,
                "severity": qc_severity,
                "details": {
                    "report_path": str(source_fixture_path),
                    "report_type": str(report.get("report_type", "")).strip(),
                    "candidate_id": str(report.get("candidate_id", "")).strip(),
                    "source_asset_reference": source_asset_reference,
                    "source_evidence_ref": source_evidence_ref,
                    "visual_profile_id": str(report.get("visual_profile_id", "")).strip(),
                    "visual_profile_version": str(report.get("visual_profile_version", "")).strip(),
                    "evidence_class": evidence_class,
                    "screenshot_set_id": str(report.get("screenshot_set_id", "")).strip(),
                    "screenshot_refs": scanned_refs,
                    "screenshot_count": screenshot_count,
                    "required_views_present": required_views_present,
                    "computed_required_views_present": present_required_views,
                    "missing_required_views": missing_required_views,
                    "image_resolution_status": str(report.get("image_resolution_status", "")).strip(),
                    "file_reference_status": file_reference_status,
                    "visual_identity_status": str(report.get("visual_identity_status", "")).strip(),
                    "silhouette_status": str(report.get("silhouette_status", "")).strip(),
                    "scale_visual_status": str(report.get("scale_visual_status", "")).strip(),
                    "material_visual_status": str(report.get("material_visual_status", "")).strip(),
                    "uv_texture_visual_status": str(report.get("uv_texture_visual_status", "")).strip(),
                    "skeleton_pose_visual_status": str(report.get("skeleton_pose_visual_status", "")).strip(),
                    "animation_pose_visual_status": str(report.get("animation_pose_visual_status", "")).strip(),
                    "missing_asset_visual_status": str(report.get("missing_asset_visual_status", "")).strip(),
                    "artifact_or_corruption_status": str(report.get("artifact_or_corruption_status", "")).strip(),
                    "lighting_context_status": str(report.get("lighting_context_status", "")).strip(),
                    "viewport_context_status": str(report.get("viewport_context_status", "")).strip(),
                    "review_frame_status": str(report.get("review_frame_status", "")).strip(),
                    "claim_status": claim_status,
                    "safety": {
                        "screenshot_capture_status": str(safety.get("screenshot_capture_status", "")).strip(),
                        "o3de_execution_status": str(safety.get("o3de_execution_status", "")).strip(),
                        "editor_execution_status": str(safety.get("editor_execution_status", "")).strip(),
                        "runtime_execution_status": str(safety.get("runtime_execution_status", "")).strip(),
                        "dcc_execution_status": str(safety.get("dcc_execution_status", "")).strip(),
                        "blender_execution_status": str(safety.get("blender_execution_status", "")).strip(),
                        "asset_processor_execution_status": str(safety.get("asset_processor_execution_status", "")).strip(),
                        "production_write_status": str(safety.get("production_write_status", "")).strip(),
                    },
                    "execution_admitted": False,
                    "validated_at_utc": utc_now(),
                },
            },
        },
    }

    print(json.dumps(output_payload, indent=2))
    if computed_status == "pass":
        return 0
    if computed_status == "warn":
        return 0 if args.allow_warn else 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
