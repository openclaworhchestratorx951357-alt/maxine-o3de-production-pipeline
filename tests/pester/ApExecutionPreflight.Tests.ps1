Describe "AP Execution Preflight Pack" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $importCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApEvidenceImport.ps1"
        $buildCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApExecutionPreflightBuild.ps1"
        $inspectCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApExecutionPreflightInspect.ps1"
        $bundleCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApExecutionPreflightBundleExport.ps1"
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

        function New-PreflightFixture {
            $suffix = [Guid]::NewGuid().ToString("N")
            $generatedRel = "scripts/generated/pester-ap-preflight-$suffix"
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

            $projectRel = "examples/sandbox/project-inventory/pester-ap-preflight-project-$suffix.json"
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

            $assetInventoryRel = "examples/sandbox/asset-candidates/pester-ap-preflight-asset-inventory-$suffix.json"
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

            $proposalRel = "examples/sandbox/product-resolution-proposals/pester-ap-preflight-proposal-$suffix.json"
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

            $importRel = "examples/sandbox/ap-evidence-imports/pester-ap-preflight-import-$suffix.json"
            $importAbs = Join-Path $repoRoot $importRel
            & powershell -NoProfile -ExecutionPolicy Bypass -File $importCmd -ProposalPath $proposalRel -ProjectInventoryPath $projectRel -AssetCandidateInventoryPath $assetInventoryRel -EvidencePaths "$logRel,$snapshotRel" -OutputPath $importRel | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "failed to create AP evidence import fixture"
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
            }
        }

        function Remove-PreflightFixture {
            param([Parameter(Mandatory = $true)]$Context)

            foreach ($path in @(
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
        }
    }

    It "builds non-executing preflight as sandbox-local output" {
        $ctx = New-PreflightFixture
        try {
            $preflightRel = "examples/sandbox/ap-execution-preflights/pester-ap-preflight-$($ctx.suffix).json"
            $preflightAbs = Join-Path $repoRoot $preflightRel

            $modelHashBefore = (Get-FileHash -LiteralPath $ctx.modelAbs -Algorithm SHA256).Hash
            $logHashBefore = (Get-FileHash -LiteralPath $ctx.logAbs -Algorithm SHA256).Hash

            $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $buildCmd -ApEvidenceImportPath $ctx.importRel -ProposalPath $ctx.proposalRel -ProjectInventoryPath $ctx.projectRel -OutputPath $preflightRel
            $LASTEXITCODE | Should Be 0
            (Test-Path -LiteralPath $preflightAbs) | Should Be $true

            $obj = $output | ConvertFrom-Json
            $obj.required_manual_confirmation | Should Be $true
            $obj.local_only | Should Be $true
            $obj.execution_admitted | Should Be $false
            $obj.output_path.StartsWith("examples/sandbox/ap-execution-preflights/") | Should Be $true
            $obj.proposed_ap_command_display.Contains("ap_batch_display_only") | Should Be $true
            $obj.proposed_ap_command_display.Contains("|") | Should Be $false
            $obj.proposed_ap_command_display.Contains(";") | Should Be $false

            (Get-FileHash -LiteralPath $ctx.modelAbs -Algorithm SHA256).Hash | Should Be $modelHashBefore
            (Get-FileHash -LiteralPath $ctx.logAbs -Algorithm SHA256).Hash | Should Be $logHashBefore

            if (Test-Path -LiteralPath $preflightAbs) { Remove-Item -LiteralPath $preflightAbs -Force }
        }
        finally {
            Remove-PreflightFixture -Context $ctx
        }
    }

    It "blocks traversal and forbidden readiness statuses" {
        $ctx = New-PreflightFixture
        try {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $buildCmd -ApEvidenceImportPath "../outside-import.json" -ProposalPath $ctx.proposalRel | Out-Null
            $LASTEXITCODE | Should Not Be 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $buildCmd -ApEvidenceImportPath $ctx.importRel -ProposalPath $ctx.proposalRel -OutputPath "../outside/preflight.json" | Out-Null
            $LASTEXITCODE | Should Not Be 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $buildCmd -ApEvidenceImportPath $ctx.importRel -ProposalPath $ctx.proposalRel -ReadinessStatus "executed" | Out-Null
            $LASTEXITCODE | Should Not Be 0
        }
        finally {
            Remove-PreflightFixture -Context $ctx
        }
    }

    It "inspect is read-only and bundle export is sandbox-local JSON-only" {
        $ctx = New-PreflightFixture
        try {
            $preflightRel = "examples/sandbox/ap-execution-preflights/pester-ap-preflight-inspect-$($ctx.suffix).json"
            $preflightAbs = Join-Path $repoRoot $preflightRel
            $bundleRel = "examples/sandbox/ap-execution-preflight-bundles/pester-ap-preflight-$($ctx.suffix)/bundle.manifest.json"
            $bundleAbs = Join-Path $repoRoot $bundleRel
            $bundleDir = Split-Path -Parent $bundleAbs

            & powershell -NoProfile -ExecutionPolicy Bypass -File $buildCmd -ApEvidenceImportPath $ctx.importRel -ProposalPath $ctx.proposalRel -ProjectInventoryPath $ctx.projectRel -OutputPath $preflightRel | Out-Null
            $LASTEXITCODE | Should Be 0

            $preflightObj = Get-Content -LiteralPath $preflightAbs -Raw | ConvertFrom-Json
            $preflightHashBefore = (Get-FileHash -LiteralPath $preflightAbs -Algorithm SHA256).Hash
            $importHashBefore = (Get-FileHash -LiteralPath $ctx.importAbs -Algorithm SHA256).Hash

            $listOut = & powershell -NoProfile -ExecutionPolicy Bypass -File $inspectCmd -List
            $LASTEXITCODE | Should Be 0
            ($listOut | ConvertFrom-Json).preflight_count | Should BeGreaterThan 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $inspectCmd -PreflightId $preflightObj.preflight_id -ShowBlockingReasons -ShowWarnings | Out-Null
            $LASTEXITCODE | Should Be 0

            (Get-FileHash -LiteralPath $preflightAbs -Algorithm SHA256).Hash | Should Be $preflightHashBefore
            (Get-FileHash -LiteralPath $ctx.importAbs -Algorithm SHA256).Hash | Should Be $importHashBefore

            $bundleOut = & powershell -NoProfile -ExecutionPolicy Bypass -File $bundleCmd -PreflightPath $preflightRel -BundlePath $bundleRel
            $LASTEXITCODE | Should Be 0
            (Test-Path -LiteralPath $bundleAbs) | Should Be $true

            $manifest = $bundleOut | ConvertFrom-Json
            $manifest.bundle_path.StartsWith("examples/sandbox/ap-execution-preflight-bundles/") | Should Be $true
            foreach ($rel in $manifest.copied_artifact_paths) {
                $rel.StartsWith("examples/sandbox/ap-execution-preflight-bundles/") | Should Be $true
                $rel.EndsWith(".json") | Should Be $true
            }

            ((Get-ChildItem -LiteralPath $bundleDir -Recurse -File | Select-Object -ExpandProperty Name) -contains ([System.IO.Path]::GetFileName($ctx.modelRel))) | Should Be $false
            ((Get-ChildItem -LiteralPath $bundleDir -Recurse -File | Select-Object -ExpandProperty Name) -contains ([System.IO.Path]::GetFileName($ctx.logRel))) | Should Be $false

            & powershell -NoProfile -ExecutionPolicy Bypass -File $bundleCmd -PreflightPath $preflightRel -BundlePath "../outside/bundle.manifest.json" | Out-Null
            $LASTEXITCODE | Should Not Be 0

            if (Test-Path -LiteralPath $bundleDir) { Remove-Item -LiteralPath $bundleDir -Recurse -Force }
            if (Test-Path -LiteralPath $preflightAbs) { Remove-Item -LiteralPath $preflightAbs -Force }
        }
        finally {
            Remove-PreflightFixture -Context $ctx
        }
    }

    It "keeps AP/O3DE execution blocked and authoritative writer absent" {
        (Test-Path -LiteralPath $authoritative) | Should Be $false

        $combined = (
            (Get-Content -LiteralPath $buildCmd -Raw).ToLowerInvariant() + "`n" +
            (Get-Content -LiteralPath $inspectCmd -Raw).ToLowerInvariant() + "`n" +
            (Get-Content -LiteralPath $bundleCmd -Raw).ToLowerInvariant()
        )

        $combined.Contains("o3de editor") | Should Be $false
        $combined.Contains("asset processor") | Should Be $false
        $combined.Contains("o3de.exe") | Should Be $false
        $combined.Contains("editor.exe") | Should Be $false
        $combined.Contains("invoke-maxineauthoritativeresolverwrite.ps1") | Should Be $false
        $combined.Contains("start-process") | Should Be $false
        $combined.Contains("invoke-expression") | Should Be $false

        $matrix = Get-Content -LiteralPath (Join-Path $repoRoot "examples/capabilities/maxine-capability-matrix.json") -Raw | ConvertFrom-Json
        $caps = $matrix.capabilities
        $caps.ap_execution_preflight_build | Should Be "sandbox_only"
        $caps.ap_execution_preflight_inspect | Should Be "read_only"
        $caps.ap_execution_preflight_bundle_export | Should Be "sandbox_only"
        $caps.asset_processor_execution | Should Be "blocked"
        $caps.o3de_editor_execution | Should Be "blocked"
        $caps.o3de_cli_execution | Should Be "blocked"
        $caps.product_resolution | Should Be "blocked"
        $caps.product_id_claims | Should Be "blocked"
        $caps.asset_id_claims | Should Be "blocked"
        $caps.source_uuid_claims | Should Be "blocked"
        $caps.spawning | Should Be "blocked"
        $caps.publishing | Should Be "blocked"
    }
}
