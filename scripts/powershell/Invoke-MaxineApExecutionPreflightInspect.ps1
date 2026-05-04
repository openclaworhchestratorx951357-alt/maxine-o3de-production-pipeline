[CmdletBinding()]
param(
    [switch]$List,
    [string]$PreflightId,
    [string]$PreflightPath,
    [switch]$ShowBlockingReasons,
    [switch]$ShowWarnings,
    [string]$PreflightsRoot = "examples/sandbox/ap-execution-preflights"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

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

function Get-PreflightSummary {
    param([Parameter(Mandatory = $true)][object]$Item)

    return [ordered]@{
        preflight_id = [string]$Item.preflight_id
        source_ap_evidence_import_id = [string]$Item.source_ap_evidence_import_id
        source_proposal_id = [string]$Item.source_proposal_id
        source_project_inventory_id = [string]$Item.source_project_inventory_id
        readiness_status = [string]$Item.readiness_status
        execution_admitted = [bool]$Item.execution_admitted
        ready_for_future_execution_request = [bool]$Item.ready_for_future_execution_request
        output_path = [string]$Item.output_path
        created_utc = [string]$Item.created_utc
    }
}

$preflightsRootAbs = Get-SafeRelativePathAbs -RelativePath $PreflightsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "preflights_root"
if (-not (Test-Path -LiteralPath $preflightsRootAbs -PathType Container)) {
    throw "preflights root not found: $PreflightsRoot"
}

if (-not $List -and [string]::IsNullOrWhiteSpace($PreflightId) -and [string]::IsNullOrWhiteSpace($PreflightPath)) {
    $List = $true
}

if ($List -and (-not [string]::IsNullOrWhiteSpace($PreflightId) -or -not [string]::IsNullOrWhiteSpace($PreflightPath))) {
    throw "Provide either -List, -PreflightId, or -PreflightPath."
}
if (-not [string]::IsNullOrWhiteSpace($PreflightId) -and -not [string]::IsNullOrWhiteSpace($PreflightPath)) {
    throw "Provide either -PreflightId or -PreflightPath, not both."
}

$refs = @()
foreach ($file in Get-ChildItem -LiteralPath $preflightsRootAbs -File -Filter *.json -ErrorAction SilentlyContinue) {
    try {
        $obj = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
        $refs += [ordered]@{ path = $file.FullName; item = $obj }
    } catch {
        continue
    }
}

if ($List) {
    [ordered]@{
        preflight_count = $refs.Count
        preflights = @($refs | ForEach-Object { Get-PreflightSummary -Item $_.item })
    } | ConvertTo-Json -Depth 100
    exit 0
}

$selected = $null
if (-not [string]::IsNullOrWhiteSpace($PreflightPath)) {
    $targetAbs = $null
    if ([System.IO.Path]::IsPathRooted($PreflightPath)) {
        $targetAbs = [System.IO.Path]::GetFullPath($PreflightPath)
        if (-not (Test-IsPathWithin -CandidatePath $targetAbs -ParentPath $preflightsRootAbs)) {
            throw "preflight_path must remain under ap-execution-preflights."
        }
    } else {
        $targetAbs = Get-SafeRelativePathAbs -RelativePath $PreflightPath -AllowedRootAbs $preflightsRootAbs -Label "preflight_path"
    }

    if (-not (Test-Path -LiteralPath $targetAbs -PathType Leaf)) {
        throw "preflight_path not found: $PreflightPath"
    }
    $selected = Get-Content -LiteralPath $targetAbs -Raw | ConvertFrom-Json
} else {
    $match = $refs | Where-Object { [string]$_.item.preflight_id -eq $PreflightId } | Select-Object -First 1
    if (-not $match) {
        throw "preflight_id '$PreflightId' not found."
    }
    $selected = $match.item
}

if ($ShowBlockingReasons -or $ShowWarnings) {
    $selected | ConvertTo-Json -Depth 100
} else {
    Get-PreflightSummary -Item $selected | ConvertTo-Json -Depth 100
}
