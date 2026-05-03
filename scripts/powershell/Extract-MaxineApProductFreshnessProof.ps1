param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [string]$OutputPath = "",
    [int]$MaxStaleSeconds = 0
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$extractScript = Join-Path $repoRoot "tools\asset-resolver\extract_ap_product_freshness_proof.py"

$commandArgs = @(
    $extractScript,
    "--manifest", $ManifestPath,
    "--max-stale-seconds", $MaxStaleSeconds
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
