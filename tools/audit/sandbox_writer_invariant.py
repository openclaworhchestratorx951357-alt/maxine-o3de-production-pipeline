#!/usr/bin/env python3
"""Shared sandbox-writer admitted-only safety invariant helpers."""

from __future__ import annotations

from pathlib import Path
from typing import List


SANDBOX_WRITER_REL = "scripts/powershell/Invoke-MaxineSandboxResolverWrite.ps1"
SANDBOX_ROLLBACK_REL = "scripts/powershell/Invoke-MaxineSandboxRollback.ps1"
SANDBOX_INSPECT_REL = "scripts/powershell/Invoke-MaxineSandboxReceiptInspect.ps1"
SANDBOX_REVIEW_BUILD_REL = "scripts/powershell/Invoke-MaxineSandboxReviewPacketBuild.ps1"
SANDBOX_REVIEW_INSPECT_REL = "scripts/powershell/Invoke-MaxineSandboxReviewPacketInspect.ps1"
SANDBOX_REVIEW_DECISION_RECORD_REL = "scripts/powershell/Invoke-MaxineSandboxReviewDecisionRecord.ps1"
SANDBOX_REVIEW_DECISION_INSPECT_REL = "scripts/powershell/Invoke-MaxineSandboxReviewDecisionInspect.ps1"
SANDBOX_WORKFLOW_RUN_REL = "scripts/powershell/Invoke-MaxineSandboxWorkflowRun.ps1"
SANDBOX_WORKFLOW_INSPECT_REL = "scripts/powershell/Invoke-MaxineSandboxWorkflowInspect.ps1"
AUTHORITATIVE_REL = "scripts/powershell/Invoke-MaxineAuthoritativeResolverWrite.ps1"
RECEIPT_INDEX_REL = "examples/sandbox/receipts/index.json"
RECEIPT_INDEX_SCHEMA_REL = "schemas/maxine_sandbox_receipt_index.schema.json"
REVIEW_PACKET_SCHEMA_REL = "schemas/maxine_sandbox_review_packet.schema.json"
REVIEW_DECISION_SCHEMA_REL = "schemas/maxine_sandbox_review_decision.schema.json"
WORKFLOW_RUN_SCHEMA_REL = "schemas/maxine_sandbox_workflow_run.schema.json"
REVIEW_PACKETS_DIR_REL = "examples/sandbox/review-packets"
REVIEW_DECISIONS_DIR_REL = "examples/sandbox/review-decisions"
WORKFLOW_RUNS_DIR_REL = "examples/sandbox/workflow-runs"

ADMITTED_SANDBOX_COMMANDS = {
    SANDBOX_WRITER_REL,
    SANDBOX_ROLLBACK_REL,
    SANDBOX_INSPECT_REL,
    SANDBOX_REVIEW_BUILD_REL,
    SANDBOX_REVIEW_INSPECT_REL,
    SANDBOX_REVIEW_DECISION_RECORD_REL,
    SANDBOX_REVIEW_DECISION_INSPECT_REL,
    SANDBOX_WORKFLOW_RUN_REL,
    SANDBOX_WORKFLOW_INSPECT_REL,
}

REQUIRED_WRITER_NEEDLES = [
    "sandbox_only",
    "explicit_sandbox_approval",
    "approved_target_under_sandbox",
    "examples/sandbox/staging",
    "receipt_index_path",
    "receipts/index.json",
    "parent traversal and is blocked",
]

REQUIRED_ROLLBACK_NEEDLES = [
    "confirmrollback",
    "files_written",
    "sandbox_only",
    "receipt_index_path",
    "rolled_back",
]

REQUIRED_INSPECT_NEEDLES = [
    "receipt_id",
    "status",
    "files_written",
    "sha256_before",
    "sha256_after",
    "rollback_status",
    "blocked_reason",
]

REQUIRED_REVIEW_BUILD_NEEDLES = [
    "source_receipt_id",
    "operator_decision_state",
    "pending_review",
    "accepted_for_sandbox_only",
    "request_rollback",
    "rejected",
    "explicit_blocked_capabilities",
    "review-packets",
    "product_resolution",
    "asset_id_claims",
    "spawning",
    "publishing",
    "authoritative_writes",
]

REQUIRED_REVIEW_INSPECT_NEEDLES = [
    "review_packet_id",
    "source_receipt_id",
    "write_status",
    "rollback_status",
    "operator_decision_state",
]

