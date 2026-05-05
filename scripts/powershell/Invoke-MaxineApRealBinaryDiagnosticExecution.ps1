[CmdletBinding(DefaultParameterSetName = "ByPath")]
param(
    [Parameter(Mandatory = $true, ParameterSetName = "ByPath")]
    [string]$ApBinaryPreflightPath,

    [Parameter(Mandatory = $true, ParameterSetName = "ById")]
    [string]$ApBinaryPreflightId,

    [switch]$ApproveRealBinaryDiagnosticExecution,
    [ValidateSet("RealBinaryDiagnosticOnly")]
    [string]$ExecutionMode = "RealBinaryDiagnosticOnly",
    [string]$DiagnosticArgument = "--version",
    [switch]$UseSimulatedCommandMode,
    [switch]$SimulateTimeout,
    [ValidateRange(1, 600)]
    [int]$TimeoutSeconds = 30,
    [string]$OutputPath,

    [string]$ApBinaryPreflightsRoot = "examples/sandbox/ap-binary-preflights",
    [string]$RealBinaryDiagnosticExecutionsRoot = "examples/sandbox/ap-real-binary-diagnostic-executions"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$allowedDiagnosticArguments = @(
    "--help",
    "-help",
    "/?",
    "--version",
    "-version"
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

function Resolve-ApBinaryPreflight {
    param(
        [string]$ApBinaryPreflightPath,
        [string]$ApBinaryPreflightId,
        [string]$RootAbs
    )

    $hasPath = -not [string]::IsNullOrWhiteSpace($ApBinaryPreflightPath)
    $hasId = -not [string]::IsNullOrWhiteSpace($ApBinaryPreflightId)
    if (($hasPath -and $hasId) -or (-not $hasPath -and -not $hasId)) {
        throw "Provide either ap_binary_preflight_path or ap_binary_preflight_id."
    }

    if ($hasPath) {
        $pathAbs = $null
        if ([System.IO.Path]::IsPathRooted($ApBinaryPreflightPath)) {
            $pathAbs = [System.IO.Path]::GetFullPath($ApBinaryPreflightPath)
            if (-not (Test-IsPathWithin -CandidatePath $pathAbs -ParentPath $RootAbs)) {
                throw "ap_binary_preflight_path must remain under ap-binary-preflights."
            }
        } else {
            $pathAbs = Get-SafeRelativePathAbs -RelativePath $ApBinaryPreflightPath -AllowedRootAbs $RootAbs -Label "ap_binary_preflight_path"
        }

        if (-not (Test-Path -LiteralPath $pathAbs -PathType Leaf)) {
            throw "ap_binary_preflight_path not found: $ApBinaryPreflightPath"
        }

        $item = Get-Content -LiteralPath $pathAbs -Raw | ConvertFrom-Json
        return [ordered]@{ path = $pathAbs; item = $item }
    }

    $match = Resolve-JsonById -RootAbs $RootAbs -IdProperty "ap_binary_preflight_id" -IdValue $ApBinaryPreflightId
    if ($null -eq $match) {
        throw "ap_binary_preflight_id '$ApBinaryPreflightId' not found."
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

function Test-IsDiagnosticArgumentAllowlisted {
    param([string]$Argument)

    return $allowedDiagnosticArguments -contains $Argument
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

    return $true
}

function Resolve-BinaryPathAbs {
    param([Parameter(Mandatory = $true)][string]$PathText)

    if ([System.IO.Path]::IsPathRooted($PathText)) {
        return [System.IO.Path]::GetFullPath($PathText)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $repoRoot $PathText))
}

$apBinaryPreflightsRootAbs = Get-SafeRelativePathAbs -RelativePath $ApBinaryPreflightsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "ap_binary_preflights_root"
$diagnosticExecutionsRootAbs = Get-SafeRelativePathAbs -RelativePath $RealBinaryDiagnosticExecutionsRoot -AllowedRootAbs $sandboxAnchorAbs -Label "real_binary_diagnostic_executions_root"
if (-not (Test-Path -LiteralPath $diagnosticExecutionsRootAbs -PathType Container)) {
    New-Item -Path $diagnosticExecutionsRootAbs -ItemType Directory -Force | Out-Null
}

$preflightRef = Resolve-ApBinaryPreflight -ApBinaryPreflightPath $ApBinaryPreflightPath -ApBinaryPreflightId $ApBinaryPreflightId -RootAbs $apBinaryPreflightsRootAbs
$preflight = $preflightRef.item

if ([string]::IsNullOrWhiteSpace([string]$preflight.ap_binary_preflight_id)) {
    throw "AP binary preflight is missing ap_binary_preflight_id."
}
if ([string]$preflight.sandbox_root -ne "examples/sandbox") {
    throw "AP binary preflight sandbox_root must be examples/sandbox."
}
if ([string]::IsNullOrWhiteSpace([string]$preflight.output_path)) {
    throw "AP binary preflight output_path is required."
}

$executionId = "ap-real-binary-diagnostic-execution-$([Guid]::NewGuid().ToString('N'))"
$outputRel = $OutputPath
if ([string]::IsNullOrWhiteSpace($outputRel)) {
    $outputRel = "$RealBinaryDiagnosticExecutionsRoot/$executionId.json"
}
$outputAbs = Get-SafeRelativePathAbs -RelativePath $outputRel -AllowedRootAbs $diagnosticExecutionsRootAbs -Label "output_path"

$stdoutAbs = [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $outputAbs) "$executionId.stdout.txt"))
$stderrAbs = [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $outputAbs) "$executionId.stderr.txt"))
if (-not (Test-IsPathWithin -CandidatePath $stdoutAbs -ParentPath $diagnosticExecutionsRootAbs)) {
    throw "stdout_path escapes the approved sandbox root."
}
if (-not (Test-IsPathWithin -CandidatePath $stderrAbs -ParentPath $diagnosticExecutionsRootAbs)) {
    throw "stderr_path escapes the approved sandbox root."
}

