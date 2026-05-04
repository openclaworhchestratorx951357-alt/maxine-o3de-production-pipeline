[CmdletBinding()]
param(
    [string]$EvidenceImportPath,
    [string]$EvidenceImportId,

    [string]$ApEvidenceImportsRoot = "examples/sandbox/ap-evidence-imports",
    [string]$ProposalsRoot = "examples/sandbox/product-resolution-proposals",
    [string]$ProjectInventoryRoot = "examples/sandbox/project-inventory",
    [string]$AssetCandidateInventoryRoot = "examples/sandbox/asset-candidates",
    [string]$ApEvidenceBundlesRoot = "examples/sandbox/ap-evidence-bundles",
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
    "product_id_claims",
    "asset_id_claims",
    "source_uuid_claims",
    "asset_processor_execution",
    "o3de_editor_execution",
    "o3de_cli_execution",
    "cache_read",
    "live_asset_database_read",
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
    param([Parameter(Mandatory = $true)][string]$AbsolutePath)

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
                $matches += [ordered]@{ path = $file.FullName; item = $item }
            }
        } catch {
            continue
        }
    }

    if ($matches.Count -eq 0) { return $null }
    if ($matches.Count -gt 1) { throw "$IdProperty '$IdValue' is ambiguous." }

    return $matches[0]
}

function Resolve-Import {
    param(
        [string]$EvidenceImportPath,
        [string]$EvidenceImportId,
        [string]$RootAbs
    )

    $hasPath = -not [string]::IsNullOrWhiteSpace($EvidenceImportPath)
    $hasId = -not [string]::IsNullOrWhiteSpace($EvidenceImportId)
    if (($hasPath -and $hasId) -or (-not $hasPath -and -not $hasId)) {
        throw "Provide either evidence_import_path or evidence_import_id."
    }

    if ($hasPath) {
        $pathAbs = $null
        if ([System.IO.Path]::IsPathRooted($EvidenceImportPath)) {
            $pathAbs = [System.IO.Path]::GetFullPath($EvidenceImportPath)
            if (-not (Test-IsPathWithin -CandidatePath $pathAbs -ParentPath $RootAbs)) {
                throw "evidence_import_path must remain under ap-evidence-imports."
            }
        } else {
            $pathAbs = Get-SafeRelativePathAbs -RelativePath $EvidenceImportPath -AllowedRootAbs $RootAbs -Label "evidence_import_path"
        }

        if (-not (Test-Path -LiteralPath $pathAbs -PathType Leaf)) {
            throw "evidence_import_path not found: $EvidenceImportPath"
        }
        $item = Get-Content -LiteralPath $pathAbs -Raw | ConvertFrom-Json
        return [ordered]@{ path = $pathAbs; item = $item }
    }

    $match = Resolve-JsonById -RootAbs $RootAbs -IdProperty "ap_evidence_import_id" -IdValue $EvidenceImportId
    if ($null -eq $match) {
        throw "evidence_import_id '$EvidenceImportId' not found."
    }
    return $match
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)][object]$InputObject,
        [Parameter(Mandatory = $true)][string]$OutputPath
    )

    $directory = Split-Path -Parent $OutputPath
    if ($directory -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -Path $directory -ItemType Directory -Force | Out-Null
    }

    $json = $InputObject | ConvertTo-Json -Depth 100
    [System.IO.File]::WriteAllText($OutputPath, $json, [System.Text.UTF8Encoding]::new($false))
}

$importsRootAbs = Get-SafeRelativePathAbs -RelativePath $ApEvidenceImportsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "ap_evidence_imports_root"
$proposalsRootAbs = Get-SafeRelativePathAbs -RelativePath $ProposalsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "proposals_root"
$projectInventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $ProjectInventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "project_inventory_root"
$assetInventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $AssetCandidateInventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "asset_candidate_inventory_root"
$bundlesRootAbs = Get-SafeRelativePathAbs -RelativePath $ApEvidenceBundlesRoot -AllowedRootAbs $sandboxAnchorAbs -Label "ap_evidence_bundles_root"
if (-not (Test-Path -LiteralPath $bundlesRootAbs -PathType Container)) {
    New-Item -Path $bundlesRootAbs -ItemType Directory -Force | Out-Null
}

$importRef = Resolve-Import -EvidenceImportPath $EvidenceImportPath -EvidenceImportId $EvidenceImportId -RootAbs $importsRootAbs
$importItem = $importRef.item

if ([string]::IsNullOrWhiteSpace([string]$importItem.ap_evidence_import_id)) {
    throw "AP evidence import is missing ap_evidence_import_id."
}
if ([string]$importItem.sandbox_root -ne "examples/sandbox") {
    throw "AP evidence import sandbox_root must be examples/sandbox."
}

