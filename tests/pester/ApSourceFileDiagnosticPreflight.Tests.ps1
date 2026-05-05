Describe "AP Source File Diagnostic Preflight" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $buildCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApSourceFileDiagnosticPreflightBuild.ps1"
        $inspectCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApSourceFileDiagnosticPreflightInspect.ps1"
        $bundleCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApSourceFileDiagnosticPreflightBundleExport.ps1"
        $authoritative = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineAuthoritativeResolverWrite.ps1"

        function Write-JsonUtf8NoBom {
            param(
                [Parameter(Mandatory = $true)][string]$Path,
                [Parameter(Mandatory = $true)][object]$Object,
                [int]$Depth = 100
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

        function New-SourceFilePreflightFixture {
            param([bool]$IncludeRealDiagnostic = $true)

            $suffix = [Guid]::NewGuid().ToString("N")

            $generatedRel = "scripts/generated/pester-ap-source-file-preflight-$suffix"
            $generatedAbs = Join-Path $repoRoot $generatedRel
            New-Item -Path $generatedAbs -ItemType Directory -Force | Out-Null

            $sourceRel = "$generatedRel/candidate-$suffix.fbx"
            $sourceAbs = Join-Path $repoRoot $sourceRel
            Set-Content -LiteralPath $sourceAbs -Value "source-file-fixture" -Encoding UTF8
            $sourceHash = (Get-FileHash -LiteralPath $sourceAbs -Algorithm SHA256).Hash.ToLowerInvariant()

            $binaryRel = "$generatedRel/AssetProcessorBatch.exe"
            $binaryAbs = Join-Path $repoRoot $binaryRel
            Set-Content -LiteralPath $binaryAbs -Value "fake-ap-binary" -Encoding UTF8

            $reviewPacketId = "asset-candidate-review-packet-$suffix"
            $proposalId = "product-resolution-proposal-$suffix"
            $preflightId = "ap-binary-preflight-$suffix"
            $projectId = "project-inventory-$suffix"
            $realDiagId = "ap-real-binary-diagnostic-execution-$suffix"

            $reviewRel = "examples/sandbox/asset-candidate-review-packets/pester-ap-source-file-review-$suffix.json"
            $reviewAbs = Join-Path $repoRoot $reviewRel
            Write-JsonUtf8NoBom -Path $reviewAbs -Object ([ordered]@{
                schema_version = "1.0.0"
                review_packet_id = $reviewPacketId
                source_inventory_id = "asset-inventory-$suffix"
                candidate_id = "candidate-$suffix"
                project_root = "."
                sandbox_root = "examples/sandbox"
                candidate_relative_path = $sourceRel
                candidate_extension = ".fbx"
                candidate_category = "character_source"
                size_bytes = (Get-Item -LiteralPath $sourceAbs).Length
                sha256 = $sourceHash
                last_write_time_utc = "2026-05-05T00:00:00Z"
                confidence = "high"
                evidence_links = @{ candidate = $sourceRel }
                provenance_links = @()
                material_texture_links = @()
                warnings = @()
                safety_summary = "review packet fixture"
                recommended_next_step = "inspect_candidate"
                operator_decision_state = "pending_review"
                explicit_non_admissions = @("authoritative_writes", "product_resolution", "asset_id_claims", "source_uuid_claims", "spawning", "publishing", "o3de_editor_execution", "asset_processor_execution")
                output_path = $reviewRel
                created_utc = "2026-05-05T00:00:00Z"
            })

            $proposalRel = "examples/sandbox/product-resolution-proposals/pester-ap-source-file-proposal-$suffix.json"
            $proposalAbs = Join-Path $repoRoot $proposalRel
            Write-JsonUtf8NoBom -Path $proposalAbs -Object ([ordered]@{
                schema_version = "1.0.0"
                proposal_id = $proposalId
                source_review_packet_id = $reviewPacketId
                source_inventory_id = "asset-inventory-$suffix"
                source_project_inventory_id = $projectId
                candidate_id = "candidate-$suffix"
                project_root = "."
                sandbox_root = "examples/sandbox"
                candidate_relative_path = $sourceRel
                candidate_extension = ".fbx"
                candidate_category = "character_source"
                candidate_sha256 = $sourceHash
                proposal_status = "proposal_only"
                expected_product_classes = @("model_product_candidate")
                likely_asset_pipeline_requirements = @("proposal_only")
                required_next_evidence = @("read_only_ap_evidence_import")
                blocking_reasons = @()
                warnings = @()
                proposal_only = $true
                product_ids_claimed = $false
                asset_ids_claimed = $false
                source_uuids_claimed = $false
                asset_processor_execution_admitted = $false
                o3de_execution_admitted = $false
                cache_access_admitted = $false
                spawn_admitted = $false
                publish_admitted = $false
                safety_summary = "proposal fixture"
                explicit_non_admissions = @("authoritative_writes", "product_resolution", "asset_id_claims", "source_uuid_claims", "spawning", "publishing", "o3de_editor_execution", "asset_processor_execution")
                output_path = $proposalRel
                created_utc = "2026-05-05T00:00:00Z"
            })

            $apBinaryPreflightRel = "examples/sandbox/ap-binary-preflights/pester-ap-source-file-binary-preflight-$suffix.json"
            $apBinaryPreflightAbs = Join-Path $repoRoot $apBinaryPreflightRel
            Write-JsonUtf8NoBom -Path $apBinaryPreflightAbs -Object ([ordered]@{
                schema_version = "1.0.0"
                ap_binary_preflight_id = $preflightId
                source_discovery_id = "ap-binary-discovery-$suffix"
                source_ap_execution_preflight_id = "ap-execution-preflight-$suffix"
                sandbox_root = "examples/sandbox"
                selected_binary_path = $binaryRel
                binary_kind = "AssetProcessorBatch"
                binary_exists = $true
                binary_allowed_for_future_execution_request = $true
                execution_admitted = $false
                required_manual_confirmation = $true
                local_only = $true
                readiness_status = "ready_for_future_real_ap_execution_request"
                blocking_reasons = @()
                warnings = @()
                safety_summary = "binary preflight fixture"
                explicit_non_admissions = @("authoritative_writes", "asset_processor_execution", "real_asset_processor_execution", "o3de_editor_execution")
                output_path = $apBinaryPreflightRel
                created_utc = "2026-05-05T00:00:00Z"
            })

            $projectRel = "examples/sandbox/project-inventory/pester-ap-source-file-project-$suffix.json"
            $projectAbs = Join-Path $repoRoot $projectRel
            Write-JsonUtf8NoBom -Path $projectAbs -Object ([ordered]@{
                schema_version = "1.0.0"
                inventory_id = $projectId
                project_root = "."
                sandbox_root = "examples/sandbox"
                project_json_path = "project.json"
                project_name = "pester-project"
                known_asset_folders = @($generatedRel)
                generated_asset_candidate_folders = @($generatedRel)
                sandbox_evidence_folders = @("examples/sandbox")
                gem_names = @()
                configured_non_executed_path_hints = @()
                read_only_project_scan = $true
                explicit_non_admissions = @("authoritative_writes", "asset_processor_execution", "o3de_editor_execution")
                output_path = $projectRel
                created_utc = "2026-05-05T00:00:00Z"
            })

            $realDiagRel = ""
            $realDiagAbs = $null
            if ($IncludeRealDiagnostic) {
                $realDiagRel = "examples/sandbox/ap-real-binary-diagnostic-executions/pester-ap-source-file-real-diagnostic-$suffix.json"
                $realDiagAbs = Join-Path $repoRoot $realDiagRel
                Write-JsonUtf8NoBom -Path $realDiagAbs -Object ([ordered]@{
                    schema_version = "1.0.0"
                    real_binary_diagnostic_execution_id = $realDiagId
                    source_ap_binary_preflight_id = $preflightId
                    sandbox_root = "examples/sandbox"
                    selected_binary_path = $binaryRel
                    binary_kind = "AssetProcessorBatch"
                    execution_mode = "RealBinaryDiagnosticOnly"
                    approved_by_flag = $true
                    diagnostic_argument = "--version"
                    command_display = "`"$binaryRel`" --version"
                    command_executed = $true
                    command_allowlisted = $true
                    local_only = $true
                    timeout_seconds = 30
                    exit_code = 0
                    stdout_path = ""
                    stderr_path = ""
                    stdout_sha256 = ""
                    stderr_sha256 = ""
                    execution_status = "succeeded"
                    blocked_reason = ""
                    product_ids_claimed = $false
                    asset_ids_claimed = $false
                    source_uuids_claimed = $false
                    product_resolution_claimed = $false
                    cache_access_admitted = $false
                    live_database_access_admitted = $false
                    spawn_admitted = $false
                    publish_admitted = $false
                    explicit_non_admissions = @("authoritative_writes")
                    output_path = $realDiagRel
                    started_utc = "2026-05-05T00:00:00Z"
                    completed_utc = "2026-05-05T00:00:01Z"
                })
            }

            return [ordered]@{
                suffix = $suffix
                generatedAbs = $generatedAbs
                sourceAbs = $sourceAbs
                sourceRel = $sourceRel
                binaryAbs = $binaryAbs
                binaryRel = $binaryRel
                reviewAbs = $reviewAbs
                reviewRel = $reviewRel
                proposalAbs = $proposalAbs
                proposalRel = $proposalRel
                apBinaryPreflightAbs = $apBinaryPreflightAbs
                apBinaryPreflightRel = $apBinaryPreflightRel
                projectAbs = $projectAbs
                projectRel = $projectRel
                realDiagAbs = $realDiagAbs
                realDiagRel = $realDiagRel
            }
        }

        function Set-JsonValues {
            param(
                [Parameter(Mandatory = $true)][string]$Path,
                [Parameter(Mandatory = $true)][hashtable]$Updates
            )

            $payload = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
            foreach ($key in $Updates.Keys) {
                $payload.$key = $Updates[$key]
            }
            Write-JsonUtf8NoBom -Path $Path -Object $payload
        }

        function Remove-SourceFilePreflightFixture {
            param([Parameter(Mandatory = $true)]$Context)

            $preflightRoot = Join-Path $repoRoot "examples/sandbox/ap-source-file-diagnostic-preflights"
            $bundleRoot = Join-Path $repoRoot "examples/sandbox/ap-source-file-diagnostic-preflight-bundles"

            Get-ChildItem -LiteralPath $preflightRoot -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -like "*$($Context.suffix)*.json" } |
                ForEach-Object {
                    if (Test-Path -LiteralPath $_.FullName) { Remove-Item -LiteralPath $_.FullName -Force }
                }

            Get-ChildItem -LiteralPath $bundleRoot -Directory -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -like "*$($Context.suffix)*" } |
                ForEach-Object {
                    if (Test-Path -LiteralPath $_.FullName) { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
                }

            foreach ($path in @(
                $Context.reviewAbs,
                $Context.proposalAbs,
                $Context.apBinaryPreflightAbs,
                $Context.projectAbs,
                $Context.realDiagAbs,
                $Context.sourceAbs,
                $Context.binaryAbs
            )) {
                if ($null -ne $path -and (Test-Path -LiteralPath $path)) {
                    Remove-Item -LiteralPath $path -Force
                }
            }

            if (Test-Path -LiteralPath $Context.generatedAbs) {
                Remove-Item -LiteralPath $Context.generatedAbs -Recurse -Force
            }
        }
    }

    It "builds source-file diagnostic preflight as display-only non-executing output" {
        $ctx = New-SourceFilePreflightFixture -IncludeRealDiagnostic $true
        try {
            $outputRel = "examples/sandbox/ap-source-file-diagnostic-preflights/pester-ap-source-file-preflight-$($ctx.suffix).json"
            $outputAbs = Join-Path $repoRoot $outputRel

            $sourceHashBefore = (Get-FileHash -LiteralPath $ctx.sourceAbs -Algorithm SHA256).Hash
            $binaryHashBefore = (Get-FileHash -LiteralPath $ctx.binaryAbs -Algorithm SHA256).Hash

            $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $buildCmd -ReviewPacketPath $ctx.reviewRel -ProposalPath $ctx.proposalRel -ApBinaryPreflightPath $ctx.apBinaryPreflightRel -RealBinaryDiagnosticExecutionPath $ctx.realDiagRel -ProjectInventoryPath $ctx.projectRel -OutputPath $outputRel
            $LASTEXITCODE | Should Be 0
            (Test-Path -LiteralPath $outputAbs) | Should Be $true

            $payload = $out | ConvertFrom-Json
            $payload.required_manual_confirmation | Should Be $true
            $payload.local_only | Should Be $true
            $payload.execution_admitted | Should Be $false
            $payload.output_path.StartsWith("examples/sandbox/ap-source-file-diagnostic-preflights/") | Should Be $true
            $payload.proposed_diagnostic_command_display.Contains("--source-file") | Should Be $true
            $payload.proposed_diagnostic_command_display.Contains("--no-execution") | Should Be $true
            $payload.proposed_diagnostic_command_display.ToLowerInvariant().Contains("--scan") | Should Be $false
            $payload.proposed_diagnostic_command_display.ToLowerInvariant().Contains("scanfolder") | Should Be $false

            (Get-FileHash -LiteralPath $ctx.sourceAbs -Algorithm SHA256).Hash | Should Be $sourceHashBefore
            (Get-FileHash -LiteralPath $ctx.binaryAbs -Algorithm SHA256).Hash | Should Be $binaryHashBefore

            if (Test-Path -LiteralPath $outputAbs) { Remove-Item -LiteralPath $outputAbs -Force }
        }
        finally {
            Remove-SourceFilePreflightFixture -Context $ctx
        }
    }

    It "blocks outside traversal inputs and forbidden readiness status" {
        $ctx = New-SourceFilePreflightFixture -IncludeRealDiagnostic $false
        try {
            $outsidePath = Join-Path $env:TEMP "outside-review-$($ctx.suffix).json"
            Set-Content -LiteralPath $outsidePath -Value "{}" -Encoding UTF8

            & powershell -NoProfile -ExecutionPolicy Bypass -File $buildCmd -ReviewPacketPath $outsidePath -ProposalPath $ctx.proposalRel -ApBinaryPreflightPath $ctx.apBinaryPreflightRel -ProjectInventoryPath $ctx.projectRel | Out-Null
            $LASTEXITCODE | Should Not Be 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $buildCmd -ReviewPacketPath "../outside/review.json" -ProposalPath $ctx.proposalRel -ApBinaryPreflightPath $ctx.apBinaryPreflightRel -ProjectInventoryPath $ctx.projectRel | Out-Null
            $LASTEXITCODE | Should Not Be 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $buildCmd -ReviewPacketPath $ctx.reviewRel -ProposalPath $ctx.proposalRel -ApBinaryPreflightPath $ctx.apBinaryPreflightRel -ProjectInventoryPath $ctx.projectRel -OutputPath "../outside/preflight.json" | Out-Null
            $LASTEXITCODE | Should Not Be 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $buildCmd -ReviewPacketPath $ctx.reviewRel -ProposalPath $ctx.proposalRel -ApBinaryPreflightPath $ctx.apBinaryPreflightRel -ProjectInventoryPath $ctx.projectRel -ReadinessStatus "executed" | Out-Null
            $LASTEXITCODE | Should Not Be 0

            if (Test-Path -LiteralPath $outsidePath) { Remove-Item -LiteralPath $outsidePath -Force }
        }
        finally {
            Remove-SourceFilePreflightFixture -Context $ctx
        }
    }

    It "blocks unsafe command tokens cache and assetdb paths and preserves inspect read-only" {
        $ctx = New-SourceFilePreflightFixture -IncludeRealDiagnostic $false
        try {
            $scenarios = @(
                @{ updates = @{ selected_binary_path = "$($ctx.binaryRel)|whoami" }; expected = "selected_binary_path_contains_shell_operators" },
                @{ updates = @{ selected_binary_path = "Cache/project/AssetProcessorBatch.exe" }; expected = "selected_binary_path_references_cache" },
                @{ updates = @{ selected_binary_path = "assetdb.sqlite" }; expected = "selected_binary_path_references_database" }
            )

            foreach ($scenario in $scenarios) {
                Set-JsonValues -Path $ctx.apBinaryPreflightAbs -Updates @{
                    selected_binary_path = $ctx.binaryRel
                    binary_exists = $true
                    binary_allowed_for_future_execution_request = $true
                    binary_kind = "AssetProcessorBatch"
                    required_manual_confirmation = $true
                    local_only = $true
                    execution_admitted = $false
                    readiness_status = "ready_for_future_real_ap_execution_request"
                }
                Set-JsonValues -Path $ctx.apBinaryPreflightAbs -Updates $scenario.updates

                $outputRel = "examples/sandbox/ap-source-file-diagnostic-preflights/pester-ap-source-file-safety-$($ctx.suffix)-$([Guid]::NewGuid().ToString('N')).json"
                $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $buildCmd -ReviewPacketPath $ctx.reviewRel -ProposalPath $ctx.proposalRel -ApBinaryPreflightPath $ctx.apBinaryPreflightRel -ProjectInventoryPath $ctx.projectRel -OutputPath $outputRel
                $LASTEXITCODE | Should Be 0
                $payload = $out | ConvertFrom-Json
                $payload.readiness_status | Should Be "blocked_safety_boundary"
                ($payload.blocking_reasons -contains $scenario.expected) | Should Be $true

                $outputAbs = Join-Path $repoRoot $payload.output_path
                if (Test-Path -LiteralPath $outputAbs) { Remove-Item -LiteralPath $outputAbs -Force }
            }

            Set-JsonValues -Path $ctx.reviewAbs -Updates @{ candidate_relative_path = "scripts/generated/*.fbx" }
            Set-JsonValues -Path $ctx.proposalAbs -Updates @{ candidate_relative_path = "scripts/generated/*.fbx" }
            $wildcardRel = "examples/sandbox/ap-source-file-diagnostic-preflights/pester-ap-source-file-wildcard-$($ctx.suffix).json"
            $wildcard = & powershell -NoProfile -ExecutionPolicy Bypass -File $buildCmd -ReviewPacketPath $ctx.reviewRel -ProposalPath $ctx.proposalRel -ApBinaryPreflightPath $ctx.apBinaryPreflightRel -ProjectInventoryPath $ctx.projectRel -OutputPath $wildcardRel
            $LASTEXITCODE | Should Be 0
            $wildcardPayload = $wildcard | ConvertFrom-Json
            $wildcardPayload.readiness_status | Should Be "blocked_safety_boundary"
            ($wildcardPayload.blocking_reasons -contains "candidate_relative_path_must_be_single_file_not_wildcard") | Should Be $true

            $wildcardAbs = Join-Path $repoRoot $wildcardPayload.output_path
            $preflightHashBefore = (Get-FileHash -LiteralPath $wildcardAbs -Algorithm SHA256).Hash
            $reviewHashBefore = (Get-FileHash -LiteralPath $ctx.reviewAbs -Algorithm SHA256).Hash

            $listOut = & powershell -NoProfile -ExecutionPolicy Bypass -File $inspectCmd -List
            $LASTEXITCODE | Should Be 0
            ($listOut | ConvertFrom-Json).preflight_count | Should BeGreaterThan 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $inspectCmd -PreflightId $wildcardPayload.source_file_diagnostic_preflight_id -ShowRequirements -ShowBlockingReasons | Out-Null
            $LASTEXITCODE | Should Be 0

            (Get-FileHash -LiteralPath $wildcardAbs -Algorithm SHA256).Hash | Should Be $preflightHashBefore
            (Get-FileHash -LiteralPath $ctx.reviewAbs -Algorithm SHA256).Hash | Should Be $reviewHashBefore

            if (Test-Path -LiteralPath $wildcardAbs) { Remove-Item -LiteralPath $wildcardAbs -Force }
        }
        finally {
            Remove-SourceFilePreflightFixture -Context $ctx
        }
    }

    It "bundle export is sandbox-local JSON snapshots only and source asset/AP binary are not copied" {
        $ctx = New-SourceFilePreflightFixture -IncludeRealDiagnostic $true
        try {
            $outputRel = "examples/sandbox/ap-source-file-diagnostic-preflights/pester-ap-source-file-bundle-preflight-$($ctx.suffix).json"
            $outputAbs = Join-Path $repoRoot $outputRel
            $bundleRel = "examples/sandbox/ap-source-file-diagnostic-preflight-bundles/pester-ap-source-file-$($ctx.suffix)/bundle.manifest.json"
            $bundleAbs = Join-Path $repoRoot $bundleRel
            $bundleDir = Split-Path -Parent $bundleAbs

            & powershell -NoProfile -ExecutionPolicy Bypass -File $buildCmd -ReviewPacketPath $ctx.reviewRel -ProposalPath $ctx.proposalRel -ApBinaryPreflightPath $ctx.apBinaryPreflightRel -RealBinaryDiagnosticExecutionPath $ctx.realDiagRel -ProjectInventoryPath $ctx.projectRel -OutputPath $outputRel | Out-Null
            $LASTEXITCODE | Should Be 0
            (Test-Path -LiteralPath $outputAbs) | Should Be $true

            $bundleOut = & powershell -NoProfile -ExecutionPolicy Bypass -File $bundleCmd -PreflightPath $outputRel -BundlePath $bundleRel
            $LASTEXITCODE | Should Be 0
            (Test-Path -LiteralPath $bundleAbs) | Should Be $true

            $manifest = $bundleOut | ConvertFrom-Json
            $manifest.bundle_path.StartsWith("examples/sandbox/ap-source-file-diagnostic-preflight-bundles/") | Should Be $true
            foreach ($rel in $manifest.copied_artifact_paths) {
                $rel.StartsWith("examples/sandbox/ap-source-file-diagnostic-preflight-bundles/") | Should Be $true
                $rel.ToLowerInvariant().EndsWith(".json") | Should Be $true
            }

            $fileNames = Get-ChildItem -LiteralPath $bundleDir -Recurse -File | Select-Object -ExpandProperty Name
            ($fileNames -contains ([System.IO.Path]::GetFileName($ctx.sourceRel))) | Should Be $false
            ($fileNames -contains ([System.IO.Path]::GetFileName($ctx.binaryRel))) | Should Be $false

            & powershell -NoProfile -ExecutionPolicy Bypass -File $bundleCmd -PreflightPath $outputRel -BundlePath "../outside/bundle.manifest.json" | Out-Null
            $LASTEXITCODE | Should Not Be 0

            if (Test-Path -LiteralPath $bundleDir) { Remove-Item -LiteralPath $bundleDir -Recurse -Force }
            if (Test-Path -LiteralPath $outputAbs) { Remove-Item -LiteralPath $outputAbs -Force }
        }
        finally {
            Remove-SourceFilePreflightFixture -Context $ctx
        }
    }

    It "keeps broad execution blocked and authoritative writer absent" {
        (Test-Path -LiteralPath $authoritative) | Should Be $false

        $combined = (
            (Get-Content -LiteralPath $buildCmd -Raw).ToLowerInvariant() + "`n" +
            (Get-Content -LiteralPath $inspectCmd -Raw).ToLowerInvariant() + "`n" +
            (Get-Content -LiteralPath $bundleCmd -Raw).ToLowerInvariant()
        )

        $combined.Contains("o3de.exe") | Should Be $false
        $combined.Contains("editor.exe") | Should Be $false
        $combined.Contains("invoke-expression") | Should Be $false
        $combined.Contains("start-process") | Should Be $false
        $combined.Contains("invoke-maxineauthoritativeresolverwrite.ps1") | Should Be $false

        $matrix = Get-Content -LiteralPath (Join-Path $repoRoot "examples/capabilities/maxine-capability-matrix.json") -Raw | ConvertFrom-Json
        $caps = $matrix.capabilities

        $caps.ap_source_file_diagnostic_preflight_build | Should Be "sandbox_only"
        $caps.ap_source_file_diagnostic_preflight_inspect | Should Be "read_only"
        $caps.ap_source_file_diagnostic_preflight_bundle_export | Should Be "sandbox_only"
        $caps.asset_processor_execution | Should Be "blocked"
        $caps.real_asset_processor_execution | Should Be "blocked"
        $caps.ap_source_file_processing_execution | Should Be "blocked"
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
