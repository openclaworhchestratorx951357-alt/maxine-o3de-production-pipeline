[CmdletBinding(DefaultParameterSetName = "ByPath")]
param(
    [Parameter(Mandatory = $true, ParameterSetName = "ByPath")]
    [string]$ProposalPath,

    [Parameter(Mandatory = $true, ParameterSetName = "ById")]
    [string]$ProposalId,

    [string]$ProjectInventoryPath,
    [string]$ProjectInventoryId,
    [string]$AssetCandidateInventoryPath,
    [string]$AssetCandidateInventoryId,

    [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
    [string[]]$EvidencePaths,

    [string]$OutputPath,

    [string]$ProposalsRoot = "examples/sandbox/product-resolution-proposals",
    [string]$ProjectInventoryRoot = "examples/sandbox/project-inventory",
    [string]$AssetCandidateInventoryRoot = "examples/sandbox/asset-candidates",
    [string]$ApEvidenceImportsRoot = "examples/sandbox/ap-evidence-imports"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$allowedEvidenceQuality = @("none", "weak", "partial", "strong_snapshot_only")
$forbiddenEvidenceQuality = @("live_verified", "product_resolved", "asset_id_resolved", "ap_executed", "cache_verified")

$allowedEvidenceInputExtensions = @(
    ".json",
    ".txt",
    ".log"
)

$blockedEvidenceInputExtensions = @(
    ".fbx",
    ".glb",
    ".gltf",
    ".obj",
    ".blend",
    ".material",
    ".azmaterial",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".exr",
    ".dds",
    ".dll",
    ".exe",
    ".pdb",
    ".bin",
    ".pak",
    ".prefab",
    ".spawnable",
    ".uasset",
    ".umap",
    ".pyc",
    ".zip",
    ".7z",
    ".rar"
)

$explicitNonAdmissions = @(
    "authoritative_writes",
    "product_resolution",
    "product_resolution_as_fact",
    "product_id_claims",
    "asset_id_claims",
    "source_uuid_claims",
    "asset_processor_execution",
    "o3de_editor_execution",
    "o3de_cli_execution",
    "cache_read",
    "live_asset_database_read",
    "cache_path_write",
    "engine_path_write",
    "production_path_write",
    "spawning",
    "publishing"
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

function Resolve-PathWithinRepo {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputPath,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    $pathAbs = $null
    if ([System.IO.Path]::IsPathRooted($InputPath)) {
        $pathAbs = [System.IO.Path]::GetFullPath($InputPath)
        if (-not (Test-IsPathWithin -CandidatePath $pathAbs -ParentPath $repoRoot)) {
            throw "$Label must remain inside repository root."
        }
    } else {
        if ($InputPath.StartsWith("\") -or $InputPath.StartsWith("/")) {
            throw "$Label cannot start with slash or backslash."
        }
        $normalized = $InputPath.Replace("\", "/")
        if (($normalized -split "/") -contains "..") {
            throw "$Label contains parent traversal and is blocked."
        }

        $pathAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $InputPath))
        if (-not (Test-IsPathWithin -CandidatePath $pathAbs -ParentPath $repoRoot)) {
            throw "$Label escapes repository root."
        }
    }

    if (-not (Test-Path -LiteralPath $pathAbs -PathType Leaf)) {
        throw "$Label not found: $InputPath"
    }

    return $pathAbs
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
                $matches += [ordered]@{
                    path = $file.FullName
                    item = $item
                }
            }
        } catch {
            continue
        }
    }

    if ($matches.Count -eq 0) {
        return $null
    }
    if ($matches.Count -gt 1) {
        throw "$IdProperty '$IdValue' is ambiguous."
    }

    return $matches[0]
}

