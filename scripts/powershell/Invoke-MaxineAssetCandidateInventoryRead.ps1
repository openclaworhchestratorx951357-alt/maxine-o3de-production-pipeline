[CmdletBinding()]
param(
    [string]$ProjectInventoryPath,
    [string]$InventoryRoot = "examples/sandbox/asset-candidates",
    [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))
$projectInventoryRootAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox\project-inventory"))
$assetCandidateRootAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox\asset-candidates"))

function Test-IsPathWithin {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CandidatePath,
        [Parameter(Mandatory = $true)]
        [string]$ParentPath
    )

    $candidateAbs = [System.IO.Path]::GetFullPath($CandidatePath)
    $parentAbs = [System.IO.Path]::GetFullPath($ParentPath)

    if ($candidateAbs.Equals($parentAbs, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }

    $prefix = $parentAbs.TrimEnd("\") + "\"
    return $candidateAbs.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-RepoRelativePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AbsolutePath
    )

    $abs = [System.IO.Path]::GetFullPath($AbsolutePath)
    if (-not (Test-IsPathWithin -CandidatePath $abs -ParentPath $repoRoot)) {
        return $abs
    }

    return $abs.Substring($repoRoot.Length).TrimStart("\").Replace("\", "/")
}

function Get-SafeRelativePathAbs {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath,
        [Parameter(Mandatory = $true)]
        [string]$AllowedRootAbs,
        [string]$Label = "path"
    )

    if ([string]::IsNullOrWhiteSpace($RelativePath)) {
        throw "$Label is empty."
    }

    if ([System.IO.Path]::IsPathRooted($RelativePath)) {
        throw "$Label must be relative."
    }

    if ($RelativePath.StartsWith("\") -or $RelativePath.StartsWith("/")) {
        throw "$Label cannot start with slash or backslash."
    }

    $normalized = $RelativePath.Replace("\", "/")
    if (($normalized -split "/") -contains "..") {
        throw "$Label contains parent traversal and is blocked."
    }

    $candidateAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $RelativePath))
    if (-not (Test-IsPathWithin -CandidatePath $candidateAbs -ParentPath $AllowedRootAbs)) {
        throw "$Label escapes the approved sandbox root."
    }

    return $candidateAbs
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath
    )

    $directory = Split-Path -Parent $OutputPath
    if ($directory -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -Path $directory -ItemType Directory -Force | Out-Null
    }

    $json = $InputObject | ConvertTo-Json -Depth 100
    [System.IO.File]::WriteAllText($OutputPath, $json, [System.Text.UTF8Encoding]::new($false))
}

