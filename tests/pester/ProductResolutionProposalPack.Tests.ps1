Describe "Product Resolution Proposal Pack" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $build = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineProductResolutionProposalBuild.ps1"
        $inspect = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineProductResolutionProposalInspect.ps1"
        $bundle = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineProductResolutionProposalBundleExport.ps1"
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

        function New-ProposalPackFixture {
            $suffix = [Guid]::NewGuid().ToString("N")
            $generatedRel = "scripts/generated/pester-product-resolution-$suffix"
            $generatedAbs = Join-Path $repoRoot $generatedRel
            New-Item -Path $generatedAbs -ItemType Directory -Force | Out-Null

            $modelRel = "$generatedRel/character-$suffix.fbx"
            $modelAbs = Join-Path $repoRoot $modelRel
            Set-Content -LiteralPath $modelAbs -Value "proposal-source" -Encoding UTF8
            $modelHash = (Get-FileHash -LiteralPath $modelAbs -Algorithm SHA256).Hash.ToLowerInvariant()

            $projectId = "project-inventory-$suffix"
            $assetInventoryId = "asset-inventory-$suffix"
            $reviewPacketId = "asset-candidate-review-$suffix"
            $candidateId = "asset-candidate-$suffix"

            $projectRel = "examples/sandbox/project-inventory/pester-product-proposal-project-$suffix.json"
            $projectAbs = Join-Path $repoRoot $projectRel
            $projectPayload = [ordered]@{
                schema_version = "1.0.0"
                inventory_id = $projectId
                project_root = "."
                sandbox_root = "examples/sandbox"
                project_json_candidates = @("project.json")
                known_asset_folders = @($generatedRel)
                generated_asset_candidate_folders = @($generatedRel)
                sandbox_evidence_folders = @(
                    "examples/sandbox/receipts",
                    "examples/sandbox/review-packets",
                    "examples/sandbox/review-decisions",
                    "examples/sandbox/workflow-runs"
                )
                o3de_project_path_metadata = [ordered]@{ project_name_hint = "MaxineShow" }
                configured_non_executed_path_hints = [ordered]@{
                    o3de_editor_path_hint = "C:/O3DE/Editor.exe"
                    asset_processor_path_hint = "C:/O3DE/AssetProcessorBatch.exe"
                }
                output_path = $projectRel
                created_utc = "2026-05-04T00:00:00Z"
            }
            Write-JsonUtf8NoBom -Path $projectAbs -Object $projectPayload

            $assetInventoryRel = "examples/sandbox/asset-candidates/pester-product-proposal-asset-inventory-$suffix.json"
            $assetInventoryAbs = Join-Path $repoRoot $assetInventoryRel
            $assetInventoryPayload = [ordered]@{
                schema_version = "1.0.0"
                inventory_id = $assetInventoryId
                source_project_inventory_id = $projectId
                project_root = "."
                sandbox_root = "examples/sandbox"
                scanned_roots = @($generatedRel)
                generated_candidate_folders = @($generatedRel)
                source_asset_candidates = @(
                    [ordered]@{
                        candidate_id = $candidateId
                        relative_path = $modelRel
                        extension = ".fbx"
                        category = "character_source"
                        size_bytes = (Get-Item -LiteralPath $modelAbs).Length
                        sha256 = $modelHash
                        last_write_time_utc = "2026-05-04T00:00:00Z"
                        evidence_links = [ordered]@{
                            receipt_ids = @("receipt-$suffix")
                            review_packet_ids = @()
                            decision_ids = @()
                            workflow_run_ids = @()
                            evidence_bundle_ids = @()
                        }
                        confidence = "high"
                        notes = @("fixture candidate")
                    }
                )
                material_texture_candidates = @()
                metadata_provenance_candidates = @()
                linked_sandbox_evidence = [ordered]@{
                    receipt_ids = @("receipt-$suffix")
                    review_packet_ids = @($reviewPacketId)
                    decision_ids = @()
                    workflow_run_ids = @("workflow-$suffix")
                    evidence_bundle_ids = @()
                }
                warnings = @()
                explicit_non_admissions = @(
                    "authoritative_writes",
                    "product_resolution",
                    "asset_id_claims",
                    "source_uuid_claims",
                    "spawning",
                    "publishing",
                    "o3de_editor_execution",
                    "asset_processor_execution",
                    "cache_read"
                )
                output_path = $assetInventoryRel
                created_utc = "2026-05-04T00:00:00Z"
            }
            Write-JsonUtf8NoBom -Path $assetInventoryAbs -Object $assetInventoryPayload

            $reviewRel = "examples/sandbox/asset-candidate-review-packets/pester-product-proposal-review-$suffix.json"
            $reviewAbs = Join-Path $repoRoot $reviewRel
            $reviewPayload = [ordered]@{
                schema_version = "1.0.0"
                review_packet_id = $reviewPacketId
                source_inventory_id = $assetInventoryId
                candidate_id = $candidateId
                project_root = "."
                sandbox_root = "examples/sandbox"
                candidate_relative_path = $modelRel
                candidate_extension = ".fbx"
                candidate_category = "character_source"
                size_bytes = (Get-Item -LiteralPath $modelAbs).Length
                sha256 = $modelHash
                last_write_time_utc = "2026-05-04T00:00:00Z"
                confidence = "high"
                evidence_links = [ordered]@{
                    receipt_ids = @("receipt-$suffix")
                    review_packet_ids = @()
                    decision_ids = @()
                    workflow_run_ids = @()
                    evidence_bundle_ids = @()
                }
                provenance_links = @()
                material_texture_links = @()
                warnings = @()
                safety_summary = "sandbox-only review packet"
                recommended_next_step = "bundle_evidence"
                operator_decision_state = "pending_review"
                explicit_non_admissions = @(
                    "authoritative_writes",
                    "product_resolution",
                    "asset_id_claims",
                    "source_uuid_claims",
                    "spawning",
                    "publishing",
                    "o3de_editor_execution",
                    "asset_processor_execution",
                    "cache_read"
                )
                output_path = $reviewRel
                created_utc = "2026-05-04T00:00:00Z"
            }
            Write-JsonUtf8NoBom -Path $reviewAbs -Object $reviewPayload

            return [ordered]@{
                suffix = $suffix
                generatedAbs = $generatedAbs
                modelAbs = $modelAbs
                modelRel = $modelRel
                modelHash = $modelHash
                projectId = $projectId
                projectRel = $projectRel
                projectAbs = $projectAbs
                assetInventoryId = $assetInventoryId
                assetInventoryRel = $assetInventoryRel
                assetInventoryAbs = $assetInventoryAbs
                reviewPacketId = $reviewPacketId
                reviewRel = $reviewRel
                reviewAbs = $reviewAbs
                candidateId = $candidateId
            }
        }

        function Remove-ProposalPackFixture {
            param([Parameter(Mandatory = $true)]$Context)

            foreach ($path in @(
                $Context.reviewAbs,
                $Context.assetInventoryAbs,
                $Context.projectAbs,
                $Context.modelAbs
            )) {
                if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
            }
            if (Test-Path -LiteralPath $Context.generatedAbs) {
                Remove-Item -LiteralPath $Context.generatedAbs -Recurse -Force
            }
        }
    }

    It "builds proposal-only product resolution packets under sandbox proposals" {
        $ctx = New-ProposalPackFixture
        try {
            $proposalRel = "examples/sandbox/product-resolution-proposals/pester-product-proposal-$($ctx.suffix).json"
            $proposalAbs = Join-Path $repoRoot $proposalRel
            if (Test-Path -LiteralPath $proposalAbs) { Remove-Item -LiteralPath $proposalAbs -Force }

            $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $build -ReviewPacketPath $ctx.reviewRel -AssetCandidateInventoryPath $ctx.assetInventoryRel -ProjectInventoryPath $ctx.projectRel -OutputPath $proposalRel -OperatorId pester-operator
            $LASTEXITCODE | Should Be 0
            (Test-Path -LiteralPath $proposalAbs) | Should Be $true

            $proposal = Get-Content -LiteralPath $proposalAbs -Raw | ConvertFrom-Json
            $proposal.proposal_only | Should Be $true
            $proposal.product_ids_claimed | Should Be $false
            $proposal.asset_ids_claimed | Should Be $false
            $proposal.source_uuids_claimed | Should Be $false
            $proposal.asset_processor_execution_admitted | Should Be $false
            $proposal.o3de_execution_admitted | Should Be $false
            $proposal.cache_access_admitted | Should Be $false
            $proposal.spawn_admitted | Should Be $false
            $proposal.publish_admitted | Should Be $false
            $proposal.output_path.StartsWith("examples/sandbox/product-resolution-proposals/") | Should Be $true
            $proposal.candidate_sha256 | Should Be $ctx.modelHash
            ($proposal.expected_product_classes -contains "model_product_candidate") | Should Be $true
            ($proposal.expected_product_classes -contains "actor_product_candidate") | Should Be $true
            ($proposal.proposal_status -in @("proposal_only", "blocked_missing_evidence", "ready_for_read_only_ap_evidence_import", "rejected")) | Should Be $true

            if (Test-Path -LiteralPath $proposalAbs) { Remove-Item -LiteralPath $proposalAbs -Force }
        }
        finally {
            Remove-ProposalPackFixture -Context $ctx
        }
    }

    It "blocks outside-sandbox review paths, traversal outputs, and forbidden proposal statuses" {
        $ctx = New-ProposalPackFixture
        try {
            $outsideReview = Join-Path $env:TEMP "outside-review-$($ctx.suffix).json"
            $outsidePayload = [ordered]@{
                review_packet_id = "outside"
                source_inventory_id = $ctx.assetInventoryId
                candidate_id = $ctx.candidateId
                project_root = "."
                sandbox_root = "examples/sandbox"
                candidate_relative_path = $ctx.modelRel
                candidate_extension = ".fbx"
                candidate_category = "character_source"
                sha256 = $ctx.modelHash
            }
            Write-JsonUtf8NoBom -Path $outsideReview -Object $outsidePayload -Depth 20

            & powershell -NoProfile -ExecutionPolicy Bypass -File $build -ReviewPacketPath $outsideReview -AssetCandidateInventoryPath $ctx.assetInventoryRel -ProjectInventoryPath $ctx.projectRel | Out-Null
            $LASTEXITCODE | Should Not Be 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $build -ReviewPacketPath $ctx.reviewRel -AssetCandidateInventoryPath $ctx.assetInventoryRel -ProjectInventoryPath $ctx.projectRel -OutputPath "../outside/proposal.json" | Out-Null
            $LASTEXITCODE | Should Not Be 0

            & powershell -NoProfile -ExecutionPolicy Bypass -File $build -ReviewPacketPath $ctx.reviewRel -ProposalStatus "resolved" | Out-Null
            $LASTEXITCODE | Should Not Be 0

            if (Test-Path -LiteralPath $outsideReview) { Remove-Item -LiteralPath $outsideReview -Force }
        }
        finally {
            Remove-ProposalPackFixture -Context $ctx
        }
    }

    It "proposal inspect is read-only by list, id, and path" {
        $ctx = New-ProposalPackFixture
        try {
            $proposalRel = "examples/sandbox/product-resolution-proposals/pester-product-proposal-inspect-$($ctx.suffix).json"
            $proposalAbs = Join-Path $repoRoot $proposalRel

            & powershell -NoProfile -ExecutionPolicy Bypass -File $build -ReviewPacketPath $ctx.reviewRel -AssetCandidateInventoryPath $ctx.assetInventoryRel -ProjectInventoryPath $ctx.projectRel -OutputPath $proposalRel | Out-Null
            $LASTEXITCODE | Should Be 0

            $proposal = Get-Content -LiteralPath $proposalAbs -Raw | ConvertFrom-Json
            $reviewHashBefore = (Get-FileHash -LiteralPath $ctx.reviewAbs -Algorithm SHA256).Hash
            $proposalHashBefore = (Get-FileHash -LiteralPath $proposalAbs -Algorithm SHA256).Hash

            $listOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $inspect -List
            $LASTEXITCODE | Should Be 0
            ($listOutput | ConvertFrom-Json).proposal_count | Should BeGreaterThan 0

            $byIdOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $inspect -ProposalId $proposal.proposal_id
            $LASTEXITCODE | Should Be 0
            ($byIdOutput | ConvertFrom-Json).proposal_id | Should Be $proposal.proposal_id

            $byPathOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $inspect -ProposalPath $proposalRel -ShowRequirements -ShowBlockingReasons
            $LASTEXITCODE | Should Be 0
            ($byPathOutput | ConvertFrom-Json).proposal_id | Should Be $proposal.proposal_id

            (Get-FileHash -LiteralPath $ctx.reviewAbs -Algorithm SHA256).Hash | Should Be $reviewHashBefore
            (Get-FileHash -LiteralPath $proposalAbs -Algorithm SHA256).Hash | Should Be $proposalHashBefore

            if (Test-Path -LiteralPath $proposalAbs) { Remove-Item -LiteralPath $proposalAbs -Force }
        }
        finally {
            Remove-ProposalPackFixture -Context $ctx
        }
    }

    It "proposal bundle export is sandbox-local JSON-only and preserves source evidence" {
        $ctx = New-ProposalPackFixture
        try {
            $proposalRel = "examples/sandbox/product-resolution-proposals/pester-product-proposal-bundle-$($ctx.suffix).json"
            $proposalAbs = Join-Path $repoRoot $proposalRel
            $bundleRel = "examples/sandbox/product-resolution-proposal-bundles/pester-product-proposal-bundle-$($ctx.suffix)/bundle.manifest.json"
            $bundleAbs = Join-Path $repoRoot $bundleRel
            $bundleDir = Split-Path -Parent $bundleAbs

            & powershell -NoProfile -ExecutionPolicy Bypass -File $build -ReviewPacketPath $ctx.reviewRel -AssetCandidateInventoryPath $ctx.assetInventoryRel -ProjectInventoryPath $ctx.projectRel -OutputPath $proposalRel | Out-Null
            $LASTEXITCODE | Should Be 0

            $reviewHashBefore = (Get-FileHash -LiteralPath $ctx.reviewAbs -Algorithm SHA256).Hash
            $proposalHashBefore = (Get-FileHash -LiteralPath $proposalAbs -Algorithm SHA256).Hash
            $assetInventoryHashBefore = (Get-FileHash -LiteralPath $ctx.assetInventoryAbs -Algorithm SHA256).Hash
            $projectHashBefore = (Get-FileHash -LiteralPath $ctx.projectAbs -Algorithm SHA256).Hash

            $bundleOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $bundle -ProposalPath $proposalRel -BundlePath $bundleRel
            $LASTEXITCODE | Should Be 0
            (Test-Path -LiteralPath $bundleAbs) | Should Be $true

            $manifest = $bundleOutput | ConvertFrom-Json
            $manifest.bundle_path.StartsWith("examples/sandbox/product-resolution-proposal-bundles/") | Should Be $true
            foreach ($rel in $manifest.copied_artifact_paths) {
                $rel.StartsWith("examples/sandbox/product-resolution-proposal-bundles/") | Should Be $true
                $rel.EndsWith(".json") | Should Be $true
                (Test-Path -LiteralPath (Join-Path $repoRoot $rel)) | Should Be $true
            }
            ((Get-ChildItem -LiteralPath $bundleDir -Recurse -File | Select-Object -ExpandProperty Name) -contains ([System.IO.Path]::GetFileName($ctx.modelRel))) | Should Be $false

            (Get-FileHash -LiteralPath $ctx.reviewAbs -Algorithm SHA256).Hash | Should Be $reviewHashBefore
            (Get-FileHash -LiteralPath $proposalAbs -Algorithm SHA256).Hash | Should Be $proposalHashBefore
            (Get-FileHash -LiteralPath $ctx.assetInventoryAbs -Algorithm SHA256).Hash | Should Be $assetInventoryHashBefore
            (Get-FileHash -LiteralPath $ctx.projectAbs -Algorithm SHA256).Hash | Should Be $projectHashBefore

            & powershell -NoProfile -ExecutionPolicy Bypass -File $bundle -ProposalPath $proposalRel -BundlePath "../outside/bundle.manifest.json" | Out-Null
            $LASTEXITCODE | Should Not Be 0

            if (Test-Path -LiteralPath $bundleDir) { Remove-Item -LiteralPath $bundleDir -Recurse -Force }
            if (Test-Path -LiteralPath $proposalAbs) { Remove-Item -LiteralPath $proposalAbs -Force }
        }
        finally {
            Remove-ProposalPackFixture -Context $ctx
        }
    }

    It "keeps authoritative writer absent and blocks O3DE/AP/Editor execution hooks and forbidden admissions" {
        (Test-Path -LiteralPath $authoritative) | Should Be $false

        $combined = (
            (Get-Content -LiteralPath $build -Raw).ToLowerInvariant() + "`n" +
            (Get-Content -LiteralPath $inspect -Raw).ToLowerInvariant() + "`n" +
            (Get-Content -LiteralPath $bundle -Raw).ToLowerInvariant()
        )
        $combined.Contains("o3de editor") | Should Be $false
        $combined.Contains("asset processor") | Should Be $false
        $combined.Contains("o3de.exe") | Should Be $false
        $combined.Contains("editor.exe") | Should Be $false
        $combined.Contains("invoke-maxineauthoritativeresolverwrite.ps1") | Should Be $false

        $matrixPath = Join-Path $repoRoot "examples/capabilities/maxine-capability-matrix.json"
        $caps = (Get-Content -LiteralPath $matrixPath -Raw | ConvertFrom-Json).capabilities
        $caps.product_resolution_proposal_build | Should Be "sandbox_only"
        $caps.product_resolution_proposal_inspect | Should Be "read_only"
        $caps.product_resolution_proposal_bundle_export | Should Be "sandbox_only"
        $caps.product_resolution | Should Be "blocked"
        $caps.asset_id_claims | Should Be "blocked"
        $caps.source_uuid_claims | Should Be "blocked"
        $caps.cache_read | Should Be "blocked"
        $caps.spawning | Should Be "blocked"
        $caps.publishing | Should Be "blocked"
    }
}
