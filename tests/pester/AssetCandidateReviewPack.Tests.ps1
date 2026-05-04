Describe "Asset Candidate Review Pack" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $build = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineAssetCandidateReviewPacketBuild.ps1"
        $inspect = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineAssetCandidateReviewPacketInspect.ps1"
        $bundle = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineAssetCandidateEvidenceBundleExport.ps1"
        $authoritative = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineAuthoritativeResolverWrite.ps1"
    }

    It "builds sandbox-only candidate review packet and preserves candidate evidence fields" {
        $suffix = [Guid]::NewGuid().ToString("N")
        $generatedRel = "scripts/generated/pester-asset-candidate-review-$suffix"
        $generatedAbs = Join-Path $repoRoot $generatedRel
        New-Item -Path $generatedAbs -ItemType Directory -Force | Out-Null

        $modelRel = "$generatedRel/model-$suffix.fbx"
        $textureRel = "$generatedRel/albedo-$suffix.png"
        $metaRel = "$generatedRel/model-$suffix.manifest.json"
        Set-Content -LiteralPath (Join-Path $repoRoot $modelRel) -Value "model-source" -Encoding UTF8
        Set-Content -LiteralPath (Join-Path $repoRoot $textureRel) -Value "texture-source" -Encoding UTF8
        Set-Content -LiteralPath (Join-Path $repoRoot $metaRel) -Value "{`"meta`":true}" -Encoding UTF8

        $modelId = "asset-candidate-model-$suffix"
        $textureId = "asset-candidate-texture-$suffix"
        $metaId = "asset-candidate-meta-$suffix"

        $modelHash = (Get-FileHash -LiteralPath (Join-Path $repoRoot $modelRel) -Algorithm SHA256).Hash.ToLowerInvariant()
        $textureHash = (Get-FileHash -LiteralPath (Join-Path $repoRoot $textureRel) -Algorithm SHA256).Hash.ToLowerInvariant()
        $metaHash = (Get-FileHash -LiteralPath (Join-Path $repoRoot $metaRel) -Algorithm SHA256).Hash.ToLowerInvariant()

        $inventoryRel = "examples/sandbox/asset-candidates/pester-asset-candidate-review-inventory-$suffix.json"
        $inventoryAbs = Join-Path $repoRoot $inventoryRel
        $inventory = [ordered]@{
            schema_version = "1.0.0"
            inventory_id = "asset-inventory-$suffix"
            source_project_inventory_id = "project-inventory-$suffix"
            project_root = "."
            sandbox_root = "examples/sandbox"
            scanned_roots = @($generatedRel)
            generated_candidate_folders = @($generatedRel)
            source_asset_candidates = @(
                [ordered]@{
                    candidate_id = $modelId
                    relative_path = $modelRel
                    extension = ".fbx"
                    category = "character_source"
                    size_bytes = (Get-Item -LiteralPath (Join-Path $repoRoot $modelRel)).Length
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
                    notes = @("pester source candidate")
                },
                [ordered]@{
                    candidate_id = $textureId
                    relative_path = $textureRel
                    extension = ".png"
                    category = "texture_source"
                    size_bytes = (Get-Item -LiteralPath (Join-Path $repoRoot $textureRel)).Length
                    sha256 = $textureHash
                    last_write_time_utc = "2026-05-04T00:00:00Z"
                    evidence_links = [ordered]@{
                        receipt_ids = @("receipt-$suffix")
                        review_packet_ids = @()
                        decision_ids = @()
                        workflow_run_ids = @()
                        evidence_bundle_ids = @()
                    }
                    confidence = "medium"
                    notes = @("pester texture candidate")
                },
                [ordered]@{
                    candidate_id = $metaId
                    relative_path = $metaRel
                    extension = ".json"
                    category = "metadata_source"
                    size_bytes = (Get-Item -LiteralPath (Join-Path $repoRoot $metaRel)).Length
                    sha256 = $metaHash
                    last_write_time_utc = "2026-05-04T00:00:00Z"
                    evidence_links = [ordered]@{
                        receipt_ids = @("receipt-$suffix")
                        review_packet_ids = @()
                        decision_ids = @()
                        workflow_run_ids = @()
                        evidence_bundle_ids = @()
                    }
                    confidence = "medium"
                    notes = @("pester metadata candidate")
                }
            )
            material_texture_candidates = @($textureId)
            metadata_provenance_candidates = @($metaId)
            linked_sandbox_evidence = [ordered]@{
                receipt_ids = @("receipt-$suffix")
                review_packet_ids = @("review-$suffix")
                decision_ids = @("decision-$suffix")
                workflow_run_ids = @("workflow-$suffix")
                evidence_bundle_ids = @("bundle-$suffix")
            }
            warnings = @()
            explicit_non_admissions = @(
                "authoritative_writes",
                "product_resolution",
                "asset_id_claims",
                "spawning",
                "publishing",
                "o3de_editor_execution",
                "asset_processor_execution",
                "o3de_cli_execution",
                "cache_path_write",
                "engine_path_write",
                "production_path_write"
            )
            output_path = $inventoryRel
            created_utc = "2026-05-04T00:00:00Z"
        }
        [System.IO.File]::WriteAllText($inventoryAbs, ($inventory | ConvertTo-Json -Depth 50), [System.Text.UTF8Encoding]::new($false))

        $packetRel = "examples/sandbox/asset-candidate-review-packets/pester-asset-candidate-review-packet-$suffix.json"
        $packetAbs = Join-Path $repoRoot $packetRel
        if (Test-Path -LiteralPath $packetAbs) { Remove-Item -LiteralPath $packetAbs -Force }

        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $build -InventoryPath $inventoryRel -CandidateId $modelId -OutputPath $packetRel -OperatorDecisionState pending_review -RecommendedNextStep bundle_evidence -OperatorId pester-operator
        $LASTEXITCODE | Should Be 0
        (Test-Path -LiteralPath $packetAbs) | Should Be $true

        $summary = $output | ConvertFrom-Json
        $summary.review_packet_count | Should Be 1

        $packet = Get-Content -LiteralPath $packetAbs -Raw | ConvertFrom-Json
        $packet.source_inventory_id | Should Be $inventory.inventory_id
        $packet.candidate_id | Should Be $modelId
        $packet.sha256 | Should Be $modelHash
        $packet.candidate_relative_path | Should Be $modelRel
        $packet.operator_decision_state | Should Be "pending_review"
        $packet.recommended_next_step | Should Be "bundle_evidence"
        $packet.output_path.StartsWith("examples/sandbox/asset-candidate-review-packets/") | Should Be $true

        foreach ($p in @($packetAbs, $inventoryAbs, (Join-Path $repoRoot $modelRel), (Join-Path $repoRoot $textureRel), (Join-Path $repoRoot $metaRel))) {
            if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force }
        }
        if (Test-Path -LiteralPath $generatedAbs) { Remove-Item -LiteralPath $generatedAbs -Recurse -Force }
    }

    It "blocks forbidden decision states, forbidden next steps, traversal, and unknown candidate ids" {
        $suffix = [Guid]::NewGuid().ToString("N")
        $inventoryRel = "examples/sandbox/asset-candidates/pester-asset-candidate-review-guard-$suffix.json"
        $inventoryAbs = Join-Path $repoRoot $inventoryRel
        $inventory = [ordered]@{
            schema_version = "1.0.0"
            inventory_id = "asset-inventory-$suffix"
            sandbox_root = "examples/sandbox"
            source_asset_candidates = @(
                [ordered]@{
                    candidate_id = "candidate-$suffix"
                    relative_path = "scripts/generated/candidate-$suffix.fbx"
                    extension = ".fbx"
                    category = "character_source"
                    size_bytes = 1
                    sha256 = ("a" * 64)
                    last_write_time_utc = "2026-05-04T00:00:00Z"
                    evidence_links = @{}
                    confidence = "high"
                    notes = @()
                }
            )
            material_texture_candidates = @()
            metadata_provenance_candidates = @()
            linked_sandbox_evidence = @{}
            warnings = @()
            project_root = "."
        }
        [System.IO.File]::WriteAllText($inventoryAbs, ($inventory | ConvertTo-Json -Depth 20), [System.Text.UTF8Encoding]::new($false))

        & powershell -NoProfile -ExecutionPolicy Bypass -File $build -InventoryPath $inventoryRel -CandidateId "candidate-$suffix" -OperatorDecisionState approve_product_resolution | Out-Null
        $LASTEXITCODE | Should Not Be 0

        & powershell -NoProfile -ExecutionPolicy Bypass -File $build -InventoryPath $inventoryRel -CandidateId "candidate-$suffix" -RecommendedNextStep run_asset_processor | Out-Null
        $LASTEXITCODE | Should Not Be 0

        & powershell -NoProfile -ExecutionPolicy Bypass -File $build -InventoryPath $inventoryRel -CandidateId "unknown-candidate" | Out-Null
        $LASTEXITCODE | Should Not Be 0

        & powershell -NoProfile -ExecutionPolicy Bypass -File $build -InventoryPath $inventoryRel -CandidateId "candidate-$suffix" -OutputPath "../outside/review.json" | Out-Null
        $LASTEXITCODE | Should Not Be 0

        if (Test-Path -LiteralPath $inventoryAbs) { Remove-Item -LiteralPath $inventoryAbs -Force }
    }

    It "review inspect is read-only and candidate evidence bundle export stays sandbox-local JSON-only without mutating source evidence" {
        $suffix = [Guid]::NewGuid().ToString("N")
        $generatedRel = "scripts/generated/pester-asset-candidate-evidence-$suffix"
        $generatedAbs = Join-Path $repoRoot $generatedRel
        New-Item -Path $generatedAbs -ItemType Directory -Force | Out-Null
        $modelRel = "$generatedRel/model-$suffix.fbx"
        Set-Content -LiteralPath (Join-Path $repoRoot $modelRel) -Value "model-source" -Encoding UTF8
        $modelHash = (Get-FileHash -LiteralPath (Join-Path $repoRoot $modelRel) -Algorithm SHA256).Hash.ToLowerInvariant()

        $inventoryRel = "examples/sandbox/asset-candidates/pester-asset-candidate-evidence-inventory-$suffix.json"
        $inventoryAbs = Join-Path $repoRoot $inventoryRel
        $inventory = [ordered]@{
            schema_version = "1.0.0"
            inventory_id = "asset-inventory-$suffix"
            source_project_inventory_id = "project-inventory-$suffix"
            project_root = "."
            sandbox_root = "examples/sandbox"
            scanned_roots = @($generatedRel)
            generated_candidate_folders = @($generatedRel)
            source_asset_candidates = @(
                [ordered]@{
                    candidate_id = "candidate-$suffix"
                    relative_path = $modelRel
                    extension = ".fbx"
                    category = "character_source"
                    size_bytes = (Get-Item -LiteralPath (Join-Path $repoRoot $modelRel)).Length
                    sha256 = $modelHash
                    last_write_time_utc = "2026-05-04T00:00:00Z"
                    evidence_links = [ordered]@{
                        receipt_ids = @("receipt-$suffix")
                        review_packet_ids = @()
                        decision_ids = @()
                        workflow_run_ids = @("workflow-$suffix")
                        evidence_bundle_ids = @("bundle-$suffix")
                    }
                    confidence = "high"
                    notes = @("candidate note")
                }
            )
            material_texture_candidates = @()
            metadata_provenance_candidates = @()
            linked_sandbox_evidence = [ordered]@{
                receipt_ids = @("receipt-$suffix")
                review_packet_ids = @("review-$suffix")
                decision_ids = @("decision-$suffix")
                workflow_run_ids = @("workflow-$suffix")
                evidence_bundle_ids = @("bundle-$suffix")
            }
            warnings = @()
            explicit_non_admissions = @("authoritative_writes")
            output_path = $inventoryRel
            created_utc = "2026-05-04T00:00:00Z"
        }
        [System.IO.File]::WriteAllText($inventoryAbs, ($inventory | ConvertTo-Json -Depth 30), [System.Text.UTF8Encoding]::new($false))

        $packetRel = "examples/sandbox/asset-candidate-review-packets/pester-asset-candidate-evidence-packet-$suffix.json"
        $packetAbs = Join-Path $repoRoot $packetRel
        $bundleRel = "examples/sandbox/asset-candidate-evidence-bundles/pester-asset-candidate-evidence-bundle-$suffix/bundle.manifest.json"
        $bundleAbs = Join-Path $repoRoot $bundleRel
        $bundleDir = Split-Path -Parent $bundleAbs

        & powershell -NoProfile -ExecutionPolicy Bypass -File $build -InventoryPath $inventoryRel -CandidateId "candidate-$suffix" -OutputPath $packetRel -RecommendedNextStep bundle_evidence | Out-Null
        $LASTEXITCODE | Should Be 0

        $packet = Get-Content -LiteralPath $packetAbs -Raw | ConvertFrom-Json
        $packetHashBefore = (Get-FileHash -LiteralPath $packetAbs -Algorithm SHA256).Hash
        $inventoryHashBefore = (Get-FileHash -LiteralPath $inventoryAbs -Algorithm SHA256).Hash

        $listOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $inspect -List
        $LASTEXITCODE | Should Be 0
        ($listOutput | ConvertFrom-Json).review_packet_count | Should BeGreaterThan 0

        $inspectOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $inspect -ReviewPacketId $packet.review_packet_id -ShowEvidenceLinks
        $LASTEXITCODE | Should Be 0
        ($inspectOutput | ConvertFrom-Json).review_packet_id | Should Be $packet.review_packet_id

        $packetHashAfterInspect = (Get-FileHash -LiteralPath $packetAbs -Algorithm SHA256).Hash
        $inventoryHashAfterInspect = (Get-FileHash -LiteralPath $inventoryAbs -Algorithm SHA256).Hash
        $packetHashAfterInspect | Should Be $packetHashBefore
        $inventoryHashAfterInspect | Should Be $inventoryHashBefore

        $bundleOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $bundle -ReviewPacketPath $packetRel -BundlePath $bundleRel
        $LASTEXITCODE | Should Be 0
        (Test-Path -LiteralPath $bundleAbs) | Should Be $true

        $manifest = $bundleOutput | ConvertFrom-Json
        $manifest.bundle_path.StartsWith("examples/sandbox/asset-candidate-evidence-bundles/") | Should Be $true
        foreach ($rel in $manifest.copied_artifact_paths) {
            $rel.StartsWith("examples/sandbox/asset-candidate-evidence-bundles/") | Should Be $true
            $rel.EndsWith(".json") | Should Be $true
            (Test-Path -LiteralPath (Join-Path $repoRoot $rel)) | Should Be $true
        }

        ((Get-ChildItem -LiteralPath $bundleDir -Recurse -File | Select-Object -ExpandProperty Name) -contains ([System.IO.Path]::GetFileName($modelRel))) | Should Be $false

        $packetHashAfterBundle = (Get-FileHash -LiteralPath $packetAbs -Algorithm SHA256).Hash
        $inventoryHashAfterBundle = (Get-FileHash -LiteralPath $inventoryAbs -Algorithm SHA256).Hash
        $packetHashAfterBundle | Should Be $packetHashBefore
        $inventoryHashAfterBundle | Should Be $inventoryHashBefore

        & powershell -NoProfile -ExecutionPolicy Bypass -File $bundle -ReviewPacketPath $packetRel -BundlePath "../outside/bundle.manifest.json" | Out-Null
        $LASTEXITCODE | Should Not Be 0

        foreach ($p in @($packetAbs, $inventoryAbs, (Join-Path $repoRoot $modelRel))) {
            if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force }
        }
        if (Test-Path -LiteralPath $bundleDir) { Remove-Item -LiteralPath $bundleDir -Recurse -Force }
        if (Test-Path -LiteralPath $generatedAbs) { Remove-Item -LiteralPath $generatedAbs -Recurse -Force }
    }

    It "keeps authoritative writer absent and blocks O3DE/AP/Editor execution hooks" {
        (Test-Path -LiteralPath $authoritative) | Should Be $false

        $combined = ((Get-Content -LiteralPath $build -Raw).ToLowerInvariant()) + "`n" + ((Get-Content -LiteralPath $inspect -Raw).ToLowerInvariant()) + "`n" + ((Get-Content -LiteralPath $bundle -Raw).ToLowerInvariant())
        $combined.Contains("o3de editor") | Should Be $false
        $combined.Contains("asset processor") | Should Be $false
        $combined.Contains("o3de.exe") | Should Be $false
        $combined.Contains("editor.exe") | Should Be $false
        $combined.Contains("invoke-maxineauthoritativeresolverwrite.ps1") | Should Be $false
    }

    It "capability matrix preserves asset candidate review pack boundaries" {
        $matrixPath = Join-Path $repoRoot "examples/capabilities/maxine-capability-matrix.json"
        (Test-Path -LiteralPath $matrixPath) | Should Be $true
        $matrix = Get-Content -LiteralPath $matrixPath -Raw | ConvertFrom-Json
        $caps = $matrix.capabilities

        $caps.asset_candidate_review_packet_build | Should Be "sandbox_only"
        $caps.asset_candidate_review_packet_inspect | Should Be "read_only"
        $caps.asset_candidate_evidence_bundle_export | Should Be "sandbox_only"
        $caps.authoritative_resolver_write | Should Be "forbidden"
        $caps.product_resolution | Should Be "blocked"
        $caps.asset_id_claims | Should Be "blocked"
        $caps.spawning | Should Be "blocked"
        $caps.publishing | Should Be "blocked"
    }
}
