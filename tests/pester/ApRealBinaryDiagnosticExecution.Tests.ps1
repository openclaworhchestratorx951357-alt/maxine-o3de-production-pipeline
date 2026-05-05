Describe "AP Real Binary Diagnostic Execution" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $binaryPreflightBuildCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApBinaryPreflightBuild.ps1"
        $executeCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApRealBinaryDiagnosticExecution.ps1"
        $inspectCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApRealBinaryDiagnosticInspect.ps1"
        $bundleCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApRealBinaryDiagnosticBundleExport.ps1"
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

        function New-RealBinaryFixture {
            $suffix = [Guid]::NewGuid().ToString("N")

            $generatedRel = "scripts/generated/pester-ap-real-binary-$suffix"
            $generatedAbs = Join-Path $repoRoot $generatedRel
            New-Item -Path $generatedAbs -ItemType Directory -Force | Out-Null

            $fakeBinaryRel = "$generatedRel/AssetProcessorBatch.exe"
            $fakeBinaryAbs = Join-Path $repoRoot $fakeBinaryRel
            Set-Content -LiteralPath $fakeBinaryAbs -Value "fake-ap-binary-fixture" -Encoding UTF8

            $discoveryRel = "examples/sandbox/ap-binary-discovery/pester-ap-real-binary-discovery-$suffix.json"
            $discoveryAbs = Join-Path $repoRoot $discoveryRel
            Write-JsonUtf8NoBom -Path $discoveryAbs -Object ([ordered]@{
                schema_version = "1.0.0"
                discovery_id = "ap-binary-discovery-$suffix"
                sandbox_root = "examples/sandbox"
                read_only = $true
                execution_admitted = $false
                existing_candidates = @(
                    [ordered]@{
                        candidate_path = $fakeBinaryRel
                        path_source = "explicit"
                        exists = $true
                    }
                )
                rejected_candidates = @()
                output_path = $discoveryRel
                created_utc = "2026-05-04T00:00:00Z"
            })

            $apExecutionPreflightRel = "examples/sandbox/ap-execution-preflights/pester-ap-real-binary-ap-preflight-$suffix.json"
            $apExecutionPreflightAbs = Join-Path $repoRoot $apExecutionPreflightRel
            Write-JsonUtf8NoBom -Path $apExecutionPreflightAbs -Object ([ordered]@{
                schema_version = "1.0.0"
                preflight_id = "ap-execution-preflight-$suffix"
                sandbox_root = "examples/sandbox"
                required_manual_confirmation = $true
                local_only = $true
                execution_admitted = $false
                readiness_status = "ready_for_future_execution_request"
                proposed_ap_command_display = "ap_batch_display_only --project-root . --candidate scripts/generated/mock.fbx --mode preflight_display_only --no_execution"
                output_path = $apExecutionPreflightRel
                created_utc = "2026-05-04T00:00:00Z"
            })

            $binaryPreflightRel = "examples/sandbox/ap-binary-preflights/pester-ap-real-binary-preflight-$suffix.json"
            $binaryPreflightAbs = Join-Path $repoRoot $binaryPreflightRel
            & powershell -NoProfile -ExecutionPolicy Bypass -File $binaryPreflightBuildCmd -DiscoveryPath $discoveryRel -ApExecutionPreflightPath $apExecutionPreflightRel -OutputPath $binaryPreflightRel | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "failed to create AP binary preflight fixture"
            }

            return [ordered]@{
                suffix = $suffix
                generatedAbs = $generatedAbs
                generatedRel = $generatedRel
                fakeBinaryAbs = $fakeBinaryAbs
                fakeBinaryRel = $fakeBinaryRel
                discoveryAbs = $discoveryAbs
                discoveryRel = $discoveryRel
                apExecutionPreflightAbs = $apExecutionPreflightAbs
                apExecutionPreflightRel = $apExecutionPreflightRel
                binaryPreflightAbs = $binaryPreflightAbs
                binaryPreflightRel = $binaryPreflightRel
            }
        }

        function Set-BinaryPreflightValues {
            param(
                [Parameter(Mandatory = $true)]$Context,
                [Parameter(Mandatory = $true)][hashtable]$Updates
            )

            $payload = Get-Content -LiteralPath $Context.binaryPreflightAbs -Raw | ConvertFrom-Json
            foreach ($key in $Updates.Keys) {
                $payload.$key = $Updates[$key]
            }
            Write-JsonUtf8NoBom -Path $Context.binaryPreflightAbs -Object $payload
        }

        function New-ExecutionOutputPath {
            param([Parameter(Mandatory = $true)]$Context)

            return "examples/sandbox/ap-real-binary-diagnostic-executions/pester-ap-real-binary-execution-$($Context.suffix)-$([Guid]::NewGuid().ToString('N')).json"
        }

        function Remove-RealBinaryFixture {
            param([Parameter(Mandatory = $true)]$Context)

            foreach ($path in @(
                $Context.binaryPreflightAbs,
                $Context.apExecutionPreflightAbs,
                $Context.discoveryAbs,
                $Context.fakeBinaryAbs
            )) {
                if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
            }

            if (Test-Path -LiteralPath $Context.generatedAbs) {
                Remove-Item -LiteralPath $Context.generatedAbs -Recurse -Force
            }

            $executionRoot = Join-Path $repoRoot "examples/sandbox/ap-real-binary-diagnostic-executions"
            $executionFiles = Get-ChildItem -LiteralPath $executionRoot -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*$($Context.suffix)*" }
            foreach ($file in $executionFiles) {
                try {
                    $payload = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
                    if ($payload.stdout_path) {
                        $stdoutAbs = Join-Path $repoRoot ([string]$payload.stdout_path)
                        if (Test-Path -LiteralPath $stdoutAbs) { Remove-Item -LiteralPath $stdoutAbs -Force }
                    }
                    if ($payload.stderr_path) {
                        $stderrAbs = Join-Path $repoRoot ([string]$payload.stderr_path)
                        if (Test-Path -LiteralPath $stderrAbs) { Remove-Item -LiteralPath $stderrAbs -Force }
                    }
                } catch {
                    # no-op
                }
                if (Test-Path -LiteralPath $file.FullName) { Remove-Item -LiteralPath $file.FullName -Force }
            }

            $bundleRoot = Join-Path $repoRoot "examples/sandbox/ap-real-binary-diagnostic-bundles"
            $bundleDirs = Get-ChildItem -LiteralPath $bundleRoot -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*$($Context.suffix)*" }
            foreach ($dir in $bundleDirs) {
                if (Test-Path -LiteralPath $dir.FullName) { Remove-Item -LiteralPath $dir.FullName -Recurse -Force }
            }
        }
    }

    It "blocks without approval and blocks unsafe arguments/command display and unsupported preflight gates" {
        $ctx = New-RealBinaryFixture
        try {
            $outNoApproval = New-ExecutionOutputPath -Context $ctx
            $noApproval = & powershell -NoProfile -ExecutionPolicy Bypass -File $executeCmd -ApBinaryPreflightPath $ctx.binaryPreflightRel -OutputPath $outNoApproval -UseSimulatedCommandMode
            $LASTEXITCODE | Should Be 0
            $payloadNoApproval = $noApproval | ConvertFrom-Json
            $payloadNoApproval.execution_status | Should Be "blocked"
            $payloadNoApproval.command_executed | Should Be $false
            $payloadNoApproval.blocked_reason.Contains("without approval flag") | Should Be $true

            Set-BinaryPreflightValues -Context $ctx -Updates @{ readiness_status = "blocked_missing_binary" }
            $outUnready = New-ExecutionOutputPath -Context $ctx
            $unready = & powershell -NoProfile -ExecutionPolicy Bypass -File $executeCmd -ApBinaryPreflightPath $ctx.binaryPreflightRel -OutputPath $outUnready -ApproveRealBinaryDiagnosticExecution -UseSimulatedCommandMode
            $LASTEXITCODE | Should Be 0
            ($unready | ConvertFrom-Json).blocked_reason.Contains("readiness_status") | Should Be $true

            Set-BinaryPreflightValues -Context $ctx -Updates @{
                readiness_status = "ready_for_future_real_ap_execution_request"
                binary_exists = $true
                binary_allowed_for_future_execution_request = $true
                local_only = $true
                execution_admitted = $false
                binary_kind = "AssetProcessorBatch"
            }

            $scenarios = @(
                @{ updates = @{ binary_exists = $false }; expected = "binary_exists must be true" },
                @{ updates = @{ binary_allowed_for_future_execution_request = $false }; expected = "binary_allowed_for_future_execution_request must be true" },
                @{ updates = @{ local_only = $false }; expected = "local_only must be true" },
                @{ updates = @{ execution_admitted = $true }; expected = "execution_admitted=true" },
                @{ updates = @{ binary_kind = "unknown" }; expected = "binary_kind 'unknown'" }
            )

            foreach ($scenario in $scenarios) {
                Set-BinaryPreflightValues -Context $ctx -Updates @{
                    binary_exists = $true
                    binary_allowed_for_future_execution_request = $true
                    local_only = $true
                    execution_admitted = $false
                    binary_kind = "AssetProcessorBatch"
                }
                Set-BinaryPreflightValues -Context $ctx -Updates $scenario.updates

                $outScenario = New-ExecutionOutputPath -Context $ctx
                $blocked = & powershell -NoProfile -ExecutionPolicy Bypass -File $executeCmd -ApBinaryPreflightPath $ctx.binaryPreflightRel -OutputPath $outScenario -ApproveRealBinaryDiagnosticExecution -UseSimulatedCommandMode
                $LASTEXITCODE | Should Be 0
                $payloadBlocked = $blocked | ConvertFrom-Json
                $payloadBlocked.execution_status | Should Be "blocked"
                $payloadBlocked.command_executed | Should Be $false
                $payloadBlocked.blocked_reason.Contains($scenario.expected) | Should Be $true
            }

            Set-BinaryPreflightValues -Context $ctx -Updates @{
                binary_exists = $true
                binary_allowed_for_future_execution_request = $true
                local_only = $true
                execution_admitted = $false
                binary_kind = "AssetProcessorBatch"
                selected_binary_path = "$($ctx.generatedRel)/AssetProcessorBatch.exe"
            }

            $outUnsafeArg = New-ExecutionOutputPath -Context $ctx
            $unsafeArg = & powershell -NoProfile -ExecutionPolicy Bypass -File $executeCmd -ApBinaryPreflightPath $ctx.binaryPreflightRel -OutputPath $outUnsafeArg -ApproveRealBinaryDiagnosticExecution -UseSimulatedCommandMode -DiagnosticArgument "--list"
            $LASTEXITCODE | Should Be 0
            ($unsafeArg | ConvertFrom-Json).blocked_reason.Contains("not allowlisted") | Should Be $true

            Set-BinaryPreflightValues -Context $ctx -Updates @{ selected_binary_path = "$($ctx.generatedRel)/AssetProcessorBatch.exe|whoami" }
            $outUnsafeDisplay = New-ExecutionOutputPath -Context $ctx
            $unsafeDisplay = & powershell -NoProfile -ExecutionPolicy Bypass -File $executeCmd -ApBinaryPreflightPath $ctx.binaryPreflightRel -OutputPath $outUnsafeDisplay -ApproveRealBinaryDiagnosticExecution -UseSimulatedCommandMode
            $LASTEXITCODE | Should Be 0
            ($unsafeDisplay | ConvertFrom-Json).blocked_reason.Contains("command display contains shell operators") | Should Be $true

            Set-BinaryPreflightValues -Context $ctx -Updates @{ selected_binary_path = "Cache/project/AssetProcessorBatch.exe" }
            $outCache = New-ExecutionOutputPath -Context $ctx
            $cacheBlocked = & powershell -NoProfile -ExecutionPolicy Bypass -File $executeCmd -ApBinaryPreflightPath $ctx.binaryPreflightRel -OutputPath $outCache -ApproveRealBinaryDiagnosticExecution -UseSimulatedCommandMode
            $LASTEXITCODE | Should Be 0
            ($cacheBlocked | ConvertFrom-Json).blocked_reason.Contains("includes Cache") | Should Be $true

            Set-BinaryPreflightValues -Context $ctx -Updates @{ selected_binary_path = "assetdb.sqlite" }
            $outDb = New-ExecutionOutputPath -Context $ctx
            $dbBlocked = & powershell -NoProfile -ExecutionPolicy Bypass -File $executeCmd -ApBinaryPreflightPath $ctx.binaryPreflightRel -OutputPath $outDb -ApproveRealBinaryDiagnosticExecution -UseSimulatedCommandMode
            $LASTEXITCODE | Should Be 0
            ($dbBlocked | ConvertFrom-Json).blocked_reason.Contains("assetdb.sqlite") | Should Be $true
        }
        finally {
            Remove-RealBinaryFixture -Context $ctx
        }
    }

    It "succeeds in allowlisted simulated mode, records hashes/flags, and records timeout in simulation" {
        $ctx = New-RealBinaryFixture
        try {
            $outSuccess = New-ExecutionOutputPath -Context $ctx
            $success = & powershell -NoProfile -ExecutionPolicy Bypass -File $executeCmd -ApBinaryPreflightPath $ctx.binaryPreflightRel -OutputPath $outSuccess -ApproveRealBinaryDiagnosticExecution -UseSimulatedCommandMode -DiagnosticArgument "--version"
            $LASTEXITCODE | Should Be 0
            $payloadSuccess = $success | ConvertFrom-Json

            $payloadSuccess.execution_status | Should Be "succeeded"
            $payloadSuccess.command_executed | Should Be $true
            $payloadSuccess.command_allowlisted | Should Be $true
            $payloadSuccess.execution_mode | Should Be "RealBinaryDiagnosticOnly"
            $payloadSuccess.approved_by_flag | Should Be $true
            $payloadSuccess.local_only | Should Be $true
            $payloadSuccess.exit_code | Should Be 0
            $payloadSuccess.output_path.StartsWith("examples/sandbox/ap-real-binary-diagnostic-executions/") | Should Be $true
            $payloadSuccess.stdout_path.StartsWith("examples/sandbox/ap-real-binary-diagnostic-executions/") | Should Be $true
            $payloadSuccess.stderr_path.StartsWith("examples/sandbox/ap-real-binary-diagnostic-executions/") | Should Be $true
            $payloadSuccess.stdout_sha256.Length | Should Be 64
            $payloadSuccess.stderr_sha256.Length | Should Be 64

            $payloadSuccess.product_ids_claimed | Should Be $false
            $payloadSuccess.asset_ids_claimed | Should Be $false
            $payloadSuccess.source_uuids_claimed | Should Be $false
            $payloadSuccess.product_resolution_claimed | Should Be $false
            $payloadSuccess.cache_access_admitted | Should Be $false
            $payloadSuccess.live_database_access_admitted | Should Be $false
            $payloadSuccess.spawn_admitted | Should Be $false
            $payloadSuccess.publish_admitted | Should Be $false

            $stdoutAbs = Join-Path $repoRoot $payloadSuccess.stdout_path
            $stderrAbs = Join-Path $repoRoot $payloadSuccess.stderr_path
            (Test-Path -LiteralPath $stdoutAbs) | Should Be $true
            (Test-Path -LiteralPath $stderrAbs) | Should Be $true

            $outTimeout = New-ExecutionOutputPath -Context $ctx
            $timeout = & powershell -NoProfile -ExecutionPolicy Bypass -File $executeCmd -ApBinaryPreflightPath $ctx.binaryPreflightRel -OutputPath $outTimeout -ApproveRealBinaryDiagnosticExecution -UseSimulatedCommandMode -SimulateTimeout -TimeoutSeconds 2
            $LASTEXITCODE | Should Be 0
            $payloadTimeout = $timeout | ConvertFrom-Json
            $payloadTimeout.execution_status | Should Be "timed_out"
            $payloadTimeout.command_executed | Should Be $true
            $payloadTimeout.exit_code | Should Be 124
            $payloadTimeout.timeout_seconds | Should Be 2
        }
        finally {
            Remove-RealBinaryFixture -Context $ctx
        }
    }

    It "inspect is read-only and bundle export is sandbox-local JSON plus stdout/stderr text only" {
        $ctx = New-RealBinaryFixture
        try {
            $outSuccess = New-ExecutionOutputPath -Context $ctx
            $success = & powershell -NoProfile -ExecutionPolicy Bypass -File $executeCmd -ApBinaryPreflightPath $ctx.binaryPreflightRel -OutputPath $outSuccess -ApproveRealBinaryDiagnosticExecution -UseSimulatedCommandMode
            $LASTEXITCODE | Should Be 0
            $payload = $success | ConvertFrom-Json

            $executionAbs = Join-Path $repoRoot $payload.output_path
            $stdoutAbs = Join-Path $repoRoot $payload.stdout_path
            $stderrAbs = Join-Path $repoRoot $payload.stderr_path
            $executionHashBefore = (Get-FileHash -LiteralPath $executionAbs -Algorithm SHA256).Hash
            $stdoutHashBefore = (Get-FileHash -LiteralPath $stdoutAbs -Algorithm SHA256).Hash
            $stderrHashBefore = (Get-FileHash -LiteralPath $stderrAbs -Algorithm SHA256).Hash

            $listOut = & powershell -NoProfile -ExecutionPolicy Bypass -File $inspectCmd -List
            $LASTEXITCODE | Should Be 0
            ($listOut | ConvertFrom-Json).execution_count | Should BeGreaterThan 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $inspectCmd -ExecutionId $payload.real_binary_diagnostic_execution_id -ShowOutputRefs -ShowBlockedReason | Out-Null
            $LASTEXITCODE | Should Be 0

            (Get-FileHash -LiteralPath $executionAbs -Algorithm SHA256).Hash | Should Be $executionHashBefore
            (Get-FileHash -LiteralPath $stdoutAbs -Algorithm SHA256).Hash | Should Be $stdoutHashBefore
            (Get-FileHash -LiteralPath $stderrAbs -Algorithm SHA256).Hash | Should Be $stderrHashBefore

            $bundleRel = "examples/sandbox/ap-real-binary-diagnostic-bundles/pester-ap-real-binary-$($ctx.suffix)/bundle.manifest.json"
            $bundleAbs = Join-Path $repoRoot $bundleRel
            $bundleDir = Split-Path -Parent $bundleAbs

            $bundleOut = & powershell -NoProfile -ExecutionPolicy Bypass -File $bundleCmd -ExecutionPath $payload.output_path -BundlePath $bundleRel
            $LASTEXITCODE | Should Be 0
            $manifest = $bundleOut | ConvertFrom-Json
            (Test-Path -LiteralPath $bundleAbs) | Should Be $true

            $manifest.bundle_path.StartsWith("examples/sandbox/ap-real-binary-diagnostic-bundles/") | Should Be $true
            foreach ($rel in $manifest.copied_artifact_paths) {
                $rel.StartsWith("examples/sandbox/ap-real-binary-diagnostic-bundles/") | Should Be $true
                ($rel.EndsWith(".json") -or $rel.EndsWith(".txt")) | Should Be $true
            }

            ((Get-ChildItem -LiteralPath $bundleDir -Recurse -File | Select-Object -ExpandProperty Name) -contains ([System.IO.Path]::GetFileName($ctx.fakeBinaryRel))) | Should Be $false

            & powershell -NoProfile -ExecutionPolicy Bypass -File $bundleCmd -ExecutionPath $payload.output_path -BundlePath "../outside/bundle.manifest.json" | Out-Null
            $LASTEXITCODE | Should Not Be 0
        }
        finally {
            Remove-RealBinaryFixture -Context $ctx
        }
    }

    It "keeps authoritative writer absent and broad AP/O3DE execution blocked" {
        (Test-Path -LiteralPath $authoritative) | Should Be $false

        $combined = (
            (Get-Content -LiteralPath $executeCmd -Raw).ToLowerInvariant() + "`n" +
            (Get-Content -LiteralPath $inspectCmd -Raw).ToLowerInvariant() + "`n" +
            (Get-Content -LiteralPath $bundleCmd -Raw).ToLowerInvariant()
        )

        $combined.Contains("invoke-expression") | Should Be $false
        $combined.Contains("start-process") | Should Be $false
        $combined.Contains("o3de.exe") | Should Be $false
        $combined.Contains("editor.exe") | Should Be $false
        $combined.Contains("invoke-maxineauthoritativeresolverwrite.ps1") | Should Be $false

        $matrix = Get-Content -LiteralPath (Join-Path $repoRoot "examples/capabilities/maxine-capability-matrix.json") -Raw | ConvertFrom-Json
        $caps = $matrix.capabilities

        $caps.ap_real_binary_diagnostic_execution | Should Be "sandbox_only"
        $caps.asset_processor_execution | Should Be "blocked"
        $caps.real_asset_processor_execution | Should Be "blocked"
        $caps.o3de_editor_execution | Should Be "blocked"
        $caps.o3de_cli_execution | Should Be "blocked"
        $caps.product_resolution | Should Be "blocked"
        $caps.product_id_claims | Should Be "blocked"
        $caps.asset_id_claims | Should Be "blocked"
        $caps.source_uuid_claims | Should Be "blocked"
        $caps.cache_read | Should Be "blocked"
        $caps.live_asset_database_read | Should Be "blocked"
        $caps.spawning | Should Be "blocked"
        $caps.publishing | Should Be "blocked"
    }
}
