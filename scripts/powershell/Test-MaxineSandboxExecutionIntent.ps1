param(
    [string]$IntentPath = "examples/manifests/example-sandbox-execution-intent.json",
    [string]$FinalPreflightReportPath = "examples/manifests/example-sandbox-write-final-preflight-report.json"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$auditScript = Join-Path $repoRoot "tools\audit\verify_sandbox_execution_intent.py"

if ([System.IO.Path]::IsPathRooted($IntentPath)) {
    $resolvedIntentPath = $IntentPath
}
else {
    $resolvedIntentPath = Join-Path $repoRoot $IntentPath
}

if ([System.IO.Path]::IsPathRooted($FinalPreflightReportPath)) {
    $resolvedReportPath = $FinalPreflightReportPath
}
else {
    $resolvedReportPath = Join-Path $repoRoot $FinalPreflightReportPath
}

$commandArgs = @(
    $auditScript,
    "--intent",
    $resolvedIntentPath,
    "--final-preflight-report",
    $resolvedReportPath
)

$quoted = $commandArgs | ForEach-Object {
    if ($_ -match "\s") { "`"$_`"" } else { "$_" }
}
$commandLine = "python " + ($quoted -join " ")
Write-Host "Command: $commandLine"

& python @commandArgs
exit $LASTEXITCODE
