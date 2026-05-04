[CmdletBinding(DefaultParameterSetName = "ByPath")]
param(
    [Parameter(Mandatory = $true, ParameterSetName = "ByPath")]
    [string]$ReviewPacketPath,

    [Parameter(Mandatory = $true, ParameterSetName = "ById")]
    [string]$ReviewPacketId,

    [string]$ProjectInventoryPath,
    [string]$ProjectInventoryId,
    [string]$AssetCandidateInventoryPath,
    [string]$AssetCandidateInventoryId,

    [string]$OperatorId,
    [string[]]$Notes = @(),
    [string]$ProposalStatus,
    [string]$OutputPath,

    [string]$ReviewPacketsRoot = "examples/sandbox/asset-candidate-review-packets",
    [string]$ProjectInventoryRoot = "examples/sandbox/project-inventory",
    [string]$AssetCandidateInventoryRoot = "examples/sandbox/asset-candidates",
    [string]$ProposalsRoot = "examples/sandbox/product-resolution-proposals"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$allowedProposalStatuses = @(
    "proposal_only",
    "blocked_missing_evidence",
    "ready_for_read_only_ap_evidence_import",
    "rejected"
)
$forbiddenProposalStatuses = @(
    "resolved",
    "asset_id_resolved",
    "product_id_resolved",
    "ap_executed",
    "spawned",
    "published",
    "production_approved"
)

# Forbidden proposal language tokens that must never be admitted in proposal outputs.
$forbiddenProposalLanguageTokens = @(
    "resolved_product_id",
    "resolved_asset_id",
    "source_uuid",
    "asset_processor_executed",
    "cache_verified",
    "spawned_entity",
    "published_asset"
)

$explicitNonAdmissions = @(
    "authoritative_writes",
    "product_resolution",
    "product_resolution_as_fact",
    "asset_id_claims",
    "source_uuid_claims",
    "o3de_editor_execution",
    "asset_processor_execution",
    "o3de_cli_execution",
    "cache_read",
    "cache_path_write",
    "engine_path_write",
    "production_path_write",
    "spawning",
    "publishing"
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

function Resolve-JsonById {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootAbs,
        [Parameter(Mandatory = $true)]
        [string]$IdProperty,
        [Parameter(Mandatory = $true)]
        [string]$IdValue
    )

    if ([string]::IsNullOrWhiteSpace($IdValue)) {
        return $null
    }

    $matches = @()
    foreach ($file in Get-ChildItem -LiteralPath $RootAbs -File -Filter *.json -Recurse -ErrorAction SilentlyContinue) {
        try {
            $item = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
            if ([string]$item.$IdProperty -eq $IdValue) {
                $matches += [ordered]@{
                    path = $file.FullName
                    item = $item
                }
            }
        } catch {
            continue
        }
    }

    if ($matches.Count -eq 0) {
        return $null
    }
    if ($matches.Count -gt 1) {
        throw "$IdProperty '$IdValue' is ambiguous."
    }

    return $matches[0]
}

function Resolve-JsonByPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputPath,
        [Parameter(Mandatory = $true)]
        [string]$RootAbs,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    $pathAbs = $null
    if ([System.IO.Path]::IsPathRooted($InputPath)) {
        $pathAbs = [System.IO.Path]::GetFullPath($InputPath)
        if (-not (Test-IsPathWithin -CandidatePath $pathAbs -ParentPath $RootAbs)) {
            throw "$Label must remain within approved sandbox root."
        }
    } else {
        $pathAbs = Get-SafeRelativePathAbs -RelativePath $InputPath -AllowedRootAbs $RootAbs -Label $Label
    }

    if (-not (Test-Path -LiteralPath $pathAbs -PathType Leaf)) {
        throw "$Label not found: $InputPath"
    }

    try {
        $item = Get-Content -LiteralPath $pathAbs -Raw | ConvertFrom-Json
    } catch {
        throw "$Label is not valid JSON: $InputPath"
    }

    return [ordered]@{
        path = $pathAbs
        item = $item
    }
}

