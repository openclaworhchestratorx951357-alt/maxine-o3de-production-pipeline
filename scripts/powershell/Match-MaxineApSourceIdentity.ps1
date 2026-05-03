param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [string]$SourceAsset = "",
    [string]$OutputPath = "",
    [double]$MinConfidence = 0.50
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$matchScript = Join-Path $repoRoot "tools\asset-resolver\match_ap_source_identity.py"

$commandArgs = @(
    $matchScript,
    "--manifest", $ManifestPath,
    "--min-confidence", $MinConfidence
)

if ($SourceAsset) {
    $commandArgs += @("--source-asset", $SourceAsset)
}

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
