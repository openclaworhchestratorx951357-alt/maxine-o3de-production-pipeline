#!/usr/bin/env python3
"""Validate a MAXINE natural-language O3DE control command envelope."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_SCHEMA_REL = Path("schemas/maxine_nl_o3de_control_command.schema.json")
DEFAULT_COMMAND_REL = Path(
    "examples/nl-o3de-control/nl_o3de_control_command_inspect_actor_products_v1.json"
)

PASS_MODES = {
    "read_only",
    "evidence_only",
    "noop_receipt",
    "dry_run_planning",
}
BLOCKED_EXECUTION_MODES = {
    "sandbox_dry_run",
    "real_execution",
    "publication",
}
REQUIRED_FORBIDDEN_ACTIONS = {
    "write_production_asset",
    "live_o3de_editor_execution",
    "asset_processor_execution",
    "real_execution",
    "publication",
    "engine_path_write",
    "production_path_write",
    "cache_live_db_access",
    "destructive_cleanup",
}
REQUIRED_FORBIDDEN_PATH_TOKENS = {
    ".git",
    "engine",
    "cache",
    "production",
    "site-packages",
}
SOURCE_ARTIFACT_KEYS = {
    "candidate_matrix_ref",
    "preflight_contracts_ref",
    "preflight_proof_packages_ref",
    "readiness_rollup_ref",
    "production_readiness_report_ref",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a MAXINE natural-language O3DE control command envelope."
    )
    parser.add_argument(
        "command_path",
        nargs="?",
        default=str(DEFAULT_COMMAND_REL),
        help="Path to NL O3DE control command JSON.",
    )
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Return zero when the command is structurally valid but blocked by admission policy.",
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


def as_string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def resolve_ref_path(repo_root: Path, raw_path: str) -> Path:
    candidate = Path(str(raw_path).strip())
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root / candidate).resolve()


def _path_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def validate_payload(payload: Dict[str, Any], repo_root: Path) -> Tuple[str, List[Dict[str, Any]]]:
    findings: List[Dict[str, Any]] = []
    status = "pass"

    if payload.get("record_type") != "NL_O3DE_CONTROL_COMMAND_v1":
        add_finding(findings, "record_type_mismatch", "error", "record_type must be NL_O3DE_CONTROL_COMMAND_v1.")
        status = "fail"

    if str(payload.get("natural_language_request", "")).strip() == "":
        add_finding(findings, "empty_natural_language_request", "error", "natural_language_request must not be empty.")
        status = "fail"

    normalized_intent = str(payload.get("normalized_intent", "")).strip()
    if normalized_intent == "unknown_or_unsupported":
        add_finding(
            findings,
            "unsupported_intent",
            "blocker",
            "Command was parsed as unknown_or_unsupported and must be clarified before O3DE control.",
        )
        status = "blocked" if status != "fail" else status

    execution_mode = str(payload.get("execution_mode", "")).strip()
    if execution_mode in BLOCKED_EXECUTION_MODES:
        add_finding(
            findings,
            "execution_mode_not_admitted",
            "blocker",
            "This execution mode requires explicit admission before the agent may run it.",
            {"execution_mode": execution_mode},
        )
        status = "blocked" if status != "fail" else status
    elif execution_mode not in PASS_MODES:
        add_finding(findings, "execution_mode_unknown", "error", "execution_mode is not recognized.")
        status = "fail"

    admission_status = str(payload.get("admission_status", "")).strip()
    if execution_mode in {"real_execution", "publication"} and admission_status not in {
        "admitted_real_execution",
        "admitted_publication",
    }:
        add_finding(
            findings,
            "execution_admission_missing",
            "blocker",
            "Real execution/publication commands require a matching admitted status.",
        )
        status = "blocked" if status != "fail" else status

    allowed_actions = as_string_set(payload.get("allowed_actions"))
    forbidden_actions = as_string_set(payload.get("forbidden_actions"))
    missing_forbidden = sorted(REQUIRED_FORBIDDEN_ACTIONS - forbidden_actions)
    if missing_forbidden:
        add_finding(
            findings,
            "required_forbidden_actions_missing",
            "error",
            "Command must keep all high-risk O3DE actions explicitly forbidden until admitted.",
            {"missing": missing_forbidden},
        )
        status = "fail"

    conflicting_actions = sorted(allowed_actions & REQUIRED_FORBIDDEN_ACTIONS)
    if conflicting_actions:
        add_finding(
            findings,
            "forbidden_actions_also_allowed",
            "error",
            "High-risk actions cannot appear in allowed_actions.",
            {"conflicts": conflicting_actions},
        )
        status = "fail"

    source_artifacts = payload.get("source_artifacts", {})
    if not isinstance(source_artifacts, dict):
        source_artifacts = {}
    for key in sorted(SOURCE_ARTIFACT_KEYS):
        ref = str(source_artifacts.get(key, "")).strip()
        ref_path = resolve_ref_path(repo_root, ref)
        if not ref or not ref_path.exists():
            add_finding(
                findings,
                "source_artifact_missing",
                "error",
                f"Required source artifact {key} does not exist.",
                {"key": key, "path": ref},
            )
            status = "fail"

    approval = payload.get("approval", {})
    if not isinstance(approval, dict):
        approval = {}
    if approval.get("phrase_present") is True and not approval.get("decision_ref"):
        add_finding(
            findings,
            "approval_phrase_without_decision_ref",
            "error",
            "Approval phrase cannot be treated as valid without an auditable decision_ref.",
        )
        status = "fail"
    if approval.get("required") is True and execution_mode in {"real_execution", "publication"}:
        if approval.get("phrase_present") is not True or not approval.get("decision_ref"):
            add_finding(
                findings,
                "required_approval_not_satisfied",
                "blocker",
                "Required approval is not satisfied for the requested execution mode.",
            )
            status = "blocked" if status != "fail" else status

    safety = payload.get("safety", {})
    if not isinstance(safety, dict):
        safety = {}
    unsafe_flags = {
        "real_execution_allowed": safety.get("real_execution_allowed") is True,
        "publication_allowed": safety.get("publication_allowed") is True,
        "production_ready_claimed": safety.get("production_ready_claimed") is True,
    }
    active_unsafe_flags = [name for name, enabled in unsafe_flags.items() if enabled]
    if active_unsafe_flags:
        add_finding(
            findings,
            "unsafe_safety_claims",
            "error",
            "NL command v1 may not claim real execution, publication, or production readiness.",
            {"active_flags": active_unsafe_flags},
        )
        status = "fail"

    output_contract = payload.get("output_contract", {})
    if not isinstance(output_contract, dict):
        output_contract = {}
    forbidden_path_tokens = as_string_set(output_contract.get("forbidden_path_tokens"))
    missing_tokens = sorted(REQUIRED_FORBIDDEN_PATH_TOKENS - forbidden_path_tokens)
    if missing_tokens:
        add_finding(
            findings,
            "required_forbidden_path_tokens_missing",
            "error",
            "Command must explicitly block known high-risk path tokens.",
            {"missing": missing_tokens},
        )
        status = "fail"

    for raw_path in output_contract.get("allowed_output_paths", []):
        path = resolve_ref_path(repo_root, str(raw_path))
        if not _path_within(path, repo_root):
            add_finding(
                findings,
                "allowed_output_path_outside_repo",
                "error",
                "Allowed output paths must remain inside the repository.",
                {"path": str(raw_path)},
            )
            status = "fail"

    return status, findings


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    command_path = resolve_ref_path(repo_root, args.command_path)
    schema_path = repo_root / DEFAULT_SCHEMA_REL

    if not command_path.exists():
        print(json.dumps({"status": "fail", "findings": [{"id": "command_not_found"}]}, indent=2))
        return 2

    payload = load_json(command_path)
    schema = load_json(schema_path)
    schema_ok, schema_messages = validate_schema(payload, schema)
    status, findings = validate_payload(payload, repo_root)
    if not schema_ok:
        status = "fail"
        for message in schema_messages:
            add_finding(findings, "schema_validation_error", "error", message)

    report = {
        "status": status,
        "report_type": "NL_O3DE_CONTROL_COMMAND_VALIDATION_v1_REPORT",
        "check_id": "nl_o3de_control_command_v1",
        "command_path": str(command_path),
        "command_id": payload.get("command_id"),
        "normalized_intent": payload.get("normalized_intent"),
        "execution_mode": payload.get("execution_mode"),
        "admission_status": payload.get("admission_status"),
        "findings": findings,
        "manifest_attachment": {
            "target_path": "qc.gates[]",
            "future_target_path": "qc.checks[]"
        }
    }
    print(json.dumps(report, indent=2))

    if status == "pass":
        return 0
    if status == "blocked" and args.allow_blocked:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
