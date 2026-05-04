[CmdletBinding()]
param(
    [switch]$List,
    [string]$ProposalId,
    [string]$ProposalPath,
    [switch]$ShowRequirements,
    [switch]$ShowBlockingReasons,
    [string]$ProposalsRoot = "examples/sandbox/product-resolution-proposals"
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

function Get-ProposalSummary {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Proposal
    )

    return [ordered]@{
        proposal_id = [string]$Proposal.proposal_id
        source_review_packet_id = [string]$Proposal.source_review_packet_id
        source_inventory_id = [string]$Proposal.source_inventory_id
        source_project_inventory_id = [string]$Proposal.source_project_inventory_id
        candidate_id = [string]$Proposal.candidate_id
        proposal_status = [string]$Proposal.proposal_status
        expected_product_classes = @($Proposal.expected_product_classes)
        output_path = [string]$Proposal.output_path
        created_utc = [string]$Proposal.created_utc
    }
}

$proposalsRootAbs = Get-SafeRelativePathAbs -RelativePath $ProposalsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "proposals_root"
if (-not (Test-Path -LiteralPath $proposalsRootAbs -PathType Container)) {
    throw "proposals root not found: $ProposalsRoot"
}

if (-not $List -and [string]::IsNullOrWhiteSpace($ProposalId) -and [string]::IsNullOrWhiteSpace($ProposalPath)) {
    $List = $true
}

if ($List -and (-not [string]::IsNullOrWhiteSpace($ProposalId) -or -not [string]::IsNullOrWhiteSpace($ProposalPath))) {
    throw "Provide either -List, -ProposalId, or -ProposalPath."
}
if (-not [string]::IsNullOrWhiteSpace($ProposalId) -and -not [string]::IsNullOrWhiteSpace($ProposalPath)) {
    throw "Provide either -ProposalId or -ProposalPath, not both."
}

$proposalRefs = @()
foreach ($file in Get-ChildItem -LiteralPath $proposalsRootAbs -File -Filter *.json -ErrorAction SilentlyContinue) {
    try {
        $obj = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
        $proposalRefs += [ordered]@{
            path = $file.FullName
            item = $obj
        }
    } catch {
        continue
    }
}

if ($List) {
    $summary = @($proposalRefs | ForEach-Object { Get-ProposalSummary -Proposal $_.item })
    [ordered]@{
        proposal_count = $summary.Count
        proposals = $summary
    } | ConvertTo-Json -Depth 100
    exit 0
}

$selected = $null
if (-not [string]::IsNullOrWhiteSpace($ProposalPath)) {
    $proposalAbs = $null
    if ([System.IO.Path]::IsPathRooted($ProposalPath)) {
        $proposalAbs = [System.IO.Path]::GetFullPath($ProposalPath)
        if (-not (Test-IsPathWithin -CandidatePath $proposalAbs -ParentPath $proposalsRootAbs)) {
            throw "proposal_path must remain under product-resolution-proposals."
        }
    } else {
        $proposalAbs = Get-SafeRelativePathAbs -RelativePath $ProposalPath -AllowedRootAbs $proposalsRootAbs -Label "proposal_path"
    }

    if (-not (Test-Path -LiteralPath $proposalAbs -PathType Leaf)) {
        throw "proposal_path not found: $ProposalPath"
    }

    $selected = Get-Content -LiteralPath $proposalAbs -Raw | ConvertFrom-Json
} else {
    $match = $proposalRefs | Where-Object { [string]$_.item.proposal_id -eq $ProposalId } | Select-Object -First 1
    if (-not $match) {
        throw "proposal_id '$ProposalId' not found."
    }
    $selected = $match.item
}

if ($ShowRequirements -or $ShowBlockingReasons) {
    $selected | ConvertTo-Json -Depth 100
} else {
    Get-ProposalSummary -Proposal $selected | ConvertTo-Json -Depth 100
}
