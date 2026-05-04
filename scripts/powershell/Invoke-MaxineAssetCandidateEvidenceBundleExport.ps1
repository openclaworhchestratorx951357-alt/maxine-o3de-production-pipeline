[CmdletBinding()]
param(
    [string]$ReviewPacketPath,
    [string]$ReviewPacketId,
    [string]$InventoryPath,

    [string]$ReviewPacketsRoot = "examples/sandbox/asset-candidate-review-packets",
    [string]$InventoryRoot = "examples/sandbox/asset-candidates",
    [string]$EvidenceBundlesRoot = "examples/sandbox/asset-candidate-evidence-bundles",
    [string]$BundlePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$explicitNonAdmissionsDefault = @(
    "authoritative_writes",
    "o3de_editor_execution",
    "asset_processor_execution",
    "o3de_cli_execution",
    "product_resolution",
    "asset_id_claims",
    "spawning",
    "publishing",
    "production_cache_engine_writes"
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

function Resolve-ReviewPacket {
    param(
        [string]$ReviewPacketPath,
        [string]$ReviewPacketId,
        [string]$ReviewPacketsRootAbs
    )

    $hasPath = -not [string]::IsNullOrWhiteSpace($ReviewPacketPath)
    $hasId = -not [string]::IsNullOrWhiteSpace($ReviewPacketId)
    if (($hasPath -and $hasId) -or (-not $hasPath -and -not $hasId)) {
        throw "Provide either review_packet_path or review_packet_id."
    }

    if ($hasPath) {
        $packetAbs = $null
        if ([System.IO.Path]::IsPathRooted($ReviewPacketPath)) {
            $packetAbs = [System.IO.Path]::GetFullPath($ReviewPacketPath)
            if (-not (Test-IsPathWithin -CandidatePath $packetAbs -ParentPath $ReviewPacketsRootAbs)) {
                throw "review_packet_path must remain under asset candidate review packets root."
            }
        } else {
            $packetAbs = Get-SafeRelativePathAbs -RelativePath $ReviewPacketPath -AllowedRootAbs $ReviewPacketsRootAbs -Label "review_packet_path"
        }

        if (-not (Test-Path -LiteralPath $packetAbs -PathType Leaf)) {
            throw "review packet path not found: $ReviewPacketPath"
        }

        try {
            $packet = Get-Content -LiteralPath $packetAbs -Raw | ConvertFrom-Json
        } catch {
            throw "review packet is not valid JSON: $ReviewPacketPath"
        }

        return [ordered]@{
            path = $packetAbs
            item = $packet
        }
    }

    $matches = @()
    foreach ($file in Get-ChildItem -LiteralPath $ReviewPacketsRootAbs -File -Filter *.json -ErrorAction SilentlyContinue) {
        try {
            $packet = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
            if ([string]$packet.review_packet_id -eq $ReviewPacketId) {
                $matches += [ordered]@{
                    path = $file.FullName
                    item = $packet
                }
            }
        } catch {
            continue
        }
    }

    if ($matches.Count -eq 0) {
        throw "review_packet_id '$ReviewPacketId' not found."
    }
    if ($matches.Count -gt 1) {
        throw "review_packet_id '$ReviewPacketId' is ambiguous."
    }
    return $matches[0]
}

function Resolve-Inventory {
    param(
        [string]$InventoryPath,
        [string]$SourceInventoryId,
        [string]$InventoryRootAbs
    )

    if (-not [string]::IsNullOrWhiteSpace($InventoryPath)) {
        $inventoryAbs = $null
        if ([System.IO.Path]::IsPathRooted($InventoryPath)) {
            $inventoryAbs = [System.IO.Path]::GetFullPath($InventoryPath)
            if (-not (Test-IsPathWithin -CandidatePath $inventoryAbs -ParentPath $InventoryRootAbs)) {
                throw "inventory_path must remain under asset candidate inventory root."
            }
        } else {
            $inventoryAbs = Get-SafeRelativePathAbs -RelativePath $InventoryPath -AllowedRootAbs $InventoryRootAbs -Label "inventory_path"
        }

        if (-not (Test-Path -LiteralPath $inventoryAbs -PathType Leaf)) {
            throw "inventory_path not found: $InventoryPath"
        }

        try {
            $inventory = Get-Content -LiteralPath $inventoryAbs -Raw | ConvertFrom-Json
        } catch {
            throw "inventory_path is not valid JSON: $InventoryPath"
        }

        if ([string]$inventory.inventory_id -ne $SourceInventoryId) {
            throw "inventory_path inventory_id does not match source_inventory_id."
        }

        return [ordered]@{
            path = $inventoryAbs
            item = $inventory
        }
    }

    $matches = @()
    foreach ($file in Get-ChildItem -LiteralPath $InventoryRootAbs -File -Filter *.json -ErrorAction SilentlyContinue) {
        try {
            $inventory = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
            if ([string]$inventory.inventory_id -eq $SourceInventoryId) {
                $matches += [ordered]@{
                    path = $file.FullName
                    item = $inventory
                }
            }
        } catch {
            continue
        }
    }

    if ($matches.Count -eq 0) {
        throw "source inventory '$SourceInventoryId' not found."
    }
    if ($matches.Count -gt 1) {
        throw "source inventory '$SourceInventoryId' is ambiguous."
    }
    return $matches[0]
}

$reviewPacketsRootAbs = Get-SafeRelativePathAbs -RelativePath $ReviewPacketsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "review_packets_root"
$inventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $InventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "inventory_root"
$evidenceBundlesRootAbs = Get-SafeRelativePathAbs -RelativePath $EvidenceBundlesRoot -AllowedRootAbs $sandboxAnchorAbs -Label "evidence_bundles_root"
if (-not (Test-Path -LiteralPath $evidenceBundlesRootAbs -PathType Container)) {
    New-Item -Path $evidenceBundlesRootAbs -ItemType Directory -Force | Out-Null
}

$packetRef = Resolve-ReviewPacket -ReviewPacketPath $ReviewPacketPath -ReviewPacketId $ReviewPacketId -ReviewPacketsRootAbs $reviewPacketsRootAbs
$packet = $packetRef.item
if ([string]::IsNullOrWhiteSpace([string]$packet.review_packet_id)) {
    throw "review packet is missing review_packet_id."
}
if ([string]::IsNullOrWhiteSpace([string]$packet.source_inventory_id)) {
    throw "review packet is missing source_inventory_id."
}
if ([string]::IsNullOrWhiteSpace([string]$packet.candidate_id)) {
    throw "review packet is missing candidate_id."
}
if ([string]$packet.sandbox_root -ne "examples/sandbox") {
    throw "review packet sandbox_root must be examples/sandbox."
}

$inventoryRef = Resolve-Inventory -InventoryPath $InventoryPath -SourceInventoryId ([string]$packet.source_inventory_id) -InventoryRootAbs $inventoryRootAbs
$inventory = $inventoryRef.item
if ([string]$inventory.sandbox_root -ne "examples/sandbox") {
    throw "source inventory sandbox_root must be examples/sandbox."
}

$candidateExists = $false
foreach ($candidate in @($inventory.source_asset_candidates)) {
    if ([string]$candidate.candidate_id -eq [string]$packet.candidate_id) {
        $candidateExists = $true
        break
    }
}
if (-not $candidateExists) {
    throw "candidate_id from review packet is not present in source inventory."
}

$bundleId = "asset-candidate-evidence-bundle-$([Guid]::NewGuid().ToString('N'))"
$manifestRel = $BundlePath
if ([string]::IsNullOrWhiteSpace($manifestRel)) {
    $manifestRel = "$EvidenceBundlesRoot/$bundleId/bundle.manifest.json"
} elseif (-not $manifestRel.ToLowerInvariant().EndsWith(".json")) {
    $manifestRel = $manifestRel.TrimEnd("/", "\") + "/bundle.manifest.json"
}

$manifestAbs = Get-SafeRelativePathAbs -RelativePath $manifestRel -AllowedRootAbs $evidenceBundlesRootAbs -Label "bundle_path"
$bundleDirAbs = Split-Path -Parent $manifestAbs
if (-not (Test-Path -LiteralPath $bundleDirAbs -PathType Container)) {
    New-Item -Path $bundleDirAbs -ItemType Directory -Force | Out-Null
}

$includedArtifacts = New-Object System.Collections.Generic.List[string]
$copiedArtifactPaths = New-Object System.Collections.Generic.List[string]
$artifactSha = [ordered]@{}

function Add-Snapshot {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string]$SnapshotName,
        [Parameter(Mandatory = $true)]
        [string]$ArtifactLabel
    )

    $snapshotAbs = Join-Path $bundleDirAbs $SnapshotName
    Write-JsonFile -InputObject $InputObject -OutputPath $snapshotAbs

    $snapshotRel = Get-RepoRelativePath -AbsolutePath $snapshotAbs
    $includedArtifacts.Add($ArtifactLabel) | Out-Null
    $copiedArtifactPaths.Add($snapshotRel) | Out-Null
    $artifactSha[$snapshotRel] = (Get-FileHash -LiteralPath $snapshotAbs -Algorithm SHA256).Hash
}

Add-Snapshot -InputObject $inventory -SnapshotName "asset-candidate-inventory.snapshot.json" -ArtifactLabel "asset_candidate_inventory"
Add-Snapshot -InputObject $packet -SnapshotName "asset-candidate-review-packet.snapshot.json" -ArtifactLabel "asset_candidate_review_packet"

$linkedEvidence = [ordered]@{
    source_inventory_id = [string]$packet.source_inventory_id
    source_review_packet_id = [string]$packet.review_packet_id
    candidate_id = [string]$packet.candidate_id
    candidate_evidence_links = $packet.evidence_links
    inventory_linked_sandbox_evidence = $inventory.linked_sandbox_evidence
}
Add-Snapshot -InputObject $linkedEvidence -SnapshotName "linked-sandbox-evidence.snapshot.json" -ArtifactLabel "linked_sandbox_evidence_references"

$explicitNonAdmissions = @($packet.explicit_non_admissions)
if ($explicitNonAdmissions.Count -eq 0) {
    $explicitNonAdmissions = @($explicitNonAdmissionsDefault)
}

$manifest = [ordered]@{
    schema_version = "1.0.0"
    bundle_id = $bundleId
    source_inventory_id = [string]$packet.source_inventory_id
    source_review_packet_id = [string]$packet.review_packet_id
    candidate_id = [string]$packet.candidate_id
    sandbox_root = "examples/sandbox"
    bundle_path = Get-RepoRelativePath -AbsolutePath $manifestAbs
    included_artifacts = @($includedArtifacts)
    copied_artifact_paths = @($copiedArtifactPaths)
    artifact_sha256 = $artifactSha
    safety_summary = "Sandbox-only asset candidate evidence bundle export. Copies JSON evidence snapshots only; source assets, textures, models, binaries, cache files, and runtime outputs are not copied."
    explicit_non_admissions = @($explicitNonAdmissions)
    created_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

Write-JsonFile -InputObject $manifest -OutputPath $manifestAbs
$manifest | ConvertTo-Json -Depth 100
