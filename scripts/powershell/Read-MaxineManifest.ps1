param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,
    [switch]$AsJson
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "MaxineManifestHelpers.ps1")

$repoRoot = Resolve-MaxineRepoRoot -ScriptRoot $PSScriptRoot
$resolvedPath = Resolve-MaxinePath -Path $ManifestPath -RepoRoot $repoRoot
if (-not (Test-Path -LiteralPath $resolvedPath)) {
    Write-Error ("Manifest not found: {0}" -f $resolvedPath)
    exit 1
}

$manifest = Read-MaxineJsonObject -Path $resolvedPath
if ($AsJson.IsPresent) {
    $manifest | ConvertTo-Json -Depth 40
}
else {
    $manifest
}