function Resolve-JsonByPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputPath,
        [Parameter(Mandatory = $true)]
        [string]$RootAbs,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    $pathAbs = $null
    if ([System.IO.Path]::IsPathRooted($InputPath)) {
        $pathAbs = [System.IO.Path]::GetFullPath($InputPath)
        if (-not (Test-IsPathWithin -CandidatePath $pathAbs -ParentPath $RootAbs)) {
            throw "$Label must remain within approved sandbox root."
        }
    } else {
        $pathAbs = Get-SafeRelativePathAbs -RelativePath $InputPath -AllowedRootAbs $RootAbs -Label $Label
    }

    if (-not (Test-Path -LiteralPath $pathAbs -PathType Leaf)) {
        throw "$Label not found: $InputPath"
    }

    try {
        $item = Get-Content -LiteralPath $pathAbs -Raw | ConvertFrom-Json
    } catch {
        throw "$Label is not valid JSON: $InputPath"
    }

    return [ordered]@{
        path = $pathAbs
        item = $item
    }
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

$proposalsRootAbs = Get-SafeRelativePathAbs -RelativePath $ProposalsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "proposals_root"
$projectInventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $ProjectInventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "project_inventory_root"
$assetCandidateInventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $AssetCandidateInventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "asset_candidate_inventory_root"
$apEvidenceImportsRootAbs = Get-SafeRelativePathAbs -RelativePath $ApEvidenceImportsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "ap_evidence_imports_root"
if (-not (Test-Path -LiteralPath $apEvidenceImportsRootAbs -PathType Container)) {
    New-Item -Path $apEvidenceImportsRootAbs -ItemType Directory -Force | Out-Null
}

if (-not [string]::IsNullOrWhiteSpace($ProjectInventoryPath) -and -not [string]::IsNullOrWhiteSpace($ProjectInventoryId)) {
    throw "Provide either project_inventory_path or project_inventory_id, not both."
}
if (-not [string]::IsNullOrWhiteSpace($AssetCandidateInventoryPath) -and -not [string]::IsNullOrWhiteSpace($AssetCandidateInventoryId)) {
    throw "Provide either asset_candidate_inventory_path or asset_candidate_inventory_id, not both."
}
if ($EvidencePaths.Count -eq 0) {
    throw "At least one evidence path is required."
}

$expandedEvidencePaths = New-Object System.Collections.Generic.List[string]
foreach ($entry in $EvidencePaths) {
    if ([string]::IsNullOrWhiteSpace($entry)) {
        continue
    }
    foreach ($part in ($entry -split ",")) {
        $trimmed = $part.Trim()
        if (-not [string]::IsNullOrWhiteSpace($trimmed)) {
            $expandedEvidencePaths.Add($trimmed) | Out-Null
        }
    }
}
$EvidencePaths = @($expandedEvidencePaths)
if ($EvidencePaths.Count -eq 0) {
    throw "At least one evidence path is required."
}

$proposalRef = $null
if ($PSCmdlet.ParameterSetName -eq "ByPath") {
    $proposalRef = Resolve-JsonByPath -InputPath $ProposalPath -RootAbs $proposalsRootAbs -Label "proposal_path"
} else {
    $proposalRef = Resolve-JsonById -RootAbs $proposalsRootAbs -IdProperty "proposal_id" -IdValue $ProposalId
    if ($null -eq $proposalRef) {
        throw "proposal_id '$ProposalId' not found."
    }
}

$proposal = $proposalRef.item
if ([string]::IsNullOrWhiteSpace([string]$proposal.proposal_id)) {
    throw "proposal is missing proposal_id."
}
if ([string]$proposal.sandbox_root -ne "examples/sandbox") {
    throw "proposal sandbox_root must be examples/sandbox."
}

$projectInventoryRef = $null
if (-not [string]::IsNullOrWhiteSpace($ProjectInventoryPath)) {
    $projectInventoryRef = Resolve-JsonByPath -InputPath $ProjectInventoryPath -RootAbs $projectInventoryRootAbs -Label "project_inventory_path"
} elseif (-not [string]::IsNullOrWhiteSpace($ProjectInventoryId)) {
    $projectInventoryRef = Resolve-JsonById -RootAbs $projectInventoryRootAbs -IdProperty "inventory_id" -IdValue $ProjectInventoryId
    if ($null -eq $projectInventoryRef) {
        throw "project_inventory_id '$ProjectInventoryId' not found."
    }
} elseif (-not [string]::IsNullOrWhiteSpace([string]$proposal.source_project_inventory_id)) {
    $projectInventoryRef = Resolve-JsonById -RootAbs $projectInventoryRootAbs -IdProperty "inventory_id" -IdValue ([string]$proposal.source_project_inventory_id)
}

