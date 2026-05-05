[CmdletBinding(DefaultParameterSetName = "ByPath")]
param(
    [Parameter(Mandatory = $true, ParameterSetName = "ByPath")]
    [string]$PreflightPath,

    [Parameter(Mandatory = $true, ParameterSetName = "ById")]
    [string]$PreflightId,

    [switch]$ApproveLocalDiagnosticExecution,
    [ValidateSet("DiagnosticOnly")]
    [string]$ExecutionMode = "DiagnosticOnly",
    [switch]$UseMockDiagnosticCommand,
    [switch]$SimulateTimeout,
    [ValidateRange(1, 600)]
    [int]$TimeoutSeconds = 30,
    [string]$OutputPath,

    [string]$PreflightsRoot = "examples/sandbox/ap-execution-preflights",
    [string]$DiagnosticExecutionsRoot = "examples/sandbox/ap-diagnostic-executions"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$explicitNonAdmissions = @(
    "authoritative_writes",
    "asset_processor_execution",
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

function Resolve-Preflight {
    param(
        [string]$PreflightPath,
        [string]$PreflightId,
        [string]$RootAbs
    )

    $hasPath = -not [string]::IsNullOrWhiteSpace($PreflightPath)
    $hasId = -not [string]::IsNullOrWhiteSpace($PreflightId)
    if (($hasPath -and $hasId) -or (-not $hasPath -and -not $hasId)) {
        throw "Provide either preflight_path or preflight_id."
    }

    if ($hasPath) {
        $pathAbs = $null
        if ([System.IO.Path]::IsPathRooted($PreflightPath)) {
            $pathAbs = [System.IO.Path]::GetFullPath($PreflightPath)
            if (-not (Test-IsPathWithin -CandidatePath $pathAbs -ParentPath $RootAbs)) {
                throw "preflight_path must remain under ap-execution-preflights."
            }
        } else {
            $pathAbs = Get-SafeRelativePathAbs -RelativePath $PreflightPath -AllowedRootAbs $RootAbs -Label "preflight_path"
        }

        if (-not (Test-Path -LiteralPath $pathAbs -PathType Leaf)) {
            throw "preflight_path not found: $PreflightPath"
        }

        $item = Get-Content -LiteralPath $pathAbs -Raw | ConvertFrom-Json
        return [ordered]@{ path = $pathAbs; item = $item }
    }

    $match = Resolve-JsonById -RootAbs $RootAbs -IdProperty "preflight_id" -IdValue $PreflightId
    if ($null -eq $match) {
        throw "preflight_id '$PreflightId' not found."
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

function Get-Sha256OrEmpty {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ""
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return ""
    }

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Test-SafeDisplayCommand {
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

    $lower = $Text.ToLowerInvariant()
    if ($lower.Contains("cache")) {
        return $false
    }
    if ($lower.Contains("assetdb.sqlite") -or $lower.Contains(".sqlite")) {
        return $false
    }
    if ($lower.Contains("engine\\") -or $lower.Contains("engine/")) {
        return $false
    }

    return $true
}

function Get-AllowlistedCommand {
    param([switch]$UseMock)

    if (-not $UseMock) {
        return $null
    }

    return [ordered]@{
        command_source = "allowlisted_mock_diagnostic"
        command_display = 'powershell -NoProfile -Command "Write-Output ''MAXINE_AP_DIAGNOSTIC_MOCK''"'
        file_path = "powershell"
        arguments = '-NoProfile -Command "Write-Output ''MAXINE_AP_DIAGNOSTIC_MOCK''"'
    }
}

$preflightsRootAbs = Get-SafeRelativePathAbs -RelativePath $PreflightsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "preflights_root"
$diagnosticRootAbs = Get-SafeRelativePathAbs -RelativePath $DiagnosticExecutionsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "diagnostic_executions_root"
if (-not (Test-Path -LiteralPath $diagnosticRootAbs -PathType Container)) {
    New-Item -Path $diagnosticRootAbs -ItemType Directory -Force | Out-Null
}

$preflightRef = Resolve-Preflight -PreflightPath $PreflightPath -PreflightId $PreflightId -RootAbs $preflightsRootAbs
$preflight = $preflightRef.item

if ([string]::IsNullOrWhiteSpace([string]$preflight.preflight_id)) {
    throw "preflight is missing preflight_id."
}
if ([string]$preflight.sandbox_root -ne "examples/sandbox") {
    throw "preflight sandbox_root must be examples/sandbox."
}
if ([string]::IsNullOrWhiteSpace([string]$preflight.output_path)) {
    throw "preflight output_path is required."
}

$executionId = "ap-diagnostic-execution-$([Guid]::NewGuid().ToString('N'))"
$outputRel = $OutputPath
if ([string]::IsNullOrWhiteSpace($outputRel)) {
    $outputRel = "$DiagnosticExecutionsRoot/$executionId.json"
}
$outputAbs = Get-SafeRelativePathAbs -RelativePath $outputRel -AllowedRootAbs $diagnosticRootAbs -Label "output_path"

$stdoutAbs = [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $outputAbs) "$executionId.stdout.txt"))
$stderrAbs = [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $outputAbs) "$executionId.stderr.txt"))
if (-not (Test-IsPathWithin -CandidatePath $stdoutAbs -ParentPath $diagnosticRootAbs)) {
    throw "stdout_path escapes the approved sandbox root."
}
if (-not (Test-IsPathWithin -CandidatePath $stderrAbs -ParentPath $diagnosticRootAbs)) {
    throw "stderr_path escapes the approved sandbox root."
}

