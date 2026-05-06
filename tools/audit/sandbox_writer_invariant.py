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
ASSET_CANDIDATE_INVENTORY_READ_REL = "scripts/powershell/Invoke-MaxineAssetCandidateInventoryRead.ps1"
ASSET_CANDIDATE_INVENTORY_INSPECT_REL = "scripts/powershell/Invoke-MaxineAssetCandidateInventoryInspect.ps1"
ASSET_CANDIDATE_REVIEW_PACKET_BUILD_REL = (
    "scripts/powershell/Invoke-MaxineAssetCandidateReviewPacketBuild.ps1"
)
ASSET_CANDIDATE_REVIEW_PACKET_INSPECT_REL = (
    "scripts/powershell/Invoke-MaxineAssetCandidateReviewPacketInspect.ps1"
)
ASSET_CANDIDATE_EVIDENCE_BUNDLE_EXPORT_REL = (
    "scripts/powershell/Invoke-MaxineAssetCandidateEvidenceBundleExport.ps1"
)
PRODUCT_RESOLUTION_PROPOSAL_BUILD_REL = (
    "scripts/powershell/Invoke-MaxineProductResolutionProposalBuild.ps1"
)
PRODUCT_RESOLUTION_PROPOSAL_INSPECT_REL = (
    "scripts/powershell/Invoke-MaxineProductResolutionProposalInspect.ps1"
)
PRODUCT_RESOLUTION_PROPOSAL_BUNDLE_EXPORT_REL = (
    "scripts/powershell/Invoke-MaxineProductResolutionProposalBundleExport.ps1"
)
AP_EVIDENCE_IMPORT_REL = "scripts/powershell/Invoke-MaxineApEvidenceImport.ps1"
AP_EVIDENCE_INSPECT_REL = "scripts/powershell/Invoke-MaxineApEvidenceInspect.ps1"
AP_EVIDENCE_BUNDLE_EXPORT_REL = "scripts/powershell/Invoke-MaxineApEvidenceBundleExport.ps1"
AP_EXECUTION_PREFLIGHT_BUILD_REL = (
    "scripts/powershell/Invoke-MaxineApExecutionPreflightBuild.ps1"
)
AP_EXECUTION_PREFLIGHT_INSPECT_REL = (
    "scripts/powershell/Invoke-MaxineApExecutionPreflightInspect.ps1"
)
AP_EXECUTION_PREFLIGHT_BUNDLE_EXPORT_REL = (
    "scripts/powershell/Invoke-MaxineApExecutionPreflightBundleExport.ps1"
)
AP_DIAGNOSTIC_EXECUTION_REL = "scripts/powershell/Invoke-MaxineApDiagnosticExecution.ps1"
AP_DIAGNOSTIC_EXECUTION_INSPECT_REL = (
    "scripts/powershell/Invoke-MaxineApDiagnosticExecutionInspect.ps1"
)
AP_DIAGNOSTIC_EXECUTION_BUNDLE_EXPORT_REL = (
    "scripts/powershell/Invoke-MaxineApDiagnosticExecutionBundleExport.ps1"
)
AP_BINARY_DISCOVERY_READ_REL = "scripts/powershell/Invoke-MaxineApBinaryDiscoveryRead.ps1"
AP_BINARY_DISCOVERY_INSPECT_REL = "scripts/powershell/Invoke-MaxineApBinaryDiscoveryInspect.ps1"
AP_BINARY_PREFLIGHT_BUILD_REL = "scripts/powershell/Invoke-MaxineApBinaryPreflightBuild.ps1"
AP_REAL_BINARY_DIAGNOSTIC_EXECUTION_REL = (
    "scripts/powershell/Invoke-MaxineApRealBinaryDiagnosticExecution.ps1"
)
AP_REAL_BINARY_DIAGNOSTIC_INSPECT_REL = (
    "scripts/powershell/Invoke-MaxineApRealBinaryDiagnosticInspect.ps1"
)
AP_REAL_BINARY_DIAGNOSTIC_BUNDLE_EXPORT_REL = (
    "scripts/powershell/Invoke-MaxineApRealBinaryDiagnosticBundleExport.ps1"
)
AUTHORITATIVE_REL = "scripts/powershell/Invoke-MaxineAuthoritativeResolverWrite.ps1"
RECEIPT_INDEX_REL = "examples/sandbox/receipts/index.json"
RECEIPT_INDEX_SCHEMA_REL = "schemas/maxine_sandbox_receipt_index.schema.json"
REVIEW_PACKET_SCHEMA_REL = "schemas/maxine_sandbox_review_packet.schema.json"
REVIEW_DECISION_SCHEMA_REL = "schemas/maxine_sandbox_review_decision.schema.json"
WORKFLOW_RUN_SCHEMA_REL = "schemas/maxine_sandbox_workflow_run.schema.json"
EVIDENCE_BUNDLE_SCHEMA_REL = "schemas/maxine_sandbox_evidence_bundle.schema.json"
CAPABILITY_MATRIX_SCHEMA_REL = "schemas/maxine_capability_matrix.schema.json"
ASSET_CANDIDATE_SCHEMA_REL = "schemas/maxine_asset_candidate_inventory.schema.json"
ASSET_CANDIDATE_REVIEW_PACKET_SCHEMA_REL = (
    "schemas/maxine_asset_candidate_review_packet.schema.json"
)
ASSET_CANDIDATE_EVIDENCE_BUNDLE_SCHEMA_REL = (
    "schemas/maxine_asset_candidate_evidence_bundle.schema.json"
)
PRODUCT_RESOLUTION_PROPOSAL_SCHEMA_REL = "schemas/maxine_product_resolution_proposal.schema.json"
PRODUCT_RESOLUTION_PROPOSAL_BUNDLE_SCHEMA_REL = (
    "schemas/maxine_product_resolution_proposal_bundle.schema.json"
)
AP_EVIDENCE_IMPORT_SCHEMA_REL = "schemas/maxine_ap_evidence_import.schema.json"
AP_EVIDENCE_BUNDLE_SCHEMA_REL = "schemas/maxine_ap_evidence_bundle.schema.json"
AP_EXECUTION_PREFLIGHT_SCHEMA_REL = "schemas/maxine_ap_execution_preflight.schema.json"
AP_EXECUTION_PREFLIGHT_BUNDLE_SCHEMA_REL = (
    "schemas/maxine_ap_execution_preflight_bundle.schema.json"
)
AP_DIAGNOSTIC_EXECUTION_SCHEMA_REL = "schemas/maxine_ap_diagnostic_execution.schema.json"
AP_DIAGNOSTIC_EXECUTION_BUNDLE_SCHEMA_REL = (
    "schemas/maxine_ap_diagnostic_execution_bundle.schema.json"
)
AP_BINARY_DISCOVERY_SCHEMA_REL = "schemas/maxine_ap_binary_discovery.schema.json"
AP_BINARY_PREFLIGHT_SCHEMA_REL = "schemas/maxine_ap_binary_preflight.schema.json"
AP_REAL_BINARY_DIAGNOSTIC_EXECUTION_SCHEMA_REL = (
    "schemas/maxine_ap_real_binary_diagnostic_execution.schema.json"
)
AP_REAL_BINARY_DIAGNOSTIC_BUNDLE_SCHEMA_REL = (
    "schemas/maxine_ap_real_binary_diagnostic_bundle.schema.json"
)
SOURCE_PRODUCT_EVIDENCE_RESOLVER_SCHEMA_REL = (
    "schemas/maxine_source_product_evidence_resolver_report.schema.json"
)
SOURCE_PRODUCT_EVIDENCE_RESOLVER_VALIDATOR_REL = (
    "tools/source-product-evidence-resolver/validate_source_product_evidence_resolver_report.py"
)
MANIFEST_QC_ATTACHMENT_SCHEMA_REL = "schemas/maxine_manifest_qc_attachment.schema.json"
MANIFEST_QC_ATTACH_TOOL_REL = "tools/manifest-validator/attach_qc_gate.py"
PILOT_RELEASE_CHAIN_VALIDATOR_REL = (
    "tools/release-lane/validate_pilot_release_chain.py"
)
PILOT_RELEASE_CHAIN_FIXTURE_REL = (
    "examples/release-lane-gate-chain/max_biped_v1_release_lane_gate_chain.json"
)
PILOT_RELEASE_CHAIN_MANIFEST_REL = (
    "examples/manifests/example-release-character-pilot-chain.manifest.json"
)
PILOT_RELEASE_CHAIN_BASE_MANIFEST_REL = (
    "examples/manifests/example-release-character-pilot-chain-base.manifest.json"
)
PILOT_RELEASE_CHAIN_RUNNER_REL = (
    "tools/release-lane/run_pilot_release_chain_validation.py"
)
PILOT_RELEASE_CHAIN_CI_PROOF_REL = (
    "tools/release-lane/prove_pilot_release_chain.py"
)
CAPABILITY_MATRIX_REL = "examples/capabilities/maxine-capability-matrix.json"
EXECUTION_ADMISSION_CANDIDATE_MATRIX_REL = (
    "examples/execution-admission/execution_admission_candidate_matrix_v1.json"
)
EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_REL = (
    "examples/execution-admission/execution_admission_preflight_contracts_v1.json"
)
EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_REL = (
    "examples/execution-admission/execution_admission_preflight_proof_packages_v1.json"
)
EXECUTION_ADMISSION_READINESS_ROLLUP_REL = (
    "examples/execution-admission/execution_admission_readiness_rollup_v1.json"
)
RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_REL = (
    "examples/execution-admission/release_candidate_package_publish_dry_run_plan_v1.json"
)
RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_CONTRACT_REL = (
    "examples/execution-admission/release_candidate_package_publish_dry_run_receipt_contract_v1.json"
)
RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_BLOCKED_REL = (
    "examples/execution-admission/release_candidate_package_publish_dry_run_receipt_blocked_v1.json"
)
RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_ADMISSION_BLOCKERS_REL = (
    "examples/execution-admission/release_candidate_package_publish_dry_run_admission_blockers_v1.json"
)
RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_OPERATOR_APPROVAL_PACKET_REL = (
    "examples/execution-admission/release_candidate_package_publish_dry_run_operator_approval_packet_v1.json"
)
REVIEW_PACKETS_DIR_REL = "examples/sandbox/review-packets"
REVIEW_DECISIONS_DIR_REL = "examples/sandbox/review-decisions"
WORKFLOW_RUNS_DIR_REL = "examples/sandbox/workflow-runs"
EVIDENCE_BUNDLES_DIR_REL = "examples/sandbox/evidence-bundles"
OPERATOR_REPORTS_DIR_REL = "examples/sandbox/operator-reports"
PROJECT_INVENTORY_DIR_REL = "examples/sandbox/project-inventory"
ASSET_CANDIDATES_DIR_REL = "examples/sandbox/asset-candidates"
ASSET_CANDIDATE_REVIEW_PACKETS_DIR_REL = "examples/sandbox/asset-candidate-review-packets"
ASSET_CANDIDATE_EVIDENCE_BUNDLES_DIR_REL = "examples/sandbox/asset-candidate-evidence-bundles"
PRODUCT_RESOLUTION_PROPOSALS_DIR_REL = "examples/sandbox/product-resolution-proposals"
PRODUCT_RESOLUTION_PROPOSAL_BUNDLES_DIR_REL = (
    "examples/sandbox/product-resolution-proposal-bundles"
)
AP_EVIDENCE_IMPORTS_DIR_REL = "examples/sandbox/ap-evidence-imports"
AP_EVIDENCE_BUNDLES_DIR_REL = "examples/sandbox/ap-evidence-bundles"
AP_EXECUTION_PREFLIGHTS_DIR_REL = "examples/sandbox/ap-execution-preflights"
AP_EXECUTION_PREFLIGHT_BUNDLES_DIR_REL = (
    "examples/sandbox/ap-execution-preflight-bundles"
)
AP_DIAGNOSTIC_EXECUTIONS_DIR_REL = "examples/sandbox/ap-diagnostic-executions"
AP_DIAGNOSTIC_EXECUTION_BUNDLES_DIR_REL = (
    "examples/sandbox/ap-diagnostic-execution-bundles"
)
AP_BINARY_DISCOVERY_DIR_REL = "examples/sandbox/ap-binary-discovery"
AP_BINARY_PREFLIGHTS_DIR_REL = "examples/sandbox/ap-binary-preflights"
AP_REAL_BINARY_DIAGNOSTIC_EXECUTIONS_DIR_REL = (
    "examples/sandbox/ap-real-binary-diagnostic-executions"
)
AP_REAL_BINARY_DIAGNOSTIC_BUNDLES_DIR_REL = (
    "examples/sandbox/ap-real-binary-diagnostic-bundles"
)

NOOP_RECEIPT_CANDIDATE_ID = "release_candidate_package_receipt_noop_v1"
EXPECTED_REAL_EXECUTION_CANDIDATE_IDS = (
    "dcc_conform_execution_v1",
    "asset_processor_batch_execution_v1",
    "max_biped_skeleton_validation_execution_v1",
    "material_uv_qc_execution_v1",
    "animation_smoke_execution_v1",
    "visual_evidence_capture_execution_v1",
)
EXPECTED_PUBLICATION_CANDIDATE_IDS = ("release_candidate_package_publication_v1",)
EXPECTED_DRY_RUN_CANDIDATE_IDS = ("release_candidate_package_publish_dry_run_v1",)
EXPECTED_EXECUTION_ADMISSION_CANDIDATE_IDS = (
    NOOP_RECEIPT_CANDIDATE_ID,
    *EXPECTED_REAL_EXECUTION_CANDIDATE_IDS,
    *EXPECTED_PUBLICATION_CANDIDATE_IDS,
    *EXPECTED_DRY_RUN_CANDIDATE_IDS,
)
EXPECTED_ROLLUP_NEXT_SLICE_ID = "candidate_specific_dry_run_planning_v1"
EXPECTED_ROLLUP_NEXT_SLICE_CANDIDATE_ID = (
    "release_candidate_package_publish_dry_run_v1"
)
EXPECTED_DRY_RUN_PLAN_APPROVAL_PHRASE = (
    "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
)
EXPECTED_DRY_RUN_RECEIPT_TYPE = "release_candidate_package_publish_dry_run_receipt_v1"
EXPECTED_DRY_RUN_RECEIPT_CONTRACT_STATUS = "static_contract_valid_blocked"
EXPECTED_DRY_RUN_ADMISSION_BLOCKERS_STATUS = "static_checklist_valid_blocked"
EXPECTED_DRY_RUN_OPERATOR_APPROVAL_PACKET_STATUS = "static_template_valid_blocked"
REQUIRED_DRY_RUN_ADMISSION_BLOCKERS = (
    "missing_approval_decision",
    "dry_run_not_admitted",
    "dry_run_not_executed",
    "receipt_not_issued",
    "rollback_cleanup_evidence_missing",
    "publication_surfaces_blocked_by_policy",
)
REQUIRED_PREFLIGHT_BLOCKED_SURFACES = {
    "o3de_execution",
    "editor_runtime_execution",
    "asset_processor_execution",
    "blender_dcc_execution",
    "profiler_benchmark_execution",
    "live_screenshot_capture",
    "spawn_publish",
    "cache_live_db_access",
    "authoritative_source_uuid_claims",
    "authoritative_asset_id_claims",
    "authoritative_product_id_claims",
    "production_write",
    "engine_write",
}

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
    ASSET_CANDIDATE_INVENTORY_READ_REL,
    ASSET_CANDIDATE_INVENTORY_INSPECT_REL,
    ASSET_CANDIDATE_REVIEW_PACKET_BUILD_REL,
    ASSET_CANDIDATE_REVIEW_PACKET_INSPECT_REL,
    ASSET_CANDIDATE_EVIDENCE_BUNDLE_EXPORT_REL,
    PRODUCT_RESOLUTION_PROPOSAL_BUILD_REL,
    PRODUCT_RESOLUTION_PROPOSAL_INSPECT_REL,
    PRODUCT_RESOLUTION_PROPOSAL_BUNDLE_EXPORT_REL,
    AP_EVIDENCE_IMPORT_REL,
    AP_EVIDENCE_INSPECT_REL,
    AP_EVIDENCE_BUNDLE_EXPORT_REL,
    AP_EXECUTION_PREFLIGHT_BUILD_REL,
    AP_EXECUTION_PREFLIGHT_INSPECT_REL,
    AP_EXECUTION_PREFLIGHT_BUNDLE_EXPORT_REL,
    AP_DIAGNOSTIC_EXECUTION_REL,
    AP_DIAGNOSTIC_EXECUTION_INSPECT_REL,
    AP_DIAGNOSTIC_EXECUTION_BUNDLE_EXPORT_REL,
    AP_BINARY_DISCOVERY_READ_REL,
    AP_BINARY_DISCOVERY_INSPECT_REL,
    AP_BINARY_PREFLIGHT_BUILD_REL,
    AP_REAL_BINARY_DIAGNOSTIC_EXECUTION_REL,
    AP_REAL_BINARY_DIAGNOSTIC_INSPECT_REL,
    AP_REAL_BINARY_DIAGNOSTIC_BUNDLE_EXPORT_REL,
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

REQUIRED_ASSET_CANDIDATE_INVENTORY_READ_NEEDLES = [
    "source_project_inventory_id",
    "generated_candidate_folders",
    "source_asset_candidates",
    "material_texture_candidates",
    "metadata_provenance_candidates",
    "linked_sandbox_evidence",
    "explicit_non_admissions",
    "output_path",
    "asset-candidates",
    "cache is not an allowed scan root",
]

REQUIRED_ASSET_CANDIDATE_INVENTORY_INSPECT_NEEDLES = [
    "inventory_count",
    "inventory_id",
    "source_project_inventory_id",
    "candidate_count",
    "showcandidates",
]

REQUIRED_ASSET_CANDIDATE_REVIEW_PACKET_BUILD_NEEDLES = [
    "asset-candidate-review-packets",
    "source_inventory_id",
    "candidate_id",
    "operator_decision_state",
    "pending_review",
    "accepted_for_sandbox_only",
    "rejected",
    "needs_more_evidence",
    "request_candidate_cleanup",
    "recommended_next_step",
    "inspect_candidate",
    "bundle_evidence",
    "request_more_evidence",
    "propose_product_resolution_later",
    "reject_candidate",
    "request_sandbox_cleanup",
    "explicit_non_admissions",
]

REQUIRED_ASSET_CANDIDATE_REVIEW_PACKET_INSPECT_NEEDLES = [
    "review_packet_count",
    "review_packet_id",
    "source_inventory_id",
    "candidate_id",
    "showevidencelinks",
]

REQUIRED_ASSET_CANDIDATE_EVIDENCE_BUNDLE_EXPORT_NEEDLES = [
    "asset-candidate-evidence-bundles",
    "source_inventory_id",
    "source_review_packet_id",
    "candidate_id",
    "included_artifacts",
    "copied_artifact_paths",
    "artifact_sha256",
    "linked-sandbox-evidence.snapshot.json",
    "copies json evidence snapshots only",
]

REQUIRED_PRODUCT_RESOLUTION_PROPOSAL_BUILD_NEEDLES = [
    "product-resolution-proposals",
    "proposal_only",
    "product_ids_claimed",
    "asset_ids_claimed",
    "source_uuids_claimed",
    "asset_processor_execution_admitted",
    "o3de_execution_admitted",
    "cache_access_admitted",
    "spawn_admitted",
    "publish_admitted",
    "expected_product_classes",
    "likely_asset_pipeline_requirements",
    "required_next_evidence",
    "blocked_missing_evidence",
    "ready_for_read_only_ap_evidence_import",
    "rejected",
]

REQUIRED_PRODUCT_RESOLUTION_PROPOSAL_INSPECT_NEEDLES = [
    "proposal_count",
    "proposal_id",
    "showrequirements",
    "showblockingreasons",
]

REQUIRED_PRODUCT_RESOLUTION_PROPOSAL_BUNDLE_EXPORT_NEEDLES = [
    "product-resolution-proposal-bundles",
    "source_proposal_id",
    "source_review_packet_id",
    "source_inventory_id",
    "source_project_inventory_id",
    "candidate_id",
    "included_artifacts",
    "copied_artifact_paths",
    "artifact_sha256",
    "copies json evidence snapshots only",
]

