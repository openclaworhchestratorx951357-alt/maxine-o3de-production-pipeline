[CmdletBinding()]
param(
    [switch]$List,
    [string]$EvidenceImportId,
    [string]$EvidenceImportPath,
    [switch]$ShowWarnings,
    [switch]$ShowErrors,
    [switch]$ShowObservedMentions,
    [string]$ApEvidenceImportsRoot = "examples/sandbox/ap-evidence-imports"
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

function Get-EvidenceSummary {
    param([Parameter(Mandatory = $true)][object]$Item)

    return [ordered]@{
        ap_evidence_import_id = [string]$Item.ap_evidence_import_id
        source_proposal_id = [string]$Item.source_proposal_id
        source_project_inventory_id = [string]$Item.source_project_inventory_id
        source_asset_candidate_inventory_id = [string]$Item.source_asset_candidate_inventory_id
        evidence_quality = [string]$Item.evidence_quality
        observed_asset_processor_state = [string]$Item.observed_asset_processor_state
        output_path = [string]$Item.output_path
        created_utc = [string]$Item.created_utc
    }
}

$importsRootAbs = Get-SafeRelativePathAbs -RelativePath $ApEvidenceImportsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "ap_evidence_imports_root"
if (-not (Test-Path -LiteralPath $importsRootAbs -PathType Container)) {
    throw "AP evidence imports root not found: $ApEvidenceImportsRoot"
}

if (-not $List -and [string]::IsNullOrWhiteSpace($EvidenceImportId) -and [string]::IsNullOrWhiteSpace($EvidenceImportPath)) {
    $List = $true
}

if ($List -and (-not [string]::IsNullOrWhiteSpace($EvidenceImportId) -or -not [string]::IsNullOrWhiteSpace($EvidenceImportPath))) {
    throw "Provide either -List, -EvidenceImportId, or -EvidenceImportPath."
}
if (-not [string]::IsNullOrWhiteSpace($EvidenceImportId) -and -not [string]::IsNullOrWhiteSpace($EvidenceImportPath)) {
    throw "Provide either -EvidenceImportId or -EvidenceImportPath, not both."
}

$refs = @()
foreach ($file in Get-ChildItem -LiteralPath $importsRootAbs -File -Filter *.json -ErrorAction SilentlyContinue) {
    try {
        $obj = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
        $refs += [ordered]@{ path = $file.FullName; item = $obj }
    } catch {
        continue
    }
}

if ($List) {
    [ordered]@{
        evidence_import_count = $refs.Count
        evidence_imports = @($refs | ForEach-Object { Get-EvidenceSummary -Item $_.item })
    } | ConvertTo-Json -Depth 100
    exit 0
}

$selected = $null
if (-not [string]::IsNullOrWhiteSpace($EvidenceImportPath)) {
    $targetAbs = $null
    if ([System.IO.Path]::IsPathRooted($EvidenceImportPath)) {
        $targetAbs = [System.IO.Path]::GetFullPath($EvidenceImportPath)
        if (-not (Test-IsPathWithin -CandidatePath $targetAbs -ParentPath $importsRootAbs)) {
            throw "evidence_import_path must remain under ap-evidence-imports."
        }
    } else {
        $targetAbs = Get-SafeRelativePathAbs -RelativePath $EvidenceImportPath -AllowedRootAbs $importsRootAbs -Label "evidence_import_path"
    }

    if (-not (Test-Path -LiteralPath $targetAbs -PathType Leaf)) {
        throw "evidence_import_path not found: $EvidenceImportPath"
    }
    $selected = Get-Content -LiteralPath $targetAbs -Raw | ConvertFrom-Json
} else {
    $match = $refs | Where-Object { [string]$_.item.ap_evidence_import_id -eq $EvidenceImportId } | Select-Object -First 1
    if (-not $match) {
        throw "evidence_import_id '$EvidenceImportId' not found."
    }
    $selected = $match.item
}

if ($ShowWarnings -or $ShowErrors -or $ShowObservedMentions) {
    $selected | ConvertTo-Json -Depth 100
} else {
    Get-EvidenceSummary -Item $selected | ConvertTo-Json -Depth 100
}