$blockedReasons = New-Object System.Collections.Generic.List[string]

if (-not $ApproveLocalDiagnosticExecution.IsPresent) {
    $blockedReasons.Add("execution is blocked without approval flag ApproveLocalDiagnosticExecution.") | Out-Null
}

if ($ExecutionMode -ne "DiagnosticOnly") {
    $blockedReasons.Add("execution mode must be DiagnosticOnly.") | Out-Null
}

if ([bool]$preflight.required_manual_confirmation -ne $true) {
    $blockedReasons.Add("preflight required_manual_confirmation must be true.") | Out-Null
}

if ([bool]$preflight.local_only -ne $true) {
    $blockedReasons.Add("preflight local_only must be true.") | Out-Null
}

if ([bool]$preflight.execution_admitted -eq $true) {
    $blockedReasons.Add("preflight execution_admitted=true is forbidden for diagnostic execution.") | Out-Null
}

if ([string]$preflight.readiness_status -ne "ready_for_future_execution_request") {
    $blockedReasons.Add("preflight readiness_status must be ready_for_future_execution_request.") | Out-Null
}

$preflightCommandDisplay = [string]$preflight.proposed_ap_command_display
if (-not (Test-SafeDisplayCommand -Text $preflightCommandDisplay)) {
    $blockedReasons.Add("preflight proposed_ap_command_display contains shell operators/pipelines/redirection/traversal or blocked targets.") | Out-Null
}
if ($preflightCommandDisplay -notmatch '^ap_batch_display_only\s+--project-root\s+"?.+"?\s+--candidate\s+"?.+"?\s+--mode\s+preflight_display_only\s+--no_execution$') {
    $blockedReasons.Add("command source is arbitrary user text and is blocked.") | Out-Null
}

$proposedWorkingDirectory = [string]$preflight.proposed_working_directory
if ([string]::IsNullOrWhiteSpace($proposedWorkingDirectory)) {
    $blockedReasons.Add("preflight proposed_working_directory is required.") | Out-Null
} else {
    $workingAbs = $null
    if ([System.IO.Path]::IsPathRooted($proposedWorkingDirectory)) {
        $workingAbs = [System.IO.Path]::GetFullPath($proposedWorkingDirectory)
    } else {
        $workingAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $proposedWorkingDirectory))
    }

    if (-not (Test-IsPathWithin -CandidatePath $workingAbs -ParentPath $repoRoot)) {
        $blockedReasons.Add("proposed_working_directory must remain repo-local.") | Out-Null
    }
    $workingLower = $workingAbs.ToLowerInvariant()
    if ($workingLower.Contains("\\cache\\") -or $workingLower.EndsWith("\\cache") -or $workingLower.Contains("/cache/") -or $workingLower.EndsWith("/cache")) {
        $blockedReasons.Add("proposed_working_directory cannot target Cache paths.") | Out-Null
    }
    if ($workingLower.Contains("\\engine\\") -or $workingLower.EndsWith("\\engine") -or $workingLower.Contains("/engine/") -or $workingLower.EndsWith("/engine")) {
        $blockedReasons.Add("proposed_working_directory cannot target engine paths.") | Out-Null
    }
}

