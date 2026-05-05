#!/usr/bin/env python3
"""Validate evidence-only release package bundle reports for release-lane integration."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "RELEASE_PACKAGE_BUNDLE_v1_REPORT"
EXPECTED_CONTRACT_ID = "RELEASE_PACKAGE_BUNDLE_v1"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "release_package_bundle_v1"
CONTRACT_ID = "RELEASE_PACKAGE_BUNDLE_v1"


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
        description="Validate MAXINE release package bundle report JSON."
    )
    parser.add_argument("report_path", help="Path to release package bundle report JSON")
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


def _has_forbidden_artifact_token(path_text: str) -> bool:
    lowered = path_text.lower()
    forbidden = (
        "cache/",
        "cache\\",
        "assetdb.sqlite",
        ".fbx",
        ".gltf",
        ".glb",
        ".obj",
        ".blend",
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".exr",
        ".exe",
        ".dll",
        ".bin",
        ".pdb",
        ".sqlite",
        "model_weights",
    )
    return any(token in lowered for token in forbidden)


def _is_string_array(raw: Any) -> bool:
    return isinstance(raw, list) and all(isinstance(x, str) and x.strip() for x in raw)


def _normalize_string_list(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    return sorted(set(str(x).strip() for x in raw if isinstance(x, str) and str(x).strip()))


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    report_path = resolve_path(repo_root, args.report_path)
    schema_path = repo_root / "schemas" / "maxine_release_package_bundle_report.schema.json"

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

    lane = str(report.get("lane", "")).strip()
    for required in ("job_id", "package_id"):
        value = str(report.get(required, "")).strip()
        if not value:
            add_finding(findings, f"{required}_missing", "error", "open", f"{required} is required.")
    if not lane:
        add_finding(findings, "lane_missing", "error", "open", "lane is required.")

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

    bundle_contract = report.get("bundle_contract", {}) if isinstance(report.get("bundle_contract"), dict) else {}
    contract_id = str(bundle_contract.get("contract_id", "")).strip()
    bundle_root = str(bundle_contract.get("bundle_root", "")).strip()
    expected_manifest_path = str(bundle_contract.get("expected_manifest_path", "")).strip()
    expected_artifact_index_path = str(bundle_contract.get("expected_artifact_index_path", "")).strip()
    expected_rollback_plan_path = str(bundle_contract.get("expected_rollback_plan_path", "")).strip()
    expected_cleanup_plan_path = str(bundle_contract.get("expected_cleanup_plan_path", "")).strip()
    if contract_id != EXPECTED_CONTRACT_ID:
        add_finding(
            findings,
            "bundle_contract_id_invalid",
            "error",
            "open",
            f"bundle_contract.contract_id must be {EXPECTED_CONTRACT_ID}.",
            {"actual": contract_id},
        )
    if not bundle_root:
        add_finding(findings, "bundle_root_missing", "error", "open", "bundle_contract.bundle_root is required.")
    if bundle_root and _contains_unsafe_path_tokens(bundle_root):
        add_finding(
            findings,
            "bundle_root_unsafe",
            "error",
            "open",
            "bundle_contract.bundle_root contains unsafe traversal or absolute-path tokens.",
            {"bundle_root": bundle_root},
        )
    if bundle_contract.get("deterministic_layout") is not True:
        add_finding(
            findings,
            "deterministic_layout_required",
            "error",
            "open",
            "bundle_contract.deterministic_layout must be true.",
            {"actual": bundle_contract.get("deterministic_layout")},
        )
    if bundle_contract.get("evidence_only") is not True:
        add_finding(
            findings,
            "evidence_only_required",
            "error",
            "open",
            "bundle_contract.evidence_only must be true.",
            {"actual": bundle_contract.get("evidence_only")},
        )
    if bundle_contract.get("runtime_execution_admitted") is not False:
        add_finding(
            findings,
            "runtime_execution_admitted_must_be_false",
            "error",
            "open",
            "bundle_contract.runtime_execution_admitted must be false.",
            {"actual": bundle_contract.get("runtime_execution_admitted")},
        )

    expected_paths = [
        expected_manifest_path,
        expected_artifact_index_path,
        expected_rollback_plan_path,
        expected_cleanup_plan_path,
    ]
    for field_name, path_value in (
        ("expected_manifest_path", expected_manifest_path),
        ("expected_artifact_index_path", expected_artifact_index_path),
        ("expected_rollback_plan_path", expected_rollback_plan_path),
        ("expected_cleanup_plan_path", expected_cleanup_plan_path),
    ):
        if not path_value:
            add_finding(
                findings,
                f"{field_name}_missing",
                "error",
                "open",
                f"bundle_contract.{field_name} is required.",
            )
        elif _contains_unsafe_path_tokens(path_value):
            add_finding(
                findings,
                f"{field_name}_unsafe",
                "error",
                "open",
                f"bundle_contract.{field_name} contains unsafe traversal or absolute-path tokens.",
                {"path": path_value},
            )
        elif bundle_root and not path_value.startswith(bundle_root):
            add_finding(
                findings,
                f"{field_name}_outside_bundle_root",
                "error",
                "open",
                f"bundle_contract.{field_name} must remain under bundle_contract.bundle_root.",
                {"bundle_root": bundle_root, "path": path_value},
            )

    bundle_inventory = report.get("bundle_inventory", {}) if isinstance(report.get("bundle_inventory"), dict) else {}
    manifest_path = str(bundle_inventory.get("manifest_path", "")).strip()
    artifact_index_path = str(bundle_inventory.get("artifact_index_path", "")).strip()
    rollback_plan_path = str(bundle_inventory.get("rollback_plan_path", "")).strip()
    cleanup_plan_path = str(bundle_inventory.get("cleanup_plan_path", "")).strip()
    included_paths = bundle_inventory.get("included_paths", [])
    missing_paths = bundle_inventory.get("missing_paths", [])
    disallowed_paths = bundle_inventory.get("disallowed_paths", [])

    for field_name, path_value in (
        ("manifest_path", manifest_path),
        ("artifact_index_path", artifact_index_path),
        ("rollback_plan_path", rollback_plan_path),
        ("cleanup_plan_path", cleanup_plan_path),
    ):
        if not path_value:
            add_finding(
                findings,
                f"{field_name}_missing",
                "error",
                "open",
                f"bundle_inventory.{field_name} is required.",
            )
        elif _contains_unsafe_path_tokens(path_value):
            add_finding(
                findings,
                f"{field_name}_unsafe",
                "error",
                "open",
                f"bundle_inventory.{field_name} contains unsafe traversal or absolute-path tokens.",
                {"path": path_value},
            )
        elif bundle_root and not path_value.startswith(bundle_root):
            add_finding(
                findings,
                f"{field_name}_outside_bundle_root",
                "error",
                "open",
                f"bundle_inventory.{field_name} must remain under bundle_contract.bundle_root.",
                {"bundle_root": bundle_root, "path": path_value},
            )

    if not _is_string_array(included_paths):
        add_finding(
            findings,
            "included_paths_invalid",
            "error",
            "open",
            "bundle_inventory.included_paths must be a non-empty string array.",
        )
        included_paths = []
    if not _is_string_array(missing_paths) and missing_paths != []:
        add_finding(
            findings,
            "missing_paths_invalid",
            "error",
            "open",
            "bundle_inventory.missing_paths must be a string array.",
        )
        missing_paths = []
    if not _is_string_array(disallowed_paths) and disallowed_paths != []:
        add_finding(
            findings,
            "disallowed_paths_invalid",
            "error",
            "open",
            "bundle_inventory.disallowed_paths must be a string array.",
        )
        disallowed_paths = []

    included_paths = _normalize_string_list(included_paths)
    missing_paths = _normalize_string_list(missing_paths)
    disallowed_paths = _normalize_string_list(disallowed_paths)
    expected_paths = _normalize_string_list(expected_paths)

    for path_value in included_paths + missing_paths + disallowed_paths:
        if _contains_unsafe_path_tokens(path_value):
            add_finding(
                findings,
                "bundle_path_unsafe",
                "error",
                "open",
                "Bundle inventory path contains unsafe traversal or absolute-path tokens.",
                {"path": path_value},
            )
        if bundle_root and not path_value.startswith(bundle_root):
            add_finding(
                findings,
                "bundle_path_outside_root",
                "error",
                "open",
                "Bundle inventory path must remain under bundle_contract.bundle_root.",
                {"bundle_root": bundle_root, "path": path_value},
            )

    computed_missing_paths = sorted(set(expected_paths) - set(included_paths))
    if computed_missing_paths != missing_paths:
        add_finding(
            findings,
            "missing_paths_mismatch",
            "warning",
            "open",
            "bundle_inventory.missing_paths does not match expected-vs-included computation.",
            {"reported": missing_paths, "computed": computed_missing_paths},
        )
    if computed_missing_paths:
        add_finding(
            findings,
            "required_bundle_paths_missing",
            "error",
            "open",
            "Expected release package bundle paths are missing from included_paths.",
            {"missing_paths": computed_missing_paths},
        )
    if disallowed_paths:
        add_finding(
            findings,
            "disallowed_paths_present",
            "error",
            "open",
            "bundle_inventory.disallowed_paths must be empty.",
            {"disallowed_paths": disallowed_paths},
        )

    for path_value in included_paths + expected_paths:
        if _has_forbidden_artifact_token(path_value):
            add_finding(
                findings,
                "forbidden_bundle_token_present",
                "error",
                "open",
                "Bundle path includes forbidden binary/source/cache/database token.",
                {"path": path_value},
            )

    determinism = report.get("determinism", {}) if isinstance(report.get("determinism"), dict) else {}
    package_id_stable = determinism.get("package_id_stable")
    input_provenance_recorded = determinism.get("input_provenance_recorded")
    source_product_tracking_recorded = determinism.get("source_product_tracking_recorded")
    product_resolution_mode = str(determinism.get("product_resolution_mode", "")).strip()
    checksum_index_present = determinism.get("checksum_index_present")

    if package_id_stable is not True:
        add_finding(
            findings,
            "package_id_not_stable",
            "error",
            "open",
            "determinism.package_id_stable must be true for release package bundle readiness.",
            {"actual": package_id_stable},
        )
    if input_provenance_recorded is not True:
        add_finding(
            findings,
            "input_provenance_not_recorded",
            "error",
            "open",
            "determinism.input_provenance_recorded must be true.",
            {"actual": input_provenance_recorded},
        )
    if source_product_tracking_recorded is not True:
        add_finding(
            findings,
            "source_product_tracking_not_recorded",
            "error",
            "open",
            "determinism.source_product_tracking_recorded must be true.",
            {"actual": source_product_tracking_recorded},
        )
    if checksum_index_present is not True:
        add_finding(
            findings,
            "checksum_index_missing",
            "error",
            "open",
            "determinism.checksum_index_present must be true.",
            {"actual": checksum_index_present},
        )
    if product_resolution_mode not in {"deterministic", "proposal_only"}:
        add_finding(
            findings,
            "product_resolution_mode_invalid",
            "error",
            "open",
            "determinism.product_resolution_mode must be deterministic|proposal_only.",
            {"actual": product_resolution_mode},
        )
    elif product_resolution_mode == "proposal_only":
        add_finding(
            findings,
            "resolution_mode_proposal_only",
            "warning",
            "open",
            "determinism.product_resolution_mode is proposal_only; deterministic mode is preferred for release package readiness.",
        )

    rollback = report.get("rollback", {}) if isinstance(report.get("rollback"), dict) else {}
    undo_available = rollback.get("undo_available")
    rollback_step_count = rollback.get("rollback_step_count")
    rollback_instruction_paths = rollback.get("rollback_instruction_paths", [])
    cleanup_step_count = rollback.get("cleanup_step_count")
    cleanup_instruction_paths = rollback.get("cleanup_instruction_paths", [])
    destructive_cleanup_admitted = rollback.get("destructive_cleanup_admitted")

    if destructive_cleanup_admitted is not False:
        add_finding(
            findings,
            "destructive_cleanup_admitted_must_be_false",
            "error",
            "open",
            "rollback.destructive_cleanup_admitted must be false.",
            {"actual": destructive_cleanup_admitted},
        )
    if not isinstance(undo_available, bool):
        add_finding(
            findings,
            "undo_available_invalid",
            "error",
            "open",
            "rollback.undo_available must be boolean.",
            {"actual": undo_available},
        )
        undo_available = False
    if not isinstance(rollback_step_count, int) or rollback_step_count < 0:
        add_finding(
            findings,
            "rollback_step_count_invalid",
            "error",
            "open",
            "rollback.rollback_step_count must be integer >= 0.",
            {"actual": rollback_step_count},
        )
        rollback_step_count = 0
    if not isinstance(cleanup_step_count, int) or cleanup_step_count < 0:
        add_finding(
            findings,
            "cleanup_step_count_invalid",
            "error",
            "open",
            "rollback.cleanup_step_count must be integer >= 0.",
            {"actual": cleanup_step_count},
        )
        cleanup_step_count = 0
    if not _is_string_array(rollback_instruction_paths) and rollback_instruction_paths != []:
        add_finding(
            findings,
            "rollback_instruction_paths_invalid",
            "error",
            "open",
            "rollback.rollback_instruction_paths must be a string array.",
        )
        rollback_instruction_paths = []
    if not _is_string_array(cleanup_instruction_paths) and cleanup_instruction_paths != []:
        add_finding(
            findings,
            "cleanup_instruction_paths_invalid",
            "error",
            "open",
            "rollback.cleanup_instruction_paths must be a string array.",
        )
        cleanup_instruction_paths = []

    rollback_instruction_paths = _normalize_string_list(rollback_instruction_paths)
    cleanup_instruction_paths = _normalize_string_list(cleanup_instruction_paths)

    for path_value in rollback_instruction_paths + cleanup_instruction_paths:
        if _contains_unsafe_path_tokens(path_value):
            add_finding(
                findings,
                "rollback_cleanup_path_unsafe",
                "error",
                "open",
                "Rollback/cleanup instruction path contains unsafe traversal or absolute-path tokens.",
                {"path": path_value},
            )
        if bundle_root and not path_value.startswith(bundle_root):
            add_finding(
                findings,
                "rollback_cleanup_path_outside_root",
                "error",
                "open",
                "Rollback/cleanup instruction path must remain under bundle_contract.bundle_root.",
                {"bundle_root": bundle_root, "path": path_value},
            )

    if undo_available is not True:
        add_finding(
            findings,
            "undo_not_available",
            "error",
            "open",
            "rollback.undo_available must be true for release package bundle readiness.",
            {"actual": undo_available},
        )
    if rollback_step_count < 1:
        add_finding(
            findings,
            "rollback_steps_missing",
            "error",
            "open",
            "rollback.rollback_step_count must be >= 1.",
            {"actual": rollback_step_count},
        )
    if cleanup_step_count < 1:
        add_finding(
            findings,
            "cleanup_steps_missing",
            "error",
            "open",
            "rollback.cleanup_step_count must be >= 1.",
            {"actual": cleanup_step_count},
        )
    if not rollback_instruction_paths:
        add_finding(
            findings,
            "rollback_instructions_missing",
            "error",
            "open",
            "rollback.rollback_instruction_paths must not be empty.",
        )
    if not cleanup_instruction_paths:
        add_finding(
            findings,
            "cleanup_instructions_missing",
            "error",
            "open",
            "rollback.cleanup_instruction_paths must not be empty.",
        )

    release_readiness = report.get("release_readiness", {}) if isinstance(report.get("release_readiness"), dict) else {}
    readiness_state = str(release_readiness.get("readiness_state", "")).strip()
    manual_review_required = release_readiness.get("manual_review_required")
    if readiness_state not in {
        "ready_for_manual_release_review",
        "blocked_missing_evidence",
        "blocked_safety_boundary",
    }:
        add_finding(
            findings,
            "readiness_state_invalid",
            "error",
            "open",
            "release_readiness.readiness_state is invalid.",
            {"actual": readiness_state},
        )
    if not isinstance(manual_review_required, bool):
        add_finding(
            findings,
            "manual_review_required_invalid",
            "error",
            "open",
            "release_readiness.manual_review_required must be boolean.",
            {"actual": manual_review_required},
        )
    elif lane == "release_character" and manual_review_required is not True:
        add_finding(
            findings,
            "manual_review_required_for_release",
            "error",
            "open",
            "release_character lane must require manual review.",
        )
    if readiness_state == "ready_for_manual_release_review" and computed_missing_paths:
        add_finding(
            findings,
            "ready_state_with_missing_bundle_paths",
            "error",
            "open",
            "ready_for_manual_release_review cannot be set while required bundle paths are missing.",
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
