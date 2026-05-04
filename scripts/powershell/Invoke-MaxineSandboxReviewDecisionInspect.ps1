[CmdletBinding()]
param(
    [switch]$List,
    [string]$DecisionId,
    [string]$DecisionsRoot = "examples/sandbox/review-decisions"
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

$decisionsRootAbs = Get-SafeRelativePathAbs -RelativePath $DecisionsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "decisions_root"
if (-not (Test-Path -LiteralPath $decisionsRootAbs -PathType Container)) {
    throw "review decisions root not found: $DecisionsRoot"
}

if (-not $List -and [string]::IsNullOrWhiteSpace($DecisionId)) {
    $List = $true
}
if ($List -and -not [string]::IsNullOrWhiteSpace($DecisionId)) {
    throw "Provide either -List or -DecisionId, not both."
}

$decisionFiles = Get-ChildItem -LiteralPath $decisionsRootAbs -File -Filter *.json
$decisions = @()
foreach ($file in $decisionFiles) {
    $decisions += (Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json)
}

if ($List) {
    $summary = foreach ($decision in $decisions) {
        [ordered]@{
            decision_id = [string]$decision.decision_id
            source_review_packet_id = [string]$decision.source_review_packet_id
            source_receipt_id = [string]$decision.source_receipt_id
            decision_state = [string]$decision.decision_state
            operator_id = [string]$decision.operator_id
            requested_next_action = $decision.requested_next_action
            rollback_execution_admitted = $decision.rollback_execution_admitted
            timestamp_utc = [string]$decision.timestamp_utc
        }
    }

    [ordered]@{
        decision_count = @($summary).Count
        decisions = @($summary)
    } | ConvertTo-Json -Depth 50

    exit 0
}

$match = $decisions | Where-Object { $_.decision_id -eq $DecisionId } | Select-Object -First 1
if (-not $match) {
    throw "decision_id '$DecisionId' not found."
}

$match | ConvertTo-Json -Depth 50