$blockedReasons = New-Object System.Collections.Generic.List[string]

if (-not $ApproveRealBinaryDiagnosticExecution.IsPresent) {
    $blockedReasons.Add("execution is blocked without approval flag ApproveRealBinaryDiagnosticExecution.") | Out-Null
}

if ($ExecutionMode -ne "RealBinaryDiagnosticOnly") {
    $blockedReasons.Add("execution mode must be RealBinaryDiagnosticOnly.") | Out-Null
}

if ($preflight.required_manual_confirmation -ne $true) {
    $blockedReasons.Add("AP binary preflight required_manual_confirmation must be true.") | Out-Null
}
if ($preflight.local_only -ne $true) {
    $blockedReasons.Add("AP binary preflight local_only must be true.") | Out-Null
}
if ($preflight.execution_admitted -eq $true) {
    $blockedReasons.Add("AP binary preflight execution_admitted=true is forbidden for diagnostic execution.") | Out-Null
}
if ([string]$preflight.readiness_status -ne "ready_for_future_real_ap_execution_request") {
    $blockedReasons.Add("AP binary preflight readiness_status must be ready_for_future_real_ap_execution_request.") | Out-Null
}
if ($preflight.binary_exists -ne $true) {
    $blockedReasons.Add("AP binary preflight binary_exists must be true.") | Out-Null
}
if ($preflight.binary_allowed_for_future_execution_request -ne $true) {
    $blockedReasons.Add("AP binary preflight binary_allowed_for_future_execution_request must be true.") | Out-Null
}

$binaryKind = [string]$preflight.binary_kind
if ($binaryKind -notin @("AssetProcessorBatch", "AssetProcessor")) {
    $blockedReasons.Add("binary_kind '$binaryKind' is not allowed for this diagnostic execution slice.") | Out-Null
}

if (-not (Test-IsDiagnosticArgumentAllowlisted -Argument $DiagnosticArgument)) {
    $blockedReasons.Add("diagnostic_argument '$DiagnosticArgument' is not allowlisted. Allowed values are --help, -help, /?, --version, -version.") | Out-Null
}

$selectedBinaryPathText = [string]$preflight.selected_binary_path
if ([string]::IsNullOrWhiteSpace($selectedBinaryPathText)) {
    $blockedReasons.Add("selected_binary_path is required.") | Out-Null
}

