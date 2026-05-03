param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [string[]]$DatabasePath = @(),
    [string]$ProjectPath = "",
    [string]$SourceAsset = "",
    [string]$OutputPath = "",
    [int]$MaxRowsPerTable = 25,
    [string[]]$SourceTable = @(),
    [string[]]$ProductTable = @(),
    [string[]]$JobTable = @(),
    [string[]]$DependencyTable = @()
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$mapScript = Join-Path $repoRoot "tools\asset-resolver\map_ap_source_product_rows.py"

$commandArgs = @(
    $mapScript,
    "--manifest", $ManifestPath,
    "--max-rows-per-table", $MaxRowsPerTable
)

foreach ($db in $DatabasePath) {
    if ($db) {
        $commandArgs += @("--database", $db)
    }
}

if ($ProjectPath) {
    $commandArgs += @("--project-path", $ProjectPath)
}

if ($SourceAsset) {
    $commandArgs += @("--source-asset", $SourceAsset)
}

if ($OutputPath) {
    $commandArgs += @("--output", $OutputPath)
}

foreach ($name in $SourceTable) {
    if ($name) {
        $commandArgs += @("--source-table", $name)
    }
}

foreach ($name in $ProductTable) {
    if ($name) {
        $commandArgs += @("--product-table", $name)
    }
}

foreach ($name in $JobTable) {
    if ($name) {
        $commandArgs += @("--job-table", $name)
    }
}

foreach ($name in $DependencyTable) {
    if ($name) {
        $commandArgs += @("--dependency-table", $name)
    }
}

$quoted = $commandArgs | ForEach-Object {
    if ($_ -match "\s") { "`"$_`"" } else { "$_" }
}
$commandLine = "python " + ($quoted -join " ")
Write-Host "Command: $commandLine"

& python @commandArgs
exit $LASTEXITCODE
