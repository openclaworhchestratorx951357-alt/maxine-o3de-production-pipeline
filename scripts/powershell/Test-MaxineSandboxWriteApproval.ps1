param(
    [string]$ApprovalPath = "examples/manifests/example-sandbox-write-approval.json",
    [string]$DryRunReportPath = "examples/manifests/example-sandbox-write-dry-run-report.json"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$auditScript = Join-Path $repoRoot "tools\audit\verify_sandbox_write_approval.py"

if ([System.IO.Path]::IsPathRooted($ApprovalPath)) {
    $resolvedApproval = $ApprovalPath
}
else {
    $resolvedApproval = Join-Path $repoRoot $ApprovalPath
}

if ([System.IO.Path]::IsPathRooted($DryRunReportPath)) {
    $resolvedDryRun = $DryRunReportPath
}
else {
    $resolvedDryRun = Join-Path $repoRoot $DryRunReportPath
}

$commandArgs = @(
    $auditScript,
    "--approval",
    $resolvedApproval,
    "--dry-run-report",
    $resolvedDryRun
)

$quoted = $commandArgs | ForEach-Object {
    if ($_ -match "\s") { "`"$_`"" } else { "$_" }
}
$commandLine = "python " + ($quoted -join " ")
Write-Host "Command: $commandLine"

& python @commandArgs
exit $LASTEXITCODE
