param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [string]$OutputPath = "",
    [string]$TargetPlatform = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$extractScript = Join-Path $repoRoot "tools\asset-resolver\extract_ap_platform_proof.py"

$commandArgs = @(
    $extractScript,
    "--manifest", $ManifestPath
)

if ($OutputPath) {
    $commandArgs += @("--output", $OutputPath)
}

if ($TargetPlatform) {
    $commandArgs += @("--target-platform", $TargetPlatform)
}

$quoted = $commandArgs | ForEach-Object {
    if ($_ -match "\s") { "`"$_`"" } else { "$_" }
}
$commandLine = "python " + ($quoted -join " ")
Write-Host "Command: $commandLine"

& python @commandArgs
exit $LASTEXITCODE
