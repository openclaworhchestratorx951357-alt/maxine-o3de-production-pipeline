[CmdletBinding(DefaultParameterSetName = "ByCandidates")]
param(
    [Parameter(Mandatory = $true, ParameterSetName = "ByCandidates")]
    [string[]]$CandidatePaths,

    [Parameter(Mandatory = $true, ParameterSetName = "ByJsonFile")]
    [string]$CandidatePathsJsonPath,

    [Parameter(Mandatory = $true, ParameterSetName = "ByProjectInventoryPath")]
    [string]$ProjectInventoryPath,

    [Parameter(Mandatory = $true, ParameterSetName = "ByProjectInventoryId")]
    [string]$ProjectInventoryId,

    [string]$PathSource,
    [string]$OutputPath,

    [string]$ProjectInventoryRoot = "examples/sandbox/project-inventory",
    [string]$DiscoveryRoot = "examples/sandbox/ap-binary-discovery"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$explicitNonAdmissions = @(
    "authoritative_writes",
    "asset_processor_execution",
    "real_asset_processor_execution",
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
        [Parameter(Mandatory = $true)][string]$CandidatePath,
        [Parameter(Mandatory = $true)][string]$ParentPath
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
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$AllowedRootAbs,
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

function Resolve-PathWithinRepo {
    param(
        [Parameter(Mandatory = $true)][string]$InputPath,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $resolved = $null
    if ([System.IO.Path]::IsPathRooted($InputPath)) {
        $resolved = [System.IO.Path]::GetFullPath($InputPath)
        if (-not (Test-IsPathWithin -CandidatePath $resolved -ParentPath $repoRoot)) {
            throw "$Label must remain within repository root."
        }
    } else {
        if ($InputPath.StartsWith("\") -or $InputPath.StartsWith("/")) {
            throw "$Label cannot start with slash or backslash."
        }

        $normalized = $InputPath.Replace("\", "/")
        if (($normalized -split "/") -contains "..") {
            throw "$Label contains parent traversal and is blocked."
        }

        $resolved = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $InputPath))
        if (-not (Test-IsPathWithin -CandidatePath $resolved -ParentPath $repoRoot)) {
            throw "$Label escapes repository root."
        }
    }

    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "$Label not found: $InputPath"
    }

    return $resolved
}

function Resolve-JsonById {
    param(
        [Parameter(Mandatory = $true)][string]$RootAbs,
        [Parameter(Mandatory = $true)][string]$IdProperty,
        [Parameter(Mandatory = $true)][string]$IdValue
    )

    if ([string]::IsNullOrWhiteSpace($IdValue)) {
        return $null
    }

    if (-not (Test-Path -LiteralPath $RootAbs -PathType Container)) {
        return $null
    }

    $matches = @()
    foreach ($file in Get-ChildItem -LiteralPath $RootAbs -File -Filter *.json -ErrorAction SilentlyContinue) {
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

function Resolve-ProjectInventoryByPath {
    param(
        [Parameter(Mandatory = $true)][string]$InputPath,
        [Parameter(Mandatory = $true)][string]$RootAbs
    )

    $pathAbs = $null
    if ([System.IO.Path]::IsPathRooted($InputPath)) {
        $pathAbs = [System.IO.Path]::GetFullPath($InputPath)
        if (-not (Test-IsPathWithin -CandidatePath $pathAbs -ParentPath $RootAbs)) {
            throw "project_inventory_path must remain within approved sandbox root."
        }
    } else {
        $pathAbs = Get-SafeRelativePathAbs -RelativePath $InputPath -AllowedRootAbs $RootAbs -Label "project_inventory_path"
    }

    if (-not (Test-Path -LiteralPath $pathAbs -PathType Leaf)) {
        throw "project_inventory_path not found: $InputPath"
    }

    try {
        $item = Get-Content -LiteralPath $pathAbs -Raw | ConvertFrom-Json
    } catch {
        throw "project_inventory_path is not valid JSON: $InputPath"
    }

    return [ordered]@{ path = $pathAbs; item = $item }
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)][object]$InputObject,
        [Parameter(Mandatory = $true)][string]$OutputPath
    )

    $dir = Split-Path -Parent $OutputPath
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -Path $dir -ItemType Directory -Force | Out-Null
    }

    $json = $InputObject | ConvertTo-Json -Depth 100
    [System.IO.File]::WriteAllText($OutputPath, $json, [System.Text.UTF8Encoding]::new($false))
}

function Get-BinaryKindFromPath {
    param([Parameter(Mandatory = $true)][string]$PathText)

    $name = [System.IO.Path]::GetFileName($PathText).ToLowerInvariant()
    if ($name -eq "assetprocessorbatch.exe") { return "AssetProcessorBatch" }
    if ($name -eq "assetprocessor.exe") { return "AssetProcessor" }
    return "unknown"
}

