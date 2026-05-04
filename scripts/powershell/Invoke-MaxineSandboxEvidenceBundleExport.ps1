[CmdletBinding()]
param(
    [string]$WorkflowRunPath,
    [string]$WorkflowRunId,
    [string]$WorkflowRunsRoot = "examples/sandbox/workflow-runs",
    [string]$EvidenceBundlesRoot = "examples/sandbox/evidence-bundles",
    [string]$BundlePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$defaultNonAdmissions = @(
    "authoritative_writes",
    "o3de_editor_execution",
    "asset_processor_execution",
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

function Resolve-WorkflowRunPath {
    param(
        [string]$WorkflowRunPath,
        [string]$WorkflowRunId,
        [string]$WorkflowRunsRootAbs
    )

    $hasPath = -not [string]::IsNullOrWhiteSpace($WorkflowRunPath)
    $hasId = -not [string]::IsNullOrWhiteSpace($WorkflowRunId)
    if (($hasPath -and $hasId) -or (-not $hasPath -and -not $hasId)) {
        throw "Provide either workflow_run_path or workflow_run_id."
    }

    if ($hasPath) {
        $resolved = (Resolve-Path -LiteralPath $WorkflowRunPath).Path
        $pathAbs = [System.IO.Path]::GetFullPath($resolved)
        if (-not (Test-IsPathWithin -CandidatePath $pathAbs -ParentPath $sandboxAnchorAbs)) {
            throw "workflow run path must remain within sandbox root."
        }
        return $pathAbs
    }

    if (-not (Test-Path -LiteralPath $WorkflowRunsRootAbs -PathType Container)) {
        throw "workflow runs root not found: $WorkflowRunsRoot"
    }

    $matches = @()
    foreach ($file in Get-ChildItem -LiteralPath $WorkflowRunsRootAbs -File -Filter *.json) {
        try {
            $candidate = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
            if ($candidate.workflow_run_id -eq $WorkflowRunId) {
                $matches += $file.FullName
            }
        } catch {
            continue
        }
    }

    if ($matches.Count -eq 0) {
        throw "workflow_run_id '$WorkflowRunId' not found."
    }
    if ($matches.Count -gt 1) {
        throw "workflow_run_id '$WorkflowRunId' is ambiguous."
    }

    return [System.IO.Path]::GetFullPath($matches[0])
}

$workflowRunsRootAbs = Get-SafeRelativePathAbs -RelativePath $WorkflowRunsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "workflow_runs_root"
$evidenceRootAbs = Get-SafeRelativePathAbs -RelativePath $EvidenceBundlesRoot -AllowedRootAbs $sandboxAnchorAbs -Label "evidence_bundles_root"
if (-not (Test-Path -LiteralPath $evidenceRootAbs -PathType Container)) {
    New-Item -Path $evidenceRootAbs -ItemType Directory -Force | Out-Null
}

$workflowAbs = Resolve-WorkflowRunPath -WorkflowRunPath $WorkflowRunPath -WorkflowRunId $WorkflowRunId -WorkflowRunsRootAbs $workflowRunsRootAbs
if (-not (Test-IsPathWithin -CandidatePath $workflowAbs -ParentPath $workflowRunsRootAbs)) {
    throw "workflow run must be under workflow runs root."
}
$workflow = Get-Content -LiteralPath $workflowAbs -Raw | ConvertFrom-Json

if ([string]::IsNullOrWhiteSpace([string]$workflow.workflow_run_id)) {
    throw "workflow run is missing workflow_run_id."
}

$bundleId = "sandbox-evidence-bundle-$([Guid]::NewGuid().ToString('N'))"
$manifestRel = $BundlePath
if ([string]::IsNullOrWhiteSpace($manifestRel)) {
    $manifestRel = "$EvidenceBundlesRoot/$bundleId/bundle.manifest.json"
} elseif (-not $manifestRel.ToLowerInvariant().EndsWith(".json")) {
    $manifestRel = ($manifestRel.TrimEnd("/", "\") + "/bundle.manifest.json")
}
$manifestAbs = Get-SafeRelativePathAbs -RelativePath $manifestRel -AllowedRootAbs $evidenceRootAbs -Label "bundle_path"
$bundleDirAbs = Split-Path -Parent $manifestAbs
if (-not (Test-Path -LiteralPath $bundleDirAbs -PathType Container)) {
    New-Item -Path $bundleDirAbs -ItemType Directory -Force | Out-Null
}

$includedArtifacts = [System.Collections.Generic.List[string]]::new()
$copiedArtifactPaths = [System.Collections.Generic.List[string]]::new()
$artifactSha = [ordered]@{}

function Add-Snapshot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceAbs,
        [Parameter(Mandatory = $true)]
        [string]$SnapshotName,
        [Parameter(Mandatory = $true)]
        [string]$ArtifactLabel
    )

    if (-not (Test-Path -LiteralPath $SourceAbs -PathType Leaf)) {
        throw "source artifact not found: $SourceAbs"
    }
    if (-not (Test-IsPathWithin -CandidatePath $SourceAbs -ParentPath $sandboxAnchorAbs)) {
        throw "source artifact escapes sandbox root: $SourceAbs"
    }

    $parsed = Get-Content -LiteralPath $SourceAbs -Raw | ConvertFrom-Json
    $snapshotAbs = Join-Path $bundleDirAbs $SnapshotName
    Write-JsonFile -InputObject $parsed -OutputPath $snapshotAbs

    $snapshotRel = Get-RepoRelativePath -AbsolutePath $snapshotAbs
    $includedArtifacts.Add($ArtifactLabel) | Out-Null
    $copiedArtifactPaths.Add($snapshotRel) | Out-Null
    $artifactSha[$snapshotRel] = (Get-FileHash -LiteralPath $snapshotAbs -Algorithm SHA256).Hash
}

Add-Snapshot -SourceAbs $workflowAbs -SnapshotName "workflow-run.snapshot.json" -ArtifactLabel "workflow_run"

$receiptAbs = $null
if (-not [string]::IsNullOrWhiteSpace([string]$workflow.receipt_path)) {
    $receiptAbs = Get-SafeRelativePathAbs -RelativePath ([string]$workflow.receipt_path) -AllowedRootAbs $sandboxAnchorAbs -Label "receipt_path"
    Add-Snapshot -SourceAbs $receiptAbs -SnapshotName "receipt.snapshot.json" -ArtifactLabel "receipt"
}

$reviewPacketAbs = $null
if (-not [string]::IsNullOrWhiteSpace([string]$workflow.review_packet_path)) {
    $reviewPacketAbs = Get-SafeRelativePathAbs -RelativePath ([string]$workflow.review_packet_path) -AllowedRootAbs $sandboxAnchorAbs -Label "review_packet_path"
    Add-Snapshot -SourceAbs $reviewPacketAbs -SnapshotName "review-packet.snapshot.json" -ArtifactLabel "review_packet"
}

$decisionAbs = $null
if (-not [string]::IsNullOrWhiteSpace([string]$workflow.decision_path)) {
    $decisionAbs = Get-SafeRelativePathAbs -RelativePath ([string]$workflow.decision_path) -AllowedRootAbs $sandboxAnchorAbs -Label "decision_path"
    Add-Snapshot -SourceAbs $decisionAbs -SnapshotName "review-decision.snapshot.json" -ArtifactLabel "review_decision"
}

$planMetadata = [ordered]@{
    input_plan_path = $workflow.input_plan_path
    source_plan_exists = $false
    source_plan_within_sandbox = $false
    source_plan_parsed = $false
    plan_id = $null
    sandbox_scope = $null
    explicit_sandbox_approval = $null
    target_path = $null
}

if (-not [string]::IsNullOrWhiteSpace([string]$workflow.input_plan_path)) {
    $planInput = [string]$workflow.input_plan_path
    $planAbs = $null
    if ([System.IO.Path]::IsPathRooted($planInput)) {
        $planAbs = [System.IO.Path]::GetFullPath($planInput)
    } else {
        $planAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $planInput))
    }

    if (Test-Path -LiteralPath $planAbs -PathType Leaf) {
        $planMetadata.source_plan_exists = $true

        if (Test-IsPathWithin -CandidatePath $planAbs -ParentPath $sandboxAnchorAbs) {
            $planMetadata.source_plan_within_sandbox = $true
            try {
                $planJson = Get-Content -LiteralPath $planAbs -Raw | ConvertFrom-Json
                $planMetadata.source_plan_parsed = $true
                $planMetadata.plan_id = $planJson.plan_id
                $planMetadata.sandbox_scope = $planJson.sandbox_scope
                $planMetadata.explicit_sandbox_approval = $planJson.explicit_sandbox_approval
                $planMetadata.target_path = $planJson.target_path
            } catch {
                $planMetadata.source_plan_parsed = $false
            }
        }
    }
}

