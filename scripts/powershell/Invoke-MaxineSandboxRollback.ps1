[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ReceiptPath,

    [Parameter(Mandatory = $true)]
    [switch]$ConfirmRollback,

    [string]$RollbackReceiptPath,

    [string]$ReceiptIndexPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$commandName = "Invoke-MaxineSandboxRollback.ps1"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))
$defaultReceiptIndexRel = "examples/sandbox/receipts/index.json"

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

function Load-ReceiptIndex {
    param(
        [Parameter(Mandatory = $true)]
        [string]$IndexAbs
    )

    if (Test-Path -LiteralPath $IndexAbs -PathType Leaf) {
        $existing = Get-Content -LiteralPath $IndexAbs -Raw | ConvertFrom-Json
        if ($existing.receipts -eq $null) {
            $existing | Add-Member -MemberType NoteProperty -Name receipts -Value @() -Force
        }
        return $existing
    }

    return [ordered]@{
        schema_version = "1.0.0"
        sandbox_root = "examples/sandbox"
        receipts = @()
    }
}

function Upsert-ReceiptIndexEntry {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Index,
        [Parameter(Mandatory = $true)]
        [object]$ReceiptObject
    )

    $entry = [ordered]@{
        receipt_id = $ReceiptObject.receipt_id
        status = $ReceiptObject.status
        rollback_status = $ReceiptObject.rollback_status
        command_name = $ReceiptObject.command_name
        input_plan_path = $ReceiptObject.input_plan_path
        receipt_path = $ReceiptObject.receipt_path
        target_path = $ReceiptObject.target_path
        files_written = @($ReceiptObject.files_written)
        sha256_before = $ReceiptObject.sha256_before
        sha256_after = $ReceiptObject.sha256_after
        blocked_reason = $ReceiptObject.blocked_reason
        write_attempted = $ReceiptObject.write_attempted
        write_succeeded = $ReceiptObject.write_succeeded
        mutation_scope = $ReceiptObject.mutation_scope
        timestamp_utc = $ReceiptObject.timestamp_utc
        last_updated_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    }

    $replaced = $false
    $newReceipts = @()
    foreach ($existing in $Index.receipts) {
        if ($existing.receipt_id -eq $entry.receipt_id) {
            $newReceipts += $entry
            $replaced = $true
        } else {
            $newReceipts += $existing
        }
    }

    if (-not $replaced) {
        $newReceipts += $entry
    }

    $Index.receipts = $newReceipts
    return $Index
}

function Finalize {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ExitCode,
        [Parameter(Mandatory = $true)]
        [hashtable]$Report,
        [Parameter(Mandatory = $true)]
        [object]$ReceiptObject,
        [Parameter(Mandatory = $true)]
        [string]$ReceiptAbs,
        [Parameter(Mandatory = $true)]
        [string]$IndexAbs
    )

    $outputPath = $RollbackReceiptPath
    if (-not $outputPath) {
        $baseName = [System.IO.Path]::GetFileNameWithoutExtension($ReceiptPath)
        $outputPath = "examples/sandbox/manifests/reports/$baseName.rollback.json"
    }

    $reportPathAbs = Get-SafeRelativePathAbs -RelativePath $outputPath -AllowedRootAbs $sandboxAnchorAbs -Label "rollback_receipt_path"
    $report.timestamp_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    Write-JsonFile -InputObject $Report -OutputPath $reportPathAbs

    if ($ExitCode -eq 0) {
        $ReceiptObject.status = "rolled_back"
        $ReceiptObject.rollback_status = "rolled_back"
        $ReceiptObject.blocked_reason = $null
    } else {
        $ReceiptObject.rollback_status = "rollback_failed"
    }

    $ReceiptObject.rollback_receipt_hint = "Rollback report: $(Get-RepoRelativePath -AbsolutePath $reportPathAbs)"
    $ReceiptObject.receipt_index_path = Get-RepoRelativePath -AbsolutePath $IndexAbs
    $ReceiptObject.timestamp_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

    Write-JsonFile -InputObject $ReceiptObject -OutputPath $ReceiptAbs

    $index = Load-ReceiptIndex -IndexAbs $IndexAbs
    $index = Upsert-ReceiptIndexEntry -Index $index -ReceiptObject $ReceiptObject
    Write-JsonFile -InputObject $index -OutputPath $IndexAbs

    Write-Host "Rollback report: $reportPathAbs"
    Write-Host "Receipt index: $IndexAbs"
    if ($ExitCode -eq 0) {
        Write-Host "PASS: sandbox-only rollback skeleton completed."
    } else {
        Write-Host "FAIL: sandbox-only rollback skeleton blocked."
    }

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
    receipt_id = $null
    status = "failed"
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

