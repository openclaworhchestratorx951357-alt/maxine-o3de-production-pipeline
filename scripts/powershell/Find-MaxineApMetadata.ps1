param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,

    [string]$OutputPath = "",
    [string]$CandidateFile = "",
    [int]$MaxFilesPerGlob = 100,
    [ValidateSet("true", "false")]
    [string]$IncludeHashes = "false"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$discoverScript = Join-Path $repoRoot "tools\asset-resolver\discover_ap_metadata_sources.py"

$commandArgs = @(
    $discoverScript,
    "--manifest", $ManifestPath,
    "--project-path", $ProjectPath,
    "--max-files-per-glob", $MaxFilesPerGlob,
    "--include-hashes", $IncludeHashes
)

if ($OutputPath) {
    $commandArgs += @("--output", $OutputPath)
}

if ($CandidateFile) {
    $commandArgs += @("--candidate-file", $CandidateFile)
}

$quoted = $commandArgs | ForEach-Object {
    if ($_ -match "\s") { "`"$_`"" } else { "$_" }
}
$commandLine = "python " + ($quoted -join " ")
Write-Host "Command: $commandLine"

& python @commandArgs
exit $LASTEXITCODE