$allowlistedCommand = Get-AllowlistedCommand -UseMock:$UseMockDiagnosticCommand.IsPresent
if ($null -eq $allowlistedCommand) {
    $blockedReasons.Add("mock diagnostic command allowlist flag UseMockDiagnosticCommand is required in this slice.") | Out-Null
}

$startedUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$executionStatus = "blocked"
$exitCode = $null
$commandExecuted = $false
$commandAllowlisted = $false
$blockedReasonText = ""
$stdoutText = ""
$stderrText = ""
$commandSource = "preflight_display_allowlist"
$commandDisplay = $preflightCommandDisplay

if ($blockedReasons.Count -eq 0) {
    $commandSource = [string]$allowlistedCommand.command_source
    $commandDisplay = [string]$allowlistedCommand.command_display
    $commandAllowlisted = $true

    if ($SimulateTimeout.IsPresent) {
        $commandExecuted = $true
        $executionStatus = "timed_out"
        $exitCode = 124
        $stdoutText = "MAXINE_AP_DIAGNOSTIC_TIMEOUT_SIMULATED"
        $stderrText = "MAXINE_AP_DIAGNOSTIC_TIMEOUT_SIMULATED"
    } else {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = [string]$allowlistedCommand.file_path
        $psi.Arguments = [string]$allowlistedCommand.arguments
        $psi.WorkingDirectory = $repoRoot
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true

        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $psi

        [void]$process.Start()
        if ($process.WaitForExit($TimeoutSeconds * 1000)) {
            $stdoutText = $process.StandardOutput.ReadToEnd()
            $stderrText = $process.StandardError.ReadToEnd()
            $exitCode = $process.ExitCode
            $commandExecuted = $true
            if ($exitCode -eq 0) {
                $executionStatus = "succeeded"
            } else {
                $executionStatus = "failed"
            }
        } else {
            try {
                $process.Kill()
            } catch {
                # no-op
            }
            $stdoutText = "MAXINE_AP_DIAGNOSTIC_TIMEOUT"
            $stderrText = "MAXINE_AP_DIAGNOSTIC_TIMEOUT"
            $exitCode = 124
            $commandExecuted = $true
            $executionStatus = "timed_out"
        }
    }
}

if ($commandExecuted) {
    [System.IO.File]::WriteAllText($stdoutAbs, $stdoutText, [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText($stderrAbs, $stderrText, [System.Text.UTF8Encoding]::new($false))
} else {
    $blockedReasonText = ($blockedReasons -join " ")
}

$completedUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

$record = [ordered]@{
    schema_version = "1.0.0"
    diagnostic_execution_id = $executionId
    source_preflight_id = [string]$preflight.preflight_id
    sandbox_root = "examples/sandbox"
    project_root = [string]$preflight.project_root
    execution_mode = $ExecutionMode
    approved_by_flag = [bool]$ApproveLocalDiagnosticExecution.IsPresent
    command_source = $commandSource
    command_display = $commandDisplay
    command_executed = [bool]$commandExecuted
    command_allowlisted = [bool]$commandAllowlisted
    local_only = $true
    timeout_seconds = $TimeoutSeconds
    exit_code = $exitCode
    stdout_path = $(if ($commandExecuted) { Get-RepoRelativePath -AbsolutePath $stdoutAbs } else { "" })
    stderr_path = $(if ($commandExecuted) { Get-RepoRelativePath -AbsolutePath $stderrAbs } else { "" })
    stdout_sha256 = $(if ($commandExecuted) { Get-Sha256OrEmpty -Path $stdoutAbs } else { "" })
    stderr_sha256 = $(if ($commandExecuted) { Get-Sha256OrEmpty -Path $stderrAbs } else { "" })
    execution_status = $executionStatus
    blocked_reason = $(if ($commandExecuted) { "" } else { $blockedReasonText })
    product_ids_claimed = $false
    asset_ids_claimed = $false
    source_uuids_claimed = $false
    product_resolution_claimed = $false
    cache_access_admitted = $false
    live_database_access_admitted = $false
    spawn_admitted = $false
    publish_admitted = $false
    explicit_non_admissions = @($explicitNonAdmissions)
    output_path = Get-RepoRelativePath -AbsolutePath $outputAbs
    started_utc = $startedUtc
    completed_utc = $completedUtc
}

Write-JsonFile -InputObject $record -OutputPath $outputAbs
$record | ConvertTo-Json -Depth 100
