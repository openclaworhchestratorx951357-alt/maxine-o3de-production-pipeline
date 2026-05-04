[CmdletBinding()]
param(
    [switch]$List,
    [string]$ReceiptId,
    [string]$IndexPath = "examples/sandbox/receipts/index.json"
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

$indexAbs = Get-SafeRelativePathAbs -RelativePath $IndexPath -AllowedRootAbs $sandboxAnchorAbs -Label "index_path"
if (-not (Test-Path -LiteralPath $indexAbs -PathType Leaf)) {
    throw "receipt index not found at '$IndexPath'."
}

$index = Get-Content -LiteralPath $indexAbs -Raw | ConvertFrom-Json
if ($null -eq $index.receipts) {
    throw "receipt index is missing receipts array."
}

if (-not $List -and [string]::IsNullOrWhiteSpace($ReceiptId)) {
    $List = $true
}

if ($List -and -not [string]::IsNullOrWhiteSpace($ReceiptId)) {
    throw "Provide either -List or -ReceiptId, not both."
}

if ($List) {
    $summary = foreach ($entry in $index.receipts) {
        [ordered]@{
            receipt_id = [string]$entry.receipt_id
            status = [string]$entry.status
            rollback_status = [string]$entry.rollback_status
            files_written = @($entry.files_written)
            sha256_before = $entry.sha256_before
            sha256_after = $entry.sha256_after
            blocked_reason = $entry.blocked_reason
            receipt_path = $entry.receipt_path
            target_path = $entry.target_path
        }
    }

    [ordered]@{
        schema_version = $index.schema_version
        sandbox_root = $index.sandbox_root
        receipt_count = @($index.receipts).Count
        receipts = @($summary)
    } | ConvertTo-Json -Depth 50

    exit 0
}

$match = $index.receipts | Where-Object { $_.receipt_id -eq $ReceiptId } | Select-Object -First 1
if (-not $match) {
    throw "receipt_id '$ReceiptId' not found in index."
}

[ordered]@{
    receipt_id = [string]$match.receipt_id
    status = [string]$match.status
    rollback_status = [string]$match.rollback_status
    files_written = @($match.files_written)
    sha256_before = $match.sha256_before
    sha256_after = $match.sha256_after
    blocked_reason = $match.blocked_reason
    receipt_path = $match.receipt_path
    target_path = $match.target_path
    input_plan_path = $match.input_plan_path
    mutation_scope = $match.mutation_scope
    timestamp_utc = $match.timestamp_utc
    last_updated_utc = $match.last_updated_utc
} | ConvertTo-Json -Depth 50
