#!/usr/bin/env python3
"""Validate PR #92 natural-language command-pack audit artifact v1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


DEFAULT_SCHEMA_REL = Path("schemas/maxine_pr_92_natural_language_command_pack_audit.schema.json")
DEFAULT_AUDIT_REL = Path("examples/execution-admission/pr_92_natural_language_command_pack_audit_v1.json")
REQUIRED_CRITERIA_IDS: Set[str] = {str(i) for i in range(1, 27)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate PR #92 natural-language command-pack audit artifact."
    )
    parser.add_argument(
        "audit_report_path",
        nargs="?",
        default=str(DEFAULT_AUDIT_REL),
        help="Path to the PR #92 audit report JSON.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_schema(payload: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return True, []

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    if not errors:
        return True, []

    messages: List[str] = []
    for err in errors:
        location = ".".join(str(p) for p in err.absolute_path) or "<root>"
        messages.append(f"{location}: {err.message}")
    return False, messages


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
        "message": message,
    }
    if details:
        item["details"] = details
    findings.append(item)


def _check_required_keys(
    findings: List[Dict[str, Any]],
    payload: Dict[str, Any],
    section_name: str,
    required_keys: List[str],
) -> bool:
    value = payload.get(section_name)
    if not isinstance(value, dict):
        add_finding(
            findings,
            f"{section_name}_missing_or_invalid",
            "error",
            f"{section_name} must be an object.",
        )
        return False

    missing = [key for key in required_keys if key not in value]
    if missing:
        add_finding(
            findings,
            f"{section_name}_missing_keys",
            "error",
            f"{section_name} is missing required keys.",
            {"missing_keys": missing},
        )
        return False
    return True


def _is_merge_safe_recommendation(merge_recommendation: str) -> bool:
    return merge_recommendation == "safe_to_merge_after_follow_up"


def _criteria_map(payload: Dict[str, Any]) -> Dict[str, bool]:
    result: Dict[str, bool] = {}
    rows = payload.get("strict_acceptance_criteria", [])
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id", "")).strip()
        if cid:
            result[cid] = bool(row.get("pass"))
    return result


def _resolve_ref_path(repo_root: Path, raw_value: str) -> Path:
    p = Path(raw_value)
    if p.is_absolute():
        return p
    return repo_root / p


def validate_payload(payload: Dict[str, Any], repo_root: Path) -> Tuple[str, List[Dict[str, Any]]]:
    findings: List[Dict[str, Any]] = []
    status = "pass"

    # PR identity checks.
    audited_pr = payload.get("audited_pr")
    if not isinstance(audited_pr, dict):
        add_finding(findings, "missing_pr_identity", "error", "audited_pr object is required.")
        status = "fail"
    else:
        required_pr_keys = ["repo", "pr_number", "title", "url", "head_branch", "base_branch", "head_sha"]
        missing_pr = [k for k in required_pr_keys if str(audited_pr.get(k, "")).strip() == ""]
        if missing_pr:
            add_finding(
                findings,
                "missing_pr_identity_fields",
                "error",
                "audited_pr is missing required identity fields.",
                {"missing_fields": missing_pr},
            )
            status = "fail"

    # Changed files summary checks.
    changed = payload.get("changed_files_summary")
    if not isinstance(changed, dict):
        add_finding(findings, "missing_changed_files_summary", "error", "changed_files_summary is required.")
        status = "fail"
    else:
        files = changed.get("files")
        if not isinstance(files, list) or not files:
            add_finding(
                findings,
                "changed_files_summary_missing_files",
                "error",
                "changed_files_summary.files must be non-empty.",
            )
            status = "fail"

    merge_recommendation = str(payload.get("merge_recommendation", "")).strip()
    if not merge_recommendation:
        add_finding(findings, "missing_merge_recommendation", "error", "merge_recommendation is required.")
        status = "fail"

    # Required findings for safety surfaces.
    required_sections = {
        "execution_surface_findings": [
            "direct_o3de_execution_detected",
            "editor_runtime_execution_detected",
            "asset_processor_execution_detected",
            "blender_dcc_execution_detected",
            "screenshot_capture_execution_detected",
            "notes",
        ],
        "runner_surface_findings": [
            "runner_implementation_detected",
            "runner_admission_detected",
            "runner_execution_detected",
            "notes",
        ],
        "gem_surface_findings": [
            "maxine_agent_control_gem_implementation_detected",
            "gem_adapter_implementation_detected",
            "notes",
        ],
        "admission_surface_findings": [
            "command_admission_detected",
            "approval_ready_claim_detected",
            "operator_approval_granted_detected",
            "approval_phrase_decision_detected",
            "notes",
        ],
        "publication_surface_findings": [
            "publication_admission_claim_detected",
            "publish_or_spawn_path_detected",
            "notes",
        ],
        "production_readiness_surface_findings": [
            "real_execution_admission_claim_detected",
            "publication_admission_claim_detected",
            "production_ready_claim_detected",
            "notes",
        ],
    }

    for section_name, keys in required_sections.items():
        if not _check_required_keys(findings, payload, section_name, keys):
            status = "fail"

    # Strict acceptance criteria completeness.
    criteria = _criteria_map(payload)
    missing_ids = sorted(REQUIRED_CRITERIA_IDS - set(criteria.keys()), key=lambda x: int(x))
    if missing_ids:
        add_finding(
            findings,
            "strict_acceptance_criteria_incomplete",
            "error",
            "strict_acceptance_criteria must include ids 1..26.",
            {"missing_ids": missing_ids},
        )
        status = "fail"

    # Validate source artifact refs exist when they are path refs.
    refs = payload.get("source_artifact_references", {})
    if isinstance(refs, dict):
        for key, value in refs.items():
            raw = str(value).strip()
            if not raw:
                add_finding(
                    findings,
                    "source_artifact_ref_empty",
                    "error",
                    "Source artifact reference is empty.",
                    {"key": key},
                )
                status = "fail"
                continue
            if raw.startswith("refs/"):
                continue
            path = _resolve_ref_path(repo_root, raw)
            if not path.exists():
                add_finding(
                    findings,
                    "source_artifact_ref_missing",
                    "error",
                    "Source artifact reference path does not exist.",
                    {"key": key, "path": raw},
                )
                status = "fail"

    audit_status = str(payload.get("audit_status", "")).strip()
    unsafe_claims_detected = bool(payload.get("unsafe_claims_detected"))

    # Merge-safe recommendation is only allowed when every strict criterion passes and key findings are explicitly safe.
    if _is_merge_safe_recommendation(merge_recommendation):
        if audit_status != "audit_complete_merge_safe_if_static_only":
            add_finding(
                findings,
                "merge_safe_status_mismatch",
                "error",
                "merge-safe recommendation requires audit_status=audit_complete_merge_safe_if_static_only.",
            )
            status = "fail"

        if unsafe_claims_detected:
            add_finding(
                findings,
                "unsafe_claims_with_merge_safe_recommendation",
                "error",
                "unsafe_claims_detected cannot be true when merge recommendation is merge-safe.",
            )
            status = "fail"

        if any(not passed for passed in criteria.values()) or len(criteria) != len(REQUIRED_CRITERIA_IDS):
            add_finding(
                findings,
                "merge_safe_without_all_strict_criteria_passing",
                "error",
                "merge-safe recommendation requires all strict acceptance criteria to pass.",
            )
            status = "fail"

        # Explicit surface checks required for merge-safe recommendation.
        surface_checks = [
            ("execution_surface_findings", "direct_o3de_execution_detected"),
            ("runner_surface_findings", "runner_implementation_detected"),
            ("gem_surface_findings", "gem_adapter_implementation_detected"),
            ("admission_surface_findings", "command_admission_detected"),
            ("publication_surface_findings", "publication_admission_claim_detected"),
            ("production_readiness_surface_findings", "production_ready_claim_detected"),
        ]
        for section, key in surface_checks:
            section_value = payload.get(section, {})
            if not isinstance(section_value, dict):
                continue
            if bool(section_value.get(key)):
                add_finding(
                    findings,
                    "merge_safe_with_unsafe_surface_detection",
                    "error",
                    "merge-safe recommendation cannot coexist with unsafe surface detections.",
                    {"section": section, "field": key},
                )
                status = "fail"

    if audit_status in {
        "audit_inconclusive",
        "audit_failed_unable_to_fetch_pr",
        "audit_failed_unsafe_surface_detected",
    } and _is_merge_safe_recommendation(merge_recommendation):
        add_finding(
            findings,
            "incompatible_inconclusive_or_unsafe_merge_recommendation",
            "error",
            "Inconclusive/unsafe audit_status cannot recommend merge-safe outcome.",
        )
        status = "fail"

    return status, findings


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    audit_path = _resolve_ref_path(repo_root, args.audit_report_path)
    schema_path = repo_root / DEFAULT_SCHEMA_REL

    if not audit_path.exists():
        report = {
            "schema_version": "1.0.0",
            "report_type": "PR_92_NL_COMMAND_PACK_AUDIT_VALIDATION_v1_REPORT",
            "status": "fail",
            "audit_report_path": str(audit_path),
            "findings": [
                {
                    "id": "audit_report_not_found",
                    "severity": "error",
                    "message": "Audit report path does not exist.",
                }
            ],
        }
        print(json.dumps(report, indent=2))
        return 2

    payload = load_json(audit_path)
    schema = load_json(schema_path)

    schema_ok, schema_messages = validate_schema(payload, schema)
    status, findings = validate_payload(payload, repo_root)

    if not schema_ok:
        status = "fail"
        for message in schema_messages:
            add_finding(findings, "schema_validation_error", "error", message)

    report = {
        "schema_version": "1.0.0",
        "report_type": "PR_92_NL_COMMAND_PACK_AUDIT_VALIDATION_v1_REPORT",
        "status": status,
        "audit_report_path": str(audit_path),
        "audited_pr": payload.get("audited_pr", {}),
        "audit_status": payload.get("audit_status"),
        "merge_recommendation": payload.get("merge_recommendation"),
        "unsafe_claims_detected": payload.get("unsafe_claims_detected"),
        "findings": findings,
    }
    print(json.dumps(report, indent=2))

    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
