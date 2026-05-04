Describe "Asset Candidate Inventory Read Only" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $projectInventoryRead = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineProjectInventoryRead.ps1"
        $assetInventoryRead = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineAssetCandidateInventoryRead.ps1"
        $assetInventoryInspect = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineAssetCandidateInventoryInspect.ps1"
        $authoritative = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineAuthoritativeResolverWrite.ps1"
    }

    It "writes sandbox-local asset candidate inventory and records sha256 candidates" {
        $suffix = [Guid]::NewGuid().ToString("N")
        $generatedDirRel = "scripts/generated/pester-asset-candidates-$suffix"
        $generatedDirAbs = Join-Path $repoRoot $generatedDirRel
        New-Item -Path $generatedDirAbs -ItemType Directory -Force | Out-Null

        $modelRel = "$generatedDirRel/pester-$suffix.fbx"
        $modelAbs = Join-Path $repoRoot $modelRel
        Set-Content -LiteralPath $modelAbs -Value "sandbox model placeholder" -Encoding UTF8

        $projectInventoryRel = "examples/sandbox/project-inventory/pester-project-inventory-$suffix.json"
        $projectInventoryAbs = Join-Path $repoRoot $projectInventoryRel
        $projectJson = & powershell -NoProfile -ExecutionPolicy Bypass -File $projectInventoryRead -ProjectRoot . -OutputPath $projectInventoryRel
        $LASTEXITCODE | Should Be 0
        $projectObj = $projectJson | ConvertFrom-Json

        $outputRel = "examples/sandbox/asset-candidates/pester-asset-candidate-inventory-$suffix.json"
        $outputAbs = Join-Path $repoRoot $outputRel
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $assetInventoryRead -ProjectInventoryPath $projectInventoryRel -OutputPath $outputRel
        $LASTEXITCODE | Should Be 0
        (Test-Path -LiteralPath $outputAbs) | Should Be $true

        $json = $output | ConvertFrom-Json
        $json.output_path | Should Be $outputRel
        $json.sandbox_root | Should Be "examples/sandbox"
        $json.source_project_inventory_id | Should Be $projectObj.inventory_id
        @($json.source_asset_candidates).Count | Should BeGreaterThan 0

        $candidate = @($json.source_asset_candidates | Where-Object { $_.relative_path -eq $modelRel })[0]
        $candidate | Should Not BeNullOrEmpty
        $candidate.sha256.Length | Should Be 64
        $candidate.category | Should Be "character_source"

        if (Test-Path -LiteralPath $outputAbs) { Remove-Item -LiteralPath $outputAbs -Force }
        if (Test-Path -LiteralPath $projectInventoryAbs) { Remove-Item -LiteralPath $projectInventoryAbs -Force }
        if (Test-Path -LiteralPath $generatedDirAbs) { Remove-Item -LiteralPath $generatedDirAbs -Recurse -Force }
    }

    It "blocks traversal and keeps inspect read-only" {
        $suffix = [Guid]::NewGuid().ToString("N")
        $projectInventoryRel = "examples/sandbox/project-inventory/pester-project-inventory-$suffix.json"
        $projectInventoryAbs = Join-Path $repoRoot $projectInventoryRel
        & powershell -NoProfile -ExecutionPolicy Bypass -File $projectInventoryRead -ProjectRoot . -OutputPath $projectInventoryRel | Out-Null
        $LASTEXITCODE | Should Be 0

        $outputRel = "examples/sandbox/asset-candidates/pester-asset-candidate-inventory-$suffix.json"
        $outputAbs = Join-Path $repoRoot $outputRel
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $assetInventoryRead -ProjectInventoryPath $projectInventoryRel -OutputPath $outputRel
        $LASTEXITCODE | Should Be 0
        $json = $output | ConvertFrom-Json

        $before = (Get-FileHash -LiteralPath $outputAbs -Algorithm SHA256).Hash
        $inspectList = & powershell -NoProfile -ExecutionPolicy Bypass -File $assetInventoryInspect -List
        $LASTEXITCODE | Should Be 0
        ($inspectList | ConvertFrom-Json).inventory_count | Should BeGreaterThan 0

        & powershell -NoProfile -ExecutionPolicy Bypass -File $assetInventoryInspect -InventoryId $json.inventory_id | Out-Null
        $LASTEXITCODE | Should Be 0
        $after = (Get-FileHash -LiteralPath $outputAbs -Algorithm SHA256).Hash
        $after | Should Be $before

        & powershell -NoProfile -ExecutionPolicy Bypass -File $assetInventoryRead -ProjectInventoryPath $projectInventoryRel -OutputPath "../outside/asset-candidates.json" | Out-Null
        $LASTEXITCODE | Should Not Be 0

        if (Test-Path -LiteralPath $outputAbs) { Remove-Item -LiteralPath $outputAbs -Force }
        if (Test-Path -LiteralPath $projectInventoryAbs) { Remove-Item -LiteralPath $projectInventoryAbs -Force }
    }

    It "never allows cache as a scan root" {
        $suffix = [Guid]::NewGuid().ToString("N")
        $cacheRel = "cache/pester-asset-candidates-$suffix"
        $cacheAbs = Join-Path $repoRoot $cacheRel
        New-Item -Path $cacheAbs -ItemType Directory -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $cacheAbs "cache-$suffix.fbx") -Value "cache file" -Encoding UTF8

        $allowedRel = "scripts/generated/pester-allowed-$suffix"
        $allowedAbs = Join-Path $repoRoot $allowedRel
        New-Item -Path $allowedAbs -ItemType Directory -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $allowedAbs "allowed-$suffix.fbx") -Value "allowed file" -Encoding UTF8

        $projectInventoryRel = "examples/sandbox/project-inventory/pester-cache-project-inventory-$suffix.json"
        $projectInventoryAbs = Join-Path $repoRoot $projectInventoryRel
        $projectInventoryObj = [ordered]@{
            schema_version = "1.0.0"
            inventory_id = "pester-cache-project-inventory-$suffix"
            project_root = "."
            known_asset_folders = @($cacheRel, $allowedRel)
            generated_asset_candidate_folders = @($allowedRel)
        }
        $projectInventoryObj | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $projectInventoryAbs -Encoding UTF8

        $outputRel = "examples/sandbox/asset-candidates/pester-cache-asset-candidate-inventory-$suffix.json"
        $outputAbs = Join-Path $repoRoot $outputRel
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $assetInventoryRead -ProjectInventoryPath $projectInventoryRel -OutputPath $outputRel
        $LASTEXITCODE | Should Be 0

        $json = $output | ConvertFrom-Json
        ($json.warnings -join "`n").ToLowerInvariant().Contains("cache is not an allowed scan root") | Should Be $true
        ($json.scanned_roots -join "`n").ToLowerInvariant().Contains("cache/") | Should Be $false

        if (Test-Path -LiteralPath $outputAbs) { Remove-Item -LiteralPath $outputAbs -Force }
        if (Test-Path -LiteralPath $projectInventoryAbs) { Remove-Item -LiteralPath $projectInventoryAbs -Force }
        if (Test-Path -LiteralPath $cacheAbs) { Remove-Item -LiteralPath $cacheAbs -Recurse -Force }
        if (Test-Path -LiteralPath $allowedAbs) { Remove-Item -LiteralPath $allowedAbs -Recurse -Force }
    }

    It "keeps authoritative writer absent and avoids O3DE/AP/Editor hooks" {
        (Test-Path -LiteralPath $authoritative) | Should Be $false

        $combined = ((Get-Content -LiteralPath $assetInventoryRead -Raw).ToLowerInvariant()) + "`n" + ((Get-Content -LiteralPath $assetInventoryInspect -Raw).ToLowerInvariant())
        $combined.Contains("o3de editor") | Should Be $false
        $combined.Contains("asset processor") | Should Be $false
        $combined.Contains("o3de.exe") | Should Be $false
        $combined.Contains("editor.exe") | Should Be $false
        $combined.Contains("invoke-maxineauthoritativeresolverwrite.ps1") | Should Be $false
    }
}
