[CmdletBinding(DefaultParameterSetName = "ByPath")]
param(
    [Parameter(Mandatory = $true, ParameterSetName = "ByPath")]
    [string]$InventoryPath,

    [Parameter(Mandatory = $true, ParameterSetName = "ById")]
    [string]$InventoryId,

    [string]$CandidateId,
    [switch]$AllCandidates,

    [string]$OperatorId,
    [string[]]$Notes = @(),
    [string]$OperatorDecisionState = "pending_review",
    [string]$RecommendedNextStep = "inspect_candidate",

    [string]$InventoryRoot = "examples/sandbox/asset-candidates",
    [string]$ReviewPacketsRoot = "examples/sandbox/asset-candidate-review-packets",
    [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$allowedOperatorDecisionStates = @(
    "pending_review",
    "accepted_for_sandbox_only",
    "rejected",
    "needs_more_evidence",
    "request_candidate_cleanup"
)
$forbiddenOperatorDecisionStates = @(
    "approve_product_resolution",
    "approve_asset_id_claim",
    "approve_spawn",
    "approve_publish",
    "approve_o3de_execution",
    "approve_asset_processor_execution",
    "approve_authoritative_write"
)

$allowedNextSteps = @(
    "inspect_candidate",
    "bundle_evidence",
    "request_more_evidence",
    "propose_product_resolution_later",
    "reject_candidate",
    "request_sandbox_cleanup"
)
$forbiddenNextSteps = @(
    "run_asset_processor",
    "launch_editor",
    "spawn_entity",
    "publish_asset",
    "claim_asset_id"
)

$explicitNonAdmissions = @(
    "authoritative_writes",
    "o3de_editor_execution",
    "asset_processor_execution",
    "o3de_cli_execution",
    "product_resolution",
    "asset_id_claims",
    "spawning",
    "publishing",
    "production_cache_engine_writes"
)

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

function New-HashSet {
    return ,([System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase))
}

function Resolve-InventoryById {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DesiredInventoryId,
        [Parameter(Mandatory = $true)]
        [string]$InventoryRootAbs
    )

    if (-not (Test-Path -LiteralPath $InventoryRootAbs -PathType Container)) {
        throw "inventory root not found: $InventoryRoot"
    }

    $matches = @()
    foreach ($file in Get-ChildItem -LiteralPath $InventoryRootAbs -File -Filter *.json -ErrorAction SilentlyContinue) {
        try {
            $candidate = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
            if ([string]$candidate.inventory_id -eq $DesiredInventoryId) {
                $matches += [ordered]@{
                    path = $file.FullName
                    item = $candidate
                }
            }
        } catch {
            continue
        }
    }

    if ($matches.Count -eq 0) {
        throw "inventory_id '$DesiredInventoryId' not found."
    }
    if ($matches.Count -gt 1) {
        throw "inventory_id '$DesiredInventoryId' is ambiguous."
    }

    return $matches[0]
}

function Resolve-InventoryByPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputPath,
        [Parameter(Mandatory = $true)]
        [string]$InventoryRootAbs
    )

    $inventoryAbs = $null
    if ([System.IO.Path]::IsPathRooted($InputPath)) {
        $inventoryAbs = [System.IO.Path]::GetFullPath($InputPath)
        if (-not (Test-IsPathWithin -CandidatePath $inventoryAbs -ParentPath $InventoryRootAbs)) {
            throw "inventory_path must remain under asset candidate inventory root."
        }
    } else {
        $inventoryAbs = Get-SafeRelativePathAbs -RelativePath $InputPath -AllowedRootAbs $InventoryRootAbs -Label "inventory_path"
    }

    if (-not (Test-Path -LiteralPath $inventoryAbs -PathType Leaf)) {
        throw "inventory_path not found: $InputPath"
    }

    try {
        $item = Get-Content -LiteralPath $inventoryAbs -Raw | ConvertFrom-Json
    } catch {
        throw "inventory_path is not valid JSON: $InputPath"
    }

    return [ordered]@{
        path = $inventoryAbs
        item = $item
    }
}

if ($forbiddenOperatorDecisionStates -contains $OperatorDecisionState) {
    throw "operator_decision_state '$OperatorDecisionState' is forbidden."
}
if ($allowedOperatorDecisionStates -notcontains $OperatorDecisionState) {
    throw "operator_decision_state '$OperatorDecisionState' is invalid."
}
if ($forbiddenNextSteps -contains $RecommendedNextStep) {
    throw "recommended_next_step '$RecommendedNextStep' is forbidden."
}
if ($allowedNextSteps -notcontains $RecommendedNextStep) {
    throw "recommended_next_step '$RecommendedNextStep' is invalid."
}

if (($AllCandidates -and -not [string]::IsNullOrWhiteSpace($CandidateId)) -or (-not $AllCandidates -and [string]::IsNullOrWhiteSpace($CandidateId))) {
    throw "Provide either candidate_id or -AllCandidates."
}

$inventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $InventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "inventory_root"
$reviewPacketsRootAbs = Get-SafeRelativePathAbs -RelativePath $ReviewPacketsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "review_packets_root"
if (-not (Test-Path -LiteralPath $reviewPacketsRootAbs -PathType Container)) {
    New-Item -Path $reviewPacketsRootAbs -ItemType Directory -Force | Out-Null
}

$inventoryRef = $null
if ($PSCmdlet.ParameterSetName -eq "ByPath") {
    $inventoryRef = Resolve-InventoryByPath -InputPath $InventoryPath -InventoryRootAbs $inventoryRootAbs
} else {
    $inventoryRef = Resolve-InventoryById -DesiredInventoryId $InventoryId -InventoryRootAbs $inventoryRootAbs
}

$inventory = $inventoryRef.item
$sourceInventoryId = [string]$inventory.inventory_id
if ([string]::IsNullOrWhiteSpace($sourceInventoryId)) {
    throw "inventory_id is missing."
}
if ([string]$inventory.sandbox_root -ne "examples/sandbox") {
    throw "inventory sandbox_root must be examples/sandbox."
}

$sourceCandidates = @($inventory.source_asset_candidates)
if ($sourceCandidates.Count -eq 0) {
    throw "inventory has no source_asset_candidates."
}

$selectedCandidates = @()
if ($AllCandidates) {
    $selectedCandidates = @($sourceCandidates)
} else {
    $selected = $sourceCandidates | Where-Object { [string]$_.candidate_id -eq $CandidateId } | Select-Object -First 1
    if (-not $selected) {
        throw "candidate_id '$CandidateId' not found in inventory."
    }
    $selectedCandidates = @($selected)
}

$batchId = "asset-candidate-review-batch-$([Guid]::NewGuid().ToString('N'))"
$multiCandidate = $selectedCandidates.Count -gt 1
$outputBaseAbs = $null
$singleExplicitOutputAbs = $null

if ($multiCandidate) {
    if ([string]::IsNullOrWhiteSpace($OutputPath)) {
        $outputBaseAbs = [System.IO.Path]::GetFullPath((Join-Path $reviewPacketsRootAbs $batchId))
    } else {
        if ($OutputPath.ToLowerInvariant().EndsWith(".json")) {
            throw "output_path cannot be a file when -AllCandidates is used."
        }
        $outputBaseAbs = Get-SafeRelativePathAbs -RelativePath $OutputPath -AllowedRootAbs $reviewPacketsRootAbs -Label "output_path"
    }
    if (-not (Test-IsPathWithin -CandidatePath $outputBaseAbs -ParentPath $reviewPacketsRootAbs)) {
        throw "output_path escapes asset candidate review packets root."
    }
    if (-not (Test-Path -LiteralPath $outputBaseAbs -PathType Container)) {
        New-Item -Path $outputBaseAbs -ItemType Directory -Force | Out-Null
    }
} else {
    if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
        if ($OutputPath.ToLowerInvariant().EndsWith(".json")) {
            $singleExplicitOutputAbs = Get-SafeRelativePathAbs -RelativePath $OutputPath -AllowedRootAbs $reviewPacketsRootAbs -Label "output_path"
        } else {
            $singleDirAbs = Get-SafeRelativePathAbs -RelativePath $OutputPath -AllowedRootAbs $reviewPacketsRootAbs -Label "output_path"
            if (-not (Test-Path -LiteralPath $singleDirAbs -PathType Container)) {
                New-Item -Path $singleDirAbs -ItemType Directory -Force | Out-Null
            }
            $singleExplicitOutputAbs = $singleDirAbs
        }
    }
}

$materialTextureIds = New-HashSet
foreach ($id in @($inventory.material_texture_candidates)) {
    $idText = [string]$id
    if (-not [string]::IsNullOrWhiteSpace($idText)) {
        $materialTextureIds.Add($idText) | Out-Null
    }
}

$provenanceIds = New-HashSet
foreach ($id in @($inventory.metadata_provenance_candidates)) {
    $idText = [string]$id
    if (-not [string]::IsNullOrWhiteSpace($idText)) {
        $provenanceIds.Add($idText) | Out-Null
    }
}

$resultPackets = @()

