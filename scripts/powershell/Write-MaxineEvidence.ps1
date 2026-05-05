param(
    [string]$JobId = "",
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,
    [string]$EvidenceRoot = "",
    [string]$StdoutPath = "",
    [string]$StderrPath = "",
    [string]$LogPath = "",
    [string]$Status = "running",
    [string]$Message = "",
    [int]$ExitCode = 0,
    [string]$ErrorCode = "",
    [string]$ErrorStage = "",
    [string]$ManualReviewReason = "",
    [string[]]$CleanupPaths = @(),
    [string]$RetentionClass = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "MaxineManifestHelpers.ps1")

$allowedStatuses = @(
    "created",
    "cancelled",
    "pass",
    "warn",
    "fail",
    "pending_manual",
    "running",
    "queued"
)

$allowedRetention = @("draft-7d", "release-365d", "manual", "unknown")

function Get-QcFromStatus {
    param([string]$CurrentStatus)
    switch ($CurrentStatus) {
        "pass" { return "pass" }
        "warn" { return "warn" }
        "fail" { return "fail" }
        default { return "not_run" }
    }
}

if ($allowedStatuses -notcontains $Status) {
    Write-Error ("Invalid status '{0}'. Allowed statuses: {1}" -f $Status, ($allowedStatuses -join ", "))
    exit 1
}

if (-not [string]::IsNullOrWhiteSpace($RetentionClass) -and $allowedRetention -notcontains $RetentionClass) {
    Write-Error ("Invalid retention class '{0}'. Allowed values: {1}" -f $RetentionClass, ($allowedRetention -join ", "))
    exit 1
}

$repoRoot = Resolve-MaxineRepoRoot -ScriptRoot $PSScriptRoot
$manifestResolved = Resolve-MaxinePath -Path $ManifestPath -RepoRoot $repoRoot
if (-not (Test-Path -LiteralPath $manifestResolved)) {
    Write-Error ("Manifest not found: {0}" -f $manifestResolved)
    exit 1
}

$manifest = Read-MaxineJsonObject -Path $manifestResolved

$jobObj = Ensure-MaxineChildObject -Parent $manifest -Name "job"
$qcObj = Ensure-MaxineChildObject -Parent $manifest -Name "qc"
$evidenceObj = Ensure-MaxineChildObject -Parent $manifest -Name "evidence"
$cleanupObj = Ensure-MaxineChildObject -Parent $manifest -Name "cleanup"
$manualReviewObj = Ensure-MaxineChildObject -Parent $manifest -Name "manual_review"

if ([string]::IsNullOrWhiteSpace($JobId)) {
    if ($jobObj -and $jobObj.PSObject.Properties["job_id"] -and $jobObj.job_id) {
        $JobId = [string]$jobObj.job_id
    }
}
if ([string]::IsNullOrWhiteSpace($JobId)) {
    Write-Error "JobId was not supplied and could not be resolved from manifest."
    exit 1
}

if ([string]::IsNullOrWhiteSpace($EvidenceRoot)) {
    if ($evidenceObj.PSObject.Properties["artifact_root"] -and -not [string]::IsNullOrWhiteSpace([string]$evidenceObj.artifact_root)) {
        $EvidenceRoot = [string]$evidenceObj.artifact_root
    }
    else {
        $EvidenceRoot = Join-Path $repoRoot ("evidence\jobs\{0}" -f $JobId)
    }
}
else {
    $EvidenceRoot = Resolve-MaxinePath -Path $EvidenceRoot -RepoRoot $repoRoot
}

$logsDir = Join-Path $EvidenceRoot "logs"
$screenshotsDir = Join-Path $EvidenceRoot "screenshots"
$o3deDir = Join-Path $EvidenceRoot "o3de"
$qcDir = Join-Path $EvidenceRoot "qc"
$tempDir = Join-Path $EvidenceRoot "temp"
$undoDir = Join-Path $EvidenceRoot "undo"
$cleanupDir = Join-Path $EvidenceRoot "cleanup"
$reportsDir = Join-Path $EvidenceRoot "reports"

