[CmdletBinding()]
param(
    [int]$LatestCount = 5,
    [switch]$WriteReport,
    [string]$ReportPath,
    [string]$WorkflowRunsRoot = "examples/sandbox/workflow-runs",
    [string]$ReviewPacketsRoot = "examples/sandbox/review-packets",
    [string]$DecisionsRoot = "examples/sandbox/review-decisions",
    [string]$EvidenceBundlesRoot = "examples/sandbox/evidence-bundles",
    [string]$ReportsRoot = "examples/sandbox/operator-reports"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$explicitNonAdmissions = @(
    "authoritative_writes",
    "o3de_editor_execution",
    "asset_processor_execution",
    "product_resolution",
    "asset_id_claims",
    "spawning",
    "publishing",
    "production_cache_engine_writes"
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
    param(
        [Parameter(Mandatory = $true)]
        [string]$AbsolutePath
    )

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

function Load-JsonFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootAbs
    )

    $items = @()
    if (-not (Test-Path -LiteralPath $RootAbs -PathType Container)) {
        return @()
    }

    foreach ($file in Get-ChildItem -LiteralPath $RootAbs -File -Filter *.json -Recurse) {
        try {
            $parsed = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
            $items += $parsed
        } catch {
            continue
        }
    }

    return $items
}

function Get-CountMap {
    param(
        [array]$Items = @(),
        [Parameter(Mandatory = $true)]
        [string]$PropertyName,
        [string]$DefaultKey = "unknown"
    )

    $counts = [ordered]@{}
    if ($null -eq $Items) {
        return $counts
    }
    foreach ($item in $Items) {
        $key = [string]$item.$PropertyName
        if ([string]::IsNullOrWhiteSpace($key)) {
            $key = $DefaultKey
        }
        if (-not $counts.Contains($key)) {
            $counts[$key] = 0
        }
        $counts[$key] = [int]$counts[$key] + 1
    }
    return $counts
}

function Get-SafeDateValue {
    param(
        [object]$Primary,
        [object]$Secondary
    )

    foreach ($candidate in @($Primary, $Secondary)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$candidate)) {
            try {
                return [DateTime]::Parse([string]$candidate)
            } catch {
                continue
            }
        }
    }

    return [DateTime]::MinValue
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath
    )

    $directory = Split-Path -Parent $OutputPath
    if ($directory -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -Path $directory -ItemType Directory -Force | Out-Null
    }

    $json = $InputObject | ConvertTo-Json -Depth 100
    [System.IO.File]::WriteAllText($OutputPath, $json, [System.Text.UTF8Encoding]::new($false))
}

if ($LatestCount -lt 1) {
    throw "latest_count must be >= 1."
}

$workflowRunsRootAbs = Get-SafeRelativePathAbs -RelativePath $WorkflowRunsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "workflow_runs_root"
$reviewPacketsRootAbs = Get-SafeRelativePathAbs -RelativePath $ReviewPacketsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "review_packets_root"
$decisionsRootAbs = Get-SafeRelativePathAbs -RelativePath $DecisionsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "decisions_root"
$evidenceBundlesRootAbs = Get-SafeRelativePathAbs -RelativePath $EvidenceBundlesRoot -AllowedRootAbs $sandboxAnchorAbs -Label "evidence_bundles_root"
$reportsRootAbs = Get-SafeRelativePathAbs -RelativePath $ReportsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "reports_root"

$workflowRuns = Load-JsonFiles -RootAbs $workflowRunsRootAbs
$reviewPackets = Load-JsonFiles -RootAbs $reviewPacketsRootAbs
$decisions = Load-JsonFiles -RootAbs $decisionsRootAbs
$allBundleJson = Load-JsonFiles -RootAbs $evidenceBundlesRootAbs
$bundles = @($allBundleJson | Where-Object {
    $props = @($_.PSObject.Properties.Name)
    ($props -contains "bundle_id") -and
    ($props -contains "source_workflow_run_id") -and
    (-not [string]::IsNullOrWhiteSpace([string]$_.bundle_id)) -and
    (-not [string]::IsNullOrWhiteSpace([string]$_.source_workflow_run_id))
})

$workflowStatusCounts = Get-CountMap -Items $workflowRuns -PropertyName "workflow_status"
$decisionCounts = Get-CountMap -Items $decisions -PropertyName "decision_state"

