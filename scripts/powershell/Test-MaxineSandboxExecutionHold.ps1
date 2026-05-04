param(
    [string]$HoldPath = "examples/manifests/example-sandbox-execution-hold.json"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$auditScript = Join-Path $repoRoot "tools\audit\verify_sandbox_execution_hold.py"

if ([System.IO.Path]::IsPathRooted($HoldPath)) {
    $resolvedHoldPath = $HoldPath
}
else {
    $resolvedHoldPath = Join-Path $repoRoot $HoldPath
}

$commandArgs = @(
    $auditScript,
    "--hold",
    $resolvedHoldPath
)

$quoted = $commandArgs | ForEach-Object {
    if ($_ -match "\s") { "`"$_`"" } else { "$_" }
}
$commandLine = "python " + ($quoted -join " ")
Write-Host "Command: $commandLine"

& python @commandArgs
exit $LASTEXITCODE
