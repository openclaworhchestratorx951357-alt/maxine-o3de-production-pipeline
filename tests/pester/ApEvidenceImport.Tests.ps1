Describe "AP Evidence Import Pack" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $importCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApEvidenceImport.ps1"
        $inspectCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApEvidenceInspect.ps1"
        $bundleCmd = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineApEvidenceBundleExport.ps1"
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

        function New-ApEvidenceFixture {
            $suffix = [Guid]::NewGuid().ToString("N")
            $generatedRel = "scripts/generated/pester-ap-evidence-$suffix"
            $generatedAbs = Join-Path $repoRoot $generatedRel
            New-Item -Path $generatedAbs -ItemType Directory -Force | Out-Null

            $modelRel = "$generatedRel/character-$suffix.fbx"
            $modelAbs = Join-Path $repoRoot $modelRel
            Set-Content -LiteralPath $modelAbs -Value "source-binary-like" -Encoding UTF8

            $logRel = "$generatedRel/assetprocessor-export-$suffix.log"
            $logAbs = Join-Path $repoRoot $logRel
            Set-Content -LiteralPath $logAbs -Value @(
                "Info: AP export imported only",
                "Warning: compile warning for scripts/generated/foo.material",
                "Error: missing dependency for scripts/generated/foo.fbx",
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

            $projectRel = "examples/sandbox/project-inventory/pester-ap-evidence-project-$suffix.json"
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

            $assetInventoryRel = "examples/sandbox/asset-candidates/pester-ap-evidence-asset-inventory-$suffix.json"
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

            $proposalRel = "examples/sandbox/product-resolution-proposals/pester-ap-evidence-proposal-$suffix.json"
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
            }
        }

        function Remove-ApEvidenceFixture {
            param([Parameter(Mandatory = $true)]$Context)

            foreach ($path in @(
                $Context.proposalAbs,
                $Context.projectAbs,
                $Context.assetInventoryAbs,
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

    It "imports AP evidence as read-only and writes sandbox-local output" {
        $ctx = New-ApEvidenceFixture
        try {
            $outputRel = "examples/sandbox/ap-evidence-imports/pester-ap-evidence-import-$($ctx.suffix).json"
            $outputAbs = Join-Path $repoRoot $outputRel

            $result = & powershell -NoProfile -ExecutionPolicy Bypass -File $importCmd -ProposalPath $ctx.proposalRel -ProjectInventoryPath $ctx.projectRel -AssetCandidateInventoryPath $ctx.assetInventoryRel -EvidencePaths "$($ctx.logRel),$($ctx.snapshotRel)" -OutputPath $outputRel
            $LASTEXITCODE | Should Be 0
            (Test-Path -LiteralPath $outputAbs) | Should Be $true

            $payload = $result | ConvertFrom-Json
            $payload.read_only | Should Be $true
            $payload.asset_processor_execution_admitted | Should Be $false
            $payload.o3de_execution_admitted | Should Be $false
            $payload.cache_access_admitted | Should Be $false
            $payload.live_database_access_admitted | Should Be $false
            $payload.product_ids_claimed | Should Be $false
            $payload.asset_ids_claimed | Should Be $false
            $payload.source_uuids_claimed | Should Be $false
            $payload.product_resolution_claimed | Should Be $false
            $payload.spawn_admitted | Should Be $false
            $payload.publish_admitted | Should Be $false
            $payload.output_path.StartsWith("examples/sandbox/ap-evidence-imports/") | Should Be $true

            if (Test-Path -LiteralPath $outputAbs) { Remove-Item -LiteralPath $outputAbs -Force }
        }
        finally {
            Remove-ApEvidenceFixture -Context $ctx
        }
    }

    It "blocks traversal, cache, assetdb sqlite, and binary evidence inputs" {
        $ctx = New-ApEvidenceFixture
        try {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $importCmd -ProposalPath $ctx.proposalRel -EvidencePaths "../outside.log" | Out-Null
            $LASTEXITCODE | Should Not Be 0

            $cacheRel = "cache/pester-ap-evidence-$($ctx.suffix).log"
            $cacheAbs = Join-Path $repoRoot $cacheRel
            Set-Content -LiteralPath $cacheAbs -Value "cache" -Encoding UTF8
            & powershell -NoProfile -ExecutionPolicy Bypass -File $importCmd -ProposalPath $ctx.proposalRel -EvidencePaths $cacheRel | Out-Null
            $LASTEXITCODE | Should Not Be 0

            $sqliteRel = "scripts/generated/pester-ap-evidence-$($ctx.suffix)-assetdb.sqlite"
            $sqliteAbs = Join-Path $repoRoot $sqliteRel
            Set-Content -LiteralPath $sqliteAbs -Value "sqlite" -Encoding UTF8
            & powershell -NoProfile -ExecutionPolicy Bypass -File $importCmd -ProposalPath $ctx.proposalRel -EvidencePaths $sqliteRel | Out-Null
            $LASTEXITCODE | Should Not Be 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $importCmd -ProposalPath $ctx.proposalRel -EvidencePaths $ctx.modelRel | Out-Null
            $LASTEXITCODE | Should Not Be 0

            if (Test-Path -LiteralPath $cacheAbs) { Remove-Item -LiteralPath $cacheAbs -Force }
            if (Test-Path -LiteralPath $sqliteAbs) { Remove-Item -LiteralPath $sqliteAbs -Force }
        }
        finally {
            Remove-ApEvidenceFixture -Context $ctx
        }
    }

    It "inspect is read-only and bundle export is sandbox-local JSON-only" {
        $ctx = New-ApEvidenceFixture
        try {
            $importRel = "examples/sandbox/ap-evidence-imports/pester-ap-evidence-inspect-$($ctx.suffix).json"
            $importAbs = Join-Path $repoRoot $importRel
            $bundleRel = "examples/sandbox/ap-evidence-bundles/pester-ap-evidence-$($ctx.suffix)/bundle.manifest.json"
            $bundleAbs = Join-Path $repoRoot $bundleRel
            $bundleDir = Split-Path -Parent $bundleAbs

            & powershell -NoProfile -ExecutionPolicy Bypass -File $importCmd -ProposalPath $ctx.proposalRel -ProjectInventoryPath $ctx.projectRel -AssetCandidateInventoryPath $ctx.assetInventoryRel -EvidencePaths "$($ctx.logRel),$($ctx.snapshotRel)" -OutputPath $importRel | Out-Null
            $LASTEXITCODE | Should Be 0

            $importObj = Get-Content -LiteralPath $importAbs -Raw | ConvertFrom-Json
            $importHashBefore = (Get-FileHash -LiteralPath $importAbs -Algorithm SHA256).Hash
            $logHashBefore = (Get-FileHash -LiteralPath $ctx.logAbs -Algorithm SHA256).Hash

            $listOut = & powershell -NoProfile -ExecutionPolicy Bypass -File $inspectCmd -List
            $LASTEXITCODE | Should Be 0
            ($listOut | ConvertFrom-Json).evidence_import_count | Should BeGreaterThan 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $inspectCmd -EvidenceImportId $importObj.ap_evidence_import_id -ShowWarnings -ShowErrors -ShowObservedMentions | Out-Null
            $LASTEXITCODE | Should Be 0

            (Get-FileHash -LiteralPath $importAbs -Algorithm SHA256).Hash | Should Be $importHashBefore
            (Get-FileHash -LiteralPath $ctx.logAbs -Algorithm SHA256).Hash | Should Be $logHashBefore

            $bundleOut = & powershell -NoProfile -ExecutionPolicy Bypass -File $bundleCmd -EvidenceImportPath $importRel -BundlePath $bundleRel
            $LASTEXITCODE | Should Be 0
            (Test-Path -LiteralPath $bundleAbs) | Should Be $true

            $manifest = $bundleOut | ConvertFrom-Json
            $manifest.bundle_path.StartsWith("examples/sandbox/ap-evidence-bundles/") | Should Be $true
            foreach ($rel in $manifest.copied_artifact_paths) {
                $rel.StartsWith("examples/sandbox/ap-evidence-bundles/") | Should Be $true
                $rel.EndsWith(".json") | Should Be $true
            }
            ((Get-ChildItem -LiteralPath $bundleDir -Recurse -File | Select-Object -ExpandProperty Name) -contains ([System.IO.Path]::GetFileName($ctx.logRel))) | Should Be $false
            ((Get-ChildItem -LiteralPath $bundleDir -Recurse -File | Select-Object -ExpandProperty Name) -contains ([System.IO.Path]::GetFileName($ctx.modelRel))) | Should Be $false

            & powershell -NoProfile -ExecutionPolicy Bypass -File $bundleCmd -EvidenceImportPath $importRel -BundlePath "../outside/bundle.manifest.json" | Out-Null
            $LASTEXITCODE | Should Not Be 0

            if (Test-Path -LiteralPath $bundleDir) { Remove-Item -LiteralPath $bundleDir -Recurse -Force }
            if (Test-Path -LiteralPath $importAbs) { Remove-Item -LiteralPath $importAbs -Force }
        }
        finally {
            Remove-ApEvidenceFixture -Context $ctx
        }
    }

    It "keeps authoritative writer absent and safety boundaries blocked" {
        (Test-Path -LiteralPath $authoritative) | Should Be $false

        $combined = (
            (Get-Content -LiteralPath $importCmd -Raw).ToLowerInvariant() + "`n" +
            (Get-Content -LiteralPath $inspectCmd -Raw).ToLowerInvariant() + "`n" +
            (Get-Content -LiteralPath $bundleCmd -Raw).ToLowerInvariant()
        )

        $combined.Contains("o3de editor") | Should Be $false
        $combined.Contains("asset processor") | Should Be $false
        $combined.Contains("o3de.exe") | Should Be $false
        $combined.Contains("editor.exe") | Should Be $false
        $combined.Contains("invoke-maxineauthoritativeresolverwrite.ps1") | Should Be $false

        $matrix = Get-Content -LiteralPath (Join-Path $repoRoot "examples/capabilities/maxine-capability-matrix.json") -Raw | ConvertFrom-Json
        $caps = $matrix.capabilities
        $caps.ap_evidence_import | Should Be "read_only"
        $caps.ap_evidence_inspect | Should Be "read_only"
        $caps.ap_evidence_bundle_export | Should Be "sandbox_only"
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