REQUIRED_REVIEW_DECISION_RECORD_NEEDLES = [
    "accepted_for_sandbox_only",
    "request_rollback",
    "rejected",
    "needs_more_evidence",
    "rollback_requested",
    "rollback_execution_admitted",
    "review-decisions",
    "examples/sandbox",
    "explicit_non_admissions",
]

REQUIRED_REVIEW_DECISION_INSPECT_NEEDLES = [
    "decision_id",
    "source_review_packet_id",
    "source_receipt_id",
    "decision_state",
    "requested_next_action",
    "rollback_execution_admitted",
]

REQUIRED_WORKFLOW_RUN_NEEDLES = [
    "writeonly",
    "writeandreview",
    "writereviewanddecision",
    "rollbackrequestedonly",
    "invoke-maxinesandboxresolverwrite.ps1",
    "invoke-maxinesandboxreviewpacketbuild.ps1",
    "invoke-maxinesandboxreviewdecisionrecord.ps1",
    "workflow-runs",
    "rollback_execution_admitted",
    "explicit_non_admissions",
    "request_rollback",
    "rollback_requested",
]

REQUIRED_WORKFLOW_INSPECT_NEEDLES = [
    "workflow_run_id",
    "workflow_status",
    "receipt_id",
    "review_packet_id",
    "decision_id",
    "blocked_reason",
    "explicit_non_admissions",
]

FORBIDDEN_EXECUTION_NEEDLES = [
    "o3de editor",
    "asset processor",
    "o3de.exe",
    "editor.exe",
    "assetprocessorbatch",
    "invoke-maxineauthoritativeresolverwrite.ps1",
]

FORBIDDEN_CAPABILITY_NEEDLES = [
    "product resolution",
    "resolved_products",
    "asset_id",
    "asset ids",
    "spawn entities",
    "publish prefabs",
]

FORBIDDEN_INSPECT_MUTATION_NEEDLES = [
    "remove-item",
    "set-content",
    "add-content",
    "clear-content",
    "writealltext",
    "new-item",
    "out-file",
]

FORBIDDEN_REVIEW_INSPECT_MUTATION_NEEDLES = [
    "remove-item",
    "set-content",
    "add-content",
    "clear-content",
    "writealltext",
    "new-item",
    "out-file",
]

FORBIDDEN_REVIEW_DECISION_INSPECT_MUTATION_NEEDLES = [
    "remove-item",
    "set-content",
    "add-content",
    "clear-content",
    "writealltext",
    "new-item",
    "out-file",
]

FORBIDDEN_WORKFLOW_INSPECT_MUTATION_NEEDLES = [
    "remove-item",
    "set-content",
    "add-content",
    "clear-content",
    "writealltext",
    "new-item",
    "out-file",
]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").lower()


def sanitize_required_absent(paths: List[str]) -> List[str]:
    sanitized: List[str] = []
    for rel in paths:
        if rel in ADMITTED_SANDBOX_COMMANDS:
            continue
        sanitized.append(rel)
    return sanitized