REQUIRED_AP_EVIDENCE_IMPORT_NEEDLES = [
    "ap-evidence-imports",
    "read_only",
    "imported_log_paths",
    "imported_snapshot_metadata_paths",
    "observed_product_like_mentions",
    "observed_warning_mentions",
    "observed_error_mentions",
    "asset_processor_execution_admitted",
    "o3de_execution_admitted",
    "cache_access_admitted",
    "live_database_access_admitted",
    "product_ids_claimed",
    "asset_ids_claimed",
    "source_uuids_claimed",
    "product_resolution_claimed",
    "spawn_admitted",
    "publish_admitted",
    "live cache directory evidence inputs are blocked",
    "live asset database evidence inputs are blocked",
    "only .json, .txt, and .log are allowed",
]

REQUIRED_AP_EVIDENCE_INSPECT_NEEDLES = [
    "evidence_import_count",
    "ap_evidence_import_id",
    "showwarnings",
    "showerrors",
    "showobservedmentions",
]

REQUIRED_AP_EVIDENCE_BUNDLE_EXPORT_NEEDLES = [
    "ap-evidence-bundles",
    "source_ap_evidence_import_id",
    "source_proposal_id",
    "source_project_inventory_id",
    "source_asset_candidate_inventory_id",
    "included_artifacts",
    "copied_artifact_paths",
    "artifact_sha256",
    "copies json snapshots only",
    "does not copy logs directly",
]

REQUIRED_AP_EXECUTION_PREFLIGHT_BUILD_NEEDLES = [
    "ap-execution-preflights",
    "proposed_ap_command_display",
    "required_manual_confirmation",
    "local_only",
    "execution_admitted",
    "ready_for_future_execution_request",
    "blocked_missing_evidence",
    "blocked_safety_boundary",
    "ready_for_future_execution_request",
    "rejected",
    "ap_batch_display_only",
    "preflight_display_only",
    "no_execution",
    "contains parent traversal and is blocked",
]

REQUIRED_AP_EXECUTION_PREFLIGHT_INSPECT_NEEDLES = [
    "preflight_count",
    "preflight_id",
    "showblockingreasons",
    "showwarnings",
]

REQUIRED_AP_EXECUTION_PREFLIGHT_BUNDLE_EXPORT_NEEDLES = [
    "ap-execution-preflight-bundles",
    "source_preflight_id",
    "source_ap_evidence_import_id",
    "source_proposal_id",
    "source_project_inventory_id",
    "included_artifacts",
    "copied_artifact_paths",
    "artifact_sha256",
    "copies json snapshots only",
]

REQUIRED_AP_DIAGNOSTIC_EXECUTION_NEEDLES = [
    "ap-diagnostic-executions",
    "approvelocaldiagnosticexecution",
    "diagnosticonly",
    "usemockdiagnosticcommand",
    "simulatetimeout",
    "command_allowlisted",
    "command_executed",
    "execution_status",
    "timed_out",
    "blocked",
    "succeeded",
    "failed",
    "source_preflight_id",
    "stdout_sha256",
    "stderr_sha256",
    "product_ids_claimed = $false",
    "asset_ids_claimed = $false",
    "source_uuids_claimed = $false",
    "product_resolution_claimed = $false",
    "cache_access_admitted = $false",
    "live_database_access_admitted = $false",
    "spawn_admitted = $false",
    "publish_admitted = $false",
    "command source is arbitrary user text and is blocked",
    "contains shell operators/pipelines/redirection/traversal",
]

REQUIRED_AP_DIAGNOSTIC_EXECUTION_INSPECT_NEEDLES = [
    "diagnostic_execution_count",
    "diagnostic_execution_id",
    "showoutputrefs",
    "showblockedreason",
]

REQUIRED_AP_DIAGNOSTIC_EXECUTION_BUNDLE_EXPORT_NEEDLES = [
    "ap-diagnostic-execution-bundles",
    "source_diagnostic_execution_id",
    "source_preflight_id",
    "included_artifacts",
    "copied_artifact_paths",
    "artifact_sha256",
    ".txt",
    "json",
]

REQUIRED_AP_BINARY_DISCOVERY_READ_NEEDLES = [
    "ap-binary-discovery",
    "candidate_paths",
    "normalized_candidate_paths",
    "existing_candidates",
    "rejected_candidates",
    "path_source",
    "read_only = $true",
    "execution_admitted = $false",
    "cache_access_admitted = $false",
    "live_database_access_admitted = $false",
    "contains parent traversal and is blocked",
    "cache paths are blocked as binary candidates",
    "assetdb.sqlite paths are blocked as binary candidates",
]

REQUIRED_AP_BINARY_DISCOVERY_INSPECT_NEEDLES = [
    "discovery_count",
    "discovery_id",
    "showcandidates",
    "showrejected",
]

REQUIRED_AP_BINARY_PREFLIGHT_BUILD_NEEDLES = [
    "ap-binary-preflights",
    "source_discovery_id",
    "source_ap_execution_preflight_id",
    "selected_binary_path",
    "binary_kind",
    "binary_exists",
    "binary_allowed_for_future_execution_request",
    "execution_admitted = $false",
    "required_manual_confirmation = $true",
    "local_only = $true",
    "blocked_missing_binary",
    "blocked_unsupported_binary",
    "ready_for_future_real_ap_execution_request",
    "rejected",
    "source ap execution preflight readiness_status is not ready_for_future_execution_request",
]

REQUIRED_AP_REAL_BINARY_DIAGNOSTIC_EXECUTION_NEEDLES = [
    "ap-real-binary-diagnostic-executions",
    "approverealbinarydiagnosticexecution",
    "realbinarydiagnosticonly",
    "diagnosticargument",
    "usesimulatedcommandmode",
    "simulatetimeout",
    "command_allowlisted",
    "command_executed",
    "execution_status",
    "timed_out",
    "blocked",
    "succeeded",
    "failed",
    "source_ap_binary_preflight_id",
    "stdout_sha256",
    "stderr_sha256",
    "product_ids_claimed = $false",
    "asset_ids_claimed = $false",
    "source_uuids_claimed = $false",
    "product_resolution_claimed = $false",
    "cache_access_admitted = $false",
    "live_database_access_admitted = $false",
    "spawn_admitted = $false",
    "publish_admitted = $false",
    "binary_kind",
    "assetprocessorbatch",
    "assetprocessor",
    "diagnostic_argument '$diagnosticargument' is not allowlisted",
    "contains shell operators/pipelines/redirection/traversal",
    "ready_for_future_real_ap_execution_request",
]

REQUIRED_AP_REAL_BINARY_DIAGNOSTIC_INSPECT_NEEDLES = [
    "execution_count",
    "real_binary_diagnostic_execution_id",
    "executionid",
    "executionpath",
    "showoutputrefs",
    "showblockedreason",
]

REQUIRED_AP_REAL_BINARY_DIAGNOSTIC_BUNDLE_EXPORT_NEEDLES = [
    "ap-real-binary-diagnostic-bundles",
    "source_execution_id",
    "source_ap_binary_preflight_id",
    "included_artifacts",
    "copied_artifact_paths",
    "artifact_sha256",
    ".txt",
    "json",
    "does not copy ap binaries",
]

REQUIRED_SOURCE_PRODUCT_EVIDENCE_RESOLVER_VALIDATOR_NEEDLES = [
    "source_product_evidence_resolver_v1",
    "source_product_evidence_resolver_v1_report",
    "expected_products",
    "observed_products",
    "source_uuid_claim_status",
    "asset_id_claim_status",
    "product_id_claim_status",
    "cache_access_status",
    "live_db_access_status",
    "future_admitted",
    "qc.gates[]",
    "qc.checks[]",
    "--allow-warn",
]

REQUIRED_MANIFEST_QC_ATTACH_TOOL_NEEDLES = [
    "manifest_attachment",
    "qc.gates[]",
    "qc.checks[]",
    "allow-duplicate-check-id",
    "atomic_write_json",
    "os.replace(",
    "inside repository root",
    "duplicate check_id",
]

REQUIRED_PILOT_RELEASE_CHAIN_VALIDATOR_NEEDLES = [
    "pilot_release_chain_v1",
    "max_biped_v1_skeleton_contract",
    "dcc_conform_v1",
    "source_product_evidence_resolver_v1",
    "material_uv_qc_v1",
    "animation_smoke_v1",
    "release_publication_execution_handoff_v1",
    "release_publication_execution_admission_request_packet_v1",
    "release_publication_gate_set_v1",
    "qc.gates[]",
    "qc.checks[]",
    "--allow-warn",
]

REQUIRED_PILOT_RELEASE_CHAIN_RUNNER_NEEDLES = [
    "run_pilot_release_chain_validation.py",
    "example-release-character-pilot-chain-base.manifest.json",
    "max_biped_v1_skeleton_contract",
    "dcc_conform_v1",
    "source_product_evidence_resolver_v1",
    "material_uv_qc_v1",
    "animation_smoke_v1",
    "release_publication_execution_handoff_v1",
    "release_publication_execution_admission_request_packet_v1",
    "release_publication_gate_set_v1",
    "pilot_release_chain_v1",
    "attach_qc_gate.py",
    "qc.gates[]",
    "qc.checks[]",
]

