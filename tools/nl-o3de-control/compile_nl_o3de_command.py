#!/usr/bin/env python3
"""Compile natural language into a static, non-executing O3DE command envelope."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_OUTPUT_ROOTS = (
    Path("examples/sandbox/nl-o3de-control"),
    Path("examples/sandbox/manifests/reports/nl-o3de-control"),
)
ALLOWED_OUTPUT_EXTENSIONS = {".json", ".md", ".txt", ".sha256"}
FORBIDDEN_OUTPUT_EXTENSIONS = {
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
FORBIDDEN_OUTPUT_PARTS = {
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

SOURCE_ARTIFACTS = {
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
SOURCE_ARTIFACT_VALIDATION_STATUS = {
    "candidate_matrix_status": "pass",
    "preflight_contracts_status": "pass",
    "preflight_proof_packages_status": "pass",
    "readiness_rollup_status": "pass",
    "dry_run_plan_status": "pass",
    "dry_run_receipt_contract_status": "pass",
    "blocked_unissued_receipt_status": "pass",
    "admission_blocker_checklist_status": "pass",
    "operator_approval_packet_status": "pass",
    "operator_approval_packet_completeness_status": "pass",
    "approval_request_readiness_status": "pass",
    "non_approval_decision_status": "pass",
    "sandbox_boundary_status": "pass",
    "runner_interface_status": "pass",
    "production_readiness_status": "pass",
    "noop_receipt_status": "pass",
}
REQUIRED_ADMISSION_GATES = [
    "candidate_specific_admission",
    "runner_interface_contract",
    "sandbox_boundary_contract",
    "receipt_contract",
    "safety_verifier",
    "proof_flow",
]
FORBIDDEN_ACTIONS = [
    "direct_o3de_execution",
    "editor_runtime_execution",
    "asset_processor_execution",
    "blender_dcc_execution",
    "screenshot_capture",
    "spawn",
    "publication",
    "production_path_write",
    "engine_path_write",
    "cache_live_db_access",
    "gem_adapter_implementation",
    "maxine_agent_control_gem_implementation",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile a natural-language request into a static O3DE command envelope."
    )
    parser.add_argument("request", help="Natural-language O3DE request.")
    parser.add_argument("--output", help="Optional sandbox output path for the envelope JSON.")
    return parser.parse_args()


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:72] or "natural-language-o3de-command"


def _is_network_path(raw_path: str) -> bool:
    normalized = raw_path.replace("\\", "/")
    return normalized.startswith("//")


def _within(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _output_path_error(raw_path: str) -> str | None:
    if _is_network_path(raw_path):
        return "network_output_path"
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return "absolute_output_path"
    if ".." in candidate.parts:
        return "parent_traversal"
    lowered_parts = {part.lower() for part in candidate.parts}
    if lowered_parts & FORBIDDEN_OUTPUT_PARTS:
        return "forbidden_output_root"
    if candidate.suffix.lower() in FORBIDDEN_OUTPUT_EXTENSIONS:
        return "forbidden_output_extension"
    if candidate.suffix.lower() not in ALLOWED_OUTPUT_EXTENSIONS:
        return "forbidden_output_extension"

    full_path = (REPO_ROOT / candidate).resolve(strict=False)
    if not any(_within(full_path, REPO_ROOT / root) for root in ALLOWED_OUTPUT_ROOTS):
        return "outside_sandbox_root"
    return None


def validate_output_path(raw_path: str) -> Path:
    reason = _output_path_error(raw_path)
    if reason:
        raise ValueError(f"{reason}: {raw_path}")
    return REPO_ROOT / Path(raw_path)


def classify_request(text: str) -> Tuple[str, str | None]:
    lower = text.lower()
    if "maxineagentcontrol" in lower:
        return "unsupported_or_unsafe", "maxine_agent_control_gem_unimplemented"
    if "gem adapter" in lower or ("adapter" in lower and "gem" in lower):
        return "unsupported_or_unsafe", "gem_adapter_unimplemented"
    if "asset processor" in lower and any(term in lower for term in ("run", "execute", "start", "process")):
        return "unsupported_or_unsafe", "asset_processor_execution_forbidden"
    if "blender" in lower or "dcc" in lower:
        return "unsupported_or_unsafe", "blender_dcc_execution_forbidden"
    if any(term in lower for term in ("spawn", "publish", "publication", "export")) and (
        "dry run" in lower or "dry-run" in lower
    ):
        return "future_publication_dry_run", "publication_mode_unadmitted"
    if "editor" in lower or "runtime" in lower:
        return "unsupported_or_unsafe", "editor_runtime_execution_forbidden"
    if any(term in lower for term in ("spawn", "publish", "publication", "export")):
        return "unsupported_or_unsafe", "spawn_publish_forbidden"
    if "o3de" in lower and any(term in lower for term in ("run", "execute", "launch", "load")):
        return "unsupported_or_unsafe", "direct_o3de_execution_forbidden"
    if any(term in lower for term in ("inspect", "validate", "check", "static", "evidence", "actor", "product")):
        return "static_read_only", None
    return "unsupported_or_unsafe", "unsupported_command"


def build_envelope(text: str) -> Dict[str, object]:
    execution_mode, refusal_reason_code = classify_request(text)
    blocked = refusal_reason_code is not None
    future_execution = execution_mode != "static_read_only"
    return {
        "schema_version": "1.0.0",
        "record_type": "NATURAL_LANGUAGE_O3DE_COMMAND_ENVELOPE_v1",
        "command_id": slugify(text),
        "command_version": "v1",
        "natural_language_request": text,
        "normalized_intent": execution_mode,
        "command_envelope_status": "static_envelope_blocked" if blocked else "static_envelope_valid",
        "command_admission_status": "blocked" if blocked else "unadmitted",
        "execution_mode": execution_mode,
        "refusal_reason_code": refusal_reason_code,
        "runner_required": future_execution,
        "runner_interface_required": future_execution,
        "runner_implemented": False,
        "runner_admitted": False,
        "runner_executed": False,
        "sandbox_boundary_required": True,
        "sandbox_boundary_validation_required": future_execution,
        "receipt_contract_required": future_execution,
        "receipt_contract_validation_required": future_execution,
        "candidate_admission_required": future_execution,
        "execution_admitted": False,
        "publication_admitted": False,
        "production_ready_claimed": False,
        "approval_required": future_execution,
        "approval_phrase_present": False,
        "approval_decision_ref": None,
        "planned_actions": [],
        "allowed_static_operations": [
            "parse_natural_language",
            "emit_static_command_envelope",
            "validate_static_command_envelope",
        ],
        "forbidden_actions": FORBIDDEN_ACTIONS,
        "source_artifacts": SOURCE_ARTIFACTS,
        "source_artifact_validation_status": SOURCE_ARTIFACT_VALIDATION_STATUS,
        "required_admission_gates": REQUIRED_ADMISSION_GATES,
        "output_contract": {
            "sandbox_only": True,
            "allowed_output_roots": [str(root).replace("\\", "/") for root in ALLOWED_OUTPUT_ROOTS],
            "planned_outputs": [
                "examples/sandbox/nl-o3de-control/"
                + ("blocked" if blocked else "static")
                + f"-{slugify(text)}.json"
            ],
            "allowed_extensions": sorted(ALLOWED_OUTPUT_EXTENSIONS),
            "forbidden_extensions": sorted(FORBIDDEN_OUTPUT_EXTENSIONS),
        },
        "safety_notes": [
            "This command envelope is static and non-executing.",
            "This command envelope does not admit a command, implement a runner, or implement Gem adapters.",
            "Future execution requires candidate-specific admission, runner interface, sandbox boundary, receipt contract, safety verifier, and proof flow.",
        ],
    }


def main() -> int:
    args = parse_args()
    envelope = build_envelope(args.request)
    output = json.dumps(envelope, indent=2) + "\n"
    if args.output:
        try:
            output_path = validate_output_path(args.output)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