def collect_sandbox_writer_invariant_failures(root: Path) -> List[str]:
    failures: List[str] = []

    writer = root / SANDBOX_WRITER_REL
    rollback = root / SANDBOX_ROLLBACK_REL
    inspect = root / SANDBOX_INSPECT_REL
    review_build = root / SANDBOX_REVIEW_BUILD_REL
    review_inspect = root / SANDBOX_REVIEW_INSPECT_REL
    review_decision_record = root / SANDBOX_REVIEW_DECISION_RECORD_REL
    review_decision_inspect = root / SANDBOX_REVIEW_DECISION_INSPECT_REL
    workflow_run = root / SANDBOX_WORKFLOW_RUN_REL
    workflow_inspect = root / SANDBOX_WORKFLOW_INSPECT_REL
    authoritative = root / AUTHORITATIVE_REL
    receipt_index = root / RECEIPT_INDEX_REL
    receipt_index_schema = root / RECEIPT_INDEX_SCHEMA_REL
    review_packet_schema = root / REVIEW_PACKET_SCHEMA_REL
    review_decision_schema = root / REVIEW_DECISION_SCHEMA_REL
    workflow_run_schema = root / WORKFLOW_RUN_SCHEMA_REL
    review_packets_dir = root / REVIEW_PACKETS_DIR_REL
    review_decisions_dir = root / REVIEW_DECISIONS_DIR_REL
    workflow_runs_dir = root / WORKFLOW_RUNS_DIR_REL

    if not writer.exists():
        failures.append(f"sandbox writer command missing: {SANDBOX_WRITER_REL}")
    if not rollback.exists():
        failures.append(f"sandbox rollback command missing: {SANDBOX_ROLLBACK_REL}")
    if not inspect.exists():
        failures.append(f"sandbox receipt inspect command missing: {SANDBOX_INSPECT_REL}")
    if not review_build.exists():
        failures.append(f"sandbox review packet build command missing: {SANDBOX_REVIEW_BUILD_REL}")
    if not review_inspect.exists():
        failures.append(f"sandbox review packet inspect command missing: {SANDBOX_REVIEW_INSPECT_REL}")
    if not review_decision_record.exists():
        failures.append(
            f"sandbox review decision record command missing: {SANDBOX_REVIEW_DECISION_RECORD_REL}"
        )
    if not review_decision_inspect.exists():
        failures.append(
            f"sandbox review decision inspect command missing: {SANDBOX_REVIEW_DECISION_INSPECT_REL}"
        )
    if not workflow_run.exists():
        failures.append(f"sandbox workflow run command missing: {SANDBOX_WORKFLOW_RUN_REL}")
    if not workflow_inspect.exists():
        failures.append(f"sandbox workflow inspect command missing: {SANDBOX_WORKFLOW_INSPECT_REL}")
    if authoritative.exists():
        failures.append(f"authoritative command must remain absent: {AUTHORITATIVE_REL}")
    if not receipt_index.exists():
        failures.append(f"receipt index missing: {RECEIPT_INDEX_REL}")
    if not receipt_index_schema.exists():
        failures.append(f"receipt index schema missing: {RECEIPT_INDEX_SCHEMA_REL}")
    if not review_packet_schema.exists():
        failures.append(f"review packet schema missing: {REVIEW_PACKET_SCHEMA_REL}")
    if not review_decision_schema.exists():
        failures.append(f"review decision schema missing: {REVIEW_DECISION_SCHEMA_REL}")
    if not workflow_run_schema.exists():
        failures.append(f"workflow run schema missing: {WORKFLOW_RUN_SCHEMA_REL}")
    if not review_packets_dir.exists():
        failures.append(f"review packets directory missing: {REVIEW_PACKETS_DIR_REL}")
    if not review_decisions_dir.exists():
        failures.append(f"review decisions directory missing: {REVIEW_DECISIONS_DIR_REL}")
    if not workflow_runs_dir.exists():
        failures.append(f"workflow runs directory missing: {WORKFLOW_RUNS_DIR_REL}")

    if writer.exists():
        writer_text = _read_text(writer)
        for needle in REQUIRED_WRITER_NEEDLES:
            if needle not in writer_text:
                failures.append(f"sandbox writer missing safety needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in writer_text:
                failures.append(f"sandbox writer contains forbidden execution needle: {needle}")
        for needle in FORBIDDEN_CAPABILITY_NEEDLES:
            if needle in writer_text:
                failures.append(f"sandbox writer contains forbidden capability needle: {needle}")

    if rollback.exists():
        rollback_text = _read_text(rollback)
        for needle in REQUIRED_ROLLBACK_NEEDLES:
            if needle not in rollback_text:
                failures.append(f"sandbox rollback missing safety needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in rollback_text:
                failures.append(f"sandbox rollback contains forbidden execution needle: {needle}")
        for needle in FORBIDDEN_CAPABILITY_NEEDLES:
            if needle in rollback_text:
                failures.append(f"sandbox rollback contains forbidden capability needle: {needle}")

    if inspect.exists():
        inspect_text = _read_text(inspect)
        for needle in REQUIRED_INSPECT_NEEDLES:
            if needle not in inspect_text:
                failures.append(f"sandbox inspect command missing required needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in inspect_text:
                failures.append(f"sandbox inspect command contains forbidden execution needle: {needle}")
        for needle in FORBIDDEN_CAPABILITY_NEEDLES:
            if needle in inspect_text:
                failures.append(f"sandbox inspect command contains forbidden capability needle: {needle}")
        for needle in FORBIDDEN_INSPECT_MUTATION_NEEDLES:
            if needle in inspect_text:
                failures.append(f"sandbox inspect command is not read-only; contains mutation needle: {needle}")

    if review_build.exists():
        review_build_text = _read_text(review_build)
        for needle in REQUIRED_REVIEW_BUILD_NEEDLES:
            if needle not in review_build_text:
                failures.append(f"sandbox review build command missing required needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in review_build_text:
                failures.append(f"sandbox review build command contains forbidden execution needle: {needle}")
        # Ensure forbidden operator approvals are explicitly rejected.
        for forbidden_decision in (
            "approve_authoritative_write",
            "approve_asset_id_claim",
            "approve_product_resolution",
            "approve_spawn",
            "approve_publish",
            "approve_o3de_execution",
            "approve_asset_processor_execution",
        ):
            if forbidden_decision not in review_build_text:
                failures.append(
                    f"sandbox review build command must explicitly guard forbidden operator decision: {forbidden_decision}"
                )

    if review_inspect.exists():
        review_inspect_text = _read_text(review_inspect)
        for needle in REQUIRED_REVIEW_INSPECT_NEEDLES:
            if needle not in review_inspect_text:
                failures.append(f"sandbox review inspect command missing required needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in review_inspect_text:
                failures.append(f"sandbox review inspect command contains forbidden execution needle: {needle}")
        for needle in FORBIDDEN_REVIEW_INSPECT_MUTATION_NEEDLES:
            if needle in review_inspect_text:
                failures.append(
                    f"sandbox review inspect command is not read-only; contains mutation needle: {needle}"
                )

    if review_decision_record.exists():
        review_decision_record_text = _read_text(review_decision_record)
        for needle in REQUIRED_REVIEW_DECISION_RECORD_NEEDLES:
            if needle not in review_decision_record_text:
                failures.append(
                    f"sandbox review decision record command missing required needle: {needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in review_decision_record_text:
                failures.append(
                    f"sandbox review decision record command contains forbidden execution needle: {needle}"
                )
        for forbidden_decision in (
            "approve_authoritative_write",
            "approve_asset_id_claim",
            "approve_product_resolution",
            "approve_spawn",
            "approve_publish",
            "approve_o3de_execution",
            "approve_asset_processor_execution",
        ):
            if forbidden_decision not in review_decision_record_text:
                failures.append(
                    "sandbox review decision record command must explicitly guard forbidden "
                    f"decision state: {forbidden_decision}"
                )

    if review_decision_inspect.exists():
        review_decision_inspect_text = _read_text(review_decision_inspect)
        for needle in REQUIRED_REVIEW_DECISION_INSPECT_NEEDLES:
            if needle not in review_decision_inspect_text:
                failures.append(
                    f"sandbox review decision inspect command missing required needle: {needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in review_decision_inspect_text:
                failures.append(
                    f"sandbox review decision inspect command contains forbidden execution needle: {needle}"
                )
        for needle in FORBIDDEN_REVIEW_DECISION_INSPECT_MUTATION_NEEDLES:
            if needle in review_decision_inspect_text:
                failures.append(
                    "sandbox review decision inspect command is not read-only; contains "
                    f"mutation needle: {needle}"
                )

    if workflow_run.exists():
        workflow_run_text = _read_text(workflow_run)
        for needle in REQUIRED_WORKFLOW_RUN_NEEDLES:
            if needle not in workflow_run_text:
                failures.append(f"sandbox workflow run command missing required needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in workflow_run_text:
                failures.append(f"sandbox workflow run command contains forbidden execution needle: {needle}")
        for forbidden_decision in (
            "approve_authoritative_write",
            "approve_asset_id_claim",
            "approve_product_resolution",
            "approve_spawn",
            "approve_publish",
            "approve_o3de_execution",
            "approve_asset_processor_execution",
        ):
            if forbidden_decision in workflow_run_text:
                failures.append(
                    "sandbox workflow run command should not admit forbidden decision state: "
                    f"{forbidden_decision}"
                )
        if "invoke-maxinesandboxrollback.ps1" in workflow_run_text:
            failures.append(
                "sandbox workflow run command must not auto-execute rollback in this slice."
            )

    if workflow_inspect.exists():
        workflow_inspect_text = _read_text(workflow_inspect)
        for needle in REQUIRED_WORKFLOW_INSPECT_NEEDLES:
            if needle not in workflow_inspect_text:
                failures.append(f"sandbox workflow inspect command missing required needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in workflow_inspect_text:
                failures.append(
                    f"sandbox workflow inspect command contains forbidden execution needle: {needle}"
                )
        for needle in FORBIDDEN_WORKFLOW_INSPECT_MUTATION_NEEDLES:
            if needle in workflow_inspect_text:
                failures.append(
                    f"sandbox workflow inspect command is not read-only; contains mutation needle: {needle}"
                )

    if receipt_index.exists():
        try:
            raw = receipt_index.read_text(encoding="utf-8-sig")
            import json

            parsed = json.loads(raw)
            if parsed.get("sandbox_root") != "examples/sandbox":
                failures.append("receipt index sandbox_root must be examples/sandbox.")
            if not isinstance(parsed.get("receipts"), list):
                failures.append("receipt index receipts field must be an array.")
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(f"receipt index is not valid JSON: {exc}")

    return failures
