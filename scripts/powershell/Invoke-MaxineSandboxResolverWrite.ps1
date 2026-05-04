[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PlanPath,

    [string]$ReceiptPath,

    [string]$ReceiptIndexPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$commandName = "Invoke-MaxineSandboxResolverWrite.ps1"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))
$defaultReceiptDirAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox\manifests\reports"))
$defaultReceiptIndexRel = "examples/sandbox/receipts/index.json"
$planSchemaPath = Join-Path $repoRoot "schemas\maxine_sandbox_resolver_write_plan.schema.json"

$resolvedReceiptIndexAbs = $null
$resolvedReceiptIndexRel = $defaultReceiptIndexRel

$timestampUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$receiptId = "sandbox-write-receipt-$([System.Guid]::NewGuid().ToString('N'))"
$receipt = [ordered]@{
    receipt_id = $receiptId
    command_name = $commandName
    input_plan_path = $PlanPath
    sandbox_root = $null
    target_path = $null
    write_attempted = $false
    write_succeeded = $false
    mutation_scope = "sandbox_only"
    blocked_reason = $null
    status = "failed"
    rollback_status = "not_requested"
    files_written = @()
    sha256_before = $null
    sha256_after = $null
    rollback_receipt_hint = $null
    receipt_path = $null
    receipt_index_path = $resolvedReceiptIndexRel
    timestamp_utc = $timestampUtc
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
        [string]$Label = "path",
        [switch]$RequireStaging
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
    $lower = $normalized.ToLowerInvariant()

    if (($normalized -split "/") -contains "..") {
        throw "$Label contains parent traversal and is blocked."
    }

    foreach ($forbidden in @("maxineshow", "/cache/", "/engine/", "assetprocessor", ".o3de", "o3de/projects", "authoritative")) {
        if ($lower.Contains($forbidden)) {
            throw "$Label hit forbidden pattern '$forbidden'."
        }
    }

    $candidateAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $RelativePath))
    if (-not (Test-IsPathWithin -CandidatePath $candidateAbs -ParentPath $AllowedRootAbs)) {
        throw "$Label escapes the approved sandbox root."
    }

    if ($RequireStaging) {
        $stagingAbs = [System.IO.Path]::GetFullPath((Join-Path $AllowedRootAbs "staging"))
        if (-not (Test-IsPathWithin -CandidatePath $candidateAbs -ParentPath $stagingAbs)) {
            throw "$Label must be under examples/sandbox/staging."
        }
    }

    return $candidateAbs
}

function Get-Sha256OrNull {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Has-Property {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string]$PropertyName
    )

    return $InputObject.PSObject.Properties.Name -contains $PropertyName
}

function Load-ReceiptIndex {
    param(
        [Parameter(Mandatory = $true)]
        [string]$IndexAbs,
        [Parameter(Mandatory = $true)]
        [string]$SandboxRootRel
    )

    if (Test-Path -LiteralPath $IndexAbs -PathType Leaf) {
        $existing = Get-Content -LiteralPath $IndexAbs -Raw | ConvertFrom-Json
        if (-not (Has-Property -InputObject $existing -PropertyName "receipts")) {
            throw "receipt index is missing receipts array."
        }
        if ($existing.receipts -eq $null) {
            $existing | Add-Member -MemberType NoteProperty -Name receipts -Value @() -Force
        }
        return $existing
    }

    return [ordered]@{
        schema_version = "1.0.0"
        sandbox_root = $SandboxRootRel
        receipts = @()
    }
}

