param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [string[]]$DatabasePath = @(),
    [string]$ProjectPath = "",
    [string]$OutputPath = "",
    [int]$MaxRowCountTables = 50,
    [int]$MaxIndexesPerTable = 50,
    [ValidateSet("true", "false")]
    [string]$SkipRowCounts = "false"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$inspectScript = Join-Path $repoRoot "tools\asset-resolver\inspect_ap_database_schema.py"

$commandArgs = @(
    $inspectScript,
    "--manifest", $ManifestPath,
    "--max-row-count-tables", $MaxRowCountTables,
    "--max-indexes-per-table", $MaxIndexesPerTable,
    "--skip-row-counts", $SkipRowCounts
)

foreach ($db in $DatabasePath) {
    if ($db) {
        $commandArgs += @("--database", $db)
    }
}

if ($ProjectPath) {
    $commandArgs += @("--project-path", $ProjectPath)
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
