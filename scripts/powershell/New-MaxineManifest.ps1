param(
    [string]$JobId = "",
    [string]$Lane,
    [string]$Status = "queued",
    [string]$CharacterId = "",
    [string]$CharacterName = "",
    [string]$JobType = "",
    [string]$InputPath = "",
    [string]$Prompt = "",
    [string]$OutputPath = "",
    [string]$RetryOf = "",
    [string]$Notes = ""
)

$ErrorActionPreference = "Stop"

$allowedLanes = @(
    "draft_mesh",
    "text_mesh",
    "photo_rig_prep",
    "text_full_rig",
    "external_rig_import",
    "release_character"
)

$allowedStatuses = @(
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
        "fail" { return "fail" }
        default { return "warn" }
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

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

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

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $calledFromInvoke = $false
    foreach ($frame in (Get-PSCallStack)) {
        if ($frame.ScriptName -and $frame.ScriptName -like "*Invoke-MaxineJob.ps1") {
            $calledFromInvoke = $true
            break
        }
    }

    if ($calledFromInvoke) {
        $OutputPath = Join-Path $repoRoot ("evidence\manifests\{0}.manifest.json" -f $JobId)
    }
    else {
        $OutputPath = Join-Path $repoRoot ("examples\manifests\{0}.manifest.json" -f $JobId)
    }
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $repoRoot $OutputPath
}

$parentDir = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($parentDir)) {
    New-Item -ItemType Directory -Force -Path $parentDir | Out-Null
}

$utcNow = (Get-Date).ToUniversalTime().ToString("o")

$manifest = [ordered]@{
    schema_version     = "1.0.0"
    job                = [ordered]@{
        job_id       = $JobId
        lane         = $Lane
        status       = $Status
        job_type     = $JobType
        retry_of     = $RetryOf
        notes        = $Notes
        created_utc  = $utcNow
        updated_utc  = $utcNow
    }
    identity           = [ordered]@{
        character_id   = $CharacterId
        character_name = $CharacterName
    }
    inputs             = [ordered]@{
        input_path      = $InputPath
        prompt          = $Prompt
    }
    generation         = [ordered]@{
        provider        = ""
        output_sources  = @()
    }
    dcc_conform        = [ordered]@{
        status          = "not_started"
        notes           = ""
    }
    o3de               = [ordered]@{
        source_assets   = @()
        products        = @{}
    }
    qc                 = [ordered]@{
        overall         = (Get-QcFromStatus -CurrentStatus $Status)
        gates           = @()
    }
    runtime_validation = [ordered]@{
        smoke_status    = "not_started"
        checks          = @()
    }
    evidence           = [ordered]@{
        logs            = @()
        reports         = @()
        screenshots     = @()
        exit_code       = $null
        message         = ""
    }
    provenance         = [ordered]@{
        adapter_slice   = "manifest-first-adapter"
        created_by      = "New-MaxineManifest.ps1"
        repository_root = $repoRoot
    }
    undo               = [ordered]@{
        rollback_plan   = ""
    }
    cleanup            = [ordered]@{
        temp_paths      = @()
        completed       = $false
    }
}

$manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $OutputPath -Encoding UTF8

Write-Host ("Manifest created: {0}" -f $OutputPath)
Write-Output $OutputPath
