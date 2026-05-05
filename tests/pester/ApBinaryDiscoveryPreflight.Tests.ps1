Describe "AP Binary Discovery and Preflight" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $discoveryRead = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApBinaryDiscoveryRead.ps1"
        $discoveryInspect = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApBinaryDiscoveryInspect.ps1"
        $preflightBuild = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApBinaryPreflightBuild.ps1"
        $authoritative = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineAuthoritativeResolverWrite.ps1"

        function Write-JsonUtf8NoBom {
            param(
                [Parameter(Mandatory = $true)][string]$Path,
                [Parameter(Mandatory = $true)][object]$Object,
                [int]$Depth = 50
            )
            $dir = Split-Path -Parent $Path
            if (-not [string]::IsNullOrWhiteSpace($dir) -and -not (Test-Path -LiteralPath $dir)) {
                New-Item -Path $dir -ItemType Directory -Force | Out-Null
            }
            [System.IO.File]::WriteAllText(
                $Path,
                ($Object | ConvertTo-Json -Depth $Depth),
                [System.Text.UTF8Encoding]::new($false)
            )
        }

        function New-BinaryFixture {
            $suffix = [Guid]::NewGuid().ToString("N")
            $generatedRel = "scripts/generated/pester-ap-binary-$suffix"
            $generatedAbs = Join-Path $repoRoot $generatedRel
            New-Item -Path $generatedAbs -ItemType Directory -Force | Out-Null

            $batchRel = "$generatedRel/AssetProcessorBatch.exe"
            $batchAbs = Join-Path $repoRoot $batchRel
            Set-Content -LiteralPath $batchAbs -Value "mock-batch" -Encoding UTF8

            $unsupportedRel = "$generatedRel/tool-unknown.exe"
            $unsupportedAbs = Join-Path $repoRoot $unsupportedRel
            Set-Content -LiteralPath $unsupportedAbs -Value "mock-unknown" -Encoding UTF8

            $sourcePreflightRel = "examples/sandbox/ap-execution-preflights/pester-ap-binary-source-$suffix.json"
            $sourcePreflightAbs = Join-Path $repoRoot $sourcePreflightRel
            Write-JsonUtf8NoBom -Path $sourcePreflightAbs -Object ([ordered]@{
                schema_version = "1.0.0"
                preflight_id = "ap-preflight-source-$suffix"
                source_ap_evidence_import_id = "ap-evidence-$suffix"
                source_proposal_id = "proposal-$suffix"
                source_project_inventory_id = "project-$suffix"
                sandbox_root = "examples/sandbox"
                project_root = "."
                candidate_relative_path = "scripts/generated/example.fbx"
                proposed_ap_command_display = "ap_batch_display_only --project-root . --candidate scripts/generated/example.fbx --mode preflight_display_only --no_execution"
                proposed_working_directory = "."
                required_manual_confirmation = $true
                local_only = $true
                execution_admitted = $false
                ready_for_future_execution_request = $true
                readiness_status = "ready_for_future_execution_request"
                required_next_evidence = @("ap_binary_discovery")
                blocking_reasons = @()
                warnings = @()
                safety_summary = "source preflight fixture"
                explicit_non_admissions = @(
                    "authoritative_writes",
                    "asset_processor_execution",
                    "o3de_editor_execution",
                    "o3de_cli_execution",
                    "cache_read",
                    "live_asset_database_read",
                    "product_resolution",
                    "product_id_claims",
                    "asset_id_claims",
                    "source_uuid_claims",
                    "spawning",
                    "publishing"
                )
                output_path = $sourcePreflightRel
                created_utc = "2026-05-04T00:00:00Z"
            })

            return [ordered]@{
                suffix = $suffix
                generatedAbs = $generatedAbs
                batchRel = $batchRel
                batchAbs = $batchAbs
                unsupportedRel = $unsupportedRel
                unsupportedAbs = $unsupportedAbs
                sourcePreflightRel = $sourcePreflightRel
                sourcePreflightAbs = $sourcePreflightAbs
            }
        }

        function Remove-BinaryFixture {
            param([Parameter(Mandatory = $true)]$Context)

            foreach ($path in @(
                $Context.sourcePreflightAbs,
                $Context.batchAbs,
                $Context.unsupportedAbs
            )) {
                if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
            }
            if (Test-Path -LiteralPath $Context.generatedAbs) {
                Remove-Item -LiteralPath $Context.generatedAbs -Recurse -Force
            }
        }
    }

    It "reads explicit candidate metadata and writes sandbox-local discovery output" {
        $ctx = New-BinaryFixture
        try {
            $discoveryRel = "examples/sandbox/ap-binary-discovery/pester-ap-binary-discovery-$($ctx.suffix).json"
            $discoveryAbs = Join-Path $repoRoot $discoveryRel

            $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $discoveryRead -CandidatePaths "$($ctx.batchRel),$($ctx.unsupportedRel)" -OutputPath $discoveryRel
            $LASTEXITCODE | Should Be 0
            (Test-Path -LiteralPath $discoveryAbs) | Should Be $true

            $obj = $output | ConvertFrom-Json
            $obj.read_only | Should Be $true
            $obj.execution_admitted | Should Be $false
            $obj.cache_access_admitted | Should Be $false
            $obj.live_database_access_admitted | Should Be $false
            $obj.output_path.StartsWith("examples/sandbox/ap-binary-discovery/") | Should Be $true

            if (Test-Path -LiteralPath $discoveryAbs) { Remove-Item -LiteralPath $discoveryAbs -Force }
        }
        finally {
            Remove-BinaryFixture -Context $ctx
        }
    }

    It "blocks traversal and unsafe candidate paths" {
        $ctx = New-BinaryFixture
        try {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $discoveryRead -CandidatePaths "../outside/AssetProcessorBatch.exe" | Out-Null
            $LASTEXITCODE | Should Not Be 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $discoveryRead -CandidatePaths "AssetProcessorBatch.exe|Write-Host unsafe" | Out-Null
            $LASTEXITCODE | Should Not Be 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $discoveryRead -CandidatePaths $ctx.batchRel -OutputPath "../outside/discovery.json" | Out-Null
            $LASTEXITCODE | Should Not Be 0
        }
        finally {
            Remove-BinaryFixture -Context $ctx
        }
    }

    It "builds binary preflight from discovery and AP execution preflight with execution_admitted false" {
        $ctx = New-BinaryFixture
        try {
            $discoveryRel = "examples/sandbox/ap-binary-discovery/pester-ap-binary-preflight-discovery-$($ctx.suffix).json"
            $discoveryAbs = Join-Path $repoRoot $discoveryRel
            $preflightRel = "examples/sandbox/ap-binary-preflights/pester-ap-binary-preflight-$($ctx.suffix).json"
            $preflightAbs = Join-Path $repoRoot $preflightRel

            & powershell -NoProfile -ExecutionPolicy Bypass -File $discoveryRead -CandidatePaths $ctx.batchRel -OutputPath $discoveryRel | Out-Null
            $LASTEXITCODE | Should Be 0

            $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $preflightBuild -DiscoveryPath $discoveryRel -ApExecutionPreflightPath $ctx.sourcePreflightRel -OutputPath $preflightRel
            $LASTEXITCODE | Should Be 0
            (Test-Path -LiteralPath $preflightAbs) | Should Be $true

            $obj = $output | ConvertFrom-Json
            $obj.execution_admitted | Should Be $false
            $obj.required_manual_confirmation | Should Be $true
            $obj.local_only | Should Be $true

            if (Test-Path -LiteralPath $preflightAbs) { Remove-Item -LiteralPath $preflightAbs -Force }
            if (Test-Path -LiteralPath $discoveryAbs) { Remove-Item -LiteralPath $discoveryAbs -Force }
        }
        finally {
            Remove-BinaryFixture -Context $ctx
        }
    }

    It "inspect is read-only and unsupported binaries are blocked for future real AP execution" {
        $ctx = New-BinaryFixture
        try {
            $discoveryRel = "examples/sandbox/ap-binary-discovery/pester-ap-binary-unsupported-$($ctx.suffix).json"
            $discoveryAbs = Join-Path $repoRoot $discoveryRel
            $preflightRel = "examples/sandbox/ap-binary-preflights/pester-ap-binary-unsupported-$($ctx.suffix).json"
            $preflightAbs = Join-Path $repoRoot $preflightRel

            & powershell -NoProfile -ExecutionPolicy Bypass -File $discoveryRead -CandidatePaths $ctx.unsupportedRel -OutputPath $discoveryRel | Out-Null
            $LASTEXITCODE | Should Be 0

            $discoveryHashBefore = (Get-FileHash -LiteralPath $discoveryAbs -Algorithm SHA256).Hash
            $listOut = & powershell -NoProfile -ExecutionPolicy Bypass -File $discoveryInspect -List
            $LASTEXITCODE | Should Be 0
            ($listOut | ConvertFrom-Json).discovery_count | Should BeGreaterThan 0

            $buildOut = & powershell -NoProfile -ExecutionPolicy Bypass -File $preflightBuild -DiscoveryPath $discoveryRel -ApExecutionPreflightPath $ctx.sourcePreflightRel -OutputPath $preflightRel
            $LASTEXITCODE | Should Be 0
            ($buildOut | ConvertFrom-Json).readiness_status | Should Be "blocked_unsupported_binary"

            (Get-FileHash -LiteralPath $discoveryAbs -Algorithm SHA256).Hash | Should Be $discoveryHashBefore

            if (Test-Path -LiteralPath $preflightAbs) { Remove-Item -LiteralPath $preflightAbs -Force }
            if (Test-Path -LiteralPath $discoveryAbs) { Remove-Item -LiteralPath $discoveryAbs -Force }
        }
        finally {
            Remove-BinaryFixture -Context $ctx
        }
    }

    It "keeps broad AP/O3DE execution blocked and authoritative writer absent" {
        (Test-Path -LiteralPath $authoritative) | Should Be $false

        $combined = (
            (Get-Content -LiteralPath $discoveryRead -Raw).ToLowerInvariant() + "`n" +
            (Get-Content -LiteralPath $discoveryInspect -Raw).ToLowerInvariant() + "`n" +
            (Get-Content -LiteralPath $preflightBuild -Raw).ToLowerInvariant()
        )

        $combined.Contains("start-process") | Should Be $false
        $combined.Contains("invoke-expression") | Should Be $false
        $combined.Contains("o3de.exe") | Should Be $false
        $combined.Contains("editor.exe") | Should Be $false

        $matrix = Get-Content -LiteralPath (Join-Path $repoRoot "examples/capabilities/maxine-capability-matrix.json") -Raw | ConvertFrom-Json
        $caps = $matrix.capabilities
        $caps.ap_binary_discovery_read | Should Be "read_only"
        $caps.ap_binary_discovery_inspect | Should Be "read_only"
        $caps.ap_binary_preflight_build | Should Be "sandbox_only"
        $caps.real_asset_processor_execution | Should Be "blocked"
        $caps.asset_processor_execution | Should Be "blocked"
        $caps.product_resolution | Should Be "blocked"
        $caps.product_id_claims | Should Be "blocked"
        $caps.asset_id_claims | Should Be "blocked"
        $caps.source_uuid_claims | Should Be "blocked"
        $caps.spawning | Should Be "blocked"
        $caps.publishing | Should Be "blocked"
    }
}
