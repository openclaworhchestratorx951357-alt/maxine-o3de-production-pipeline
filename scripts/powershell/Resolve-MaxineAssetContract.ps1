param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,
    [Parameter(Mandatory = $true)]
    [string]$SourceAsset,
    [string]$Lane = "",
    [string]$OutputPath = "",
    [ValidateSet("planned", "unresolved", "resolved")]
    [string]$Status = "planned"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$resolverScript = Join-Path $repoRoot "tools\asset-resolver\resolve_asset_contract.py"

$manifestResolved = $ManifestPath
if (-not [System.IO.Path]::IsPathRooted($manifestResolved)) {
    $manifestResolved = Join-Path $repoRoot $manifestResolved
}
$manifestResolved = (Resolve-Path $manifestResolved).Path

$args = @(
    $resolverScript,
    "--manifest", $manifestResolved,
    "--source-asset", $SourceAsset,
    "--status", $Status
)

if (-not [string]::IsNullOrWhiteSpace($Lane)) {
    $args += @("--lane", $Lane)
}
if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
    $outPathResolved = $OutputPath
    if (-not [System.IO.Path]::IsPathRooted($outPathResolved)) {
        $outPathResolved = Join-Path $repoRoot $outPathResolved
    }
    $args += @("--output", $outPathResolved)
}

$commandDisplay = "python " + (($args | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join " ")
Write-Host ("Running command: {0}" -f $commandDisplay)

& python @args
$exitCode = $LASTEXITCODE

exit $exitCode