function Get-CandidateFromText {
    param([Parameter(Mandatory = $true)][string]$PathText)

    $trimmed = $PathText.Trim()
    if ([string]::IsNullOrWhiteSpace($trimmed)) {
        return [ordered]@{ accepted = $false; reason = "candidate path is empty." }
    }
    if ($trimmed.Contains("`n") -or $trimmed.Contains("`r")) {
        return [ordered]@{ accepted = $false; reason = "candidate path contains newline characters and is blocked." }
    }
    if ($trimmed -match "[|><;&`]") {
        return [ordered]@{ accepted = $false; reason = "candidate path contains shell operators/pipelines/redirection and is blocked." }
    }
    if ($trimmed.Contains("*") -or $trimmed.Contains("?")) {
        return [ordered]@{ accepted = $false; reason = "candidate path contains wildcard tokens and is blocked." }
    }

    $normalizedSlash = $trimmed.Replace("\", "/")
    if (($normalizedSlash -split "/") -contains "..") {
        return [ordered]@{ accepted = $false; reason = "candidate path contains parent traversal and is blocked." }
    }

    $lower = $normalizedSlash.ToLowerInvariant()
    if ($lower -match "(^|/)cache(/|$)") {
        return [ordered]@{ accepted = $false; reason = "cache paths are blocked as binary candidates." }
    }
    if ($lower.Contains("assetdb.sqlite")) {
        return [ordered]@{ accepted = $false; reason = "assetdb.sqlite paths are blocked as binary candidates." }
    }

    $normalized = $null
    if ([System.IO.Path]::IsPathRooted($trimmed)) {
        try {
            $normalized = [System.IO.Path]::GetFullPath($trimmed)
        } catch {
            return [ordered]@{ accepted = $false; reason = "candidate path cannot be normalized." }
        }
    } else {
        $normalized = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $trimmed))
    }

    return [ordered]@{
        accepted = $true
        normalized = $normalized
        kind = Get-BinaryKindFromPath -PathText $normalized
    }
}

function Get-CandidateHintsFromProjectInventory {
    param([Parameter(Mandatory = $true)][object]$Inventory)

    $hints = New-Object System.Collections.Generic.List[string]

    if ($null -ne $Inventory.configured_non_executed_path_hints) {
        foreach ($entry in @($Inventory.configured_non_executed_path_hints)) {
            if ($entry -is [string] -and -not [string]::IsNullOrWhiteSpace($entry)) {
                $hints.Add($entry.Trim()) | Out-Null
            }
        }
    }

    if ($null -ne $Inventory.o3de_project_path_metadata) {
        $meta = $Inventory.o3de_project_path_metadata
        foreach ($key in @("asset_processor_path_hints", "asset_processor_batch_path_hints", "o3de_cli_path_hints")) {
            if ($null -ne $meta.$key) {
                foreach ($entry in @($meta.$key)) {
                    if ($entry -is [string] -and -not [string]::IsNullOrWhiteSpace($entry)) {
                        $hints.Add($entry.Trim()) | Out-Null
                    }
                }
            }
        }
    }

    return @($hints)
}

$projectInventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $ProjectInventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "project_inventory_root"
$discoveryRootAbs = Get-SafeRelativePathAbs -RelativePath $DiscoveryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "discovery_root"
if (-not (Test-Path -LiteralPath $discoveryRootAbs -PathType Container)) {
    New-Item -Path $discoveryRootAbs -ItemType Directory -Force | Out-Null
}

$candidateInputs = New-Object System.Collections.Generic.List[string]
$effectivePathSource = $PathSource

