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
}
