Describe "Maxine Manifest Repository Baseline" {
    It "has schema file" {
        Test-Path -LiteralPath "schemas/maxine_job_manifest.schema.json" | Should Be $true
    }

    It "has example manifest file" {
        Test-Path -LiteralPath "examples/manifests/example-draft-mesh.manifest.json" | Should Be $true
    }

    It "has manifest validator script" {
        Test-Path -LiteralPath "tools/manifest-validator/validate_manifest.py" | Should Be $true
    }

    It "has New-MaxineManifest adapter script" {
        Test-Path -LiteralPath "scripts/powershell/New-MaxineManifest.ps1" | Should Be $true
    }

    It "has Write-MaxineEvidence adapter script" {
        Test-Path -LiteralPath "scripts/powershell/Write-MaxineEvidence.ps1" | Should Be $true
    }

    It "has Invoke-MaxineJob adapter script" {
        Test-Path -LiteralPath "scripts/powershell/Invoke-MaxineJob.ps1" | Should Be $true
    }

    It "has asset resolver python script" {
        Test-Path -LiteralPath "tools/asset-resolver/resolve_asset_contract.py" | Should Be $true
    }

    It "has asset resolver product contracts file" {
        Test-Path -LiteralPath "tools/asset-resolver/product_contracts.json" | Should Be $true
    }

    It "has Resolve-MaxineAssetContract wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Resolve-MaxineAssetContract.ps1" | Should Be $true
    }

    It "has filesystem probe python script" {
        Test-Path -LiteralPath "tools/asset-resolver/probe_o3de_asset_filesystem.py" | Should Be $true
    }

    It "has Probe-MaxineO3deAsset wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Probe-MaxineO3deAsset.ps1" | Should Be $true
    }

    It "has asset probe example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-asset-probe.manifest.json" | Should Be $true
    }

    It "has asset probe example job file" {
        Test-Path -LiteralPath "examples/jobs/example-asset-probe-job.json" | Should Be $true
    }

    It "has AP metadata discovery python script" {
        Test-Path -LiteralPath "tools/asset-resolver/discover_ap_metadata_sources.py" | Should Be $true
    }

    It "has Find-MaxineApMetadata wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Find-MaxineApMetadata.ps1" | Should Be $true
    }

    It "has AP metadata candidates file" {
        Test-Path -LiteralPath "tools/asset-resolver/ap_metadata_candidates.json" | Should Be $true
    }

    It "has AP metadata discovery example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-ap-metadata-discovery.manifest.json" | Should Be $true
    }

    It "has AP metadata discovery example job file" {
        Test-Path -LiteralPath "examples/jobs/example-ap-metadata-discovery-job.json" | Should Be $true
    }

    It "has AP DB schema inspection python script" {
        Test-Path -LiteralPath "tools/asset-resolver/inspect_ap_database_schema.py" | Should Be $true
    }

    It "has Inspect-MaxineApDatabase wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Inspect-MaxineApDatabase.ps1" | Should Be $true
    }

    It "has AP DB schema inspection example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-ap-database-inspection.manifest.json" | Should Be $true
    }

    It "has AP DB schema inspection example job file" {
        Test-Path -LiteralPath "examples/jobs/example-ap-database-inspection-job.json" | Should Be $true
    }

    It "has AP row mapping python script" {
        Test-Path -LiteralPath "tools/asset-resolver/map_ap_source_product_rows.py" | Should Be $true
    }

    It "has Map-MaxineApRows wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Map-MaxineApRows.ps1" | Should Be $true
    }

    It "has AP row mapping example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-ap-row-mapping.manifest.json" | Should Be $true
    }

    It "has AP row mapping example job file" {
        Test-Path -LiteralPath "examples/jobs/example-ap-row-mapping-job.json" | Should Be $true
    }

    It "has AP source identity matching python script" {
        Test-Path -LiteralPath "tools/asset-resolver/match_ap_source_identity.py" | Should Be $true
    }

    It "has Match-MaxineApSourceIdentity wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Match-MaxineApSourceIdentity.ps1" | Should Be $true
    }

    It "has AP source identity matching example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-ap-source-identity-match.manifest.json" | Should Be $true
    }

    It "has AP source identity matching example job file" {
        Test-Path -LiteralPath "examples/jobs/example-ap-source-identity-match-job.json" | Should Be $true
    }

    It "has AP candidate product matching python script" {
        Test-Path -LiteralPath "tools/asset-resolver/match_ap_product_candidates.py" | Should Be $true
    }

    It "has Match-MaxineApProductCandidates wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Match-MaxineApProductCandidates.ps1" | Should Be $true
    }

    It "has AP candidate product matching example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-ap-product-candidate-match.manifest.json" | Should Be $true
    }

    It "has AP candidate product matching example job file" {
        Test-Path -LiteralPath "examples/jobs/example-ap-product-candidate-match-job.json" | Should Be $true
    }

    It "has AP product file validation python script" {
        Test-Path -LiteralPath "tools/asset-resolver/validate_ap_product_files.py" | Should Be $true
    }

    It "has Validate-MaxineApProductFiles wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Validate-MaxineApProductFiles.ps1" | Should Be $true
    }

    It "has AP product file validation example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-ap-product-file-validation.manifest.json" | Should Be $true
    }

    It "has AP product file validation example job file" {
        Test-Path -LiteralPath "examples/jobs/example-ap-product-file-validation-job.json" | Should Be $true
    }

    It "has AP resolver readiness python script" {
        Test-Path -LiteralPath "tools/asset-resolver/evaluate_ap_resolver_readiness.py" | Should Be $true
    }

    It "has Evaluate-MaxineApResolverReadiness wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Evaluate-MaxineApResolverReadiness.ps1" | Should Be $true
    }

    It "has AP resolver readiness example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-ap-resolver-readiness.manifest.json" | Should Be $true
    }

    It "has AP resolver readiness example job file" {
        Test-Path -LiteralPath "examples/jobs/example-ap-resolver-readiness-job.json" | Should Be $true
    }

    It "has authoritative resolver dry-run planner script" {
        Test-Path -LiteralPath "tools/asset-resolver/plan_authoritative_resolution.py" | Should Be $true
    }

    It "has Plan-MaxineAuthoritativeResolution wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Plan-MaxineAuthoritativeResolution.ps1" | Should Be $true
    }

    It "has authoritative resolver plan schema" {
        Test-Path -LiteralPath "schemas/maxine_authoritative_resolver_plan.schema.json" | Should Be $true
    }

    It "has authoritative resolver example plan manifest" {
        Test-Path -LiteralPath "examples/manifests/example-authoritative-resolution-plan.json" | Should Be $true
    }

    It "has authoritative resolver example plan job file" {
        Test-Path -LiteralPath "examples/jobs/example-authoritative-resolution-plan-job.json" | Should Be $true
    }

    It "has authoritative resolver design document" {
        Test-Path -LiteralPath "docs/o3de-integration/AUTHORITATIVE-RESOLVER-DESIGN.md" | Should Be $true
    }

    It "has AP job-state proof extractor script" {
        Test-Path -LiteralPath "tools/asset-resolver/extract_ap_job_state_proof.py" | Should Be $true
    }

    It "has Extract-MaxineApJobStateProof wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Extract-MaxineApJobStateProof.ps1" | Should Be $true
    }

    It "has AP job-state proof example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-ap-job-state-proof.manifest.json" | Should Be $true
    }

    It "has AP job-state proof example job file" {
        Test-Path -LiteralPath "examples/jobs/example-ap-job-state-proof-job.json" | Should Be $true
    }

    It "has AP job-state proof design document" {
        Test-Path -LiteralPath "docs/o3de-integration/AP-JOB-STATE-PROOF.md" | Should Be $true
    }

    It "has AP platform proof extractor script" {
        Test-Path -LiteralPath "tools/asset-resolver/extract_ap_platform_proof.py" | Should Be $true
    }

    It "has Extract-MaxineApPlatformProof wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Extract-MaxineApPlatformProof.ps1" | Should Be $true
    }

    It "has AP platform proof example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-ap-platform-proof.manifest.json" | Should Be $true
    }

    It "has AP platform proof example job file" {
        Test-Path -LiteralPath "examples/jobs/example-ap-platform-proof-job.json" | Should Be $true
    }

    It "has AP platform proof design document" {
        Test-Path -LiteralPath "docs/o3de-integration/AP-PLATFORM-PROOF.md" | Should Be $true
    }

    It "has AP product freshness proof extractor script" {
        Test-Path -LiteralPath "tools/asset-resolver/extract_ap_product_freshness_proof.py" | Should Be $true
    }

    It "has Extract-MaxineApProductFreshnessProof wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Extract-MaxineApProductFreshnessProof.ps1" | Should Be $true
    }

    It "has AP product freshness proof example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-ap-product-freshness-proof.manifest.json" | Should Be $true
    }

    It "has AP product freshness proof example job file" {
        Test-Path -LiteralPath "examples/jobs/example-ap-product-freshness-proof-job.json" | Should Be $true
    }

    It "has AP product freshness proof design document" {
        Test-Path -LiteralPath "docs/o3de-integration/AP-PRODUCT-FRESHNESS-PROOF.md" | Should Be $true
    }

    It "has AP product identity proof extractor script" {
        Test-Path -LiteralPath "tools/asset-resolver/extract_ap_product_identity_proof.py" | Should Be $true
    }

    It "has Extract-MaxineApProductIdentityProof wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Extract-MaxineApProductIdentityProof.ps1" | Should Be $true
    }

    It "has AP product identity proof example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-ap-product-identity-proof.manifest.json" | Should Be $true
    }

    It "has AP product identity proof example job file" {
        Test-Path -LiteralPath "examples/jobs/example-ap-product-identity-proof-job.json" | Should Be $true
    }

    It "has AP product identity proof design document" {
        Test-Path -LiteralPath "docs/o3de-integration/AP-PRODUCT-IDENTITY-PROOF.md" | Should Be $true
    }

    It "has authoritative write protocol proposal script" {
        Test-Path -LiteralPath "tools/asset-resolver/propose_authoritative_write_protocol.py" | Should Be $true
    }

    It "has Propose-MaxineAuthoritativeWriteProtocol wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Propose-MaxineAuthoritativeWriteProtocol.ps1" | Should Be $true
    }

    It "has authoritative write protocol proposal schema" {
        Test-Path -LiteralPath "schemas/maxine_authoritative_write_protocol.schema.json" | Should Be $true
    }

    It "has authoritative write protocol proposal example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-authoritative-write-protocol-proposal.json" | Should Be $true
    }

    It "has authoritative write protocol proposal example job file" {
        Test-Path -LiteralPath "examples/jobs/example-authoritative-write-protocol-job.json" | Should Be $true
    }

    It "has authoritative write protocol design document" {
        Test-Path -LiteralPath "docs/o3de-integration/AUTHORITATIVE-WRITE-PROTOCOL.md" | Should Be $true
    }

    It "has operator approval validation script" {
        Test-Path -LiteralPath "tools/asset-resolver/validate_operator_approval.py" | Should Be $true
    }

    It "has Validate-MaxineOperatorApproval wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Validate-MaxineOperatorApproval.ps1" | Should Be $true
    }

    It "has operator approval schema" {
        Test-Path -LiteralPath "schemas/maxine_operator_approval.schema.json" | Should Be $true
    }

    It "has operator approval example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-operator-approval.json" | Should Be $true
    }

    It "has operator approval validation example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-operator-approval-validation.json" | Should Be $true
    }

    It "has operator approval validation example job file" {
        Test-Path -LiteralPath "examples/jobs/example-operator-approval-validation-job.json" | Should Be $true
    }

    It "has operator approval protocol document" {
        Test-Path -LiteralPath "docs/o3de-integration/OPERATOR-APPROVAL-PROTOCOL.md" | Should Be $true
    }

    It "has pre-write report builder script" {
        Test-Path -LiteralPath "tools/asset-resolver/build_pre_write_report.py" | Should Be $true
    }

    It "has Build-MaxinePreWriteReport wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Build-MaxinePreWriteReport.ps1" | Should Be $true
    }

    It "has pre-write report schema" {
        Test-Path -LiteralPath "schemas/maxine_pre_write_report.schema.json" | Should Be $true
    }

    It "has pre-write report example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-pre-write-report.json" | Should Be $true
    }

    It "has pre-write report example job file" {
        Test-Path -LiteralPath "examples/jobs/example-pre-write-report-job.json" | Should Be $true
    }

    It "has approved-write dry-run report document" {
        Test-Path -LiteralPath "docs/o3de-integration/APPROVED-WRITE-DRY-RUN-REPORT.md" | Should Be $true
    }

    It "has execution gate policy validator script" {
        Test-Path -LiteralPath "tools/asset-resolver/validate_execution_gate_policy.py" | Should Be $true
    }

    It "has Validate-MaxineExecutionGatePolicy wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Validate-MaxineExecutionGatePolicy.ps1" | Should Be $true
    }

    It "has execution gate policy schema" {
        Test-Path -LiteralPath "schemas/maxine_execution_gate_policy.schema.json" | Should Be $true
    }

    It "has execution gate policy example manifest" {
        Test-Path -LiteralPath "examples/manifests/example-execution-gate-policy.json" | Should Be $true
    }

    It "has execution gate policy example job file" {
        Test-Path -LiteralPath "examples/jobs/example-execution-gate-policy-job.json" | Should Be $true
    }

    It "has authoritative execution gate policy document" {
        Test-Path -LiteralPath "docs/o3de-integration/AUTHORITATIVE-EXECUTION-GATE-POLICY.md" | Should Be $true
    }

    It "has resolver ladder roadmap index document" {
        Test-Path -LiteralPath "docs/roadmap/RESOLVER-LADDER-INDEX.md" | Should Be $true
    }

    It "has PR stack consolidation guide document" {
        Test-Path -LiteralPath "docs/operator-playbooks/PR-STACK-CONSOLIDATION-GUIDE.md" | Should Be $true
    }

    It "has Phase 1 audit report" {
        Test-Path -LiteralPath "docs/audits/PHASE-1-OPERATIONAL-BASELINE.md" | Should Be $true
    }

    It "has Phase 1 baseline inventory" {
        Test-Path -LiteralPath "docs/audits/phase1_operational_baseline_inventory.json" | Should Be $true
    }

    It "has Phase 1 baseline verifier script" {
        Test-Path -LiteralPath "tools/audit/verify_phase1_baseline.py" | Should Be $true
    }

    It "has Phase 1 baseline wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Test-MaxinePhase1Baseline.ps1" | Should Be $true
    }

    It "does not have authoritative write command implementation" {
        Test-Path -LiteralPath "scripts/powershell/Invoke-MaxineAuthoritativeResolverWrite.ps1" | Should Be $false
    }

    It "has Phase 2 sandbox write design document" {
        Test-Path -LiteralPath "docs/roadmap/PHASE-2-SANDBOX-WRITE-PROTOTYPE-DESIGN.md" | Should Be $true
    }

    It "has sandbox write prototype contract document" {
        Test-Path -LiteralPath "docs/contracts/SANDBOX-WRITE-PROTOTYPE-CONTRACT.md" | Should Be $true
    }

    It "has Phase 2 design inventory" {
        Test-Path -LiteralPath "docs/audits/phase2_sandbox_write_design_inventory.json" | Should Be $true
    }

    It "has Phase 2 design verifier script" {
        Test-Path -LiteralPath "tools/audit/verify_phase2_design_only.py" | Should Be $true
    }

    It "has Phase 2 design PowerShell wrapper script" {
        Test-Path -LiteralPath "scripts/powershell/Test-MaxinePhase2DesignOnly.ps1" | Should Be $true
    }

    It "does not have sandbox write command implementation" {
        Test-Path -LiteralPath "scripts/powershell/Invoke-MaxineSandboxResolverWrite.ps1" | Should Be $false
    }

    It "still does not have authoritative write command implementation" {
        Test-Path -LiteralPath "scripts/powershell/Invoke-MaxineAuthoritativeResolverWrite.ps1" | Should Be $false
    }

    It "has Phase 2 rollback design doc" {
        Test-Path -LiteralPath "docs/roadmap/PHASE-2-ROLLBACK-ARTIFACT-DESIGN.md" | Should Be $true
    }

    It "has sandbox rollback contract" {
        Test-Path -LiteralPath "docs/contracts/SANDBOX-ROLLBACK-ARTIFACT-CONTRACT.md" | Should Be $true
    }

    It "has sandbox rollback schema" {
        Test-Path -LiteralPath "schemas/maxine_sandbox_rollback_artifact.schema.json" | Should Be $true
    }

    It "has sandbox rollback example" {
        Test-Path -LiteralPath "examples/manifests/example-sandbox-rollback-artifact.json" | Should Be $true
    }

    It "has sandbox rollback verifier" {
        Test-Path -LiteralPath "tools/audit/verify_sandbox_rollback_artifact.py" | Should Be $true
    }

    It "has Phase 2 rollback verifier" {
        Test-Path -LiteralPath "tools/audit/verify_phase2_rollback_design.py" | Should Be $true
    }

    It "does not have rollback command implementation" {
        Test-Path -LiteralPath "scripts/powershell/Invoke-MaxineSandboxRollback.ps1" | Should Be $false
    }

    It "still does not have sandbox write command implementation" {
        Test-Path -LiteralPath "scripts/powershell/Invoke-MaxineSandboxResolverWrite.ps1" | Should Be $false
    }

    It "still does not have authoritative write command implementation (rollback phase)" {
        Test-Path -LiteralPath "scripts/powershell/Invoke-MaxineAuthoritativeResolverWrite.ps1" | Should Be $false
    }

    It "has sandbox fixture path-safety design doc" {
        Test-Path -LiteralPath "docs/roadmap/PHASE-2-SANDBOX-FIXTURE-PATH-SAFETY-DESIGN.md" | Should Be $true
    }

    It "has sandbox fixture path-safety contract" {
        Test-Path -LiteralPath "docs/contracts/SANDBOX-FIXTURE-PATH-SAFETY-CONTRACT.md" | Should Be $true
    }

    It "has sandbox README" {
        Test-Path -LiteralPath "examples/sandbox/README.md" | Should Be $true
    }

    It "has path safety policy" {
        Test-Path -LiteralPath "docs/audits/phase2_sandbox_path_safety_policy.json" | Should Be $true
    }

    It "has path safety verifier" {
        Test-Path -LiteralPath "tools/audit/verify_sandbox_path_safety.py" | Should Be $true
    }

    It "has phase verifier for sandbox fixture path safety" {
        Test-Path -LiteralPath "tools/audit/verify_phase2_sandbox_fixture_design.py" | Should Be $true
    }

    It "has path safety wrapper" {
        Test-Path -LiteralPath "scripts/powershell/Test-MaxineSandboxPathSafety.ps1" | Should Be $true
    }

    It "has phase wrapper for sandbox fixture path safety" {
        Test-Path -LiteralPath "scripts/powershell/Test-MaxinePhase2SandboxFixtureDesign.ps1" | Should Be $true
    }

    It "does not have sandbox write command implementation (path-safety phase)" {
        Test-Path -LiteralPath "scripts/powershell/Invoke-MaxineSandboxResolverWrite.ps1" | Should Be $false
    }

    It "does not have rollback command implementation (path-safety phase)" {
        Test-Path -LiteralPath "scripts/powershell/Invoke-MaxineSandboxRollback.ps1" | Should Be $false
    }

    It "does not have authoritative write command implementation (path-safety phase)" {
        Test-Path -LiteralPath "scripts/powershell/Invoke-MaxineAuthoritativeResolverWrite.ps1" | Should Be $false
    }
}
