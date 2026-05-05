param(
    [string]$JobId = "",
    [string]$Lane,
    [string]$Status = "created",
    [string]$CharacterId = "",
    [string]$CharacterName = "",
    [string]$PackageId = "",
    [string]$DisplayName = "",
    [string]$Tier = "unknown",
    [string]$PackageVersion = "0.1.0",
    [string]$Operator = "unknown",
    [string]$JobType = "",
    [string]$InputPath = "",
    [string]$Prompt = "",
    [string]$Project = "",
    [string]$Platform = "pc",
    [string]$ArtifactRoot = "",
    [string]$OutputPath = "",
    [string]$RetryOf = "",
    [string]$Notes = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "MaxineManifestHelpers.ps1")

$allowedLanes = @(
    "draft_mesh",
    "text_mesh",
    "photo_rig_prep",
    "text_full_rig",
    "external_rig_import",
    "release_character"
)

$allowedStatuses = @(
    "created",
    "cancelled",
    "pass",
    "warn",
    "fail",
    "pending_manual",
    "running",
    "queued"
)

function New-JobId {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $rand = Get-Random -Minimum 1000 -Maximum 9999
    return "maxine-$stamp-$rand"
}

function ConvertTo-Slug {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
    $slug = $Value.ToLowerInvariant()
    $slug = $slug -replace "[^a-z0-9]+", "-"
    $slug = $slug.Trim("-")
    if ([string]::IsNullOrWhiteSpace($slug)) { return "" }
    return $slug
}

function Get-QcFromStatus {
    param([string]$CurrentStatus)
    switch ($CurrentStatus) {
        "pass" { return "pass" }
        "warn" { return "warn" }
        "fail" { return "fail" }
        default { return "not_run" }
    }
}

if ($allowedLanes -notcontains $Lane) {
    Write-Error ("Invalid lane '{0}'. Allowed lanes: {1}" -f $Lane, ($allowedLanes -join ", "))
    exit 1
}

if ($allowedStatuses -notcontains $Status) {
    Write-Error ("Invalid status '{0}'. Allowed statuses: {1}" -f $Status, ($allowedStatuses -join ", "))
    exit 1
}

$allowedTiers = @("draft", "npc", "hero", "test", "unknown")
if ($allowedTiers -notcontains $Tier) {
    Write-Error ("Invalid tier '{0}'. Allowed tiers: {1}" -f $Tier, ($allowedTiers -join ", "))
    exit 1
}

$allowedOperators = @("human", "service", "ci", "unknown")
if ($allowedOperators -notcontains $Operator) {
    Write-Error ("Invalid operator '{0}'. Allowed operators: {1}" -f $Operator, ($allowedOperators -join ", "))
    exit 1
}

$repoRoot = Resolve-MaxineRepoRoot -ScriptRoot $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($JobId)) {
    $JobId = New-JobId
}

if ([string]::IsNullOrWhiteSpace($CharacterName)) {
    $CharacterName = "UnknownCharacter"
}

if ([string]::IsNullOrWhiteSpace($CharacterId)) {
    $charSlug = ConvertTo-Slug -Value $CharacterName
    if ([string]::IsNullOrWhiteSpace($charSlug)) {
        $charSlug = "unknown-character"
    }
    $CharacterId = $charSlug
}

if ([string]::IsNullOrWhiteSpace($DisplayName)) {
    $DisplayName = $CharacterName
}

if ([string]::IsNullOrWhiteSpace($PackageId)) {
    $PackageId = $CharacterId
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $calledFromInvoke = $false
    foreach ($frame in (Get-PSCallStack)) {
        if ($frame.ScriptName -and $frame.ScriptName -like "*Invoke-MaxineJob.ps1") {
            $calledFromInvoke = $true
            break
        }
    }

    if ($calledFromInvoke) {
        $OutputPath = Join-Path $repoRoot ("evidence\jobs\{0}\manifest.json" -f $JobId)
    }
    else {
        $OutputPath = Join-Path $repoRoot ("examples\manifests\{0}.manifest.json" -f $JobId)
    }
}
else {
    $OutputPath = Resolve-MaxinePath -Path $OutputPath -RepoRoot $repoRoot
}

