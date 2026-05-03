param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [string]$ProjectRoot = "",
    [string]$CacheRoot = "",
    [string[]]$Root = @(),
    [string]$OutputPath = "",
    [ValidateSet("true", "false")]
    [string]$RequireExistingRequired = "false"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$validateScript = Join-Path $repoRoot "tools\asset-resolver\validate_ap_product_files.py"

$commandArgs = @(
    $validateScript,
    "--manifest", $ManifestPath,
    "--require-existing-required", $RequireExistingRequired
)

if ($ProjectRoot) {
    $commandArgs += @("--project-root", $ProjectRoot)
}

if ($CacheRoot) {
    $commandArgs += @("--cache-root", $CacheRoot)
}

foreach ($r in $Root) {
    if ($r) {
        $commandArgs += @("--root", $r)
    }
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