function Upsert-ReceiptIndexEntry {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Index,
        [Parameter(Mandatory = $true)]
        [hashtable]$ReceiptObject
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

function Finalize-Receipt {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ExitCode,
        [string]$BlockedReason
    )

    if ($BlockedReason) {
        $receipt.blocked_reason = $BlockedReason
    }

    if ($receipt.write_succeeded -eq $true) {
        $receipt.status = "written"
    } elseif ($receipt.blocked_reason) {
        $receipt.status = "blocked"
    } else {
        $receipt.status = "failed"
    }

    $resolvedReceiptAbs = $null
    if ($ReceiptPath) {
        try {
            $resolvedReceiptAbs = Get-SafeRelativePathAbs -RelativePath $ReceiptPath -AllowedRootAbs $sandboxAnchorAbs -Label "receipt_path"
        } catch {
            $fallbackName = "sandbox-write-receipt-fallback-$([System.Guid]::NewGuid().ToString('N')).json"
            $resolvedReceiptAbs = Join-Path $defaultReceiptDirAbs $fallbackName
            $receipt.blocked_reason = (($receipt.blocked_reason + "; ") -replace '^\s*;\s*', '') + "unsafe receipt_path supplied; fallback receipt path used."
        }
    } else {
        $receiptName = "sandbox-write-receipt-$($receipt.receipt_id).json"
        $resolvedReceiptAbs = Join-Path $defaultReceiptDirAbs $receiptName
    }

    $receipt.receipt_path = Get-RepoRelativePath -AbsolutePath $resolvedReceiptAbs
    $receipt.receipt_index_path = $resolvedReceiptIndexRel

    if (-not $receipt.rollback_receipt_hint) {
        $receipt.rollback_receipt_hint = "Invoke-MaxineSandboxRollback.ps1 -ReceiptPath `"$($receipt.receipt_path)`" -ConfirmRollback"
    }

    $receipt.timestamp_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    Write-JsonFile -InputObject $receipt -OutputPath $resolvedReceiptAbs

    if (-not $resolvedReceiptIndexAbs) {
        $resolvedReceiptIndexAbs = Get-SafeRelativePathAbs -RelativePath $defaultReceiptIndexRel -AllowedRootAbs $sandboxAnchorAbs -Label "receipt_index_path"
        $resolvedReceiptIndexRel = $defaultReceiptIndexRel
        $receipt.receipt_index_path = $resolvedReceiptIndexRel
    }

    $index = Load-ReceiptIndex -IndexAbs $resolvedReceiptIndexAbs -SandboxRootRel "examples/sandbox"
    $index = Upsert-ReceiptIndexEntry -Index $index -ReceiptObject $receipt
    Write-JsonFile -InputObject $index -OutputPath $resolvedReceiptIndexAbs

    Write-Host "Receipt: $resolvedReceiptAbs"
    Write-Host "Receipt index: $resolvedReceiptIndexAbs"

    if ($ExitCode -eq 0) {
        Write-Host "PASS: sandbox-only write skeleton completed."
    } else {
        Write-Host "FAIL: sandbox-only write skeleton blocked."
    }

    exit $ExitCode
}

try {
    if (-not (Test-Path -LiteralPath $planSchemaPath -PathType Leaf)) {
        throw "plan schema missing at '$planSchemaPath'."
    }

    $planPathAbs = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $PlanPath).Path)
    if (-not (Test-Path -LiteralPath $planPathAbs -PathType Leaf)) {
        throw "plan file not found."
    }

    $planSchema = Get-Content -LiteralPath $planSchemaPath -Raw | ConvertFrom-Json
    $plan = Get-Content -LiteralPath $planPathAbs -Raw | ConvertFrom-Json

    if (-not (Has-Property -InputObject $planSchema -PropertyName "required")) {
        throw "plan schema has no required list."
    }

    foreach ($requiredField in $planSchema.required) {
        if (-not (Has-Property -InputObject $plan -PropertyName $requiredField)) {
            throw "plan is missing required field '$requiredField'."
        }
    }

    if ($plan.command_name -ne $commandName) {
        throw "plan.command_name must equal $commandName."
    }
    if ($plan.sandbox_scope -ne "sandbox_only") {
        throw "plan.sandbox_scope must be sandbox_only."
    }
    if (-not (Has-Property -InputObject $plan -PropertyName "plan_signature")) {
        throw "plan.plan_signature is required."
    }
    if ($plan.plan_signature.signed_by -eq $null -or [string]::IsNullOrWhiteSpace([string]$plan.plan_signature.signed_by)) {
        throw "plan.plan_signature.signed_by is required."
    }
    if ($plan.plan_signature.signature -eq $null -or [string]::IsNullOrWhiteSpace([string]$plan.plan_signature.signature)) {
        throw "plan.plan_signature.signature is required."
    }

    $sandboxRootRel = [string]$plan.sandbox_root
    $sandboxRootAbs = Get-SafeRelativePathAbs -RelativePath $sandboxRootRel -AllowedRootAbs $sandboxAnchorAbs -Label "sandbox_root"
    $sandboxRootCanonical = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))
    if (-not $sandboxRootAbs.Equals($sandboxRootCanonical, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "sandbox_root must resolve to examples/sandbox."
    }

    $indexRel = $ReceiptIndexPath
    if ([string]::IsNullOrWhiteSpace($indexRel) -and (Has-Property -InputObject $plan -PropertyName "receipt_index_path") -and -not [string]::IsNullOrWhiteSpace([string]$plan.receipt_index_path)) {
        $indexRel = [string]$plan.receipt_index_path
    }
    if ([string]::IsNullOrWhiteSpace($indexRel)) {
        $indexRel = $defaultReceiptIndexRel
    }

    $resolvedReceiptIndexAbs = Get-SafeRelativePathAbs -RelativePath $indexRel -AllowedRootAbs $sandboxRootAbs -Label "receipt_index_path"
    $resolvedReceiptIndexRel = Get-RepoRelativePath -AbsolutePath $resolvedReceiptIndexAbs

    if ($plan.explicit_sandbox_approval -ne $true) {
        throw "plan.explicit_sandbox_approval must be true."
    }
    if ($plan.approved_target_under_sandbox -ne $true) {
        throw "plan.approved_target_under_sandbox must be true."
    }

    $targetRel = [string]$plan.target_path
    $targetAbs = Get-SafeRelativePathAbs -RelativePath $targetRel -AllowedRootAbs $sandboxRootAbs -Label "target_path" -RequireStaging

    $receipt.sandbox_root = $sandboxRootRel
    $receipt.target_path = $targetRel
    $receipt.receipt_index_path = $resolvedReceiptIndexRel

    $payload = @{}
    if ((Has-Property -InputObject $plan -PropertyName "write_payload") -and $null -ne $plan.write_payload) {
        $payload = $plan.write_payload
    }

    $receipt.sha256_before = Get-Sha256OrNull -Path $targetAbs
    $receipt.write_attempted = $true

    $targetDirectory = Split-Path -Parent $targetAbs
    if ($targetDirectory -and -not (Test-Path -LiteralPath $targetDirectory)) {
        New-Item -Path $targetDirectory -ItemType Directory -Force | Out-Null
    }

    $placeholder = [ordered]@{
        schema_version = "1.0.0"
        command_name = $commandName
        plan_id = [string]$plan.plan_id
        mutation_scope = "sandbox_only"
        proof_only = $true
        target_path = $targetRel
        signed_by = [string]$plan.plan_signature.signed_by
        write_payload = $payload
        written_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    }

    Write-JsonFile -InputObject $placeholder -OutputPath $targetAbs

    $receipt.files_written = @($targetRel)
    $receipt.sha256_after = Get-Sha256OrNull -Path $targetAbs
    $receipt.write_succeeded = $true

    Finalize-Receipt -ExitCode 0
} catch {
    Finalize-Receipt -ExitCode 1 -BlockedReason $_.Exception.Message
}