REQUIRED_PILOT_RELEASE_CHAIN_CI_PROOF_NEEDLES = [
    "prove_pilot_release_chain.py",
    "run_pilot_release_chain_validation.py",
    "pilot_release_chain_ci_proof_v1",
    "pilot_chain_status",
    "--strict-chain",
    "qc.gates[]",
    "qc.checks[]",
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
    "project_inventory_read": "read_only",
    "project_inventory_inspect": "read_only",
    "asset_candidate_inventory_read": "read_only",
    "asset_candidate_inventory_inspect": "read_only",
    "asset_candidate_review_packet_build": "sandbox_only",
    "asset_candidate_review_packet_inspect": "read_only",
    "asset_candidate_evidence_bundle_export": "sandbox_only",
    "product_resolution_proposal_build": "sandbox_only",
    "product_resolution_proposal_inspect": "read_only",
    "product_resolution_proposal_bundle_export": "sandbox_only",
    "ap_evidence_import": "read_only",
    "ap_evidence_inspect": "read_only",
    "ap_evidence_bundle_export": "sandbox_only",
    "ap_execution_preflight_build": "sandbox_only",
    "ap_execution_preflight_inspect": "read_only",
    "ap_execution_preflight_bundle_export": "sandbox_only",
    "ap_diagnostic_execution": "sandbox_only",
    "ap_binary_discovery_read": "read_only",
    "ap_binary_discovery_inspect": "read_only",
    "ap_binary_preflight_build": "sandbox_only",
    "ap_real_binary_diagnostic_execution": "sandbox_only",
    "source_product_evidence_resolver_validate": "read_only",
    "manifest_qc_attachment_pipeline": "sandbox_only",
    "pilot_release_chain_validation": "read_only",
    "pilot_release_chain_attachment_run": "sandbox_only",
    "release_publication_gate_set_report_validation": "proof_only",
    "real_asset_processor_execution": "blocked",
    "authoritative_resolver_write": "forbidden",
    "o3de_editor_execution": "blocked",
    "asset_processor_execution": "blocked",
    "o3de_cli_execution": "blocked",
    "product_resolution": "blocked",
    "product_id_claims": "blocked",
    "asset_id_claims": "blocked",
    "source_uuid_claims": "blocked",
    "cache_read": "blocked",
    "live_asset_database_read": "blocked",
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
    asset_candidate_inventory_read = root / ASSET_CANDIDATE_INVENTORY_READ_REL
    asset_candidate_inventory_inspect = root / ASSET_CANDIDATE_INVENTORY_INSPECT_REL
    asset_candidate_review_packet_build = root / ASSET_CANDIDATE_REVIEW_PACKET_BUILD_REL
    asset_candidate_review_packet_inspect = root / ASSET_CANDIDATE_REVIEW_PACKET_INSPECT_REL
    asset_candidate_evidence_bundle_export = root / ASSET_CANDIDATE_EVIDENCE_BUNDLE_EXPORT_REL
    product_resolution_proposal_build = root / PRODUCT_RESOLUTION_PROPOSAL_BUILD_REL
    product_resolution_proposal_inspect = root / PRODUCT_RESOLUTION_PROPOSAL_INSPECT_REL
    product_resolution_proposal_bundle_export = root / PRODUCT_RESOLUTION_PROPOSAL_BUNDLE_EXPORT_REL
    ap_evidence_import = root / AP_EVIDENCE_IMPORT_REL
    ap_evidence_inspect = root / AP_EVIDENCE_INSPECT_REL
    ap_evidence_bundle_export = root / AP_EVIDENCE_BUNDLE_EXPORT_REL
    ap_execution_preflight_build = root / AP_EXECUTION_PREFLIGHT_BUILD_REL
    ap_execution_preflight_inspect = root / AP_EXECUTION_PREFLIGHT_INSPECT_REL
    ap_execution_preflight_bundle_export = root / AP_EXECUTION_PREFLIGHT_BUNDLE_EXPORT_REL
    ap_diagnostic_execution = root / AP_DIAGNOSTIC_EXECUTION_REL
    ap_diagnostic_execution_inspect = root / AP_DIAGNOSTIC_EXECUTION_INSPECT_REL
    ap_diagnostic_execution_bundle_export = root / AP_DIAGNOSTIC_EXECUTION_BUNDLE_EXPORT_REL
    ap_binary_discovery_read = root / AP_BINARY_DISCOVERY_READ_REL
    ap_binary_discovery_inspect = root / AP_BINARY_DISCOVERY_INSPECT_REL
    ap_binary_preflight_build = root / AP_BINARY_PREFLIGHT_BUILD_REL
    ap_real_binary_diagnostic_execution = root / AP_REAL_BINARY_DIAGNOSTIC_EXECUTION_REL
    ap_real_binary_diagnostic_inspect = root / AP_REAL_BINARY_DIAGNOSTIC_INSPECT_REL
    ap_real_binary_diagnostic_bundle_export = (
        root / AP_REAL_BINARY_DIAGNOSTIC_BUNDLE_EXPORT_REL
    )
    authoritative = root / AUTHORITATIVE_REL
    receipt_index = root / RECEIPT_INDEX_REL
    receipt_index_schema = root / RECEIPT_INDEX_SCHEMA_REL
    review_packet_schema = root / REVIEW_PACKET_SCHEMA_REL
    review_decision_schema = root / REVIEW_DECISION_SCHEMA_REL
    workflow_run_schema = root / WORKFLOW_RUN_SCHEMA_REL
    evidence_bundle_schema = root / EVIDENCE_BUNDLE_SCHEMA_REL
    capability_matrix_schema = root / CAPABILITY_MATRIX_SCHEMA_REL
    asset_candidate_schema = root / ASSET_CANDIDATE_SCHEMA_REL
    asset_candidate_review_packet_schema = root / ASSET_CANDIDATE_REVIEW_PACKET_SCHEMA_REL
    asset_candidate_evidence_bundle_schema = root / ASSET_CANDIDATE_EVIDENCE_BUNDLE_SCHEMA_REL
    product_resolution_proposal_schema = root / PRODUCT_RESOLUTION_PROPOSAL_SCHEMA_REL
    product_resolution_proposal_bundle_schema = root / PRODUCT_RESOLUTION_PROPOSAL_BUNDLE_SCHEMA_REL
    ap_evidence_import_schema = root / AP_EVIDENCE_IMPORT_SCHEMA_REL
    ap_evidence_bundle_schema = root / AP_EVIDENCE_BUNDLE_SCHEMA_REL
    ap_execution_preflight_schema = root / AP_EXECUTION_PREFLIGHT_SCHEMA_REL
    ap_execution_preflight_bundle_schema = root / AP_EXECUTION_PREFLIGHT_BUNDLE_SCHEMA_REL
    ap_diagnostic_execution_schema = root / AP_DIAGNOSTIC_EXECUTION_SCHEMA_REL
    ap_diagnostic_execution_bundle_schema = root / AP_DIAGNOSTIC_EXECUTION_BUNDLE_SCHEMA_REL
    ap_binary_discovery_schema = root / AP_BINARY_DISCOVERY_SCHEMA_REL
    ap_binary_preflight_schema = root / AP_BINARY_PREFLIGHT_SCHEMA_REL
    ap_real_binary_diagnostic_execution_schema = (
        root / AP_REAL_BINARY_DIAGNOSTIC_EXECUTION_SCHEMA_REL
    )
    ap_real_binary_diagnostic_bundle_schema = (
        root / AP_REAL_BINARY_DIAGNOSTIC_BUNDLE_SCHEMA_REL
    )
    source_product_evidence_resolver_schema = (
        root / SOURCE_PRODUCT_EVIDENCE_RESOLVER_SCHEMA_REL
    )
    source_product_evidence_resolver_validator = (
        root / SOURCE_PRODUCT_EVIDENCE_RESOLVER_VALIDATOR_REL
    )
    manifest_qc_attachment_schema = root / MANIFEST_QC_ATTACHMENT_SCHEMA_REL
    manifest_qc_attach_tool = root / MANIFEST_QC_ATTACH_TOOL_REL
    pilot_release_chain_validator = root / PILOT_RELEASE_CHAIN_VALIDATOR_REL
    pilot_release_chain_fixture = root / PILOT_RELEASE_CHAIN_FIXTURE_REL
    pilot_release_chain_manifest = root / PILOT_RELEASE_CHAIN_MANIFEST_REL
    pilot_release_chain_base_manifest = root / PILOT_RELEASE_CHAIN_BASE_MANIFEST_REL
    pilot_release_chain_runner = root / PILOT_RELEASE_CHAIN_RUNNER_REL
    pilot_release_chain_ci_proof = root / PILOT_RELEASE_CHAIN_CI_PROOF_REL
    capability_matrix = root / CAPABILITY_MATRIX_REL
    execution_admission_candidate_matrix = root / EXECUTION_ADMISSION_CANDIDATE_MATRIX_REL
    execution_admission_preflight_contracts = (
        root / EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_REL
    )
    execution_admission_preflight_proof_packages = (
        root / EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_REL
    )
    execution_admission_readiness_rollup = (
        root / EXECUTION_ADMISSION_READINESS_ROLLUP_REL
    )
    release_candidate_publication_dry_run_plan = (
        root / RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_REL
    )
    release_candidate_publication_dry_run_receipt_contract = (
        root / RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_CONTRACT_REL
    )
    release_candidate_publication_dry_run_receipt_blocked = (
        root / RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_BLOCKED_REL
    )
    release_candidate_publication_dry_run_admission_blockers = (
        root / RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_ADMISSION_BLOCKERS_REL
    )
    release_candidate_publication_dry_run_operator_approval_packet = (
        root / RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_OPERATOR_APPROVAL_PACKET_REL
    )
    review_packets_dir = root / REVIEW_PACKETS_DIR_REL
    review_decisions_dir = root / REVIEW_DECISIONS_DIR_REL
    workflow_runs_dir = root / WORKFLOW_RUNS_DIR_REL
    evidence_bundles_dir = root / EVIDENCE_BUNDLES_DIR_REL
    operator_reports_dir = root / OPERATOR_REPORTS_DIR_REL
    project_inventory_dir = root / PROJECT_INVENTORY_DIR_REL
    asset_candidates_dir = root / ASSET_CANDIDATES_DIR_REL
    asset_candidate_review_packets_dir = root / ASSET_CANDIDATE_REVIEW_PACKETS_DIR_REL
    asset_candidate_evidence_bundles_dir = root / ASSET_CANDIDATE_EVIDENCE_BUNDLES_DIR_REL
    product_resolution_proposals_dir = root / PRODUCT_RESOLUTION_PROPOSALS_DIR_REL
    product_resolution_proposal_bundles_dir = root / PRODUCT_RESOLUTION_PROPOSAL_BUNDLES_DIR_REL
    ap_evidence_imports_dir = root / AP_EVIDENCE_IMPORTS_DIR_REL
    ap_evidence_bundles_dir = root / AP_EVIDENCE_BUNDLES_DIR_REL
    ap_execution_preflights_dir = root / AP_EXECUTION_PREFLIGHTS_DIR_REL
    ap_execution_preflight_bundles_dir = root / AP_EXECUTION_PREFLIGHT_BUNDLES_DIR_REL
    ap_diagnostic_executions_dir = root / AP_DIAGNOSTIC_EXECUTIONS_DIR_REL
    ap_diagnostic_execution_bundles_dir = root / AP_DIAGNOSTIC_EXECUTION_BUNDLES_DIR_REL
    ap_binary_discovery_dir = root / AP_BINARY_DISCOVERY_DIR_REL
    ap_binary_preflights_dir = root / AP_BINARY_PREFLIGHTS_DIR_REL
    ap_real_binary_diagnostic_executions_dir = (
        root / AP_REAL_BINARY_DIAGNOSTIC_EXECUTIONS_DIR_REL
    )
    ap_real_binary_diagnostic_bundles_dir = (
        root / AP_REAL_BINARY_DIAGNOSTIC_BUNDLES_DIR_REL
    )

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
    if not asset_candidate_inventory_read.exists():
        failures.append(
            "asset candidate inventory read command missing: "
            f"{ASSET_CANDIDATE_INVENTORY_READ_REL}"
        )
    if not asset_candidate_inventory_inspect.exists():
        failures.append(
            "asset candidate inventory inspect command missing: "
            f"{ASSET_CANDIDATE_INVENTORY_INSPECT_REL}"
        )
    if not asset_candidate_review_packet_build.exists():
        failures.append(
            "asset candidate review packet build command missing: "
            f"{ASSET_CANDIDATE_REVIEW_PACKET_BUILD_REL}"
        )
    if not asset_candidate_review_packet_inspect.exists():
        failures.append(
            "asset candidate review packet inspect command missing: "
            f"{ASSET_CANDIDATE_REVIEW_PACKET_INSPECT_REL}"
        )
    if not asset_candidate_evidence_bundle_export.exists():
        failures.append(
            "asset candidate evidence bundle export command missing: "
            f"{ASSET_CANDIDATE_EVIDENCE_BUNDLE_EXPORT_REL}"
        )
    if not product_resolution_proposal_build.exists():
        failures.append(
            "product resolution proposal build command missing: "
            f"{PRODUCT_RESOLUTION_PROPOSAL_BUILD_REL}"
        )
    if not product_resolution_proposal_inspect.exists():
        failures.append(
            "product resolution proposal inspect command missing: "
            f"{PRODUCT_RESOLUTION_PROPOSAL_INSPECT_REL}"
        )
    if not product_resolution_proposal_bundle_export.exists():
        failures.append(
            "product resolution proposal bundle export command missing: "
            f"{PRODUCT_RESOLUTION_PROPOSAL_BUNDLE_EXPORT_REL}"
        )
    if not ap_evidence_import.exists():
        failures.append(f"AP evidence import command missing: {AP_EVIDENCE_IMPORT_REL}")
    if not ap_evidence_inspect.exists():
        failures.append(f"AP evidence inspect command missing: {AP_EVIDENCE_INSPECT_REL}")
    if not ap_evidence_bundle_export.exists():
        failures.append(
            "AP evidence bundle export command missing: "
            f"{AP_EVIDENCE_BUNDLE_EXPORT_REL}"
        )
    if not ap_execution_preflight_build.exists():
        failures.append(
            "AP execution preflight build command missing: "
            f"{AP_EXECUTION_PREFLIGHT_BUILD_REL}"
        )
    if not ap_execution_preflight_inspect.exists():
        failures.append(
            "AP execution preflight inspect command missing: "
            f"{AP_EXECUTION_PREFLIGHT_INSPECT_REL}"
        )
    if not ap_execution_preflight_bundle_export.exists():
        failures.append(
            "AP execution preflight bundle export command missing: "
            f"{AP_EXECUTION_PREFLIGHT_BUNDLE_EXPORT_REL}"
        )
    if not ap_diagnostic_execution.exists():
        failures.append(
            "AP diagnostic execution command missing: "
            f"{AP_DIAGNOSTIC_EXECUTION_REL}"
        )
    if not ap_diagnostic_execution_inspect.exists():
        failures.append(
            "AP diagnostic execution inspect command missing: "
            f"{AP_DIAGNOSTIC_EXECUTION_INSPECT_REL}"
        )
    if not ap_diagnostic_execution_bundle_export.exists():
        failures.append(
            "AP diagnostic execution bundle export command missing: "
            f"{AP_DIAGNOSTIC_EXECUTION_BUNDLE_EXPORT_REL}"
        )
    if not ap_binary_discovery_read.exists():
        failures.append(
            "AP binary discovery read command missing: "
            f"{AP_BINARY_DISCOVERY_READ_REL}"
        )
    if not ap_binary_discovery_inspect.exists():
        failures.append(
            "AP binary discovery inspect command missing: "
            f"{AP_BINARY_DISCOVERY_INSPECT_REL}"
        )
    if not ap_binary_preflight_build.exists():
        failures.append(
            "AP binary preflight build command missing: "
            f"{AP_BINARY_PREFLIGHT_BUILD_REL}"
        )
    if not ap_real_binary_diagnostic_execution.exists():
        failures.append(
            "AP real binary diagnostic execution command missing: "
            f"{AP_REAL_BINARY_DIAGNOSTIC_EXECUTION_REL}"
        )
    if not ap_real_binary_diagnostic_inspect.exists():
        failures.append(
            "AP real binary diagnostic inspect command missing: "
            f"{AP_REAL_BINARY_DIAGNOSTIC_INSPECT_REL}"
        )
    if not ap_real_binary_diagnostic_bundle_export.exists():
        failures.append(
            "AP real binary diagnostic bundle export command missing: "
            f"{AP_REAL_BINARY_DIAGNOSTIC_BUNDLE_EXPORT_REL}"
        )
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
    if not asset_candidate_schema.exists():
        failures.append(f"asset candidate inventory schema missing: {ASSET_CANDIDATE_SCHEMA_REL}")
    if not asset_candidate_review_packet_schema.exists():
        failures.append(
            "asset candidate review packet schema missing: "
            f"{ASSET_CANDIDATE_REVIEW_PACKET_SCHEMA_REL}"
        )
    if not asset_candidate_evidence_bundle_schema.exists():
        failures.append(
            "asset candidate evidence bundle schema missing: "
            f"{ASSET_CANDIDATE_EVIDENCE_BUNDLE_SCHEMA_REL}"
        )
    if not product_resolution_proposal_schema.exists():
        failures.append(
            "product resolution proposal schema missing: "
            f"{PRODUCT_RESOLUTION_PROPOSAL_SCHEMA_REL}"
        )
    if not product_resolution_proposal_bundle_schema.exists():
        failures.append(
            "product resolution proposal bundle schema missing: "
            f"{PRODUCT_RESOLUTION_PROPOSAL_BUNDLE_SCHEMA_REL}"
        )
    if not ap_evidence_import_schema.exists():
        failures.append(f"AP evidence import schema missing: {AP_EVIDENCE_IMPORT_SCHEMA_REL}")
    if not ap_evidence_bundle_schema.exists():
        failures.append(f"AP evidence bundle schema missing: {AP_EVIDENCE_BUNDLE_SCHEMA_REL}")
    if not ap_execution_preflight_schema.exists():
        failures.append(
            "AP execution preflight schema missing: "
            f"{AP_EXECUTION_PREFLIGHT_SCHEMA_REL}"
        )
    if not ap_execution_preflight_bundle_schema.exists():
        failures.append(
            "AP execution preflight bundle schema missing: "
            f"{AP_EXECUTION_PREFLIGHT_BUNDLE_SCHEMA_REL}"
        )
    if not ap_diagnostic_execution_schema.exists():
        failures.append(
            "AP diagnostic execution schema missing: "
            f"{AP_DIAGNOSTIC_EXECUTION_SCHEMA_REL}"
        )
    if not ap_diagnostic_execution_bundle_schema.exists():
        failures.append(
            "AP diagnostic execution bundle schema missing: "
            f"{AP_DIAGNOSTIC_EXECUTION_BUNDLE_SCHEMA_REL}"
        )
    if not ap_binary_discovery_schema.exists():
        failures.append(
            "AP binary discovery schema missing: "
            f"{AP_BINARY_DISCOVERY_SCHEMA_REL}"
        )
    if not ap_binary_preflight_schema.exists():
        failures.append(
            "AP binary preflight schema missing: "
            f"{AP_BINARY_PREFLIGHT_SCHEMA_REL}"
        )
    if not ap_real_binary_diagnostic_execution_schema.exists():
        failures.append(
            "AP real binary diagnostic execution schema missing: "
            f"{AP_REAL_BINARY_DIAGNOSTIC_EXECUTION_SCHEMA_REL}"
        )
    if not ap_real_binary_diagnostic_bundle_schema.exists():
        failures.append(
            "AP real binary diagnostic bundle schema missing: "
            f"{AP_REAL_BINARY_DIAGNOSTIC_BUNDLE_SCHEMA_REL}"
        )
    if not source_product_evidence_resolver_schema.exists():
        failures.append(
            "Source product evidence resolver schema missing: "
            f"{SOURCE_PRODUCT_EVIDENCE_RESOLVER_SCHEMA_REL}"
        )
    if not source_product_evidence_resolver_validator.exists():
        failures.append(
            "Source product evidence resolver validator missing: "
            f"{SOURCE_PRODUCT_EVIDENCE_RESOLVER_VALIDATOR_REL}"
        )
    if not manifest_qc_attachment_schema.exists():
        failures.append(
            "Manifest QC attachment schema missing: "
            f"{MANIFEST_QC_ATTACHMENT_SCHEMA_REL}"
        )
    if not manifest_qc_attach_tool.exists():
        failures.append(
            "Manifest QC attachment tool missing: "
            f"{MANIFEST_QC_ATTACH_TOOL_REL}"
        )
    if not pilot_release_chain_validator.exists():
        failures.append(
            "Pilot release chain validator missing: "
            f"{PILOT_RELEASE_CHAIN_VALIDATOR_REL}"
        )
    if not pilot_release_chain_fixture.exists():
        failures.append(
            "Pilot release chain fixture missing: "
            f"{PILOT_RELEASE_CHAIN_FIXTURE_REL}"
        )
    if not pilot_release_chain_manifest.exists():
        failures.append(
            "Pilot release chain manifest fixture missing: "
            f"{PILOT_RELEASE_CHAIN_MANIFEST_REL}"
        )
    if not pilot_release_chain_base_manifest.exists():
        failures.append(
            "Pilot release chain base manifest fixture missing: "
            f"{PILOT_RELEASE_CHAIN_BASE_MANIFEST_REL}"
        )
    if not pilot_release_chain_runner.exists():
        failures.append(
            "Pilot release chain runner missing: "
            f"{PILOT_RELEASE_CHAIN_RUNNER_REL}"
        )
    if not pilot_release_chain_ci_proof.exists():
        failures.append(
            "Pilot release chain CI proof command missing: "
            f"{PILOT_RELEASE_CHAIN_CI_PROOF_REL}"
        )
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
    if not asset_candidates_dir.exists():
        failures.append(f"asset candidates directory missing: {ASSET_CANDIDATES_DIR_REL}")
    if not asset_candidate_review_packets_dir.exists():
        failures.append(
            "asset candidate review packets directory missing: "
            f"{ASSET_CANDIDATE_REVIEW_PACKETS_DIR_REL}"
        )
    if not asset_candidate_evidence_bundles_dir.exists():
        failures.append(
            "asset candidate evidence bundles directory missing: "
            f"{ASSET_CANDIDATE_EVIDENCE_BUNDLES_DIR_REL}"
        )
    if not product_resolution_proposals_dir.exists():
        failures.append(
            "product resolution proposals directory missing: "
            f"{PRODUCT_RESOLUTION_PROPOSALS_DIR_REL}"
        )
    if not product_resolution_proposal_bundles_dir.exists():
        failures.append(
            "product resolution proposal bundles directory missing: "
            f"{PRODUCT_RESOLUTION_PROPOSAL_BUNDLES_DIR_REL}"
        )
    if not ap_evidence_imports_dir.exists():
        failures.append(
            f"AP evidence imports directory missing: {AP_EVIDENCE_IMPORTS_DIR_REL}"
        )
    if not ap_evidence_bundles_dir.exists():
        failures.append(
            f"AP evidence bundles directory missing: {AP_EVIDENCE_BUNDLES_DIR_REL}"
        )
    if not ap_execution_preflights_dir.exists():
        failures.append(
            "AP execution preflights directory missing: "
            f"{AP_EXECUTION_PREFLIGHTS_DIR_REL}"
        )
    if not ap_execution_preflight_bundles_dir.exists():
        failures.append(
            "AP execution preflight bundles directory missing: "
            f"{AP_EXECUTION_PREFLIGHT_BUNDLES_DIR_REL}"
        )
    if not ap_diagnostic_executions_dir.exists():
        failures.append(
            "AP diagnostic executions directory missing: "
            f"{AP_DIAGNOSTIC_EXECUTIONS_DIR_REL}"
        )
    if not ap_diagnostic_execution_bundles_dir.exists():
        failures.append(
            "AP diagnostic execution bundles directory missing: "
            f"{AP_DIAGNOSTIC_EXECUTION_BUNDLES_DIR_REL}"
        )
    if not ap_binary_discovery_dir.exists():
        failures.append(
            "AP binary discovery directory missing: "
            f"{AP_BINARY_DISCOVERY_DIR_REL}"
        )
    if not ap_binary_preflights_dir.exists():
        failures.append(
            "AP binary preflights directory missing: "
            f"{AP_BINARY_PREFLIGHTS_DIR_REL}"
        )
    if not ap_real_binary_diagnostic_executions_dir.exists():
        failures.append(
            "AP real binary diagnostic executions directory missing: "
            f"{AP_REAL_BINARY_DIAGNOSTIC_EXECUTIONS_DIR_REL}"
        )
    if not ap_real_binary_diagnostic_bundles_dir.exists():
        failures.append(
            "AP real binary diagnostic bundles directory missing: "
            f"{AP_REAL_BINARY_DIAGNOSTIC_BUNDLES_DIR_REL}"
        )

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

    if asset_candidate_inventory_read.exists():
        asset_candidate_inventory_read_text = _read_text(asset_candidate_inventory_read)
        for needle in REQUIRED_ASSET_CANDIDATE_INVENTORY_READ_NEEDLES:
            if needle not in asset_candidate_inventory_read_text:
                failures.append(
                    "asset candidate inventory read command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in asset_candidate_inventory_read_text:
                failures.append(
                    "asset candidate inventory read command contains forbidden execution needle: "
                    f"{needle}"
                )

    if asset_candidate_inventory_inspect.exists():
        asset_candidate_inventory_inspect_text = _read_text(asset_candidate_inventory_inspect)
        for needle in REQUIRED_ASSET_CANDIDATE_INVENTORY_INSPECT_NEEDLES:
            if needle not in asset_candidate_inventory_inspect_text:
                failures.append(
                    "asset candidate inventory inspect command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in asset_candidate_inventory_inspect_text:
                failures.append(
                    "asset candidate inventory inspect command contains forbidden execution needle: "
                    f"{needle}"
                )
        for needle in MUTATION_NEEDLES:
            if needle in asset_candidate_inventory_inspect_text:
                failures.append(
                    "asset candidate inventory inspect command is not read-only; contains mutation "
                    f"needle: {needle}"
                )

    if asset_candidate_review_packet_build.exists():
        asset_candidate_review_packet_build_text = _read_text(asset_candidate_review_packet_build)
        for needle in REQUIRED_ASSET_CANDIDATE_REVIEW_PACKET_BUILD_NEEDLES:
            if needle not in asset_candidate_review_packet_build_text:
                failures.append(
                    "asset candidate review packet build command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in asset_candidate_review_packet_build_text:
                failures.append(
                    "asset candidate review packet build command contains forbidden execution "
                    f"needle: {needle}"
                )
        for forbidden_decision in (
            "approve_product_resolution",
            "approve_asset_id_claim",
            "approve_spawn",
            "approve_publish",
            "approve_o3de_execution",
            "approve_asset_processor_execution",
            "approve_authoritative_write",
        ):
            if forbidden_decision not in asset_candidate_review_packet_build_text:
                failures.append(
                    "asset candidate review packet build command must explicitly guard forbidden "
                    f"operator decision state: {forbidden_decision}"
                )
        for forbidden_next_step in (
            "run_asset_processor",
            "launch_editor",
            "spawn_entity",
            "publish_asset",
            "claim_asset_id",
        ):
            if forbidden_next_step not in asset_candidate_review_packet_build_text:
                failures.append(
                    "asset candidate review packet build command must explicitly guard forbidden "
                    f"recommended next step: {forbidden_next_step}"
                )

    if asset_candidate_review_packet_inspect.exists():
        asset_candidate_review_packet_inspect_text = _read_text(asset_candidate_review_packet_inspect)
        for needle in REQUIRED_ASSET_CANDIDATE_REVIEW_PACKET_INSPECT_NEEDLES:
            if needle not in asset_candidate_review_packet_inspect_text:
                failures.append(
                    "asset candidate review packet inspect command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in asset_candidate_review_packet_inspect_text:
                failures.append(
                    "asset candidate review packet inspect command contains forbidden execution "
                    f"needle: {needle}"
                )
        for needle in MUTATION_NEEDLES:
            if needle in asset_candidate_review_packet_inspect_text:
                failures.append(
                    "asset candidate review packet inspect command is not read-only; contains "
                    f"mutation needle: {needle}"
                )

    if asset_candidate_evidence_bundle_export.exists():
        asset_candidate_evidence_bundle_export_text = _read_text(
            asset_candidate_evidence_bundle_export
        )
        for needle in REQUIRED_ASSET_CANDIDATE_EVIDENCE_BUNDLE_EXPORT_NEEDLES:
            if needle not in asset_candidate_evidence_bundle_export_text:
                failures.append(
                    "asset candidate evidence bundle export command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in asset_candidate_evidence_bundle_export_text:
                failures.append(
                    "asset candidate evidence bundle export command contains forbidden execution "
                    f"needle: {needle}"
                )
        for forbidden_copy in (
            ".fbx",
            ".gltf",
            ".glb",
            ".obj",
            ".blend",
            ".png",
            ".jpg",
            ".jpeg",
            ".tiff",
            ".exr",
            ".bin",
            ".dll",
            ".pdb",
        ):
            if f'"{forbidden_copy}"' in asset_candidate_evidence_bundle_export_text:
                failures.append(
                    "asset candidate evidence bundle export command should not hardcode copying "
                    f"binary/source artifact extension: {forbidden_copy}"
                )

    if product_resolution_proposal_build.exists():
        product_resolution_proposal_build_text = _read_text(product_resolution_proposal_build)
        for needle in REQUIRED_PRODUCT_RESOLUTION_PROPOSAL_BUILD_NEEDLES:
            if needle not in product_resolution_proposal_build_text:
                failures.append(
                    "product resolution proposal build command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in product_resolution_proposal_build_text:
                failures.append(
                    "product resolution proposal build command contains forbidden execution "
                    f"needle: {needle}"
                )
        for forbidden_status in (
            "resolved",
            "asset_id_resolved",
            "product_id_resolved",
            "ap_executed",
            "spawned",
            "published",
            "production_approved",
        ):
            if forbidden_status not in product_resolution_proposal_build_text:
                failures.append(
                    "product resolution proposal build command must explicitly guard forbidden "
                    f"proposal_status: {forbidden_status}"
                )
        for forbidden_phrase in (
            "resolved_product_id",
            "resolved_asset_id",
            "source_uuid",
            "asset_processor_executed",
            "cache_verified",
            "spawned_entity",
            "published_asset",
        ):
            if forbidden_phrase not in product_resolution_proposal_build_text:
                failures.append(
                    "product resolution proposal build command must explicitly guard forbidden "
                    f"proposal language: {forbidden_phrase}"
                )

    if product_resolution_proposal_inspect.exists():
        product_resolution_proposal_inspect_text = _read_text(product_resolution_proposal_inspect)
        for needle in REQUIRED_PRODUCT_RESOLUTION_PROPOSAL_INSPECT_NEEDLES:
            if needle not in product_resolution_proposal_inspect_text:
                failures.append(
                    "product resolution proposal inspect command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in product_resolution_proposal_inspect_text:
                failures.append(
                    "product resolution proposal inspect command contains forbidden execution "
                    f"needle: {needle}"
                )
        for needle in MUTATION_NEEDLES:
            if needle in product_resolution_proposal_inspect_text:
                failures.append(
                    "product resolution proposal inspect command is not read-only; contains "
                    f"mutation needle: {needle}"
                )

    if product_resolution_proposal_bundle_export.exists():
        product_resolution_proposal_bundle_export_text = _read_text(
            product_resolution_proposal_bundle_export
        )
        for needle in REQUIRED_PRODUCT_RESOLUTION_PROPOSAL_BUNDLE_EXPORT_NEEDLES:
            if needle not in product_resolution_proposal_bundle_export_text:
                failures.append(
                    "product resolution proposal bundle export command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in product_resolution_proposal_bundle_export_text:
                failures.append(
                    "product resolution proposal bundle export command contains forbidden "
                    f"execution needle: {needle}"
                )
        for forbidden_copy in (
            ".fbx",
            ".gltf",
            ".glb",
            ".obj",
            ".blend",
            ".png",
            ".jpg",
            ".jpeg",
            ".tiff",
            ".exr",
            ".bin",
            ".dll",
            ".pdb",
            "cache",
        ):
            if f'"{forbidden_copy}"' in product_resolution_proposal_bundle_export_text:
                failures.append(
                    "product resolution proposal bundle export command should not hardcode "
                    f"copying binary/source/runtime/cache artifact token: {forbidden_copy}"
                )

    if ap_evidence_import.exists():
        ap_evidence_import_text = _read_text(ap_evidence_import)
        for needle in REQUIRED_AP_EVIDENCE_IMPORT_NEEDLES:
            if needle not in ap_evidence_import_text:
                failures.append(
                    "AP evidence import command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in ap_evidence_import_text:
                failures.append(
                    "AP evidence import command contains forbidden execution needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "launch assetprocessor",
            "assetprocessorbatch.exe",
            "invoke-expression",
            "start-process",
        ):
            if forbidden_phrase in ap_evidence_import_text:
                failures.append(
                    "AP evidence import command must remain read-only and non-executing; "
                    f"forbidden phrase present: {forbidden_phrase}"
                )
        for forbidden_admission in (
            "product_resolution_claimed = $true",
            "product_ids_claimed = $true",
            "asset_ids_claimed = $true",
            "source_uuids_claimed = $true",
            "cache_access_admitted = $true",
            "live_database_access_admitted = $true",
            "asset_processor_execution_admitted = $true",
            "o3de_execution_admitted = $true",
            "spawn_admitted = $true",
            "publish_admitted = $true",
        ):
            if forbidden_admission in ap_evidence_import_text:
                failures.append(
                    "AP evidence import command widens forbidden admission: "
                    f"{forbidden_admission}"
                )

    if ap_evidence_inspect.exists():
        ap_evidence_inspect_text = _read_text(ap_evidence_inspect)
        for needle in REQUIRED_AP_EVIDENCE_INSPECT_NEEDLES:
            if needle not in ap_evidence_inspect_text:
                failures.append(
                    "AP evidence inspect command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in ap_evidence_inspect_text:
                failures.append(
                    "AP evidence inspect command contains forbidden execution needle: "
                    f"{needle}"
                )
        for needle in MUTATION_NEEDLES:
            if needle in ap_evidence_inspect_text:
                failures.append(
                    "AP evidence inspect command is not read-only; contains mutation needle: "
                    f"{needle}"
                )

    if ap_evidence_bundle_export.exists():
        ap_evidence_bundle_export_text = _read_text(ap_evidence_bundle_export)
        for needle in REQUIRED_AP_EVIDENCE_BUNDLE_EXPORT_NEEDLES:
            if needle not in ap_evidence_bundle_export_text:
                failures.append(
                    "AP evidence bundle export command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in ap_evidence_bundle_export_text:
                failures.append(
                    "AP evidence bundle export command contains forbidden execution needle: "
                    f"{needle}"
                )
        for forbidden_copy in (
            ".fbx",
            ".gltf",
            ".glb",
            ".obj",
            ".blend",
            ".png",
            ".jpg",
            ".jpeg",
            ".tiff",
            ".exr",
            ".bin",
            ".dll",
            ".pdb",
            ".sqlite",
            "assetdb.sqlite",
            "cache",
        ):
            if f'"{forbidden_copy}"' in ap_evidence_bundle_export_text:
                failures.append(
                    "AP evidence bundle export command should not hardcode copying "
                    f"binary/source/runtime/cache/database token: {forbidden_copy}"
                )

    if ap_execution_preflight_build.exists():
        ap_execution_preflight_build_text = _read_text(ap_execution_preflight_build)
        for needle in REQUIRED_AP_EXECUTION_PREFLIGHT_BUILD_NEEDLES:
            if needle not in ap_execution_preflight_build_text:
                failures.append(
                    "AP execution preflight build command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in ap_execution_preflight_build_text:
                failures.append(
                    "AP execution preflight build command contains forbidden execution needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "start-process",
            "invoke-expression",
            "invoke-maxineauthoritativeresolverwrite.ps1",
        ):
            if forbidden_phrase in ap_execution_preflight_build_text:
                failures.append(
                    "AP execution preflight build command must remain non-executing; "
                    f"forbidden phrase present: {forbidden_phrase}"
                )
        for forbidden_status in (
            "executed",
            "ap_executed",
            "product_resolved",
            "asset_id_resolved",
            "spawned",
            "published",
        ):
            if forbidden_status not in ap_execution_preflight_build_text:
                failures.append(
                    "AP execution preflight build command must explicitly guard forbidden "
                    f"readiness_status: {forbidden_status}"
                )
        for forbidden_admission in (
            "execution_admitted = $true",
            "required_manual_confirmation = $false",
            "local_only = $false",
        ):
            if forbidden_admission in ap_execution_preflight_build_text:
                failures.append(
                    "AP execution preflight build command widens forbidden admission: "
                    f"{forbidden_admission}"
                )

    if ap_execution_preflight_inspect.exists():
        ap_execution_preflight_inspect_text = _read_text(ap_execution_preflight_inspect)
        for needle in REQUIRED_AP_EXECUTION_PREFLIGHT_INSPECT_NEEDLES:
            if needle not in ap_execution_preflight_inspect_text:
                failures.append(
                    "AP execution preflight inspect command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in ap_execution_preflight_inspect_text:
                failures.append(
                    "AP execution preflight inspect command contains forbidden execution needle: "
                    f"{needle}"
                )
        for needle in MUTATION_NEEDLES:
            if needle in ap_execution_preflight_inspect_text:
                failures.append(
                    "AP execution preflight inspect command is not read-only; contains mutation "
                    f"needle: {needle}"
                )

    if ap_execution_preflight_bundle_export.exists():
        ap_execution_preflight_bundle_export_text = _read_text(
            ap_execution_preflight_bundle_export
        )
        for needle in REQUIRED_AP_EXECUTION_PREFLIGHT_BUNDLE_EXPORT_NEEDLES:
            if needle not in ap_execution_preflight_bundle_export_text:
                failures.append(
                    "AP execution preflight bundle export command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in ap_execution_preflight_bundle_export_text:
                failures.append(
                    "AP execution preflight bundle export command contains forbidden execution needle: "
                    f"{needle}"
                )
        for forbidden_copy in (
            ".fbx",
            ".gltf",
            ".glb",
            ".obj",
            ".blend",
            ".png",
            ".jpg",
            ".jpeg",
            ".tiff",
            ".exr",
            ".bin",
            ".dll",
            ".pdb",
            ".sqlite",
            "assetdb.sqlite",
            "cache",
        ):
            if f'"{forbidden_copy}"' in ap_execution_preflight_bundle_export_text:
                failures.append(
                    "AP execution preflight bundle export command should not hardcode copying "
                    f"binary/source/runtime/cache/database token: {forbidden_copy}"
                )

    if ap_diagnostic_execution.exists():
        ap_diagnostic_execution_text = _read_text(ap_diagnostic_execution)
        for needle in REQUIRED_AP_DIAGNOSTIC_EXECUTION_NEEDLES:
            if needle not in ap_diagnostic_execution_text:
                failures.append(
                    "AP diagnostic execution command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in ap_diagnostic_execution_text:
                failures.append(
                    "AP diagnostic execution command contains forbidden execution needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "assetprocessor.exe",
            "assetprocessorbatch.exe",
            "editor.exe",
            "o3de.exe",
            "invoke-expression",
            "start-process",
        ):
            if forbidden_phrase in ap_diagnostic_execution_text:
                failures.append(
                    "AP diagnostic execution command must remain mock/allowlist bounded; "
                    f"forbidden phrase present: {forbidden_phrase}"
                )
        for forbidden_admission in (
            "product_ids_claimed = $true",
            "asset_ids_claimed = $true",
            "source_uuids_claimed = $true",
            "product_resolution_claimed = $true",
            "cache_access_admitted = $true",
            "live_database_access_admitted = $true",
            "spawn_admitted = $true",
            "publish_admitted = $true",
        ):
            if forbidden_admission in ap_diagnostic_execution_text:
                failures.append(
                    "AP diagnostic execution command widens forbidden admission: "
                    f"{forbidden_admission}"
                )
        if "-command" in ap_diagnostic_execution_text and "valuefromremainingarguments" in ap_diagnostic_execution_text:
            failures.append(
                "AP diagnostic execution command must not accept arbitrary command text arguments."
            )

    if ap_diagnostic_execution_inspect.exists():
        ap_diagnostic_execution_inspect_text = _read_text(ap_diagnostic_execution_inspect)
        for needle in REQUIRED_AP_DIAGNOSTIC_EXECUTION_INSPECT_NEEDLES:
            if needle not in ap_diagnostic_execution_inspect_text:
                failures.append(
                    "AP diagnostic execution inspect command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in ap_diagnostic_execution_inspect_text:
                failures.append(
                    "AP diagnostic execution inspect command contains forbidden execution needle: "
                    f"{needle}"
                )
        for needle in MUTATION_NEEDLES:
            if needle in ap_diagnostic_execution_inspect_text:
                failures.append(
                    "AP diagnostic execution inspect command is not read-only; contains mutation "
                    f"needle: {needle}"
                )

    if ap_diagnostic_execution_bundle_export.exists():
        ap_diagnostic_execution_bundle_export_text = _read_text(
            ap_diagnostic_execution_bundle_export
        )
        for needle in REQUIRED_AP_DIAGNOSTIC_EXECUTION_BUNDLE_EXPORT_NEEDLES:
            if needle not in ap_diagnostic_execution_bundle_export_text:
                failures.append(
                    "AP diagnostic execution bundle export command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in ap_diagnostic_execution_bundle_export_text:
                failures.append(
                    "AP diagnostic execution bundle export command contains forbidden execution "
                    f"needle: {needle}"
                )
        for forbidden_copy in (
            ".fbx",
            ".gltf",
            ".glb",
            ".obj",
            ".blend",
            ".png",
            ".jpg",
            ".jpeg",
            ".tiff",
            ".exr",
            ".bin",
            ".dll",
            ".pdb",
            ".sqlite",
            "assetdb.sqlite",
            "cache",
        ):
            if f'"{forbidden_copy}"' in ap_diagnostic_execution_bundle_export_text:
                failures.append(
                    "AP diagnostic execution bundle export command should not hardcode copying "
                    f"binary/source/runtime/cache/database token: {forbidden_copy}"
                )

    if ap_binary_discovery_read.exists():
        ap_binary_discovery_read_text = _read_text(ap_binary_discovery_read)
        for needle in REQUIRED_AP_BINARY_DISCOVERY_READ_NEEDLES:
            if needle not in ap_binary_discovery_read_text:
                failures.append(
                    "AP binary discovery read command missing required needle: "
                    f"{needle}"
                )
        for needle in (
            "o3de editor",
            "asset processor",
            "o3de.exe",
            "editor.exe",
            "invoke-maxineauthoritativeresolverwrite.ps1",
        ):
            if needle in ap_binary_discovery_read_text:
                failures.append(
                    "AP binary discovery read command contains forbidden execution needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "-recurse",
            "start-process",
            "invoke-expression",
            "editor.exe",
            "o3de.exe",
        ):
            if forbidden_phrase in ap_binary_discovery_read_text:
                failures.append(
                    "AP binary discovery read command must remain non-executing and "
                    f"non-recursive; forbidden phrase present: {forbidden_phrase}"
                )
        for forbidden_admission in (
            "execution_admitted = $true",
            "cache_access_admitted = $true",
            "live_database_access_admitted = $true",
        ):
            if forbidden_admission in ap_binary_discovery_read_text:
                failures.append(
                    "AP binary discovery read command widens forbidden admission: "
                    f"{forbidden_admission}"
                )

    if ap_binary_discovery_inspect.exists():
        ap_binary_discovery_inspect_text = _read_text(ap_binary_discovery_inspect)
        for needle in REQUIRED_AP_BINARY_DISCOVERY_INSPECT_NEEDLES:
            if needle not in ap_binary_discovery_inspect_text:
                failures.append(
                    "AP binary discovery inspect command missing required needle: "
                    f"{needle}"
                )
        for needle in FORBIDDEN_EXECUTION_NEEDLES:
            if needle in ap_binary_discovery_inspect_text:
                failures.append(
                    "AP binary discovery inspect command contains forbidden execution needle: "
                    f"{needle}"
                )
        for needle in MUTATION_NEEDLES:
            if needle in ap_binary_discovery_inspect_text:
                failures.append(
                    "AP binary discovery inspect command is not read-only; contains mutation "
                    f"needle: {needle}"
                )

    if ap_binary_preflight_build.exists():
        ap_binary_preflight_build_text = _read_text(ap_binary_preflight_build)
        for needle in REQUIRED_AP_BINARY_PREFLIGHT_BUILD_NEEDLES:
            if needle not in ap_binary_preflight_build_text:
                failures.append(
                    "AP binary preflight build command missing required needle: "
                    f"{needle}"
                )
        for needle in (
            "o3de editor",
            "asset processor",
            "o3de.exe",
            "editor.exe",
            "invoke-maxineauthoritativeresolverwrite.ps1",
        ):
            if needle in ap_binary_preflight_build_text:
                failures.append(
                    "AP binary preflight build command contains forbidden execution needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "-recurse",
            "start-process",
            "invoke-expression",
            "editor.exe",
            "o3de.exe",
        ):
            if forbidden_phrase in ap_binary_preflight_build_text:
                failures.append(
                    "AP binary preflight build command must remain non-executing and "
                    f"non-recursive; forbidden phrase present: {forbidden_phrase}"
                )
        for forbidden_admission in (
            "execution_admitted = $true",
            "required_manual_confirmation = $false",
            "local_only = $false",
            "binary_allowed_for_future_execution_request = $true",
        ):
            if forbidden_admission in ap_binary_preflight_build_text:
                failures.append(
                    "AP binary preflight build command widens forbidden admission: "
                    f"{forbidden_admission}"
                )

    if ap_real_binary_diagnostic_execution.exists():
        ap_real_binary_diagnostic_execution_text = _read_text(
            ap_real_binary_diagnostic_execution
        )
        for needle in REQUIRED_AP_REAL_BINARY_DIAGNOSTIC_EXECUTION_NEEDLES:
            if needle not in ap_real_binary_diagnostic_execution_text:
                failures.append(
                    "AP real binary diagnostic execution command missing required needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "o3de.exe",
            "editor.exe",
            "invoke-expression",
            "start-process",
            "invoke-maxineauthoritativeresolverwrite.ps1",
        ):
            if forbidden_phrase in ap_real_binary_diagnostic_execution_text:
                failures.append(
                    "AP real binary diagnostic execution command contains forbidden phrase: "
                    f"{forbidden_phrase}"
                )
        for allowed_arg in ("--help", "-help", "/?", "--version", "-version"):
            if allowed_arg not in ap_real_binary_diagnostic_execution_text:
                failures.append(
                    "AP real binary diagnostic execution command must explicitly include "
                    f"allowlisted argument token: {allowed_arg}"
                )
        for forbidden_admission in (
            "product_ids_claimed = $true",
            "asset_ids_claimed = $true",
            "source_uuids_claimed = $true",
            "product_resolution_claimed = $true",
            "cache_access_admitted = $true",
            "live_database_access_admitted = $true",
            "spawn_admitted = $true",
            "publish_admitted = $true",
            "local_only = $false",
            "execution_admitted = $true",
            "required_manual_confirmation = $false",
            "binary_allowed_for_future_execution_request = $false",
            "binary_exists = $false",
        ):
            if forbidden_admission in ap_real_binary_diagnostic_execution_text:
                failures.append(
                    "AP real binary diagnostic execution command widens forbidden admission: "
                    f"{forbidden_admission}"
                )
        if (
            "-command" in ap_real_binary_diagnostic_execution_text
            and "valuefromremainingarguments" in ap_real_binary_diagnostic_execution_text
        ):
            failures.append(
                "AP real binary diagnostic execution command must not accept arbitrary "
                "command text arguments."
            )

    if ap_real_binary_diagnostic_inspect.exists():
        ap_real_binary_diagnostic_inspect_text = _read_text(
            ap_real_binary_diagnostic_inspect
        )
        for needle in REQUIRED_AP_REAL_BINARY_DIAGNOSTIC_INSPECT_NEEDLES:
            if needle not in ap_real_binary_diagnostic_inspect_text:
                failures.append(
                    "AP real binary diagnostic inspect command missing required needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "o3de.exe",
            "editor.exe",
            "invoke-expression",
            "start-process",
            "invoke-maxineauthoritativeresolverwrite.ps1",
        ):
            if forbidden_phrase in ap_real_binary_diagnostic_inspect_text:
                failures.append(
                    "AP real binary diagnostic inspect command contains forbidden phrase: "
                    f"{forbidden_phrase}"
                )
        for needle in MUTATION_NEEDLES:
            if needle in ap_real_binary_diagnostic_inspect_text:
                failures.append(
                    "AP real binary diagnostic inspect command is not read-only; contains "
                    f"mutation needle: {needle}"
                )

    if ap_real_binary_diagnostic_bundle_export.exists():
        ap_real_binary_diagnostic_bundle_export_text = _read_text(
            ap_real_binary_diagnostic_bundle_export
        )
        for needle in REQUIRED_AP_REAL_BINARY_DIAGNOSTIC_BUNDLE_EXPORT_NEEDLES:
            if needle not in ap_real_binary_diagnostic_bundle_export_text:
                failures.append(
                    "AP real binary diagnostic bundle export command missing required needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "o3de.exe",
            "editor.exe",
            "invoke-expression",
            "start-process",
            "invoke-maxineauthoritativeresolverwrite.ps1",
        ):
            if forbidden_phrase in ap_real_binary_diagnostic_bundle_export_text:
                failures.append(
                    "AP real binary diagnostic bundle export command contains forbidden phrase: "
                    f"{forbidden_phrase}"
                )
        for forbidden_copy in (
            ".fbx",
            ".gltf",
            ".glb",
            ".obj",
            ".blend",
            ".png",
            ".jpg",
            ".jpeg",
            ".tiff",
            ".exr",
            ".bin",
            ".dll",
            ".pdb",
            ".sqlite",
            ".exe",
            "assetdb.sqlite",
            "cache",
        ):
            if f'"{forbidden_copy}"' in ap_real_binary_diagnostic_bundle_export_text:
                failures.append(
                    "AP real binary diagnostic bundle export command should not hardcode "
                    "copying binary/source/runtime/cache/database token: "
                    f"{forbidden_copy}"
                )

    if source_product_evidence_resolver_validator.exists():
        source_product_validator_text = _read_text(
            source_product_evidence_resolver_validator
        )
        for needle in REQUIRED_SOURCE_PRODUCT_EVIDENCE_RESOLVER_VALIDATOR_NEEDLES:
            if needle not in source_product_validator_text:
                failures.append(
                    "Source product evidence resolver validator missing required needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "start-process",
            "invoke-expression",
            "subprocess.popen(",
            "shell=true",
            "assetdb.sqlite",
            "sqlite3.connect(",
        ):
            if forbidden_phrase in source_product_validator_text:
                failures.append(
                    "Source product evidence resolver validator contains forbidden phrase: "
                    f"{forbidden_phrase}"
                )

    if source_product_evidence_resolver_schema.exists():
        try:
            source_product_schema = json.loads(
                source_product_evidence_resolver_schema.read_text(encoding="utf-8-sig")
            )
            properties = source_product_schema.get("properties", {})
            cache_status = properties.get("cache_access_status", {})
            live_db_status = properties.get("live_db_access_status", {})
            if cache_status.get("const") != "blocked":
                failures.append(
                    "Source product evidence resolver schema must keep cache_access_status const blocked."
                )
            if live_db_status.get("const") != "blocked":
                failures.append(
                    "Source product evidence resolver schema must keep live_db_access_status const blocked."
                )
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(
                "Source product evidence resolver schema is not valid JSON: "
                f"{exc}"
            )

    if manifest_qc_attach_tool.exists():
        manifest_qc_attach_text = _read_text(manifest_qc_attach_tool)
        for needle in REQUIRED_MANIFEST_QC_ATTACH_TOOL_NEEDLES:
            if needle not in manifest_qc_attach_text:
                failures.append(
                    "Manifest QC attachment tool missing required needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "start-process",
            "invoke-expression",
            "subprocess.popen(",
            "shell=true",
            "assetdb.sqlite",
            "sqlite3.connect(",
        ):
            if forbidden_phrase in manifest_qc_attach_text:
                failures.append(
                    "Manifest QC attachment tool contains forbidden phrase: "
                    f"{forbidden_phrase}"
                )

    if manifest_qc_attachment_schema.exists():
        try:
            attach_schema = json.loads(
                manifest_qc_attachment_schema.read_text(encoding="utf-8-sig")
            )
            attachment_props = (
                attach_schema.get("properties", {})
                .get("manifest_attachment", {})
                .get("properties", {})
            )
            target_schema = attachment_props.get("target_path", {})
            future_schema = attachment_props.get("future_target_path", {})
            if "qc.gates[]" not in target_schema.get("enum", []):
                failures.append(
                    "Manifest QC attachment schema target_path must allow qc.gates[]."
                )
            if future_schema.get("const") != "qc.checks[]":
                failures.append(
                    "Manifest QC attachment schema future_target_path must remain qc.checks[]."
                )
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(
                "Manifest QC attachment schema is not valid JSON: "
                f"{exc}"
            )

    if pilot_release_chain_validator.exists():
        pilot_chain_validator_text = _read_text(pilot_release_chain_validator)
        for needle in REQUIRED_PILOT_RELEASE_CHAIN_VALIDATOR_NEEDLES:
            if needle not in pilot_chain_validator_text:
                failures.append(
                    "Pilot release chain validator missing required needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "start-process",
            "invoke-expression",
            "subprocess.popen(",
            "shell=true",
            "assetdb.sqlite",
            "sqlite3.connect(",
            "o3de.exe",
            "editor.exe",
            "assetprocessorbatch",
        ):
            if forbidden_phrase in pilot_chain_validator_text:
                failures.append(
                    "Pilot release chain validator contains forbidden phrase: "
                    f"{forbidden_phrase}"
                )

    if pilot_release_chain_runner.exists():
        pilot_chain_runner_text = _read_text(pilot_release_chain_runner)
        for needle in REQUIRED_PILOT_RELEASE_CHAIN_RUNNER_NEEDLES:
            if needle not in pilot_chain_runner_text:
                failures.append(
                    "Pilot release chain runner missing required needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "start-process",
            "invoke-expression",
            "subprocess.popen(",
            "shell=true",
            "assetdb.sqlite",
            "sqlite3.connect(",
            "o3de.exe",
            "editor.exe",
            "assetprocessorbatch",
        ):
            if forbidden_phrase in pilot_chain_runner_text:
                failures.append(
                    "Pilot release chain runner contains forbidden phrase: "
                    f"{forbidden_phrase}"
                )

    if pilot_release_chain_ci_proof.exists():
        pilot_chain_ci_proof_text = _read_text(pilot_release_chain_ci_proof)
        for needle in REQUIRED_PILOT_RELEASE_CHAIN_CI_PROOF_NEEDLES:
            if needle not in pilot_chain_ci_proof_text:
                failures.append(
                    "Pilot release chain CI proof command missing required needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "start-process",
            "invoke-expression",
            "subprocess.popen(",
            "shell=true",
            "assetdb.sqlite",
            "sqlite3.connect(",
            "o3de.exe",
            "editor.exe",
            "assetprocessorbatch",
        ):
            if forbidden_phrase in pilot_chain_ci_proof_text:
                failures.append(
                    "Pilot release chain CI proof command contains forbidden phrase: "
                    f"{forbidden_phrase}"
                )

    if pilot_release_chain_fixture.exists():
        try:
            fixture = json.loads(
                pilot_release_chain_fixture.read_text(encoding="utf-8-sig")
            )
            if fixture.get("manifest_attachment_target_path") != "qc.gates[]":
                failures.append(
                    "Pilot release chain fixture must keep manifest_attachment_target_path as qc.gates[]."
                )
            if fixture.get("future_manifest_attachment_target_path") != "qc.checks[]":
                failures.append(
                    "Pilot release chain fixture must keep future_manifest_attachment_target_path as qc.checks[]."
                )
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(
                "Pilot release chain fixture is not valid JSON: "
                f"{exc}"
            )

    if pilot_release_chain_manifest.exists():
        try:
            pilot_manifest = json.loads(
                pilot_release_chain_manifest.read_text(encoding="utf-8-sig")
            )
            qc = pilot_manifest.get("qc", {})
            gates = qc.get("gates", []) if isinstance(qc, dict) else []
            if not isinstance(gates, list):
                failures.append("Pilot release chain manifest qc.gates must be an array.")
            else:
                gate_ids = {
                    str(item.get("check_id", "")).strip()
                    for item in gates
                    if isinstance(item, dict)
                }
                for required_check in (
                    "max_biped_v1_skeleton_contract",
                    "dcc_conform_v1",
                    "source_product_evidence_resolver_v1",
                    "material_uv_qc_v1",
                    "animation_smoke_v1",
                    "release_publication_execution_handoff_v1",
                    "release_publication_execution_admission_request_packet_v1",
                    "release_publication_gate_set_v1",
                ):
                    if required_check not in gate_ids:
                        failures.append(
                            "Pilot release chain manifest is missing required gate check_id: "
                            f"{required_check}"
                        )
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(
                "Pilot release chain manifest fixture is not valid JSON: "
                f"{exc}"
            )

    if pilot_release_chain_base_manifest.exists():
        try:
            base_manifest = json.loads(
                pilot_release_chain_base_manifest.read_text(encoding="utf-8-sig")
            )
            qc = base_manifest.get("qc", {})
            gates = qc.get("gates", []) if isinstance(qc, dict) else []
            if not isinstance(gates, list):
                failures.append("Pilot release chain base manifest qc.gates must be an array.")
            else:
                gate_ids = {
                    str(item.get("check_id", "")).strip()
                    for item in gates
                    if isinstance(item, dict)
                }
                for implemented_gate in (
                    "max_biped_v1_skeleton_contract",
                    "dcc_conform_v1",
                    "source_product_evidence_resolver_v1",
                    "material_uv_qc_v1",
                    "animation_smoke_v1",
                ):
                    if implemented_gate in gate_ids:
                        failures.append(
                            "Pilot release chain base manifest must not pre-attach implemented "
                            f"gate check_id: {implemented_gate}"
                        )
                if "release_publication_gate_set_v1" not in gate_ids:
                    failures.append(
                        "Pilot release chain base manifest must retain downstream gate "
                        "release_publication_gate_set_v1."
                    )
                for required_downstream_gate in (
                    "release_publication_execution_handoff_v1",
                    "release_publication_execution_admission_request_packet_v1",
                ):
                    if required_downstream_gate not in gate_ids:
                        failures.append(
                            "Pilot release chain base manifest must retain downstream gate "
                            f"{required_downstream_gate}."
                        )
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(
                "Pilot release chain base manifest fixture is not valid JSON: "
                f"{exc}"
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
                    "real_asset_processor_execution",
                    "o3de_cli_execution",
                    "product_resolution",
                    "product_id_claims",
                    "asset_id_claims",
                    "source_uuid_claims",
                    "cache_read",
                    "live_asset_database_read",
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

    if execution_admission_candidate_matrix.exists():
        try:
            matrix = json.loads(
                execution_admission_candidate_matrix.read_text(encoding="utf-8-sig")
            )

            if matrix.get("schema_version") != "1.0.0":
                failures.append(
                    "execution admission candidate matrix schema_version must be 1.0.0."
                )
            if matrix.get("production_ready_claimed") is not False:
                failures.append(
                    "execution admission candidate matrix must keep production_ready_claimed=false."
                )

            if matrix.get("real_execution_admission_status") != "blocked":
                failures.append(
                    "execution admission candidate matrix must keep real_execution_admission_status=blocked."
                )
            if matrix.get("publication_admission_status") != "blocked":
                failures.append(
                    "execution admission candidate matrix must keep publication_admission_status=blocked."
                )

            admitted_noop = {
                str(item).strip()
                for item in (matrix.get("admitted_noop_receipt_candidate_ids") or [])
                if str(item).strip()
            }
            receipt_backed = {
                str(item).strip()
                for item in (matrix.get("receipt_backed_candidate_ids") or [])
                if str(item).strip()
            }
            admitted_real = {
                str(item).strip()
                for item in (matrix.get("admitted_real_execution_candidate_ids") or [])
                if str(item).strip()
            }
            admitted_publication = {
                str(item).strip()
                for item in (matrix.get("admitted_publication_candidate_ids") or [])
                if str(item).strip()
            }

            if admitted_noop != {NOOP_RECEIPT_CANDIDATE_ID}:
                failures.append(
                    "execution admission candidate matrix must keep only release_candidate_package_receipt_noop_v1 in admitted_noop_receipt_candidate_ids."
                )
            if receipt_backed != {NOOP_RECEIPT_CANDIDATE_ID}:
                failures.append(
                    "execution admission candidate matrix must keep only release_candidate_package_receipt_noop_v1 in receipt_backed_candidate_ids."
                )
            if admitted_real:
                failures.append(
                    "execution admission candidate matrix must keep admitted_real_execution_candidate_ids empty."
                )
            if admitted_publication:
                failures.append(
                    "execution admission candidate matrix must keep admitted_publication_candidate_ids empty."
                )

            candidates_raw = matrix.get("candidates")
            if not isinstance(candidates_raw, list):
                failures.append(
                    "execution admission candidate matrix candidates field must be an array."
                )
            else:
                candidate_map = {}
                for entry in candidates_raw:
                    if isinstance(entry, dict):
                        cid = str(entry.get("candidate_id", "")).strip()
                        if cid:
                            candidate_map[cid] = entry

                noop_entry = candidate_map.get(NOOP_RECEIPT_CANDIDATE_ID)
                if not isinstance(noop_entry, dict):
                    failures.append(
                        "execution admission candidate matrix must include release_candidate_package_receipt_noop_v1 candidate entry."
                    )
                else:
                    if str(noop_entry.get("candidate_type", "")).strip() != "no_op_receipt":
                        failures.append(
                            "execution admission candidate matrix no-op candidate must keep candidate_type=no_op_receipt."
                        )
                    if str(noop_entry.get("current_status", "")).strip() != "admitted":
                        failures.append(
                            "execution admission candidate matrix no-op candidate must keep current_status=admitted."
                        )

                for required_id in EXPECTED_REAL_EXECUTION_CANDIDATE_IDS:
                    entry = candidate_map.get(required_id)
                    if not isinstance(entry, dict):
                        failures.append(
                            "execution admission candidate matrix is missing expected real execution candidate: "
                            f"{required_id}"
                        )
                        continue
                    if str(entry.get("candidate_type", "")).strip() != "real_execution":
                        failures.append(
                            "execution admission candidate matrix real execution candidate has wrong type: "
                            f"{required_id}"
                        )
                    if str(entry.get("current_status", "")).strip() == "admitted":
                        failures.append(
                            "execution admission candidate matrix must not admit real execution candidates in this slice: "
                            f"{required_id}"
                        )

                for required_id in EXPECTED_PUBLICATION_CANDIDATE_IDS:
                    entry = candidate_map.get(required_id)
                    if not isinstance(entry, dict):
                        failures.append(
                            "execution admission candidate matrix is missing expected publication candidate: "
                            f"{required_id}"
                        )
                        continue
                    if str(entry.get("candidate_type", "")).strip() != "publication":
                        failures.append(
                            "execution admission candidate matrix publication candidate has wrong type: "
                            f"{required_id}"
                        )
                    if str(entry.get("current_status", "")).strip() == "admitted":
                        failures.append(
                            "execution admission candidate matrix must not admit publication candidates in this slice: "
                            f"{required_id}"
                        )

                for required_id in EXPECTED_DRY_RUN_CANDIDATE_IDS:
                    entry = candidate_map.get(required_id)
                    if not isinstance(entry, dict):
                        failures.append(
                            "execution admission candidate matrix is missing expected dry-run candidate: "
                            f"{required_id}"
                        )
                        continue
                    if str(entry.get("candidate_type", "")).strip() != "dry_run":
                        failures.append(
                            "execution admission candidate matrix dry-run candidate has wrong type: "
                            f"{required_id}"
                        )
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(
                "execution admission candidate matrix is not valid JSON: "
                f"{exc}"
            )

    if execution_admission_preflight_contracts.exists():
        try:
            contracts = json.loads(
                execution_admission_preflight_contracts.read_text(encoding="utf-8-sig")
            )

            if contracts.get("schema_version") != "1.0.0":
                failures.append(
                    "execution admission preflight contracts schema_version must be 1.0.0."
                )
            if contracts.get("record_type") != "EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_v1":
                failures.append(
                    "execution admission preflight contracts record_type must be EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_v1."
                )
            if contracts.get("production_ready_claimed") is not False:
                failures.append(
                    "execution admission preflight contracts must keep production_ready_claimed=false."
                )
            if contracts.get("publication_admitted_claimed") is not False:
                failures.append(
                    "execution admission preflight contracts must keep publication_admitted_claimed=false."
                )
            if contracts.get("real_execution_admission_status") != "blocked":
                failures.append(
                    "execution admission preflight contracts must keep real_execution_admission_status=blocked."
                )
            if contracts.get("publication_admission_status") != "blocked":
                failures.append(
                    "execution admission preflight contracts must keep publication_admission_status=blocked."
                )

            admitted_noop = {
                str(item).strip()
                for item in (contracts.get("admitted_noop_receipt_candidate_ids") or [])
                if str(item).strip()
            }
            admitted_real = {
                str(item).strip()
                for item in (contracts.get("admitted_real_execution_candidate_ids") or [])
                if str(item).strip()
            }
            admitted_publication = {
                str(item).strip()
                for item in (contracts.get("admitted_publication_candidate_ids") or [])
                if str(item).strip()
            }
            real_preflight_passed = {
                str(item).strip()
                for item in (contracts.get("real_execution_preflight_passed_candidate_ids") or [])
                if str(item).strip()
            }
            publication_preflight_passed = {
                str(item).strip()
                for item in (contracts.get("publication_preflight_passed_candidate_ids") or [])
                if str(item).strip()
            }

            if admitted_noop != {NOOP_RECEIPT_CANDIDATE_ID}:
                failures.append(
                    "execution admission preflight contracts must keep only release_candidate_package_receipt_noop_v1 in admitted_noop_receipt_candidate_ids."
                )
            if admitted_real:
                failures.append(
                    "execution admission preflight contracts must keep admitted_real_execution_candidate_ids empty."
                )
            if admitted_publication:
                failures.append(
                    "execution admission preflight contracts must keep admitted_publication_candidate_ids empty."
                )
            if real_preflight_passed:
                failures.append(
                    "execution admission preflight contracts must keep real_execution_preflight_passed_candidate_ids empty."
                )
            if publication_preflight_passed:
                failures.append(
                    "execution admission preflight contracts must keep publication_preflight_passed_candidate_ids empty."
                )

            contracts_raw = contracts.get("contracts")
            if not isinstance(contracts_raw, list):
                failures.append(
                    "execution admission preflight contracts contracts field must be an array."
                )
            else:
                contract_map = {}
                for entry in contracts_raw:
                    if isinstance(entry, dict):
                        cid = str(entry.get("candidate_id", "")).strip()
                        if cid:
                            contract_map[cid] = entry

                expected_ids = set(EXPECTED_EXECUTION_ADMISSION_CANDIDATE_IDS)
                missing_ids = sorted(expected_ids - set(contract_map))
                extra_ids = sorted(set(contract_map) - expected_ids)
                for missing_id in missing_ids:
                    failures.append(
                        "execution admission preflight contracts is missing expected candidate contract: "
                        f"{missing_id}"
                    )
                for extra_id in extra_ids:
                    failures.append(
                        "execution admission preflight contracts contains unknown candidate contract: "
                        f"{extra_id}"
                    )

                noop_entry = contract_map.get(NOOP_RECEIPT_CANDIDATE_ID)
                if not isinstance(noop_entry, dict):
                    failures.append(
                        "execution admission preflight contracts must include release_candidate_package_receipt_noop_v1 contract."
                    )
                else:
                    if str(noop_entry.get("candidate_type", "")).strip() != "no_op_receipt":
                        failures.append(
                            "execution admission preflight contracts no-op candidate must keep candidate_type=no_op_receipt."
                        )
                    if str(noop_entry.get("admission_status", "")).strip() != "admitted_no_op_only":
                        failures.append(
                            "execution admission preflight contracts no-op candidate must keep admission_status=admitted_no_op_only."
                        )

                for candidate_id in EXPECTED_REAL_EXECUTION_CANDIDATE_IDS:
                    entry = contract_map.get(candidate_id)
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("candidate_type", "")).strip() != "real_execution":
                        failures.append(
                            "execution admission preflight contracts real execution candidate has wrong type: "
                            f"{candidate_id}"
                        )
                    if str(entry.get("admission_status", "")).strip() != "unadmitted":
                        failures.append(
                            "execution admission preflight contracts must keep real execution candidates unadmitted: "
                            f"{candidate_id}"
                        )
                    if str(entry.get("preflight_status", "")).strip() == "passed":
                        failures.append(
                            "execution admission preflight contracts must not mark real execution preflight as passed in this slice: "
                            f"{candidate_id}"
                        )

                for candidate_id in EXPECTED_PUBLICATION_CANDIDATE_IDS:
                    entry = contract_map.get(candidate_id)
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("candidate_type", "")).strip() != "publication":
                        failures.append(
                            "execution admission preflight contracts publication candidate has wrong type: "
                            f"{candidate_id}"
                        )
                    if str(entry.get("admission_status", "")).strip() != "unadmitted":
                        failures.append(
                            "execution admission preflight contracts must keep publication candidates unadmitted: "
                            f"{candidate_id}"
                        )
                    if str(entry.get("preflight_status", "")).strip() == "passed":
                        failures.append(
                            "execution admission preflight contracts must not mark publication preflight as passed in this slice: "
                            f"{candidate_id}"
                        )

                for candidate_id in (
                    *EXPECTED_REAL_EXECUTION_CANDIDATE_IDS,
                    *EXPECTED_PUBLICATION_CANDIDATE_IDS,
                    *EXPECTED_DRY_RUN_CANDIDATE_IDS,
                ):
                    entry = contract_map.get(candidate_id)
                    if not isinstance(entry, dict):
                        continue
                    blocked_surfaces = {
                        str(item).strip()
                        for item in (entry.get("blocked_surfaces") or [])
                        if str(item).strip()
                    }
                    missing_surfaces = sorted(
                        REQUIRED_PREFLIGHT_BLOCKED_SURFACES - blocked_surfaces
                    )
                    if missing_surfaces:
                        failures.append(
                            "execution admission preflight contracts candidate is missing blocked surfaces: "
                            f"{candidate_id} -> {', '.join(missing_surfaces)}"
                        )
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(
                "execution admission preflight contracts is not valid JSON: "
                f"{exc}"
            )

    if execution_admission_preflight_proof_packages.exists():
        try:
            proof_packages = json.loads(
                execution_admission_preflight_proof_packages.read_text(
                    encoding="utf-8-sig"
                )
            )

            if proof_packages.get("schema_version") != "1.0.0":
                failures.append(
                    "execution admission preflight proof packages schema_version must be 1.0.0."
                )
            if (
                proof_packages.get("record_type")
                != "EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_v1"
            ):
                failures.append(
                    "execution admission preflight proof packages record_type must be EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_v1."
                )
            if proof_packages.get("production_ready_claimed") is not False:
                failures.append(
                    "execution admission preflight proof packages must keep production_ready_claimed=false."
                )
            if proof_packages.get("publication_admitted_claimed") is not False:
                failures.append(
                    "execution admission preflight proof packages must keep publication_admitted_claimed=false."
                )
            if proof_packages.get("real_execution_admission_status") != "blocked":
                failures.append(
                    "execution admission preflight proof packages must keep real_execution_admission_status=blocked."
                )
            if proof_packages.get("publication_admission_status") != "blocked":
                failures.append(
                    "execution admission preflight proof packages must keep publication_admission_status=blocked."
                )

            admitted_noop = {
                str(item).strip()
                for item in (
                    proof_packages.get("admitted_noop_receipt_candidate_ids") or []
                )
                if str(item).strip()
            }
            admitted_real = {
                str(item).strip()
                for item in (
                    proof_packages.get("admitted_real_execution_candidate_ids") or []
                )
                if str(item).strip()
            }
            admitted_publication = {
                str(item).strip()
                for item in (
                    proof_packages.get("admitted_publication_candidate_ids") or []
                )
                if str(item).strip()
            }
            real_preflight_passed = {
                str(item).strip()
                for item in (
                    proof_packages.get("real_execution_preflight_passed_candidate_ids")
                    or []
                )
                if str(item).strip()
            }
            publication_preflight_passed = {
                str(item).strip()
                for item in (
                    proof_packages.get("publication_preflight_passed_candidate_ids")
                    or []
                )
                if str(item).strip()
            }
            blocked_real_preflight = {
                str(item).strip()
                for item in (
                    proof_packages.get("blocked_real_execution_preflight_candidate_ids")
                    or []
                )
                if str(item).strip()
            }
            blocked_publication_preflight = {
                str(item).strip()
                for item in (
                    proof_packages.get("blocked_publication_preflight_candidate_ids")
                    or []
                )
                if str(item).strip()
            }
            blocked_dry_run_preflight = {
                str(item).strip()
                for item in (
                    proof_packages.get("blocked_dry_run_preflight_candidate_ids")
                    or []
                )
                if str(item).strip()
            }

            if admitted_noop != {NOOP_RECEIPT_CANDIDATE_ID}:
                failures.append(
                    "execution admission preflight proof packages must keep only release_candidate_package_receipt_noop_v1 in admitted_noop_receipt_candidate_ids."
                )
            if admitted_real:
                failures.append(
                    "execution admission preflight proof packages must keep admitted_real_execution_candidate_ids empty."
                )
            if admitted_publication:
                failures.append(
                    "execution admission preflight proof packages must keep admitted_publication_candidate_ids empty."
                )
            if real_preflight_passed:
                failures.append(
                    "execution admission preflight proof packages must keep real_execution_preflight_passed_candidate_ids empty."
                )
            if publication_preflight_passed:
                failures.append(
                    "execution admission preflight proof packages must keep publication_preflight_passed_candidate_ids empty."
                )

            if blocked_real_preflight != set(EXPECTED_REAL_EXECUTION_CANDIDATE_IDS):
                failures.append(
                    "execution admission preflight proof packages blocked_real_execution_preflight_candidate_ids must match expected real execution candidate ids."
                )
            if blocked_publication_preflight != set(
                EXPECTED_PUBLICATION_CANDIDATE_IDS
            ):
                failures.append(
                    "execution admission preflight proof packages blocked_publication_preflight_candidate_ids must match expected publication candidate ids."
                )
            if blocked_dry_run_preflight != set(EXPECTED_DRY_RUN_CANDIDATE_IDS):
                failures.append(
                    "execution admission preflight proof packages blocked_dry_run_preflight_candidate_ids must match expected dry-run candidate ids."
                )

            packages_raw = proof_packages.get("proof_packages")
            if not isinstance(packages_raw, list):
                failures.append(
                    "execution admission preflight proof packages proof_packages field must be an array."
                )
            else:
                package_map = {}
                for entry in packages_raw:
                    if isinstance(entry, dict):
                        cid = str(entry.get("candidate_id", "")).strip()
                        if cid:
                            package_map[cid] = entry

                expected_ids = set(EXPECTED_EXECUTION_ADMISSION_CANDIDATE_IDS)
                missing_ids = sorted(expected_ids - set(package_map))
                extra_ids = sorted(set(package_map) - expected_ids)
                for missing_id in missing_ids:
                    failures.append(
                        "execution admission preflight proof packages is missing expected candidate proof package: "
                        f"{missing_id}"
                    )
                for extra_id in extra_ids:
                    failures.append(
                        "execution admission preflight proof packages contains unknown candidate proof package: "
                        f"{extra_id}"
                    )

                noop_entry = package_map.get(NOOP_RECEIPT_CANDIDATE_ID)
                if not isinstance(noop_entry, dict):
                    failures.append(
                        "execution admission preflight proof packages must include release_candidate_package_receipt_noop_v1 package."
                    )
                else:
                    if str(noop_entry.get("candidate_type", "")).strip() != "no_op_receipt":
                        failures.append(
                            "execution admission preflight proof packages no-op candidate must keep candidate_type=no_op_receipt."
                        )
                    if str(noop_entry.get("admission_status", "")).strip() != "admitted_no_op_only":
                        failures.append(
                            "execution admission preflight proof packages no-op candidate must keep admission_status=admitted_no_op_only."
                        )
                    if (
                        str(noop_entry.get("proof_package_status", "")).strip()
                        not in {"satisfied_no_op_only", "satisfied_non_execution_only"}
                    ):
                        failures.append(
                            "execution admission preflight proof packages no-op candidate must keep a no-op-only satisfied proof status."
                        )

                for candidate_id in EXPECTED_REAL_EXECUTION_CANDIDATE_IDS:
                    entry = package_map.get(candidate_id)
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("candidate_type", "")).strip() != "real_execution":
                        failures.append(
                            "execution admission preflight proof packages real execution candidate has wrong type: "
                            f"{candidate_id}"
                        )
                    if str(entry.get("admission_status", "")).strip() != "unadmitted":
                        failures.append(
                            "execution admission preflight proof packages must keep real execution candidates unadmitted: "
                            f"{candidate_id}"
                        )
                    if bool(entry.get("preflight_passed", False)):
                        failures.append(
                            "execution admission preflight proof packages must keep real execution preflight_passed=false in this slice: "
                            f"{candidate_id}"
                        )
                    if str(entry.get("proof_package_status", "")).strip() in {
                        "satisfied_no_op_only",
                        "satisfied_non_execution_only",
                    }:
                        failures.append(
                            "execution admission preflight proof packages must not mark real execution candidates as fully satisfied in this slice: "
                            f"{candidate_id}"
                        )
                    missing_evidence = {
                        str(item).strip()
                        for item in (entry.get("missing_evidence_items") or [])
                        if str(item).strip()
                    }
                    if not missing_evidence:
                        failures.append(
                            "execution admission preflight proof packages real execution candidate must include missing_evidence_items: "
                            f"{candidate_id}"
                        )
                    blocked_reason_codes = {
                        str(item).strip()
                        for item in (entry.get("blocked_reason_codes") or [])
                        if str(item).strip()
                    }
                    if not blocked_reason_codes:
                        failures.append(
                            "execution admission preflight proof packages real execution candidate must include blocked_reason_codes: "
                            f"{candidate_id}"
                        )
                    if not str(entry.get("required_validator", "")).strip():
                        failures.append(
                            "execution admission preflight proof packages real execution candidate must include required_validator: "
                            f"{candidate_id}"
                        )
                    if not str(entry.get("required_receipt_schema", "")).strip():
                        failures.append(
                            "execution admission preflight proof packages real execution candidate must include required_receipt_schema: "
                            f"{candidate_id}"
                        )
                    if not str(entry.get("approval_phrase_required", "")).strip():
                        failures.append(
                            "execution admission preflight proof packages real execution candidate must include approval_phrase_required: "
                            f"{candidate_id}"
                        )
                    if bool(entry.get("unsafe_claims_detected", False)):
                        failures.append(
                            "execution admission preflight proof packages real execution candidate must keep unsafe_claims_detected=false: "
                            f"{candidate_id}"
                        )

                for candidate_id in EXPECTED_PUBLICATION_CANDIDATE_IDS:
                    entry = package_map.get(candidate_id)
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("candidate_type", "")).strip() != "publication":
                        failures.append(
                            "execution admission preflight proof packages publication candidate has wrong type: "
                            f"{candidate_id}"
                        )
                    if str(entry.get("admission_status", "")).strip() != "unadmitted":
                        failures.append(
                            "execution admission preflight proof packages must keep publication candidates unadmitted: "
                            f"{candidate_id}"
                        )
                    if bool(entry.get("preflight_passed", False)):
                        failures.append(
                            "execution admission preflight proof packages must keep publication preflight_passed=false in this slice: "
                            f"{candidate_id}"
                        )
                    if str(entry.get("proof_package_status", "")).strip() in {
                        "satisfied_no_op_only",
                        "satisfied_non_execution_only",
                    }:
                        failures.append(
                            "execution admission preflight proof packages must not mark publication candidates as fully satisfied in this slice: "
                            f"{candidate_id}"
                        )
                    missing_evidence = {
                        str(item).strip()
                        for item in (entry.get("missing_evidence_items") or [])
                        if str(item).strip()
                    }
                    if not missing_evidence:
                        failures.append(
                            "execution admission preflight proof packages publication candidate must include missing_evidence_items: "
                            f"{candidate_id}"
                        )
                    blocked_reason_codes = {
                        str(item).strip()
                        for item in (entry.get("blocked_reason_codes") or [])
                        if str(item).strip()
                    }
                    if not blocked_reason_codes:
                        failures.append(
                            "execution admission preflight proof packages publication candidate must include blocked_reason_codes: "
                            f"{candidate_id}"
                        )
                    if not str(entry.get("required_validator", "")).strip():
                        failures.append(
                            "execution admission preflight proof packages publication candidate must include required_validator: "
                            f"{candidate_id}"
                        )
                    if not str(entry.get("required_receipt_schema", "")).strip():
                        failures.append(
                            "execution admission preflight proof packages publication candidate must include required_receipt_schema: "
                            f"{candidate_id}"
                        )
                    if not str(entry.get("approval_phrase_required", "")).strip():
                        failures.append(
                            "execution admission preflight proof packages publication candidate must include approval_phrase_required: "
                            f"{candidate_id}"
                        )
                    if bool(entry.get("unsafe_claims_detected", False)):
                        failures.append(
                            "execution admission preflight proof packages publication candidate must keep unsafe_claims_detected=false: "
                            f"{candidate_id}"
                        )
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(
                "execution admission preflight proof packages is not valid JSON: "
                f"{exc}"
            )

    if execution_admission_readiness_rollup.exists():
        try:
            rollup = json.loads(
                execution_admission_readiness_rollup.read_text(encoding="utf-8-sig")
            )

            if rollup.get("schema_version") != "1.0.0":
                failures.append(
                    "execution admission readiness rollup schema_version must be 1.0.0."
                )
            if rollup.get("record_type") != "EXECUTION_ADMISSION_READINESS_ROLLUP_v1":
                failures.append(
                    "execution admission readiness rollup record_type must be EXECUTION_ADMISSION_READINESS_ROLLUP_v1."
                )
            if rollup.get("overall_readiness_rollup_status") != "static_rollup_valid_blocked":
                failures.append(
                    "execution admission readiness rollup must keep overall_readiness_rollup_status=static_rollup_valid_blocked."
                )
            if rollup.get("production_ready_claimed") is not False:
                failures.append(
                    "execution admission readiness rollup must keep production_ready_claimed=false."
                )
            if rollup.get("unsafe_claims_detected") is not False:
                failures.append(
                    "execution admission readiness rollup must keep unsafe_claims_detected=false."
                )
            if rollup.get("real_execution_admission_status") != "blocked":
                failures.append(
                    "execution admission readiness rollup must keep real_execution_admission_status=blocked."
                )
            if rollup.get("publication_admission_status") != "blocked":
                failures.append(
                    "execution admission readiness rollup must keep publication_admission_status=blocked."
                )
            if (
                str(rollup.get("approval_phrase_required", "")).strip()
                != "APPROVE EXECUTION ADMISSION <candidate_id>"
            ):
                failures.append(
                    "execution admission readiness rollup approval_phrase_required must be APPROVE EXECUTION ADMISSION <candidate_id>."
                )

            admitted_noop = {
                str(item).strip()
                for item in (rollup.get("admitted_noop_receipt_candidate_ids") or [])
                if str(item).strip()
            }
            admitted_real = {
                str(item).strip()
                for item in (rollup.get("admitted_real_execution_candidate_ids") or [])
                if str(item).strip()
            }
            admitted_publication = {
                str(item).strip()
                for item in (rollup.get("admitted_publication_candidate_ids") or [])
                if str(item).strip()
            }
            real_preflight_passed = {
                str(item).strip()
                for item in (rollup.get("real_execution_preflight_passed_candidate_ids") or [])
                if str(item).strip()
            }
            publication_preflight_passed = {
                str(item).strip()
                for item in (rollup.get("publication_preflight_passed_candidate_ids") or [])
                if str(item).strip()
            }
            blocked_real = {
                str(item).strip()
                for item in (rollup.get("blocked_real_execution_candidate_ids") or [])
                if str(item).strip()
            }
            blocked_publication = {
                str(item).strip()
                for item in (rollup.get("blocked_publication_candidate_ids") or [])
                if str(item).strip()
            }
            blocked_dry_run = {
                str(item).strip()
                for item in (rollup.get("blocked_dry_run_candidate_ids") or [])
                if str(item).strip()
            }

            if admitted_noop != {NOOP_RECEIPT_CANDIDATE_ID}:
                failures.append(
                    "execution admission readiness rollup must keep only release_candidate_package_receipt_noop_v1 in admitted_noop_receipt_candidate_ids."
                )
            if admitted_real:
                failures.append(
                    "execution admission readiness rollup must keep admitted_real_execution_candidate_ids empty."
                )
            if admitted_publication:
                failures.append(
                    "execution admission readiness rollup must keep admitted_publication_candidate_ids empty."
                )
            if real_preflight_passed:
                failures.append(
                    "execution admission readiness rollup must keep real_execution_preflight_passed_candidate_ids empty."
                )
            if publication_preflight_passed:
                failures.append(
                    "execution admission readiness rollup must keep publication_preflight_passed_candidate_ids empty."
                )
            if blocked_real != set(EXPECTED_REAL_EXECUTION_CANDIDATE_IDS):
                failures.append(
                    "execution admission readiness rollup blocked_real_execution_candidate_ids must match expected real execution candidate ids."
                )
            if blocked_publication != set(EXPECTED_PUBLICATION_CANDIDATE_IDS):
                failures.append(
                    "execution admission readiness rollup blocked_publication_candidate_ids must match expected publication candidate ids."
                )
            if blocked_dry_run != set(EXPECTED_DRY_RUN_CANDIDATE_IDS):
                failures.append(
                    "execution admission readiness rollup blocked_dry_run_candidate_ids must match expected dry-run candidate ids."
                )

            rollups_raw = rollup.get("candidate_rollups")
            if not isinstance(rollups_raw, list):
                failures.append(
                    "execution admission readiness rollup candidate_rollups field must be an array."
                )
            else:
                rollup_map = {}
                for entry in rollups_raw:
                    if isinstance(entry, dict):
                        cid = str(entry.get("candidate_id", "")).strip()
                        if cid:
                            rollup_map[cid] = entry

                expected_ids = set(EXPECTED_EXECUTION_ADMISSION_CANDIDATE_IDS)
                missing_ids = sorted(expected_ids - set(rollup_map))
                extra_ids = sorted(set(rollup_map) - expected_ids)
                for missing_id in missing_ids:
                    failures.append(
                        "execution admission readiness rollup is missing expected candidate rollup: "
                        f"{missing_id}"
                    )
                for extra_id in extra_ids:
                    failures.append(
                        "execution admission readiness rollup contains unknown candidate rollup: "
                        f"{extra_id}"
                    )

                noop_entry = rollup_map.get(NOOP_RECEIPT_CANDIDATE_ID)
                if not isinstance(noop_entry, dict):
                    failures.append(
                        "execution admission readiness rollup must include release_candidate_package_receipt_noop_v1 rollup entry."
                    )
                else:
                    if str(noop_entry.get("candidate_type", "")).strip() != "no_op_receipt":
                        failures.append(
                            "execution admission readiness rollup no-op candidate must keep candidate_type=no_op_receipt."
                        )
                    if str(noop_entry.get("admission_status", "")).strip() != "admitted_no_op_only":
                        failures.append(
                            "execution admission readiness rollup no-op candidate must keep admission_status=admitted_no_op_only."
                        )
                    if (
                        str(noop_entry.get("proof_package_status", "")).strip()
                        not in {"satisfied_no_op_only", "satisfied_non_execution_only"}
                    ):
                        failures.append(
                            "execution admission readiness rollup no-op candidate must keep a no-op-only satisfied proof status."
                        )

                for candidate_id in EXPECTED_REAL_EXECUTION_CANDIDATE_IDS:
                    entry = rollup_map.get(candidate_id)
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("candidate_type", "")).strip() != "real_execution":
                        failures.append(
                            "execution admission readiness rollup real execution candidate has wrong type: "
                            f"{candidate_id}"
                        )
                    if str(entry.get("admission_status", "")).strip() != "unadmitted":
                        failures.append(
                            "execution admission readiness rollup must keep real execution candidates unadmitted: "
                            f"{candidate_id}"
                        )
                    if bool(entry.get("preflight_passed", False)):
                        failures.append(
                            "execution admission readiness rollup must keep real execution preflight_passed=false in this slice: "
                            f"{candidate_id}"
                        )

                for candidate_id in EXPECTED_PUBLICATION_CANDIDATE_IDS:
                    entry = rollup_map.get(candidate_id)
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("candidate_type", "")).strip() != "publication":
                        failures.append(
                            "execution admission readiness rollup publication candidate has wrong type: "
                            f"{candidate_id}"
                        )
                    if str(entry.get("admission_status", "")).strip() != "unadmitted":
                        failures.append(
                            "execution admission readiness rollup must keep publication candidates unadmitted: "
                            f"{candidate_id}"
                        )
                    if bool(entry.get("preflight_passed", False)):
                        failures.append(
                            "execution admission readiness rollup must keep publication preflight_passed=false in this slice: "
                            f"{candidate_id}"
                        )

                for candidate_id in EXPECTED_DRY_RUN_CANDIDATE_IDS:
                    entry = rollup_map.get(candidate_id)
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("candidate_type", "")).strip() != "dry_run":
                        failures.append(
                            "execution admission readiness rollup dry-run candidate has wrong type: "
                            f"{candidate_id}"
                        )
                    if str(entry.get("admission_status", "")).strip() != "unadmitted":
                        failures.append(
                            "execution admission readiness rollup must keep dry-run candidates unadmitted: "
                            f"{candidate_id}"
                        )
                    if bool(entry.get("can_advance_without_explicit_approval", True)):
                        failures.append(
                            "execution admission readiness rollup must keep dry-run candidates can_advance_without_explicit_approval=false in this slice: "
                            f"{candidate_id}"
                        )

            next_slice = (
                rollup.get("safest_next_preparation_slice")
                if isinstance(rollup.get("safest_next_preparation_slice"), dict)
                else {}
            )
            if str(next_slice.get("slice_id", "")).strip() != EXPECTED_ROLLUP_NEXT_SLICE_ID:
                failures.append(
                    "execution admission readiness rollup safest_next_preparation_slice.slice_id must match expected planning slice."
                )
            if (
                str(next_slice.get("candidate_id", "")).strip()
                != EXPECTED_ROLLUP_NEXT_SLICE_CANDIDATE_ID
            ):
                failures.append(
                    "execution admission readiness rollup safest_next_preparation_slice.candidate_id must match expected dry-run planning candidate."
                )
            if bool(next_slice.get("admits_execution", False)):
                failures.append(
                    "execution admission readiness rollup safest_next_preparation_slice must keep admits_execution=false."
                )
            if bool(next_slice.get("admits_publication", False)):
                failures.append(
                    "execution admission readiness rollup safest_next_preparation_slice must keep admits_publication=false."
                )
            if next_slice.get("requires_future_pr") is not True:
                failures.append(
                    "execution admission readiness rollup safest_next_preparation_slice must keep requires_future_pr=true."
                )
            if next_slice.get("requires_explicit_approval_before_admission") is not True:
                failures.append(
                    "execution admission readiness rollup safest_next_preparation_slice must keep requires_explicit_approval_before_admission=true."
                )

            safety = rollup.get("safety") if isinstance(rollup.get("safety"), dict) else {}
            for field in (
                "o3de_execution_status",
                "editor_runtime_execution_status",
                "asset_processor_execution_status",
                "blender_dcc_execution_status",
                "profiler_benchmark_execution_status",
                "live_screenshot_capture_status",
                "spawn_publish_status",
                "cache_live_db_access_status",
                "production_write_status",
                "engine_write_status",
            ):
                if str(safety.get(field, "")).strip() != "blocked":
                    failures.append(
                        "execution admission readiness rollup safety field must remain blocked: "
                        f"{field}"
                    )
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(
                "execution admission readiness rollup is not valid JSON: "
                f"{exc}"
            )

    if release_candidate_publication_dry_run_plan.exists():
        try:
            dry_run_plan = json.loads(
                release_candidate_publication_dry_run_plan.read_text(encoding="utf-8-sig")
            )

            if dry_run_plan.get("schema_version") != "1.0.0":
                failures.append(
                    "release candidate publication dry-run plan schema_version must be 1.0.0."
                )
            if (
                dry_run_plan.get("record_type")
                != "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_v1"
            ):
                failures.append(
                    "release candidate publication dry-run plan record_type must be RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_v1."
                )
            if (
                str(dry_run_plan.get("candidate_id", "")).strip()
                != EXPECTED_ROLLUP_NEXT_SLICE_CANDIDATE_ID
            ):
                failures.append(
                    "release candidate publication dry-run plan candidate_id must be release_candidate_package_publish_dry_run_v1."
                )
            if str(dry_run_plan.get("candidate_type", "")).strip() != "dry_run":
                failures.append(
                    "release candidate publication dry-run plan candidate_type must be dry_run."
                )
            if str(dry_run_plan.get("admission_status", "")).strip() != "unadmitted":
                failures.append(
                    "release candidate publication dry-run plan admission_status must remain unadmitted."
                )
            if bool(dry_run_plan.get("dry_run_admitted", False)):
                failures.append(
                    "release candidate publication dry-run plan must keep dry_run_admitted=false."
                )
            if bool(dry_run_plan.get("publication_admitted", False)):
                failures.append(
                    "release candidate publication dry-run plan must keep publication_admitted=false."
                )
            if bool(dry_run_plan.get("real_execution_admitted", False)):
                failures.append(
                    "release candidate publication dry-run plan must keep real_execution_admitted=false."
                )
            if bool(dry_run_plan.get("production_ready_claimed", False)):
                failures.append(
                    "release candidate publication dry-run plan must keep production_ready_claimed=false."
                )
            if dry_run_plan.get("generated_from_static_artifacts_only") is not True:
                failures.append(
                    "release candidate publication dry-run plan must keep generated_from_static_artifacts_only=true."
                )
            if str(dry_run_plan.get("plan_status", "")).strip() != "static_plan_valid_blocked":
                failures.append(
                    "release candidate publication dry-run plan must keep plan_status=static_plan_valid_blocked."
                )
            if (
                str(dry_run_plan.get("planning_scope", "")).strip()
                != "candidate_specific_publication_dry_run_planning_only"
            ):
                failures.append(
                    "release candidate publication dry-run plan planning_scope must be candidate_specific_publication_dry_run_planning_only."
                )
            if dry_run_plan.get("publication_surfaces_blocked") is not True:
                failures.append(
                    "release candidate publication dry-run plan must keep publication_surfaces_blocked=true."
                )
            if dry_run_plan.get("execution_surfaces_blocked") is not True:
                failures.append(
                    "release candidate publication dry-run plan must keep execution_surfaces_blocked=true."
                )
            if (
                str(dry_run_plan.get("approval_phrase_required", "")).strip()
                != EXPECTED_DRY_RUN_PLAN_APPROVAL_PHRASE
            ):
                failures.append(
                    "release candidate publication dry-run plan must keep exact approval phrase for release_candidate_package_publish_dry_run_v1."
                )
            approval_decision_reference = dry_run_plan.get("approval_decision_reference")
            if isinstance(approval_decision_reference, str) and approval_decision_reference.strip():
                failures.append(
                    "release candidate publication dry-run plan approval_decision_reference must be null/empty while unadmitted."
                )

            blocked_reason_codes = {
                str(item).strip()
                for item in (dry_run_plan.get("blocked_reason_codes") or [])
                if str(item).strip()
            }
            missing_evidence_items = {
                str(item).strip()
                for item in (dry_run_plan.get("missing_evidence_items") or [])
                if str(item).strip()
            }
            if not blocked_reason_codes:
                failures.append(
                    "release candidate publication dry-run plan must include blocked_reason_codes."
                )
            if not missing_evidence_items:
                failures.append(
                    "release candidate publication dry-run plan must include missing_evidence_items."
                )

            out_of_scope_surfaces = {
                str(item).strip()
                for item in (dry_run_plan.get("out_of_scope_surfaces") or [])
                if str(item).strip()
            }
            for required_surface in (
                "publication_execution",
                "spawn_execution",
                "production_path_write",
                "engine_path_write",
                "cache_live_db_access",
            ):
                if required_surface not in out_of_scope_surfaces:
                    failures.append(
                        "release candidate publication dry-run plan out_of_scope_surfaces must include: "
                        f"{required_surface}"
                    )

            forbidden_paths = {
                str(item).strip()
                for item in (dry_run_plan.get("forbidden_paths") or [])
                if str(item).strip()
            }
            for required_path_category in (
                "production_path_category",
                "engine_path_category",
                "cache_live_db_category",
                "destructive_cleanup_category",
            ):
                if required_path_category not in forbidden_paths:
                    failures.append(
                        "release candidate publication dry-run plan forbidden_paths must include: "
                        f"{required_path_category}"
                    )

            for output in dry_run_plan.get("future_allowed_sandbox_outputs") or []:
                normalized_output = str(output).replace("\\", "/").strip().lower()
                if not normalized_output.startswith("examples/sandbox/"):
                    failures.append(
                        "release candidate publication dry-run plan future_allowed_sandbox_outputs must stay under examples/sandbox/: "
                        f"{output}"
                    )
                if "production" in normalized_output:
                    failures.append(
                        "release candidate publication dry-run plan must not allow production-path outputs: "
                        f"{output}"
                    )
                if "engine" in normalized_output:
                    failures.append(
                        "release candidate publication dry-run plan must not allow engine-path outputs: "
                        f"{output}"
                    )

            claim_status = (
                dry_run_plan.get("claim_status")
                if isinstance(dry_run_plan.get("claim_status"), dict)
                else {}
            )
            if str(claim_status.get("source_uuid_status", "")).strip() != "not_authoritative":
                failures.append(
                    "release candidate publication dry-run plan must keep claim_status.source_uuid_status=not_authoritative."
                )
            if str(claim_status.get("asset_id_status", "")).strip() != "not_authoritative":
                failures.append(
                    "release candidate publication dry-run plan must keep claim_status.asset_id_status=not_authoritative."
                )
            if str(claim_status.get("product_id_status", "")).strip() != "not_authoritative":
                failures.append(
                    "release candidate publication dry-run plan must keep claim_status.product_id_status=not_authoritative."
                )

            if bool(dry_run_plan.get("unsafe_claims_detected", False)):
                failures.append(
                    "release candidate publication dry-run plan must keep unsafe_claims_detected=false."
                )

            source_artifacts = (
                dry_run_plan.get("source_artifacts")
                if isinstance(dry_run_plan.get("source_artifacts"), dict)
                else {}
            )
            expected_source_refs = {
                "candidate_matrix_ref": EXECUTION_ADMISSION_CANDIDATE_MATRIX_REL,
                "preflight_contracts_ref": EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_REL,
                "preflight_proof_packages_ref": EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_REL,
                "readiness_rollup_ref": EXECUTION_ADMISSION_READINESS_ROLLUP_REL,
                "noop_receipt_status_ref": "examples/execution-admission/release_candidate_package_receipt_noop_execution_admission_decision_approved.json",
            }
            for field, expected_path in expected_source_refs.items():
                actual_ref = str(source_artifacts.get(field, "")).replace("\\", "/").strip()
                if not actual_ref:
                    failures.append(
                        "release candidate publication dry-run plan source_artifacts is missing field: "
                        f"{field}"
                    )
                    continue
                if actual_ref != expected_path:
                    failures.append(
                        "release candidate publication dry-run plan source_artifacts field has unexpected path: "
                        f"{field} -> {actual_ref}"
                    )

            source_status = (
                dry_run_plan.get("source_artifact_validation_status")
                if isinstance(dry_run_plan.get("source_artifact_validation_status"), dict)
                else {}
            )
            for field in (
                "candidate_matrix_status",
                "preflight_contracts_status",
                "preflight_proof_packages_status",
                "readiness_rollup_status",
                "production_readiness_status",
                "noop_receipt_status",
            ):
                if str(source_status.get(field, "")).strip() != "pass":
                    failures.append(
                        "release candidate publication dry-run plan source_artifact_validation_status must keep field pass: "
                        f"{field}"
                    )

            alignment = (
                dry_run_plan.get("readiness_rollup_alignment")
                if isinstance(dry_run_plan.get("readiness_rollup_alignment"), dict)
                else {}
            )
            if (
                str(alignment.get("safest_next_preparation_slice_id", "")).strip()
                != EXPECTED_ROLLUP_NEXT_SLICE_ID
            ):
                failures.append(
                    "release candidate publication dry-run plan readiness_rollup_alignment must keep safest_next_preparation_slice_id=candidate_specific_dry_run_planning_v1."
                )
            if (
                str(alignment.get("safest_next_preparation_candidate_id", "")).strip()
                != EXPECTED_ROLLUP_NEXT_SLICE_CANDIDATE_ID
            ):
                failures.append(
                    "release candidate publication dry-run plan readiness_rollup_alignment must keep safest_next_preparation_candidate_id=release_candidate_package_publish_dry_run_v1."
                )
            if str(alignment.get("alignment_status", "")).strip() != "aligned":
                failures.append(
                    "release candidate publication dry-run plan readiness_rollup_alignment must keep alignment_status=aligned."
                )
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(
                "release candidate publication dry-run plan is not valid JSON: "
                f"{exc}"
            )

    for receipt_example_path, expected_receipt_status in (
        (
            release_candidate_publication_dry_run_receipt_contract,
            "receipt_not_issued_contract_only",
        ),
        (
            release_candidate_publication_dry_run_receipt_blocked,
            "blocked_unissued_contract_only",
        ),
    ):
        if receipt_example_path.exists():
            try:
                receipt_contract = json.loads(
                    receipt_example_path.read_text(encoding="utf-8-sig")
                )

                if receipt_contract.get("schema_version") != "1.0.0":
                    failures.append(
                        "release candidate publication dry-run receipt contract schema_version must be 1.0.0."
                    )
                if (
                    receipt_contract.get("record_type")
                    != "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_CONTRACT_v1"
                ):
                    failures.append(
                        "release candidate publication dry-run receipt contract record_type must be RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_CONTRACT_v1."
                    )
                if (
                    str(receipt_contract.get("candidate_id", "")).strip()
                    != EXPECTED_ROLLUP_NEXT_SLICE_CANDIDATE_ID
                ):
                    failures.append(
                        "release candidate publication dry-run receipt contract candidate_id must be release_candidate_package_publish_dry_run_v1."
                    )
                if str(receipt_contract.get("candidate_type", "")).strip() != "dry_run":
                    failures.append(
                        "release candidate publication dry-run receipt contract candidate_type must be dry_run."
                    )
                if str(receipt_contract.get("admission_status", "")).strip() != "unadmitted":
                    failures.append(
                        "release candidate publication dry-run receipt contract admission_status must remain unadmitted."
                    )
                if str(receipt_contract.get("receipt_type", "")).strip() != EXPECTED_DRY_RUN_RECEIPT_TYPE:
                    failures.append(
                        "release candidate publication dry-run receipt contract receipt_type must be release_candidate_package_publish_dry_run_receipt_v1."
                    )
                if str(receipt_contract.get("receipt_contract_status", "")).strip() != "static_contract_valid_blocked":
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep receipt_contract_status=static_contract_valid_blocked."
                    )
                if str(receipt_contract.get("receipt_status", "")).strip() != expected_receipt_status:
                    failures.append(
                        "release candidate publication dry-run receipt contract receipt_status does not match expected blocked/unissued value."
                    )
                if bool(receipt_contract.get("receipt_issued", False)):
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep receipt_issued=false."
                    )
                if bool(receipt_contract.get("dry_run_admitted", False)):
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep dry_run_admitted=false."
                    )
                if bool(receipt_contract.get("publication_admitted", False)):
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep publication_admitted=false."
                    )
                if bool(receipt_contract.get("real_execution_admitted", False)):
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep real_execution_admitted=false."
                    )
                if bool(receipt_contract.get("production_ready_claimed", False)):
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep production_ready_claimed=false."
                    )
                if receipt_contract.get("generated_from_static_artifacts_only") is not True:
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep generated_from_static_artifacts_only=true."
                    )
                if receipt_contract.get("required_approval_decision_reference") is not True:
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep required_approval_decision_reference=true."
                    )
                if (
                    str(receipt_contract.get("approval_phrase_required", "")).strip()
                    != EXPECTED_DRY_RUN_PLAN_APPROVAL_PHRASE
                ):
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep exact approval phrase for release_candidate_package_publish_dry_run_v1."
                    )
                approval_decision_reference = receipt_contract.get("approval_decision_reference")
                if isinstance(approval_decision_reference, str) and approval_decision_reference.strip():
                    failures.append(
                        "release candidate publication dry-run receipt contract approval_decision_reference must be null/empty while unadmitted."
                    )

                blocked_reason_codes = {
                    str(item).strip()
                    for item in (receipt_contract.get("blocked_reason_codes") or [])
                    if str(item).strip()
                }
                missing_evidence_items = {
                    str(item).strip()
                    for item in (receipt_contract.get("missing_evidence_items") or [])
                    if str(item).strip()
                }
                if not blocked_reason_codes:
                    failures.append(
                        "release candidate publication dry-run receipt contract must include blocked_reason_codes."
                    )
                if not missing_evidence_items:
                    failures.append(
                        "release candidate publication dry-run receipt contract must include missing_evidence_items."
                    )

                forbidden_paths = {
                    str(item).strip()
                    for item in (receipt_contract.get("forbidden_paths") or [])
                    if str(item).strip()
                }
                for required_path_category in (
                    "production_path_category",
                    "engine_path_category",
                    "cache_live_db_category",
                    "destructive_cleanup_category",
                ):
                    if required_path_category not in forbidden_paths:
                        failures.append(
                            "release candidate publication dry-run receipt contract forbidden_paths must include: "
                            f"{required_path_category}"
                        )

                forbidden_outputs = {
                    str(item).strip()
                    for item in (receipt_contract.get("forbidden_outputs") or [])
                    if str(item).strip()
                }
                for required_output in (
                    "publish_operation",
                    "spawn_operation",
                    "production_path_writes",
                    "engine_path_writes",
                    "cache_live_db_access",
                    "authoritative_source_uuid_claims",
                    "authoritative_asset_id_claims",
                    "authoritative_product_id_claims",
                ):
                    if required_output not in forbidden_outputs:
                        failures.append(
                            "release candidate publication dry-run receipt contract forbidden_outputs must include: "
                            f"{required_output}"
                        )

                required_receipt_fields = {
                    str(item).strip()
                    for item in (receipt_contract.get("required_receipt_fields") or [])
                    if str(item).strip()
                }
                for required_field in (
                    "candidate_id",
                    "receipt_type",
                    "receipt_status",
                    "approval_decision_reference",
                    "source_artifact_references",
                    "input_evidence_references",
                    "sandbox_output_index",
                    "validation_summary",
                    "blocked_surface_attestations",
                    "rollback_or_cleanup_evidence",
                    "hashes",
                    "safety_posture",
                ):
                    if required_field not in required_receipt_fields:
                        failures.append(
                            "release candidate publication dry-run receipt contract required_receipt_fields must include: "
                            f"{required_field}"
                        )

                if receipt_contract.get("publication_surfaces_blocked") is not True:
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep publication_surfaces_blocked=true."
                    )
                if receipt_contract.get("execution_surfaces_blocked") is not True:
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep execution_surfaces_blocked=true."
                    )
                if receipt_contract.get("cache_live_db_access_blocked") is not True:
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep cache_live_db_access_blocked=true."
                    )
                if receipt_contract.get("authoritative_id_claims_blocked") is not True:
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep authoritative_id_claims_blocked=true."
                    )

                for output_scope in receipt_contract.get("allowed_receipt_output_scope") or []:
                    normalized_scope = str(output_scope).replace("\\", "/").strip().lower()
                    if not normalized_scope.startswith("examples/sandbox/"):
                        failures.append(
                            "release candidate publication dry-run receipt contract allowed_receipt_output_scope must stay under examples/sandbox/: "
                            f"{output_scope}"
                        )
                    if "production" in normalized_scope:
                        failures.append(
                            "release candidate publication dry-run receipt contract must not allow production-path output scopes: "
                            f"{output_scope}"
                        )
                    if "engine" in normalized_scope:
                        failures.append(
                            "release candidate publication dry-run receipt contract must not allow engine-path output scopes: "
                            f"{output_scope}"
                        )

                safety_posture = (
                    receipt_contract.get("safety_posture")
                    if isinstance(receipt_contract.get("safety_posture"), dict)
                    else {}
                )
                if str(safety_posture.get("source_uuid_status", "")).strip() != "not_authoritative":
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep safety_posture.source_uuid_status=not_authoritative."
                    )
                if str(safety_posture.get("asset_id_status", "")).strip() != "not_authoritative":
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep safety_posture.asset_id_status=not_authoritative."
                    )
                if str(safety_posture.get("product_id_status", "")).strip() != "not_authoritative":
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep safety_posture.product_id_status=not_authoritative."
                    )

                if bool(receipt_contract.get("unsafe_claims_detected", False)):
                    failures.append(
                        "release candidate publication dry-run receipt contract must keep unsafe_claims_detected=false."
                    )

                source_artifacts = (
                    receipt_contract.get("source_artifacts")
                    if isinstance(receipt_contract.get("source_artifacts"), dict)
                    else {}
                )
                expected_source_refs = {
                    "candidate_matrix_ref": EXECUTION_ADMISSION_CANDIDATE_MATRIX_REL,
                    "preflight_contracts_ref": EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_REL,
                    "preflight_proof_packages_ref": EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_REL,
                    "readiness_rollup_ref": EXECUTION_ADMISSION_READINESS_ROLLUP_REL,
                    "dry_run_plan_ref": RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_REL,
                    "noop_receipt_status_ref": "examples/execution-admission/release_candidate_package_receipt_noop_execution_admission_decision_approved.json",
                }
                for field, expected_path in expected_source_refs.items():
                    actual_ref = str(source_artifacts.get(field, "")).replace("\\", "/").strip()
                    if not actual_ref:
                        failures.append(
                            "release candidate publication dry-run receipt contract source_artifacts is missing field: "
                            f"{field}"
                        )
                        continue
                    if actual_ref != expected_path:
                        failures.append(
                            "release candidate publication dry-run receipt contract source_artifacts field has unexpected path: "
                            f"{field} -> {actual_ref}"
                        )

                source_status = (
                    receipt_contract.get("source_artifact_validation_status")
                    if isinstance(receipt_contract.get("source_artifact_validation_status"), dict)
                    else {}
                )
                for field in (
                    "candidate_matrix_status",
                    "preflight_contracts_status",
                    "preflight_proof_packages_status",
                    "readiness_rollup_status",
                    "dry_run_plan_status",
                    "production_readiness_status",
                    "noop_receipt_status",
                ):
                    if str(source_status.get(field, "")).strip() != "pass":
                        failures.append(
                            "release candidate publication dry-run receipt contract source_artifact_validation_status must keep field pass: "
                            f"{field}"
                        )

                alignment = (
                    receipt_contract.get("readiness_rollup_alignment")
                    if isinstance(receipt_contract.get("readiness_rollup_alignment"), dict)
                    else {}
                )
                if (
                    str(alignment.get("safest_next_preparation_slice_id", "")).strip()
                    != EXPECTED_ROLLUP_NEXT_SLICE_ID
                ):
                    failures.append(
                        "release candidate publication dry-run receipt contract readiness_rollup_alignment must keep safest_next_preparation_slice_id=candidate_specific_dry_run_planning_v1."
                    )
                if (
                    str(alignment.get("safest_next_preparation_candidate_id", "")).strip()
                    != EXPECTED_ROLLUP_NEXT_SLICE_CANDIDATE_ID
                ):
                    failures.append(
                        "release candidate publication dry-run receipt contract readiness_rollup_alignment must keep safest_next_preparation_candidate_id=release_candidate_package_publish_dry_run_v1."
                    )
                if str(alignment.get("alignment_status", "")).strip() != "aligned":
                    failures.append(
                        "release candidate publication dry-run receipt contract readiness_rollup_alignment must keep alignment_status=aligned."
                    )

                plan_alignment = (
                    receipt_contract.get("dry_run_plan_alignment")
                    if isinstance(receipt_contract.get("dry_run_plan_alignment"), dict)
                    else {}
                )
                if (
                    str(plan_alignment.get("planned_candidate_id", "")).strip()
                    != EXPECTED_ROLLUP_NEXT_SLICE_CANDIDATE_ID
                ):
                    failures.append(
                        "release candidate publication dry-run receipt contract dry_run_plan_alignment must keep planned_candidate_id=release_candidate_package_publish_dry_run_v1."
                    )
                if str(plan_alignment.get("alignment_status", "")).strip() != "aligned":
                    failures.append(
                        "release candidate publication dry-run receipt contract dry_run_plan_alignment must keep alignment_status=aligned."
                    )
            except Exception as exc:  # pragma: no cover - defensive failure surface
                failures.append(
                    "release candidate publication dry-run receipt contract is not valid JSON: "
                    f"{exc}"
                )

    if release_candidate_publication_dry_run_admission_blockers.exists():
        try:
            admission_blockers = json.loads(
                release_candidate_publication_dry_run_admission_blockers.read_text(
                    encoding="utf-8-sig"
                )
            )
            if admission_blockers.get("schema_version") != "1.0.0":
                failures.append(
                    "release candidate publication dry-run admission blockers schema_version must be 1.0.0."
                )
            if (
                admission_blockers.get("record_type")
                != "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_ADMISSION_BLOCKERS_v1"
            ):
                failures.append(
                    "release candidate publication dry-run admission blockers record_type must be RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_ADMISSION_BLOCKERS_v1."
                )
            if (
                str(admission_blockers.get("candidate_id", "")).strip()
                != EXPECTED_ROLLUP_NEXT_SLICE_CANDIDATE_ID
            ):
                failures.append(
                    "release candidate publication dry-run admission blockers candidate_id must be release_candidate_package_publish_dry_run_v1."
                )
            if str(admission_blockers.get("candidate_type", "")).strip() != "dry_run":
                failures.append(
                    "release candidate publication dry-run admission blockers candidate_type must be dry_run."
                )
            if str(admission_blockers.get("checklist_status", "")).strip() != EXPECTED_DRY_RUN_ADMISSION_BLOCKERS_STATUS:
                failures.append(
                    "release candidate publication dry-run admission blockers must keep checklist_status=static_checklist_valid_blocked."
                )
            if str(admission_blockers.get("admission_status", "")).strip() != "unadmitted":
                failures.append(
                    "release candidate publication dry-run admission blockers admission_status must remain unadmitted."
                )
            if bool(admission_blockers.get("ready_to_request_approval", False)):
                failures.append(
                    "release candidate publication dry-run admission blockers must keep ready_to_request_approval=false."
                )
            approval_review_ready = admission_blockers.get("approval_review_ready")
            if approval_review_ready is True or str(approval_review_ready).strip().lower() == "true":
                failures.append(
                    "release candidate publication dry-run admission blockers must keep approval_review_ready=false/blocked."
                )
            for field in (
                "dry_run_admitted",
                "receipt_issued",
                "publication_admitted",
                "real_execution_admitted",
                "production_ready_claimed",
            ):
                if bool(admission_blockers.get(field, False)):
                    failures.append(
                        "release candidate publication dry-run admission blockers must keep field false: "
                        f"{field}"
                    )
            if (
                str(admission_blockers.get("approval_phrase_required", "")).strip()
                != EXPECTED_DRY_RUN_PLAN_APPROVAL_PHRASE
            ):
                failures.append(
                    "release candidate publication dry-run admission blockers must keep exact approval phrase for release_candidate_package_publish_dry_run_v1."
                )
            approval_decision_reference = admission_blockers.get("approval_decision_reference")
            if isinstance(approval_decision_reference, str) and approval_decision_reference.strip():
                failures.append(
                    "release candidate publication dry-run admission blockers approval_decision_reference must be null/empty while unadmitted."
                )

            prerequisite_checklist = (
                admission_blockers.get("prerequisite_checklist")
                if isinstance(admission_blockers.get("prerequisite_checklist"), dict)
                else {}
            )
            expected_prerequisite_values = {
                "candidate_matrix_entry_present": True,
                "preflight_contract_present": True,
                "preflight_proof_package_present": True,
                "readiness_rollup_present": True,
                "dry_run_plan_present": True,
                "dry_run_receipt_contract_present": True,
                "blocked_unissued_receipt_example_present": True,
                "production_readiness_report_present": True,
                "noop_receipt_status_present": True,
                "source_artifact_validations_pass": True,
                "approval_decision_present": False,
                "dry_run_runner_admitted": False,
                "dry_run_executed": False,
                "dry_run_receipt_issued": False,
                "rollback_cleanup_evidence_present": False,
                "publication_surfaces_blocked": True,
                "execution_surfaces_blocked": True,
                "production_ready_claimed": False,
            }
            for key, expected_value in expected_prerequisite_values.items():
                if key not in prerequisite_checklist:
                    failures.append(
                        "release candidate publication dry-run admission blockers prerequisite_checklist is missing key: "
                        f"{key}"
                    )
                    continue
                if prerequisite_checklist.get(key) is not expected_value:
                    failures.append(
                        "release candidate publication dry-run admission blockers prerequisite_checklist has unexpected value: "
                        f"{key}"
                    )

            for key in (
                "admission_blockers",
                "approval_blockers",
                "evidence_blockers",
                "receipt_blockers",
                "rollback_or_cleanup_blockers",
                "publication_blockers",
                "execution_blockers",
            ):
                values = {
                    str(item).strip()
                    for item in (admission_blockers.get(key) or [])
                    if str(item).strip()
                }
                if not values:
                    failures.append(
                        "release candidate publication dry-run admission blockers list must be non-empty: "
                        f"{key}"
                    )
                if key == "admission_blockers":
                    for required_token in REQUIRED_DRY_RUN_ADMISSION_BLOCKERS:
                        if required_token not in values:
                            failures.append(
                                "release candidate publication dry-run admission blockers admission_blockers must include: "
                                f"{required_token}"
                            )

            if bool(admission_blockers.get("unsafe_claims_detected", False)):
                failures.append(
                    "release candidate publication dry-run admission blockers must keep unsafe_claims_detected=false."
                )

            source_artifacts = (
                admission_blockers.get("source_artifacts")
                if isinstance(admission_blockers.get("source_artifacts"), dict)
                else {}
            )
            expected_source_refs = {
                "candidate_matrix_ref": EXECUTION_ADMISSION_CANDIDATE_MATRIX_REL,
                "preflight_contracts_ref": EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_REL,
                "preflight_proof_packages_ref": EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_REL,
                "readiness_rollup_ref": EXECUTION_ADMISSION_READINESS_ROLLUP_REL,
                "dry_run_plan_ref": RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_REL,
                "dry_run_receipt_contract_ref": RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_CONTRACT_REL,
                "blocked_unissued_receipt_ref": RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_BLOCKED_REL,
                "production_readiness_report_ref": "examples/production-readiness-report/max_biped_v1_production_readiness_report_pass.json",
                "noop_receipt_status_ref": "examples/execution-admission/release_candidate_package_receipt_noop_execution_admission_decision_approved.json",
            }
            for field, expected_path in expected_source_refs.items():
                actual_ref = str(source_artifacts.get(field, "")).replace("\\", "/").strip()
                if not actual_ref:
                    failures.append(
                        "release candidate publication dry-run admission blockers source_artifacts is missing field: "
                        f"{field}"
                    )
                    continue
                if actual_ref != expected_path:
                    failures.append(
                        "release candidate publication dry-run admission blockers source_artifacts field has unexpected path: "
                        f"{field} -> {actual_ref}"
                    )

            source_status = (
                admission_blockers.get("source_artifact_validation_status")
                if isinstance(admission_blockers.get("source_artifact_validation_status"), dict)
                else {}
            )
            for field in (
                "candidate_matrix_status",
                "preflight_contracts_status",
                "preflight_proof_packages_status",
                "readiness_rollup_status",
                "dry_run_plan_status",
                "dry_run_receipt_contract_status",
                "blocked_unissued_receipt_status",
                "production_readiness_status",
                "noop_receipt_status",
            ):
                if str(source_status.get(field, "")).strip() != "pass":
                    failures.append(
                        "release candidate publication dry-run admission blockers source_artifact_validation_status must keep field pass: "
                        f"{field}"
                    )
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(
                "release candidate publication dry-run admission blockers is not valid JSON: "
                f"{exc}"
            )

    if release_candidate_publication_dry_run_operator_approval_packet.exists():
        try:
            operator_packet = json.loads(
                release_candidate_publication_dry_run_operator_approval_packet.read_text(
                    encoding="utf-8-sig"
                )
            )
            if operator_packet.get("schema_version") != "1.0.0":
                failures.append(
                    "release candidate publication dry-run operator approval packet schema_version must be 1.0.0."
                )
            if (
                operator_packet.get("record_type")
                != "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_OPERATOR_APPROVAL_PACKET_v1"
            ):
                failures.append(
                    "release candidate publication dry-run operator approval packet record_type must be RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_OPERATOR_APPROVAL_PACKET_v1."
                )
            if (
                str(operator_packet.get("candidate_id", "")).strip()
                != EXPECTED_ROLLUP_NEXT_SLICE_CANDIDATE_ID
            ):
                failures.append(
                    "release candidate publication dry-run operator approval packet candidate_id must be release_candidate_package_publish_dry_run_v1."
                )
            if str(operator_packet.get("candidate_type", "")).strip() != "dry_run":
                failures.append(
                    "release candidate publication dry-run operator approval packet candidate_type must be dry_run."
                )
            if (
                str(operator_packet.get("approval_packet_status", "")).strip()
                != EXPECTED_DRY_RUN_OPERATOR_APPROVAL_PACKET_STATUS
            ):
                failures.append(
                    "release candidate publication dry-run operator approval packet must keep approval_packet_status=static_template_valid_blocked."
                )
            if str(operator_packet.get("admission_status", "")).strip() != "unadmitted":
                failures.append(
                    "release candidate publication dry-run operator approval packet admission_status must remain unadmitted."
                )
            for field in (
                "approval_request_ready",
                "operator_approval_granted",
                "approval_phrase_present",
                "dry_run_admitted",
                "receipt_issued",
                "publication_admitted",
                "real_execution_admitted",
                "production_ready_claimed",
            ):
                if bool(operator_packet.get(field, False)):
                    failures.append(
                        "release candidate publication dry-run operator approval packet must keep field false: "
                        f"{field}"
                    )
            if (
                str(operator_packet.get("approval_phrase_required", "")).strip()
                != EXPECTED_DRY_RUN_PLAN_APPROVAL_PHRASE
            ):
                failures.append(
                    "release candidate publication dry-run operator approval packet must keep exact approval phrase for release_candidate_package_publish_dry_run_v1."
                )
            approval_decision_reference = operator_packet.get("approval_decision_reference")
            if isinstance(approval_decision_reference, str) and approval_decision_reference.strip():
                failures.append(
                    "release candidate publication dry-run operator approval packet approval_decision_reference must be null/empty while unadmitted."
                )

            approval_decision_fields = (
                operator_packet.get("approval_decision_fields")
                if isinstance(operator_packet.get("approval_decision_fields"), dict)
                else {}
            )
            for key, value in approval_decision_fields.items():
                if isinstance(value, str):
                    if value.strip():
                        failures.append(
                            "release candidate publication dry-run operator approval packet approval_decision_fields must remain empty: "
                            f"{key}"
                        )
                elif value is not None:
                    failures.append(
                        "release candidate publication dry-run operator approval packet approval_decision_fields must remain null/empty: "
                        f"{key}"
                    )

            for key in (
                "operator_review_summary",
                "approval_blocker_summary",
                "required_operator_review_items",
                "required_validation_commands",
                "rollback_or_cleanup_expectations",
                "blocked_surface_attestations",
                "forbidden_actions",
                "forbidden_outputs",
                "forbidden_paths",
                "required_post_approval_controls",
            ):
                values = {
                    str(item).strip()
                    for item in (operator_packet.get(key) or [])
                    if str(item).strip()
                }
                if not values:
                    failures.append(
                        "release candidate publication dry-run operator approval packet list must be non-empty: "
                        f"{key}"
                    )

            operator_decision_options = (
                operator_packet.get("operator_decision_options")
                if isinstance(operator_packet.get("operator_decision_options"), dict)
                else {}
            )
            default_option = str(operator_decision_options.get("default_option", "")).strip()
            if default_option != "do_not_approve":
                failures.append(
                    "release candidate publication dry-run operator approval packet operator_decision_options.default_option must remain do_not_approve."
                )

            required_validation_commands = {
                str(item).strip()
                for item in (operator_packet.get("required_validation_commands") or [])
                if str(item).strip()
            }
            for command_path in (
                "tools/execution-admission/validate_execution_admission_candidate_matrix.py",
                "tools/execution-admission/validate_execution_admission_preflight_contracts.py",
                "tools/execution-admission/validate_execution_admission_preflight_proof_packages.py",
                "tools/execution-admission/validate_execution_admission_readiness_rollup.py",
                "tools/execution-admission/validate_release_candidate_publication_dry_run_plan.py",
                "tools/execution-admission/validate_release_candidate_publication_dry_run_receipt.py",
                "tools/execution-admission/validate_release_candidate_publication_dry_run_admission_blockers.py",
                "tools/audit/verify_sandbox_writer_safety.py",
                "tools/release-lane/prove_pilot_release_chain.py",
            ):
                if command_path not in required_validation_commands:
                    failures.append(
                        "release candidate publication dry-run operator approval packet required_validation_commands must include: "
                        f"{command_path}"
                    )

            forbidden_paths = {
                str(item).strip()
                for item in (operator_packet.get("forbidden_paths") or [])
                if str(item).strip()
            }
            for token in (
                "production_path_category",
                "engine_path_category",
                "cache_live_db_category",
                "destructive_cleanup_category",
            ):
                if token not in forbidden_paths:
                    failures.append(
                        "release candidate publication dry-run operator approval packet forbidden_paths must include: "
                        f"{token}"
                    )

            forbidden_outputs = {
                str(item).strip()
                for item in (operator_packet.get("forbidden_outputs") or [])
                if str(item).strip()
            }
            for token in (
                "publish_operation",
                "spawn_operation",
                "production_path_writes",
                "engine_path_writes",
                "cache_live_db_access",
                "authoritative_source_uuid_claims",
                "authoritative_asset_id_claims",
                "authoritative_product_id_claims",
            ):
                if token not in forbidden_outputs:
                    failures.append(
                        "release candidate publication dry-run operator approval packet forbidden_outputs must include: "
                        f"{token}"
                    )

            source_artifacts = (
                operator_packet.get("source_artifacts")
                if isinstance(operator_packet.get("source_artifacts"), dict)
                else {}
            )
            expected_source_refs = {
                "candidate_matrix_ref": EXECUTION_ADMISSION_CANDIDATE_MATRIX_REL,
                "preflight_contracts_ref": EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_REL,
                "preflight_proof_packages_ref": EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_REL,
                "readiness_rollup_ref": EXECUTION_ADMISSION_READINESS_ROLLUP_REL,
                "dry_run_plan_ref": RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_REL,
                "dry_run_receipt_contract_ref": RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_CONTRACT_REL,
                "blocked_unissued_receipt_ref": RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_BLOCKED_REL,
                "admission_blocker_checklist_ref": RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_ADMISSION_BLOCKERS_REL,
                "production_readiness_report_ref": "examples/production-readiness-report/max_biped_v1_production_readiness_report_pass.json",
                "noop_receipt_status_ref": "examples/execution-admission/release_candidate_package_receipt_noop_execution_admission_decision_approved.json",
            }
            for field, expected_path in expected_source_refs.items():
                actual_ref = str(source_artifacts.get(field, "")).replace("\\", "/").strip()
                if not actual_ref:
                    failures.append(
                        "release candidate publication dry-run operator approval packet source_artifacts is missing field: "
                        f"{field}"
                    )
                    continue
                if actual_ref != expected_path:
                    failures.append(
                        "release candidate publication dry-run operator approval packet source_artifacts field has unexpected path: "
                        f"{field} -> {actual_ref}"
                    )

            source_status = (
                operator_packet.get("source_artifact_validation_status")
                if isinstance(operator_packet.get("source_artifact_validation_status"), dict)
                else {}
            )
            for field in (
                "candidate_matrix_status",
                "preflight_contracts_status",
                "preflight_proof_packages_status",
                "readiness_rollup_status",
                "dry_run_plan_status",
                "dry_run_receipt_contract_status",
                "blocked_unissued_receipt_status",
                "admission_blocker_checklist_status",
                "production_readiness_status",
                "noop_receipt_status",
            ):
                if str(source_status.get(field, "")).strip() != "pass":
                    failures.append(
                        "release candidate publication dry-run operator approval packet source_artifact_validation_status must keep field pass: "
                        f"{field}"
                    )

            expected_future_receipt_contract = (
                operator_packet.get("expected_future_receipt_contract")
                if isinstance(operator_packet.get("expected_future_receipt_contract"), dict)
                else {}
            )
            if (
                str(expected_future_receipt_contract.get("receipt_type", "")).strip()
                != EXPECTED_DRY_RUN_RECEIPT_TYPE
            ):
                failures.append(
                    "release candidate publication dry-run operator approval packet expected_future_receipt_contract.receipt_type must keep release_candidate_package_publish_dry_run_receipt_v1."
                )
            if (
                str(
                    expected_future_receipt_contract.get(
                        "receipt_contract_status_expected", ""
                    )
                ).strip()
                != EXPECTED_DRY_RUN_RECEIPT_CONTRACT_STATUS
            ):
                failures.append(
                    "release candidate publication dry-run operator approval packet expected_future_receipt_contract.receipt_contract_status_expected must keep static_contract_valid_blocked."
                )

            safety_posture = (
                operator_packet.get("safety_posture")
                if isinstance(operator_packet.get("safety_posture"), dict)
                else {}
            )
            for field in (
                "source_uuid_status",
                "asset_id_status",
                "product_id_status",
            ):
                if str(safety_posture.get(field, "")).strip() != "not_authoritative":
                    failures.append(
                        "release candidate publication dry-run operator approval packet safety_posture must keep not_authoritative: "
                        f"{field}"
                    )
            if bool(operator_packet.get("unsafe_claims_detected", False)):
                failures.append(
                    "release candidate publication dry-run operator approval packet must keep unsafe_claims_detected=false."
                )
        except Exception as exc:  # pragma: no cover - defensive failure surface
            failures.append(
                "release candidate publication dry-run operator approval packet is not valid JSON: "
                f"{exc}"
            )

    return failures
