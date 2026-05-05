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
AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUILD_REL = (
    "scripts/powershell/Invoke-MaxineApSourceFileDiagnosticPreflightBuild.ps1"
)
AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_INSPECT_REL = (
    "scripts/powershell/Invoke-MaxineApSourceFileDiagnosticPreflightInspect.ps1"
)
AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUNDLE_EXPORT_REL = (
    "scripts/powershell/Invoke-MaxineApSourceFileDiagnosticPreflightBundleExport.ps1"
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
AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_SCHEMA_REL = (
    "schemas/maxine_ap_source_file_diagnostic_preflight.schema.json"
)
AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUNDLE_SCHEMA_REL = (
    "schemas/maxine_ap_source_file_diagnostic_preflight_bundle.schema.json"
)
CAPABILITY_MATRIX_REL = "examples/capabilities/maxine-capability-matrix.json"
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
AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHTS_DIR_REL = (
    "examples/sandbox/ap-source-file-diagnostic-preflights"
)
AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUNDLES_DIR_REL = (
    "examples/sandbox/ap-source-file-diagnostic-preflight-bundles"
)

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
    AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUILD_REL,
    AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_INSPECT_REL,
    AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUNDLE_EXPORT_REL,
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

REQUIRED_AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUILD_NEEDLES = [
    "ap-source-file-diagnostic-preflights",
    "source_review_packet_id",
    "source_proposal_id",
    "source_ap_binary_preflight_id",
    "source_real_binary_diagnostic_execution_id",
    "source_project_inventory_id",
    "candidate_relative_path",
    "candidate_sha256",
    "selected_binary_path",
    "binary_kind",
    "proposed_diagnostic_command_display",
    "required_manual_confirmation = $true",
    "local_only = $true",
    "execution_admitted = $false",
    "ready_for_future_source_file_diagnostic_request",
    "blocked_missing_evidence",
    "blocked_safety_boundary",
    "contains parent traversal and is blocked",
    "single_file_not_wildcard",
    "--source-file",
    "--no-execution",
]

REQUIRED_AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_INSPECT_NEEDLES = [
    "preflight_count",
    "source_file_diagnostic_preflight_id",
    "showrequirements",
    "showblockingreasons",
]

REQUIRED_AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUNDLE_EXPORT_NEEDLES = [
    "ap-source-file-diagnostic-preflight-bundles",
    "source_preflight_id",
    "source_review_packet_id",
    "source_proposal_id",
    "source_ap_binary_preflight_id",
    "source_real_binary_diagnostic_execution_id",
    "source_project_inventory_id",
    "included_artifacts",
    "copied_artifact_paths",
    "artifact_sha256",
    "copies json snapshots only",
    "does not copy source assets",
    "does not copy source assets, ap binaries, cache files, assetdb.sqlite",
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
    "ap_source_file_diagnostic_preflight_build": "sandbox_only",
    "ap_source_file_diagnostic_preflight_inspect": "read_only",
    "ap_source_file_diagnostic_preflight_bundle_export": "sandbox_only",
    "real_asset_processor_execution": "blocked",
    "ap_source_file_processing_execution": "blocked",
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
    ap_source_file_diagnostic_preflight_build = (
        root / AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUILD_REL
    )
    ap_source_file_diagnostic_preflight_inspect = (
        root / AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_INSPECT_REL
    )
    ap_source_file_diagnostic_preflight_bundle_export = (
        root / AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUNDLE_EXPORT_REL
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
    ap_source_file_diagnostic_preflight_schema = (
        root / AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_SCHEMA_REL
    )
    ap_source_file_diagnostic_preflight_bundle_schema = (
        root / AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUNDLE_SCHEMA_REL
    )
    capability_matrix = root / CAPABILITY_MATRIX_REL
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
    ap_source_file_diagnostic_preflights_dir = (
        root / AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHTS_DIR_REL
    )
    ap_source_file_diagnostic_preflight_bundles_dir = (
        root / AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUNDLES_DIR_REL
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
    if not ap_source_file_diagnostic_preflight_build.exists():
        failures.append(
            "AP source file diagnostic preflight build command missing: "
            f"{AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUILD_REL}"
        )
    if not ap_source_file_diagnostic_preflight_inspect.exists():
        failures.append(
            "AP source file diagnostic preflight inspect command missing: "
            f"{AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_INSPECT_REL}"
        )
    if not ap_source_file_diagnostic_preflight_bundle_export.exists():
        failures.append(
            "AP source file diagnostic preflight bundle export command missing: "
            f"{AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUNDLE_EXPORT_REL}"
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
    if not ap_source_file_diagnostic_preflight_schema.exists():
        failures.append(
            "AP source file diagnostic preflight schema missing: "
            f"{AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_SCHEMA_REL}"
        )
    if not ap_source_file_diagnostic_preflight_bundle_schema.exists():
        failures.append(
            "AP source file diagnostic preflight bundle schema missing: "
            f"{AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUNDLE_SCHEMA_REL}"
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
    if not ap_source_file_diagnostic_preflights_dir.exists():
        failures.append(
            "AP source file diagnostic preflights directory missing: "
            f"{AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHTS_DIR_REL}"
        )
    if not ap_source_file_diagnostic_preflight_bundles_dir.exists():
        failures.append(
            "AP source file diagnostic preflight bundles directory missing: "
            f"{AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUNDLES_DIR_REL}"
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

    if ap_source_file_diagnostic_preflight_build.exists():
        ap_source_file_diagnostic_preflight_build_text = _read_text(
            ap_source_file_diagnostic_preflight_build
        )
        for needle in REQUIRED_AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUILD_NEEDLES:
            if needle not in ap_source_file_diagnostic_preflight_build_text:
                failures.append(
                    "AP source file diagnostic preflight build command missing required needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "o3de.exe",
            "editor.exe",
            "invoke-expression",
            "start-process",
            "invoke-maxineauthoritativeresolverwrite.ps1",
        ):
            if forbidden_phrase in ap_source_file_diagnostic_preflight_build_text:
                failures.append(
                    "AP source file diagnostic preflight build command contains forbidden phrase: "
                    f"{forbidden_phrase}"
                )
        for forbidden_admission in (
            "execution_admitted = $true",
            "required_manual_confirmation = $false",
            "local_only = $false",
            "product_ids_claimed = $true",
            "asset_ids_claimed = $true",
            "source_uuids_claimed = $true",
            "product_resolution_claimed = $true",
            "cache_access_admitted = $true",
            "live_database_access_admitted = $true",
            "spawn_admitted = $true",
            "publish_admitted = $true",
        ):
            if forbidden_admission in ap_source_file_diagnostic_preflight_build_text:
                failures.append(
                    "AP source file diagnostic preflight build command widens forbidden admission: "
                    f"{forbidden_admission}"
                )
        if (
            "-command" in ap_source_file_diagnostic_preflight_build_text
            and "valuefromremainingarguments" in ap_source_file_diagnostic_preflight_build_text
        ):
            failures.append(
                "AP source file diagnostic preflight build command must not accept arbitrary "
                "command text arguments."
            )

    if ap_source_file_diagnostic_preflight_inspect.exists():
        ap_source_file_diagnostic_preflight_inspect_text = _read_text(
            ap_source_file_diagnostic_preflight_inspect
        )
        for needle in REQUIRED_AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_INSPECT_NEEDLES:
            if needle not in ap_source_file_diagnostic_preflight_inspect_text:
                failures.append(
                    "AP source file diagnostic preflight inspect command missing required needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "o3de.exe",
            "editor.exe",
            "invoke-expression",
            "start-process",
            "invoke-maxineauthoritativeresolverwrite.ps1",
        ):
            if forbidden_phrase in ap_source_file_diagnostic_preflight_inspect_text:
                failures.append(
                    "AP source file diagnostic preflight inspect command contains forbidden phrase: "
                    f"{forbidden_phrase}"
                )
        for needle in MUTATION_NEEDLES:
            if needle in ap_source_file_diagnostic_preflight_inspect_text:
                failures.append(
                    "AP source file diagnostic preflight inspect command is not read-only; "
                    f"contains mutation needle: {needle}"
                )

    if ap_source_file_diagnostic_preflight_bundle_export.exists():
        ap_source_file_diagnostic_preflight_bundle_export_text = _read_text(
            ap_source_file_diagnostic_preflight_bundle_export
        )
        for needle in REQUIRED_AP_SOURCE_FILE_DIAGNOSTIC_PREFLIGHT_BUNDLE_EXPORT_NEEDLES:
            if needle not in ap_source_file_diagnostic_preflight_bundle_export_text:
                failures.append(
                    "AP source file diagnostic preflight bundle export command missing required needle: "
                    f"{needle}"
                )
        for forbidden_phrase in (
            "o3de.exe",
            "editor.exe",
            "invoke-expression",
            "start-process",
            "invoke-maxineauthoritativeresolverwrite.ps1",
        ):
            if forbidden_phrase in ap_source_file_diagnostic_preflight_bundle_export_text:
                failures.append(
                    "AP source file diagnostic preflight bundle export command contains forbidden phrase: "
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
            if f'"{forbidden_copy}"' in ap_source_file_diagnostic_preflight_bundle_export_text:
                failures.append(
                    "AP source file diagnostic preflight bundle export command should not hardcode "
                    "copying binary/source/runtime/cache/database token: "
                    f"{forbidden_copy}"
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
                    "ap_source_file_processing_execution",
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

    return failures
