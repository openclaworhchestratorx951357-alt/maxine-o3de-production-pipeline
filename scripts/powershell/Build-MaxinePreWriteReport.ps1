param(
    [Parameter(Mandatory = $true)]
    [string]$ProposalPath,

    [Parameter(Mandatory = $true)]
    [string]$ApprovalValidationPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$builderScript = Join-Path $repoRoot "tools\asset-resolver\build_pre_write_report.py"

$commandArgs = @(
    $builderScript,
    "--proposal", $ProposalPath,
    "--approval-validation", $ApprovalValidationPath,
    "--output", $OutputPath
)

$quoted = $commandArgs | ForEach-Object {
    if ($_ -match "\s") { "`"$_`"" } else { "$_" }
}
$commandLine = "python " + ($quoted -join " ")
Write-Host "Command: $commandLine"

& python @commandArgs
exit $LASTEXITCODE
