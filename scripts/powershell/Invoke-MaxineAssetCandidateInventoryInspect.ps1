[CmdletBinding()]
param(
    [switch]$List,
    [string]$InventoryId,
    [string]$InventoryPath,
    [switch]$ShowCandidates,
    [string]$InventoryRoot = "examples/sandbox/asset-candidates"
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

function Get-InventorySummary {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InventoryObject
    )

    $sourceCandidates = @($InventoryObject.source_asset_candidates)
    return [ordered]@{
        inventory_id = [string]$InventoryObject.inventory_id
        source_project_inventory_id = [string]$InventoryObject.source_project_inventory_id
        created_utc = [string]$InventoryObject.created_utc
        project_root = [string]$InventoryObject.project_root
        sandbox_root = [string]$InventoryObject.sandbox_root
        output_path = [string]$InventoryObject.output_path
        candidate_count = @($sourceCandidates).Count
        generated_candidate_folder_count = @($InventoryObject.generated_candidate_folders).Count
        scanned_root_count = @($InventoryObject.scanned_roots).Count
        warning_count = @($InventoryObject.warnings).Count
        linked_sandbox_evidence = $InventoryObject.linked_sandbox_evidence
    }
}

$inventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $InventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "inventory_root"
if (-not (Test-Path -LiteralPath $inventoryRootAbs -PathType Container)) {
    throw "inventory root not found: $InventoryRoot"
}

if (-not $List -and [string]::IsNullOrWhiteSpace($InventoryId) -and [string]::IsNullOrWhiteSpace($InventoryPath)) {
    $List = $true
}

if (($List -and -not [string]::IsNullOrWhiteSpace($InventoryId)) -or ($List -and -not [string]::IsNullOrWhiteSpace($InventoryPath))) {
    throw "Provide either -List, -InventoryId, or -InventoryPath."
}

if (-not [string]::IsNullOrWhiteSpace($InventoryId) -and -not [string]::IsNullOrWhiteSpace($InventoryPath)) {
    throw "Provide either -InventoryId or -InventoryPath, not both."
}

$inventories = @()
foreach ($file in Get-ChildItem -LiteralPath $inventoryRootAbs -File -Filter *.json -ErrorAction SilentlyContinue) {
    try {
        $obj = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
        $inventories += [ordered]@{
            path = $file.FullName
            item = $obj
        }
    } catch {
        continue
    }
}

if ($List) {
    $summary = @($inventories | ForEach-Object { Get-InventorySummary -InventoryObject $_.item })
    [ordered]@{
        inventory_count = @($summary).Count
        inventories = @($summary)
    } | ConvertTo-Json -Depth 100
    exit 0
}

if (-not [string]::IsNullOrWhiteSpace($InventoryPath)) {
    $inventoryAbs = Get-SafeRelativePathAbs -RelativePath $InventoryPath -AllowedRootAbs $inventoryRootAbs -Label "inventory_path"
    if (-not (Test-Path -LiteralPath $inventoryAbs -PathType Leaf)) {
        throw "inventory_path not found: $InventoryPath"
    }

    $payload = Get-Content -LiteralPath $inventoryAbs -Raw | ConvertFrom-Json
    if ($ShowCandidates) {
        $payload | ConvertTo-Json -Depth 100
    } else {
        Get-InventorySummary -InventoryObject $payload | ConvertTo-Json -Depth 100
    }
    exit 0
}

$match = $inventories | Where-Object { [string]$_.item.inventory_id -eq $InventoryId } | Select-Object -First 1
if (-not $match) {
    throw "inventory_id '$InventoryId' not found."
}

if ($ShowCandidates) {
    $match.item | ConvertTo-Json -Depth 100
} else {
    Get-InventorySummary -InventoryObject $match.item | ConvertTo-Json -Depth 100
}