$pendingReviewPackets = @($reviewPackets | Where-Object {
    [string]$_.operator_decision_state -eq "pending_review"
}).Count

$rollbackRequestedDecisions = @($decisions | Where-Object {
    [string]$_.decision_state -eq "request_rollback" -or [string]$_.requested_next_action -eq "rollback_requested"
}).Count
$rejectedDecisions = @($decisions | Where-Object { [string]$_.decision_state -eq "rejected" }).Count
$acceptedDecisions = @($decisions | Where-Object { [string]$_.decision_state -eq "accepted_for_sandbox_only" }).Count

$blockedReasonCounts = [ordered]@{}
foreach ($run in $workflowRuns) {
    $reason = [string]$run.blocked_reason
    if ([string]::IsNullOrWhiteSpace($reason)) {
        continue
    }
    if (-not $blockedReasonCounts.Contains($reason)) {
        $blockedReasonCounts[$reason] = 0
    }
    $blockedReasonCounts[$reason] = [int]$blockedReasonCounts[$reason] + 1
}

$latestRuns = @($workflowRuns | Sort-Object {
    Get-SafeDateValue -Primary $_.completed_utc -Secondary $_.timestamp_utc
} -Descending | Select-Object -First $LatestCount | ForEach-Object {
    [ordered]@{
        workflow_run_id = [string]$_.workflow_run_id
        workflow_mode = [string]$_.workflow_mode
        workflow_status = [string]$_.workflow_status
        receipt_id = $_.receipt_id
        review_packet_id = $_.review_packet_id
        decision_id = $_.decision_id
        blocked_reason = $_.blocked_reason
        completed_utc = [string]$_.completed_utc
    }
})

$latestBundles = @($bundles | Sort-Object {
    Get-SafeDateValue -Primary $_.created_utc -Secondary $null
} -Descending | Select-Object -First $LatestCount | ForEach-Object {
    [ordered]@{
        bundle_id = [string]$_.bundle_id
        source_workflow_run_id = [string]$_.source_workflow_run_id
        source_receipt_id = $_.source_receipt_id
        source_review_packet_id = $_.source_review_packet_id
        source_decision_id = $_.source_decision_id
        bundle_path = $_.bundle_path
        created_utc = [string]$_.created_utc
    }
})

$nextSafestStep = "continue_sandbox_only_workflow"
if (@($workflowRuns | Where-Object { [string]$_.workflow_status -eq "blocked" }).Count -gt 0) {
    $nextSafestStep = "resolve_blocked_workflow_runs_then_retry_sandbox_only"
} elseif ($pendingReviewPackets -gt 0) {
    $nextSafestStep = "review_pending_review_packets"
} elseif ($rollbackRequestedDecisions -gt 0) {
    $nextSafestStep = "execute_sandbox_rollback_for_requested_decisions"
}

$summary = [ordered]@{
    schema_version = "1.0.0"
    sandbox_root = "examples/sandbox"
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    total_workflow_runs = @($workflowRuns).Count
    workflow_status_counts = $workflowStatusCounts
    latest_workflow_runs = $latestRuns
    pending_review_packets = $pendingReviewPackets
    decision_counts = $decisionCounts
    rollback_requested_decisions = $rollbackRequestedDecisions
    rejected_decisions = $rejectedDecisions
    accepted_for_sandbox_only_decisions = $acceptedDecisions
    blocked_reasons = $blockedReasonCounts
    latest_evidence_bundles = $latestBundles
    next_safest_step = $nextSafestStep
    explicit_non_admissions = @($explicitNonAdmissions)
}

# Write report is optional and only allowed with explicit -WriteReport.
if ($WriteReport) {
    $reportRel = $ReportPath
    if ([string]::IsNullOrWhiteSpace($reportRel)) {
        $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
        $reportRel = "$ReportsRoot/operator-summary-$stamp.json"
    }

    $reportAbs = Get-SafeRelativePathAbs -RelativePath $reportRel -AllowedRootAbs $reportsRootAbs -Label "report_path"
    Write-JsonFile -InputObject $summary -OutputPath $reportAbs
    $summary.report_path = Get-RepoRelativePath -AbsolutePath $reportAbs
}

$summary | ConvertTo-Json -Depth 100
