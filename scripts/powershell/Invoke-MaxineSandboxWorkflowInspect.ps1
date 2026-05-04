[CmdletBinding()]
param(
    [switch]$List,
    [string]$WorkflowRunId,
    [string]$WorkflowRunsRoot = "examples/sandbox/workflow-runs"
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

$workflowRunsAbs = Get-SafeRelativePathAbs -RelativePath $WorkflowRunsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "workflow_runs_root"
if (-not (Test-Path -LiteralPath $workflowRunsAbs -PathType Container)) {
    throw "workflow runs root not found: $WorkflowRunsRoot"
}

if (-not $List -and [string]::IsNullOrWhiteSpace($WorkflowRunId)) {
    $List = $true
}
if ($List -and -not [string]::IsNullOrWhiteSpace($WorkflowRunId)) {
    throw "Provide either -List or -WorkflowRunId, not both."
}

$runFiles = Get-ChildItem -LiteralPath $workflowRunsAbs -File -Filter *.json
$runs = @()
foreach ($file in $runFiles) {
    $runs += (Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json)
}

if ($List) {
    $summary = foreach ($run in $runs) {
        [ordered]@{
            workflow_run_id = [string]$run.workflow_run_id
            workflow_mode = [string]$run.workflow_mode
            workflow_status = [string]$run.workflow_status
            receipt_id = $run.receipt_id
            review_packet_id = $run.review_packet_id
            decision_id = $run.decision_id
            blocked_reason = $run.blocked_reason
            explicit_non_admissions = @($run.explicit_non_admissions)
            completed_utc = [string]$run.completed_utc
        }
    }

    [ordered]@{
        workflow_run_count = @($summary).Count
        workflow_runs = @($summary)
    } | ConvertTo-Json -Depth 50

    exit 0
}

$match = $runs | Where-Object { $_.workflow_run_id -eq $WorkflowRunId } | Select-Object -First 1
if (-not $match) {
    throw "workflow_run_id '$WorkflowRunId' not found."
}

$match | ConvertTo-Json -Depth 50
