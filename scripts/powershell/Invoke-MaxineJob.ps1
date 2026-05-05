param(
    [Parameter(Mandatory = $true)]
    [string]$JobType,
    [string]$CharacterName = "",
    [string]$InputPath = "",
    [string]$Prompt = "",
    [string]$ExistingFactoryToolsPath = "C:\Users\topgu\OneDrive\Documents\O3de_GEMS_Research\Projects\MaxineShow\Tools",
    [string]$OutputRoot = "evidence/jobs",
    [switch]$DryRun,
    [switch]$PassThru,
    [string]$RetryOf = ""
)

$ErrorActionPreference = "Stop"

$jobTypeMap = @{
    "photo_mesh"          = [ordered]@{ Lane = "draft_mesh"; Script = "create_mesh_entity_from_triposr_photo.ps1"; RequiredKind = "input"; ParamAliases = @("ReferenceImagePath", "InputPath") }
    "text_mesh"           = [ordered]@{ Lane = "text_mesh"; Script = "create_mesh_entity_from_text_prompt.ps1"; RequiredKind = "prompt"; ParamAliases = @("Prompt") }
    "photo_rig_prep"      = [ordered]@{ Lane = "photo_rig_prep"; Script = "prepare_triposr_for_mixamo.ps1"; RequiredKind = "input"; ParamAliases = @("ReferenceImagePath", "InputPath") }
    "text_full_rig"       = [ordered]@{ Lane = "text_full_rig"; Script = "create_rigged_entity_from_text_prompt.ps1"; RequiredKind = "prompt"; ParamAliases = @("Prompt") }
    "external_rig_import" = [ordered]@{ Lane = "external_rig_import"; Script = "import_rigged_fbx_to_o3de.ps1"; RequiredKind = "input"; ParamAliases = @("RiggedFbxPath", "InputPath") }
    "release_character"   = [ordered]@{ Lane = "release_character"; Script = "" ; RequiredKind = "none"; ParamAliases = @() }
}

function New-AdapterJobId {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $rand = Get-Random -Minimum 1000 -Maximum 9999
    return "maxine-$stamp-$rand"
}

function Get-ScriptParameterNames {
    param([Parameter(Mandatory = $true)][string]$ScriptPath)
    if (!(Test-Path -LiteralPath $ScriptPath)) { return @() }

    $content = Get-Content -LiteralPath $ScriptPath
    $inParam = $false
    $block = New-Object System.Collections.Generic.List[string]

    foreach ($line in $content) {
        if (-not $inParam -and $line -match '^\s*param\s*\(') {
            $inParam = $true
        }
        if ($inParam) {
            $block.Add($line)
            if ($line -match '^\s*\)\s*$') { break }
        }
    }

    $joined = ($block -join "`n")
    $matches = [regex]::Matches($joined, '\$([A-Za-z_][A-Za-z0-9_]*)')
    $names = @()
    foreach ($m in $matches) {
        $n = $m.Groups[1].Value
        if ($names -notcontains $n) {
            $names += $n
        }
    }
    return $names
}

function Get-FirstSupportedName {
    param(
        [string[]]$Candidates,
        [string[]]$Supported
    )
    foreach ($name in $Candidates) {
        if ($Supported -contains $name) { return $name }
    }
    return ""
}

