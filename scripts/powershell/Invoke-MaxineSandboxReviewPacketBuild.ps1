[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ReceiptPath,

    [string]$OutputPath,

    [string]$OperatorDecisionState = "pending_review"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))
$reviewPacketsRootRel = "examples/sandbox/review-packets"
$reviewPacketsRootAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox\review-packets"))

$allowedOperatorDecisionStates = @(
    "pending_review",
    "accepted_for_sandbox_only",
    "request_rollback",
    "rejected"
)
$forbiddenOperatorDecisionStates = @(
    "approve_authoritative_write",
    "approve_asset_id_claim",
    "approve_product_resolution",
    "approve_spawn",
    "approve_publish",
    "approve_o3de_execution",
    "approve_asset_processor_execution"
)

$blockedCapabilities = @(
    "authoritative_writes",
    "product_resolution",
    "asset_id_claims",
    "spawning",
    "publishing",
    "o3de_editor_execution",
    "asset_processor_execution",
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

if ($forbiddenOperatorDecisionStates -contains $OperatorDecisionState) {
    throw "operator decision '$OperatorDecisionState' is forbidden."
}
if ($allowedOperatorDecisionStates -notcontains $OperatorDecisionState) {
    throw "operator decision '$OperatorDecisionState' is invalid."
}

$receiptAbs = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $ReceiptPath).Path)
if (-not (Test-Path -LiteralPath $receiptAbs -PathType Leaf)) {
    throw "receipt not found: $ReceiptPath"
}
if (-not (Test-IsPathWithin -CandidatePath $receiptAbs -ParentPath $sandboxAnchorAbs)) {
    throw "receipt must be within sandbox root."
}

$receipt = Get-Content -LiteralPath $receiptAbs -Raw | ConvertFrom-Json

if ($null -eq $receipt.receipt_id -or [string]::IsNullOrWhiteSpace([string]$receipt.receipt_id)) {
    throw "receipt_id is missing in source receipt."
}
if ($receipt.command_name -ne "Invoke-MaxineSandboxResolverWrite.ps1") {
    throw "source receipt command_name is invalid for review packet build."
}

$reviewPacketId = "sandbox-review-packet-$([Guid]::NewGuid().ToString('N'))"
$outRel = $OutputPath
if ([string]::IsNullOrWhiteSpace($outRel)) {
    $outRel = "$reviewPacketsRootRel/$reviewPacketId.json"
}
$outAbs = Get-SafeRelativePathAbs -RelativePath $outRel -AllowedRootAbs $reviewPacketsRootAbs -Label "output_path"

$writeStatus = [string]$receipt.status
if ([string]::IsNullOrWhiteSpace($writeStatus)) {
    if ($receipt.write_succeeded -eq $true) {
        $writeStatus = "written"
    } elseif ($null -ne $receipt.blocked_reason) {
        $writeStatus = "blocked"
    } else {
        $writeStatus = "failed"
    }
}

$rollbackStatus = [string]$receipt.rollback_status
if ([string]::IsNullOrWhiteSpace($rollbackStatus)) {
    $rollbackStatus = "not_requested"
}

$nextSafestStep = "pending_operator_review"
if ($writeStatus -eq "blocked") {
    $nextSafestStep = "review_blocked_reason"
} elseif ($rollbackStatus -eq "rolled_back") {
    $nextSafestStep = "preserve_evidence_and_keep_sandbox_only"
} elseif ($OperatorDecisionState -eq "request_rollback") {
    $nextSafestStep = "execute_sandbox_rollback"
}

$packet = [ordered]@{
    schema_version = "1.0.0"
    review_packet_id = $reviewPacketId
    source_receipt_id = [string]$receipt.receipt_id
    sandbox_root = "examples/sandbox"
    target_path = $receipt.target_path
    files_written = @($receipt.files_written)
    write_status = $writeStatus
    rollback_status = $rollbackStatus
    sha256_before = $receipt.sha256_before
    sha256_after = $receipt.sha256_after
    blocked_reason = $receipt.blocked_reason
    safety_summary = "Sandbox-only review packet. Authoritative writes, O3DE/AP execution, product resolution, Asset IDs, spawning, and publishing remain blocked."
    operator_decision_state = $OperatorDecisionState
    next_safest_step = $nextSafestStep
    explicit_blocked_capabilities = @($blockedCapabilities)
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

Write-JsonFile -InputObject $packet -OutputPath $outAbs
Write-Host "Review packet: $outAbs"