$assetCandidateInventoryRef = $null
if (-not [string]::IsNullOrWhiteSpace($AssetCandidateInventoryPath)) {
    $assetCandidateInventoryRef = Resolve-JsonByPath -InputPath $AssetCandidateInventoryPath -RootAbs $assetCandidateInventoryRootAbs -Label "asset_candidate_inventory_path"
} elseif (-not [string]::IsNullOrWhiteSpace($AssetCandidateInventoryId)) {
    $assetCandidateInventoryRef = Resolve-JsonById -RootAbs $assetCandidateInventoryRootAbs -IdProperty "inventory_id" -IdValue $AssetCandidateInventoryId
    if ($null -eq $assetCandidateInventoryRef) {
        throw "asset_candidate_inventory_id '$AssetCandidateInventoryId' not found."
    }
} elseif (-not [string]::IsNullOrWhiteSpace([string]$proposal.source_inventory_id)) {
    $assetCandidateInventoryRef = Resolve-JsonById -RootAbs $assetCandidateInventoryRootAbs -IdProperty "inventory_id" -IdValue ([string]$proposal.source_inventory_id)
}

$resolvedProjectInventoryId = [string]$proposal.source_project_inventory_id
if ([string]::IsNullOrWhiteSpace($resolvedProjectInventoryId) -and $null -ne $projectInventoryRef) {
    $resolvedProjectInventoryId = [string]$projectInventoryRef.item.inventory_id
}
if ([string]::IsNullOrWhiteSpace($resolvedProjectInventoryId)) {
    $resolvedProjectInventoryId = "unknown-project-inventory-id"
}

$resolvedAssetCandidateInventoryId = [string]$proposal.source_inventory_id
if ([string]::IsNullOrWhiteSpace($resolvedAssetCandidateInventoryId) -and $null -ne $assetCandidateInventoryRef) {
    $resolvedAssetCandidateInventoryId = [string]$assetCandidateInventoryRef.item.inventory_id
}
if ([string]::IsNullOrWhiteSpace($resolvedAssetCandidateInventoryId)) {
    $resolvedAssetCandidateInventoryId = "unknown-asset-candidate-inventory-id"
}

$inputEvidencePaths = New-Object System.Collections.Generic.List[string]
$importedLogPaths = New-Object System.Collections.Generic.List[string]
$importedSnapshotMetadataPaths = New-Object System.Collections.Generic.List[string]
$observedSourcePaths = New-Object System.Collections.Generic.HashSet[string]([System.StringComparer]::OrdinalIgnoreCase)
$observedProductLikeMentions = New-Object System.Collections.Generic.HashSet[string]([System.StringComparer]::OrdinalIgnoreCase)
$observedWarningMentions = New-Object System.Collections.Generic.List[string]
$observedErrorMentions = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]
$blockingReasons = New-Object System.Collections.Generic.List[string]
$requiredNextEvidence = New-Object System.Collections.Generic.List[string]

$sourcePathRegex = [regex]"(?im)[A-Za-z0-9_./\\:-]+\.(fbx|glb|gltf|obj|blend|material|azmaterial|png|jpg|jpeg|tif|tiff|exr)"
$productLikeRegex = [regex]"(?im)[A-Za-z0-9_./\\:-]+\.(azmodel|azmaterial|spawnable|prefab|streamingimage|motionset|actor|pak)"

