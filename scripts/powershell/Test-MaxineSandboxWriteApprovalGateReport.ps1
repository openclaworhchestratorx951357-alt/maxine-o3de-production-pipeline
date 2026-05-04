param(
    [string]$ReportPath = "examples/manifests/example-sandbox-write-approval-gate-report.json"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$auditScript = Join-Path $repoRoot "tools\audit\verify_sandbox_write_approval_gate_report.py"

if ([System.IO.Path]::IsPathRooted($ReportPath)) {
    $resolvedReport = $ReportPath
}
else {
    $resolvedReport = Join-Path $repoRoot $ReportPath
}

$commandArgs = @(
    $auditScript,
    "--report",
    $resolvedReport
)

$quoted = $commandArgs | ForEach-Object {
    if ($_ -match "\s") { "`"$_`"" } else { "$_" }
}
$commandLine = "python " + ($quoted -join " ")
Write-Host "Command: $commandLine"

& python @commandArgs
exit $LASTEXITCODE
