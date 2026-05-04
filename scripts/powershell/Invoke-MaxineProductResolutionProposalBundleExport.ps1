[CmdletBinding()]
param(
    [string]$ProposalPath,
    [string]$ProposalId,

    [string]$ProposalsRoot = "examples/sandbox/product-resolution-proposals",
    [string]$ReviewPacketsRoot = "examples/sandbox/asset-candidate-review-packets",
    [string]$AssetCandidateInventoryRoot = "examples/sandbox/asset-candidates",
    [string]$ProjectInventoryRoot = "examples/sandbox/project-inventory",
    [string]$ProposalBundlesRoot = "examples/sandbox/product-resolution-proposal-bundles",
    [string]$BundlePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$fallbackNonAdmissions = @(
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

function Resolve-Proposal {
    param(
        [string]$ProposalPath,
        [string]$ProposalId,
        [string]$ProposalsRootAbs
    )

    $hasPath = -not [string]::IsNullOrWhiteSpace($ProposalPath)
    $hasId = -not [string]::IsNullOrWhiteSpace($ProposalId)
    if (($hasPath -and $hasId) -or (-not $hasPath -and -not $hasId)) {
        throw "Provide either proposal_path or proposal_id."
    }

    if ($hasPath) {
        $proposalAbs = $null
        if ([System.IO.Path]::IsPathRooted($ProposalPath)) {
            $proposalAbs = [System.IO.Path]::GetFullPath($ProposalPath)
            if (-not (Test-IsPathWithin -CandidatePath $proposalAbs -ParentPath $ProposalsRootAbs)) {
                throw "proposal_path must remain under product-resolution-proposals."
            }
        } else {
            $proposalAbs = Get-SafeRelativePathAbs -RelativePath $ProposalPath -AllowedRootAbs $ProposalsRootAbs -Label "proposal_path"
        }

        if (-not (Test-Path -LiteralPath $proposalAbs -PathType Leaf)) {
            throw "proposal_path not found: $ProposalPath"
        }

        $item = Get-Content -LiteralPath $proposalAbs -Raw | ConvertFrom-Json
        return [ordered]@{
            path = $proposalAbs
            item = $item
        }
    }

    $match = Resolve-JsonById -RootAbs $ProposalsRootAbs -IdProperty "proposal_id" -IdValue $ProposalId
    if ($null -eq $match) {
        throw "proposal_id '$ProposalId' not found."
    }
    return $match
}

$proposalsRootAbs = Get-SafeRelativePathAbs -RelativePath $ProposalsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "proposals_root"
$reviewPacketsRootAbs = Get-SafeRelativePathAbs -RelativePath $ReviewPacketsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "review_packets_root"
$assetCandidateInventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $AssetCandidateInventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "asset_candidate_inventory_root"
$projectInventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $ProjectInventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "project_inventory_root"
$proposalBundlesRootAbs = Get-SafeRelativePathAbs -RelativePath $ProposalBundlesRoot -AllowedRootAbs $sandboxAnchorAbs -Label "proposal_bundles_root"
if (-not (Test-Path -LiteralPath $proposalBundlesRootAbs -PathType Container)) {
    New-Item -Path $proposalBundlesRootAbs -ItemType Directory -Force | Out-Null
}

$proposalRef = Resolve-Proposal -ProposalPath $ProposalPath -ProposalId $ProposalId -ProposalsRootAbs $proposalsRootAbs
$proposal = $proposalRef.item
if ([string]::IsNullOrWhiteSpace([string]$proposal.proposal_id)) {
    throw "proposal is missing proposal_id."
}
if ([string]$proposal.sandbox_root -ne "examples/sandbox") {
    throw "proposal sandbox_root must be examples/sandbox."
}

$reviewRef = Resolve-JsonById -RootAbs $reviewPacketsRootAbs -IdProperty "review_packet_id" -IdValue ([string]$proposal.source_review_packet_id)
if ($null -eq $reviewRef) {
    throw "source review packet not found for proposal."
}

$assetInventoryRef = Resolve-JsonById -RootAbs $assetCandidateInventoryRootAbs -IdProperty "inventory_id" -IdValue ([string]$proposal.source_inventory_id)
$projectInventoryRef = Resolve-JsonById -RootAbs $projectInventoryRootAbs -IdProperty "inventory_id" -IdValue ([string]$proposal.source_project_inventory_id)

$bundleId = "product-resolution-proposal-bundle-$([Guid]::NewGuid().ToString('N'))"
$manifestRel = $BundlePath
if ([string]::IsNullOrWhiteSpace($manifestRel)) {
    $manifestRel = "$ProposalBundlesRoot/$bundleId/bundle.manifest.json"
} elseif (-not $manifestRel.ToLowerInvariant().EndsWith(".json")) {
    $manifestRel = $manifestRel.TrimEnd("/", "\") + "/bundle.manifest.json"
}

$manifestAbs = Get-SafeRelativePathAbs -RelativePath $manifestRel -AllowedRootAbs $proposalBundlesRootAbs -Label "bundle_path"
$bundleDirAbs = Split-Path -Parent $manifestAbs
if (-not (Test-Path -LiteralPath $bundleDirAbs -PathType Container)) {
    New-Item -Path $bundleDirAbs -ItemType Directory -Force | Out-Null
}

$includedArtifacts = New-Object System.Collections.Generic.List[string]
$copiedArtifactPaths = New-Object System.Collections.Generic.List[string]
$artifactSha = [ordered]@{}

function Add-Snapshot {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string]$SnapshotName,
        [Parameter(Mandatory = $true)]
        [string]$ArtifactLabel
    )

    $snapshotAbs = Join-Path $bundleDirAbs $SnapshotName
    Write-JsonFile -InputObject $InputObject -OutputPath $snapshotAbs

    $snapshotRel = Get-RepoRelativePath -AbsolutePath $snapshotAbs
    $includedArtifacts.Add($ArtifactLabel) | Out-Null
    $copiedArtifactPaths.Add($snapshotRel) | Out-Null
    $artifactSha[$snapshotRel] = (Get-FileHash -LiteralPath $snapshotAbs -Algorithm SHA256).Hash
}

Add-Snapshot -InputObject $proposal -SnapshotName "product-resolution-proposal.snapshot.json" -ArtifactLabel "product_resolution_proposal"
Add-Snapshot -InputObject $reviewRef.item -SnapshotName "asset-candidate-review-packet.snapshot.json" -ArtifactLabel "asset_candidate_review_packet"
if ($null -ne $assetInventoryRef) {
    Add-Snapshot -InputObject $assetInventoryRef.item -SnapshotName "asset-candidate-inventory.snapshot.json" -ArtifactLabel "asset_candidate_inventory"
}
if ($null -ne $projectInventoryRef) {
    Add-Snapshot -InputObject $projectInventoryRef.item -SnapshotName "project-inventory.snapshot.json" -ArtifactLabel "project_inventory"
}

$linkSummary = [ordered]@{
    source_proposal_id = [string]$proposal.proposal_id
    source_review_packet_id = [string]$proposal.source_review_packet_id
    source_inventory_id = [string]$proposal.source_inventory_id
    source_project_inventory_id = [string]$proposal.source_project_inventory_id
    candidate_id = [string]$proposal.candidate_id
    expected_product_classes = @($proposal.expected_product_classes)
    proposal_status = [string]$proposal.proposal_status
}
Add-Snapshot -InputObject $linkSummary -SnapshotName "proposal-link-summary.snapshot.json" -ArtifactLabel "proposal_link_summary"

$explicitNonAdmissions = @($proposal.explicit_non_admissions)
if ($explicitNonAdmissions.Count -eq 0) {
    $explicitNonAdmissions = @($fallbackNonAdmissions)
}

$manifest = [ordered]@{
    schema_version = "1.0.0"
    bundle_id = $bundleId
    source_proposal_id = [string]$proposal.proposal_id
    source_review_packet_id = [string]$proposal.source_review_packet_id
    source_inventory_id = [string]$proposal.source_inventory_id
    source_project_inventory_id = [string]$proposal.source_project_inventory_id
    candidate_id = [string]$proposal.candidate_id
    sandbox_root = "examples/sandbox"
    bundle_path = Get-RepoRelativePath -AbsolutePath $manifestAbs
    included_artifacts = @($includedArtifacts)
    copied_artifact_paths = @($copiedArtifactPaths)
    artifact_sha256 = $artifactSha
    safety_summary = "Sandbox-only product-resolution proposal bundle export. Copies JSON evidence snapshots only and does not copy source assets, binaries, Cache files, AP outputs, model weights, or runtime outputs."
    explicit_non_admissions = @($explicitNonAdmissions)
    created_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

Write-JsonFile -InputObject $manifest -OutputPath $manifestAbs
$manifest | ConvertTo-Json -Depth 100
