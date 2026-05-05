#!/usr/bin/env python3
"""Verify sandbox writer skeleton safety boundaries."""

from __future__ import annotations

from pathlib import Path

from sandbox_writer_invariant import collect_sandbox_writer_invariant_failures


REQUIRED_FILES = [
    "scripts/powershell/Invoke-MaxineSandboxResolverWrite.ps1",
    "scripts/powershell/Invoke-MaxineSandboxRollback.ps1",
    "scripts/powershell/Invoke-MaxineSandboxReceiptInspect.ps1",
    "scripts/powershell/Invoke-MaxineSandboxReviewPacketBuild.ps1",
    "scripts/powershell/Invoke-MaxineSandboxReviewPacketInspect.ps1",
    "scripts/powershell/Invoke-MaxineSandboxReviewDecisionRecord.ps1",
    "scripts/powershell/Invoke-MaxineSandboxReviewDecisionInspect.ps1",
    "scripts/powershell/Invoke-MaxineSandboxWorkflowRun.ps1",
    "scripts/powershell/Invoke-MaxineSandboxWorkflowInspect.ps1",
    "scripts/powershell/Invoke-MaxineSandboxEvidenceBundleExport.ps1",
    "scripts/powershell/Invoke-MaxineSandboxOperatorSummary.ps1",
    "scripts/powershell/Invoke-MaxineProjectInventoryRead.ps1",
    "scripts/powershell/Invoke-MaxineProjectInventoryInspect.ps1",
    "scripts/powershell/Invoke-MaxineAssetCandidateInventoryRead.ps1",
    "scripts/powershell/Invoke-MaxineAssetCandidateInventoryInspect.ps1",
    "scripts/powershell/Invoke-MaxineAssetCandidateReviewPacketBuild.ps1",
    "scripts/powershell/Invoke-MaxineAssetCandidateReviewPacketInspect.ps1",
    "scripts/powershell/Invoke-MaxineAssetCandidateEvidenceBundleExport.ps1",
    "scripts/powershell/Invoke-MaxineProductResolutionProposalBuild.ps1",
    "scripts/powershell/Invoke-MaxineProductResolutionProposalInspect.ps1",
    "scripts/powershell/Invoke-MaxineProductResolutionProposalBundleExport.ps1",
    "scripts/powershell/Invoke-MaxineApEvidenceImport.ps1",
    "scripts/powershell/Invoke-MaxineApEvidenceInspect.ps1",
    "scripts/powershell/Invoke-MaxineApEvidenceBundleExport.ps1",
    "scripts/powershell/Invoke-MaxineApExecutionPreflightBuild.ps1",
    "scripts/powershell/Invoke-MaxineApExecutionPreflightInspect.ps1",
    "scripts/powershell/Invoke-MaxineApExecutionPreflightBundleExport.ps1",
    "scripts/powershell/Invoke-MaxineApDiagnosticExecution.ps1",
    "scripts/powershell/Invoke-MaxineApDiagnosticExecutionInspect.ps1",
    "scripts/powershell/Invoke-MaxineApDiagnosticExecutionBundleExport.ps1",
    "scripts/powershell/Invoke-MaxineApBinaryDiscoveryRead.ps1",
    "scripts/powershell/Invoke-MaxineApBinaryDiscoveryInspect.ps1",
    "scripts/powershell/Invoke-MaxineApBinaryPreflightBuild.ps1",
    "scripts/powershell/Invoke-MaxineApRealBinaryDiagnosticExecution.ps1",
    "scripts/powershell/Invoke-MaxineApRealBinaryDiagnosticInspect.ps1",
    "scripts/powershell/Invoke-MaxineApRealBinaryDiagnosticBundleExport.ps1",
    "schemas/maxine_sandbox_resolver_write_plan.schema.json",
    "schemas/maxine_sandbox_write_receipt.schema.json",
    "schemas/maxine_sandbox_receipt_index.schema.json",
    "schemas/maxine_sandbox_review_packet.schema.json",
    "schemas/maxine_sandbox_review_decision.schema.json",
    "schemas/maxine_sandbox_workflow_run.schema.json",
    "schemas/maxine_sandbox_evidence_bundle.schema.json",
    "schemas/maxine_asset_candidate_inventory.schema.json",
    "schemas/maxine_asset_candidate_review_packet.schema.json",
    "schemas/maxine_asset_candidate_evidence_bundle.schema.json",
    "schemas/maxine_product_resolution_proposal.schema.json",
    "schemas/maxine_product_resolution_proposal_bundle.schema.json",
    "schemas/maxine_ap_evidence_import.schema.json",
    "schemas/maxine_ap_evidence_bundle.schema.json",
    "schemas/maxine_ap_execution_preflight.schema.json",
    "schemas/maxine_ap_execution_preflight_bundle.schema.json",
    "schemas/maxine_ap_diagnostic_execution.schema.json",
    "schemas/maxine_ap_diagnostic_execution_bundle.schema.json",
    "schemas/maxine_ap_binary_discovery.schema.json",
    "schemas/maxine_ap_binary_preflight.schema.json",
    "schemas/maxine_ap_real_binary_diagnostic_execution.schema.json",
    "schemas/maxine_ap_real_binary_diagnostic_bundle.schema.json",
    "schemas/maxine_dcc_conform_report.schema.json",
    "schemas/maxine_material_uv_qc_report.schema.json",
    "schemas/maxine_animation_smoke_report.schema.json",
    "schemas/maxine_source_product_evidence_resolver_report.schema.json",
    "schemas/maxine_manifest_qc_attachment.schema.json",
    "schemas/maxine_capability_matrix.schema.json",
    "examples/sandbox/receipts/index.json",
    "examples/sandbox/evidence-bundles/.gitkeep",
    "examples/sandbox/operator-reports/.gitkeep",
    "examples/sandbox/project-inventory/.gitkeep",
    "examples/sandbox/asset-candidates/.gitkeep",
    "examples/sandbox/asset-candidate-review-packets/.gitkeep",
    "examples/sandbox/asset-candidate-evidence-bundles/.gitkeep",
    "examples/sandbox/product-resolution-proposals/.gitkeep",
    "examples/sandbox/product-resolution-proposal-bundles/.gitkeep",
    "examples/sandbox/ap-evidence-imports/.gitkeep",
    "examples/sandbox/ap-evidence-bundles/.gitkeep",
    "examples/sandbox/ap-execution-preflights/.gitkeep",
    "examples/sandbox/ap-execution-preflight-bundles/.gitkeep",
    "examples/sandbox/ap-diagnostic-executions",
    "examples/sandbox/ap-diagnostic-execution-bundles",
    "examples/sandbox/ap-binary-discovery/.gitkeep",
    "examples/sandbox/ap-binary-preflights/.gitkeep",
    "examples/sandbox/ap-real-binary-diagnostic-executions/.gitkeep",
    "examples/sandbox/ap-real-binary-diagnostic-bundles/.gitkeep",
    "examples/dcc-conform/max_biped_v1_conform_pass.json",
    "examples/dcc-conform/max_biped_v1_conform_warn.json",
    "examples/dcc-conform/max_biped_v1_conform_fail.json",
    "examples/material-uv-qc/max_biped_v1_material_uv_pass.json",
    "examples/material-uv-qc/max_biped_v1_material_uv_warn.json",
    "examples/material-uv-qc/max_biped_v1_material_uv_fail.json",
    "examples/animation-smoke/max_biped_v1_animation_smoke_pass.json",
    "examples/animation-smoke/max_biped_v1_animation_smoke_warn.json",
    "examples/animation-smoke/max_biped_v1_animation_smoke_fail.json",
    "examples/source-product-evidence-resolver/max_biped_v1_source_product_resolver_pass.json",
    "examples/source-product-evidence-resolver/max_biped_v1_source_product_resolver_warn.json",
    "examples/source-product-evidence-resolver/max_biped_v1_source_product_resolver_fail.json",
    "examples/manifest-qc-attachments/max_biped_v1_skeleton_attach_pass.json",
    "examples/manifest-qc-attachments/max_biped_v1_dcc_conform_attach_warn.json",
    "examples/manifest-qc-attachments/max_biped_v1_source_product_attach_fail.json",
    "examples/manifests/example-release-character-qc-attach-base.manifest.json",
    "examples/capabilities/maxine-capability-matrix.json",
    "examples/sandbox/review-packets/.gitkeep",
    "examples/sandbox/review-decisions/.gitkeep",
    "examples/sandbox/workflow-runs/.gitkeep",
    "examples/sandbox/staging/.gitkeep",
    "tools/dcc-conform/validate_dcc_conform_report.py",
    "docs/maxine/specs/dcc-conform-v1.md",
    "tools/material-uv-qc/validate_material_uv_qc_report.py",
    "docs/maxine/specs/material-uv-qc-v1.md",
    "tools/animation-smoke/validate_animation_smoke_report.py",
    "docs/maxine/specs/animation-smoke-v1.md",
    "tools/source-product-evidence-resolver/validate_source_product_evidence_resolver_report.py",
    "docs/maxine/specs/source-product-evidence-resolver-v1.md",
    "tools/manifest-validator/attach_qc_gate.py",
    "docs/maxine/specs/manifest-qc-attachment-pipeline-v1.md",
    "docs/maxine/release-lane-gate-chain-v1.md",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def check_exists(root: Path, rel_paths: list[str], failures: list[str]) -> None:
    for rel in rel_paths:
        if not (root / rel).exists():
            failures.append(f"missing required file: {rel}")


def main() -> int:
    root = repo_root()
    failures: list[str] = []

    check_exists(root, REQUIRED_FILES, failures)
    failures.extend(collect_sandbox_writer_invariant_failures(root))

    if failures:
        print("FAIL: sandbox writer safety verification failed.")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("PASS: sandbox writer admitted-only safety verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
