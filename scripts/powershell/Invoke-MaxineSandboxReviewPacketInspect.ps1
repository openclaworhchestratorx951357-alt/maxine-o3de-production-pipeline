[CmdletBinding()]
param(
    [switch]$List,
    [string]$ReviewPacketId,
    [string]$ReviewPacketsRoot = "examples/sandbox/review-packets"
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

$packetsRootAbs = Get-SafeRelativePathAbs -RelativePath $ReviewPacketsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "review_packets_root"
if (-not (Test-Path -LiteralPath $packetsRootAbs -PathType Container)) {
    throw "review packets root not found: $ReviewPacketsRoot"
}

if (-not $List -and [string]::IsNullOrWhiteSpace($ReviewPacketId)) {
    $List = $true
}
if ($List -and -not [string]::IsNullOrWhiteSpace($ReviewPacketId)) {
    throw "Provide either -List or -ReviewPacketId, not both."
}

$packetFiles = Get-ChildItem -LiteralPath $packetsRootAbs -File -Filter *.json
$packets = @()
foreach ($file in $packetFiles) {
    $packets += (Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json)
}

if ($List) {
    $summary = foreach ($packet in $packets) {
        [ordered]@{
            review_packet_id = [string]$packet.review_packet_id
            source_receipt_id = [string]$packet.source_receipt_id
            write_status = [string]$packet.write_status
            rollback_status = [string]$packet.rollback_status
            operator_decision_state = [string]$packet.operator_decision_state
            target_path = $packet.target_path
            files_written = @($packet.files_written)
            blocked_reason = $packet.blocked_reason
        }
    }

    [ordered]@{
        packet_count = @($summary).Count
        review_packets = @($summary)
    } | ConvertTo-Json -Depth 50

    exit 0
}

$match = $packets | Where-Object { $_.review_packet_id -eq $ReviewPacketId } | Select-Object -First 1
if (-not $match) {
    throw "review_packet_id '$ReviewPacketId' not found."
}

$match | ConvertTo-Json -Depth 50
