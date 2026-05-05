#!/usr/bin/env python3
"""Validate evidence-only material/UV QC reports for release-lane integration."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
SEVERITY_FROM_RULE = {"warning", "error", "manual_review"}
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "MATERIAL_UV_QC_v1_REPORT"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "material_uv_qc_v1"
CONTRACT_ID = "MATERIAL_UV_QC_v1"


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
        description="Validate MAXINE material/UV QC report JSON."
    )
    parser.add_argument("report_path", help="Path to Material/UV QC report JSON")
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


def _severity_or_default(raw: Any, default: str = "warning") -> str:
    value = str(raw or "").strip()
    if value in SEVERITY_FROM_RULE:
        return value
    return default


def _contains_unsafe_path_tokens(path_text: str) -> bool:
    blocked = ("..", "|", ";", ">", "<", "&", "`")
    lowered = path_text.lower()
    return any(token in lowered for token in blocked)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    report_path = resolve_path(repo_root, args.report_path)
    schema_path = repo_root / "schemas" / "maxine_material_uv_qc_report.schema.json"

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

    target = report.get("target", {}) if isinstance(report.get("target"), dict) else {}
    package_tier = str(target.get("package_tier", "")).strip()
    material_profile = str(target.get("material_profile", "")).strip()
    if not package_tier:
        add_finding(findings, "package_tier_missing", "error", "open", "target.package_tier is required.")
    if not material_profile:
        add_finding(findings, "material_profile_missing", "error", "open", "target.material_profile is required.")

    material = report.get("material_summary", {}) if isinstance(report.get("material_summary"), dict) else {}
    slot_count_raw = material.get("material_slot_count")
    slot_budget_raw = material.get("material_slot_budget")
    slot_sev = _severity_or_default(material.get("slot_budget_exceeded_severity"), "warning")
    missing_materials = material.get("missing_materials", [])
    unsupported_materials = material.get("unsupported_materials", [])
    texture_refs = material.get("texture_references", [])
    missing_textures = material.get("missing_textures", [])

    if not isinstance(slot_count_raw, int) or slot_count_raw < 0:
        add_finding(findings, "material_slot_count_invalid", "error", "open", "material_slot_count must be >= 0 integer.")
        slot_count_raw = 0
    if not isinstance(slot_budget_raw, int) or slot_budget_raw < 0:
        add_finding(findings, "material_slot_budget_invalid", "error", "open", "material_slot_budget must be >= 0 integer.")
        slot_budget_raw = 0
    if slot_count_raw > slot_budget_raw:
        add_finding(
            findings,
            "material_slot_budget_exceeded",
            slot_sev,
            "open",
            "Material slot count exceeds configured budget.",
            {"material_slot_count": slot_count_raw, "material_slot_budget": slot_budget_raw},
        )

    if not isinstance(missing_materials, list):
        add_finding(findings, "missing_materials_invalid", "error", "open", "missing_materials must be an array.")
        missing_materials = []
    if missing_materials:
        add_finding(
            findings,
            "missing_required_materials",
            "error",
            "open",
            "Required materials are missing.",
            {"missing_materials": missing_materials},
        )

    if not isinstance(unsupported_materials, list):
        add_finding(findings, "unsupported_materials_invalid", "error", "open", "unsupported_materials must be an array.")
        unsupported_materials = []
    if unsupported_materials:
        add_finding(
            findings,
            "unsupported_materials_detected",
            "warning",
            "open",
            "Unsupported materials were reported.",
            {"unsupported_materials": unsupported_materials},
        )

    if not isinstance(texture_refs, list):
        add_finding(findings, "texture_references_invalid", "error", "open", "texture_references must be an array.")
        texture_refs = []
    for idx, ref in enumerate(texture_refs):
        if not isinstance(ref, dict):
            add_finding(
                findings,
                "texture_reference_invalid",
                "error",
                "open",
                f"texture_references[{idx}] must be an object.",
            )
            continue
        texture_path = str(ref.get("texture_path", "")).strip()
        if not texture_path:
            add_finding(
                findings,
                "texture_reference_path_missing",
                "error",
                "open",
                f"texture_references[{idx}].texture_path is required.",
            )
            continue
        if _contains_unsafe_path_tokens(texture_path):
            add_finding(
                findings,
                "texture_reference_path_unsafe",
                "error",
                "open",
                "texture_path contains unsafe traversal or shell tokens.",
                {"texture_path": texture_path},
            )

    if not isinstance(missing_textures, list):
        add_finding(findings, "missing_textures_invalid", "error", "open", "missing_textures must be an array.")
        missing_textures = []
    if missing_textures:
        add_finding(
            findings,
            "missing_required_textures",
            "error",
            "open",
            "Required textures are missing.",
            {"missing_textures": missing_textures},
        )

    uv = report.get("uv_summary", {}) if isinstance(report.get("uv_summary"), dict) else {}
    required_uv_sets = uv.get("required_uv_sets", [])
    present_uv_sets = uv.get("present_uv_sets", [])
    reported_missing_uv_sets = uv.get("missing_uv_sets", [])
    overlap_status = str(uv.get("overlapping_uvs_status", "")).strip()
    out_of_bounds_status = str(uv.get("out_of_bounds_uvs_status", "")).strip()

    if not isinstance(required_uv_sets, list) or not all(isinstance(x, str) and x.strip() for x in required_uv_sets):
        add_finding(findings, "required_uv_sets_invalid", "error", "open", "required_uv_sets must be a string array.")
        required_uv_sets = []
    if not isinstance(present_uv_sets, list) or not all(isinstance(x, str) and x.strip() for x in present_uv_sets):
        add_finding(findings, "present_uv_sets_invalid", "error", "open", "present_uv_sets must be a string array.")
        present_uv_sets = []
    if not isinstance(reported_missing_uv_sets, list) or not all(isinstance(x, str) and x.strip() for x in reported_missing_uv_sets):
        add_finding(findings, "missing_uv_sets_invalid", "error", "open", "missing_uv_sets must be a string array.")
        reported_missing_uv_sets = []

    missing_from_calc = sorted(set(required_uv_sets) - set(present_uv_sets))
    if missing_from_calc:
        add_finding(
            findings,
            "missing_required_uv_sets",
            "error",
            "open",
            "Required UV sets are missing.",
            {"required_uv_sets": required_uv_sets, "present_uv_sets": present_uv_sets, "missing_uv_sets": missing_from_calc},
        )
    if sorted(set(reported_missing_uv_sets)) != missing_from_calc:
        add_finding(
            findings,
            "missing_uv_sets_mismatch",
            "warning",
            "open",
            "reported missing_uv_sets does not match computed missing sets.",
            {"reported": reported_missing_uv_sets, "computed": missing_from_calc},
        )

    if overlap_status == "major":
        add_finding(
            findings,
            "overlapping_uvs_major",
            "warning",
            "open",
            "Major overlapping UVs reported.",
        )
    if out_of_bounds_status == "major":
        add_finding(
            findings,
            "out_of_bounds_uvs_major",
            "warning",
            "open",
            "Major out-of-bounds UVs reported.",
        )

    texture_budget = report.get("texture_budget", {}) if isinstance(report.get("texture_budget"), dict) else {}
    max_res = texture_budget.get("max_texture_resolution")
    oversized = texture_budget.get("oversized_textures", [])
    oversized_sev = _severity_or_default(texture_budget.get("oversized_textures_severity"), "warning")
    texture_count = texture_budget.get("texture_count")

    if not isinstance(max_res, int) or max_res < 1:
        add_finding(findings, "max_texture_resolution_invalid", "error", "open", "max_texture_resolution must be integer >= 1.")
        max_res = 1
    if not isinstance(texture_count, int) or texture_count < 0:
        add_finding(findings, "texture_count_invalid", "error", "open", "texture_count must be integer >= 0.")

    if not isinstance(oversized, list):
        add_finding(findings, "oversized_textures_invalid", "error", "open", "oversized_textures must be an array.")
        oversized = []

    for idx, item in enumerate(oversized):
        if not isinstance(item, dict):
            add_finding(findings, "oversized_texture_item_invalid", "error", "open", f"oversized_textures[{idx}] must be an object.")
            continue
        texture_path = str(item.get("texture_path", "")).strip()
        actual_res = item.get("actual_resolution")
        if not texture_path:
            add_finding(findings, "oversized_texture_path_missing", "error", "open", f"oversized_textures[{idx}].texture_path is required.")
            continue
        if _contains_unsafe_path_tokens(texture_path):
            add_finding(findings, "oversized_texture_path_unsafe", "error", "open", "oversized texture path contains unsafe tokens.")
        if not isinstance(actual_res, int) or actual_res < 1:
            add_finding(findings, "oversized_texture_resolution_invalid", "error", "open", f"oversized_textures[{idx}].actual_resolution must be integer >= 1.")
            continue
        if actual_res <= max_res:
            add_finding(
                findings,
                "oversized_texture_not_over_limit",
                "warning",
                "open",
                "oversized_textures entry does not exceed max_texture_resolution.",
                {"texture_path": texture_path, "actual_resolution": actual_res, "max_texture_resolution": max_res},
            )

    if oversized:
        add_finding(
            findings,
            "oversized_textures_detected",
            oversized_sev,
            "open",
            "One or more textures exceed max_texture_resolution.",
            {"count": len(oversized), "max_texture_resolution": max_res},
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