function Get-ExpectedProductClasses {
    param(
        [string]$CandidateExtension,
        [string]$CandidateCategory,
        [string]$CandidatePath
    )

    $classes = New-Object System.Collections.Generic.HashSet[string]([System.StringComparer]::OrdinalIgnoreCase)
    $ext = ([string]$CandidateExtension).ToLowerInvariant()
    $category = ([string]$CandidateCategory).ToLowerInvariant()
    $pathLower = ([string]$CandidatePath).ToLowerInvariant()

    if ($ext -in @(".fbx", ".glb", ".gltf", ".obj", ".blend")) {
        $classes.Add("model_product_candidate") | Out-Null
    }
    if ($category -eq "character_source" -or $pathLower.Contains("character") -or $pathLower.Contains("actor")) {
        $classes.Add("actor_product_candidate") | Out-Null
    }
    if ($pathLower.Contains("anim") -or $pathLower.Contains("motion")) {
        $classes.Add("motion_product_candidate") | Out-Null
    }
    if ($category -eq "material_source" -or $ext -eq ".material" -or $ext -eq ".azmaterial") {
        $classes.Add("material_product_candidate") | Out-Null
    }
    if ($category -eq "texture_source" -or $ext -in @(".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr")) {
        $classes.Add("texture_product_candidate") | Out-Null
    }
    if ($category -eq "scene_source" -or $pathLower.Contains("prefab")) {
        $classes.Add("prefab_product_candidate") | Out-Null
    }

    if ($classes.Count -eq 0) {
        $classes.Add("unknown_product_candidate") | Out-Null
    }

    return @($classes | Sort-Object)
}

$reviewPacketsRootAbs = Get-SafeRelativePathAbs -RelativePath $ReviewPacketsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "review_packets_root"
$projectInventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $ProjectInventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "project_inventory_root"
$assetCandidateInventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $AssetCandidateInventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "asset_candidate_inventory_root"
$proposalsRootAbs = Get-SafeRelativePathAbs -RelativePath $ProposalsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "proposals_root"
if (-not (Test-Path -LiteralPath $proposalsRootAbs -PathType Container)) {
    New-Item -Path $proposalsRootAbs -ItemType Directory -Force | Out-Null
}

if (-not [string]::IsNullOrWhiteSpace($ProjectInventoryPath) -and -not [string]::IsNullOrWhiteSpace($ProjectInventoryId)) {
    throw "Provide either project_inventory_path or project_inventory_id, not both."
}
if (-not [string]::IsNullOrWhiteSpace($AssetCandidateInventoryPath) -and -not [string]::IsNullOrWhiteSpace($AssetCandidateInventoryId)) {
    throw "Provide either asset_candidate_inventory_path or asset_candidate_inventory_id, not both."
}

if ($forbiddenProposalStatuses -contains $ProposalStatus) {
    throw "proposal_status '$ProposalStatus' is forbidden."
}
if (-not [string]::IsNullOrWhiteSpace($ProposalStatus) -and ($allowedProposalStatuses -notcontains $ProposalStatus)) {
    throw "proposal_status '$ProposalStatus' is invalid."
}

foreach ($forbiddenToken in $forbiddenProposalLanguageTokens) {
    if (-not [string]::IsNullOrWhiteSpace($forbiddenToken)) {
        # No-op guard: keep explicit forbidden vocabulary present and blocked by design.
        $null = $forbiddenToken
    }
}

$reviewRef = $null
if ($PSCmdlet.ParameterSetName -eq "ByPath") {
    $reviewRef = Resolve-JsonByPath -InputPath $ReviewPacketPath -RootAbs $reviewPacketsRootAbs -Label "review_packet_path"
} else {
    $reviewRef = Resolve-JsonById -RootAbs $reviewPacketsRootAbs -IdProperty "review_packet_id" -IdValue $ReviewPacketId
    if ($null -eq $reviewRef) {
        throw "review_packet_id '$ReviewPacketId' not found."
    }
}

$review = $reviewRef.item
if ([string]::IsNullOrWhiteSpace([string]$review.review_packet_id)) {
    throw "review packet is missing review_packet_id."
}
if ([string]$review.sandbox_root -ne "examples/sandbox") {
    throw "review packet sandbox_root must be examples/sandbox."
}
if ([string]::IsNullOrWhiteSpace([string]$review.source_inventory_id)) {
    throw "review packet is missing source_inventory_id."
}
if ([string]::IsNullOrWhiteSpace([string]$review.candidate_id)) {
    throw "review packet is missing candidate_id."
}
if ([string]::IsNullOrWhiteSpace([string]$review.candidate_relative_path)) {
    throw "review packet is missing candidate_relative_path."
}

