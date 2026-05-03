param(
    [string[]]$PathToCheck,
    [string]$PolicyPath = "docs/audits/phase2_sandbox_path_safety_policy.json"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$auditScript = Join-Path $repoRoot "tools\audit\verify_sandbox_path_safety.py"

$commandArgs = @(
    $auditScript,
    "--policy",
    $PolicyPath
)

if ($PathToCheck) {
    foreach ($p in $PathToCheck) {
        $commandArgs += "--path"
        $commandArgs += $p
    }
}

$quoted = $commandArgs | ForEach-Object {
    if ($_ -match "\s") { "`"$_`"" } else { "$_" }
}
$commandLine = "python " + ($quoted -join " ")
Write-Host "Command: $commandLine"

& python @commandArgs
exit $LASTEXITCODE
