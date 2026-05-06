#!/usr/bin/env python3
"""Generate the admitted no-op release-candidate package receipt report."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


BLOCKED_PATH_TOKENS = {"cache", "engine", ".git", "site-packages"}
CANDIDATE_ID = "release_candidate_package_receipt_noop_v1"
APPROVAL_PHRASE = f"APPROVE EXECUTION ADMISSION {CANDIDATE_ID}"
REPORT_TYPE = "RELEASE_CANDIDATE_PACKAGE_RECEIPT_NOOP_v1_REPORT"
CONTRACT_ID = "RELEASE_CANDIDATE_PACKAGE_RECEIPT_NOOP_v1"
APPROVED_OUTPUT_ROOT = (
    "examples/sandbox/execution-receipts/release-candidate-package-receipt-noop"
)
DEFAULT_DECISION_RECORD = (
    "examples/execution-admission/"
    "release_candidate_package_receipt_noop_execution_admission_decision_approved.json"
)
DEFAULT_RELEASE_CANDIDATE_PACKAGE_REPORT = (
    "examples/real-pilot-release-candidate-package/"
    "max_biped_v1_real_pilot_release_candidate_package_pass.json"
)
DEFAULT_OUTPUT = (
    "examples/sandbox/execution-receipts/release-candidate-package-receipt-noop/"
    "release_candidate_package_receipt_noop_v1.receipt.json"
)
EXPECTED_BLOCKED_SURFACES = {
    "o3de_editor_execution",
    "o3de_cli_execution",
    "asset_processor_execution",
    "blender_or_dcc_execution",
    "spawn_or_publish_execution",
    "cache_read",
    "live_asset_database_read",
    "authoritative_source_uuid_claims",
    "authoritative_asset_id_claims",
    "authoritative_product_id_claims",
    "production_path_write",
    "engine_path_write",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate admitted no-op receipt report for "
            "release_candidate_package_receipt_noop_v1."
        )
    )
    parser.add_argument(
        "--decision-record",
        default=DEFAULT_DECISION_RECORD,
        help="Path to approved execution-admission decision record JSON.",
    )
    parser.add_argument(
        "--release-candidate-package-report",
        default=DEFAULT_RELEASE_CANDIDATE_PACKAGE_REPORT,
        help="Path to real pilot release-candidate package proof report JSON.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Output receipt report JSON path.",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def ensure_output_root(repo_root: Path, output_path: Path) -> None:
    allowed_root = resolve_safe_path(repo_root, APPROVED_OUTPUT_ROOT, "approved_output_root")
    if not _path_within(output_path, allowed_root):
        raise ValueError(
            "output path must remain under "
            f"{APPROVED_OUTPUT_ROOT} for this admitted no-op candidate."
        )


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + os.linesep, encoding="utf-8")


def rel_ref(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def add_finding(
    findings: List[Dict[str, Any]],
    finding_id: str,
    severity: str,
    message: str,
    details: Dict[str, Any] | None = None,
) -> None:
    payload: Dict[str, Any] = {
        "id": finding_id,
        "severity": severity,
        "message": message,
    }
    if details:
        payload["details"] = details
    findings.append(payload)


def build_fail_payload(error_message: str) -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "report_type": REPORT_TYPE,
        "status": "fail",
        "receipt_id": "receipt-noop-error",
        "candidate_id": CANDIDATE_ID,
        "admission_decision_ref": "",
        "approval_phrase": APPROVAL_PHRASE,
        "approval_status": "missing",
        "operator_approval_required": True,
        "operator_approval_present": False,
        "started_at": utc_now(),
        "finished_at": utc_now(),
        "input_refs": [],
        "output_refs": [],
        "evidence_hashes": {"input_sha256": []},
        "command_invoked": " ".join(sys.argv),
        "command_mode": "noop",
        "external_execution_performed": False,
        "publication_performed": False,
        "o3de_execution_status": "blocked",
        "editor_execution_status": "blocked",
        "runtime_execution_status": "blocked",
        "asset_processor_execution_status": "blocked",
        "blender_dcc_execution_status": "blocked",
        "cache_live_db_access_status": "blocked",
        "spawn_publish_status": "blocked",
        "production_write_status": "blocked",
        "source_uuid_claim_status": "not_authoritative",
        "asset_id_claim_status": "not_authoritative",
        "product_id_claim_status": "not_authoritative",
        "result": "fail",
        "findings": [
            {
                "id": "receipt_generation_failed",
                "severity": "error",
                "message": error_message,
            }
        ],
        "post_validation": {
            "safety_verifier_required": True,
            "proof_flow_required": True,
            "working_tree_clean_required": True,
        },
        "manifest_attachment": {
            "target_path": "qc.gates[]",
            "future_target_path": "qc.checks[]",
            "qc_check": {
                "check_id": CANDIDATE_ID,
                "result": "fail",
                "severity": "error",
                "details": {
                    "contract_id": CONTRACT_ID,
                    "candidate_id": CANDIDATE_ID,
                    "execution_admission_status": "blocked",
                    "publication_admission_status": "blocked",
                    "claim_status": "not_authoritative",
                },
            },
        },
    }


def validate_inputs(
    decision: Dict[str, Any],
    release_candidate_package_report: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> None:
    candidate_id = str(decision.get("candidate_id", "")).strip()
    if candidate_id != CANDIDATE_ID:
        add_finding(
            findings,
            "candidate_id_mismatch",
            "error",
            "Decision candidate_id must match release_candidate_package_receipt_noop_v1.",
            {"actual": candidate_id, "expected": CANDIDATE_ID},
        )

    decision_state = str(decision.get("decision_state", "")).strip()
    if decision_state != "approved":
        add_finding(
            findings,
            "decision_state_not_approved",
            "error",
            "Decision state must be approved for admitted no-op receipt generation.",
            {"actual": decision_state},
        )

    requested_execution = (
        decision.get("requested_execution")
        if isinstance(decision.get("requested_execution"), dict)
        else {}
    )
    surface_id = str(requested_execution.get("surface_id", "")).strip()
    if surface_id != "release_candidate_package_receipt_noop_execution":
        add_finding(
            findings,
            "surface_id_invalid",
            "error",
            "requested_execution.surface_id must be release_candidate_package_receipt_noop_execution.",
            {"actual": surface_id},
        )

    command_or_tool_path = str(requested_execution.get("command_or_tool_path", "")).strip()
    if not command_or_tool_path:
        add_finding(
            findings,
            "command_or_tool_path_missing",
            "error",
            "requested_execution.command_or_tool_path is required.",
        )

    approval = decision.get("approval") if isinstance(decision.get("approval"), dict) else {}
    approval_received = bool(approval.get("approval_received"))
    phrase = str(approval.get("approval_phrase_received", "")).strip()
    if not approval_received:
        add_finding(
            findings,
            "operator_approval_missing",
            "error",
            "approval.approval_received must be true.",
        )
    if phrase != APPROVAL_PHRASE:
        add_finding(
            findings,
            "approval_phrase_mismatch",
            "error",
            "approval.approval_phrase_received must exactly match approved candidate phrase.",
            {"actual": phrase, "expected": APPROVAL_PHRASE},
        )

    scope = decision.get("scope") if isinstance(decision.get("scope"), dict) else {}
    blocked_surfaces = scope.get("blocked_surfaces_confirmed", [])
    blocked_surface_values = {
        value.strip() for value in blocked_surfaces if isinstance(value, str) and value.strip()
    }
    missing_blocked = sorted(EXPECTED_BLOCKED_SURFACES - blocked_surface_values)
    if missing_blocked:
        add_finding(
            findings,
            "blocked_surfaces_incomplete",
            "error",
            "Decision record is missing required blocked surface confirmations.",
            {"missing_blocked_surfaces": missing_blocked},
        )

    admission_outcome = (
        decision.get("admission_outcome")
        if isinstance(decision.get("admission_outcome"), dict)
        else {}
    )
    if admission_outcome.get("execution_admitted") is not True:
        add_finding(
            findings,
            "admission_outcome_not_admitted",
            "error",
            "admission_outcome.execution_admitted must be true for this admitted no-op candidate.",
        )
    scope_value = str(admission_outcome.get("admission_scope", "")).strip()
    if scope_value != "bounded_candidate_only":
        add_finding(
            findings,
            "admission_scope_invalid",
            "error",
            "admission_outcome.admission_scope must be bounded_candidate_only.",
            {"actual": scope_value},
        )

    report_type = str(release_candidate_package_report.get("report_type", "")).strip()
    if report_type != "REAL_PILOT_RELEASE_CANDIDATE_PACKAGE_v1_REPORT":
        add_finding(
            findings,
            "release_candidate_package_report_type_invalid",
            "error",
            "Release-candidate package report type must be REAL_PILOT_RELEASE_CANDIDATE_PACKAGE_v1_REPORT.",
            {"actual": report_type},
        )

    report_status = str(release_candidate_package_report.get("status", "")).strip()
    if report_status not in {"pass", "warn"}:
        add_finding(
            findings,
            "release_candidate_package_status_invalid",
            "error",
            "Release-candidate package report status must be pass or warn for no-op receipt generation.",
            {"actual": report_status},
        )

    safety = (
        release_candidate_package_report.get("safety")
        if isinstance(release_candidate_package_report.get("safety"), dict)
        else {}
    )
    package_publication_status = str(safety.get("package_publication_status", "")).strip()
    if package_publication_status != "blocked":
        add_finding(
            findings,
            "package_publication_status_not_blocked",
            "error",
            "Release-candidate package safety.package_publication_status must remain blocked.",
            {"actual": package_publication_status},
        )


def build_payload(
    repo_root: Path,
    decision_path: Path,
    package_report_path: Path,
    output_path: Path,
    decision: Dict[str, Any],
    release_candidate_package_report: Dict[str, Any],
    started_at: str,
) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    validate_inputs(decision, release_candidate_package_report, findings)

    input_refs = [
        rel_ref(repo_root, decision_path),
        rel_ref(repo_root, package_report_path),
    ]
    output_refs = [rel_ref(repo_root, output_path)]

    evidence_hashes = {
        "input_sha256": [
            {"path": rel_ref(repo_root, decision_path), "sha256": sha256_file(decision_path)},
            {"path": rel_ref(repo_root, package_report_path), "sha256": sha256_file(package_report_path)},
        ]
    }

    result = "pass" if not any(item.get("severity") == "error" for item in findings) else "fail"
    status = result
    finished_at = utc_now()
    receipt_id = (
        "receipt-noop-"
        + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    )
    severity = "info" if result == "pass" else "error"

    payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "report_type": REPORT_TYPE,
        "status": status,
        "receipt_id": receipt_id,
        "candidate_id": CANDIDATE_ID,
        "admission_decision_ref": rel_ref(repo_root, decision_path),
        "approval_phrase": APPROVAL_PHRASE,
        "approval_status": "approved" if result == "pass" else "missing",
        "operator_approval_required": True,
        "operator_approval_present": True,
        "started_at": started_at,
        "finished_at": finished_at,
        "input_refs": input_refs,
        "output_refs": output_refs,
        "evidence_hashes": evidence_hashes,
        "command_invoked": " ".join(sys.argv),
        "command_mode": "noop",
        "external_execution_performed": False,
        "publication_performed": False,
        "o3de_execution_status": "blocked",
        "editor_execution_status": "blocked",
        "runtime_execution_status": "blocked",
        "asset_processor_execution_status": "blocked",
        "blender_dcc_execution_status": "blocked",
        "cache_live_db_access_status": "blocked",
        "spawn_publish_status": "blocked",
        "production_write_status": "blocked",
        "source_uuid_claim_status": "not_authoritative",
        "asset_id_claim_status": "not_authoritative",
        "product_id_claim_status": "not_authoritative",
        "result": result,
        "findings": findings,
        "post_validation": {
            "safety_verifier_required": True,
            "proof_flow_required": True,
            "working_tree_clean_required": True,
        },
        "manifest_attachment": {
            "target_path": "qc.gates[]",
            "future_target_path": "qc.checks[]",
            "qc_check": {
                "check_id": CANDIDATE_ID,
                "result": result,
                "severity": severity,
                "details": {
                    "contract_id": CONTRACT_ID,
                    "candidate_id": CANDIDATE_ID,
                    "command_mode": "noop",
                    "external_execution_performed": False,
                    "publication_performed": False,
                    "execution_scope": "receipt_noop_only",
                    "execution_admission_status": "admitted_noop_only",
                    "publication_admission_status": "blocked",
                    "claim_status": "not_authoritative",
                    "release_candidate_package_status": str(
                        release_candidate_package_report.get("status", "")
                    ).strip(),
                },
            },
        },
    }
    return payload


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    started_at = utc_now()

    try:
        decision_path = resolve_safe_path(repo_root, args.decision_record, "decision_record")
        package_report_path = resolve_safe_path(
            repo_root,
            args.release_candidate_package_report,
            "release_candidate_package_report",
        )
        output_path = resolve_safe_path(repo_root, args.output, "output")
        ensure_output_root(repo_root, output_path)
    except Exception as exc:
        payload = build_fail_payload(str(exc))
        print(json.dumps(payload, indent=2))
        return 1

    if not decision_path.exists():
        payload = build_fail_payload(f"decision_record not found: {decision_path}")
        print(json.dumps(payload, indent=2))
        return 1
    if not package_report_path.exists():
        payload = build_fail_payload(f"release_candidate_package_report not found: {package_report_path}")
        print(json.dumps(payload, indent=2))
        return 1

    try:
        decision = load_json(decision_path)
        release_candidate_package_report = load_json(package_report_path)
    except Exception as exc:
        payload = build_fail_payload(f"failed to parse input JSON: {exc}")
        print(json.dumps(payload, indent=2))
        return 1

    payload = build_payload(
        repo_root=repo_root,
        decision_path=decision_path,
        package_report_path=package_report_path,
        output_path=output_path,
        decision=decision,
        release_candidate_package_report=release_candidate_package_report,
        started_at=started_at,
    )
    write_json(output_path, payload)
    payload["output_path"] = rel_ref(repo_root, output_path)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
