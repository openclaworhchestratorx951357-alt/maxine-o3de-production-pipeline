#!/usr/bin/env python3
"""Generate an execution-admission no-op receipt dry-run proof artifact."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


BLOCKED_PATH_TOKENS = {"cache", "engine", ".git", "site-packages"}
DEFAULT_DECISION_RECORD = (
    "examples/execution-admission/max_biped_v1_execution_admission_decision_approved.json"
)
DEFAULT_OUTPUT = (
    "examples/sandbox/manifests/reports/pilot-release-chain-proof/"
    "execution-admission-receipt-dry-run.json"
)
APPROVAL_PREFIX = "APPROVE EXECUTION ADMISSION "
REPORT_TYPE = "EXECUTION_ADMISSION_RECEIPT_DRY_RUN_v1_REPORT"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a no-op execution-admission receipt report from a decision record. "
            "This command does not execute any external tool."
        )
    )
    parser.add_argument(
        "--decision-record",
        default=DEFAULT_DECISION_RECORD,
        help="Path to execution-admission decision record JSON.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Output path for execution-admission dry-run receipt report JSON.",
    )
    return parser.parse_args()


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


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _to_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _slug(value: str) -> str:
    allowed = []
    for ch in value.lower():
        if ch.isalnum() or ch in {"-", "_"}:
            allowed.append(ch)
        else:
            allowed.append("-")
    text = "".join(allowed).strip("-")
    return text or "candidate"


def build_report(decision: Dict[str, Any], decision_path: Path) -> Dict[str, Any]:
    failures: List[str] = []

    candidate_id = str(decision.get("candidate_id", "")).strip()
    decision_id = str(decision.get("decision_id", "")).strip()
    decision_state = str(decision.get("decision_state", "")).strip()

    requested_execution = (
        decision.get("requested_execution", {})
        if isinstance(decision.get("requested_execution"), dict)
        else {}
    )
    surface_id = str(requested_execution.get("surface_id", "")).strip()
    command_or_tool_path = str(requested_execution.get("command_or_tool_path", "")).strip()
    arguments = _to_string_list(requested_execution.get("arguments", []))

    scope = decision.get("scope", {}) if isinstance(decision.get("scope"), dict) else {}
    allowed_input_paths = _to_string_list(scope.get("allowed_input_paths", []))
    allowed_output_paths = _to_string_list(scope.get("allowed_output_paths", []))
    blocked_surfaces = _to_string_list(scope.get("blocked_surfaces_confirmed", []))

    approval = decision.get("approval", {}) if isinstance(decision.get("approval"), dict) else {}
    approval_received = bool(approval.get("approval_received"))
    approval_phrase_received = str(approval.get("approval_phrase_received", "")).strip()
    expected_phrase = f"{APPROVAL_PREFIX}{candidate_id}" if candidate_id else ""

    admission_outcome = (
        decision.get("admission_outcome", {})
        if isinstance(decision.get("admission_outcome"), dict)
        else {}
    )
    admission_scope = str(admission_outcome.get("admission_scope", "")).strip()

    if not candidate_id:
        failures.append("candidate_id is required.")
    if not decision_id:
        failures.append("decision_id is required.")
    if decision_state != "approved":
        failures.append("decision_state must be approved for no-op dry-run receipt generation.")
    if not surface_id:
        failures.append("requested_execution.surface_id is required.")
    if not command_or_tool_path:
        failures.append("requested_execution.command_or_tool_path is required.")
    if not blocked_surfaces:
        failures.append("scope.blocked_surfaces_confirmed must include at least one blocked surface.")
    if not approval_received:
        failures.append("approval.approval_received must be true.")
    if expected_phrase and approval_phrase_received != expected_phrase:
        failures.append(
            "approval.approval_phrase_received must exactly match "
            f"'{expected_phrase}'."
        )

    arg_display = " ".join(arguments).strip()
    command_display = command_or_tool_path if not arg_display else f"{command_or_tool_path} {arg_display}"
    now_utc = datetime.now(timezone.utc).isoformat()
    receipt_id = f"dryrun-{_slug(candidate_id)}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    status = "pass" if not failures else "fail"
    report: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": REPORT_TYPE,
        "status": status,
        "generated_utc": now_utc,
        "decision_record_path": str(decision_path),
        "candidate_id": candidate_id,
        "decision_id": decision_id,
        "decision_state": decision_state,
        "admission_scope": admission_scope or "none",
        "execution_mode": "no_op_dry_run",
        "execution_performed": False,
        "approval_phrase_required": "APPROVE EXECUTION ADMISSION <candidate_id>",
        "approval_phrase_received": approval_phrase_received,
        "bounded_surface_id": surface_id,
        "command_or_tool_path": command_or_tool_path,
        "allowed_input_paths": allowed_input_paths,
        "allowed_output_paths": allowed_output_paths,
        "blocked_surfaces_confirmed": blocked_surfaces,
        "dry_run_receipt": {
            "receipt_id": receipt_id,
            "receipt_kind": "execution_admission_receipt_dry_run",
            "no_command_execution_recorded": True,
            "command_display": f"DisplayOnly: {command_display}".strip(),
            "recorded_by": "proof_flow",
        },
        "failures": failures,
    }
    return report


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    try:
        decision_path = resolve_safe_path(repo_root, args.decision_record, "decision_record")
        output_path = resolve_safe_path(repo_root, args.output, "output")
    except ValueError as exc:
        print(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "report_type": REPORT_TYPE,
                    "status": "fail",
                    "error": str(exc),
                },
                indent=2,
            )
        )
        return 2

    if not decision_path.exists():
        payload = {
            "schema_version": "1.0.0",
            "report_type": REPORT_TYPE,
            "status": "fail",
            "error": f"decision_record not found: {decision_path}",
        }
        print(json.dumps(payload, indent=2))
        return 1

    try:
        decision = _read_json(decision_path)
    except Exception as exc:
        payload = {
            "schema_version": "1.0.0",
            "report_type": REPORT_TYPE,
            "status": "fail",
            "error": f"failed to parse decision_record: {exc}",
        }
        print(json.dumps(payload, indent=2))
        return 1

    report = build_report(decision, decision_path)
    _write_json(output_path, report)
    report["output_path"] = str(output_path)
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
