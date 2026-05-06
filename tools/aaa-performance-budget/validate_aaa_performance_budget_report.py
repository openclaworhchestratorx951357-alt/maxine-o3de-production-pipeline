#!/usr/bin/env python3
"""Validate evidence-only AAA performance budget reports for release-lane integration."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
ALLOWED_EVIDENCE_CLASS = {"fixture", "imported", "controlled_real"}
ALLOWED_ASSET_TIER = {"hero", "npc", "prop", "environment"}
ALLOWED_CLAIM_STATUS = {"evidence_only", "not_authoritative"}
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "AAA_PERFORMANCE_BUDGET_v1_REPORT"
EXPECTED_PROFILE_ID = "AAA_PERFORMANCE_BUDGET_v1"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "aaa_performance_budget_v1"
CONTRACT_ID = "AAA_PERFORMANCE_BUDGET_v1"

STATUS_FIELDS = [
    "triangle_budget_status",
    "material_slot_budget_status",
    "texture_budget_status",
    "uv_budget_status",
    "bone_budget_status",
    "skin_influence_budget_status",
    "lod_budget_status",
    "animation_budget_status",
    "package_size_budget_status",
    "runtime_load_readiness_status",
    "review_tier_status",
]
OPTIONAL_STATUS_FIELDS = ["import_time_estimate_status"]

TIER_BUDGETS: Dict[str, Dict[str, int]] = {
    "hero": {
        "triangle_warn": 120000,
        "triangle_fail": 180000,
        "material_slot_warn": 6,
        "material_slot_fail": 8,
        "texture_resolution_warn": 4096,
        "texture_resolution_fail": 8192,
        "bone_warn": 160,
        "bone_fail": 220,
        "skin_influence_warn": 4,
        "skin_influence_fail": 8,
        "lod_min_warn": 4,
    },
    "npc": {
        "triangle_warn": 60000,
        "triangle_fail": 100000,
        "material_slot_warn": 4,
        "material_slot_fail": 6,
        "texture_resolution_warn": 2048,
        "texture_resolution_fail": 4096,
        "bone_warn": 120,
        "bone_fail": 180,
        "skin_influence_warn": 4,
        "skin_influence_fail": 8,
        "lod_min_warn": 3,
    },
    "prop": {
        "triangle_warn": 30000,
        "triangle_fail": 50000,
        "material_slot_warn": 3,
        "material_slot_fail": 5,
        "texture_resolution_warn": 2048,
        "texture_resolution_fail": 4096,
        "bone_warn": 64,
        "bone_fail": 96,
        "skin_influence_warn": 4,
        "skin_influence_fail": 8,
        "lod_min_warn": 2,
    },
    "environment": {
        "triangle_warn": 180000,
        "triangle_fail": 280000,
        "material_slot_warn": 8,
        "material_slot_fail": 12,
        "texture_resolution_warn": 4096,
        "texture_resolution_fail": 8192,
        "bone_warn": 0,
        "bone_fail": 0,
        "skin_influence_warn": 0,
        "skin_influence_fail": 0,
        "lod_min_warn": 3,
    },
}


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
        description="Validate MAXINE AAA performance budget report JSON."
    )
    parser.add_argument("report_path", help="Path to AAA performance budget report JSON")
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


def _status_severity(status: str) -> str:
    if status == "fail":
        return "error"
    if status == "pending_manual":
        return "manual_review"
    if status == "warn":
        return "warning"
    return "info"


def _collect_component_status(report: Dict[str, Any]) -> str:
    seen: List[str] = []
    for field in STATUS_FIELDS + OPTIONAL_STATUS_FIELDS:
        raw = report.get(field)
        if raw is None and field in OPTIONAL_STATUS_FIELDS:
            continue
        value = str(raw or "").strip()
        if value in ALLOWED_STATUS:
            seen.append(value)
    if "fail" in seen:
        return "fail"
    if "pending_manual" in seen:
        return "pending_manual"
    if "warn" in seen:
        return "warn"
    return "pass"


def _collect_findings_status(findings: List[Dict[str, Any]]) -> str:
    severities = {str(item.get("severity", "")).strip() for item in findings}
    if "error" in severities:
        return "fail"
    if "manual_review" in severities:
        return "pending_manual"
    if "warning" in severities:
        return "warn"
    return "pass"


def _merge_status(a: str, b: str) -> str:
    order = ["pass", "warn", "pending_manual", "fail"]
    return max(a, b, key=lambda value: order.index(value))


def _contains_unsafe_path_tokens(path_text: str) -> bool:
    blocked = ("..", "|", ";", ">", "<", "&", "`", "\\\\", ":\\")
    lowered = path_text.lower()
    return any(token in lowered for token in blocked)


def _validate_finding_array(raw_findings: Any, findings: List[Dict[str, Any]], field_name: str) -> List[Dict[str, Any]]:
    parsed: List[Dict[str, Any]] = []
    if not isinstance(raw_findings, list):
        add_finding(findings, f"{field_name}_not_array", "error", "open", f"{field_name} must be an array.")
        return parsed

    for idx, item in enumerate(raw_findings):
        if not isinstance(item, dict):
            add_finding(findings, f"{field_name}_item_invalid", "error", "open", f"{field_name}[{idx}] must be an object.")
            continue
        fid = str(item.get("id", "")).strip()
        sev = str(item.get("severity", "")).strip()
        fstatus = str(item.get("status", "")).strip()
        msg = str(item.get("message", "")).strip()
        if not fid:
            add_finding(findings, f"{field_name}_id_missing", "error", "open", f"{field_name}[{idx}].id is required.")
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
            add_finding(findings, f"{field_name}_status_missing", "error", "open", f"{field_name}[{idx}].status is required.")
        if not msg:
            add_finding(findings, f"{field_name}_message_missing", "error", "open", f"{field_name}[{idx}].message is required.")
        parsed.append(item)
    return parsed


def _require_int(report: Dict[str, Any], field: str, findings: List[Dict[str, Any]], minimum: int = 0) -> int:
    value = report.get(field)
    if not isinstance(value, int) or value < minimum:
        add_finding(
            findings,
            f"{field}_invalid",
            "error",
            "open",
            f"{field} must be an integer >= {minimum}.",
            {"actual": value},
        )
        return minimum
    return value


def _require_number(report: Dict[str, Any], field: str, findings: List[Dict[str, Any]], minimum: float = 0.0) -> float:
    value = report.get(field)
    if not isinstance(value, (int, float)) or value < minimum:
        add_finding(
            findings,
            f"{field}_invalid",
            "error",
            "open",
            f"{field} must be a number >= {minimum}.",
            {"actual": value},
        )
        return minimum
    return float(value)


def _evaluate_upper_budget(
    *,
    metric_id: str,
    metric_label: str,
    value: float,
    warn_threshold: float,
    fail_threshold: float,
    waiver_status: str,
    waiver_ids: List[str],
    waiver_reasons: List[str],
    findings: List[Dict[str, Any]],
) -> None:
    if value <= warn_threshold:
        return

    if value > fail_threshold:
        details = {
            "value": value,
            "warn_threshold": warn_threshold,
            "fail_threshold": fail_threshold,
        }
        if waiver_status == "waived" and waiver_ids and waiver_reasons:
            details["waiver_ids"] = waiver_ids
            details["waiver_reasons"] = waiver_reasons
            add_finding(
                findings,
                f"{metric_id}_fail_threshold_waived",
                "warning",
                "open",
                f"{metric_label} exceeds fail threshold but is explicitly waived.",
                details,
            )
        else:
            add_finding(
                findings,
                f"{metric_id}_fail_threshold_exceeded",
                "error",
                "open",
                f"{metric_label} exceeds fail threshold.",
                details,
            )
        return

    add_finding(
        findings,
        f"{metric_id}_warn_threshold_exceeded",
        "warning",
        "open",
        f"{metric_label} exceeds warn threshold.",
        {
            "value": value,
            "warn_threshold": warn_threshold,
            "fail_threshold": fail_threshold,
        },
    )


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    report_path = resolve_path(repo_root, args.report_path)
    schema_path = repo_root / "schemas" / "maxine_aaa_performance_budget_report.schema.json"

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
        "performance_profile_id",
        "performance_profile_version",
    ):
        value = str(report.get(required, "")).strip()
        if not value:
            add_finding(findings, f"{required}_missing", "error", "open", f"{required} is required.")

    performance_profile_id = str(report.get("performance_profile_id", "")).strip()
    if performance_profile_id and performance_profile_id != EXPECTED_PROFILE_ID:
        add_finding(
            findings,
            "performance_profile_id_invalid",
            "error",
            "open",
            f"performance_profile_id must be {EXPECTED_PROFILE_ID}.",
            {"actual": performance_profile_id},
        )

    asset_tier = str(report.get("asset_tier", "")).strip()
    if asset_tier not in ALLOWED_ASSET_TIER:
        add_finding(
            findings,
            "asset_tier_invalid",
            "error",
            "open",
            "asset_tier must be hero|npc|prop|environment.",
            {"actual": asset_tier},
        )
        asset_tier = "hero"

    source_evidence_ref = str(report.get("source_evidence_ref", "")).strip()
    if source_evidence_ref and _contains_unsafe_path_tokens(source_evidence_ref):
        add_finding(
            findings,
            "source_evidence_ref_unsafe",
            "error",
            "open",
            "source_evidence_ref contains unsafe traversal or absolute-path tokens.",
            {"source_evidence_ref": source_evidence_ref},
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

    waiver_status = str(report.get("waiver_status", "")).strip()
    waiver_ids_raw = report.get("waiver_ids", [])
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

    if not isinstance(waiver_ids_raw, list):
        add_finding(findings, "waiver_ids_invalid", "error", "open", "waiver_ids must be a string array.")
        waiver_ids_raw = []
    if not isinstance(waiver_reasons_raw, list):
        add_finding(findings, "waiver_reasons_invalid", "error", "open", "waiver_reasons must be a string array.")
        waiver_reasons_raw = []

    waiver_ids = [str(x).strip() for x in waiver_ids_raw if isinstance(x, str) and str(x).strip()]
    waiver_reasons = [str(x).strip() for x in waiver_reasons_raw if isinstance(x, str) and str(x).strip()]

    if waiver_status == "waived":
        if not waiver_ids:
            add_finding(findings, "waiver_ids_required", "error", "open", "waiver_ids must be provided when waiver_status=waived.")
        if not waiver_reasons:
            add_finding(findings, "waiver_reasons_required", "error", "open", "waiver_reasons must be provided when waiver_status=waived.")
    elif waiver_ids or waiver_reasons:
        add_finding(
            findings,
            "waiver_details_present_without_waiver",
            "warning",
            "open",
            "waiver_ids/waiver_reasons are present while waiver_status=none.",
        )

    safety = report.get("safety", {})
    if not isinstance(safety, dict):
        safety = {}
        add_finding(findings, "safety_not_object", "error", "open", "safety must be an object.")
    for safety_field in (
        "o3de_execution_status",
        "editor_execution_status",
        "runtime_execution_status",
        "asset_processor_execution_status",
        "dcc_execution_status",
        "blender_execution_status",
        "benchmark_execution_status",
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
    for field_name in OPTIONAL_STATUS_FIELDS:
        if field_name not in report:
            continue
        value = str(report.get(field_name, "")).strip()
        if value not in ALLOWED_STATUS:
            add_finding(
                findings,
                f"{field_name}_invalid",
                "error",
                "open",
                f"{field_name} must be pass|warn|fail|pending_manual when provided.",
                {"actual": value},
            )

    triangle_count = _require_int(report, "triangle_count", findings, 0)
    material_slot_count = _require_int(report, "material_slot_count", findings, 0)
    texture_count = _require_int(report, "texture_count", findings, 0)
    texture_resolution_max = _require_int(report, "texture_resolution_max", findings, 1)
    texture_memory_estimate_mb = _require_number(report, "texture_memory_estimate_mb", findings, 0.0)
    uv_set_count = _require_int(report, "uv_set_count", findings, 0)
    bone_count = _require_int(report, "bone_count", findings, 0)
    skin_influence_max = _require_int(report, "skin_influence_max", findings, 0)
    lod_count = _require_int(report, "lod_count", findings, 0)
    animation_clip_count = _require_int(report, "animation_clip_count", findings, 0)
    package_size_estimate_mb = _require_number(report, "package_size_estimate_mb", findings, 0.0)

    if animation_clip_count < 1:
        add_finding(
            findings,
            "animation_clip_count_missing_required",
            "error",
            "open",
            "At least one animation clip must be represented for release candidates.",
            {"animation_clip_count": animation_clip_count},
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

    thresholds = TIER_BUDGETS.get(asset_tier, TIER_BUDGETS["hero"])
    _evaluate_upper_budget(
        metric_id="triangle_count",
        metric_label="Triangle count",
        value=float(triangle_count),
        warn_threshold=float(thresholds["triangle_warn"]),
        fail_threshold=float(thresholds["triangle_fail"]),
        waiver_status=waiver_status,
        waiver_ids=waiver_ids,
        waiver_reasons=waiver_reasons,
        findings=findings,
    )
    _evaluate_upper_budget(
        metric_id="material_slot_count",
        metric_label="Material slot count",
        value=float(material_slot_count),
        warn_threshold=float(thresholds["material_slot_warn"]),
        fail_threshold=float(thresholds["material_slot_fail"]),
        waiver_status=waiver_status,
        waiver_ids=waiver_ids,
        waiver_reasons=waiver_reasons,
        findings=findings,
    )
    _evaluate_upper_budget(
        metric_id="texture_resolution_max",
        metric_label="Max texture resolution",
        value=float(texture_resolution_max),
        warn_threshold=float(thresholds["texture_resolution_warn"]),
        fail_threshold=float(thresholds["texture_resolution_fail"]),
        waiver_status=waiver_status,
        waiver_ids=waiver_ids,
        waiver_reasons=waiver_reasons,
        findings=findings,
    )

    if asset_tier != "environment":
        _evaluate_upper_budget(
            metric_id="bone_count",
            metric_label="Bone count",
            value=float(bone_count),
            warn_threshold=float(thresholds["bone_warn"]),
            fail_threshold=float(thresholds["bone_fail"]),
            waiver_status=waiver_status,
            waiver_ids=waiver_ids,
            waiver_reasons=waiver_reasons,
            findings=findings,
        )
        _evaluate_upper_budget(
            metric_id="skin_influence_max",
            metric_label="Skin influence max",
            value=float(skin_influence_max),
            warn_threshold=float(thresholds["skin_influence_warn"]),
            fail_threshold=float(thresholds["skin_influence_fail"]),
            waiver_status=waiver_status,
            waiver_ids=waiver_ids,
            waiver_reasons=waiver_reasons,
            findings=findings,
        )

    lod_min_warn = int(thresholds["lod_min_warn"])
    if lod_count < lod_min_warn:
        add_finding(
            findings,
            "lod_count_below_recommended",
            "warning",
            "open",
            "LOD count is below recommended threshold for asset tier.",
            {"lod_count": lod_count, "recommended_min": lod_min_warn, "asset_tier": asset_tier},
        )

    if uv_set_count < 1:
        add_finding(
            findings,
            "uv_set_count_missing_uv0",
            "error",
            "open",
            "UV0 must exist for performance-ready evaluation.",
            {"uv_set_count": uv_set_count},
        )

    budget_thresholds = report.get("budget_thresholds", {})
    if not isinstance(budget_thresholds, dict):
        add_finding(findings, "budget_thresholds_invalid", "error", "open", "budget_thresholds must be an object when provided.")
        budget_thresholds = {}

    package_warn = budget_thresholds.get("package_size_warn_mb")
    package_fail = budget_thresholds.get("package_size_fail_mb")
    if isinstance(package_warn, (int, float)) and isinstance(package_fail, (int, float)) and package_warn <= package_fail:
        _evaluate_upper_budget(
            metric_id="package_size_estimate_mb",
            metric_label="Package size estimate (MB)",
            value=package_size_estimate_mb,
            warn_threshold=float(package_warn),
            fail_threshold=float(package_fail),
            waiver_status=waiver_status,
            waiver_ids=waiver_ids,
            waiver_reasons=waiver_reasons,
            findings=findings,
        )

    memory_warn = budget_thresholds.get("texture_memory_warn_mb")
    memory_fail = budget_thresholds.get("texture_memory_fail_mb")
    if isinstance(memory_warn, (int, float)) and isinstance(memory_fail, (int, float)) and memory_warn <= memory_fail:
        _evaluate_upper_budget(
            metric_id="texture_memory_estimate_mb",
            metric_label="Texture memory estimate (MB)",
            value=texture_memory_estimate_mb,
            warn_threshold=float(memory_warn),
            fail_threshold=float(memory_fail),
            waiver_status=waiver_status,
            waiver_ids=waiver_ids,
            waiver_reasons=waiver_reasons,
            findings=findings,
        )

    report_findings = _validate_finding_array(report.get("findings", []), findings, "findings")

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
    findings_status = _collect_findings_status(findings + report_findings)
    computed_status = _merge_status(component_status, findings_status)

    if declared_status in ALLOWED_STATUS and declared_status != computed_status:
        add_finding(
            findings,
            "status_mismatch",
            "error",
            "open",
            "report.status does not match computed status.",
            {"declared": declared_status, "computed": computed_status},
        )
        computed_status = "fail"

    qc_severity = _status_severity(computed_status)
    output_payload: Dict[str, Any] = {
        "status": computed_status,
        "check_id": CHECK_ID,
        "contract_id": CONTRACT_ID,
        "evidence_class": evidence_class,
        "claim_status": claim_status,
        "candidate_id": str(report.get("candidate_id", "")).strip(),
        "source_asset_reference": str(report.get("source_asset_reference", "")).strip(),
        "source_evidence_ref": source_evidence_ref,
        "asset_tier": asset_tier,
        "findings": findings + report_findings,
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
                    "evidence_class": evidence_class,
                    "claim_status": claim_status,
                    "asset_tier": asset_tier,
                    "triangle_count": triangle_count,
                    "material_slot_count": material_slot_count,
                    "texture_count": texture_count,
                    "texture_resolution_max": texture_resolution_max,
                    "texture_memory_estimate_mb": texture_memory_estimate_mb,
                    "uv_set_count": uv_set_count,
                    "bone_count": bone_count,
                    "skin_influence_max": skin_influence_max,
                    "lod_count": lod_count,
                    "animation_clip_count": animation_clip_count,
                    "package_size_estimate_mb": package_size_estimate_mb,
                    "waiver_status": waiver_status,
                    "waiver_ids": waiver_ids,
                    "waiver_reasons": waiver_reasons,
                    "safety": {
                        "o3de_execution_status": str(safety.get("o3de_execution_status", "")).strip(),
                        "editor_execution_status": str(safety.get("editor_execution_status", "")).strip(),
                        "runtime_execution_status": str(safety.get("runtime_execution_status", "")).strip(),
                        "asset_processor_execution_status": str(safety.get("asset_processor_execution_status", "")).strip(),
                        "dcc_execution_status": str(safety.get("dcc_execution_status", "")).strip(),
                        "blender_execution_status": str(safety.get("blender_execution_status", "")).strip(),
                        "benchmark_execution_status": str(safety.get("benchmark_execution_status", "")).strip(),
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
