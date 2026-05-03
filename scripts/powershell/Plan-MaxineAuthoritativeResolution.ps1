param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [string]$PlanSchema = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$plannerScript = Join-Path $repoRoot "tools\asset-resolver\plan_authoritative_resolution.py"

$commandArgs = @(
    $plannerScript,
    "--manifest", $ManifestPath,
    "--output", $OutputPath
)

if ($PlanSchema) {
    $commandArgs += @("--plan-schema", $PlanSchema)
}

$quoted = $commandArgs | ForEach-Object {
    if ($_ -match "\s") { "`"$_`"" } else { "$_" }
}
$commandLine = "python " + ($quoted -join " ")
Write-Host "Command: $commandLine"

& python @commandArgs
exit $LASTEXITCODE
