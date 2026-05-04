#!/usr/bin/env python3
"""Shared sandbox-writer admitted-only safety invariant helpers."""

from __future__ import annotations

import json
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
SANDBOX_EVIDENCE_EXPORT_REL = "scripts/powershell/Invoke-MaxineSandboxEvidenceBundleExport.ps1"
SANDBOX_OPERATOR_SUMMARY_REL = "scripts/powershell/Invoke-MaxineSandboxOperatorSummary.ps1"
PROJECT_INVENTORY_READ_REL = "scripts/powershell/Invoke-MaxineProjectInventoryRead.ps1"
PROJECT_INVENTORY_INSPECT_REL = "scripts/powershell/Invoke-MaxineProjectInventoryInspect.ps1"
AUTHORITATIVE_REL = "scripts/powershell/Invoke-MaxineAuthoritativeResolverWrite.ps1"
RECEIPT_INDEX_REL = "examples/sandbox/receipts/index.json"
RECEIPT_INDEX_SCHEMA_REL = "schemas/maxine_sandbox_receipt_index.schema.json"
REVIEW_PACKET_SCHEMA_REL = "schemas/maxine_sandbox_review_packet.schema.json"
REVIEW_DECISION_SCHEMA_REL = "schemas/maxine_sandbox_review_decision.schema.json"
WORKFLOW_RUN_SCHEMA_REL = "schemas/maxine_sandbox_workflow_run.schema.json"
EVIDENCE_BUNDLE_SCHEMA_REL = "schemas/maxine_sandbox_evidence_bundle.schema.json"
CAPABILITY_MATRIX_SCHEMA_REL = "schemas/maxine_capability_matrix.schema.json"
CAPABILITY_MATRIX_REL = "examples/capabilities/maxine-capability-matrix.json"
REVIEW_PACKETS_DIR_REL = "examples/sandbox/review-packets"
REVIEW_DECISIONS_DIR_REL = "examples/sandbox/review-decisions"
WORKFLOW_RUNS_DIR_REL = "examples/sandbox/workflow-runs"
EVIDENCE_BUNDLES_DIR_REL = "examples/sandbox/evidence-bundles"
OPERATOR_REPORTS_DIR_REL = "examples/sandbox/operator-reports"
PROJECT_INVENTORY_DIR_REL = "examples/sandbox/project-inventory"

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
    SANDBOX_EVIDENCE_EXPORT_REL,
    SANDBOX_OPERATOR_SUMMARY_REL,
    PROJECT_INVENTORY_READ_REL,
    PROJECT_INVENTORY_INSPECT_REL,
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

REQUIRED_EVIDENCE_EXPORT_NEEDLES = [
    "evidence-bundles",
    "source_workflow_run_id",
    "source_receipt_id",
    "included_artifacts",
    "copied_artifact_paths",
    "artifact_sha256",
    "explicit_non_admissions",
    "safety_summary",
    "source-plan-metadata.snapshot.json",
]

REQUIRED_OPERATOR_SUMMARY_NEEDLES = [
    "total_workflow_runs",
    "workflow_status_counts",
    "pending_review_packets",
    "decision_counts",
    "rollback_requested_decisions",
    "accepted_for_sandbox_only_decisions",
    "blocked_reasons",
    "latest_evidence_bundles",
    "next_safest_step",
    "writereport",
    "operator-reports",
]

REQUIRED_PROJECT_INVENTORY_READ_NEEDLES = [
    "project.json",
    "gem_names",
    "known_asset_folders",
    "generated_asset_candidate_folders",
    "sandbox_evidence_folders",
    "o3de_project_path_metadata",
    "configured_non_executed_path_hints",
    "project-inventory",
    "read_only_project_scan",
]

