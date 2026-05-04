[CmdletBinding()]
param(
    [string]$ProjectRoot = ".",
    [string]$InventoryRoot = "examples/sandbox/project-inventory",
    [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))
$inventoryRootAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox\project-inventory"))
$evidenceRootAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "evidence"))

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
    param(
        [Parameter(Mandatory = $true)]
        [string]$AbsolutePath
    )

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

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath
    )

    $directory = Split-Path -Parent $OutputPath
    if ($directory -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -Path $directory -ItemType Directory -Force | Out-Null
    }

    $json = $InputObject | ConvertTo-Json -Depth 100
    [System.IO.File]::WriteAllText($OutputPath, $json, [System.Text.UTF8Encoding]::new($false))
}

function Add-UniqueRelPath {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [System.Collections.Generic.HashSet[string]]$Set,
        [string]$AbsolutePath
    )

    if ([string]::IsNullOrWhiteSpace($AbsolutePath)) {
        return
    }

    if (-not (Test-Path -LiteralPath $AbsolutePath)) {
        return
    }

    $Set.Add((Get-RepoRelativePath -AbsolutePath $AbsolutePath)) | Out-Null
}

function Find-ProjectJsonCandidates {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRootAbs
    )

    $paths = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

    foreach ($rel in @(
        "project.json",
        "user/project.json",
        "Projects/MaxineShow/project.json",
        "o3de/project.json"
    )) {
        $candidate = [System.IO.Path]::GetFullPath((Join-Path $ProjectRootAbs $rel))
        Add-UniqueRelPath -Set $paths -AbsolutePath $candidate
    }

    foreach ($file in Get-ChildItem -LiteralPath $ProjectRootAbs -File -Filter project.json -Recurse -Depth 5 -ErrorAction SilentlyContinue) {
        Add-UniqueRelPath -Set $paths -AbsolutePath $file.FullName
    }

    return @($paths)
}

function Get-GemNames {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [array]$ProjectJsonObjects,
        [Parameter(Mandatory = $true)]
        [string]$ProjectRootAbs
    )

    $names = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

    foreach ($projectJson in $ProjectJsonObjects) {
        foreach ($source in @($projectJson.gem_names, $projectJson.gems, $projectJson.Gems)) {
            foreach ($value in @($source)) {
                if ([string]::IsNullOrWhiteSpace([string]$value)) { continue }
                $names.Add([string]$value) | Out-Null
            }
        }

        foreach ($pathValue in @($projectJson.external_subdirectories, $projectJson.external_subdirs)) {
            foreach ($entry in @($pathValue)) {
                if ([string]::IsNullOrWhiteSpace([string]$entry)) { continue }
                $names.Add([System.IO.Path]::GetFileName([string]$entry)) | Out-Null
            }
        }
    }

    foreach ($gemJson in Get-ChildItem -LiteralPath $ProjectRootAbs -File -Filter gem.json -Recurse -Depth 6 -ErrorAction SilentlyContinue) {
        try {
            $parsed = Get-Content -LiteralPath $gemJson.FullName -Raw | ConvertFrom-Json
            foreach ($candidate in @($parsed.gem_name, $parsed.GemName, $parsed.name, $parsed.Name)) {
                if ([string]::IsNullOrWhiteSpace([string]$candidate)) { continue }
                $names.Add([string]$candidate) | Out-Null
            }
        } catch {
            continue
        }
    }

    foreach ($gemDir in Get-ChildItem -LiteralPath (Join-Path $repoRoot "o3de/gems") -Directory -ErrorAction SilentlyContinue) {
        if ([string]::IsNullOrWhiteSpace($gemDir.Name) -or $gemDir.Name -eq ".gitkeep") { continue }
        $names.Add($gemDir.Name) | Out-Null
    }

    return @($names | Sort-Object)
}

