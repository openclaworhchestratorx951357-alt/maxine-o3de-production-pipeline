param(
    [switch]$Strict
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$args = @("tools/validation/validate_all.py")
if ($Strict) {
    Write-Host "Strict switch is accepted for operator ergonomics; validate_all keeps integration checks skipped unless explicitly requested."
}
Push-Location $repoRoot
try {
    python @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
