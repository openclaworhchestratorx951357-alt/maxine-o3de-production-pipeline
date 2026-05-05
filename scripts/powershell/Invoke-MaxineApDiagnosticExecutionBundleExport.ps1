[CmdletBinding()]
param(
    [string]$DiagnosticExecutionPath,
    [string]$DiagnosticExecutionId,

    [string]$DiagnosticExecutionsRoot = "examples/sandbox/ap-diagnostic-executions",
    [string]$PreflightsRoot = "examples/sandbox/ap-execution-preflights",
    [string]$DiagnosticExecutionBundlesRoot = "examples/sandbox/ap-diagnostic-execution-bundles",
    [string]$BundlePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$fallbackNonAdmissions = @(
    "authoritative_writes",
    "asset_processor_execution",
    "o3de_editor_execution",
    "o3de_cli_execution",
    "cache_read",
    "live_asset_database_read",
    "product_resolution",
    "product_id_claims",
    "asset_id_claims",
    "source_uuid_claims",
    "spawning",
    "publishing",
    "production_path_write",
    "cache_path_write",
    "engine_path_write"
)

function Test-IsPathWithin {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CandidatePath,
        [Parameter(Mandatory = $true)]
        [string]$ParentPath
    )

    $candidateAbs = [System.IO.Path]::GetFullPath($CandidatePath)
    $parentAbs = [System.IO.Path]::GetFullPath($ParentPath)
    if ($candidateAbs.Equals($parentAbs, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }

    $prefix = $parentAbs.TrimEnd("\") + "\"
    return $candidateAbs.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-RepoRelativePath {
    param([Parameter(Mandatory = $true)][string]$AbsolutePath)

    $abs = [System.IO.Path]::GetFullPath($AbsolutePath)
    if (-not (Test-IsPathWithin -CandidatePath $abs -ParentPath $repoRoot)) {
        return $abs
    }

    return $abs.Substring($repoRoot.Length).TrimStart("\").Replace("\", "/")
}

function Get-SafeRelativePathAbs {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath,
        [Parameter(Mandatory = $true)]
        [string]$AllowedRootAbs,
        [string]$Label = "path"
    )

    if ([string]::IsNullOrWhiteSpace($RelativePath)) {
        throw "$Label is empty."
    }
    if ([System.IO.Path]::IsPathRooted($RelativePath)) {
        throw "$Label must be relative."
    }
    if ($RelativePath.StartsWith("\") -or $RelativePath.StartsWith("/")) {
        throw "$Label cannot start with slash or backslash."
    }

    $normalized = $RelativePath.Replace("\", "/")
    if (($normalized -split "/") -contains "..") {
        throw "$Label contains parent traversal and is blocked."
    }

    $candidateAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $RelativePath))
    if (-not (Test-IsPathWithin -CandidatePath $candidateAbs -ParentPath $AllowedRootAbs)) {
        throw "$Label escapes the approved sandbox root."
    }

    return $candidateAbs
}

function Resolve-JsonById {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootAbs,
        [Parameter(Mandatory = $true)]
        [string]$IdProperty,
        [Parameter(Mandatory = $true)]
        [string]$IdValue
    )

    if ([string]::IsNullOrWhiteSpace($IdValue)) {
        return $null
    }

    $matches = @()
    foreach ($file in Get-ChildItem -LiteralPath $RootAbs -File -Filter *.json -Recurse -ErrorAction SilentlyContinue) {
        try {
            $item = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
            if ([string]$item.$IdProperty -eq $IdValue) {
                $matches += [ordered]@{ path = $file.FullName; item = $item }
            }
        } catch {
            continue
        }
    }

    if ($matches.Count -eq 0) { return $null }
    if ($matches.Count -gt 1) { throw "$IdProperty '$IdValue' is ambiguous." }
    return $matches[0]
}

function Resolve-DiagnosticExecution {
    param(
        [string]$DiagnosticExecutionPath,
        [string]$DiagnosticExecutionId,
        [string]$RootAbs
    )

    $hasPath = -not [string]::IsNullOrWhiteSpace($DiagnosticExecutionPath)
    $hasId = -not [string]::IsNullOrWhiteSpace($DiagnosticExecutionId)
    if (($hasPath -and $hasId) -or (-not $hasPath -and -not $hasId)) {
        throw "Provide either diagnostic_execution_path or diagnostic_execution_id."
    }

    if ($hasPath) {
        $pathAbs = $null
        if ([System.IO.Path]::IsPathRooted($DiagnosticExecutionPath)) {
            $pathAbs = [System.IO.Path]::GetFullPath($DiagnosticExecutionPath)
            if (-not (Test-IsPathWithin -CandidatePath $pathAbs -ParentPath $RootAbs)) {
                throw "diagnostic_execution_path must remain under ap-diagnostic-executions."
            }
        } else {
            $pathAbs = Get-SafeRelativePathAbs -RelativePath $DiagnosticExecutionPath -AllowedRootAbs $RootAbs -Label "diagnostic_execution_path"
        }

        if (-not (Test-Path -LiteralPath $pathAbs -PathType Leaf)) {
            throw "diagnostic_execution_path not found: $DiagnosticExecutionPath"
        }

        $item = Get-Content -LiteralPath $pathAbs -Raw | ConvertFrom-Json
        return [ordered]@{ path = $pathAbs; item = $item }
    }

    $match = Resolve-JsonById -RootAbs $RootAbs -IdProperty "diagnostic_execution_id" -IdValue $DiagnosticExecutionId
    if ($null -eq $match) {
        throw "diagnostic_execution_id '$DiagnosticExecutionId' not found."
    }
    return $match
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)][object]$InputObject,
        [Parameter(Mandatory = $true)][string]$OutputPath
    )

    $directory = Split-Path -Parent $OutputPath
    if ($directory -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -Path $directory -ItemType Directory -Force | Out-Null
    }

    $json = $InputObject | ConvertTo-Json -Depth 100
    [System.IO.File]::WriteAllText($OutputPath, $json, [System.Text.UTF8Encoding]::new($false))
}