function Get-KnownFoldersByName {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootAbs,
        [Parameter(Mandatory = $true)]
        [string[]]$Names
    )

    $set = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($dir in Get-ChildItem -LiteralPath $RootAbs -Directory -Recurse -Depth 6 -ErrorAction SilentlyContinue) {
        if ($Names -contains $dir.Name) {
            Add-UniqueRelPath -Set $set -AbsolutePath $dir.FullName
        }
    }

    return @($set | Sort-Object)
}

function Get-PathHintsFromEvidence {
    param(
        [Parameter(Mandatory = $true)]
        [string]$EvidenceRootAbs
    )

    $projectHints = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    $o3deHints = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    $assetProcessorHints = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    $cacheHints = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

    if (-not (Test-Path -LiteralPath $EvidenceRootAbs -PathType Container)) {
        return [ordered]@{
            evidence_file_count = 0
            project_path_hints = @()
            o3de_path_hints = @()
            asset_processor_path_hints = @()
            cache_path_hints = @()
        }
    }

    $jsonFiles = Get-ChildItem -LiteralPath $EvidenceRootAbs -File -Filter *.json -ErrorAction SilentlyContinue
    foreach ($file in $jsonFiles) {
        $raw = ""
        try {
            $raw = Get-Content -LiteralPath $file.FullName -Raw
        } catch {
            continue
        }

        foreach ($match in [System.Text.RegularExpressions.Regex]::Matches($raw, '"([^"]+)"')) {
            $text = [string]$match.Groups[1].Value
            if ([string]::IsNullOrWhiteSpace($text)) { continue }
            $lower = $text.ToLowerInvariant()

            if ($lower.Contains("project") -and ($lower.Contains("path") -or $lower.EndsWith("project.json"))) {
                $projectHints.Add($text) | Out-Null
            }
            if ($lower.Contains("o3de") -or $lower.Contains("engine")) {
                $o3deHints.Add($text) | Out-Null
            }
            if ($lower.Contains("assetprocessor") -or $lower.Contains("apmetadata") -or $lower.Contains("assetdb")) {
                $assetProcessorHints.Add($text) | Out-Null
            }
            if ($lower.Contains("cache")) {
                $cacheHints.Add($text) | Out-Null
            }
        }
    }

    return [ordered]@{
        evidence_file_count = @($jsonFiles).Count
        project_path_hints = @($projectHints | Sort-Object | Select-Object -First 50)
        o3de_path_hints = @($o3deHints | Sort-Object | Select-Object -First 50)
        asset_processor_path_hints = @($assetProcessorHints | Sort-Object | Select-Object -First 50)
        cache_path_hints = @($cacheHints | Sort-Object | Select-Object -First 50)
    }
}

if (-not (Test-Path -LiteralPath $inventoryRootAbs -PathType Container)) {
    New-Item -Path $inventoryRootAbs -ItemType Directory -Force | Out-Null
}

$projectRootAbs = $null
if ([System.IO.Path]::IsPathRooted($ProjectRoot)) {
    $projectRootAbs = [System.IO.Path]::GetFullPath($ProjectRoot)
    if (-not (Test-IsPathWithin -CandidatePath $projectRootAbs -ParentPath $repoRoot)) {
        throw "project_root must be within repository root for read-only inventory."
    }
} else {
    $projectRootAbs = Get-SafeRelativePathAbs -RelativePath $ProjectRoot -AllowedRootAbs $repoRoot -Label "project_root"
}

if (-not (Test-Path -LiteralPath $projectRootAbs -PathType Container)) {
    throw "project_root does not exist: $ProjectRoot"
}

$inventoryId = "sandbox-project-inventory-$([Guid]::NewGuid().ToString('N'))"
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = "$InventoryRoot/$inventoryId.json"
}
$outputAbs = Get-SafeRelativePathAbs -RelativePath $OutputPath -AllowedRootAbs $inventoryRootAbs -Label "output_path"

