#!/usr/bin/env python3
"""Validate the PR #92 supersession record after PR #95 hardening."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECORD_REL = Path("examples/execution-admission/pr_92_supersession_record_v1.json")
SCHEMA_REL = Path("schemas/maxine_pr_92_supersession_record.schema.json")

REQUIRED_FUTURE_ROUTING = {
    "command-pack validator": "missing_command_pack_validator_routing",
    "candidate-specific admission": "missing_candidate_specific_admission_routing",
    "runner interface contract": "missing_runner_interface_routing",
    "sandbox boundary contract": "missing_sandbox_boundary_routing",
    "receipt contract": "missing_receipt_contract_routing",
    "safety verifier": "missing_safety_verifier_routing",
    "proof flow": "missing_proof_flow_routing",
    "production-readiness gate": "missing_production_readiness_gate_routing",
}

SAFETY_FALSE_FIELDS = {
    "direct_o3de_execution": "direct_o3de_execution_allowed",
    "runner_implemented": "runner_implemented_true",
    "gem_adapter_implemented": "gem_adapter_implemented_true",
    "command_admitted": "command_admitted_true",
    "dry_run_admitted": "dry_run_admitted_true",
    "real_execution_admitted": "real_execution_admitted_true",
    "publication_admitted": "publication_admitted_true",
    "production_ready_claimed": "production_ready_claimed_true",
}

FORBIDDEN_INTERPRETATIONS = {
    "approval",
    "command admission",
    "dry-run admission",
    "real execution admission",
    "publication admission",
    "production_ready",
    "runner implementation",
    "runner admission",
    "Gem adapter implementation",
    "MaxineAgentControl Gem implementation",
    "direct O3DE control",
    "live Editor/runtime access",
    "spawn/publish permission",
    "production/engine write permission",
    "Cache/live DB access permission",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the PR #92 supersession record."
    )
    parser.add_argument(
        "record_path",
        nargs="?",
        default=str(DEFAULT_RECORD_REL),
        help="Path to the PR #92 supersession record JSON.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def _section(payload: Dict[str, Any], section_name: str) -> Dict[str, Any]:
    value = payload.get(section_name)
    if isinstance(value, dict):
        return value
    return {}


def _string_set(payload: Dict[str, Any], key: str) -> set[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def validate_payload(payload: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    findings: List[Dict[str, Any]] = []

    superseded_pr = _section(payload, "superseded_pr")
    superseding_pr = _section(payload, "superseding_pr")
    audit_pr = _section(payload, "audit_pr")

    if superseded_pr.get("pr_number") != 92:
        add_finding(findings, "wrong_superseded_pr", "error", "superseded_pr.pr_number must be 92.")
    if superseding_pr.get("pr_number") != 95:
        add_finding(findings, "wrong_superseding_pr", "error", "superseding_pr.pr_number must be 95.")
    if audit_pr.get("pr_number") != 94:
        add_finding(findings, "wrong_audit_pr", "error", "audit_pr.pr_number must be 94.")
    if audit_pr.get("audit_status") != "audit_complete_block_merge_pending_hardening":
        add_finding(
            findings,
            "wrong_audit_status",
            "error",
            "audit_pr.audit_status must preserve PR #94 blocked hardening status.",
        )
    if audit_pr.get("merge_recommendation") != "do_not_merge_yet":
        add_finding(
            findings,
            "wrong_audit_merge_recommendation",
            "error",
            "audit_pr.merge_recommendation must be do_not_merge_yet.",
        )

    if payload.get("supersession_status") != "active_supersession_record":
        add_finding(
            findings,
            "wrong_supersession_status",
            "error",
            "supersession_status must be active_supersession_record.",
        )

    if payload.get("pr_92_merge_allowed") is not False:
        add_finding(
            findings,
            "pr_92_merge_allowed_true",
            "error",
            "PR #92 merge must remain disallowed as-is.",
        )
    if payload.get("pr_92_close_recommended") is not True:
        add_finding(
            findings,
            "pr_92_close_not_recommended",
            "error",
            "PR #92 close-as-superseded recommendation must be present.",
        )
    if payload.get("pr_92_safe_to_merge_without_revision") is not False:
        add_finding(
            findings,
            "pr_92_safe_to_merge_without_revision",
            "error",
            "Record must not claim PR #92 is safe to merge without revision.",
        )

    if not payload.get("required_revision_conditions"):
        add_finding(
            findings,
            "missing_required_revision_conditions",
            "error",
            "required_revision_conditions must be non-empty.",
        )
    if not payload.get("forbidden_interpretations"):
        add_finding(
            findings,
            "missing_forbidden_interpretations",
            "error",
            "forbidden_interpretations must be non-empty.",
        )
    if not payload.get("required_future_routing"):
        add_finding(
            findings,
            "missing_required_future_routing",
            "error",
            "required_future_routing must be non-empty.",
        )

    routing = _string_set(payload, "required_future_routing")
    for required, finding_id in REQUIRED_FUTURE_ROUTING.items():
        if required not in routing:
            add_finding(
                findings,
                finding_id,
                "error",
                "required_future_routing is missing a required gate.",
                {"missing": required},
            )

    forbidden = _string_set(payload, "forbidden_interpretations")
    missing_forbidden = sorted(FORBIDDEN_INTERPRETATIONS - forbidden)
    if missing_forbidden:
        add_finding(
            findings,
            "missing_forbidden_interpretation_entries",
            "error",
            "forbidden_interpretations must cover all blocked readings.",
            {"missing": missing_forbidden},
        )

    safety_posture = _section(payload, "safety_posture")
    for field, finding_id in SAFETY_FALSE_FIELDS.items():
        if safety_posture.get(field) is not False:
            add_finding(
                findings,
                finding_id,
                "error",
                f"safety_posture.{field} must be false.",
            )
    if safety_posture.get("blocked_surfaces_preserved") is not True:
        add_finding(
            findings,
            "blocked_surfaces_not_preserved",
            "error",
            "safety_posture.blocked_surfaces_preserved must be true.",
        )

    if payload.get("unsafe_claims_detected") is not False:
        add_finding(
            findings,
            "unsafe_claims_detected",
            "error",
            "unsafe_claims_detected must be false unless the record is explicitly unsafe_do_not_merge.",
        )

    if superseding_pr.get("merge_commit") != "ddc787c2eacf9409bf66f69f5813845e6a989c6e":
        add_finding(
            findings,
            "missing_pr_95_superseding_hardening",
            "error",
            "Record must identify PR #95 merge commit as the superseding hardening layer.",
        )
    if audit_pr.get("merge_commit") != "d55ca160ae96cc37e984799c90bb7580ddcacfd4":
        add_finding(
            findings,
            "missing_pr_94_audit_result",
            "error",
            "Record must identify PR #94 audit result.",
        )

    notes = " ".join(str(item) for item in payload.get("final_notes", []))
    if "safe to merge" in notes.lower() and "not" not in notes.lower():
        add_finding(
            findings,
            "implies_pr_92_safe_to_merge_without_revision",
            "error",
            "Record must not imply PR #92 is safe to merge without revision.",
        )

    status = "fail" if any(item["severity"] == "error" for item in findings) else "pass"
    return status, findings


def main() -> int:
    args = parse_args()
    record_path = Path(args.record_path)
    if not record_path.is_absolute():
        record_path = REPO_ROOT / record_path

    findings: List[Dict[str, Any]] = []
    try:
        payload = load_json(record_path)
    except Exception as exc:
        report = {
            "schema_version": "1.0.0",
            "report_type": "PR_92_SUPERSESSION_RECORD_VALIDATION_v1_REPORT",
            "status": "fail",
            "record_path": str(record_path),
            "findings": [
                {
                    "id": "record_load_failed",
                    "severity": "error",
                    "message": f"Unable to load record JSON: {exc}",
                }
            ],
        }
        print(json.dumps(report, indent=2))
        return 1

    schema_ok, schema_messages = validate_schema(payload, REPO_ROOT / SCHEMA_REL)
    if not schema_ok:
        for message in schema_messages:
            add_finding(findings, "schema_validation_error", "error", message)

    status, payload_findings = validate_payload(payload)
    findings.extend(payload_findings)
    if findings:
        status = "fail"

    report = {
        "schema_version": "1.0.0",
        "report_type": "PR_92_SUPERSESSION_RECORD_VALIDATION_v1_REPORT",
        "status": status,
        "record_path": str(record_path),
        "superseded_pr_number": _section(payload, "superseded_pr").get("pr_number"),
        "superseding_pr_number": _section(payload, "superseding_pr").get("pr_number"),
        "audit_pr_number": _section(payload, "audit_pr").get("pr_number"),
        "supersession_status": payload.get("supersession_status"),
        "pr_92_merge_allowed": payload.get("pr_92_merge_allowed"),
        "pr_92_close_recommended": payload.get("pr_92_close_recommended"),
        "unsafe_claims_detected": payload.get("unsafe_claims_detected"),
        "findings": findings,
    }
    print(json.dumps(report, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
