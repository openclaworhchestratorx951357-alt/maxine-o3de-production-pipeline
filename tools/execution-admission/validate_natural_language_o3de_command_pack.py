#!/usr/bin/env python3
"""Validate the static natural-language O3DE command pack boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACK_REL = Path("examples/execution-admission/natural_language_o3de_command_pack_v1.json")
ENVELOPE_SCHEMA_REL = Path("schemas/maxine_natural_language_o3de_command_envelope.schema.json")
PACK_SCHEMA_REL = Path("schemas/maxine_natural_language_o3de_command_pack.schema.json")

REQUIRED_SOURCE_REFS = {
    "candidate_matrix_ref": "examples/execution-admission/execution_admission_candidate_matrix_v1.json",
    "preflight_contracts_ref": "examples/execution-admission/execution_admission_preflight_contracts_v1.json",
    "preflight_proof_packages_ref": "examples/execution-admission/execution_admission_preflight_proof_packages_v1.json",
    "readiness_rollup_ref": "examples/execution-admission/execution_admission_readiness_rollup_v1.json",
    "dry_run_plan_ref": "examples/execution-admission/release_candidate_package_publish_dry_run_plan_v1.json",
    "dry_run_receipt_contract_ref": "examples/execution-admission/release_candidate_package_publish_dry_run_receipt_contract_v1.json",
    "blocked_unissued_receipt_ref": "examples/execution-admission/release_candidate_package_publish_dry_run_receipt_blocked_v1.json",
    "admission_blocker_checklist_ref": "examples/execution-admission/release_candidate_package_publish_dry_run_admission_blockers_v1.json",
    "operator_approval_packet_ref": "examples/execution-admission/release_candidate_package_publish_dry_run_operator_approval_packet_v1.json",
    "operator_approval_packet_completeness_ref": "examples/execution-admission/release_candidate_package_publish_dry_run_operator_approval_packet_completeness_v1.json",
    "approval_request_readiness_ref": "examples/execution-admission/release_candidate_package_publish_dry_run_approval_request_readiness_v1.json",
    "non_approval_decision_ref": "examples/execution-admission/release_candidate_package_publish_dry_run_non_approval_decision_v1.json",
    "sandbox_boundary_ref": "examples/execution-admission/release_candidate_package_publish_dry_run_sandbox_boundary_v1.json",
    "runner_interface_ref": "examples/execution-admission/release_candidate_package_publish_dry_run_runner_interface_v1.json",
    "production_readiness_report_ref": "examples/production-readiness-report/max_biped_v1_production_readiness_report_pass.json",
    "noop_receipt_status_ref": "examples/execution-admission/release_candidate_package_receipt_noop_execution_admission_decision_approved.json",
}
REQUIRED_SOURCE_STATUS_FIELDS = {
    "candidate_matrix_status",
    "preflight_contracts_status",
    "preflight_proof_packages_status",
    "readiness_rollup_status",
    "dry_run_plan_status",
    "dry_run_receipt_contract_status",
    "blocked_unissued_receipt_status",
    "admission_blocker_checklist_status",
    "operator_approval_packet_status",
    "operator_approval_packet_completeness_status",
    "approval_request_readiness_status",
    "non_approval_decision_status",
    "sandbox_boundary_status",
    "runner_interface_status",
    "production_readiness_status",
    "noop_receipt_status",
}
PROTECTED_FALSE_FIELDS = (
    "runner_implemented",
    "runner_admitted",
    "runner_executed",
    "execution_admitted",
    "publication_admitted",
    "production_ready_claimed",
    "approval_phrase_present",
)
BLOCKED_GATE_FIELDS = (
    "sandbox_boundary_required",
    "sandbox_boundary_validation_required",
    "runner_interface_required",
    "receipt_contract_required",
    "receipt_contract_validation_required",
    "candidate_admission_required",
)
REQUIRED_ADMISSION_GATES = {
    "candidate_specific_admission",
    "runner_interface_contract",
    "sandbox_boundary_contract",
    "receipt_contract",
    "safety_verifier",
    "proof_flow",
}
ALLOWED_OUTPUT_ROOTS = (
    Path("examples/sandbox/nl-o3de-control"),
    Path("examples/sandbox/manifests/reports/nl-o3de-control"),
)
ALLOWED_EXTENSIONS = {".json", ".md", ".txt", ".sha256"}
FORBIDDEN_EXTENSIONS = {
    ".exe",
    ".dll",
    ".bat",
    ".cmd",
    ".ps1",
    ".py",
    ".fbx",
    ".asset",
    ".prefab",
    ".pak",
    ".zip",
    ".7z",
    ".db",
    ".sqlite",
    ".cache",
}
FORBIDDEN_PATH_PARTS = {
    ".git",
    "cache",
    "engine",
    "engineroot",
    "export",
    "livedb",
    "publish",
    "publication",
    "production",
    "spawn",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a natural-language O3DE command envelope or command pack."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=str(DEFAULT_PACK_REL),
        help="Path to a command pack JSON or command envelope JSON.",
    )
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Return zero for a structurally valid blocked command envelope.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_path(raw_path: str) -> Path:
    path = Path(str(raw_path).strip())
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def add_finding(
    findings: List[Dict[str, Any]],
    finding_id: str,
    severity: str,
    message: str,
    details: Dict[str, Any] | None = None,
) -> None:
    finding: Dict[str, Any] = {
        "id": finding_id,
        "severity": severity,
        "message": message,
    }
    if details:
        finding["details"] = details
    findings.append(finding)


def validate_schema(payload: Dict[str, Any], schema_path: Path) -> Tuple[bool, List[str]]:
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return True, []
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    messages: List[str] = []
    for err in errors:
        location = ".".join(str(item) for item in err.absolute_path) or "<root>"
        messages.append(f"{location}: {err.message}")
    return not messages, messages


def _within(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _path_is_network(raw_path: str) -> bool:
    return raw_path.replace("\\", "/").startswith("//")


def _validate_output_path(
    findings: List[Dict[str, Any]], blocked_or_failed_fields: List[str], raw_path: str
) -> bool:
    if _path_is_network(raw_path):
        add_finding(findings, "network_output_path", "error", "Output path must not be a network path.", {"path": raw_path})
        blocked_or_failed_fields.append("output_contract")
        return False
    path = Path(raw_path)
    if path.is_absolute():
        add_finding(findings, "absolute_output_path", "error", "Output path must be repo-relative.", {"path": raw_path})
        blocked_or_failed_fields.append("output_contract")
        return False
    if ".." in path.parts:
        add_finding(findings, "parent_traversal", "error", "Output path must not contain parent traversal.", {"path": raw_path})
        blocked_or_failed_fields.append("output_contract")
        return False
    if path.suffix.lower() in FORBIDDEN_EXTENSIONS or path.suffix.lower() not in ALLOWED_EXTENSIONS:
        add_finding(findings, "forbidden_output_extension", "error", "Output extension is not allowed.", {"path": raw_path})
        blocked_or_failed_fields.append("output_contract")
        return False
    if {part.lower() for part in path.parts} & FORBIDDEN_PATH_PARTS:
        add_finding(findings, "forbidden_output_root", "error", "Output path contains a forbidden root token.", {"path": raw_path})
        blocked_or_failed_fields.append("output_contract")
        return False
    full_path = (REPO_ROOT / path).resolve(strict=False)
    if not any(_within(full_path, REPO_ROOT / allowed_root) for allowed_root in ALLOWED_OUTPUT_ROOTS):
        add_finding(findings, "outside_sandbox_root", "error", "Output path must stay within allowed sandbox roots.", {"path": raw_path})
        blocked_or_failed_fields.append("output_contract")
        return False
    return True


def _validate_source_artifacts(
    payload: Dict[str, Any],
    findings: List[Dict[str, Any]],
    blocked_or_failed_fields: List[str],
) -> None:
    source_artifacts = payload.get("source_artifacts")
    if not isinstance(source_artifacts, dict):
        add_finding(findings, "source_artifacts_missing", "error", "source_artifacts must be present.")
        blocked_or_failed_fields.append("source_artifacts")
        return
    for field, expected_path in REQUIRED_SOURCE_REFS.items():
        actual = str(source_artifacts.get(field, "")).replace("\\", "/").strip()
        if not actual:
            add_finding(
                findings,
                "source_artifact_ref_missing",
                "error",
                "Required post-PR93 source artifact reference is missing.",
                {"field": field},
            )
            blocked_or_failed_fields.append("source_artifacts")
            continue
        if actual != expected_path:
            add_finding(
                findings,
                "source_artifact_ref_unexpected",
                "error",
                "Source artifact reference must bind to the post-PR93 chain path.",
                {"field": field, "expected": expected_path, "actual": actual},
            )
            blocked_or_failed_fields.append("source_artifacts")
            continue
        if not resolve_path(actual).exists():
            add_finding(
                findings,
                "source_artifact_ref_missing",
                "error",
                "Source artifact reference path does not exist.",
                {"field": field, "path": actual},
            )
            blocked_or_failed_fields.append("source_artifacts")

    source_status = payload.get("source_artifact_validation_status")
    if not isinstance(source_status, dict):
        add_finding(findings, "source_artifact_validation_status_missing", "error", "source_artifact_validation_status must be present.")
        blocked_or_failed_fields.append("source_artifact_validation_status")
        return
    for field in sorted(REQUIRED_SOURCE_STATUS_FIELDS):
        if str(source_status.get(field, "")).strip() != "pass":
            add_finding(
                findings,
                "source_artifact_validation_status_not_pass",
                "error",
                "Source artifact validation status must be pass.",
                {"field": field},
            )
            blocked_or_failed_fields.append("source_artifact_validation_status")


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for child in value.values():
            yield from _iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_strings(child)
    elif isinstance(value, str):
        yield value


def validate_envelope(payload: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]], List[str]]:
    findings: List[Dict[str, Any]] = []
    blocked_or_failed_fields: List[str] = []
    status = "pass"

    schema_ok, schema_messages = validate_schema(payload, REPO_ROOT / ENVELOPE_SCHEMA_REL)
    if not schema_ok:
        status = "fail"
        blocked_or_failed_fields.append("schema")
        for message in schema_messages:
            add_finding(findings, "schema_validation_error", "error", message)

    if payload.get("record_type") != "NATURAL_LANGUAGE_O3DE_COMMAND_ENVELOPE_v1":
        status = "fail"
        blocked_or_failed_fields.append("record_type")
        add_finding(findings, "record_type_mismatch", "error", "Unexpected record_type.")

    envelope_status = str(payload.get("command_envelope_status", "")).strip()
    admission_status = str(payload.get("command_admission_status", "")).strip()
    if envelope_status == "static_envelope_blocked":
        status = "blocked" if status != "fail" else status
    elif envelope_status != "static_envelope_valid":
        status = "fail"
        blocked_or_failed_fields.append("command_envelope_status")
        add_finding(findings, "command_envelope_status_invalid", "error", "Invalid command_envelope_status.")

    if admission_status not in {"unadmitted", "blocked"}:
        status = "fail"
        blocked_or_failed_fields.append("command_admission_status")
        add_finding(findings, "command_admission_status_invalid", "error", "Command envelopes cannot admit commands.")

    for field in PROTECTED_FALSE_FIELDS:
        if bool(payload.get(field, False)):
            status = "fail"
            blocked_or_failed_fields.append(field)
            add_finding(findings, "protected_status_field_true", "error", "Protected status field must remain false.", {"field": field})

    if bool(payload.get("approval_phrase_present", False)) and not payload.get("approval_decision_ref"):
        status = "fail"
        blocked_or_failed_fields.append("approval_phrase_present")
        add_finding(
            findings,
            "approval_phrase_without_decision_ref",
            "error",
            "Approval phrase cannot be treated as a command-envelope decision.",
        )

    future_execution = bool(payload.get("runner_required")) or admission_status == "blocked"
    if future_execution:
        for field in BLOCKED_GATE_FIELDS:
            if payload.get(field) is not True:
                status = "fail"
                blocked_or_failed_fields.append(field)
                add_finding(
                    findings,
                    "required_gate_field_false",
                    "error",
                    "Future execution command is missing a required fail-closed gate field.",
                    {"field": field},
                )
        gates = {str(item).strip() for item in payload.get("required_admission_gates", [])}
        missing_gates = sorted(REQUIRED_ADMISSION_GATES - gates)
        if missing_gates:
            status = "fail"
            blocked_or_failed_fields.append("required_admission_gates")
            add_finding(
                findings,
                "required_admission_gates_missing",
                "error",
                "Future execution command must route through the full admission chain.",
                {"missing": missing_gates},
            )

    source_finding_count = len(findings)
    _validate_source_artifacts(payload, findings, blocked_or_failed_fields)
    if len(findings) > source_finding_count and status != "fail":
        status = "fail"

    output_contract = payload.get("output_contract")
    if not isinstance(output_contract, dict):
        status = "fail"
        blocked_or_failed_fields.append("output_contract")
        add_finding(findings, "output_contract_missing", "error", "output_contract must be present.")
    else:
        if output_contract.get("sandbox_only") is not True:
            status = "fail"
            blocked_or_failed_fields.append("output_contract")
            add_finding(findings, "output_contract_not_sandbox_only", "error", "output_contract.sandbox_only must be true.")
        for raw_path in output_contract.get("planned_outputs", []):
            if not _validate_output_path(findings, blocked_or_failed_fields, str(raw_path)):
                status = "fail"

    forbidden_phrases = {
        "command envelope equals execution",
        "command envelope equals admission",
        "command envelope equals runner implementation",
        "command envelope equals gem adapter implementation",
        "command envelope equals maxineagentcontrol gem implementation",
        "command envelope equals publication",
        "command envelope equals production_ready",
        "natural-language command pack can bypass runner interface",
        "natural-language command pack can bypass sandbox boundary",
        "natural-language command pack can bypass receipt contract",
        "natural-language command pack can bypass approval",
        "natural-language command pack can bypass admission",
    }
    all_text = "\n".join(_iter_strings(payload)).lower()
    for phrase in sorted(forbidden_phrases):
        if phrase in all_text:
            status = "fail"
            blocked_or_failed_fields.append("unsafe_language")
            add_finding(findings, "unsafe_command_pack_language", "error", "Envelope contains unsafe bypass/equivalence language.", {"phrase": phrase})

    return status, findings, sorted(set(blocked_or_failed_fields))


def validate_pack(payload: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    findings: List[Dict[str, Any]] = []
    envelope_reports: List[Dict[str, Any]] = []
    status = "pass"

    schema_ok, schema_messages = validate_schema(payload, REPO_ROOT / PACK_SCHEMA_REL)
    if not schema_ok:
        status = "fail"
        for message in schema_messages:
            add_finding(findings, "schema_validation_error", "error", message)

    if payload.get("record_type") != "NATURAL_LANGUAGE_O3DE_COMMAND_PACK_v1":
        status = "fail"
        add_finding(findings, "record_type_mismatch", "error", "Unexpected command-pack record_type.")

    protected_false = (
        "runner_implemented",
        "runner_admitted",
        "execution_admitted",
        "publication_admitted",
        "production_ready_claimed",
        "approval_phrase_present",
    )
    for field in protected_false:
        if bool(payload.get(field, False)):
            status = "fail"
            add_finding(findings, "pack_protected_status_field_true", "error", "Pack protected field must remain false.", {"field": field})

    for ref in payload.get("command_envelope_refs", []):
        raw_path = str(ref.get("path", "") if isinstance(ref, dict) else "")
        expected_status = str(ref.get("expected_status", "") if isinstance(ref, dict) else "")
        envelope_path = resolve_path(raw_path)
        if not raw_path or not envelope_path.exists():
            status = "fail"
            add_finding(findings, "command_envelope_ref_missing", "error", "Command envelope ref is missing.", {"path": raw_path})
            continue
        envelope = load_json(envelope_path)
        envelope_status, envelope_findings, blocked_or_failed_fields = validate_envelope(envelope)
        envelope_reports.append(
            {
                "path": raw_path,
                "status": envelope_status,
                "expected_status": expected_status,
                "findings": envelope_findings,
                "blocked_or_failed_fields": blocked_or_failed_fields,
            }
        )
        if envelope_status != expected_status:
            status = "fail"
            add_finding(
                findings,
                "command_envelope_status_mismatch",
                "error",
                "Command envelope status did not match pack expectation.",
                {"path": raw_path, "expected": expected_status, "actual": envelope_status},
            )
        if envelope_status == "fail":
            status = "fail"

    return status, findings, envelope_reports


def main() -> int:
    args = parse_args()
    target_path = resolve_path(args.path)
    if not target_path.exists():
        report = {
            "schema_version": "1.0.0",
            "report_type": "NATURAL_LANGUAGE_O3DE_COMMAND_PACK_VALIDATION_v1_REPORT",
            "status": "fail",
            "findings": [
                {
                    "id": "input_not_found",
                    "severity": "error",
                    "message": "Input JSON path does not exist.",
                }
            ],
            "blocked_or_failed_fields": ["input_path"],
        }
        print(json.dumps(report, indent=2))
        return 2

    payload = load_json(target_path)
    record_type = payload.get("record_type")
    if record_type == "NATURAL_LANGUAGE_O3DE_COMMAND_PACK_v1":
        status, findings, envelope_reports = validate_pack(payload)
        report = {
            "schema_version": "1.0.0",
            "report_type": "NATURAL_LANGUAGE_O3DE_COMMAND_PACK_VALIDATION_v1_REPORT",
            "status": status,
            "command_pack_path": str(target_path),
            "runner_implemented": bool(payload.get("runner_implemented")),
            "runner_admitted": bool(payload.get("runner_admitted")),
            "execution_admitted": bool(payload.get("execution_admitted")),
            "publication_admitted": bool(payload.get("publication_admitted")),
            "production_ready_claimed": bool(payload.get("production_ready_claimed")),
            "findings": findings,
            "envelope_reports": envelope_reports,
        }
        print(json.dumps(report, indent=2))
        return 0 if status == "pass" else 1

    status, findings, blocked_or_failed_fields = validate_envelope(payload)
    report = {
        "schema_version": "1.0.0",
        "report_type": "NATURAL_LANGUAGE_O3DE_COMMAND_ENVELOPE_VALIDATION_v1_REPORT",
        "status": status,
        "command_envelope_path": str(target_path),
        "command_id": payload.get("command_id"),
        "command_envelope_status": payload.get("command_envelope_status"),
        "command_admission_status": payload.get("command_admission_status"),
        "runner_implemented": bool(payload.get("runner_implemented")),
        "runner_admitted": bool(payload.get("runner_admitted")),
        "execution_admitted": bool(payload.get("execution_admitted")),
        "publication_admitted": bool(payload.get("publication_admitted")),
        "production_ready_claimed": bool(payload.get("production_ready_claimed")),
        "blocked_or_failed_fields": blocked_or_failed_fields,
        "findings": findings,
    }
    print(json.dumps(report, indent=2))
    if status == "pass":
        return 0
    if status == "blocked" and args.allow_blocked:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