$diagnosticRootAbs = Get-SafeRelativePathAbs -RelativePath $DiagnosticExecutionsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "diagnostic_executions_root"
$preflightsRootAbs = Get-SafeRelativePathAbs -RelativePath $PreflightsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "preflights_root"
$bundlesRootAbs = Get-SafeRelativePathAbs -RelativePath $DiagnosticExecutionBundlesRoot -AllowedRootAbs $sandboxAnchorAbs -Label "diagnostic_execution_bundles_root"
if (-not (Test-Path -LiteralPath $bundlesRootAbs -PathType Container)) {
    New-Item -Path $bundlesRootAbs -ItemType Directory -Force | Out-Null
}

$diagnosticRef = Resolve-DiagnosticExecution -DiagnosticExecutionPath $DiagnosticExecutionPath -DiagnosticExecutionId $DiagnosticExecutionId -RootAbs $diagnosticRootAbs
$diagnostic = $diagnosticRef.item

if ([string]::IsNullOrWhiteSpace([string]$diagnostic.diagnostic_execution_id)) {
    throw "diagnostic execution record is missing diagnostic_execution_id."
}
if ([string]$diagnostic.sandbox_root -ne "examples/sandbox") {
    throw "diagnostic execution sandbox_root must be examples/sandbox."
}

$preflightRef = Resolve-JsonById -RootAbs $preflightsRootAbs -IdProperty "preflight_id" -IdValue ([string]$diagnostic.source_preflight_id)
if ($null -eq $preflightRef) {
    throw "source preflight not found for diagnostic execution record."
}

$bundleId = "ap-diagnostic-execution-bundle-$([Guid]::NewGuid().ToString('N'))"
$manifestRel = $BundlePath
if ([string]::IsNullOrWhiteSpace($manifestRel)) {
    $manifestRel = "$DiagnosticExecutionBundlesRoot/$bundleId/bundle.manifest.json"
} elseif (-not $manifestRel.ToLowerInvariant().EndsWith(".json")) {
    $manifestRel = $manifestRel.TrimEnd("/", "\") + "/bundle.manifest.json"
}

$manifestAbs = Get-SafeRelativePathAbs -RelativePath $manifestRel -AllowedRootAbs $bundlesRootAbs -Label "bundle_path"
$bundleDirAbs = Split-Path -Parent $manifestAbs
if (-not (Test-Path -LiteralPath $bundleDirAbs -PathType Container)) {
    New-Item -Path $bundleDirAbs -ItemType Directory -Force | Out-Null
}

$includedArtifacts = New-Object System.Collections.Generic.List[string]
$copiedArtifactPaths = New-Object System.Collections.Generic.List[string]
$artifactSha = [ordered]@{}

function Add-JsonSnapshot {
    param(
        [Parameter(Mandatory = $true)][object]$InputObject,
        [Parameter(Mandatory = $true)][string]$SnapshotName,
        [Parameter(Mandatory = $true)][string]$ArtifactLabel
    )

    $snapshotAbs = Join-Path $bundleDirAbs $SnapshotName
    Write-JsonFile -InputObject $InputObject -OutputPath $snapshotAbs

    $snapshotRel = Get-RepoRelativePath -AbsolutePath $snapshotAbs
    $includedArtifacts.Add($ArtifactLabel) | Out-Null
    $copiedArtifactPaths.Add($snapshotRel) | Out-Null
    $artifactSha[$snapshotRel] = (Get-FileHash -LiteralPath $snapshotAbs -Algorithm SHA256).Hash
}

function Add-TextSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$SnapshotName,
        [Parameter(Mandatory = $true)][string]$ArtifactLabel
    )

    if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
        return
    }
    if (-not (Test-IsPathWithin -CandidatePath $SourcePath -ParentPath $sandboxAnchorAbs)) {
        throw "$ArtifactLabel source path must remain under sandbox root."
    }

    $extension = [System.IO.Path]::GetExtension($SourcePath).ToLowerInvariant()
    if ($extension -ne ".txt") {
        throw "$ArtifactLabel must be a .txt diagnostic output reference."
    }

    $targetAbs = Join-Path $bundleDirAbs $SnapshotName
    Copy-Item -LiteralPath $SourcePath -Destination $targetAbs -Force

    $targetRel = Get-RepoRelativePath -AbsolutePath $targetAbs
    $includedArtifacts.Add($ArtifactLabel) | Out-Null
    $copiedArtifactPaths.Add($targetRel) | Out-Null
    $artifactSha[$targetRel] = (Get-FileHash -LiteralPath $targetAbs -Algorithm SHA256).Hash
}