if (-not $jobTypeMap.Contains($JobType)) {
    Write-Error ("Unsupported JobType '{0}'. Supported: {1}" -f $JobType, (($jobTypeMap.Keys | Sort-Object) -join ", "))
    exit 1
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$newManifestScript = Join-Path $PSScriptRoot "New-MaxineManifest.ps1"
$writeEvidenceScript = Join-Path $PSScriptRoot "Write-MaxineEvidence.ps1"

$jobConfig = $jobTypeMap[$JobType]
$lane = [string]$jobConfig.Lane
$jobId = New-AdapterJobId

if (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
    $outputRootResolved = Join-Path $repoRoot $OutputRoot
}
else {
    $outputRootResolved = $OutputRoot
}

$evidencePath = Join-Path $outputRootResolved $jobId
$logsPath = Join-Path $evidencePath "logs"
$reportsPath = Join-Path $evidencePath "reports"
$manifestPath = Join-Path $evidencePath "manifest.json"
$stdoutLog = Join-Path $logsPath "stdout.log"
$stderrLog = Join-Path $logsPath "stderr.log"
$runPlanReport = Join-Path $reportsPath "run-plan.txt"

foreach ($dir in @(
        $evidencePath,
        $logsPath,
        $reportsPath,
        (Join-Path $evidencePath "screenshots"),
        (Join-Path $evidencePath "o3de"),
        (Join-Path $evidencePath "qc"),
        (Join-Path $evidencePath "temp"),
        (Join-Path $evidencePath "undo"),
        (Join-Path $evidencePath "cleanup")
    )) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

$finalStatus = "fail"
$finalMessage = "Unhandled adapter failure."
$finalErrorCode = "ADAPTER_UNHANDLED_FAILURE"
$finalErrorStage = "invoke_job"
$exitCode = 1
$legacyScriptPath = ""

try {
    $finalErrorStage = "manifest_create"
    & $newManifestScript `
        -JobId $jobId `
        -Lane $lane `
        -Status "created" `
        -CharacterName $CharacterName `
        -JobType $JobType `
        -InputPath $InputPath `
        -Prompt $Prompt `
        -ArtifactRoot $evidencePath `
        -OutputPath $manifestPath `
        -Operator "service" `
        -RetryOf $RetryOf `
        -Notes "Created by Invoke-MaxineJob.ps1" | Out-Null

    $finalErrorStage = "manifest_update_running"
    & $writeEvidenceScript `
        -JobId $jobId `
        -ManifestPath $manifestPath `
        -EvidenceRoot $evidencePath `
        -Status "running" `
        -Message "Adapter started." `
        -ExitCode 0 | Out-Null

    if ($JobType -eq "release_character") {
        $finalStatus = "pending_manual"
        $finalMessage = "Release publication is not implemented in this slice."
        $finalErrorCode = ""
        $finalErrorStage = ""
        $exitCode = 0
    }
    else {
        $finalErrorStage = "legacy_script_discovery"
        $legacyFile = [string]$jobConfig.Script
        $legacyScriptPath = Join-Path $ExistingFactoryToolsPath $legacyFile

        if (!(Test-Path -LiteralPath $legacyScriptPath)) {
            $finalStatus = "pending_manual"
            $finalMessage = ("Legacy script missing: {0}" -f $legacyScriptPath)
            $finalErrorCode = ""
            $finalErrorStage = ""
            $exitCode = 0
        }
        else {
            $finalErrorStage = "legacy_parameter_mapping"
            $supportedParams = Get-ScriptParameterNames -ScriptPath $legacyScriptPath
            $legacyParamMap = [ordered]@{}
            $uncertain = $false
            $uncertainReasons = @()

            if ($supportedParams -contains "CharacterName" -and -not [string]::IsNullOrWhiteSpace($CharacterName)) {
                $legacyParamMap["CharacterName"] = $CharacterName
            }
            if ($supportedParams -contains "LaunchEditor") {
                $legacyParamMap["LaunchEditor"] = 0
            }
            if ($supportedParams -contains "SaveLevel") {
                $legacyParamMap["SaveLevel"] = 0
            }

            switch ([string]$jobConfig.RequiredKind) {
                "prompt" {
                    if ([string]::IsNullOrWhiteSpace($Prompt)) {
                        $uncertain = $true
                        $uncertainReasons += "Prompt was not provided for prompt-based job type."
                    }
                    else {
                        $promptParam = Get-FirstSupportedName -Candidates $jobConfig.ParamAliases -Supported $supportedParams
                        if ([string]::IsNullOrWhiteSpace($promptParam)) {
                            $uncertain = $true
                            $uncertainReasons += ("Prompt parameter alias not found in legacy script: {0}" -f ($jobConfig.ParamAliases -join ", "))
                        }
                        else {
                            $legacyParamMap[$promptParam] = $Prompt
                        }
                    }
                }
                "input" {
                    if ([string]::IsNullOrWhiteSpace($InputPath)) {
                        $uncertain = $true
                        $uncertainReasons += "InputPath was not provided for input-based job type."
                    }
                    else {
                        $inputParam = Get-FirstSupportedName -Candidates $jobConfig.ParamAliases -Supported $supportedParams
                        if ([string]::IsNullOrWhiteSpace($inputParam)) {
                            $uncertain = $true
                            $uncertainReasons += ("Input parameter alias not found in legacy script: {0}" -f ($jobConfig.ParamAliases -join ", "))
                        }
                        else {
                            $legacyParamMap[$inputParam] = $InputPath
                        }
                    }
                }
            }

            if ($JobType -eq "text_full_rig") {
                if ($supportedParams -contains "PromptForRiggedFbxIfMissing") {
                    $legacyParamMap["PromptForRiggedFbxIfMissing"] = 0
                }
                if ($supportedParams -contains "OpenMixamo") {
                    $legacyParamMap["OpenMixamo"] = 0
                }
            }

            $planLines = @()
            $planLines += ("job_id={0}" -f $jobId)
            $planLines += ("job_type={0}" -f $JobType)
            $planLines += ("lane={0}" -f $lane)
            $planLines += ("legacy_script={0}" -f $legacyScriptPath)
            $planLines += ("dry_run={0}" -f [bool]$DryRun.IsPresent)
            $planLines += "parameters:"
            foreach ($k in $legacyParamMap.Keys) {
                $planLines += ("  -{0} {1}" -f $k, $legacyParamMap[$k])
            }
            if ($uncertainReasons.Count -gt 0) {
                $planLines += "uncertain_reasons:"
                foreach ($r in $uncertainReasons) {
                    $planLines += ("  - {0}" -f $r)
                }
            }
            Set-Content -LiteralPath $runPlanReport -Value $planLines -Encoding UTF8

            if ($DryRun.IsPresent) {
                if ($uncertain) {
                    $finalStatus = "pending_manual"
                    $finalMessage = ("Dry run generated plan but parameter mapping is uncertain: {0}" -f ($uncertainReasons -join "; "))
                }
                else {
                    $finalStatus = "pass"
                    $finalMessage = "Dry run generated command plan successfully."
                }
                $finalErrorCode = ""
                $finalErrorStage = ""
                $exitCode = 0
            }
            elseif ($uncertain) {
                $finalStatus = "pending_manual"
                $finalMessage = ("Legacy execution skipped due to uncertain mapping: {0}" -f ($uncertainReasons -join "; "))
                $finalErrorCode = ""
                $finalErrorStage = ""
                $exitCode = 0
            }
            else {
                $finalErrorStage = "legacy_execution"
                $procArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $legacyScriptPath)
                foreach ($paramName in $legacyParamMap.Keys) {
                    $procArgs += ("-{0}" -f $paramName)
                    $procArgs += [string]$legacyParamMap[$paramName]
                }

                $proc = Start-Process -FilePath "powershell.exe" `
                    -ArgumentList $procArgs `
                    -WorkingDirectory $repoRoot `
                    -RedirectStandardOutput $stdoutLog `
                    -RedirectStandardError $stderrLog `
                    -WindowStyle Hidden `
                    -Wait `
                    -PassThru

                $exitCode = [int]$proc.ExitCode
                if ($exitCode -eq 0) {
                    $finalStatus = "pass"
                    $finalMessage = "Legacy script completed successfully."
                    $finalErrorCode = ""
                    $finalErrorStage = ""
                }
                else {
                    $finalStatus = "fail"
                    $finalMessage = ("Legacy script exited with code {0}." -f $exitCode)
                    $finalErrorCode = "LEGACY_SCRIPT_NONZERO_EXIT"
                }
            }
        }
    }
}
catch {
    $finalStatus = "fail"
    $finalMessage = $_.Exception.Message
    $finalErrorCode = "ADAPTER_EXCEPTION"
    if ([string]::IsNullOrWhiteSpace($finalErrorStage)) {
        $finalErrorStage = "adapter_exception"
    }
    if ([string]::IsNullOrWhiteSpace($finalMessage)) {
        $finalMessage = "Unhandled exception in Invoke-MaxineJob.ps1"
    }
    if ($exitCode -eq 0) { $exitCode = 1 }
}
finally {
    $stdLogForManifest = if (Test-Path -LiteralPath $stdoutLog) { $stdoutLog } else { "" }
    $errLogForManifest = if (Test-Path -LiteralPath $stderrLog) { $stderrLog } else { "" }
    $reportForManifest = if (Test-Path -LiteralPath $runPlanReport) { $runPlanReport } else { "" }

    if (Test-Path -LiteralPath $manifestPath) {
        & $writeEvidenceScript `
            -JobId $jobId `
            -ManifestPath $manifestPath `
            -EvidenceRoot $evidencePath `
            -StdoutPath $stdLogForManifest `
            -StderrPath $errLogForManifest `
            -LogPath $reportForManifest `
            -Status $finalStatus `
            -Message $finalMessage `
            -ExitCode $exitCode `
            -ErrorCode $finalErrorCode `
            -ErrorStage $finalErrorStage `
            -ManualReviewReason $finalMessage | Out-Null
    }

    $summary = [ordered]@{
        job_id             = $jobId
        manifest_path      = $manifestPath
        evidence_path      = $evidencePath
        status             = $finalStatus
        legacy_script_path = $legacyScriptPath
        exit_code          = $exitCode
    }

    Write-Host ("job_id: {0}" -f $summary.job_id)
    Write-Host ("manifest_path: {0}" -f $summary.manifest_path)
    Write-Host ("evidence_path: {0}" -f $summary.evidence_path)
    Write-Host ("status: {0}" -f $summary.status)
    Write-Host ("legacy_script_path: {0}" -f $summary.legacy_script_path)
    Write-Host ("exit_code: {0}" -f $summary.exit_code)

    if ($PassThru.IsPresent) {
        [pscustomobject]$summary
    }
}

if ($finalStatus -eq "fail") {
    if ($exitCode -eq 0) { $exitCode = 1 }
    exit $exitCode
}

exit 0