foreach ($evidencePath in $EvidencePaths) {
    if ([string]::IsNullOrWhiteSpace($evidencePath)) {
        throw "evidence path entries must be non-empty."
    }

    $evidenceAbs = Resolve-PathWithinRepo -InputPath $evidencePath -Label "evidence_path"
    $evidenceRel = Get-RepoRelativePath -AbsolutePath $evidenceAbs
    $evidenceRelNormalized = $evidenceRel.Replace("\\", "/")

    if ($evidenceRelNormalized -match "(?i)(^|/)cache(/|$)") {
        throw "live Cache directory evidence inputs are blocked."
    }

    $fileName = [System.IO.Path]::GetFileName($evidenceAbs)
    $ext = [System.IO.Path]::GetExtension($evidenceAbs).ToLowerInvariant()

    if ($fileName.Equals("assetdb.sqlite", [System.StringComparison]::OrdinalIgnoreCase) -or $ext -eq ".sqlite" -or $ext -eq ".db") {
        throw "live asset database evidence inputs are blocked."
    }

    if ($blockedEvidenceInputExtensions -contains $ext) {
        throw "binary/source/runtime evidence inputs are blocked: $evidenceRel"
    }

    if ($allowedEvidenceInputExtensions -notcontains $ext) {
        throw "unsupported evidence input extension '$ext'; only .json, .txt, and .log are allowed."
    }

    $inputEvidencePaths.Add($evidenceRelNormalized) | Out-Null
    if ($ext -in @(".log", ".txt")) {
        $importedLogPaths.Add($evidenceRelNormalized) | Out-Null
    } elseif ($ext -eq ".json") {
        $importedSnapshotMetadataPaths.Add($evidenceRelNormalized) | Out-Null
    }

    $raw = Get-Content -LiteralPath $evidenceAbs -Raw

    foreach ($match in $sourcePathRegex.Matches($raw)) {
        $value = [string]$match.Value
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            $observedSourcePaths.Add($value.Replace("\\", "/")) | Out-Null
        }
    }

    foreach ($match in $productLikeRegex.Matches($raw)) {
        $value = [string]$match.Value
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            $observedProductLikeMentions.Add($value.Replace("\\", "/")) | Out-Null
        }
    }

    foreach ($line in ($raw -split "`r?`n")) {
        if ($line -match "(?i)warning") {
            $trimmed = $line.Trim()
            if (-not [string]::IsNullOrWhiteSpace($trimmed)) {
                $observedWarningMentions.Add($trimmed) | Out-Null
            }
        }
        if ($line -match "(?i)error") {
            $trimmed = $line.Trim()
            if (-not [string]::IsNullOrWhiteSpace($trimmed)) {
                $observedErrorMentions.Add($trimmed) | Out-Null
            }
        }

        if ($line -match "(?i)product") {
            $trimmed = $line.Trim()
            if (-not [string]::IsNullOrWhiteSpace($trimmed)) {
                $observedProductLikeMentions.Add($trimmed) | Out-Null
            }
        }
    }
}

$observedAssetProcessorState = "snapshot_metadata_only"
if ($observedErrorMentions.Count -gt 0) {
    $observedAssetProcessorState = "errors_observed_in_imported_evidence"
} elseif ($observedWarningMentions.Count -gt 0) {
    $observedAssetProcessorState = "warnings_observed_in_imported_evidence"
} elseif ($importedLogPaths.Count -gt 0) {
    $observedAssetProcessorState = "log_evidence_imported_no_execution"
}

$evidenceQuality = "none"
if ($importedSnapshotMetadataPaths.Count -gt 0 -and $importedLogPaths.Count -eq 0) {
    $evidenceQuality = "strong_snapshot_only"
} elseif ($importedSnapshotMetadataPaths.Count -gt 0 -and $importedLogPaths.Count -gt 0) {
    $evidenceQuality = "partial"
} elseif ($importedLogPaths.Count -gt 0) {
    $evidenceQuality = "weak"
}

if ($forbiddenEvidenceQuality -contains $evidenceQuality) {
    throw "derived evidence_quality '$evidenceQuality' is forbidden."
}
if ($allowedEvidenceQuality -notcontains $evidenceQuality) {
    throw "derived evidence_quality '$evidenceQuality' is invalid."
}

