param(
    [string]$PlanPath = "examples/manifests/example-sandbox-write-plan.json"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$auditScript = Join-Path $repoRoot "tools\audit\verify_sandbox_write_plan.py"
$resolvedPlan = Join-Path $repoRoot $PlanPath

$commandArgs = @(
    $auditScript,
    "--plan",
    $resolvedPlan
)

$quoted = $commandArgs | ForEach-Object {
    if ($_ -match "\s") { "`"$_`"" } else { "$_" }
}
$commandLine = "python " + ($quoted -join " ")
Write-Host "Command: $commandLine"

& python @commandArgs
exit $LASTEXITCODE
