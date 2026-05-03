param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [string]$OutputPath = "",
    [double]$MinSourceConfidence = 0.70
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$extractScript = Join-Path $repoRoot "tools\asset-resolver\extract_ap_job_state_proof.py"

$commandArgs = @(
    $extractScript,
    "--manifest", $ManifestPath,
    "--min-source-confidence", $MinSourceConfidence
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
