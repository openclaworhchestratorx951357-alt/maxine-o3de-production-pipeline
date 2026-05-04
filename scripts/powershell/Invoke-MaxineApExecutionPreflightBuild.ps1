[CmdletBinding(DefaultParameterSetName = "ByPath")]
param(
    [Parameter(Mandatory = $true, ParameterSetName = "ByPath")]
    [string]$ApEvidenceImportPath,

    [Parameter(Mandatory = $true, ParameterSetName = "ById")]
    [string]$ApEvidenceImportId,

    [Parameter(Mandatory = $true, ParameterSetName = "ByPath")]
    [string]$ProposalPath,

    [Parameter(Mandatory = $true, ParameterSetName = "ById")]
    [string]$ProposalId,

    [string]$ProjectInventoryPath,
    [string]$ProjectInventoryId,

    [string]$OperatorId,
    [string[]]$Notes = @(),
    [string]$ReadinessStatus,
    [string]$OutputPath,

    [string]$ApEvidenceImportsRoot = "examples/sandbox/ap-evidence-imports",
    [string]$ProposalsRoot = "examples/sandbox/product-resolution-proposals",
    [string]$ProjectInventoryRoot = "examples/sandbox/project-inventory",
    [string]$PreflightsRoot = "examples/sandbox/ap-execution-preflights"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$allowedReadinessStatuses = @(
    "blocked_missing_evidence",
    "blocked_safety_boundary",
    "ready_for_future_execution_request",
    "rejected"
)
$forbiddenReadinessStatuses = @(
    "executed",
    "ap_executed",
    "product_resolved",
    "asset_id_resolved",
    "spawned",
    "published"
)

$explicitNonAdmissions = @(
    "authoritative_writes",
    "asset_processor_execution",
    "o3de_editor_execution",
    "o3de_cli_execution",
    "cache_read",
    "live_asset_database_read",
    "product_resolution",
    "product_resolution_as_fact",
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

    if ($Text -notmatch "^[A-Za-z0-9_ ./\\:-]+$") {
        return $false
    }

    return $true
}

function New-DisplayOnlyProposedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot,
        [Parameter(Mandatory = $true)][string]$CandidateRelativePath
    )

    $candidateNormalized = $CandidateRelativePath.Replace("\", "/")
    if ([System.IO.Path]::IsPathRooted($candidateNormalized)) {
        throw "candidate_relative_path must be relative."
    }
    if (($candidateNormalized -split "/") -contains "..") {
        throw "candidate_relative_path contains parent traversal and is blocked."
    }
    if ($candidateNormalized.ToLowerInvariant() -match "(^|/)cache(/|$)") {
        throw "candidate_relative_path cannot include cache paths."
    }
    if ($candidateNormalized.ToLowerInvariant() -match "(^|/)engine(/|$)") {
        throw "candidate_relative_path cannot include engine paths."
    }

    if (-not (Test-SafeDisplayToken -Text $ProjectRoot)) {
        throw "project_root is unsafe for proposed_ap_command_display."
    }
    if (-not (Test-SafeDisplayToken -Text $candidateNormalized)) {
        throw "candidate_relative_path is unsafe for proposed_ap_command_display."
    }

    return "ap_batch_display_only --project-root `"$ProjectRoot`" --candidate `"$candidateNormalized`" --mode preflight_display_only --no_execution"
}

$importsRootAbs = Get-SafeRelativePathAbs -RelativePath $ApEvidenceImportsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "ap_evidence_imports_root"
$proposalsRootAbs = Get-SafeRelativePathAbs -RelativePath $ProposalsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "proposals_root"
$projectInventoryRootAbs = Get-SafeRelativePathAbs -RelativePath $ProjectInventoryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "project_inventory_root"
$preflightsRootAbs = Get-SafeRelativePathAbs -RelativePath $PreflightsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "preflights_root"
if (-not (Test-Path -LiteralPath $preflightsRootAbs -PathType Container)) {
    New-Item -Path $preflightsRootAbs -ItemType Directory -Force | Out-Null
}

if (-not [string]::IsNullOrWhiteSpace($ProjectInventoryPath) -and -not [string]::IsNullOrWhiteSpace($ProjectInventoryId)) {
    throw "Provide either project_inventory_path or project_inventory_id, not both."
}

if ($forbiddenReadinessStatuses -contains $ReadinessStatus) {
    throw "readiness_status '$ReadinessStatus' is forbidden."
}
if (-not [string]::IsNullOrWhiteSpace($ReadinessStatus) -and ($allowedReadinessStatuses -notcontains $ReadinessStatus)) {
    throw "readiness_status '$ReadinessStatus' is invalid."
}

