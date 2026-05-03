param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [Parameter(Mandatory = $true)]
    [string]$SourceAsset,

    [string]$ProjectPath = "",
    [string]$CachePath = "",
    [string]$Lane = "",
    [string]$OutputPath = "",
    [int]$MaxCandidates = 25
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$probeScript = Join-Path $repoRoot "tools\asset-resolver\probe_o3de_asset_filesystem.py"

$commandArgs = @(
    $probeScript,
    "--manifest", $ManifestPath,
    "--source-asset", $SourceAsset,
    "--max-candidates", $MaxCandidates
)

if ($ProjectPath) {
    $commandArgs += @("--project-path", $ProjectPath)
}

if ($CachePath) {
    $commandArgs += @("--cache-path", $CachePath)
}

if ($Lane) {
    $commandArgs += @("--lane", $Lane)
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
