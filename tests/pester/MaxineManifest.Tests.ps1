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
}
