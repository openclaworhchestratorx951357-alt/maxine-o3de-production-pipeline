param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [string]$OutputPath = "",
    [double]$MinSourceConfidence = 0.70,
    [double]$MinProductConfidence = 0.40,
    [ValidateSet("true", "false")]
    [string]$RequireExistingRequired = "true"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$evaluateScript = Join-Path $repoRoot "tools\asset-resolver\evaluate_ap_resolver_readiness.py"

$commandArgs = @(
    $evaluateScript,
    "--manifest", $ManifestPath,
    "--min-source-confidence", $MinSourceConfidence,
    "--min-product-confidence", $MinProductConfidence,
    "--require-existing-required", $RequireExistingRequired
)

if ($OutputPath) {
    $commandArgs += @("--output", $OutputPath)
}

$quoted = $commandArgs | ForEach-Object {
    if ($_ -match "\s") { "`"$_`"" } else { "$_" }
}
$commandLine = "python " + ($quoted -join " ")
Write-Host "Command: $commandLine"

& python @commandArgs
exit $LASTEXITCODE
