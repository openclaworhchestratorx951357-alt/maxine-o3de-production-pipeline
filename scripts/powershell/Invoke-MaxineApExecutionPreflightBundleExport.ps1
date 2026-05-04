[CmdletBinding()]
param(
    [string]$PreflightPath,
    [string]$PreflightId,

    [string]$PreflightsRoot = "examples/sandbox/ap-execution-preflights",
    [string]$ApEvidenceImportsRoot = "examples/sandbox/ap-evidence-imports",
    [string]$ProposalsRoot = "examples/sandbox/product-resolution-proposals",
    [string]$ProjectInventoryRoot = "examples/sandbox/project-inventory",
    [string]$PreflightBundlesRoot = "examples/sandbox/ap-execution-preflight-bundles",
    [string]$BundlePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$fallbackNonAdmissions = @(
    "authoritative_writes",
    "asset_processor_execution",
    "o3de_editor_execution",
    "o3de_cli_execution",
    "cache_read",
    "live_asset_database_read",
    "product_resolution",
    "product_resolution_as_fact",
    "product_id_claims",
    "asset_id_claims",
    "source_uuid_claims",
    "spawning",
    "publishing",
    "production_path_write",
    "cache_path_write",
    "engine_path_write"
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

function Resolve-Preflight {
    param(
        [string]$PreflightPath,
        [string]$PreflightId,
        [string]$RootAbs
    )

    $hasPath = -not [string]::IsNullOrWhiteSpace($PreflightPath)
    $hasId = -not [string]::IsNullOrWhiteSpace($PreflightId)
    if (($hasPath -and $hasId) -or (-not $hasPath -and -not $hasId)) {
        throw "Provide either preflight_path or preflight_id."
    }

    if ($hasPath) {
        $pathAbs = $null
        if ([System.IO.Path]::IsPathRooted($PreflightPath)) {
            $pathAbs = [System.IO.Path]::GetFullPath($PreflightPath)
            if (-not (Test-IsPathWithin -CandidatePath $pathAbs -ParentPath $RootAbs)) {
                throw "preflight_path must remain under ap-execution-preflights."
            }
        } else {
            $pathAbs = Get-SafeRelativePathAbs -RelativePath $PreflightPath -AllowedRootAbs $RootAbs -Label "preflight_path"
        }

        if (-not (Test-Path -LiteralPath $pathAbs -PathType Leaf)) {
            throw "preflight_path not found: $PreflightPath"
        }

        $item = Get-Content -LiteralPath $pathAbs -Raw | ConvertFrom-Json
        return [ordered]@{ path = $pathAbs; item = $item }
    }

    $match = Resolve-JsonById -RootAbs $RootAbs -IdProperty "preflight_id" -IdValue $PreflightId
    if ($null -eq $match) {
        throw "preflight_id '$PreflightId' not found."
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

$preflightsRootAbs = Get-SafeRelativePathAbs -RelativePath $PreflightsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "preflights_root"
$importsRootAbs = Get-SafeRelativePathAbs -RelativePath $ApEvidenceImportsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "ap_evidence_imports_root"
$proposalsRootAbs = Get-SafeRelativePathAbs -RelativePath $ProposalsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "proposals_root"
$projectInventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $ProjectInventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "project_inventory_root"
$bundlesRootAbs = Get-SafeRelativePathAbs -RelativePath $PreflightBundlesRoot -AllowedRootAbs $sandboxAnchorAbs -Label "preflight_bundles_root"
if (-not (Test-Path -LiteralPath $bundlesRootAbs -PathType Container)) {
    New-Item -Path $bundlesRootAbs -ItemType Directory -Force | Out-Null
}

$preflightRef = Resolve-Preflight -PreflightPath $PreflightPath -PreflightId $PreflightId -RootAbs $preflightsRootAbs
$preflight = $preflightRef.item

if ([string]::IsNullOrWhiteSpace([string]$preflight.preflight_id)) {
    throw "preflight is missing preflight_id."
}
if ([string]$preflight.sandbox_root -ne "examples/sandbox") {
    throw "preflight sandbox_root must be examples/sandbox."
}

$importRef = Resolve-JsonById -RootAbs $importsRootAbs -IdProperty "ap_evidence_import_id" -IdValue ([string]$preflight.source_ap_evidence_import_id)
if ($null -eq $importRef) {
    throw "source AP evidence import not found for preflight."
}
$proposalRef = Resolve-JsonById -RootAbs $proposalsRootAbs -IdProperty "proposal_id" -IdValue ([string]$preflight.source_proposal_id)
if ($null -eq $proposalRef) {
    throw "source proposal not found for preflight."
}
$projectRef = Resolve-JsonById -RootAbs $projectInventoryRootAbs -IdProperty "inventory_id" -IdValue ([string]$preflight.source_project_inventory_id)

$bundleId = "ap-execution-preflight-bundle-$([Guid]::NewGuid().ToString('N'))"
$manifestRel = $BundlePath
if ([string]::IsNullOrWhiteSpace($manifestRel)) {
    $manifestRel = "$PreflightBundlesRoot/$bundleId/bundle.manifest.json"
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

Add-Snapshot -InputObject $preflight -SnapshotName "ap-execution-preflight.snapshot.json" -ArtifactLabel "ap_execution_preflight"
Add-Snapshot -InputObject $importRef.item -SnapshotName "ap-evidence-import.snapshot.json" -ArtifactLabel "ap_evidence_import"
Add-Snapshot -InputObject $proposalRef.item -SnapshotName "product-resolution-proposal.snapshot.json" -ArtifactLabel "product_resolution_proposal"
if ($null -ne $projectRef) {
    Add-Snapshot -InputObject $projectRef.item -SnapshotName "project-inventory.snapshot.json" -ArtifactLabel "project_inventory"
}

$linkSummary = [ordered]@{
    source_preflight_id = [string]$preflight.preflight_id
    source_ap_evidence_import_id = [string]$preflight.source_ap_evidence_import_id
    source_proposal_id = [string]$preflight.source_proposal_id
    source_project_inventory_id = [string]$preflight.source_project_inventory_id
    readiness_status = [string]$preflight.readiness_status
    execution_admitted = [bool]$preflight.execution_admitted
    required_manual_confirmation = [bool]$preflight.required_manual_confirmation
    local_only = [bool]$preflight.local_only
}
Add-Snapshot -InputObject $linkSummary -SnapshotName "preflight-link-summary.snapshot.json" -ArtifactLabel "ap_execution_preflight_link_summary"

$explicitNonAdmissions = @($preflight.explicit_non_admissions)
if ($explicitNonAdmissions.Count -eq 0) {
    $explicitNonAdmissions = @($fallbackNonAdmissions)
}

$manifest = [ordered]@{
    schema_version = "1.0.0"
    bundle_id = $bundleId
    source_preflight_id = [string]$preflight.preflight_id
    source_ap_evidence_import_id = [string]$preflight.source_ap_evidence_import_id
    source_proposal_id = [string]$preflight.source_proposal_id
    source_project_inventory_id = [string]$preflight.source_project_inventory_id
    sandbox_root = "examples/sandbox"
    bundle_path = Get-RepoRelativePath -AbsolutePath $manifestAbs
    included_artifacts = @($includedArtifacts)
    copied_artifact_paths = @($copiedArtifactPaths)
    artifact_sha256 = $artifactSha
    safety_summary = "Sandbox-only AP execution preflight bundle export. Copies JSON snapshots only and does not copy source assets, binaries, cache files, database files, runtime outputs, or model weights."
    explicit_non_admissions = @($explicitNonAdmissions)
    created_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

Write-JsonFile -InputObject $manifest -OutputPath $manifestAbs
$manifest | ConvertTo-Json -Depth 100
