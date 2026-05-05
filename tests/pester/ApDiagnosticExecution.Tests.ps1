Describe "AP Diagnostic Execution" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $importCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApEvidenceImport.ps1"
        $preflightBuildCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApExecutionPreflightBuild.ps1"
        $diagCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApDiagnosticExecution.ps1"
        $inspectCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApDiagnosticExecutionInspect.ps1"
        $bundleCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApDiagnosticExecutionBundleExport.ps1"
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

        function New-DiagnosticFixture {
            $suffix = [Guid]::NewGuid().ToString("N")
            $generatedRel = "scripts/generated/pester-ap-diag-$suffix"
            $generatedAbs = Join-Path $repoRoot $generatedRel
            New-Item -Path $generatedAbs -ItemType Directory -Force | Out-Null

            $modelRel = "$generatedRel/character-$suffix.fbx"
            $modelAbs = Join-Path $repoRoot $modelRel
            Set-Content -LiteralPath $modelAbs -Value "source-binary-like" -Encoding UTF8

            $logRel = "$generatedRel/ap-export-$suffix.log"
            $logAbs = Join-Path $repoRoot $logRel
            Set-Content -LiteralPath $logAbs -Value @(
                "Info: AP export imported only",
                "Warning: pipeline warning mention",
                "ProductCandidate: Cache/project/model.azmodel",
                "SourcePath: scripts/generated/foo.fbx"
            ) -Encoding UTF8

            $snapshotRel = "$generatedRel/ap-snapshot-$suffix.json"
            $snapshotAbs = Join-Path $repoRoot $snapshotRel
            Write-JsonUtf8NoBom -Path $snapshotAbs -Object ([ordered]@{
                snapshot_type = "ap_metadata"
                product_hint = "Cache/project/model.azmodel"
                source_hint = "scripts/generated/foo.fbx"
            })

            $projectId = "project-inventory-$suffix"
            $assetInventoryId = "asset-inventory-$suffix"
            $proposalId = "product-resolution-proposal-$suffix"

            $projectRel = "examples/sandbox/project-inventory/pester-ap-diag-project-$suffix.json"
            $projectAbs = Join-Path $repoRoot $projectRel
            Write-JsonUtf8NoBom -Path $projectAbs -Object ([ordered]@{
                schema_version = "1.0.0"
                inventory_id = $projectId
                project_root = "."
                sandbox_root = "examples/sandbox"
                known_asset_folders = @($generatedRel)
                output_path = $projectRel
                created_utc = "2026-05-04T00:00:00Z"
            })

            $assetInventoryRel = "examples/sandbox/asset-candidates/pester-ap-diag-asset-inventory-$suffix.json"
            $assetInventoryAbs = Join-Path $repoRoot $assetInventoryRel
            Write-JsonUtf8NoBom -Path $assetInventoryAbs -Object ([ordered]@{
                schema_version = "1.0.0"
                inventory_id = $assetInventoryId
                source_project_inventory_id = $projectId
                project_root = "."
                sandbox_root = "examples/sandbox"
                scanned_roots = @($generatedRel)
                generated_candidate_folders = @($generatedRel)
                source_asset_candidates = @()
                material_texture_candidates = @()
                metadata_provenance_candidates = @()
                linked_sandbox_evidence = @{}
                warnings = @()
                explicit_non_admissions = @("authoritative_writes", "product_resolution", "asset_id_claims", "source_uuid_claims", "spawning", "publishing", "o3de_editor_execution", "asset_processor_execution", "cache_read")
                output_path = $assetInventoryRel
                created_utc = "2026-05-04T00:00:00Z"
            })

            $proposalRel = "examples/sandbox/product-resolution-proposals/pester-ap-diag-proposal-$suffix.json"
            $proposalAbs = Join-Path $repoRoot $proposalRel
            $modelHash = (Get-FileHash -LiteralPath $modelAbs -Algorithm SHA256).Hash.ToLowerInvariant()
            Write-JsonUtf8NoBom -Path $proposalAbs -Object ([ordered]@{
                schema_version = "1.0.0"
                proposal_id = $proposalId
                source_review_packet_id = "review-$suffix"
                source_inventory_id = $assetInventoryId
                source_project_inventory_id = $projectId
                candidate_id = "candidate-$suffix"
                project_root = "."
                sandbox_root = "examples/sandbox"
                candidate_relative_path = $modelRel
                candidate_extension = ".fbx"
                candidate_category = "character_source"
                candidate_sha256 = $modelHash
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
                safety_summary = "proposal only"
                explicit_non_admissions = @("authoritative_writes", "product_resolution", "asset_id_claims", "source_uuid_claims", "spawning", "publishing", "o3de_editor_execution", "asset_processor_execution", "cache_read")
                output_path = $proposalRel
                created_utc = "2026-05-04T00:00:00Z"
            })

            $importRel = "examples/sandbox/ap-evidence-imports/pester-ap-diag-import-$suffix.json"
            $importAbs = Join-Path $repoRoot $importRel
            & powershell -NoProfile -ExecutionPolicy Bypass -File $importCmd -ProposalPath $proposalRel -ProjectInventoryPath $projectRel -AssetCandidateInventoryPath $assetInventoryRel -EvidencePaths "$logRel,$snapshotRel" -OutputPath $importRel | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "failed to create AP evidence import fixture"
            }

            $preflightRel = "examples/sandbox/ap-execution-preflights/pester-ap-diag-preflight-$suffix.json"
            $preflightAbs = Join-Path $repoRoot $preflightRel
            & powershell -NoProfile -ExecutionPolicy Bypass -File $preflightBuildCmd -ApEvidenceImportPath $importRel -ProposalPath $proposalRel -ProjectInventoryPath $projectRel -ReadinessStatus "ready_for_future_execution_request" -OutputPath $preflightRel | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "failed to create AP execution preflight fixture"
            }

            return [ordered]@{
                suffix = $suffix
                generatedAbs = $generatedAbs
                modelAbs = $modelAbs
                modelRel = $modelRel
                logAbs = $logAbs
                logRel = $logRel
                snapshotAbs = $snapshotAbs
                snapshotRel = $snapshotRel
                projectAbs = $projectAbs
                projectRel = $projectRel
                assetInventoryAbs = $assetInventoryAbs
                assetInventoryRel = $assetInventoryRel
                proposalAbs = $proposalAbs
                proposalRel = $proposalRel
                importAbs = $importAbs
                importRel = $importRel
                preflightAbs = $preflightAbs
                preflightRel = $preflightRel
            }
        }

        function Remove-DiagnosticFixture {
            param([Parameter(Mandatory = $true)]$Context)

            foreach ($path in @(
                $Context.preflightAbs,
                $Context.proposalAbs,
                $Context.projectAbs,
                $Context.assetInventoryAbs,
                $Context.importAbs,
                $Context.logAbs,
                $Context.snapshotAbs,
                $Context.modelAbs
            )) {
                if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
            }
            if (Test-Path -LiteralPath $Context.generatedAbs) {
                Remove-Item -LiteralPath $Context.generatedAbs -Recurse -Force
            }

            $diagFiles = Get-ChildItem -LiteralPath (Join-Path $repoRoot "examples/sandbox/ap-diagnostic-executions") -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*${($Context.suffix)}*" }
            foreach ($diag in $diagFiles) {
                if (Test-Path -LiteralPath $diag.FullName) { Remove-Item -LiteralPath $diag.FullName -Force }
            }

            $bundleDir = Join-Path $repoRoot "examples/sandbox/ap-diagnostic-execution-bundles/pester-ap-diag-$($Context.suffix)"
            if (Test-Path -LiteralPath $bundleDir) {
                Remove-Item -LiteralPath $bundleDir -Recurse -Force
            }
        }
    }

    It "blocks execution without approval and blocks unsafe preflight command source" {
        $ctx = New-DiagnosticFixture
        try {
            $diagRel1 = "examples/sandbox/ap-diagnostic-executions/pester-ap-diag-no-approval-$($ctx.suffix).json"
            $diagAbs1 = Join-Path $repoRoot $diagRel1
            $resultNoApproval = & powershell -NoProfile -ExecutionPolicy Bypass -File $diagCmd -PreflightPath $ctx.preflightRel -UseMockDiagnosticCommand -OutputPath $diagRel1
            $LASTEXITCODE | Should Be 0
            $payload1 = $resultNoApproval | ConvertFrom-Json
            $payload1.execution_status | Should Be "blocked"
            $payload1.command_executed | Should Be $false
            $payload1.blocked_reason.Contains("without approval flag") | Should Be $true

            $preflight = Get-Content -LiteralPath $ctx.preflightAbs -Raw | ConvertFrom-Json
            $preflight.proposed_ap_command_display = "user supplied command text"
            Write-JsonUtf8NoBom -Path $ctx.preflightAbs -Object $preflight

            $diagRel2 = "examples/sandbox/ap-diagnostic-executions/pester-ap-diag-unsafe-command-$($ctx.suffix).json"
            $diagAbs2 = Join-Path $repoRoot $diagRel2
            $resultUnsafe = & powershell -NoProfile -ExecutionPolicy Bypass -File $diagCmd -PreflightPath $ctx.preflightRel -ApproveLocalDiagnosticExecution -UseMockDiagnosticCommand -OutputPath $diagRel2
            $LASTEXITCODE | Should Be 0
            $payload2 = $resultUnsafe | ConvertFrom-Json
            $payload2.execution_status | Should Be "blocked"
            $payload2.command_executed | Should Be $false
            $payload2.blocked_reason.Contains("arbitrary user text") | Should Be $true

            if (Test-Path -LiteralPath $diagAbs1) { Remove-Item -LiteralPath $diagAbs1 -Force }
            if (Test-Path -LiteralPath $diagAbs2) { Remove-Item -LiteralPath $diagAbs2 -Force }
        }
        finally {
            Remove-DiagnosticFixture -Context $ctx
        }
    }

    It "succeeds in allowlisted mock mode and records stdout/stderr hashes" {
        $ctx = New-DiagnosticFixture
        try {
            $diagRel = "examples/sandbox/ap-diagnostic-executions/pester-ap-diag-success-$($ctx.suffix).json"
            $diagAbs = Join-Path $repoRoot $diagRel

            $result = & powershell -NoProfile -ExecutionPolicy Bypass -File $diagCmd -PreflightPath $ctx.preflightRel -ApproveLocalDiagnosticExecution -UseMockDiagnosticCommand -OutputPath $diagRel
            $LASTEXITCODE | Should Be 0
            (Test-Path -LiteralPath $diagAbs) | Should Be $true

            $payload = $result | ConvertFrom-Json
            $payload.execution_status | Should Be "succeeded"
            $payload.command_executed | Should Be $true
            $payload.command_allowlisted | Should Be $true
            $payload.execution_mode | Should Be "DiagnosticOnly"
            $payload.local_only | Should Be $true
            $payload.exit_code | Should Be 0
            $payload.output_path.StartsWith("examples/sandbox/ap-diagnostic-executions/") | Should Be $true
            $payload.stdout_path.StartsWith("examples/sandbox/ap-diagnostic-executions/") | Should Be $true
            $payload.stderr_path.StartsWith("examples/sandbox/ap-diagnostic-executions/") | Should Be $true
            $payload.stdout_sha256.Length | Should Be 64
            $payload.stderr_sha256.Length | Should Be 64

            $stdoutAbs = Join-Path $repoRoot $payload.stdout_path
            $stderrAbs = Join-Path $repoRoot $payload.stderr_path
            (Test-Path -LiteralPath $stdoutAbs) | Should Be $true
            (Test-Path -LiteralPath $stderrAbs) | Should Be $true

            if (Test-Path -LiteralPath $stdoutAbs) { Remove-Item -LiteralPath $stdoutAbs -Force }
            if (Test-Path -LiteralPath $stderrAbs) { Remove-Item -LiteralPath $stderrAbs -Force }
            if (Test-Path -LiteralPath $diagAbs) { Remove-Item -LiteralPath $diagAbs -Force }
        }
        finally {
            Remove-DiagnosticFixture -Context $ctx
        }
    }

    It "inspect is read-only and bundle export is sandbox-local JSON plus stdout/stderr text only" {
        $ctx = New-DiagnosticFixture
        try {
            $diagRel = "examples/sandbox/ap-diagnostic-executions/pester-ap-diag-readonly-$($ctx.suffix).json"
            $diagAbs = Join-Path $repoRoot $diagRel
            $bundleRel = "examples/sandbox/ap-diagnostic-execution-bundles/pester-ap-diag-$($ctx.suffix)/bundle.manifest.json"
            $bundleAbs = Join-Path $repoRoot $bundleRel
            $bundleDir = Split-Path -Parent $bundleAbs

            $result = & powershell -NoProfile -ExecutionPolicy Bypass -File $diagCmd -PreflightPath $ctx.preflightRel -ApproveLocalDiagnosticExecution -UseMockDiagnosticCommand -OutputPath $diagRel
            $LASTEXITCODE | Should Be 0
            $payload = $result | ConvertFrom-Json

            $diagHashBefore = (Get-FileHash -LiteralPath $diagAbs -Algorithm SHA256).Hash
            $stdoutAbs = Join-Path $repoRoot $payload.stdout_path
            $stderrAbs = Join-Path $repoRoot $payload.stderr_path
            $stdoutHashBefore = (Get-FileHash -LiteralPath $stdoutAbs -Algorithm SHA256).Hash
            $stderrHashBefore = (Get-FileHash -LiteralPath $stderrAbs -Algorithm SHA256).Hash

            $listOut = & powershell -NoProfile -ExecutionPolicy Bypass -File $inspectCmd -List
            $LASTEXITCODE | Should Be 0
            ($listOut | ConvertFrom-Json).diagnostic_execution_count | Should BeGreaterThan 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $inspectCmd -DiagnosticExecutionId $payload.diagnostic_execution_id -ShowOutputRefs -ShowBlockedReason | Out-Null
            $LASTEXITCODE | Should Be 0

            (Get-FileHash -LiteralPath $diagAbs -Algorithm SHA256).Hash | Should Be $diagHashBefore
            (Get-FileHash -LiteralPath $stdoutAbs -Algorithm SHA256).Hash | Should Be $stdoutHashBefore
            (Get-FileHash -LiteralPath $stderrAbs -Algorithm SHA256).Hash | Should Be $stderrHashBefore

            $bundleOut = & powershell -NoProfile -ExecutionPolicy Bypass -File $bundleCmd -DiagnosticExecutionPath $payload.output_path -BundlePath $bundleRel
            $LASTEXITCODE | Should Be 0
            (Test-Path -LiteralPath $bundleAbs) | Should Be $true

            $manifest = $bundleOut | ConvertFrom-Json
            $manifest.bundle_path.StartsWith("examples/sandbox/ap-diagnostic-execution-bundles/") | Should Be $true
            foreach ($rel in $manifest.copied_artifact_paths) {
                $rel.StartsWith("examples/sandbox/ap-diagnostic-execution-bundles/") | Should Be $true
                ($rel.EndsWith(".json") -or $rel.EndsWith(".txt")) | Should Be $true
            }

            ((Get-ChildItem -LiteralPath $bundleDir -Recurse -File | Select-Object -ExpandProperty Name) -contains ([System.IO.Path]::GetFileName($ctx.modelRel))) | Should Be $false
            ((Get-ChildItem -LiteralPath $bundleDir -Recurse -File | Select-Object -ExpandProperty Name) -contains ([System.IO.Path]::GetFileName($ctx.logRel))) | Should Be $false

            & powershell -NoProfile -ExecutionPolicy Bypass -File $bundleCmd -DiagnosticExecutionPath $payload.output_path -BundlePath "../outside/bundle.manifest.json" | Out-Null
            $LASTEXITCODE | Should Not Be 0

            if (Test-Path -LiteralPath $bundleDir) { Remove-Item -LiteralPath $bundleDir -Recurse -Force }
            if (Test-Path -LiteralPath $stdoutAbs) { Remove-Item -LiteralPath $stdoutAbs -Force }
            if (Test-Path -LiteralPath $stderrAbs) { Remove-Item -LiteralPath $stderrAbs -Force }
            if (Test-Path -LiteralPath $diagAbs) { Remove-Item -LiteralPath $diagAbs -Force }
        }
        finally {
            Remove-DiagnosticFixture -Context $ctx
        }
    }

    It "keeps authoritative writer absent and broad AP/O3DE execution blocked" {
        (Test-Path -LiteralPath $authoritative) | Should Be $false

        $combined = (
            (Get-Content -LiteralPath $diagCmd -Raw).ToLowerInvariant() + "`n" +
            (Get-Content -LiteralPath $inspectCmd -Raw).ToLowerInvariant() + "`n" +
            (Get-Content -LiteralPath $bundleCmd -Raw).ToLowerInvariant()
        )

        $combined.Contains("assetprocessor.exe") | Should Be $false
        $combined.Contains("assetprocessorbatch.exe") | Should Be $false
        $combined.Contains("editor.exe") | Should Be $false
        $combined.Contains("o3de.exe") | Should Be $false
        $combined.Contains("invoke-maxineauthoritativeresolverwrite.ps1") | Should Be $false

        $matrix = Get-Content -LiteralPath (Join-Path $repoRoot "examples/capabilities/maxine-capability-matrix.json") -Raw | ConvertFrom-Json
        $caps = $matrix.capabilities
        $caps.ap_diagnostic_execution | Should Be "sandbox_only"
        $caps.asset_processor_execution | Should Be "blocked"
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
