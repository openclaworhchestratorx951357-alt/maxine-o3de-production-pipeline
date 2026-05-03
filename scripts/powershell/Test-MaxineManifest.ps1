param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
$validatorPath = Join-Path $repoRoot "tools\\manifest-validator\\validate_manifest.py"
$manifestResolved = (Resolve-Path $ManifestPath).Path

$commandDisplay = "python `"$validatorPath`" `"$manifestResolved`""
Write-Host "Running command: $commandDisplay"

& python $validatorPath $manifestResolved
$exitCode = $LASTEXITCODE

exit $exitCode