$importRef = $null
$proposalRef = $null
if ($PSCmdlet.ParameterSetName -eq "ByPath") {
    $importRef = Resolve-JsonByPath -InputPath $ApEvidenceImportPath -RootAbs $importsRootAbs -Label "ap_evidence_import_path"
    $proposalRef = Resolve-JsonByPath -InputPath $ProposalPath -RootAbs $proposalsRootAbs -Label "proposal_path"
} else {
    $importRef = Resolve-JsonById -RootAbs $importsRootAbs -IdProperty "ap_evidence_import_id" -IdValue $ApEvidenceImportId
    if ($null -eq $importRef) {
        throw "ap_evidence_import_id '$ApEvidenceImportId' not found."
    }
    $proposalRef = Resolve-JsonById -RootAbs $proposalsRootAbs -IdProperty "proposal_id" -IdValue $ProposalId
    if ($null -eq $proposalRef) {
        throw "proposal_id '$ProposalId' not found."
    }
}

$importItem = $importRef.item
$proposalItem = $proposalRef.item

if ([string]$importItem.sandbox_root -ne "examples/sandbox") {
    throw "AP evidence import sandbox_root must be examples/sandbox."
}
if ([string]$proposalItem.sandbox_root -ne "examples/sandbox") {
    throw "proposal sandbox_root must be examples/sandbox."
}

$projectRef = $null
if (-not [string]::IsNullOrWhiteSpace($ProjectInventoryPath)) {
    $projectRef = Resolve-JsonByPath -InputPath $ProjectInventoryPath -RootAbs $projectInventoryRootAbs -Label "project_inventory_path"
} elseif (-not [string]::IsNullOrWhiteSpace($ProjectInventoryId)) {
    $projectRef = Resolve-JsonById -RootAbs $projectInventoryRootAbs -IdProperty "inventory_id" -IdValue $ProjectInventoryId
    if ($null -eq $projectRef) {
        throw "project_inventory_id '$ProjectInventoryId' not found."
    }
} else {
    $fallbackProjectId = [string]$importItem.source_project_inventory_id
    if ([string]::IsNullOrWhiteSpace($fallbackProjectId)) {
        $fallbackProjectId = [string]$proposalItem.source_project_inventory_id
    }
    if (-not [string]::IsNullOrWhiteSpace($fallbackProjectId)) {
        $projectRef = Resolve-JsonById -RootAbs $projectInventoryRootAbs -IdProperty "inventory_id" -IdValue $fallbackProjectId
    }
}

$requiredNextEvidence = New-Object System.Collections.Generic.List[string]
$requiredNextEvidence.Add("explicit_operator_execution_request") | Out-Null
$requiredNextEvidence.Add("manual_confirmation_step") | Out-Null
$requiredNextEvidence.Add("bounded_local_execution_scope_review") | Out-Null

$blockingMissing = New-Object System.Collections.Generic.List[string]
$blockingSafety = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

if ($null -eq $projectRef) {
    $blockingMissing.Add("missing_project_inventory_context") | Out-Null
    $requiredNextEvidence.Add("project_inventory_context_required") | Out-Null
}

if ([string]::IsNullOrWhiteSpace([string]$importItem.ap_evidence_import_id)) {
    $blockingMissing.Add("missing_ap_evidence_import_id") | Out-Null
}
if ([string]::IsNullOrWhiteSpace([string]$proposalItem.proposal_id)) {
    $blockingMissing.Add("missing_source_proposal_id") | Out-Null
}

if ($importItem.read_only -ne $true) {
    $blockingSafety.Add("ap_evidence_import_not_read_only") | Out-Null
}
foreach ($field in @(
    "asset_processor_execution_admitted",
    "o3de_execution_admitted",
    "cache_access_admitted",
    "live_database_access_admitted",
    "product_ids_claimed",
    "asset_ids_claimed",
    "source_uuids_claimed",
    "product_resolution_claimed",
    "spawn_admitted",
    "publish_admitted"
)) {
    if ($importItem.$field -eq $true) {
        $blockingSafety.Add("ap_evidence_import_widened_$field") | Out-Null
    }
}

if ($proposalItem.proposal_only -ne $true) {
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
    if ($proposalItem.$field -eq $true) {
        $blockingSafety.Add("proposal_widened_$field") | Out-Null
    }
}

$candidateRelativePath = [string]$proposalItem.candidate_relative_path
if ([string]::IsNullOrWhiteSpace($candidateRelativePath)) {
    $candidateRelativePath = "unknown_candidate"
    $blockingMissing.Add("missing_candidate_relative_path") | Out-Null
}