foreach ($dir in @($EvidenceRoot, $logsDir, $screenshotsDir, $o3deDir, $qcDir, $tempDir, $undoDir, $cleanupDir, $reportsDir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

$utcNow = Get-MaxineUtcNow
Set-MaxineObjectProperty -Object $jobObj -Name "status" -Value $Status
Set-MaxineObjectProperty -Object $jobObj -Name "updated_utc" -Value $utcNow

if (-not $jobObj.PSObject.Properties["submitted_at"] -or [string]::IsNullOrWhiteSpace([string]$jobObj.submitted_at)) {
    $submitted = if ($jobObj.PSObject.Properties["created_utc"] -and -not [string]::IsNullOrWhiteSpace([string]$jobObj.created_utc)) {
        [string]$jobObj.created_utc
    }
    else {
        $utcNow
    }
    Set-MaxineObjectProperty -Object $jobObj -Name "submitted_at" -Value $submitted
}

if ($Status -eq "running") {
    if (-not $jobObj.PSObject.Properties["started_at"] -or [string]::IsNullOrWhiteSpace([string]$jobObj.started_at)) {
        Set-MaxineObjectProperty -Object $jobObj -Name "started_at" -Value $utcNow
    }
}
elseif (@("pass", "warn", "fail", "pending_manual", "cancelled") -contains $Status) {
    if (-not $jobObj.PSObject.Properties["started_at"] -or [string]::IsNullOrWhiteSpace([string]$jobObj.started_at)) {
        Set-MaxineObjectProperty -Object $jobObj -Name "started_at" -Value $utcNow
    }
    Set-MaxineObjectProperty -Object $jobObj -Name "finished_at" -Value $utcNow
}

Set-MaxineObjectProperty -Object $qcObj -Name "overall" -Value (Get-QcFromStatus -CurrentStatus $Status)
if (-not $qcObj.PSObject.Properties["checks"]) {
    Set-MaxineObjectProperty -Object $qcObj -Name "checks" -Value @()
}

$resolvedLogs = @()
foreach ($candidate in @($StdoutPath, $StderrPath, $LogPath)) {
    if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
    $resolvedLogs += (Resolve-MaxinePath -Path $candidate -RepoRoot $repoRoot)
}

$existingLogs = Ensure-MaxineArrayProperty -Parent $evidenceObj -Name "logs"
$allLogs = Merge-MaxineUniqueStrings -Base $existingLogs -Incoming $resolvedLogs
Set-MaxineObjectProperty -Object $evidenceObj -Name "logs" -Value $allLogs

if (-not [string]::IsNullOrWhiteSpace($StdoutPath)) {
    Set-MaxineObjectProperty -Object $evidenceObj -Name "stdout_log" -Value (Resolve-MaxinePath -Path $StdoutPath -RepoRoot $repoRoot)
}
elseif (-not $evidenceObj.PSObject.Properties["stdout_log"]) {
    Set-MaxineObjectProperty -Object $evidenceObj -Name "stdout_log" -Value $null
}

if (-not [string]::IsNullOrWhiteSpace($StderrPath)) {
    Set-MaxineObjectProperty -Object $evidenceObj -Name "stderr_log" -Value (Resolve-MaxinePath -Path $StderrPath -RepoRoot $repoRoot)
}
elseif (-not $evidenceObj.PSObject.Properties["stderr_log"]) {
    Set-MaxineObjectProperty -Object $evidenceObj -Name "stderr_log" -Value $null
}

if (-not $evidenceObj.PSObject.Properties["screenshots"]) {
    Set-MaxineObjectProperty -Object $evidenceObj -Name "screenshots" -Value @()
}
Set-MaxineObjectProperty -Object $evidenceObj -Name "manifest_path" -Value $manifestResolved
Set-MaxineObjectProperty -Object $evidenceObj -Name "artifact_root" -Value $EvidenceRoot
Set-MaxineObjectProperty -Object $evidenceObj -Name "exit_code" -Value $ExitCode
Set-MaxineObjectProperty -Object $evidenceObj -Name "message" -Value $Message

$reportPath = Join-Path $reportsDir "evidence-summary.json"
$summary = [ordered]@{
    job_id      = $JobId
    status      = $Status
    message     = $Message
    exit_code   = $ExitCode
    updated_utc = $utcNow
}
Write-MaxineJsonAtomic -Path $reportPath -Data $summary -Depth 10

$existingReports = Ensure-MaxineArrayProperty -Parent $evidenceObj -Name "reports"
$reports = Merge-MaxineUniqueStrings -Base $existingReports -Incoming @($reportPath)
Set-MaxineObjectProperty -Object $evidenceObj -Name "reports" -Value $reports

$errorItems = @()
if ($manifest.PSObject.Properties["errors"] -and $null -ne $manifest.errors) {
    $errorItems = @($manifest.errors)
}
if ($Status -eq "fail" -or -not [string]::IsNullOrWhiteSpace($ErrorCode) -or -not [string]::IsNullOrWhiteSpace($ErrorStage)) {
    $err = [ordered]@{
        code         = $(if ([string]::IsNullOrWhiteSpace($ErrorCode)) { "JOB_STAGE_FAILURE" } else { $ErrorCode })
        message      = $(if ([string]::IsNullOrWhiteSpace($Message)) { "Job failed." } else { $Message })
        stage        = $(if ([string]::IsNullOrWhiteSpace($ErrorStage)) { "unknown" } else { $ErrorStage })
        recorded_utc = $utcNow
    }
    $errorItems += [pscustomobject]$err
}
Set-MaxineObjectProperty -Object $manifest -Name "errors" -Value $errorItems

if ($Status -eq "pending_manual") {
    Set-MaxineObjectProperty -Object $manualReviewObj -Name "required" -Value $true
    if (-not [string]::IsNullOrWhiteSpace($ManualReviewReason)) {
        Set-MaxineObjectProperty -Object $manualReviewObj -Name "reason" -Value $ManualReviewReason
    }
    elseif (-not [string]::IsNullOrWhiteSpace($Message)) {
        Set-MaxineObjectProperty -Object $manualReviewObj -Name "reason" -Value $Message
    }
    elseif (-not $manualReviewObj.PSObject.Properties["reason"]) {
        Set-MaxineObjectProperty -Object $manualReviewObj -Name "reason" -Value "Manual review required."
    }
    Set-MaxineObjectProperty -Object $manualReviewObj -Name "review_state" -Value "pending"
}
elseif (-not $manualReviewObj.PSObject.Properties["required"]) {
    Set-MaxineObjectProperty -Object $manualReviewObj -Name "required" -Value $false
    Set-MaxineObjectProperty -Object $manualReviewObj -Name "reason" -Value $null
    Set-MaxineObjectProperty -Object $manualReviewObj -Name "review_state" -Value "not_required"
}

if (-not [string]::IsNullOrWhiteSpace($RetentionClass)) {
    Set-MaxineObjectProperty -Object $cleanupObj -Name "retention_class" -Value $RetentionClass
}
elseif (-not $cleanupObj.PSObject.Properties["retention_class"]) {
    Set-MaxineObjectProperty -Object $cleanupObj -Name "retention_class" -Value "unknown"
}

$existingCleanupPaths = Ensure-MaxineArrayProperty -Parent $cleanupObj -Name "paths"
$cleanupMerge = @($CleanupPaths + @($tempDir, $cleanupDir))
$cleanupPathsFinal = Merge-MaxineUniqueStrings -Base $existingCleanupPaths -Incoming $cleanupMerge
Set-MaxineObjectProperty -Object $cleanupObj -Name "paths" -Value $cleanupPathsFinal

Write-MaxineJsonAtomic -Path $manifestResolved -Data $manifest -Depth 40
Invoke-MaxineManifestValidation -ManifestPath $manifestResolved -RepoRoot $repoRoot

Write-Host ("Updated manifest: {0}" -f $manifestResolved)
Write-Host ("Evidence root: {0}" -f $EvidenceRoot)
Write-Output $manifestResolved
