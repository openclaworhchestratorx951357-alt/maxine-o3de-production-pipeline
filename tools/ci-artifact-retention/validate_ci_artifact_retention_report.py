#!/usr/bin/env python3
"""Validate evidence-only CI artifact retention reports for release-lane integration."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "CI_ARTIFACT_RETENTION_v1_REPORT"
EXPECTED_POLICY_ID = "CI_ARTIFACT_RETENTION_v1"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "ci_artifact_retention_v1"
CONTRACT_ID = "CI_ARTIFACT_RETENTION_v1"


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
        description="Validate MAXINE CI artifact retention report JSON."
    )
    parser.add_argument("report_path", help="Path to CI artifact retention report JSON")
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


def _is_string_array(raw: Any) -> bool:
    return isinstance(raw, list) and all(isinstance(x, str) and x.strip() for x in raw)


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
        ".exe",
        ".dll",
        ".bin",
        ".pdb",
        ".sqlite",
        "model_weights",
    )
    return any(token in lowered for token in forbidden)


def _normalize_string_list(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    return sorted(set(str(x).strip() for x in raw if isinstance(x, str) and str(x).strip()))


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    report_path = resolve_path(repo_root, args.report_path)
    schema_path = repo_root / "schemas" / "maxine_ci_artifact_retention_report.schema.json"

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

    retention = report.get("retention_policy", {}) if isinstance(report.get("retention_policy"), dict) else {}
    policy_id = str(retention.get("policy_id", "")).strip()
    retention_class = str(retention.get("retention_class", "")).strip()
    min_required_days = retention.get("min_required_days")
    recommended_days = retention.get("recommended_days")
    actual_retention_days = retention.get("actual_retention_days")
    if policy_id != EXPECTED_POLICY_ID:
        add_finding(
            findings,
            "policy_id_invalid",
            "error",
            "open",
            f"retention_policy.policy_id must be {EXPECTED_POLICY_ID}.",
            {"actual": policy_id},
        )
    if retention_class not in {"draft-7d", "release-365d", "manual", "unknown"}:
        add_finding(
            findings,
            "retention_class_invalid",
            "error",
            "open",
            "retention_policy.retention_class must be draft-7d|release-365d|manual|unknown.",
            {"actual": retention_class},
        )
    if retention.get("evidence_only") is not True:
        add_finding(
            findings,
            "evidence_only_required",
            "error",
            "open",
            "retention_policy.evidence_only must be true.",
            {"actual": retention.get("evidence_only")},
        )
    if retention.get("runtime_execution_admitted") is not False:
        add_finding(
            findings,
            "runtime_execution_admitted_must_be_false",
            "error",
            "open",
            "retention_policy.runtime_execution_admitted must be false.",
            {"actual": retention.get("runtime_execution_admitted")},
        )
    if not isinstance(min_required_days, int) or min_required_days < 1:
        add_finding(
            findings,
            "min_required_days_invalid",
            "error",
            "open",
            "retention_policy.min_required_days must be integer >= 1.",
            {"actual": min_required_days},
        )
        min_required_days = 1
    if recommended_days is not None and (not isinstance(recommended_days, int) or recommended_days < 1):
        add_finding(
            findings,
            "recommended_days_invalid",
            "error",
            "open",
            "retention_policy.recommended_days must be integer >= 1 when provided.",
            {"actual": recommended_days},
        )
        recommended_days = None
    if not isinstance(actual_retention_days, int) or actual_retention_days < 0:
        add_finding(
            findings,
            "actual_retention_days_invalid",
            "error",
            "open",
            "retention_policy.actual_retention_days must be integer >= 0.",
            {"actual": actual_retention_days},
        )
        actual_retention_days = 0

    if isinstance(actual_retention_days, int) and isinstance(min_required_days, int):
        if actual_retention_days < min_required_days:
            add_finding(
                findings,
                "retention_below_required_days",
                "error",
                "open",
                "actual_retention_days is below min_required_days.",
                {"actual_retention_days": actual_retention_days, "min_required_days": min_required_days},
            )
    if (
        isinstance(actual_retention_days, int)
        and isinstance(recommended_days, int)
        and actual_retention_days < recommended_days
        and actual_retention_days >= min_required_days
    ):
        add_finding(
            findings,
            "retention_below_recommended_days",
            "warning",
            "open",
            "actual_retention_days is below recommended_days.",
            {"actual_retention_days": actual_retention_days, "recommended_days": recommended_days},
        )

    inventory = report.get("artifact_inventory", {}) if isinstance(report.get("artifact_inventory"), dict) else {}
    artifact_root = str(inventory.get("artifact_root", "")).strip()
    required_artifact_paths = inventory.get("required_artifact_paths", [])
    present_artifact_paths = inventory.get("present_artifact_paths", [])
    missing_artifacts = inventory.get("missing_artifacts", [])
    disallowed_artifact_paths = inventory.get("disallowed_artifact_paths", [])
    if not artifact_root:
        add_finding(findings, "artifact_root_missing", "error", "open", "artifact_inventory.artifact_root is required.")
    if artifact_root and _contains_unsafe_path_tokens(artifact_root):
        add_finding(
            findings,
            "artifact_root_unsafe",
            "error",
            "open",
            "artifact_inventory.artifact_root contains unsafe traversal or absolute-path tokens.",
            {"artifact_root": artifact_root},
        )
    if not _is_string_array(required_artifact_paths):
        add_finding(
            findings,
            "required_artifact_paths_invalid",
            "error",
            "open",
            "artifact_inventory.required_artifact_paths must be a non-empty string array.",
        )
        required_artifact_paths = []
    if not _is_string_array(present_artifact_paths):
        add_finding(
            findings,
            "present_artifact_paths_invalid",
            "error",
            "open",
            "artifact_inventory.present_artifact_paths must be a non-empty string array.",
        )
        present_artifact_paths = []
    if not _is_string_array(missing_artifacts) and missing_artifacts != []:
        add_finding(
            findings,
            "missing_artifacts_invalid",
            "error",
            "open",
            "artifact_inventory.missing_artifacts must be a string array.",
        )
        missing_artifacts = []
    if not _is_string_array(disallowed_artifact_paths) and disallowed_artifact_paths != []:
        add_finding(
            findings,
            "disallowed_artifact_paths_invalid",
            "error",
            "open",
            "artifact_inventory.disallowed_artifact_paths must be a string array.",
        )
        disallowed_artifact_paths = []

    required_artifact_paths = _normalize_string_list(required_artifact_paths)
    present_artifact_paths = _normalize_string_list(present_artifact_paths)
    missing_artifacts = _normalize_string_list(missing_artifacts)
    disallowed_artifact_paths = _normalize_string_list(disallowed_artifact_paths)

    for path_label, collection in (
        ("required_artifact_paths", required_artifact_paths),
        ("present_artifact_paths", present_artifact_paths),
        ("missing_artifacts", missing_artifacts),
        ("disallowed_artifact_paths", disallowed_artifact_paths),
    ):
        for path_value in collection:
            if _contains_unsafe_path_tokens(path_value):
                add_finding(
                    findings,
                    "artifact_path_unsafe",
                    "error",
                    "open",
                    f"{path_label} contains unsafe traversal or absolute-path tokens.",
                    {"path": path_value},
                )
            if artifact_root and not path_value.startswith(artifact_root):
                add_finding(
                    findings,
                    "artifact_path_outside_root",
                    "error",
                    "open",
                    f"{path_label} must stay under artifact_inventory.artifact_root.",
                    {"artifact_root": artifact_root, "path": path_value},
                )

    computed_missing_artifacts = sorted(set(required_artifact_paths) - set(present_artifact_paths))
    if computed_missing_artifacts != missing_artifacts:
        add_finding(
            findings,
            "missing_artifacts_mismatch",
            "warning",
            "open",
            "artifact_inventory.missing_artifacts does not match required-vs-present computation.",
            {"reported": missing_artifacts, "computed": computed_missing_artifacts},
        )
    if computed_missing_artifacts:
        add_finding(
            findings,
            "required_artifacts_missing",
            "error",
            "open",
            "Required artifacts are missing from present_artifact_paths.",
            {"missing_artifacts": computed_missing_artifacts},
        )

    if disallowed_artifact_paths:
        add_finding(
            findings,
            "disallowed_artifacts_present",
            "error",
            "open",
            "disallowed_artifact_paths must be empty.",
            {"disallowed_artifact_paths": disallowed_artifact_paths},
        )
    for path_value in required_artifact_paths + present_artifact_paths:
        if _has_forbidden_artifact_token(path_value):
            add_finding(
                findings,
                "forbidden_artifact_token_present",
                "error",
                "open",
                "Artifact path includes forbidden binary/cache/database token.",
                {"path": path_value},
            )

    release_validation = report.get("release_validation", {}) if isinstance(report.get("release_validation"), dict) else {}
    required_qc_gate_ids = release_validation.get("required_qc_gate_ids", [])
    present_qc_gate_ids = release_validation.get("present_qc_gate_ids", [])
    missing_qc_gate_ids = release_validation.get("missing_qc_gate_ids", [])
    release_readiness_state = str(release_validation.get("release_readiness_state", "")).strip()
    manual_review_required = release_validation.get("manual_review_required")

    if not _is_string_array(required_qc_gate_ids):
        add_finding(
            findings,
            "required_qc_gate_ids_invalid",
            "error",
            "open",
            "release_validation.required_qc_gate_ids must be a non-empty string array.",
        )
        required_qc_gate_ids = []
    if not _is_string_array(present_qc_gate_ids) and present_qc_gate_ids != []:
        add_finding(
            findings,
            "present_qc_gate_ids_invalid",
            "error",
            "open",
            "release_validation.present_qc_gate_ids must be a string array.",
        )
        present_qc_gate_ids = []
    if not _is_string_array(missing_qc_gate_ids) and missing_qc_gate_ids != []:
        add_finding(
            findings,
            "missing_qc_gate_ids_invalid",
            "error",
            "open",
            "release_validation.missing_qc_gate_ids must be a string array.",
        )
        missing_qc_gate_ids = []
    required_qc_gate_ids = _normalize_string_list(required_qc_gate_ids)
    present_qc_gate_ids = _normalize_string_list(present_qc_gate_ids)
    missing_qc_gate_ids = _normalize_string_list(missing_qc_gate_ids)

    computed_missing_gates = sorted(set(required_qc_gate_ids) - set(present_qc_gate_ids))
    if computed_missing_gates != missing_qc_gate_ids:
        add_finding(
            findings,
            "missing_qc_gate_ids_mismatch",
            "warning",
            "open",
            "release_validation.missing_qc_gate_ids does not match required-vs-present computation.",
            {"reported": missing_qc_gate_ids, "computed": computed_missing_gates},
        )
    if computed_missing_gates:
        add_finding(
            findings,
            "required_qc_gates_missing",
            "error",
            "open",
            "Required QC gates are missing.",
            {"missing_qc_gate_ids": computed_missing_gates},
        )

    if release_readiness_state not in {
        "ready_for_manual_release_review",
        "blocked_missing_evidence",
        "blocked_safety_boundary",
    }:
        add_finding(
            findings,
            "release_readiness_state_invalid",
            "error",
            "open",
            "release_validation.release_readiness_state is invalid.",
            {"actual": release_readiness_state},
        )
    else:
        if release_readiness_state == "ready_for_manual_release_review" and computed_missing_gates:
            add_finding(
                findings,
                "readiness_state_conflicts_with_missing_qc",
                "error",
                "open",
                "ready_for_manual_release_review cannot be set when QC gates are missing.",
            )
        if release_readiness_state == "blocked_missing_evidence" and not computed_missing_gates:
            add_finding(
                findings,
                "readiness_state_missing_evidence_without_missing_qc",
                "warning",
                "open",
                "blocked_missing_evidence is set but missing_qc_gate_ids is empty.",
            )
        if release_readiness_state == "blocked_safety_boundary":
            add_finding(
                findings,
                "release_blocked_safety_boundary",
                "error",
                "open",
                "Release is blocked by safety boundary policy.",
            )

    if not isinstance(manual_review_required, bool):
        add_finding(
            findings,
            "manual_review_required_invalid",
            "error",
            "open",
            "release_validation.manual_review_required must be boolean.",
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
