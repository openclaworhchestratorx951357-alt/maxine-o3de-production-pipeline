param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [string]$OutputPath = "",
    [double]$MinSourceConfidence = 0.70,
    [double]$MinProductConfidence = 0.40
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$matchScript = Join-Path $repoRoot "tools\asset-resolver\match_ap_product_candidates.py"

$commandArgs = @(
    $matchScript,
    "--manifest", $ManifestPath,
    "--min-source-confidence", $MinSourceConfidence,
    "--min-product-confidence", $MinProductConfidence
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