$planMetadataAbs = Join-Path $bundleDirAbs "source-plan-metadata.snapshot.json"
Write-JsonFile -InputObject $planMetadata -OutputPath $planMetadataAbs
$planMetadataRel = Get-RepoRelativePath -AbsolutePath $planMetadataAbs
$includedArtifacts.Add("source_plan_metadata") | Out-Null
$copiedArtifactPaths.Add($planMetadataRel) | Out-Null
$artifactSha[$planMetadataRel] = (Get-FileHash -LiteralPath $planMetadataAbs -Algorithm SHA256).Hash

$explicitNonAdmissions = @($workflow.explicit_non_admissions)
if (@($explicitNonAdmissions).Count -eq 0) {
    $explicitNonAdmissions = @($defaultNonAdmissions)
}

$manifest = [ordered]@{
    schema_version = "1.0.0"
    bundle_id = $bundleId
    source_workflow_run_id = [string]$workflow.workflow_run_id
    source_receipt_id = $workflow.receipt_id
    source_review_packet_id = $workflow.review_packet_id
    source_decision_id = $workflow.decision_id
    sandbox_root = "examples/sandbox"
    bundle_path = Get-RepoRelativePath -AbsolutePath $manifestAbs
    included_artifacts = @($includedArtifacts)
    copied_artifact_paths = @($copiedArtifactPaths)
    artifact_sha256 = $artifactSha
    safety_summary = "Sandbox-only evidence bundle export. Authoritative writes, O3DE/AP execution, product resolution, Asset IDs, spawning, and publishing remain blocked."
    explicit_non_admissions = @($explicitNonAdmissions)
    created_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

Write-JsonFile -InputObject $manifest -OutputPath $manifestAbs
$manifest | ConvertTo-Json -Depth 100