if ([string]::IsNullOrWhiteSpace($ArtifactRoot)) {
    if ($OutputPath -like "*\evidence\jobs\*\manifest.json") {
        $ArtifactRoot = Split-Path -Parent $OutputPath
    }
    else {
        $ArtifactRoot = Join-Path $repoRoot ("evidence\jobs\{0}" -f $JobId)
    }
}
else {
    $ArtifactRoot = Resolve-MaxinePath -Path $ArtifactRoot -RepoRoot $repoRoot
}

foreach ($dir in @(
        $ArtifactRoot,
        (Join-Path $ArtifactRoot "logs"),
        (Join-Path $ArtifactRoot "screenshots"),
        (Join-Path $ArtifactRoot "o3de"),
        (Join-Path $ArtifactRoot "qc"),
        (Join-Path $ArtifactRoot "temp"),
        (Join-Path $ArtifactRoot "undo"),
        (Join-Path $ArtifactRoot "cleanup"),
        (Join-Path $ArtifactRoot "reports")
    )) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

$utcNow = Get-MaxineUtcNow
$inputItems = @()
if (-not [string]::IsNullOrWhiteSpace($InputPath)) {
    $inputItems += [ordered]@{
        kind = "path"
        path = $InputPath
    }
}
if (-not [string]::IsNullOrWhiteSpace($Prompt)) {
    $inputItems += [ordered]@{
        kind   = "prompt"
        prompt = $Prompt
    }
}

$manifest = [ordered]@{
    schema_version     = "1.0.0"
    job                = [ordered]@{
        job_id       = $JobId
        lane         = $Lane
        status       = $Status
        submitted_at = $utcNow
        started_at   = $null
        finished_at  = $null
        operator     = $Operator
        job_type     = $JobType
        retry_of     = $(if ([string]::IsNullOrWhiteSpace($RetryOf)) { $null } else { $RetryOf })
        notes        = $Notes
        created_utc  = $utcNow
        updated_utc  = $utcNow
    }
    identity           = [ordered]@{
        package_id     = $PackageId
        display_name   = $DisplayName
        tier           = $Tier
        package_version= $PackageVersion
        character_id   = $CharacterId
        character_name = $CharacterName
    }
    inputs             = $inputItems
    generation         = [ordered]@{
        provider        = ""
        output_sources  = @()
    }
    dcc_conform        = [ordered]@{
        status          = "not_started"
        notes           = ""
    }
    o3de               = [ordered]@{
        project         = $(if ([string]::IsNullOrWhiteSpace($Project)) { $null } else { $Project })
        platform        = $(if ([string]::IsNullOrWhiteSpace($Platform)) { $null } else { $Platform })
        source_assets   = @()
        expected_products = @()
        products        = @()
    }
    qc                 = [ordered]@{
        overall         = (Get-QcFromStatus -CurrentStatus $Status)
        checks          = @()
        gates           = @()
    }
    runtime_validation = [ordered]@{
        spawned         = $false
        entity_id       = $null
        screenshots     = @()
        smoke_status    = "not_started"
        checks          = @()
    }
    evidence           = [ordered]@{
        manifest_path   = $OutputPath
        artifact_root   = $ArtifactRoot
        logs            = @()
        screenshots     = @()
        stdout_log      = $null
        stderr_log      = $null
        reports         = @()
        exit_code       = $null
        message         = ""
    }
    errors             = @()
    provenance         = [ordered]@{
        source_commit   = $null
        pipeline_revision = $null
        build_run_id    = $null
        adapter_slice   = "manifest-first-adapter"
        created_by      = "New-MaxineManifest.ps1"
        repository_root = $repoRoot
    }
    undo               = [ordered]@{
        available       = $false
        steps           = @()
        rollback_plan   = ""
    }
    cleanup            = [ordered]@{
        retention_class = "unknown"
        paths           = @((Join-Path $ArtifactRoot "temp"), (Join-Path $ArtifactRoot "cleanup"))
        temp_paths      = @()
        completed       = $false
    }
    manual_review      = [ordered]@{
        required        = $false
        reason          = $null
        review_state    = "not_required"
    }
}

Write-MaxineJsonAtomic -Path $OutputPath -Data $manifest -Depth 40
Invoke-MaxineManifestValidation -ManifestPath $OutputPath -RepoRoot $repoRoot

Write-Host ("Manifest created: {0}" -f $OutputPath)
Write-Output $OutputPath