$projectRoot = "."
if ($null -ne $projectRef -and -not [string]::IsNullOrWhiteSpace([string]$projectRef.item.project_root)) {
    $projectRoot = [string]$projectRef.item.project_root
} elseif (-not [string]::IsNullOrWhiteSpace([string]$proposalItem.project_root)) {
    $projectRoot = [string]$proposalItem.project_root
}

if (-not (Test-SafeDisplayToken -Text $projectRoot)) {
    $blockingSafety.Add("project_root_not_safe_for_display") | Out-Null
    $warnings.Add("project_root required sanitization for display-only command") | Out-Null
}

$proposedCommandDisplay = "ap_batch_display_only --mode preflight_display_only --no_execution"
try {
    $proposedCommandDisplay = New-DisplayOnlyProposedCommand -ProjectRoot $projectRoot -CandidateRelativePath $candidateRelativePath
} catch {
    $blockingSafety.Add("proposed_ap_command_display_invalid") | Out-Null
    $warnings.Add([string]$_.Exception.Message) | Out-Null
}

if ($proposedCommandDisplay -match "[|><;&`]") {
    $blockingSafety.Add("proposed_ap_command_display_contains_shell_operator") | Out-Null
}
if ($proposedCommandDisplay.ToLowerInvariant() -match "cache") {
    $blockingSafety.Add("proposed_ap_command_display_contains_cache_path") | Out-Null
}

foreach ($note in $Notes) {
    $text = [string]$note
    if (-not [string]::IsNullOrWhiteSpace($text)) {
        $warnings.Add("operator_note: $text") | Out-Null
    }
}

$derivedStatus = "ready_for_future_execution_request"
if ($blockingSafety.Count -gt 0) {
    $derivedStatus = "blocked_safety_boundary"
} elseif ($blockingMissing.Count -gt 0) {
    $derivedStatus = "blocked_missing_evidence"
}

if (-not [string]::IsNullOrWhiteSpace($ReadinessStatus)) {
    $derivedStatus = $ReadinessStatus
}

$readyForFutureExecutionRequest = $false
if ($derivedStatus -eq "ready_for_future_execution_request") {
    $readyForFutureExecutionRequest = $true
}

$preflightId = "ap-execution-preflight-$([Guid]::NewGuid().ToString('N'))"
$outputRel = $OutputPath
if ([string]::IsNullOrWhiteSpace($outputRel)) {
    $outputRel = "$PreflightsRoot/$preflightId.json"
}
$outputAbs = Get-SafeRelativePathAbs -RelativePath $outputRel -AllowedRootAbs $preflightsRootAbs -Label "output_path"

$resolvedProjectInventoryId = ""
if ($null -ne $projectRef) {
    $resolvedProjectInventoryId = [string]$projectRef.item.inventory_id
}
if ([string]::IsNullOrWhiteSpace($resolvedProjectInventoryId)) {
    $resolvedProjectInventoryId = [string]$importItem.source_project_inventory_id
}
if ([string]::IsNullOrWhiteSpace($resolvedProjectInventoryId)) {
    $resolvedProjectInventoryId = [string]$proposalItem.source_project_inventory_id
}
if ([string]::IsNullOrWhiteSpace($resolvedProjectInventoryId)) {
    $resolvedProjectInventoryId = "unknown-project-inventory-id"
}

$payload = [ordered]@{
    schema_version = "1.0.0"
    preflight_id = $preflightId
    source_ap_evidence_import_id = [string]$importItem.ap_evidence_import_id
    source_proposal_id = [string]$proposalItem.proposal_id
    source_project_inventory_id = [string]$resolvedProjectInventoryId
    sandbox_root = "examples/sandbox"
    project_root = $projectRoot
    candidate_relative_path = $candidateRelativePath
    proposed_ap_command_display = $proposedCommandDisplay
    proposed_working_directory = $projectRoot
    required_manual_confirmation = $true
    local_only = $true
    execution_admitted = $false
    ready_for_future_execution_request = $readyForFutureExecutionRequest
    readiness_status = $derivedStatus
    required_next_evidence = @($requiredNextEvidence | Sort-Object -Unique)
    blocking_reasons = @($blockingMissing + $blockingSafety | Sort-Object -Unique)
    warnings = @($warnings | Sort-Object -Unique)
    safety_summary = "Display-only AP execution preflight artifact. No execution is performed and no Product IDs, Asset IDs, source UUID claims, cache access, live database access, spawning, publishing, or authoritative writes are admitted."
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