REQUIRED_PROJECT_INVENTORY_INSPECT_NEEDLES = [
    "inventory_count",
    "inventory_id",
    "inventory_path",
    "project_json_existing_count",
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

MUTATION_NEEDLES = [
    "remove-item",
    "set-content",
    "add-content",
    "clear-content",
    "writealltext",
    "new-item",
    "out-file",
]

EXPECTED_CAPABILITY_STATES = {
    "sandbox_resolver_write": "sandbox_only",
    "sandbox_rollback": "sandbox_only",
    "sandbox_receipt_inspect": "read_only",
    "sandbox_review_packet_build": "sandbox_only",
    "sandbox_review_packet_inspect": "read_only",
    "sandbox_review_decision_record": "sandbox_only",
    "sandbox_review_decision_inspect": "read_only",
    "sandbox_workflow_run": "sandbox_only",
    "sandbox_workflow_inspect": "read_only",
    "sandbox_evidence_bundle_export": "sandbox_only",
    "sandbox_operator_summary": "read_only",
    "project_inventory_read": "sandbox_only",
    "project_inventory_inspect": "read_only",
    "authoritative_resolver_write": "forbidden",
    "o3de_editor_execution": "blocked",
    "asset_processor_execution": "blocked",
    "o3de_cli_execution": "blocked",
    "product_resolution": "blocked",
    "asset_id_claims": "blocked",
    "spawning": "blocked",
    "publishing": "blocked",
    "production_path_write": "forbidden",
    "cache_path_write": "forbidden",
    "engine_path_write": "forbidden",
}


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
    evidence_export = root / SANDBOX_EVIDENCE_EXPORT_REL
    operator_summary = root / SANDBOX_OPERATOR_SUMMARY_REL
    project_inventory_read = root / PROJECT_INVENTORY_READ_REL
    project_inventory_inspect = root / PROJECT_INVENTORY_INSPECT_REL
    authoritative = root / AUTHORITATIVE_REL
    receipt_index = root / RECEIPT_INDEX_REL
    receipt_index_schema = root / RECEIPT_INDEX_SCHEMA_REL
    review_packet_schema = root / REVIEW_PACKET_SCHEMA_REL
    review_decision_schema = root / REVIEW_DECISION_SCHEMA_REL
    workflow_run_schema = root / WORKFLOW_RUN_SCHEMA_REL
    evidence_bundle_schema = root / EVIDENCE_BUNDLE_SCHEMA_REL
    capability_matrix_schema = root / CAPABILITY_MATRIX_SCHEMA_REL
    capability_matrix = root / CAPABILITY_MATRIX_REL
    review_packets_dir = root / REVIEW_PACKETS_DIR_REL
    review_decisions_dir = root / REVIEW_DECISIONS_DIR_REL
    workflow_runs_dir = root / WORKFLOW_RUNS_DIR_REL
    evidence_bundles_dir = root / EVIDENCE_BUNDLES_DIR_REL
    operator_reports_dir = root / OPERATOR_REPORTS_DIR_REL
    project_inventory_dir = root / PROJECT_INVENTORY_DIR_REL

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
    if not evidence_export.exists():
        failures.append(f"sandbox evidence bundle export command missing: {SANDBOX_EVIDENCE_EXPORT_REL}")
    if not operator_summary.exists():
        failures.append(f"sandbox operator summary command missing: {SANDBOX_OPERATOR_SUMMARY_REL}")
    if not project_inventory_read.exists():
        failures.append(f"project inventory read command missing: {PROJECT_INVENTORY_READ_REL}")
    if not project_inventory_inspect.exists():
        failures.append(f"project inventory inspect command missing: {PROJECT_INVENTORY_INSPECT_REL}")
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
    if not evidence_bundle_schema.exists():
        failures.append(f"evidence bundle schema missing: {EVIDENCE_BUNDLE_SCHEMA_REL}")
    if not capability_matrix_schema.exists():
        failures.append(f"capability matrix schema missing: {CAPABILITY_MATRIX_SCHEMA_REL}")
    if not capability_matrix.exists():
        failures.append(f"capability matrix missing: {CAPABILITY_MATRIX_REL}")
    if not review_packets_dir.exists():
        failures.append(f"review packets directory missing: {REVIEW_PACKETS_DIR_REL}")
    if not review_decisions_dir.exists():
        failures.append(f"review decisions directory missing: {REVIEW_DECISIONS_DIR_REL}")
    if not workflow_runs_dir.exists():
        failures.append(f"workflow runs directory missing: {WORKFLOW_RUNS_DIR_REL}")
    if not evidence_bundles_dir.exists():
        failures.append(f"evidence bundles directory missing: {EVIDENCE_BUNDLES_DIR_REL}")
    if not operator_reports_dir.exists():
        failures.append(f"operator reports directory missing: {OPERATOR_REPORTS_DIR_REL}")
    if not project_inventory_dir.exists():
        failures.append(f"project inventory directory missing: {PROJECT_INVENTORY_DIR_REL}")

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

    if evidence_export.exists():
        evidence_export_text = _read_text(evidence_export)
        for needle in REQUIRED_EVIDENCE_EXPORT_NEEDLES:
            if needle not in evidence_export_text:
                failures.append(f"sandbox evidence export command missing required needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in evidence_export_text:
                failures.append(
                    f"sandbox evidence export command contains forbidden execution needle: {needle}"
                )
        if "cache" in evidence_export_text and "production_cache_engine_writes" not in evidence_export_text:
            failures.append("sandbox evidence export command must not admit cache-path evidence expansion.")

    if operator_summary.exists():
        operator_summary_text = _read_text(operator_summary)
        for needle in REQUIRED_OPERATOR_SUMMARY_NEEDLES:
            if needle not in operator_summary_text:
                failures.append(f"sandbox operator summary command missing required needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in operator_summary_text:
                failures.append(
                    f"sandbox operator summary command contains forbidden execution needle: {needle}"
                )
        if "if ($writereport)" not in operator_summary_text:
            failures.append("sandbox operator summary command must gate file writes behind -WriteReport.")
        for needle in MUTATION_NEEDLES:
            if needle in operator_summary_text and "writereport" not in operator_summary_text:
                failures.append(
                    "sandbox operator summary command contains mutation behavior without explicit "
                    "-WriteReport gating."
                )

    if project_inventory_read.exists():
        project_inventory_read_text = _read_text(project_inventory_read)
        for needle in REQUIRED_PROJECT_INVENTORY_READ_NEEDLES:
            if needle not in project_inventory_read_text:
                failures.append(f"project inventory read command missing required needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in project_inventory_read_text:
                failures.append(
                    f"project inventory read command contains forbidden execution needle: {needle}"
                )

    if project_inventory_inspect.exists():
        project_inventory_inspect_text = _read_text(project_inventory_inspect)
        for needle in REQUIRED_PROJECT_INVENTORY_INSPECT_NEEDLES:
            if needle not in project_inventory_inspect_text:
                failures.append(f"project inventory inspect command missing required needle: {needle}")
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in project_inventory_inspect_text:
                failures.append(
                    f"project inventory inspect command contains forbidden execution needle: {needle}"
                )
        for needle in MUTATION_NEEDLES:
            if needle in project_inventory_inspect_text:
                failures.append(
                    "project inventory inspect command is not read-only; contains mutation "
                    f"needle: {needle}"
                )

    if receipt_index.exists():
        try:
            raw = receipt_index.read_text(encoding="utf-8-sig")
            parsed = json.loads(raw)
            if parsed.get("sandbox_root") != "examples/sandbox":
                failures.append("receipt index sandbox_root must be examples/sandbox.")
            if not isinstance(parsed.get("receipts"), list):
                failures.append("receipt index receipts field must be an array.")
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(f"receipt index is not valid JSON: {exc}")

    if capability_matrix.exists():
        try:
            matrix = json.loads(capability_matrix.read_text(encoding="utf-8-sig"))
            if matrix.get("schema_version") != "1.0.0":
                failures.append("capability matrix schema_version must be 1.0.0.")

            capabilities = matrix.get("capabilities")
            if not isinstance(capabilities, dict):
                failures.append("capability matrix capabilities field must be an object.")
            else:
                for capability, expected_state in EXPECTED_CAPABILITY_STATES.items():
                    actual = capabilities.get(capability)
                    if actual != expected_state:
                        failures.append(
                            "capability matrix state mismatch for "
                            f"{capability}: expected {expected_state}, found {actual}"
                        )

                for forbidden_capability in (
                    "authoritative_resolver_write",
                    "production_path_write",
                    "cache_path_write",
                    "engine_path_write",
                ):
                    actual_state = capabilities.get(forbidden_capability)
                    if actual_state in {"admitted", "sandbox_only", "read_only", "proof_only"}:
                        failures.append(
                            "capability matrix widened forbidden capability "
                            f"{forbidden_capability} to {actual_state}"
                        )

                for blocked_capability in (
                    "o3de_editor_execution",
                    "asset_processor_execution",
                    "o3de_cli_execution",
                    "product_resolution",
                    "asset_id_claims",
                    "spawning",
                    "publishing",
                ):
                    actual_state = capabilities.get(blocked_capability)
                    if actual_state not in {"blocked", "forbidden"}:
                        failures.append(
                            "capability matrix widened blocked capability "
                            f"{blocked_capability} to {actual_state}"
                        )
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(f"capability matrix is not valid JSON: {exc}")

    return failures