Add-JsonSnapshot -InputObject $diagnostic -SnapshotName "ap-diagnostic-execution.snapshot.json" -ArtifactLabel "ap_diagnostic_execution"
Add-JsonSnapshot -InputObject $preflightRef.item -SnapshotName "ap-execution-preflight.snapshot.json" -ArtifactLabel "ap_execution_preflight"

$linkSummary = [ordered]@{
    source_diagnostic_execution_id = [string]$diagnostic.diagnostic_execution_id
    source_preflight_id = [string]$diagnostic.source_preflight_id
    execution_mode = [string]$diagnostic.execution_mode
    execution_status = [string]$diagnostic.execution_status
    command_executed = [bool]$diagnostic.command_executed
    command_allowlisted = [bool]$diagnostic.command_allowlisted
    timeout_seconds = [int]$diagnostic.timeout_seconds
    exit_code = $diagnostic.exit_code
}
Add-JsonSnapshot -InputObject $linkSummary -SnapshotName "diagnostic-link-summary.snapshot.json" -ArtifactLabel "ap_diagnostic_execution_link_summary"

if (-not [string]::IsNullOrWhiteSpace([string]$diagnostic.stdout_path)) {
    $stdoutAbs = Get-SafeRelativePathAbs -RelativePath ([string]$diagnostic.stdout_path) -AllowedRootAbs $sandboxAnchorAbs -Label "stdout_path"
    Add-TextSnapshot -SourcePath $stdoutAbs -SnapshotName "diagnostic.stdout.txt" -ArtifactLabel "diagnostic_stdout_text"
}
if (-not [string]::IsNullOrWhiteSpace([string]$diagnostic.stderr_path)) {
    $stderrAbs = Get-SafeRelativePathAbs -RelativePath ([string]$diagnostic.stderr_path) -AllowedRootAbs $sandboxAnchorAbs -Label "stderr_path"
    Add-TextSnapshot -SourcePath $stderrAbs -SnapshotName "diagnostic.stderr.txt" -ArtifactLabel "diagnostic_stderr_text"
}

$explicitNonAdmissions = @($diagnostic.explicit_non_admissions)
if ($explicitNonAdmissions.Count -eq 0) {
    $explicitNonAdmissions = @($fallbackNonAdmissions)
}

$manifest = [ordered]@{
    schema_version = "1.0.0"
    bundle_id = $bundleId
    source_diagnostic_execution_id = [string]$diagnostic.diagnostic_execution_id
    source_preflight_id = [string]$diagnostic.source_preflight_id
    sandbox_root = "examples/sandbox"
    bundle_path = Get-RepoRelativePath -AbsolutePath $manifestAbs
    included_artifacts = @($includedArtifacts)
    copied_artifact_paths = @($copiedArtifactPaths)
    artifact_sha256 = $artifactSha
    safety_summary = "Sandbox-only AP diagnostic execution bundle export. Copies JSON and stdout/stderr text only and does not copy source assets, binaries, cache, database, or runtime artifacts."
    explicit_non_admissions = @($explicitNonAdmissions)
    created_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

Write-JsonFile -InputObject $manifest -OutputPath $manifestAbs
$manifest | ConvertTo-Json -Depth 100
