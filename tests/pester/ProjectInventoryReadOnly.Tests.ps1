Describe "Project Inventory Read Only" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $inventoryRead = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineProjectInventoryRead.ps1"
        $inventoryInspect = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineProjectInventoryInspect.ps1"
        $authoritative = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineAuthoritativeResolverWrite.ps1"
    }

    It "writes inventory only under sandbox project-inventory folder" {
        $suffix = [Guid]::NewGuid().ToString('N')
        $outputRel = "examples/sandbox/project-inventory/pester-project-inventory-$suffix.json"
        $outputAbs = Join-Path $repoRoot $outputRel

        if (Test-Path -LiteralPath $outputAbs) { Remove-Item -LiteralPath $outputAbs -Force }

        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $inventoryRead -ProjectRoot . -OutputPath $outputRel
        $LASTEXITCODE | Should Be 0
        (Test-Path -LiteralPath $outputAbs) | Should Be $true

        $json = $output | ConvertFrom-Json
        $json.inventory_path | Should Be $outputRel
        $json.sandbox_root | Should Be "examples/sandbox"
        $json.safety.read_only_project_scan | Should Be $true
        $json.safety.o3de_editor_execution_admitted | Should Be $false
        $json.safety.asset_processor_execution_admitted | Should Be $false

        if (Test-Path -LiteralPath $outputAbs) { Remove-Item -LiteralPath $outputAbs -Force }
    }

    It "blocks output traversal and keeps inspect read-only" {
        $suffix = [Guid]::NewGuid().ToString('N')
        $outputRel = "examples/sandbox/project-inventory/pester-project-inventory-$suffix.json"
        $outputAbs = Join-Path $repoRoot $outputRel

        if (Test-Path -LiteralPath $outputAbs) { Remove-Item -LiteralPath $outputAbs -Force }

        & powershell -NoProfile -ExecutionPolicy Bypass -File $inventoryRead -ProjectRoot . -OutputPath $outputRel | Out-Null
        $LASTEXITCODE | Should Be 0

        $before = (Get-FileHash -LiteralPath $outputAbs -Algorithm SHA256).Hash

        $listOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $inventoryInspect -List
        $LASTEXITCODE | Should Be 0
        $listJson = $listOutput | ConvertFrom-Json
        $listJson.inventory_count | Should BeGreaterThan 0

        $oneJson = Get-Content -LiteralPath $outputAbs -Raw | ConvertFrom-Json
        $inspectOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $inventoryInspect -InventoryId $oneJson.inventory_id
        $LASTEXITCODE | Should Be 0
        $inspectJson = $inspectOutput | ConvertFrom-Json
        $inspectJson.inventory_id | Should Be $oneJson.inventory_id

        $after = (Get-FileHash -LiteralPath $outputAbs -Algorithm SHA256).Hash
        $after | Should Be $before

        & powershell -NoProfile -ExecutionPolicy Bypass -File $inventoryRead -ProjectRoot . -OutputPath "../outside/project-inventory.json" | Out-Null
        $LASTEXITCODE | Should Not Be 0

        & powershell -NoProfile -ExecutionPolicy Bypass -File $inventoryInspect -InventoryPath "../outside/project-inventory.json" | Out-Null
        $LASTEXITCODE | Should Not Be 0

        if (Test-Path -LiteralPath $outputAbs) { Remove-Item -LiteralPath $outputAbs -Force }
    }

    It "keeps authoritative writer absent" {
        (Test-Path -LiteralPath $authoritative) | Should Be $false
    }

    It "does not add O3DE/AP/Editor execution hooks" {
        $readText = (Get-Content -LiteralPath $inventoryRead -Raw).ToLowerInvariant()
        $inspectText = (Get-Content -LiteralPath $inventoryInspect -Raw).ToLowerInvariant()
        $combined = $readText + "`n" + $inspectText

        $combined.Contains("o3de editor") | Should Be $false
        $combined.Contains("asset processor") | Should Be $false
        $combined.Contains("o3de.exe") | Should Be $false
        $combined.Contains("editor.exe") | Should Be $false
        $combined.Contains("invoke-maxineauthoritativeresolverwrite.ps1") | Should Be $false
    }
}
