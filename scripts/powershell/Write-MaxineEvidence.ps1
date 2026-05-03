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
    [int]$ExitCode = 0
)

$ErrorActionPreference = "Stop"

$allowedStatuses = @(
    "pass",
    "warn",
    "fail",
    "pending_manual",
    "running",
    "queued"
)

function Get-QcFromStatus {
    param([string]$CurrentStatus)
    switch ($CurrentStatus) {
        "pass" { return "pass" }
        "fail" { return "fail" }
        "pending_manual" { return "warn" }
        default { return "warn" }
    }
}

function Set-ObjectProperty {
    param(
        [Parameter(Mandatory = $true)] [object]$Object,
        [Parameter(Mandatory = $true)] [string]$Name,
        [Parameter(Mandatory = $true)] $Value
    )
    if ($Object.PSObject.Properties[$Name]) {
        $Object.$Name = $Value
    }
    else {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function Ensure-ChildObject {
    param(
        [Parameter(Mandatory = $true)] [object]$Parent,
        [Parameter(Mandatory = $true)] [string]$Name
    )
    if (-not $Parent.PSObject.Properties[$Name] -or $null -eq $Parent.$Name) {
        Set-ObjectProperty -Object $Parent -Name $Name -Value ([pscustomobject]@{})
    }
    return $Parent.$Name
}

if ($allowedStatuses -notcontains $Status) {
    Write-Error ("Invalid status '{0}'. Allowed statuses: {1}" -f $Status, ($allowedStatuses -join ", "))
    exit 1
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

$manifestResolved = $ManifestPath
if (-not [System.IO.Path]::IsPathRooted($manifestResolved)) {
    $manifestResolved = Join-Path $repoRoot $manifestResolved
}
$manifestResolved = (Resolve-Path $manifestResolved).Path

$manifest = Get-Content -LiteralPath $manifestResolved -Raw | ConvertFrom-Json

if ([string]::IsNullOrWhiteSpace($JobId)) {
    if ($manifest.job -and $manifest.job.job_id) {
        $JobId = [string]$manifest.job.job_id
    }
}
if ([string]::IsNullOrWhiteSpace($JobId)) {
    Write-Error "JobId was not supplied and could not be resolved from manifest."
    exit 1
}

if ([string]::IsNullOrWhiteSpace($EvidenceRoot)) {
    $EvidenceRoot = Join-Path $repoRoot ("evidence\jobs\{0}" -f $JobId)
}
elseif (-not [System.IO.Path]::IsPathRooted($EvidenceRoot)) {
    $EvidenceRoot = Join-Path $repoRoot $EvidenceRoot
}

$logsDir = Join-Path $EvidenceRoot "logs"
$screenshotsDir = Join-Path $EvidenceRoot "screenshots"
$reportsDir = Join-Path $EvidenceRoot "reports"
foreach ($dir in @($EvidenceRoot, $logsDir, $screenshotsDir, $reportsDir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

$jobObj = Ensure-ChildObject -Parent $manifest -Name "job"
$qcObj = Ensure-ChildObject -Parent $manifest -Name "qc"
$evidenceObj = Ensure-ChildObject -Parent $manifest -Name "evidence"

Set-ObjectProperty -Object $jobObj -Name "status" -Value $Status
Set-ObjectProperty -Object $jobObj -Name "updated_utc" -Value ((Get-Date).ToUniversalTime().ToString("o"))
Set-ObjectProperty -Object $qcObj -Name "overall" -Value (Get-QcFromStatus -CurrentStatus $Status)

$logs = @()
foreach ($candidate in @($StdoutPath, $StderrPath, $LogPath)) {
    if (-not [string]::IsNullOrWhiteSpace($candidate)) {
        $resolved = $candidate
        if (-not [System.IO.Path]::IsPathRooted($resolved)) {
            $resolved = Join-Path $repoRoot $resolved
        }
        $logs += $resolved
    }
}
Set-ObjectProperty -Object $evidenceObj -Name "logs" -Value $logs

$reportPath = Join-Path $reportsDir "evidence-summary.json"
$summary = [ordered]@{
    job_id      = $JobId
    status      = $Status
    message     = $Message
    exit_code   = $ExitCode
    updated_utc = (Get-Date).ToUniversalTime().ToString("o")
}
$summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $reportPath -Encoding UTF8

$existingReports = @()
if ($evidenceObj.PSObject.Properties["reports"] -and $null -ne $evidenceObj.reports) {
    $existingReports = @($evidenceObj.reports)
}
if ($existingReports -notcontains $reportPath) {
    $existingReports += $reportPath
}
Set-ObjectProperty -Object $evidenceObj -Name "reports" -Value $existingReports
Set-ObjectProperty -Object $evidenceObj -Name "exit_code" -Value $ExitCode
Set-ObjectProperty -Object $evidenceObj -Name "message" -Value $Message

$manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifestResolved -Encoding UTF8

$validatorScript = Join-Path $repoRoot "tools\manifest-validator\validate_manifest.py"
& python $validatorScript $manifestResolved
if ($LASTEXITCODE -ne 0) {
    Write-Error ("Manifest validation failed after evidence update: {0}" -f $manifestResolved)
    exit $LASTEXITCODE
}

Write-Host ("Updated manifest: {0}" -f $manifestResolved)
Write-Host ("Evidence root: {0}" -f $EvidenceRoot)
Write-Output $manifestResolved
