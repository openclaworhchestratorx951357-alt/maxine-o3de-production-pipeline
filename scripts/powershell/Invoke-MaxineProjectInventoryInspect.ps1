[CmdletBinding()]
param(
    [switch]$List,
    [string]$InventoryId,
    [string]$InventoryPath,
    [string]$InventoryRoot = "examples/sandbox/project-inventory"
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
    $summary = @($inventories | ForEach-Object {
        [ordered]@{
            inventory_id = [string]$_.item.inventory_id
            generated_at_utc = [string]$_.item.generated_at_utc
            project_root = [string]$_.item.project_root
            project_json_existing_count = $_.item.o3de_project_path_metadata.project_json_existing_count
            gem_count = @($_.item.gem_names).Count
            known_asset_folder_count = @($_.item.known_asset_folders).Count
            generated_asset_candidate_folder_count = @($_.item.generated_asset_candidate_folders).Count
            path = $_.item.inventory_path
        }
    })

    [ordered]@{
        inventory_count = @($summary).Count
        inventories = @($summary)
    } | ConvertTo-Json -Depth 50

    exit 0
}

if (-not [string]::IsNullOrWhiteSpace($InventoryPath)) {
    $inventoryAbs = Get-SafeRelativePathAbs -RelativePath $InventoryPath -AllowedRootAbs $inventoryRootAbs -Label "inventory_path"
    if (-not (Test-Path -LiteralPath $inventoryAbs -PathType Leaf)) {
        throw "inventory_path not found: $InventoryPath"
    }

    Get-Content -LiteralPath $inventoryAbs -Raw
    exit 0
}

$match = $inventories | Where-Object { [string]$_.item.inventory_id -eq $InventoryId } | Select-Object -First 1
if (-not $match) {
    throw "inventory_id '$InventoryId' not found."
}

$match.item | ConvertTo-Json -Depth 100