function Test-IsCachePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    $segments = [System.IO.Path]::GetFullPath($PathValue).Replace("/", "\").Split("\") | Where-Object { $_ -ne "" }
    foreach ($segment in $segments) {
        if ($segment.Equals("cache", [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function New-HashSet {
    return ,([System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase))
}

function Get-CandidateClassification {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )

    $lower = $RelativePath.ToLowerInvariant()
    if ($lower.EndsWith(".fbx")) {
        return [ordered]@{ category = "character_source"; confidence = "high"; bucket = "source" }
    }
    if ($lower.EndsWith(".glb") -or $lower.EndsWith(".gltf") -or $lower.EndsWith(".obj")) {
        return [ordered]@{ category = "mesh_source"; confidence = "high"; bucket = "source" }
    }
    if ($lower.EndsWith(".blend")) {
        return [ordered]@{ category = "scene_source"; confidence = "medium"; bucket = "source" }
    }
    if ($lower.EndsWith(".material") -or $lower.EndsWith(".azmaterial")) {
        return [ordered]@{ category = "material_source"; confidence = "medium"; bucket = "material_texture" }
    }
    if (
        $lower.EndsWith(".png") -or $lower.EndsWith(".jpg") -or $lower.EndsWith(".jpeg") -or
        $lower.EndsWith(".tif") -or $lower.EndsWith(".tiff") -or $lower.EndsWith(".exr")
    ) {
        return [ordered]@{ category = "texture_source"; confidence = "medium"; bucket = "material_texture" }
    }
    if (
        $lower.EndsWith(".forge.json") -or $lower.EndsWith(".manifest.json") -or
        $lower.EndsWith(".meta") -or $lower.EndsWith(".json")
    ) {
        return [ordered]@{ category = "metadata_source"; confidence = "medium"; bucket = "metadata" }
    }

    return [ordered]@{ category = "unknown_source"; confidence = "low"; bucket = "source" }
}

function New-EvidenceState {
    return [ordered]@{
        receipt_ids = New-HashSet
        review_packet_ids = New-HashSet
        decision_ids = New-HashSet
        workflow_run_ids = New-HashSet
        evidence_bundle_ids = New-HashSet
        records = @()
    }
}

function Add-EvidenceId {
    param(
        [Parameter(Mandatory = $true)]
        [object]$State,
        [Parameter(Mandatory = $true)]
        [string]$Kind,
        [Parameter(Mandatory = $false)]
        [AllowEmptyString()]
        [string]$IdValue,
        [Parameter(Mandatory = $false)]
        [AllowEmptyString()]
        [string]$RawText
    )

    if ([string]::IsNullOrWhiteSpace($IdValue)) {
        return
    }

    switch ($Kind) {
        "receipt" { $State.receipt_ids.Add($IdValue) | Out-Null }
        "review_packet" { $State.review_packet_ids.Add($IdValue) | Out-Null }
        "decision" { $State.decision_ids.Add($IdValue) | Out-Null }
        "workflow_run" { $State.workflow_run_ids.Add($IdValue) | Out-Null }
        "evidence_bundle" { $State.evidence_bundle_ids.Add($IdValue) | Out-Null }
    }

    $rawLower = ([string]$RawText).ToLowerInvariant()
    $State.records += [ordered]@{
        kind = $Kind
        id = $IdValue
        raw = $rawLower
    }
}

function Collect-SandboxEvidence {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRootAbs
    )

    $state = New-EvidenceState
    $locations = @(
        [ordered]@{ kind = "receipt"; path = "examples/sandbox/receipts" },
        [ordered]@{ kind = "review_packet"; path = "examples/sandbox/review-packets" },
        [ordered]@{ kind = "decision"; path = "examples/sandbox/review-decisions" },
        [ordered]@{ kind = "workflow_run"; path = "examples/sandbox/workflow-runs" },
        [ordered]@{ kind = "evidence_bundle"; path = "examples/sandbox/evidence-bundles" }
    )

    foreach ($location in $locations) {
        $rootAbs = [System.IO.Path]::GetFullPath((Join-Path $RepoRootAbs $location.path.Replace("/", "\")))
        if (-not (Test-Path -LiteralPath $rootAbs -PathType Container)) {
            continue
        }

        foreach ($file in Get-ChildItem -LiteralPath $rootAbs -File -Filter *.json -ErrorAction SilentlyContinue) {
            $raw = ""
            $parsed = $null
            try {
                $raw = Get-Content -LiteralPath $file.FullName -Raw
                $parsed = $raw | ConvertFrom-Json
            } catch {
                continue
            }

            $idValue = $null
            switch ($location.kind) {
                "receipt" {
                    $prop = $parsed.PSObject.Properties["receipt_id"]
                    if ($null -ne $prop) { $idValue = [string]$prop.Value }
                }
                "review_packet" {
                    $prop = $parsed.PSObject.Properties["review_packet_id"]
                    if ($null -ne $prop) { $idValue = [string]$prop.Value }
                }
                "decision" {
                    $prop = $parsed.PSObject.Properties["decision_id"]
                    if ($null -ne $prop) { $idValue = [string]$prop.Value }
                }
                "workflow_run" {
                    $prop = $parsed.PSObject.Properties["workflow_run_id"]
                    if ($null -ne $prop) { $idValue = [string]$prop.Value }
                }
                "evidence_bundle" {
                    $prop = $parsed.PSObject.Properties["bundle_id"]
                    if ($null -ne $prop) { $idValue = [string]$prop.Value }
                }
            }

            Add-EvidenceId -State $state -Kind $location.kind -IdValue $idValue -RawText $raw
        }
    }

    return $state
}

function New-CandidateEvidenceLinks {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath,
        [Parameter(Mandatory = $true)]
        [object]$EvidenceState
    )

    $receipts = New-HashSet
    $reviewPackets = New-HashSet
    $decisions = New-HashSet
    $workflowRuns = New-HashSet
    $evidenceBundles = New-HashSet

    $needlePath = $RelativePath.ToLowerInvariant()
    $needleName = [System.IO.Path]::GetFileName($needlePath)

    foreach ($record in $EvidenceState.records) {
        $matched = $record.raw.Contains($needlePath)
        if (-not $matched -and -not [string]::IsNullOrWhiteSpace($needleName)) {
            $matched = $record.raw.Contains($needleName)
        }
        if (-not $matched) {
            continue
        }

        switch ([string]$record.kind) {
            "receipt" { $receipts.Add([string]$record.id) | Out-Null }
            "review_packet" { $reviewPackets.Add([string]$record.id) | Out-Null }
            "decision" { $decisions.Add([string]$record.id) | Out-Null }
            "workflow_run" { $workflowRuns.Add([string]$record.id) | Out-Null }
            "evidence_bundle" { $evidenceBundles.Add([string]$record.id) | Out-Null }
        }
    }

    return [ordered]@{
        receipt_ids = @($receipts | Sort-Object)
        review_packet_ids = @($reviewPackets | Sort-Object)
        decision_ids = @($decisions | Sort-Object)
        workflow_run_ids = @($workflowRuns | Sort-Object)
        evidence_bundle_ids = @($evidenceBundles | Sort-Object)
    }
}

function Convert-HashSetToSortedArray {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [System.Collections.Generic.HashSet[string]]$Set
    )
    return @($Set | Sort-Object)
}

if (-not (Test-Path -LiteralPath $assetCandidateRootAbs -PathType Container)) {
    New-Item -Path $assetCandidateRootAbs -ItemType Directory -Force | Out-Null
}

$projectInventoryAbs = $null
if ([string]::IsNullOrWhiteSpace($ProjectInventoryPath)) {
    if (-not (Test-Path -LiteralPath $projectInventoryRootAbs -PathType Container)) {
        throw "project inventory root not found: examples/sandbox/project-inventory"
    }
    $latest = Get-ChildItem -LiteralPath $projectInventoryRootAbs -File -Filter *.json -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
    if (-not $latest) {
        throw "No project inventory found under examples/sandbox/project-inventory."
    }
    $projectInventoryAbs = $latest.FullName
} else {
    if ([System.IO.Path]::IsPathRooted($ProjectInventoryPath)) {
        $projectInventoryAbs = [System.IO.Path]::GetFullPath($ProjectInventoryPath)
        if (-not (Test-IsPathWithin -CandidatePath $projectInventoryAbs -ParentPath $sandboxAnchorAbs)) {
            throw "project_inventory_path must remain inside examples/sandbox."
        }
    } else {
        $projectInventoryAbs = Get-SafeRelativePathAbs -RelativePath $ProjectInventoryPath -AllowedRootAbs $sandboxAnchorAbs -Label "project_inventory_path"
    }
}

if (-not (Test-Path -LiteralPath $projectInventoryAbs -PathType Leaf)) {
    throw "project_inventory_path not found: $ProjectInventoryPath"
}

$projectInventory = $null
try {
    $projectInventory = Get-Content -LiteralPath $projectInventoryAbs -Raw | ConvertFrom-Json
} catch {
    throw "project inventory could not be parsed as JSON: $projectInventoryAbs"
}

$sourceProjectInventoryId = [string]$projectInventory.inventory_id
if ([string]::IsNullOrWhiteSpace($sourceProjectInventoryId)) {
    throw "project inventory is missing inventory_id."
}

$projectRootRel = [string]$projectInventory.project_root
if ([string]::IsNullOrWhiteSpace($projectRootRel)) {
    $projectRootRel = "."
}

$projectRootAbs = $null
if ([System.IO.Path]::IsPathRooted($projectRootRel)) {
    $projectRootAbs = [System.IO.Path]::GetFullPath($projectRootRel)
} else {
    $projectRootAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $projectRootRel.Replace("/", "\")))
}
if (-not (Test-IsPathWithin -CandidatePath $projectRootAbs -ParentPath $repoRoot)) {
    throw "project_root resolved outside repository root."
}
if (-not (Test-Path -LiteralPath $projectRootAbs -PathType Container)) {
    throw "project_root does not exist: $projectRootRel"
}

$inventoryId = "sandbox-asset-candidate-inventory-$([Guid]::NewGuid().ToString('N'))"
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = "$InventoryRoot/$inventoryId.json"
}
$outputAbs = Get-SafeRelativePathAbs -RelativePath $OutputPath -AllowedRootAbs $assetCandidateRootAbs -Label "output_path"

$warnings = New-Object System.Collections.Generic.List[string]
$scannedRootSet = New-HashSet
$generatedFolderSet = New-HashSet

$inputRootCandidates = @()
$inputRootCandidates += @($projectInventory.known_asset_folders)
$inputRootCandidates += @($projectInventory.generated_asset_candidate_folders)

foreach ($candidateRoot in $inputRootCandidates) {
    $relative = [string]$candidateRoot
    if ([string]::IsNullOrWhiteSpace($relative)) {
        continue
    }

    $abs = $null
    if ([System.IO.Path]::IsPathRooted($relative)) {
        $abs = [System.IO.Path]::GetFullPath($relative)
    } else {
        $abs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $relative.Replace("/", "\")))
    }

    if (-not (Test-IsPathWithin -CandidatePath $abs -ParentPath $repoRoot)) {
        $warnings.Add("Skipped scan root outside repository: $relative") | Out-Null
        continue
    }
    if (-not (Test-Path -LiteralPath $abs -PathType Container)) {
        continue
    }
    if (Test-IsCachePath -PathValue $abs) {
        $warnings.Add("cache is not an allowed scan root. Skipped: $relative") | Out-Null
        continue
    }

    $scannedRootSet.Add((Get-RepoRelativePath -AbsolutePath $abs)) | Out-Null
}

if (@($scannedRootSet).Count -eq 0) {
    foreach ($fallback in @("scripts", "source", "assets", "examples/sandbox/staging")) {
        $abs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $fallback.Replace("/", "\")))
        if ((Test-Path -LiteralPath $abs -PathType Container) -and -not (Test-IsCachePath -PathValue $abs)) {
            $scannedRootSet.Add((Get-RepoRelativePath -AbsolutePath $abs)) | Out-Null
        }
    }
}

foreach ($generatedFolder in @($projectInventory.generated_asset_candidate_folders)) {
    $relative = [string]$generatedFolder
    if ([string]::IsNullOrWhiteSpace($relative)) { continue }
    $abs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $relative.Replace("/", "\")))
    if ((Test-Path -LiteralPath $abs -PathType Container) -and -not (Test-IsCachePath -PathValue $abs)) {
        $generatedFolderSet.Add((Get-RepoRelativePath -AbsolutePath $abs)) | Out-Null
    }
}

foreach ($scanRel in (Convert-HashSetToSortedArray -Set $scannedRootSet)) {
    $scanAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $scanRel.Replace("/", "\")))
    foreach ($dir in Get-ChildItem -LiteralPath $scanAbs -Directory -Recurse -Depth 4 -ErrorAction SilentlyContinue) {
        if (Test-IsCachePath -PathValue $dir.FullName) {
            continue
        }

        if (
            $dir.Name -eq "generated" -or $dir.Name -eq "Generated" -or $dir.Name -eq "generated_assets" -or
            $dir.Name -eq "generated-assets" -or $dir.Name -eq "autogen" -or
            $dir.Name -eq "outputs" -or $dir.Name -eq "Output" -or $dir.Name -eq "maxine_generated"
        ) {
            $generatedFolderSet.Add((Get-RepoRelativePath -AbsolutePath $dir.FullName)) | Out-Null
        }
    }
}

$evidenceState = Collect-SandboxEvidence -RepoRootAbs $repoRoot
$seenCandidatePaths = New-HashSet
$materialTextureCandidateIds = New-HashSet
$metadataCandidateIds = New-HashSet
$sourceCandidates = New-Object System.Collections.Generic.List[object]

foreach ($scanRel in (Convert-HashSetToSortedArray -Set $scannedRootSet)) {
    $scanAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $scanRel.Replace("/", "\")))
    foreach ($file in Get-ChildItem -LiteralPath $scanAbs -File -Recurse -Depth 8 -ErrorAction SilentlyContinue) {
        if (Test-IsCachePath -PathValue $file.FullName) {
            continue
        }

        $relativePath = Get-RepoRelativePath -AbsolutePath $file.FullName
        $lower = $relativePath.ToLowerInvariant()
        $isCandidate = $false

        foreach ($suffix in @(
            ".fbx", ".glb", ".gltf", ".obj", ".blend",
            ".material", ".azmaterial",
            ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr",
            ".forge.json", ".manifest.json", ".meta", ".json"
        )) {
            if ($lower.EndsWith($suffix)) {
                $isCandidate = $true
                break
            }
        }

        if (-not $isCandidate) {
            continue
        }

        if ($seenCandidatePaths.Contains($relativePath)) {
            continue
        }
        $seenCandidatePaths.Add($relativePath) | Out-Null

        $classification = Get-CandidateClassification -RelativePath $relativePath
        $pathHash = [System.BitConverter]::ToString(
            [System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($relativePath.ToLowerInvariant()))
        ).Replace("-", "").ToLowerInvariant()
        $fileHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()

        $candidateId = "asset-candidate-$($pathHash.Substring(0, 24))"
        $evidenceLinks = New-CandidateEvidenceLinks -RelativePath $relativePath -EvidenceState $evidenceState

        $candidate = [ordered]@{
            candidate_id = $candidateId
            relative_path = $relativePath
            extension = $file.Extension.ToLowerInvariant()
            category = [string]$classification.category
            size_bytes = [int64]$file.Length
            sha256 = $fileHash
            last_write_time_utc = $file.LastWriteTimeUtc.ToString("yyyy-MM-ddTHH:mm:ssZ")
            evidence_links = $evidenceLinks
            confidence = [string]$classification.confidence
            notes = @("Read-only inventory candidate from approved project scan roots.")
        }

        $sourceCandidates.Add($candidate) | Out-Null

        if ([string]$classification.bucket -eq "material_texture") {
            $materialTextureCandidateIds.Add($candidateId) | Out-Null
        } elseif ([string]$classification.bucket -eq "metadata") {
            $metadataCandidateIds.Add($candidateId) | Out-Null
        }
    }
}

$sortedCandidates = @($sourceCandidates | Sort-Object relative_path)

$inventory = [ordered]@{
    schema_version = "1.0.0"
    inventory_id = $inventoryId
    source_project_inventory_id = $sourceProjectInventoryId
    project_root = Get-RepoRelativePath -AbsolutePath $projectRootAbs
    sandbox_root = "examples/sandbox"
    scanned_roots = @(Convert-HashSetToSortedArray -Set $scannedRootSet)
    generated_candidate_folders = @(Convert-HashSetToSortedArray -Set $generatedFolderSet)
    source_asset_candidates = $sortedCandidates
    material_texture_candidates = @(Convert-HashSetToSortedArray -Set $materialTextureCandidateIds)
    metadata_provenance_candidates = @(Convert-HashSetToSortedArray -Set $metadataCandidateIds)
    linked_sandbox_evidence = [ordered]@{
        receipt_ids = @(Convert-HashSetToSortedArray -Set $evidenceState.receipt_ids)
        review_packet_ids = @(Convert-HashSetToSortedArray -Set $evidenceState.review_packet_ids)
        decision_ids = @(Convert-HashSetToSortedArray -Set $evidenceState.decision_ids)
        workflow_run_ids = @(Convert-HashSetToSortedArray -Set $evidenceState.workflow_run_ids)
        evidence_bundle_ids = @(Convert-HashSetToSortedArray -Set $evidenceState.evidence_bundle_ids)
    }
    warnings = @($warnings)
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
    output_path = Get-RepoRelativePath -AbsolutePath $outputAbs
    created_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

Write-JsonFile -InputObject $inventory -OutputPath $outputAbs
$inventory | ConvertTo-Json -Depth 100
