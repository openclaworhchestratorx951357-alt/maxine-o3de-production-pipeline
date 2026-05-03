param(
    [string]$ArtifactPath = "examples/manifests/example-sandbox-rollback-artifact.json"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$auditScript = Join-Path $repoRoot "tools\audit\verify_sandbox_rollback_artifact.py"

$commandArgs = @(
    $auditScript,
    "--artifact", $ArtifactPath
)

$quoted = $commandArgs | ForEach-Object {
    if ($_ -match "\s") { "`"$_`"" } else { "$_" }
}
$commandLine = "python " + ($quoted -join " ")
Write-Host "Command: $commandLine"

& python @commandArgs
exit $LASTEXITCODE
