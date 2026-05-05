[CmdletBinding()]
param(
    [string]$DiscoveryPath,
    [string]$DiscoveryId,
    [string]$ApExecutionPreflightPath,
    [string]$ApExecutionPreflightId,
    [string]$OperatorId,
    [string[]]$Notes = @(),
    [string]$OutputPath,

    [string]$DiscoveryRoot = "examples/sandbox/ap-binary-discovery",
    [string]$ApExecutionPreflightsRoot = "examples/sandbox/ap-execution-preflights",
    [string]$BinaryPreflightsRoot = "examples/sandbox/ap-binary-preflights"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$allowedReadinessStatuses = @(
    "blocked_missing_binary",
    "blocked_unsupported_binary",
    "ready_for_future_real_ap_execution_request",
    "rejected"
)

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

function Resolve-JsonByPath {
    param(
        [Parameter(Mandatory = $true)][string]$InputPath,
        [Parameter(Mandatory = $true)][string]$RootAbs,
        [Parameter(Mandatory = $true)][string]$Label
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

function Resolve-CandidatePath {
    param([Parameter(Mandatory = $true)][string]$PathText)

    if ([System.IO.Path]::IsPathRooted($PathText)) {
        return [System.IO.Path]::GetFullPath($PathText)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $repoRoot $PathText))
}

if ([string]::IsNullOrWhiteSpace($DiscoveryPath) -eq [string]::IsNullOrWhiteSpace($DiscoveryId)) {
    throw "Provide exactly one of discovery_path or discovery_id."
}
if ([string]::IsNullOrWhiteSpace($ApExecutionPreflightPath) -eq [string]::IsNullOrWhiteSpace($ApExecutionPreflightId)) {
    throw "Provide exactly one of ap_execution_preflight_path or ap_execution_preflight_id."
}

$discoveryRootAbs = Get-SafeRelativePathAbs -RelativePath $DiscoveryRoot -AllowedRootAbs $sandboxAnchorAbs -Label "discovery_root"
$apExecutionPreflightsRootAbs = Get-SafeRelativePathAbs -RelativePath $ApExecutionPreflightsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "ap_execution_preflights_root"
$binaryPreflightsRootAbs = Get-SafeRelativePathAbs -RelativePath $BinaryPreflightsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "binary_preflights_root"
if (-not (Test-Path -LiteralPath $binaryPreflightsRootAbs -PathType Container)) {
    New-Item -Path $binaryPreflightsRootAbs -ItemType Directory -Force | Out-Null
}

$discoveryRef = $null
if (-not [string]::IsNullOrWhiteSpace($DiscoveryPath)) {
    $discoveryRef = Resolve-JsonByPath -InputPath $DiscoveryPath -RootAbs $discoveryRootAbs -Label "discovery_path"
} else {
    $discoveryRef = Resolve-JsonById -RootAbs $discoveryRootAbs -IdProperty "discovery_id" -IdValue $DiscoveryId
    if ($null -eq $discoveryRef) {
        throw "discovery_id '$DiscoveryId' not found."
    }
}

$apExecutionPreflightRef = $null
if (-not [string]::IsNullOrWhiteSpace($ApExecutionPreflightPath)) {
    $apExecutionPreflightRef = Resolve-JsonByPath -InputPath $ApExecutionPreflightPath -RootAbs $apExecutionPreflightsRootAbs -Label "ap_execution_preflight_path"
} else {
    $apExecutionPreflightRef = Resolve-JsonById -RootAbs $apExecutionPreflightsRootAbs -IdProperty "preflight_id" -IdValue $ApExecutionPreflightId
    if ($null -eq $apExecutionPreflightRef) {
        throw "ap_execution_preflight_id '$ApExecutionPreflightId' not found."
    }
}

$discovery = $discoveryRef.item
$apExecutionPreflight = $apExecutionPreflightRef.item

$warnings = New-Object System.Collections.Generic.List[string]
$blockingReasons = New-Object System.Collections.Generic.List[string]

if ($discovery.read_only -ne $true) {
    $blockingReasons.Add("source discovery record must be read_only=true.") | Out-Null
}
if ($discovery.execution_admitted -ne $false) {
    $blockingReasons.Add("source discovery record must keep execution_admitted=false.") | Out-Null
}

if ($apExecutionPreflight.required_manual_confirmation -ne $true) {
    $blockingReasons.Add("source AP execution preflight must require manual confirmation.") | Out-Null
}
if ($apExecutionPreflight.local_only -ne $true) {
    $blockingReasons.Add("source AP execution preflight must remain local_only=true.") | Out-Null
}
if ($apExecutionPreflight.execution_admitted -ne $false) {
    $blockingReasons.Add("source AP execution preflight must keep execution_admitted=false.") | Out-Null
}
if ([string]$apExecutionPreflight.readiness_status -ne "ready_for_future_execution_request") {
    $blockingReasons.Add("source AP execution preflight readiness_status is not ready_for_future_execution_request.") | Out-Null
}

$selectedBinaryAbs = $null
$selectedBinaryKind = "unknown"
$binaryExists = $false

$existingCandidates = @($discovery.existing_candidates)
if ($existingCandidates.Count -eq 0) {
    $blockingReasons.Add("no existing binary candidates were discovered.") | Out-Null
} else {
    $supported = $existingCandidates | Where-Object {
        $kind = Get-BinaryKindFromPath -PathText ([string]$_.candidate_path)
        $kind -in @("AssetProcessorBatch", "AssetProcessor")
    }

    $picked = $null
    if (@($supported).Count -gt 0) {
        $picked = @($supported)[0]
    } else {
        $picked = @($existingCandidates)[0]
    }

    $selectedBinaryAbs = Resolve-CandidatePath -PathText ([string]$picked.candidate_path)
    $selectedBinaryKind = Get-BinaryKindFromPath -PathText $selectedBinaryAbs
    $binaryExists = Test-Path -LiteralPath $selectedBinaryAbs -PathType Leaf

    $lowerSelected = $selectedBinaryAbs.Replace("\", "/").ToLowerInvariant()
    if (($lowerSelected -split "/") -contains "..") {
        $blockingReasons.Add("selected binary path contains parent traversal and is blocked.") | Out-Null
    }
    if ($lowerSelected -match "(^|/)cache(/|$)") {
        $blockingReasons.Add("selected binary path cannot include cache paths.") | Out-Null
    }
    if ($lowerSelected.Contains("assetdb.sqlite")) {
        $blockingReasons.Add("selected binary path cannot reference assetdb.sqlite.") | Out-Null
    }

    if (-not $binaryExists) {
        $blockingReasons.Add("selected binary path does not exist.") | Out-Null
    }
    if ($selectedBinaryKind -eq "unknown") {
        $blockingReasons.Add("selected binary kind is unsupported for future execution request.") | Out-Null
    }
}

$readinessStatus = "ready_for_future_real_ap_execution_request"
if (@($blockingReasons).Count -gt 0) {
    if ($blockingReasons -contains "no existing binary candidates were discovered." -or
        $blockingReasons -contains "selected binary path does not exist.") {
        $readinessStatus = "blocked_missing_binary"
    } elseif ($blockingReasons -contains "selected binary kind is unsupported for future execution request.") {
        $readinessStatus = "blocked_unsupported_binary"
    } else {
        $readinessStatus = "rejected"
    }
}

if ($readinessStatus -notin $allowedReadinessStatuses) {
    throw "computed readiness_status '$readinessStatus' is not allowed."
}

$binaryAllowed = ($readinessStatus -eq "ready_for_future_real_ap_execution_request")
$preflightId = "ap-binary-preflight-" + [Guid]::NewGuid().ToString("N")
$timestampUtc = [DateTime]::UtcNow.ToString("o")

$outputAbs = $null
if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
    if ([System.IO.Path]::IsPathRooted($OutputPath)) {
        $outputAbs = [System.IO.Path]::GetFullPath($OutputPath)
        if (-not (Test-IsPathWithin -CandidatePath $outputAbs -ParentPath $binaryPreflightsRootAbs)) {
            throw "output_path must remain under ap-binary-preflights root."
        }
    } else {
        $outputAbs = Get-SafeRelativePathAbs -RelativePath $OutputPath -AllowedRootAbs $binaryPreflightsRootAbs -Label "output_path"
    }
} else {
    $outputAbs = Join-Path $binaryPreflightsRootAbs "$preflightId.json"
}

$selectedBinaryOut = ""
if (-not [string]::IsNullOrWhiteSpace($selectedBinaryAbs)) {
    $selectedBinaryOut = Get-RepoRelativePath -AbsolutePath $selectedBinaryAbs
}

$outputRel = Get-RepoRelativePath -AbsolutePath $outputAbs
$blockingReasonsOut = @($blockingReasons.ToArray())
$warningsOut = @($warnings.ToArray())
$record = [ordered]@{
    schema_version = "1.0.0"
    ap_binary_preflight_id = $preflightId
    source_discovery_id = [string]$discovery.discovery_id
    source_ap_execution_preflight_id = [string]$apExecutionPreflight.preflight_id
    sandbox_root = "examples/sandbox"
    selected_binary_path = $selectedBinaryOut
    binary_kind = $selectedBinaryKind
    binary_exists = [bool]$binaryExists
    binary_allowed_for_future_execution_request = [bool]$binaryAllowed
    execution_admitted = $false
    required_manual_confirmation = $true
    local_only = $true
    readiness_status = $readinessStatus
    blocking_reasons = $blockingReasonsOut
    warnings = $warningsOut
    safety_summary = "Read-only binary discovery plus non-executing preflight only; real AP execution remains blocked."
    explicit_non_admissions = @($explicitNonAdmissions)
    output_path = $outputRel
    created_utc = $timestampUtc
}

if (-not [string]::IsNullOrWhiteSpace($OperatorId)) {
    $record["operator_id"] = $OperatorId
}
if ($Notes.Count -gt 0) {
    $record["notes"] = @($Notes)
}

Write-JsonFile -InputObject $record -OutputPath $outputAbs
$record | ConvertTo-Json -Depth 100