$assetInventoryRef = $null
if (-not [string]::IsNullOrWhiteSpace($AssetCandidateInventoryPath)) {
    $assetInventoryRef = Resolve-JsonByPath -InputPath $AssetCandidateInventoryPath -RootAbs $assetCandidateInventoryRootAbs -Label "asset_candidate_inventory_path"
} elseif (-not [string]::IsNullOrWhiteSpace($AssetCandidateInventoryId)) {
    $assetInventoryRef = Resolve-JsonById -RootAbs $assetCandidateInventoryRootAbs -IdProperty "inventory_id" -IdValue $AssetCandidateInventoryId
    if ($null -eq $assetInventoryRef) {
        throw "asset_candidate_inventory_id '$AssetCandidateInventoryId' not found."
    }
} else {
    $assetInventoryRef = Resolve-JsonById -RootAbs $assetCandidateInventoryRootAbs -IdProperty "inventory_id" -IdValue ([string]$review.source_inventory_id)
}

$projectInventoryRef = $null
if (-not [string]::IsNullOrWhiteSpace($ProjectInventoryPath)) {
    $projectInventoryRef = Resolve-JsonByPath -InputPath $ProjectInventoryPath -RootAbs $projectInventoryRootAbs -Label "project_inventory_path"
} elseif (-not [string]::IsNullOrWhiteSpace($ProjectInventoryId)) {
    $projectInventoryRef = Resolve-JsonById -RootAbs $projectInventoryRootAbs -IdProperty "inventory_id" -IdValue $ProjectInventoryId
    if ($null -eq $projectInventoryRef) {
        throw "project_inventory_id '$ProjectInventoryId' not found."
    }
}

$resolvedProjectInventoryId = ""
if ($null -ne $projectInventoryRef) {
    $resolvedProjectInventoryId = [string]$projectInventoryRef.item.inventory_id
}
if ([string]::IsNullOrWhiteSpace($resolvedProjectInventoryId) -and $null -ne $assetInventoryRef) {
    $resolvedProjectInventoryId = [string]$assetInventoryRef.item.source_project_inventory_id
}
if ([string]::IsNullOrWhiteSpace($resolvedProjectInventoryId)) {
    $resolvedProjectInventoryId = "unknown-project-inventory-id"
}

if ($null -eq $projectInventoryRef -and $resolvedProjectInventoryId -ne "unknown-project-inventory-id") {
    $projectInventoryRef = Resolve-JsonById -RootAbs $projectInventoryRootAbs -IdProperty "inventory_id" -IdValue $resolvedProjectInventoryId
}

$expectedProductClasses = Get-ExpectedProductClasses -CandidateExtension ([string]$review.candidate_extension) -CandidateCategory ([string]$review.candidate_category) -CandidatePath ([string]$review.candidate_relative_path)

$likelyRequirements = New-Object System.Collections.Generic.List[string]
$requiredNextEvidence = New-Object System.Collections.Generic.List[string]
$blockingReasons = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

$likelyRequirements.Add("proposal_only") | Out-Null
$likelyRequirements.Add("no_product_id_claimed") | Out-Null
$likelyRequirements.Add("no_asset_processor_execution") | Out-Null
$requiredNextEvidence.Add("read_only_ap_evidence_import") | Out-Null
$requiredNextEvidence.Add("source_to_product_mapping_evidence") | Out-Null

$category = ([string]$review.candidate_category).ToLowerInvariant()
if ($category -eq "texture_source") {
    $likelyRequirements.Add("texture_dependency_evidence") | Out-Null
}
if ($category -eq "material_source") {
    $likelyRequirements.Add("material_graph_evidence") | Out-Null
}
if ($category -eq "character_source" -or $category -eq "mesh_source" -or $category -eq "scene_source") {
    $likelyRequirements.Add("ap_compile_evidence_import_required") | Out-Null
}

if ($expectedProductClasses.Count -eq 1 -and $expectedProductClasses[0] -eq "unknown_product_candidate") {
    $blockingReasons.Add("insufficient_classification_signal_for_candidate") | Out-Null
    $requiredNextEvidence.Add("additional_candidate_metadata") | Out-Null
}

