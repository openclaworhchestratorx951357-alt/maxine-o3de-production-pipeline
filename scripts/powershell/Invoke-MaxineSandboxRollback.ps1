[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ReceiptPath,

    [Parameter(Mandatory = $true)]
    [switch]$ConfirmRollback,

    [string]$RollbackReceiptPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$commandName = "Invoke-MaxineSandboxRollback.ps1"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

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
        throw "$Label must be relative. Absolute paths are blocked."
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

function Finalize {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ExitCode,
        [Parameter(Mandatory = $true)]
        [hashtable]$Report
    )

    $outputPath = $RollbackReceiptPath
    if (-not $outputPath) {
        $baseName = [System.IO.Path]::GetFileNameWithoutExtension($ReceiptPath)
        $outputPath = "examples/sandbox/manifests/reports/$baseName.rollback.json"
    }

    $reportPathAbs = Get-SafeRelativePathAbs -RelativePath $outputPath -AllowedRootAbs $sandboxAnchorAbs -Label "rollback_receipt_path"
    $Report.timestamp_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    Write-JsonFile -InputObject $Report -OutputPath $reportPathAbs
    Write-Host "Rollback report: $reportPathAbs"
    exit $ExitCode
}

$report = [ordered]@{
    command_name = $commandName
    input_receipt_path = $ReceiptPath
    rollback_confirmed = [bool]$ConfirmRollback
    rollback_attempted = $false
    rollback_succeeded = $false
    files_requested = @()
    files_removed = @()
    blocked_reason = $null
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

try {
    if (-not $ConfirmRollback) {
        throw "ConfirmRollback is required."
    }

    $receiptPathAbs = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $ReceiptPath).Path)
    if (-not (Test-Path -LiteralPath $receiptPathAbs -PathType Leaf)) {
        throw "receipt file not found."
    }

    $receipt = Get-Content -LiteralPath $receiptPathAbs -Raw | ConvertFrom-Json
    $report.rollback_attempted = $true

    if ($receipt.command_name -ne "Invoke-MaxineSandboxResolverWrite.ps1") {
        throw "receipt command_name is invalid."
    }
    if ($receipt.write_succeeded -ne $true) {
        throw "receipt indicates write_succeeded is not true."
    }
    if ($receipt.mutation_scope -ne "sandbox_only") {
        throw "receipt mutation_scope must be sandbox_only."
    }
    if ($null -eq $receipt.files_written -or $receipt.files_written.Count -lt 1) {
        throw "receipt.files_written must contain at least one file."
    }

    $sandboxRootRel = [string]$receipt.sandbox_root
    $sandboxRootAbs = Get-SafeRelativePathAbs -RelativePath $sandboxRootRel -AllowedRootAbs $sandboxAnchorAbs -Label "sandbox_root"
    $sandboxRootCanonical = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))
    if (-not $sandboxRootAbs.Equals($sandboxRootCanonical, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "receipt sandbox_root must resolve to examples/sandbox."
    }

    $requested = @()
    foreach ($entry in $receipt.files_written) {
        $requested += [string]$entry
    }
    $report.files_requested = $requested

    $removed = @()
    foreach ($relativeFile in $requested) {
        $fileAbs = Get-SafeRelativePathAbs -RelativePath $relativeFile -AllowedRootAbs $sandboxRootAbs -Label "files_written entry"
        if (Test-Path -LiteralPath $fileAbs -PathType Leaf) {
            Remove-Item -LiteralPath $fileAbs -Force
            $removed += $relativeFile
        }
    }

    $report.files_removed = $removed
    $report.rollback_succeeded = $true
    Finalize -ExitCode 0 -Report $report
} catch {
    $report.blocked_reason = $_.Exception.Message
    Finalize -ExitCode 1 -Report $report
}