$proposalRef = Resolve-JsonById -RootAbs $proposalsRootAbs -IdProperty "proposal_id" -IdValue ([string]$importItem.source_proposal_id)
$projectRef = Resolve-JsonById -RootAbs $projectInventoryRootAbs -IdProperty "inventory_id" -IdValue ([string]$importItem.source_project_inventory_id)
$assetRef = Resolve-JsonById -RootAbs $assetInventoryRootAbs -IdProperty "inventory_id" -IdValue ([string]$importItem.source_asset_candidate_inventory_id)

$bundleId = "ap-evidence-bundle-$([Guid]::NewGuid().ToString('N'))"
$manifestRel = $BundlePath
if ([string]::IsNullOrWhiteSpace($manifestRel)) {
    $manifestRel = "$ApEvidenceBundlesRoot/$bundleId/bundle.manifest.json"
} elseif (-not $manifestRel.ToLowerInvariant().EndsWith(".json")) {
    $manifestRel = $manifestRel.TrimEnd("/", "\") + "/bundle.manifest.json"
}

$manifestAbs = Get-SafeRelativePathAbs -RelativePath $manifestRel -AllowedRootAbs $bundlesRootAbs -Label "bundle_path"
$bundleDirAbs = Split-Path -Parent $manifestAbs
if (-not (Test-Path -LiteralPath $bundleDirAbs -PathType Container)) {
    New-Item -Path $bundleDirAbs -ItemType Directory -Force | Out-Null
}

$includedArtifacts = New-Object System.Collections.Generic.List[string]
$copiedArtifactPaths = New-Object System.Collections.Generic.List[string]
$artifactSha = [ordered]@{}

function Add-Snapshot {
    param(
        [Parameter(Mandatory = $true)][object]$InputObject,
        [Parameter(Mandatory = $true)][string]$SnapshotName,
        [Parameter(Mandatory = $true)][string]$ArtifactLabel
    )

    $snapshotAbs = Join-Path $bundleDirAbs $SnapshotName
    Write-JsonFile -InputObject $InputObject -OutputPath $snapshotAbs

    $snapshotRel = Get-RepoRelativePath -AbsolutePath $snapshotAbs
    $includedArtifacts.Add($ArtifactLabel) | Out-Null
    $copiedArtifactPaths.Add($snapshotRel) | Out-Null
    $artifactSha[$snapshotRel] = (Get-FileHash -LiteralPath $snapshotAbs -Algorithm SHA256).Hash
}

Add-Snapshot -InputObject $importItem -SnapshotName "ap-evidence-import.snapshot.json" -ArtifactLabel "ap_evidence_import"
if ($null -ne $proposalRef) {
    Add-Snapshot -InputObject $proposalRef.item -SnapshotName "product-resolution-proposal.snapshot.json" -ArtifactLabel "product_resolution_proposal"
}
if ($null -ne $projectRef) {
    Add-Snapshot -InputObject $projectRef.item -SnapshotName "project-inventory.snapshot.json" -ArtifactLabel "project_inventory"
}
if ($null -ne $assetRef) {
    Add-Snapshot -InputObject $assetRef.item -SnapshotName "asset-candidate-inventory.snapshot.json" -ArtifactLabel "asset_candidate_inventory"
}

$linkSummary = [ordered]@{
    source_ap_evidence_import_id = [string]$importItem.ap_evidence_import_id
    source_proposal_id = [string]$importItem.source_proposal_id
    source_project_inventory_id = [string]$importItem.source_project_inventory_id
    source_asset_candidate_inventory_id = [string]$importItem.source_asset_candidate_inventory_id
    evidence_quality = [string]$importItem.evidence_quality
    observed_asset_processor_state = [string]$importItem.observed_asset_processor_state
}
Add-Snapshot -InputObject $linkSummary -SnapshotName "ap-evidence-link-summary.snapshot.json" -ArtifactLabel "ap_evidence_link_summary"

$explicitNonAdmissions = @($importItem.explicit_non_admissions)
if ($explicitNonAdmissions.Count -eq 0) {
    $explicitNonAdmissions = @($fallbackNonAdmissions)
}

$manifest = [ordered]@{
    schema_version = "1.0.0"
    bundle_id = $bundleId
    source_ap_evidence_import_id = [string]$importItem.ap_evidence_import_id
    source_proposal_id = [string]$importItem.source_proposal_id
    source_project_inventory_id = [string]$importItem.source_project_inventory_id
    source_asset_candidate_inventory_id = [string]$importItem.source_asset_candidate_inventory_id
    sandbox_root = "examples/sandbox"
    bundle_path = Get-RepoRelativePath -AbsolutePath $manifestAbs
    included_artifacts = @($includedArtifacts)
    copied_artifact_paths = @($copiedArtifactPaths)
    artifact_sha256 = $artifactSha
    safety_summary = "Sandbox-only AP evidence bundle export. Copies JSON snapshots only and does not copy logs directly, cache files, database files, source assets, binaries, runtime outputs, AP outputs, or model weights."
    explicit_non_admissions = @($explicitNonAdmissions)
    created_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

Write-JsonFile -InputObject $manifest -OutputPath $manifestAbs
$manifest | ConvertTo-Json -Depth 100