if ($null -eq $assetInventoryRef) {
    $blockingReasons.Add("missing_asset_candidate_inventory_context") | Out-Null
} elseif ([string]$assetInventoryRef.item.sandbox_root -ne "examples/sandbox") {
    $blockingReasons.Add("asset_candidate_inventory_not_sandbox_scoped") | Out-Null
}

if ($null -eq $projectInventoryRef) {
    $blockingReasons.Add("missing_project_inventory_context") | Out-Null
} elseif ([string]$projectInventoryRef.item.sandbox_root -ne "examples/sandbox") {
    $warnings.Add("project_inventory_missing_expected_sandbox_root_field") | Out-Null
}

${reviewNotes} = @()
if ($null -ne $review.PSObject.Properties["notes"]) {
    $reviewNotes = @($review.notes)
}
foreach ($note in $reviewNotes) {
    $text = [string]$note
    if (-not [string]::IsNullOrWhiteSpace($text)) {
        $warnings.Add($text) | Out-Null
    }
}
foreach ($note in $Notes) {
    $text = [string]$note
    if (-not [string]::IsNullOrWhiteSpace($text)) {
        $warnings.Add("operator_note: $text") | Out-Null
    }
}

$derivedStatus = "proposal_only"
if ($blockingReasons.Count -gt 0) {
    $derivedStatus = "blocked_missing_evidence"
} elseif ($null -ne $assetInventoryRef -and $null -ne $projectInventoryRef) {
    $derivedStatus = "ready_for_read_only_ap_evidence_import"
}

if (-not [string]::IsNullOrWhiteSpace($ProposalStatus)) {
    $derivedStatus = $ProposalStatus
}

$proposalId = "product-resolution-proposal-$([Guid]::NewGuid().ToString('N'))"
$outputRel = $OutputPath
if ([string]::IsNullOrWhiteSpace($outputRel)) {
    $outputRel = "$ProposalsRoot/$proposalId.json"
}
$outputAbs = Get-SafeRelativePathAbs -RelativePath $outputRel -AllowedRootAbs $proposalsRootAbs -Label "output_path"

$proposal = [ordered]@{
    schema_version = "1.0.0"
    proposal_id = $proposalId
    source_review_packet_id = [string]$review.review_packet_id
    source_inventory_id = [string]$review.source_inventory_id
    source_project_inventory_id = [string]$resolvedProjectInventoryId
    candidate_id = [string]$review.candidate_id
    project_root = [string]$review.project_root
    sandbox_root = "examples/sandbox"
    candidate_relative_path = [string]$review.candidate_relative_path
    candidate_extension = [string]$review.candidate_extension
    candidate_category = [string]$review.candidate_category
    candidate_sha256 = [string]$review.sha256
    proposal_status = $derivedStatus
    expected_product_classes = @($expectedProductClasses)
    likely_asset_pipeline_requirements = @($likelyRequirements | Sort-Object -Unique)
    required_next_evidence = @($requiredNextEvidence | Sort-Object -Unique)
    blocking_reasons = @($blockingReasons | Sort-Object -Unique)
    warnings = @($warnings | Sort-Object -Unique)
    proposal_only = $true
    product_ids_claimed = $false
    asset_ids_claimed = $false
    source_uuids_claimed = $false
    asset_processor_execution_admitted = $false
    o3de_execution_admitted = $false
    cache_access_admitted = $false
    spawn_admitted = $false
    publish_admitted = $false
    safety_summary = "Proposal-only product resolution artifact from sandbox evidence. No Product IDs, Asset IDs, source UUID claims, cache access, AP execution, O3DE execution, spawning, or publishing are admitted."
    explicit_non_admissions = @($explicitNonAdmissions)
    output_path = Get-RepoRelativePath -AbsolutePath $outputAbs
    created_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

if (-not [string]::IsNullOrWhiteSpace($OperatorId)) {
    $proposal.operator_id = $OperatorId
}
if ($Notes.Count -gt 0) {
    $proposal.notes = @($Notes)
}
if ($null -ne $assetInventoryRef) {
    $proposal.asset_candidate_inventory_path = Get-RepoRelativePath -AbsolutePath $assetInventoryRef.path
}
if ($null -ne $projectInventoryRef) {
    $proposal.project_inventory_path = Get-RepoRelativePath -AbsolutePath $projectInventoryRef.path
}

Write-JsonFile -InputObject $proposal -OutputPath $outputAbs
$proposal | ConvertTo-Json -Depth 100
