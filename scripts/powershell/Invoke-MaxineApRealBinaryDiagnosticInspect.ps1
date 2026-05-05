[CmdletBinding()]
param(
    [switch]$List,
    [string]$ExecutionId,
    [string]$ExecutionPath,
    [switch]$ShowOutputRefs,
    [switch]$ShowBlockedReason,

    [string]$RealBinaryDiagnosticExecutionsRoot = "examples/sandbox/ap-real-binary-diagnostic-executions"
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

function Get-Summary {
    param([Parameter(Mandatory = $true)][object]$Item)

    return [ordered]@{
        real_binary_diagnostic_execution_id = [string]$Item.real_binary_diagnostic_execution_id
        source_ap_binary_preflight_id = [string]$Item.source_ap_binary_preflight_id
        selected_binary_path = [string]$Item.selected_binary_path
        binary_kind = [string]$Item.binary_kind
        execution_mode = [string]$Item.execution_mode
        diagnostic_argument = [string]$Item.diagnostic_argument
        execution_status = [string]$Item.execution_status
        command_executed = [bool]$Item.command_executed
        command_allowlisted = [bool]$Item.command_allowlisted
        exit_code = $Item.exit_code
        output_path = [string]$Item.output_path
        started_utc = [string]$Item.started_utc
        completed_utc = [string]$Item.completed_utc
    }
}

$executionRootAbs = Get-SafeRelativePathAbs -RelativePath $RealBinaryDiagnosticExecutionsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "real_binary_diagnostic_executions_root"
if (-not (Test-Path -LiteralPath $executionRootAbs -PathType Container)) {
    throw "real binary diagnostic executions root not found: $RealBinaryDiagnosticExecutionsRoot"
}

if (-not $List -and [string]::IsNullOrWhiteSpace($ExecutionId) -and [string]::IsNullOrWhiteSpace($ExecutionPath)) {
    $List = $true
}

if ($List -and (-not [string]::IsNullOrWhiteSpace($ExecutionId) -or -not [string]::IsNullOrWhiteSpace($ExecutionPath))) {
    throw "Provide either -List, -ExecutionId, or -ExecutionPath."
}
if (-not [string]::IsNullOrWhiteSpace($ExecutionId) -and -not [string]::IsNullOrWhiteSpace($ExecutionPath)) {
    throw "Provide either -ExecutionId or -ExecutionPath, not both."
}

$refs = @()
foreach ($file in Get-ChildItem -LiteralPath $executionRootAbs -File -Filter *.json -ErrorAction SilentlyContinue) {
    try {
        $obj = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
        $refs += [ordered]@{ path = $file.FullName; item = $obj }
    } catch {
        continue
    }
}

if ($List) {
    [ordered]@{
        execution_count = $refs.Count
        real_binary_diagnostic_executions = @($refs | ForEach-Object { Get-Summary -Item $_.item })
    } | ConvertTo-Json -Depth 100
    exit 0
}

$selected = $null
if (-not [string]::IsNullOrWhiteSpace($ExecutionPath)) {
    $targetAbs = $null
    if ([System.IO.Path]::IsPathRooted($ExecutionPath)) {
        $targetAbs = [System.IO.Path]::GetFullPath($ExecutionPath)
        if (-not (Test-IsPathWithin -CandidatePath $targetAbs -ParentPath $executionRootAbs)) {
            throw "execution_path must remain under ap-real-binary-diagnostic-executions."
        }
    } else {
        $targetAbs = Get-SafeRelativePathAbs -RelativePath $ExecutionPath -AllowedRootAbs $executionRootAbs -Label "execution_path"
    }

    if (-not (Test-Path -LiteralPath $targetAbs -PathType Leaf)) {
        throw "execution_path not found: $ExecutionPath"
    }

    $selected = Get-Content -LiteralPath $targetAbs -Raw | ConvertFrom-Json
} else {
    $match = $refs | Where-Object { [string]$_.item.real_binary_diagnostic_execution_id -eq $ExecutionId } | Select-Object -First 1
    if (-not $match) {
        throw "execution_id '$ExecutionId' not found."
    }
    $selected = $match.item
}

if ($ShowOutputRefs -or $ShowBlockedReason) {
    $selected | ConvertTo-Json -Depth 100
} else {
    (Get-Summary -Item $selected) | ConvertTo-Json -Depth 100
}