switch ($PSCmdlet.ParameterSetName) {
    "ByCandidates" {
        $effectivePathSource = if ([string]::IsNullOrWhiteSpace($effectivePathSource)) { "explicit_candidate_paths" } else { $effectivePathSource }
        foreach ($entry in $CandidatePaths) {
            if (-not [string]::IsNullOrWhiteSpace($entry)) {
                foreach ($part in ($entry -split ",")) {
                    $trimmed = $part.Trim()
                    if (-not [string]::IsNullOrWhiteSpace($trimmed)) {
                        $candidateInputs.Add($trimmed) | Out-Null
                    }
                }
            }
        }
    }
    "ByJsonFile" {
        $effectivePathSource = if ([string]::IsNullOrWhiteSpace($effectivePathSource)) { "candidate_paths_json" } else { $effectivePathSource }

        $jsonAbs = Resolve-PathWithinRepo -InputPath $CandidatePathsJsonPath -Label "candidate_paths_json_path"
        try {
            $loaded = Get-Content -LiteralPath $jsonAbs -Raw | ConvertFrom-Json
        } catch {
            throw "candidate_paths_json_path is not valid JSON: $CandidatePathsJsonPath"
        }

        if ($loaded -is [System.Array]) {
            foreach ($entry in $loaded) {
                if ($entry -is [string] -and -not [string]::IsNullOrWhiteSpace($entry)) {
                    $candidateInputs.Add($entry.Trim()) | Out-Null
                }
            }
        } elseif ($null -ne $loaded.candidate_paths) {
            foreach ($entry in @($loaded.candidate_paths)) {
                if ($entry -is [string] -and -not [string]::IsNullOrWhiteSpace($entry)) {
                    $candidateInputs.Add($entry.Trim()) | Out-Null
                }
            }
        } elseif ($null -ne $loaded.path_hints) {
            foreach ($entry in @($loaded.path_hints)) {
                if ($entry -is [string] -and -not [string]::IsNullOrWhiteSpace($entry)) {
                    $candidateInputs.Add($entry.Trim()) | Out-Null
                }
            }
        }
    }
    "ByProjectInventoryPath" {
        $effectivePathSource = if ([string]::IsNullOrWhiteSpace($effectivePathSource)) { "project_inventory_evidence" } else { $effectivePathSource }
        $inventoryRef = Resolve-ProjectInventoryByPath -InputPath $ProjectInventoryPath -RootAbs $projectInventoryRootAbs
        foreach ($hint in (Get-CandidateHintsFromProjectInventory -Inventory $inventoryRef.item)) {
            $candidateInputs.Add($hint) | Out-Null
        }
    }
    "ByProjectInventoryId" {
        $effectivePathSource = if ([string]::IsNullOrWhiteSpace($effectivePathSource)) { "project_inventory_evidence" } else { $effectivePathSource }
        $inventoryRef = Resolve-JsonById -RootAbs $projectInventoryRootAbs -IdProperty "inventory_id" -IdValue $ProjectInventoryId
        if ($null -eq $inventoryRef) {
            throw "project_inventory_id '$ProjectInventoryId' not found."
        }
        foreach ($hint in (Get-CandidateHintsFromProjectInventory -Inventory $inventoryRef.item)) {
            $candidateInputs.Add($hint) | Out-Null
        }
    }
}

$candidateInputs = @($candidateInputs | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($candidateInputs.Count -eq 0) {
    throw "no candidate paths were provided from the selected path source."
}

$normalizedCandidatePaths = New-Object System.Collections.Generic.List[string]
$existingCandidates = New-Object System.Collections.Generic.List[object]
$rejectedCandidates = New-Object System.Collections.Generic.List[object]

foreach ($candidate in $candidateInputs) {
    $eval = Get-CandidateFromText -PathText $candidate
    if (-not $eval.accepted) {
        $rejectedCandidates.Add([ordered]@{
            candidate_path = $candidate
            reason = $eval.reason
        }) | Out-Null
        continue
    }

    $normalizedAbs = [string]$eval.normalized
    $normalizedRepoRelative = Get-RepoRelativePath -AbsolutePath $normalizedAbs
    $normalizedCandidatePaths.Add($normalizedRepoRelative) | Out-Null

    if (Test-Path -LiteralPath $normalizedAbs -PathType Leaf) {
        $existingCandidates.Add([ordered]@{
            candidate_path = $normalizedRepoRelative
            binary_kind = [string]$eval.kind
        }) | Out-Null
    }
}

if ($normalizedCandidatePaths.Count -eq 0) {
    throw "no safe binary candidates remained after validation."
}

$discoveryId = "ap-binary-discovery-" + [Guid]::NewGuid().ToString("N")
$timestampUtc = [DateTime]::UtcNow.ToString("o")

$outputAbs = $null
if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
    if ([System.IO.Path]::IsPathRooted($OutputPath)) {
        $outputAbs = [System.IO.Path]::GetFullPath($OutputPath)
        if (-not (Test-IsPathWithin -CandidatePath $outputAbs -ParentPath $discoveryRootAbs)) {
            throw "output_path must remain under ap-binary-discovery root."
        }
    } else {
        $outputAbs = Get-SafeRelativePathAbs -RelativePath $OutputPath -AllowedRootAbs $discoveryRootAbs -Label "output_path"
    }
} else {
    $outputAbs = Join-Path $discoveryRootAbs "$discoveryId.json"
}

$outputRel = Get-RepoRelativePath -AbsolutePath $outputAbs
$candidatePathsOut = @($candidateInputs)
$normalizedCandidatePathsOut = @($normalizedCandidatePaths)
$existingCandidatesOut = @($existingCandidates.ToArray())
$rejectedCandidatesOut = @($rejectedCandidates.ToArray())
$record = [ordered]@{
    schema_version = "1.0.0"
    discovery_id = $discoveryId
    sandbox_root = "examples/sandbox"
    candidate_paths = $candidatePathsOut
    normalized_candidate_paths = $normalizedCandidatePathsOut
    existing_candidates = $existingCandidatesOut
    rejected_candidates = $rejectedCandidatesOut
    path_source = $effectivePathSource
    read_only = $true
    execution_admitted = $false
    cache_access_admitted = $false
    live_database_access_admitted = $false
    explicit_non_admissions = @($explicitNonAdmissions)
    output_path = $outputRel
    created_utc = $timestampUtc
}

Write-JsonFile -InputObject $record -OutputPath $outputAbs
$record | ConvertTo-Json -Depth 100
