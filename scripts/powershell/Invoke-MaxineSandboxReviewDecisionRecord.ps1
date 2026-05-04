[CmdletBinding()]
param(
    [string]$ReviewPacketPath,
    [string]$ReviewPacketId,

    [Parameter(Mandatory = $true)]
    [string]$DecisionState,

    [Parameter(Mandatory = $true)]
    [string]$OperatorId,

    [Parameter(Mandatory = $true)]
    [string]$DecisionReason,

    [string]$RequestedNextAction,
    [string]$ReviewPacketsRoot = "examples/sandbox/review-packets",
    [string]$DecisionsRoot = "examples/sandbox/review-decisions",
    [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$allowedDecisionStates = @(
    "accepted_for_sandbox_only",
    "request_rollback",
    "rejected",
    "needs_more_evidence"
)
$forbiddenDecisionStates = @(
    "approve_authoritative_write",
    "approve_asset_id_claim",
    "approve_product_resolution",
    "approve_spawn",
    "approve_publish",
    "approve_o3de_execution",
    "approve_asset_processor_execution"
)

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

    $json = $InputObject | ConvertTo-Json -Depth 50
    [System.IO.File]::WriteAllText($OutputPath, $json, [System.Text.UTF8Encoding]::new($false))
}

if ($forbiddenDecisionStates -contains $DecisionState) {
    throw "decision_state '$DecisionState' is forbidden."
}
if ($allowedDecisionStates -notcontains $DecisionState) {
    throw "decision_state '$DecisionState' is invalid."
}

if ([string]::IsNullOrWhiteSpace($OperatorId)) {
    throw "operator_id is required."
}
if ([string]::IsNullOrWhiteSpace($DecisionReason)) {
    throw "decision_reason is required."
}

$hasPacketPath = -not [string]::IsNullOrWhiteSpace($ReviewPacketPath)
$hasPacketId = -not [string]::IsNullOrWhiteSpace($ReviewPacketId)
if (($hasPacketPath -and $hasPacketId) -or (-not $hasPacketPath -and -not $hasPacketId)) {
    throw "Provide either review_packet_path or review_packet_id."
}

$reviewPacketsRootAbs = Get-SafeRelativePathAbs -RelativePath $ReviewPacketsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "review_packets_root"
$decisionsRootAbs = Get-SafeRelativePathAbs -RelativePath $DecisionsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "decisions_root"

$packetAbs = $null
if ($hasPacketPath) {
    $resolvedPacketPath = (Resolve-Path -LiteralPath $ReviewPacketPath).Path
    $packetAbs = [System.IO.Path]::GetFullPath($resolvedPacketPath)
    if (-not (Test-IsPathWithin -CandidatePath $packetAbs -ParentPath $sandboxAnchorAbs)) {
        throw "review packet path must remain within sandbox root."
    }
} else {
    if (-not (Test-Path -LiteralPath $reviewPacketsRootAbs -PathType Container)) {
        throw "review packets root not found: $ReviewPacketsRoot"
    }

    $matches = @()
    foreach ($file in Get-ChildItem -LiteralPath $reviewPacketsRootAbs -File -Filter *.json) {
        $candidate = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
        if ($candidate.review_packet_id -eq $ReviewPacketId) {
            $matches += $file.FullName
        }
    }

    if ($matches.Count -eq 0) {
        throw "review_packet_id '$ReviewPacketId' not found."
    }
    if ($matches.Count -gt 1) {
        throw "review_packet_id '$ReviewPacketId' is ambiguous."
    }

    $packetAbs = [System.IO.Path]::GetFullPath($matches[0])
}

if (-not (Test-Path -LiteralPath $packetAbs -PathType Leaf)) {
    throw "review packet not found."
}
if (-not (Test-IsPathWithin -CandidatePath $packetAbs -ParentPath $reviewPacketsRootAbs)) {
    throw "review packet must be under review packets root."
}

$packet = Get-Content -LiteralPath $packetAbs -Raw | ConvertFrom-Json

if ([string]::IsNullOrWhiteSpace([string]$packet.review_packet_id)) {
    throw "review packet is missing review_packet_id."
}
if ([string]::IsNullOrWhiteSpace([string]$packet.source_receipt_id)) {
    throw "review packet is missing source_receipt_id."
}
if ([string]::IsNullOrWhiteSpace([string]$packet.sandbox_root)) {
    throw "review packet is missing sandbox_root."
}
if ([string]$packet.sandbox_root -ne "examples/sandbox") {
    throw "review packet sandbox_root must be examples/sandbox."
}

$decisionId = "sandbox-review-decision-$([Guid]::NewGuid().ToString('N'))"
$nextAction = $RequestedNextAction
if ([string]::IsNullOrWhiteSpace($nextAction)) {
    $nextAction = "none"
}
$rollbackExecutionAdmitted = $false
if ($DecisionState -eq "request_rollback") {
    $nextAction = "rollback_requested"
    $rollbackExecutionAdmitted = $false
}

$outputRel = $OutputPath
if ([string]::IsNullOrWhiteSpace($outputRel)) {
    $outputRel = "$DecisionsRoot/$decisionId.json"
}
$outputAbs = Get-SafeRelativePathAbs -RelativePath $outputRel -AllowedRootAbs $decisionsRootAbs -Label "decision_path"

$decision = [ordered]@{
    schema_version = "1.0.0"
    decision_id = $decisionId
    source_review_packet_id = [string]$packet.review_packet_id
    source_receipt_id = [string]$packet.source_receipt_id
    decision_state = $DecisionState
    operator_id = $OperatorId
    decision_reason = $DecisionReason
    requested_next_action = $nextAction
    rollback_execution_admitted = $rollbackExecutionAdmitted
    sandbox_root = "examples/sandbox"
    decision_path = Get-RepoRelativePath -AbsolutePath $outputAbs
    explicit_non_admissions = @($explicitNonAdmissions)
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

Write-JsonFile -InputObject $decision -OutputPath $outputAbs
Write-Host "Decision record: $outputAbs"
