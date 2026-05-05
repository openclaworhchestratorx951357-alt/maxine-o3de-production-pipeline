[CmdletBinding()]
param(
    [switch]$List,
    [string]$DiscoveryId,
    [string]$DiscoveryPath,
    [switch]$ShowCandidates,
    [switch]$ShowRejected,
    [string]$DiscoveryRoot = "examples/sandbox/ap-binary-discovery"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

function Test-IsPathWithin {
    param(
        [Parameter(Mandatory = $true)][string]$CandidatePath,
        [Parameter(Mandatory = $true)][string]$ParentPath
    )

    $candidateAbs = [System.IO.Path]::GetFullPath($CandidatePath)
    $parentAbs = [System.IO.Path]::GetFullPath($ParentPath)
    if ($candidateAbs.Equals($parentAbs, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }

    $prefix = $parentAbs.TrimEnd("\") + "\"
    return $candidateAbs.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-SafeRelativePathAbs {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$AllowedRootAbs,
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

function Get-DiscoverySummary {
    param([Parameter(Mandatory = $true)][object]$Item)

    return [ordered]@{
        discovery_id = [string]$Item.discovery_id
        path_source = [string]$Item.path_source
        normalized_candidate_count = @($Item.normalized_candidate_paths).Count
        existing_candidate_count = @($Item.existing_candidates).Count
        rejected_candidate_count = @($Item.rejected_candidates).Count
        output_path = [string]$Item.output_path
        created_utc = [string]$Item.created_utc
    }
}

$discoveryRootAbs = Get-SafeRelativePathAbs -RelativePath $DiscoveryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "discovery_root"
if (-not (Test-Path -LiteralPath $discoveryRootAbs -PathType Container)) {
    throw "discovery root not found: $DiscoveryRoot"
}

if (-not $List -and [string]::IsNullOrWhiteSpace($DiscoveryId) -and [string]::IsNullOrWhiteSpace($DiscoveryPath)) {
    $List = $true
}

if ($List -and (-not [string]::IsNullOrWhiteSpace($DiscoveryId) -or -not [string]::IsNullOrWhiteSpace($DiscoveryPath))) {
    throw "Provide either -List, -DiscoveryId, or -DiscoveryPath."
}
if (-not [string]::IsNullOrWhiteSpace($DiscoveryId) -and -not [string]::IsNullOrWhiteSpace($DiscoveryPath)) {
    throw "Provide either -DiscoveryId or -DiscoveryPath, not both."
}

$refs = @()
foreach ($file in Get-ChildItem -LiteralPath $discoveryRootAbs -File -Filter *.json -ErrorAction SilentlyContinue) {
    try {
        $obj = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
        $refs += [ordered]@{ path = $file.FullName; item = $obj }
    } catch {
        continue
    }
}

if ($List) {
    [ordered]@{
        discovery_count = $refs.Count
        discoveries = @($refs | ForEach-Object { Get-DiscoverySummary -Item $_.item })
    } | ConvertTo-Json -Depth 100
    exit 0
}

$selectedRef = $null
if (-not [string]::IsNullOrWhiteSpace($DiscoveryPath)) {
    $targetAbs = $null
    if ([System.IO.Path]::IsPathRooted($DiscoveryPath)) {
        $targetAbs = [System.IO.Path]::GetFullPath($DiscoveryPath)
        if (-not (Test-IsPathWithin -CandidatePath $targetAbs -ParentPath $discoveryRootAbs)) {
            throw "discovery_path must remain under ap-binary-discovery."
        }
    } else {
        $targetAbs = Get-SafeRelativePathAbs -RelativePath $DiscoveryPath -AllowedRootAbs $discoveryRootAbs -Label "discovery_path"
    }

    if (-not (Test-Path -LiteralPath $targetAbs -PathType Leaf)) {
        throw "discovery_path not found: $DiscoveryPath"
    }

    $selectedRef = [ordered]@{
        path = $targetAbs
        item = (Get-Content -LiteralPath $targetAbs -Raw | ConvertFrom-Json)
    }
} else {
    $match = $refs | Where-Object { [string]$_.item.discovery_id -eq $DiscoveryId }
    if (@($match).Count -eq 0) {
        throw "discovery_id '$DiscoveryId' not found."
    }
    if (@($match).Count -gt 1) {
        throw "discovery_id '$DiscoveryId' is ambiguous."
    }

    $selectedRef = $match | Select-Object -First 1
}

if ($ShowCandidates -or $ShowRejected) {
    $selectedRef.item | ConvertTo-Json -Depth 100
} else {
    Get-DiscoverySummary -Item $selectedRef.item | ConvertTo-Json -Depth 100
}