$receipt = $null
$receiptPathAbs = $null
$receiptIndexAbs = $null

try {
    if (-not $ConfirmRollback) {
        throw "ConfirmRollback is required."
    }

    $receiptPathAbs = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $ReceiptPath).Path)
    if (-not (Test-Path -LiteralPath $receiptPathAbs -PathType Leaf)) {
        throw "receipt file not found."
    }
    if (-not (Test-IsPathWithin -CandidatePath $receiptPathAbs -ParentPath $sandboxAnchorAbs)) {
        throw "receipt file must be within examples/sandbox."
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

    $indexRel = $ReceiptIndexPath
    if ([string]::IsNullOrWhiteSpace($indexRel) -and $null -ne $receipt.receipt_index_path -and -not [string]::IsNullOrWhiteSpace([string]$receipt.receipt_index_path)) {
        $indexRel = [string]$receipt.receipt_index_path
    }
    if ([string]::IsNullOrWhiteSpace($indexRel)) {
        $indexRel = $defaultReceiptIndexRel
    }
    $receiptIndexAbs = Get-SafeRelativePathAbs -RelativePath $indexRel -AllowedRootAbs $sandboxRootAbs -Label "receipt_index_path"

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
    $report.status = "rolled_back"
    if ($null -ne $receipt.receipt_id) {
        $report.receipt_id = [string]$receipt.receipt_id
    }
    Finalize -ExitCode 0 -Report $report -ReceiptObject $receipt -ReceiptAbs $receiptPathAbs -IndexAbs $receiptIndexAbs
} catch {
    $report.blocked_reason = $_.Exception.Message
    $report.status = "blocked"

    if ($null -ne $receipt -and $null -ne $receipt.receipt_id) {
        $report.receipt_id = [string]$receipt.receipt_id
    }

    if (-not $receipt) {
        $receipt = [ordered]@{
            receipt_id = "unknown"
            command_name = "Invoke-MaxineSandboxResolverWrite.ps1"
            input_plan_path = $null
            sandbox_root = "examples/sandbox"
            target_path = $null
            write_attempted = $false
            write_succeeded = $false
            mutation_scope = "sandbox_only"
            blocked_reason = $report.blocked_reason
            status = "blocked"
            rollback_status = "rollback_failed"
            files_written = @()
            sha256_before = $null
            sha256_after = $null
            rollback_receipt_hint = $null
            receipt_path = $ReceiptPath
            receipt_index_path = $defaultReceiptIndexRel
            timestamp_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        }
    } else {
        $receipt.blocked_reason = $report.blocked_reason
        $receipt.rollback_status = "rollback_failed"
    }

    if (-not $receiptPathAbs) {
        $receiptPathAbs = Get-SafeRelativePathAbs -RelativePath "examples/sandbox/logs/rollback-failed-receipt-$([Guid]::NewGuid().ToString('N')).json" -AllowedRootAbs $sandboxAnchorAbs -Label "fallback_receipt"
    }
    if (-not $receiptIndexAbs) {
        $receiptIndexAbs = Get-SafeRelativePathAbs -RelativePath $defaultReceiptIndexRel -AllowedRootAbs $sandboxAnchorAbs -Label "receipt_index_path"
    }

    Finalize -ExitCode 1 -Report $report -ReceiptObject $receipt -ReceiptAbs $receiptPathAbs -IndexAbs $receiptIndexAbs
}