foreach ($candidate in $selectedCandidates) {
    $candidateIdText = [string]$candidate.candidate_id
    if ([string]::IsNullOrWhiteSpace($candidateIdText)) {
        throw "candidate is missing candidate_id."
    }

    $relativePath = [string]$candidate.relative_path
    if ([string]::IsNullOrWhiteSpace($relativePath)) {
        throw "candidate '$candidateIdText' is missing relative_path."
    }
    $normalized = $relativePath.Replace("\", "/")
    if ($normalized.StartsWith("/") -or [System.IO.Path]::IsPathRooted($relativePath)) {
        throw "candidate '$candidateIdText' relative_path must be relative."
    }
    if (($normalized -split "/") -contains "..") {
        throw "candidate '$candidateIdText' relative_path contains parent traversal and is blocked."
    }

    $reviewPacketId = "asset-candidate-review-packet-$([Guid]::NewGuid().ToString('N'))"
    $outputAbs = $null
    if ($multiCandidate) {
        $outputAbs = Join-Path $outputBaseAbs "$reviewPacketId.json"
    } elseif ($null -ne $singleExplicitOutputAbs) {
        if ($singleExplicitOutputAbs.ToLowerInvariant().EndsWith(".json")) {
            $outputAbs = $singleExplicitOutputAbs
        } else {
            $outputAbs = Join-Path $singleExplicitOutputAbs "$reviewPacketId.json"
        }
    } else {
        $outputAbs = [System.IO.Path]::GetFullPath((Join-Path $reviewPacketsRootAbs "$reviewPacketId.json"))
    }

    if (-not (Test-IsPathWithin -CandidatePath $outputAbs -ParentPath $reviewPacketsRootAbs)) {
        throw "output path escapes approved asset candidate review packets root."
    }

    $sameDirProvenance = New-HashSet
    $sameDirMaterial = New-HashSet
    $candidateDir = [System.IO.Path]::GetDirectoryName($relativePath.Replace("/", "\"))
    foreach ($other in $sourceCandidates) {
        $otherId = [string]$other.candidate_id
        if ([string]::IsNullOrWhiteSpace($otherId) -or $otherId -eq $candidateIdText) {
            continue
        }

        $otherPath = [string]$other.relative_path
        $otherDir = [System.IO.Path]::GetDirectoryName($otherPath.Replace("/", "\"))
        if ($otherDir -ne $candidateDir) {
            continue
        }

        $otherCategory = [string]$other.category
        if ($otherCategory -eq "metadata_source") {
            $sameDirProvenance.Add($otherId) | Out-Null
        }
        if ($otherCategory -eq "material_source" -or $otherCategory -eq "texture_source") {
            $sameDirMaterial.Add($otherId) | Out-Null
        }
    }

    foreach ($id in $provenanceIds) {
        $sameDirProvenance.Add([string]$id) | Out-Null
    }
    foreach ($id in $materialTextureIds) {
        $sameDirMaterial.Add([string]$id) | Out-Null
    }

    $warnings = New-Object System.Collections.Generic.List[string]
    foreach ($entry in @($candidate.notes)) {
        $text = [string]$entry
        if (-not [string]::IsNullOrWhiteSpace($text)) {
            $warnings.Add($text) | Out-Null
        }
    }
    foreach ($entry in @($inventory.warnings)) {
        $text = [string]$entry
        if (-not [string]::IsNullOrWhiteSpace($text)) {
            $warnings.Add($text) | Out-Null
        }
    }
    foreach ($entry in $Notes) {
        $text = [string]$entry
        if (-not [string]::IsNullOrWhiteSpace($text)) {
            $warnings.Add("operator_note: $text") | Out-Null
        }
    }

    $packet = [ordered]@{
        schema_version = "1.0.0"
        review_packet_id = $reviewPacketId
        source_inventory_id = $sourceInventoryId
        candidate_id = $candidateIdText
        project_root = [string]$inventory.project_root
        sandbox_root = "examples/sandbox"
        candidate_relative_path = $relativePath
        candidate_extension = [string]$candidate.extension
        candidate_category = [string]$candidate.category
        size_bytes = [int64]$candidate.size_bytes
        sha256 = [string]$candidate.sha256
        last_write_time_utc = [string]$candidate.last_write_time_utc
        confidence = [string]$candidate.confidence
        evidence_links = $candidate.evidence_links
        provenance_links = @($sameDirProvenance | Sort-Object)
        material_texture_links = @($sameDirMaterial | Sort-Object)
        warnings = @($warnings)
        safety_summary = "Sandbox-only asset candidate review packet. This artifact does not authorize product resolution, Asset ID claims, spawning, publishing, O3DE/AP execution, or authoritative writes."
        recommended_next_step = $RecommendedNextStep
        operator_decision_state = $OperatorDecisionState
        explicit_non_admissions = @($explicitNonAdmissions)
        output_path = Get-RepoRelativePath -AbsolutePath $outputAbs
        created_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    }

    if (-not [string]::IsNullOrWhiteSpace($OperatorId)) {
        $packet.operator_id = $OperatorId
    }
    if ($Notes.Count -gt 0) {
        $packet.notes = @($Notes)
    }

    Write-JsonFile -InputObject $packet -OutputPath $outputAbs

    $resultPackets += [ordered]@{
        review_packet_id = $reviewPacketId
        source_inventory_id = $sourceInventoryId
        candidate_id = $candidateIdText
        operator_decision_state = $OperatorDecisionState
        recommended_next_step = $RecommendedNextStep
        output_path = $packet.output_path
    }
}

[ordered]@{
    schema_version = "1.0.0"
    review_packet_count = $resultPackets.Count
    review_packets = @($resultPackets)
} | ConvertTo-Json -Depth 100