$projectJsonRelCandidates = Find-ProjectJsonCandidates -ProjectRootAbs $projectRootAbs
$projectJsonObjects = @()
$projectJsonRecords = @()
foreach ($rel in $projectJsonRelCandidates) {
    $abs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $rel))
    $exists = Test-Path -LiteralPath $abs -PathType Leaf
    $parsed = $false
    $summary = $null
    if ($exists) {
        try {
            $obj = Get-Content -LiteralPath $abs -Raw | ConvertFrom-Json
            $parsed = $true
            $projectJsonObjects += $obj
            $summary = [ordered]@{
                project_name = $obj.project_name
                project_id = $obj.project_id
                version = $obj.version
            }
        } catch {
            $parsed = $false
        }
    }

    $projectJsonRecords += [ordered]@{
        path = $rel
        exists = $exists
        parsed = $parsed
        summary = $summary
    }
}

$knownAssetFolders = Get-KnownFoldersByName -RootAbs $projectRootAbs -Names @(
    "Assets", "assets", "Materials", "materials", "Prefabs", "prefabs", "Models", "models", "Textures", "textures", "Levels", "levels", "Scripts", "scripts", "Source", "source"
)

$generatedCandidateFolders = Get-KnownFoldersByName -RootAbs $projectRootAbs -Names @(
    "generated", "Generated", "generated_assets", "generated-assets", "autogen", "outputs", "Output", "maxine_generated"
)

$sandboxEvidenceFolders = @(
    "examples/sandbox/logs",
    "examples/sandbox/receipts",
    "examples/sandbox/review-packets",
    "examples/sandbox/review-decisions",
    "examples/sandbox/workflow-runs",
    "examples/sandbox/evidence-bundles",
    "examples/sandbox/operator-reports",
    "examples/sandbox/project-inventory"
)

$o3deProjectPathMetadata = [ordered]@{
    repository_root = $repoRoot
    project_root = $projectRootAbs
    project_root_relative = Get-RepoRelativePath -AbsolutePath $projectRootAbs
    project_json_candidate_count = @($projectJsonRecords).Count
    project_json_existing_count = @($projectJsonRecords | Where-Object { $_.exists }).Count
    o3de_directories = @(
        "o3de",
        "o3de/gems",
        "o3de/editor-automation",
        "o3de/prefab-publication"
    ) | ForEach-Object {
        $abs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $_.Replace("/", "\")))
        [ordered]@{
            path = $_
            exists = (Test-Path -LiteralPath $abs -PathType Container)
        }
    }
}

$pathHints = Get-PathHintsFromEvidence -EvidenceRootAbs $evidenceRootAbs

$inventory = [ordered]@{
    schema_version = "1.0.0"
    command_name = "Invoke-MaxineProjectInventoryRead.ps1"
    inventory_id = $inventoryId
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    sandbox_root = "examples/sandbox"
    inventory_path = Get-RepoRelativePath -AbsolutePath $outputAbs
    project_root = Get-RepoRelativePath -AbsolutePath $projectRootAbs
    project_json_candidates = @($projectJsonRecords)
    gem_names = @(Get-GemNames -ProjectJsonObjects $projectJsonObjects -ProjectRootAbs $projectRootAbs)
    known_asset_folders = @($knownAssetFolders)
    generated_asset_candidate_folders = @($generatedCandidateFolders)
    sandbox_evidence_folders = @($sandboxEvidenceFolders)
    o3de_project_path_metadata = $o3deProjectPathMetadata
    configured_non_executed_path_hints = $pathHints
    safety = [ordered]@{
        read_only_project_scan = $true
        writes_limited_to_sandbox_inventory = $true
        o3de_editor_execution_admitted = $false
        asset_processor_execution_admitted = $false
        product_resolution_admitted = $false
        asset_id_claims_admitted = $false
        spawning_admitted = $false
        publishing_admitted = $false
        authoritative_writes_admitted = $false
    }
}

Write-JsonFile -InputObject $inventory -OutputPath $outputAbs
$inventory | ConvertTo-Json -Depth 100
