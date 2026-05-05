[CmdletBinding()]
param(
    [string]$ReviewPacketPath,
    [string]$ReviewPacketId,
    [string]$ProposalPath,
    [string]$ProposalId,
    [string]$ApBinaryPreflightPath,
    [string]$ApBinaryPreflightId,
    [string]$RealBinaryDiagnosticExecutionPath,
    [string]$RealBinaryDiagnosticExecutionId,
    [string]$ProjectInventoryPath,
    [string]$ProjectInventoryId,

    [string]$OperatorId,
    [string[]]$Notes = @(),
    [string]$ReadinessStatus,
    [string]$OutputPath,

    [string]$ReviewPacketsRoot = "examples/sandbox/asset-candidate-review-packets",
    [string]$ProposalsRoot = "examples/sandbox/product-resolution-proposals",
    [string]$ApBinaryPreflightsRoot = "examples/sandbox/ap-binary-preflights",
    [string]$RealBinaryDiagnosticExecutionsRoot = "examples/sandbox/ap-real-binary-diagnostic-executions",
    [string]$ProjectInventoryRoot = "examples/sandbox/project-inventory",
    [string]$SourceFileDiagnosticPreflightsRoot = "examples/sandbox/ap-source-file-diagnostic-preflights"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$allowedReadinessStatuses = @(
    "blocked_missing_evidence",
    "blocked_safety_boundary",
    "ready_for_future_source_file_diagnostic_request",
    "rejected"
)
$forbiddenReadinessStatuses = @(
    "executed",
    "ap_executed",
    "asset_processed",
    "product_resolved",
    "asset_id_resolved",
    "source_uuid_resolved",
    "spawned",
    "published"
)

$explicitNonAdmissions = @(
    "authoritative_writes",
    "asset_processor_execution",
    "real_asset_processor_execution",
    "ap_source_file_processing_execution",
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

    return [ordered]@{ path = $pathAbs; item = $item }
}

function Resolve-JsonInput {
    param(
        [string]$InputPath,
        [string]$InputId,
        [Parameter(Mandatory = $true)]
        [string]$RootAbs,
        [Parameter(Mandatory = $true)]
        [string]$IdProperty,
        [Parameter(Mandatory = $true)]
        [string]$PathLabel,
        [Parameter(Mandatory = $true)]
        [string]$IdLabel,
        [bool]$Required = $true
    )

    $hasPath = -not [string]::IsNullOrWhiteSpace($InputPath)
    $hasId = -not [string]::IsNullOrWhiteSpace($InputId)

    if ($hasPath -and $hasId) {
        throw "Provide either $PathLabel or $IdLabel, not both."
    }
    if (-not $hasPath -and -not $hasId) {
        if ($Required) {
            throw "Provide either $PathLabel or $IdLabel."
        }
        return $null
    }

    if ($hasPath) {
        return Resolve-JsonByPath -InputPath $InputPath -RootAbs $RootAbs -Label $PathLabel
    }

    $match = Resolve-JsonById -RootAbs $RootAbs -IdProperty $IdProperty -IdValue $InputId
    if ($null -eq $match) {
        throw "$IdLabel '$InputId' not found."
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

function Test-SafeDisplayToken {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $false
    }
    if ($Text.Contains("`n") -or $Text.Contains("`r")) {
        return $false
    }
    if ($Text -match "[|><;&`]") {
        return $false
    }
    if ($Text.Contains("..")) {
        return $false
    }

    return $true
}

function Test-SafeDisplayCommand {
    param([string]$Text)

    if (-not (Test-SafeDisplayToken -Text $Text)) {
        return $false
    }

    $lower = $Text.ToLowerInvariant()
    foreach ($blocked in @("cache", "assetdb.sqlite", ".sqlite", "--scan", "scanfolder", "--product", ".azmodel", ".spawnable")) {
        if ($lower.Contains($blocked)) {
            return $false
        }
    }

    return $true
}

function Resolve-AnyPathAbs {
    param([Parameter(Mandatory = $true)][string]$PathText)

    if ([System.IO.Path]::IsPathRooted($PathText)) {
        return [System.IO.Path]::GetFullPath($PathText)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $repoRoot $PathText))
}

function Get-HashOrEmpty {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ""
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return ""
    }

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

if ($forbiddenReadinessStatuses -contains $ReadinessStatus) {
    throw "readiness_status '$ReadinessStatus' is forbidden."
}
if (-not [string]::IsNullOrWhiteSpace($ReadinessStatus) -and ($allowedReadinessStatuses -notcontains $ReadinessStatus)) {
    throw "readiness_status '$ReadinessStatus' is invalid."
}

$reviewPacketsRootAbs = Get-SafeRelativePathAbs -RelativePath $ReviewPacketsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "review_packets_root"
$proposalsRootAbs = Get-SafeRelativePathAbs -RelativePath $ProposalsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "proposals_root"
$apBinaryPreflightsRootAbs = Get-SafeRelativePathAbs -RelativePath $ApBinaryPreflightsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "ap_binary_preflights_root"
$realBinaryDiagnosticExecutionsRootAbs = Get-SafeRelativePathAbs -RelativePath $RealBinaryDiagnosticExecutionsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "real_binary_diagnostic_executions_root"
$projectInventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $ProjectInventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "project_inventory_root"
$sourceFileDiagnosticPreflightsRootAbs = Get-SafeRelativePathAbs -RelativePath $SourceFileDiagnosticPreflightsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "source_file_diagnostic_preflights_root"
if (-not (Test-Path -LiteralPath $sourceFileDiagnosticPreflightsRootAbs -PathType Container)) {
    New-Item -Path $sourceFileDiagnosticPreflightsRootAbs -ItemType Directory -Force | Out-Null
}

$reviewRef = Resolve-JsonInput -InputPath $ReviewPacketPath -InputId $ReviewPacketId -RootAbs $reviewPacketsRootAbs -IdProperty "review_packet_id" -PathLabel "review_packet_path" -IdLabel "review_packet_id" -Required $true
$proposalRef = Resolve-JsonInput -InputPath $ProposalPath -InputId $ProposalId -RootAbs $proposalsRootAbs -IdProperty "proposal_id" -PathLabel "proposal_path" -IdLabel "proposal_id" -Required $true
$apBinaryPreflightRef = Resolve-JsonInput -InputPath $ApBinaryPreflightPath -InputId $ApBinaryPreflightId -RootAbs $apBinaryPreflightsRootAbs -IdProperty "ap_binary_preflight_id" -PathLabel "ap_binary_preflight_path" -IdLabel "ap_binary_preflight_id" -Required $true
$projectInventoryRef = Resolve-JsonInput -InputPath $ProjectInventoryPath -InputId $ProjectInventoryId -RootAbs $projectInventoryRootAbs -IdProperty "inventory_id" -PathLabel "project_inventory_path" -IdLabel "project_inventory_id" -Required $true
$realBinaryDiagnosticRef = Resolve-JsonInput -InputPath $RealBinaryDiagnosticExecutionPath -InputId $RealBinaryDiagnosticExecutionId -RootAbs $realBinaryDiagnosticExecutionsRootAbs -IdProperty "real_binary_diagnostic_execution_id" -PathLabel "real_binary_diagnostic_execution_path" -IdLabel "real_binary_diagnostic_execution_id" -Required $false

$review = $reviewRef.item
$proposal = $proposalRef.item
$apBinaryPreflight = $apBinaryPreflightRef.item
$projectInventory = $projectInventoryRef.item
$realBinaryDiagnostic = $null
if ($null -ne $realBinaryDiagnosticRef) {
    $realBinaryDiagnostic = $realBinaryDiagnosticRef.item
}

$requiredNextEvidence = New-Object System.Collections.Generic.List[string]
$blockingMissing = New-Object System.Collections.Generic.List[string]
$blockingSafety = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

$requiredNextEvidence.Add("explicit_operator_execution_request") | Out-Null
$requiredNextEvidence.Add("manual_confirmation_step") | Out-Null
$requiredNextEvidence.Add("single_source_file_scope_confirmation") | Out-Null
$requiredNextEvidence.Add("future_source_file_diagnostic_execution_request") | Out-Null

if ([string]$review.sandbox_root -ne "examples/sandbox") {
    $blockingSafety.Add("review_packet_not_sandbox_scoped") | Out-Null
}
if ([string]$proposal.sandbox_root -ne "examples/sandbox") {
    $blockingSafety.Add("proposal_not_sandbox_scoped") | Out-Null
}
if ([string]$apBinaryPreflight.sandbox_root -ne "examples/sandbox") {
    $blockingSafety.Add("ap_binary_preflight_not_sandbox_scoped") | Out-Null
}
if ([string]$projectInventory.sandbox_root -ne "examples/sandbox") {
    $blockingSafety.Add("project_inventory_not_sandbox_scoped") | Out-Null
}
if ($null -ne $realBinaryDiagnostic -and [string]$realBinaryDiagnostic.sandbox_root -ne "examples/sandbox") {
    $blockingSafety.Add("real_binary_diagnostic_execution_not_sandbox_scoped") | Out-Null
}

if ([string]::IsNullOrWhiteSpace([string]$review.review_packet_id)) {
    $blockingMissing.Add("missing_review_packet_id") | Out-Null
}
if ([string]::IsNullOrWhiteSpace([string]$proposal.proposal_id)) {
    $blockingMissing.Add("missing_proposal_id") | Out-Null
}
if ([string]::IsNullOrWhiteSpace([string]$apBinaryPreflight.ap_binary_preflight_id)) {
    $blockingMissing.Add("missing_ap_binary_preflight_id") | Out-Null
}
if ([string]::IsNullOrWhiteSpace([string]$projectInventory.inventory_id)) {
    $blockingMissing.Add("missing_project_inventory_id") | Out-Null
}

if ([string]$proposal.source_review_packet_id -ne [string]$review.review_packet_id) {
    $blockingSafety.Add("proposal_source_review_packet_mismatch") | Out-Null
}
if ([string]$proposal.candidate_relative_path -ne [string]$review.candidate_relative_path) {
    $blockingSafety.Add("proposal_candidate_relative_path_mismatch") | Out-Null
}

if ($proposal.proposal_only -ne $true) {
    $blockingSafety.Add("proposal_not_marked_proposal_only") | Out-Null
}
foreach ($field in @(
    "product_ids_claimed",
    "asset_ids_claimed",
    "source_uuids_claimed",
    "asset_processor_execution_admitted",
    "o3de_execution_admitted",
    "cache_access_admitted",
    "spawn_admitted",
    "publish_admitted"
)) {
    if ($proposal.$field -eq $true) {
        $blockingSafety.Add("proposal_widened_$field") | Out-Null
    }
}

if ($apBinaryPreflight.required_manual_confirmation -ne $true) {
    $blockingSafety.Add("ap_binary_preflight_required_manual_confirmation_not_true") | Out-Null
}
if ($apBinaryPreflight.local_only -ne $true) {
    $blockingSafety.Add("ap_binary_preflight_local_only_not_true") | Out-Null
}
if ($apBinaryPreflight.execution_admitted -eq $true) {
    $blockingSafety.Add("ap_binary_preflight_execution_admitted_true") | Out-Null
}
if ([string]$apBinaryPreflight.readiness_status -ne "ready_for_future_real_ap_execution_request") {
    $blockingMissing.Add("ap_binary_preflight_not_ready_for_future_real_ap_execution_request") | Out-Null
}
if ($apBinaryPreflight.binary_exists -ne $true) {
    $blockingMissing.Add("ap_binary_preflight_binary_missing") | Out-Null
}
if ($apBinaryPreflight.binary_allowed_for_future_execution_request -ne $true) {
    $blockingMissing.Add("ap_binary_preflight_binary_not_allowed_for_future_execution_request") | Out-Null
}
$binaryKind = [string]$apBinaryPreflight.binary_kind
if ($binaryKind -notin @("AssetProcessorBatch", "AssetProcessor")) {
    $blockingSafety.Add("ap_binary_preflight_binary_kind_not_allowed") | Out-Null
}

if ($null -eq $realBinaryDiagnostic) {
    $requiredNextEvidence.Add("real_binary_diagnostic_execution_preferred") | Out-Null
} else {
    if ([string]$realBinaryDiagnostic.execution_mode -ne "RealBinaryDiagnosticOnly") {
        $blockingSafety.Add("real_binary_diagnostic_execution_mode_not_supported") | Out-Null
    }
    if ([string]$realBinaryDiagnostic.source_ap_binary_preflight_id -ne [string]$apBinaryPreflight.ap_binary_preflight_id) {
        $blockingSafety.Add("real_binary_diagnostic_preflight_link_mismatch") | Out-Null
    }
    if ($realBinaryDiagnostic.local_only -ne $true) {
        $blockingSafety.Add("real_binary_diagnostic_not_local_only") | Out-Null
    }
    foreach ($field in @(
        "product_ids_claimed",
        "asset_ids_claimed",
        "source_uuids_claimed",
        "product_resolution_claimed",
        "cache_access_admitted",
        "live_database_access_admitted",
        "spawn_admitted",
        "publish_admitted"
    )) {
        if ($realBinaryDiagnostic.$field -eq $true) {
            $blockingSafety.Add("real_binary_diagnostic_widened_$field") | Out-Null
        }
    }
}

$candidateRelativePath = [string]$review.candidate_relative_path
$candidateRelativePathNormalized = $candidateRelativePath.Replace("\", "/")
if ([string]::IsNullOrWhiteSpace($candidateRelativePathNormalized)) {
    $blockingMissing.Add("missing_candidate_relative_path") | Out-Null
} else {
    if ([System.IO.Path]::IsPathRooted($candidateRelativePathNormalized) -or $candidateRelativePathNormalized.StartsWith("/")) {
        $blockingSafety.Add("candidate_relative_path_must_be_relative") | Out-Null
    }
    if (($candidateRelativePathNormalized -split "/") -contains "..") {
        $blockingSafety.Add("candidate_relative_path_contains_parent_traversal") | Out-Null
    }
    if ($candidateRelativePathNormalized.Contains("*") -or $candidateRelativePathNormalized.Contains("?")) {
        $blockingSafety.Add("candidate_relative_path_must_be_single_file_not_wildcard") | Out-Null
    }

    $candidateLower = $candidateRelativePathNormalized.ToLowerInvariant()
    if ($candidateLower -match "(^|/)cache(/|$)") {
        $blockingSafety.Add("candidate_relative_path_references_cache") | Out-Null
    }
    if ($candidateLower.Contains("assetdb.sqlite") -or $candidateLower.EndsWith(".sqlite")) {
        $blockingSafety.Add("candidate_relative_path_references_database") | Out-Null
    }
    if ($candidateLower.EndsWith(".azmodel") -or $candidateLower.EndsWith(".spawnable")) {
        $blockingSafety.Add("candidate_relative_path_looks_like_product_output") | Out-Null
    }
}

$projectRoot = [string]$projectInventory.project_root
if ([string]::IsNullOrWhiteSpace($projectRoot)) {
    $blockingMissing.Add("missing_project_root") | Out-Null
    $projectRoot = "."
}
if (-not (Test-SafeDisplayToken -Text $projectRoot)) {
    $blockingSafety.Add("project_root_unsafe_for_display") | Out-Null
}

if (-not [string]::IsNullOrWhiteSpace([string]$review.project_root) -and ([string]$review.project_root -ne $projectRoot)) {
    $warnings.Add("review packet project_root differs from provided project inventory project_root") | Out-Null
}

$candidateSha256 = [string]$review.sha256
if ([string]::IsNullOrWhiteSpace($candidateSha256) -or $candidateSha256 -notmatch "^[a-fA-F0-9]{64}$") {
    $candidateSha256 = [string]$proposal.candidate_sha256
}

$candidatePathAbs = ""
if ($blockingSafety.Count -eq 0 -and -not [string]::IsNullOrWhiteSpace($candidateRelativePathNormalized)) {
    try {
        $candidatePathAbs = Resolve-AnyPathAbs -PathText $candidateRelativePathNormalized
        if (-not (Test-Path -LiteralPath $candidatePathAbs -PathType Leaf)) {
            $blockingMissing.Add("candidate_source_file_not_found") | Out-Null
        } else {
            $actualHash = Get-HashOrEmpty -Path $candidatePathAbs
            if ([string]::IsNullOrWhiteSpace($candidateSha256) -or $candidateSha256 -notmatch "^[a-fA-F0-9]{64}$") {
                $candidateSha256 = $actualHash
            } elseif ($actualHash -ne $candidateSha256.ToLowerInvariant()) {
                $warnings.Add("candidate sha256 differs from source review packet evidence") | Out-Null
            }
        }
    } catch {
        $blockingSafety.Add("candidate_relative_path_resolve_failed") | Out-Null
    }
}

if ([string]::IsNullOrWhiteSpace($candidateSha256) -or $candidateSha256 -notmatch "^[a-fA-F0-9]{64}$") {
    $blockingMissing.Add("missing_candidate_sha256") | Out-Null
    $candidateSha256 = "0000000000000000000000000000000000000000000000000000000000000000"
}

$candidateExtension = [string]$review.candidate_extension
if ([string]::IsNullOrWhiteSpace($candidateExtension)) {
    $candidateExtension = [string]$proposal.candidate_extension
}
if ([string]::IsNullOrWhiteSpace($candidateExtension)) {
    $candidateExtension = ".unknown"
    $blockingMissing.Add("missing_candidate_extension") | Out-Null
}

$candidateCategory = [string]$review.candidate_category
if ([string]::IsNullOrWhiteSpace($candidateCategory)) {
    $candidateCategory = [string]$proposal.candidate_category
}
if ([string]::IsNullOrWhiteSpace($candidateCategory)) {
    $candidateCategory = "unknown_source"
    $blockingMissing.Add("missing_candidate_category") | Out-Null
}

$selectedBinaryPath = [string]$apBinaryPreflight.selected_binary_path
if ([string]::IsNullOrWhiteSpace($selectedBinaryPath)) {
    $blockingMissing.Add("missing_selected_binary_path") | Out-Null
}
$selectedBinaryNormalized = $selectedBinaryPath.Replace("\", "/")
if (($selectedBinaryNormalized -split "/") -contains "..") {
    $blockingSafety.Add("selected_binary_path_contains_parent_traversal") | Out-Null
}
$selectedLower = $selectedBinaryNormalized.ToLowerInvariant()
if ($selectedLower -match "(^|/)cache(/|$)") {
    $blockingSafety.Add("selected_binary_path_references_cache") | Out-Null
}
if ($selectedLower.Contains("assetdb.sqlite") -or $selectedLower.EndsWith(".sqlite")) {
    $blockingSafety.Add("selected_binary_path_references_database") | Out-Null
}
if ($selectedBinaryNormalized.Contains("|") -or $selectedBinaryNormalized.Contains(";") -or $selectedBinaryNormalized.Contains(">") -or $selectedBinaryNormalized.Contains("<")) {
    $blockingSafety.Add("selected_binary_path_contains_shell_operators") | Out-Null
}

$selectedBinaryDisplay = $selectedBinaryPath
try {
    if (-not [string]::IsNullOrWhiteSpace($selectedBinaryPath)) {
        $selectedBinaryAbs = Resolve-AnyPathAbs -PathText $selectedBinaryPath
        $selectedBinaryDisplay = Get-RepoRelativePath -AbsolutePath $selectedBinaryAbs
    }
} catch {
    $blockingSafety.Add("selected_binary_path_resolve_failed") | Out-Null
}

$proposedCommandDisplay = "display_only_source_file_diagnostic_command_not_ready"
if (-not [string]::IsNullOrWhiteSpace($selectedBinaryDisplay) -and -not [string]::IsNullOrWhiteSpace($candidateRelativePathNormalized)) {
    $proposedCommandDisplay = "`"$selectedBinaryDisplay`" --help --source-file `"$candidateRelativePathNormalized`" --mode source_file_diagnostic_display_only --no-execution"
}

if (-not (Test-SafeDisplayCommand -Text $proposedCommandDisplay)) {
    $blockingSafety.Add("proposed_diagnostic_command_display_contains_shell_operator_or_blocked_target") | Out-Null
}
if ($proposedCommandDisplay.ToLowerInvariant().Contains("--scan") -or $proposedCommandDisplay.ToLowerInvariant().Contains("scanfolder")) {
    $blockingSafety.Add("proposed_diagnostic_command_display_contains_whole_project_scan") | Out-Null
}
$sourceFileSwitchCount = ([regex]::Matches($proposedCommandDisplay, "--source-file")).Count
if ($sourceFileSwitchCount -ne 1) {
    $blockingSafety.Add("proposed_diagnostic_command_display_must_be_single_candidate_only") | Out-Null
}
if (-not $proposedCommandDisplay.Contains($candidateRelativePathNormalized)) {
    $blockingSafety.Add("proposed_diagnostic_command_display_missing_candidate_reference") | Out-Null
}

foreach ($note in $Notes) {
    $text = [string]$note
    if (-not [string]::IsNullOrWhiteSpace($text)) {
        $warnings.Add("operator_note: $text") | Out-Null
    }
}

$derivedStatus = "ready_for_future_source_file_diagnostic_request"
if ($blockingSafety.Count -gt 0) {
    $derivedStatus = "blocked_safety_boundary"
} elseif ($blockingMissing.Count -gt 0) {
    $derivedStatus = "blocked_missing_evidence"
}
if (-not [string]::IsNullOrWhiteSpace($ReadinessStatus)) {
    $derivedStatus = $ReadinessStatus
}

$readyForFutureExecutionRequest = $derivedStatus -eq "ready_for_future_source_file_diagnostic_request"

$preflightId = "ap-source-file-diagnostic-preflight-$([Guid]::NewGuid().ToString('N'))"
$outputRel = $OutputPath
if ([string]::IsNullOrWhiteSpace($outputRel)) {
    $outputRel = "$SourceFileDiagnosticPreflightsRoot/$preflightId.json"
}
$outputAbs = Get-SafeRelativePathAbs -RelativePath $outputRel -AllowedRootAbs $sourceFileDiagnosticPreflightsRootAbs -Label "output_path"

$sourceRealBinaryDiagnosticExecutionId = ""
if ($null -ne $realBinaryDiagnostic) {
    $sourceRealBinaryDiagnosticExecutionId = [string]$realBinaryDiagnostic.real_binary_diagnostic_execution_id
}

$payload = [ordered]@{
    schema_version = "1.0.0"
    source_file_diagnostic_preflight_id = $preflightId
    source_review_packet_id = [string]$review.review_packet_id
    source_proposal_id = [string]$proposal.proposal_id
    source_ap_binary_preflight_id = [string]$apBinaryPreflight.ap_binary_preflight_id
    source_real_binary_diagnostic_execution_id = $sourceRealBinaryDiagnosticExecutionId
    source_project_inventory_id = [string]$projectInventory.inventory_id
    sandbox_root = "examples/sandbox"
    project_root = $projectRoot
    candidate_relative_path = $candidateRelativePathNormalized
    candidate_sha256 = $candidateSha256.ToLowerInvariant()
    candidate_extension = $candidateExtension
    candidate_category = $candidateCategory
    selected_binary_path = $selectedBinaryDisplay
    binary_kind = $binaryKind
    proposed_diagnostic_command_display = $proposedCommandDisplay
    proposed_working_directory = $projectRoot
    required_manual_confirmation = $true
    local_only = $true
    execution_admitted = $false
    ready_for_future_execution_request = $readyForFutureExecutionRequest
    readiness_status = $derivedStatus
    required_next_evidence = @($requiredNextEvidence | Sort-Object -Unique)
    blocking_reasons = @($blockingMissing + $blockingSafety | Sort-Object -Unique)
    warnings = @($warnings | Sort-Object -Unique)
    safety_summary = "Source-file AP diagnostic preflight is display-only and non-executing. It scopes to one source candidate only, does not run Asset Processor, does not read Cache or live asset database, does not resolve products, and does not admit Product IDs, Asset IDs, source UUID claims, spawning, or publishing."
    explicit_non_admissions = @($explicitNonAdmissions)
    output_path = Get-RepoRelativePath -AbsolutePath $outputAbs
    created_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

if (-not [string]::IsNullOrWhiteSpace($OperatorId)) {
    $payload.operator_id = $OperatorId
}
if ($Notes.Count -gt 0) {
    $payload.notes = @($Notes)
}

Write-JsonFile -InputObject $payload -OutputPath $outputAbs
$payload | ConvertTo-Json -Depth 100