$selectedLowerText = $selectedBinaryPathText.Replace("\", "/").ToLowerInvariant()
if (($selectedLowerText -split "/") -contains "..") {
    $blockedReasons.Add("selected binary path contains parent traversal and is blocked.") | Out-Null
}
if ($selectedLowerText -match "(^|/)cache(/|$)") {
    $blockedReasons.Add("selected binary path includes Cache and is blocked.") | Out-Null
}
if ($selectedLowerText.Contains("assetdb.sqlite") -or $selectedLowerText.EndsWith(".sqlite")) {
    $blockedReasons.Add("selected binary path includes assetdb.sqlite or sqlite database token and is blocked.") | Out-Null
}

$selectedBinaryAbs = ""
if (-not [string]::IsNullOrWhiteSpace($selectedBinaryPathText)) {
    try {
        $selectedBinaryAbs = Resolve-BinaryPathAbs -PathText $selectedBinaryPathText
    } catch {
        $blockedReasons.Add("selected binary path is not a valid filesystem path and is blocked.") | Out-Null
        $selectedBinaryAbs = ""
    }
}

if (-not [string]::IsNullOrWhiteSpace($selectedBinaryAbs)) {
    $selectedAbsLower = $selectedBinaryAbs.Replace("\", "/").ToLowerInvariant()
    if ($selectedAbsLower -match "(^|/)cache(/|$)") {
        $blockedReasons.Add("resolved selected binary path includes Cache and is blocked.") | Out-Null
    }
    if ($selectedAbsLower.Contains("assetdb.sqlite") -or $selectedAbsLower.EndsWith(".sqlite")) {
        $blockedReasons.Add("resolved selected binary path includes assetdb.sqlite or sqlite database token and is blocked.") | Out-Null
    }

    if ((-not $UseSimulatedCommandMode.IsPresent) -and (-not (Test-Path -LiteralPath $selectedBinaryAbs -PathType Leaf))) {
        $blockedReasons.Add("selected binary path does not exist for real execution attempt.") | Out-Null
    }
}

$commandDisplay = ""
if (-not [string]::IsNullOrWhiteSpace($selectedBinaryAbs)) {
    $commandDisplay = '"' + $selectedBinaryAbs + '" ' + $DiagnosticArgument
}
if (-not (Test-SafeDisplayCommand -Text $commandDisplay)) {
    $blockedReasons.Add("command display contains shell operators/pipelines/redirection/traversal or blocked targets.") | Out-Null
}

$startedUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$executionStatus = "blocked"
$exitCode = $null
$commandExecuted = $false
$commandAllowlisted = $false
$blockedReasonText = ""
$stdoutText = ""
$stderrText = ""
$recordedCommandDisplay = $commandDisplay

if ($blockedReasons.Count -eq 0) {
    $commandAllowlisted = $true

    if ($UseSimulatedCommandMode.IsPresent) {
        $recordedCommandDisplay = "allowlisted_simulated_ap_real_binary_diagnostic $DiagnosticArgument"
        $commandExecuted = $true
        if ($SimulateTimeout.IsPresent) {
            $executionStatus = "timed_out"
            $exitCode = 124
            $stdoutText = "MAXINE_AP_REAL_BINARY_DIAGNOSTIC_TIMEOUT_SIMULATED"
            $stderrText = "MAXINE_AP_REAL_BINARY_DIAGNOSTIC_TIMEOUT_SIMULATED"
        } else {
            $executionStatus = "succeeded"
            $exitCode = 0
            $stdoutText = "MAXINE_AP_REAL_BINARY_DIAGNOSTIC_SIMULATED $DiagnosticArgument"
            $stderrText = ""
        }
    } else {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $selectedBinaryAbs
        $psi.Arguments = $DiagnosticArgument
        $psi.WorkingDirectory = $repoRoot
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true

        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $psi

        try {
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
                    $blockedReasonText = "real binary diagnostic command exited non-zero."
                }
            } else {
                try {
                    $process.Kill()
                } catch {
                    # no-op
                }
                $stdoutText = "MAXINE_AP_REAL_BINARY_DIAGNOSTIC_TIMEOUT"
                $stderrText = "MAXINE_AP_REAL_BINARY_DIAGNOSTIC_TIMEOUT"
                $exitCode = 124
                $commandExecuted = $true
                $executionStatus = "timed_out"
                $blockedReasonText = "real binary diagnostic command timed out."
            }
        } catch {
            $commandExecuted = $true
            $executionStatus = "failed"
            $exitCode = -1
            $stdoutText = ""
            $stderrText = [string]$_.Exception.Message
            $blockedReasonText = "real binary diagnostic launch failed: $stderrText"
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

$selectedBinaryOutputPath = ""
if (-not [string]::IsNullOrWhiteSpace($selectedBinaryAbs)) {
    $selectedBinaryOutputPath = Get-RepoRelativePath -AbsolutePath $selectedBinaryAbs
}

$record = [ordered]@{
    schema_version = "1.0.0"
    real_binary_diagnostic_execution_id = $executionId
    source_ap_binary_preflight_id = [string]$preflight.ap_binary_preflight_id
    sandbox_root = "examples/sandbox"
    selected_binary_path = $selectedBinaryOutputPath
    binary_kind = $binaryKind
    execution_mode = "RealBinaryDiagnosticOnly"
    approved_by_flag = [bool]$ApproveRealBinaryDiagnosticExecution.IsPresent
    diagnostic_argument = $DiagnosticArgument
    command_display = $recordedCommandDisplay
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
    blocked_reason = $blockedReasonText
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
