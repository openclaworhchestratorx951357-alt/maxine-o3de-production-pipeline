[CmdletBinding()]
param(
    [switch]$List,
    [string]$ReviewPacketId,
    [string]$ReviewPacketPath,
    [switch]$ShowEvidenceLinks,
    [string]$ReviewPacketsRoot = "examples/sandbox/asset-candidate-review-packets"
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

function Get-ReviewPacketSummary {
    param(
        [Parameter(Mandatory = $true)]
        [object]$ReviewPacket
    )

    return [ordered]@{
        review_packet_id = [string]$ReviewPacket.review_packet_id
        source_inventory_id = [string]$ReviewPacket.source_inventory_id
        candidate_id = [string]$ReviewPacket.candidate_id
        candidate_relative_path = [string]$ReviewPacket.candidate_relative_path
        candidate_category = [string]$ReviewPacket.candidate_category
        confidence = [string]$ReviewPacket.confidence
        operator_decision_state = [string]$ReviewPacket.operator_decision_state
        recommended_next_step = [string]$ReviewPacket.recommended_next_step
        output_path = [string]$ReviewPacket.output_path
        created_utc = [string]$ReviewPacket.created_utc
    }
}

$reviewPacketsRootAbs = Get-SafeRelativePathAbs -RelativePath $ReviewPacketsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "review_packets_root"
if (-not (Test-Path -LiteralPath $reviewPacketsRootAbs -PathType Container)) {
    throw "review packets root not found: $ReviewPacketsRoot"
}

if (-not $List -and [string]::IsNullOrWhiteSpace($ReviewPacketId) -and [string]::IsNullOrWhiteSpace($ReviewPacketPath)) {
    $List = $true
}

if ($List -and (-not [string]::IsNullOrWhiteSpace($ReviewPacketId) -or -not [string]::IsNullOrWhiteSpace($ReviewPacketPath))) {
    throw "Provide either -List, -ReviewPacketId, or -ReviewPacketPath."
}
if (-not [string]::IsNullOrWhiteSpace($ReviewPacketId) -and -not [string]::IsNullOrWhiteSpace($ReviewPacketPath)) {
    throw "Provide either -ReviewPacketId or -ReviewPacketPath, not both."
}

$packetRefs = @()
foreach ($file in Get-ChildItem -LiteralPath $reviewPacketsRootAbs -File -Filter *.json -ErrorAction SilentlyContinue) {
    try {
        $obj = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
        $packetRefs += [ordered]@{
            path = $file.FullName
            item = $obj
        }
    } catch {
        continue
    }
}

if ($List) {
    $summary = @($packetRefs | ForEach-Object { Get-ReviewPacketSummary -ReviewPacket $_.item })
    [ordered]@{
        review_packet_count = $summary.Count
        review_packets = $summary
    } | ConvertTo-Json -Depth 100
    exit 0
}

if (-not [string]::IsNullOrWhiteSpace($ReviewPacketPath)) {
    $packetAbs = $null
    if ([System.IO.Path]::IsPathRooted($ReviewPacketPath)) {
        $packetAbs = [System.IO.Path]::GetFullPath($ReviewPacketPath)
        if (-not (Test-IsPathWithin -CandidatePath $packetAbs -ParentPath $reviewPacketsRootAbs)) {
            throw "review_packet_path must remain under asset candidate review packets root."
        }
    } else {
        $packetAbs = Get-SafeRelativePathAbs -RelativePath $ReviewPacketPath -AllowedRootAbs $reviewPacketsRootAbs -Label "review_packet_path"
    }

    if (-not (Test-Path -LiteralPath $packetAbs -PathType Leaf)) {
        throw "review_packet_path not found: $ReviewPacketPath"
    }

    $packet = Get-Content -LiteralPath $packetAbs -Raw | ConvertFrom-Json
    if ($ShowEvidenceLinks) {
        $packet | ConvertTo-Json -Depth 100
    } else {
        Get-ReviewPacketSummary -ReviewPacket $packet | ConvertTo-Json -Depth 100
    }
    exit 0
}

$match = $packetRefs | Where-Object { [string]$_.item.review_packet_id -eq $ReviewPacketId } | Select-Object -First 1
if (-not $match) {
    throw "review_packet_id '$ReviewPacketId' not found."
}

if ($ShowEvidenceLinks) {
    $match.item | ConvertTo-Json -Depth 100
} else {
    Get-ReviewPacketSummary -ReviewPacket $match.item | ConvertTo-Json -Depth 100
}
