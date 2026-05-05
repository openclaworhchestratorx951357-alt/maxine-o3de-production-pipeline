[CmdletBinding()]
param(
    [switch]$List,
    [string]$DiagnosticExecutionId,
    [string]$DiagnosticExecutionPath,
    [switch]$ShowOutputRefs,
    [switch]$ShowBlockedReason,
    [string]$DiagnosticExecutionsRoot = "examples/sandbox/ap-diagnostic-executions"
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
        diagnostic_execution_id = [string]$Item.diagnostic_execution_id
        source_preflight_id = [string]$Item.source_preflight_id
        execution_mode = [string]$Item.execution_mode
        execution_status = [string]$Item.execution_status
        command_executed = [bool]$Item.command_executed
        command_allowlisted = [bool]$Item.command_allowlisted
        exit_code = $Item.exit_code
        output_path = [string]$Item.output_path
        started_utc = [string]$Item.started_utc
        completed_utc = [string]$Item.completed_utc
    }
}

$diagnosticRootAbs = Get-SafeRelativePathAbs -RelativePath $DiagnosticExecutionsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "diagnostic_executions_root"
if (-not (Test-Path -LiteralPath $diagnosticRootAbs -PathType Container)) {
    throw "diagnostic executions root not found: $DiagnosticExecutionsRoot"
}

if (-not $List -and [string]::IsNullOrWhiteSpace($DiagnosticExecutionId) -and [string]::IsNullOrWhiteSpace($DiagnosticExecutionPath)) {
    $List = $true
}

if ($List -and (-not [string]::IsNullOrWhiteSpace($DiagnosticExecutionId) -or -not [string]::IsNullOrWhiteSpace($DiagnosticExecutionPath))) {
    throw "Provide either -List, -DiagnosticExecutionId, or -DiagnosticExecutionPath."
}
if (-not [string]::IsNullOrWhiteSpace($DiagnosticExecutionId) -and -not [string]::IsNullOrWhiteSpace($DiagnosticExecutionPath)) {
    throw "Provide either -DiagnosticExecutionId or -DiagnosticExecutionPath, not both."
}

$refs = @()
foreach ($file in Get-ChildItem -LiteralPath $diagnosticRootAbs -File -Filter *.json -ErrorAction SilentlyContinue) {
    try {
        $obj = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
        $refs += [ordered]@{ path = $file.FullName; item = $obj }
    } catch {
        continue
    }
}

if ($List) {
    [ordered]@{
        diagnostic_execution_count = $refs.Count
        diagnostic_executions = @($refs | ForEach-Object { Get-Summary -Item $_.item })
    } | ConvertTo-Json -Depth 100
    exit 0
}

$selected = $null
if (-not [string]::IsNullOrWhiteSpace($DiagnosticExecutionPath)) {
    $targetAbs = $null
    if ([System.IO.Path]::IsPathRooted($DiagnosticExecutionPath)) {
        $targetAbs = [System.IO.Path]::GetFullPath($DiagnosticExecutionPath)
        if (-not (Test-IsPathWithin -CandidatePath $targetAbs -ParentPath $diagnosticRootAbs)) {
            throw "diagnostic_execution_path must remain under ap-diagnostic-executions."
        }
    } else {
        $targetAbs = Get-SafeRelativePathAbs -RelativePath $DiagnosticExecutionPath -AllowedRootAbs $diagnosticRootAbs -Label "diagnostic_execution_path"
    }

    if (-not (Test-Path -LiteralPath $targetAbs -PathType Leaf)) {
        throw "diagnostic_execution_path not found: $DiagnosticExecutionPath"
    }
    $selected = Get-Content -LiteralPath $targetAbs -Raw | ConvertFrom-Json
} else {
    $match = $refs | Where-Object { [string]$_.item.diagnostic_execution_id -eq $DiagnosticExecutionId } | Select-Object -First 1
    if (-not $match) {
        throw "diagnostic_execution_id '$DiagnosticExecutionId' not found."
    }
    $selected = $match.item
}

if ($ShowOutputRefs -or $ShowBlockedReason) {
    $selected | ConvertTo-Json -Depth 100
} else {
    Get-Summary -Item $selected | ConvertTo-Json -Depth 100
}
