param(
    [Parameter(Mandatory = $true)]
    [string]$PreWriteReportPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$validatorScript = Join-Path $repoRoot "tools\asset-resolver\validate_execution_gate_policy.py"

$commandArgs = @(
    $validatorScript,
    "--pre-write-report", $PreWriteReportPath,
    "--output", $OutputPath
)

$quoted = $commandArgs | ForEach-Object {
    if ($_ -match "\s") { "`"$_`"" } else { "$_" }
}
$commandLine = "python " + ($quoted -join " ")
Write-Host "Command: $commandLine"

& python @commandArgs
exit $LASTEXITCODE