$requiredNextEvidence.Add("read_only_ap_snapshot_metadata") | Out-Null
if ($importedSnapshotMetadataPaths.Count -eq 0) {
    $requiredNextEvidence.Add("snapshot_metadata_json_required") | Out-Null
}
if ($observedProductLikeMentions.Count -eq 0) {
    $requiredNextEvidence.Add("additional_product_like_mentions_required") | Out-Null
}
if ($observedErrorMentions.Count -gt 0) {
    $requiredNextEvidence.Add("triage_ap_error_mentions") | Out-Null
    $blockingReasons.Add("ap_error_mentions_present") | Out-Null
}
if ($resolvedProjectInventoryId -eq "unknown-project-inventory-id") {
    $blockingReasons.Add("missing_project_inventory_context") | Out-Null
}
if ($resolvedAssetCandidateInventoryId -eq "unknown-asset-candidate-inventory-id") {
    $blockingReasons.Add("missing_asset_candidate_inventory_context") | Out-Null
}
if ($observedWarningMentions.Count -gt 0) {
    $warnings.Add("warning_mentions_present") | Out-Null
}
if ($importedLogPaths.Count -eq 0 -and $importedSnapshotMetadataPaths.Count -eq 0) {
    $blockingReasons.Add("no_supported_evidence_inputs_imported") | Out-Null
}

$importId = "ap-evidence-import-$([Guid]::NewGuid().ToString('N'))"
$outputRel = $OutputPath
if ([string]::IsNullOrWhiteSpace($outputRel)) {
    $outputRel = "$ApEvidenceImportsRoot/$importId.json"
}
$outputAbs = Get-SafeRelativePathAbs -RelativePath $outputRel -AllowedRootAbs $apEvidenceImportsRootAbs -Label "output_path"

$payload = [ordered]@{
    schema_version = "1.0.0"
    ap_evidence_import_id = $importId
    source_proposal_id = [string]$proposal.proposal_id
    source_project_inventory_id = $resolvedProjectInventoryId
    source_asset_candidate_inventory_id = $resolvedAssetCandidateInventoryId
    sandbox_root = "examples/sandbox"
    input_evidence_paths = @($inputEvidencePaths | Sort-Object -Unique)
    imported_log_paths = @($importedLogPaths | Sort-Object -Unique)
    imported_snapshot_metadata_paths = @($importedSnapshotMetadataPaths | Sort-Object -Unique)
    observed_source_paths = @($observedSourcePaths | Sort-Object)
    observed_product_like_mentions = @($observedProductLikeMentions | Sort-Object)
    observed_warning_mentions = @($observedWarningMentions | Sort-Object -Unique)
    observed_error_mentions = @($observedErrorMentions | Sort-Object -Unique)
    observed_asset_processor_state = $observedAssetProcessorState
    evidence_quality = $evidenceQuality
    required_next_evidence = @($requiredNextEvidence | Sort-Object -Unique)
    blocking_reasons = @($blockingReasons | Sort-Object -Unique)
    warnings = @($warnings | Sort-Object -Unique)
    read_only = $true
    asset_processor_execution_admitted = $false
    o3de_execution_admitted = $false
    cache_access_admitted = $false
    live_database_access_admitted = $false
    product_ids_claimed = $false
    asset_ids_claimed = $false
    source_uuids_claimed = $false
    product_resolution_claimed = $false
    spawn_admitted = $false
    publish_admitted = $false
    explicit_non_admissions = @($explicitNonAdmissions)
    output_path = Get-RepoRelativePath -AbsolutePath $outputAbs
    created_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

if ($null -ne $projectInventoryRef) {
    $payload.source_project_inventory_path = Get-RepoRelativePath -AbsolutePath $projectInventoryRef.path
}
if ($null -ne $assetCandidateInventoryRef) {
    $payload.source_asset_candidate_inventory_path = Get-RepoRelativePath -AbsolutePath $assetCandidateInventoryRef.path
}

Write-JsonFile -InputObject $payload -OutputPath $outputAbs
$payload | ConvertTo-Json -Depth 100
