[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PlanPath,

    [ValidateSet("WriteOnly", "WriteAndReview", "WriteReviewAndDecision", "RollbackRequestedOnly")]
    [string]$WorkflowMode = "WriteOnly",

    [string]$ReceiptPath,
    [string]$ReceiptIndexPath,
    [string]$ReviewPacketPath,
    [string]$DecisionPath,
    [string]$WorkflowRunPath,

    [string]$DecisionState = "accepted_for_sandbox_only",
    [string]$OperatorId,
    [string]$DecisionReason,
    [string]$RequestedNextAction
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$sandboxAnchorAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox"))

$writerScript = Join-Path $scriptDir "Invoke-MaxineSandboxResolverWrite.ps1"
$reviewPacketBuildScript = Join-Path $scriptDir "Invoke-MaxineSandboxReviewPacketBuild.ps1"
$reviewDecisionRecordScript = Join-Path $scriptDir "Invoke-MaxineSandboxReviewDecisionRecord.ps1"

$workflowRunsRootRel = "examples/sandbox/workflow-runs"
$workflowRunsRootAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox\workflow-runs"))
$reviewPacketsRootAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox\review-packets"))
$reviewDecisionsRootAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox\review-decisions"))
$logsRootAbs = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "examples\sandbox\logs"))

$allowedDecisionStates = @(
    "accepted_for_sandbox_only",
    "request_rollback",
    "rejected",
    "needs_more_evidence"
)

$explicitNonAdmissions = @(
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

    $json = $InputObject | ConvertTo-Json -Depth 50
    [System.IO.File]::WriteAllText($OutputPath, $json, [System.Text.UTF8Encoding]::new($false))
}

function Resolve-WorkflowPath {
    param(
        [string]$RequestedPath,
        [Parameter(Mandatory = $true)]
        [string]$DefaultRelativePath,
        [Parameter(Mandatory = $true)]
        [string]$AllowedRootAbs,
        [string]$Label = "path"
    )

    if ([string]::IsNullOrWhiteSpace($RequestedPath)) {
        return Get-SafeRelativePathAbs -RelativePath $DefaultRelativePath -AllowedRootAbs $AllowedRootAbs -Label $Label
    }

    return Get-SafeRelativePathAbs -RelativePath $RequestedPath -AllowedRootAbs $AllowedRootAbs -Label $Label
}

$startedUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$workflowRunId = "sandbox-workflow-run-$([Guid]::NewGuid().ToString('N'))"

$workflow = [ordered]@{
    schema_version = "1.0.0"
    workflow_run_id = $workflowRunId
    workflow_mode = $WorkflowMode
    input_plan_path = $PlanPath
    sandbox_root = "examples/sandbox"
    receipt_id = $null
    receipt_path = $null
    review_packet_id = $null
    review_packet_path = $null
    decision_id = $null
    decision_path = $null
    decision_state = $null
    requested_next_action = $null
    rollback_execution_admitted = $false
    workflow_status = "blocked"
    blocked_reason = $null
    files_written = @()
    explicit_non_admissions = @($explicitNonAdmissions)
    timestamp_utc = $startedUtc
    completed_utc = $startedUtc
}

$workflowRunAbs = $null
$receiptAbs = $null
$reviewPacketAbs = $null
$decisionAbs = $null

function Finalize-Workflow {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ExitCode
    )

    $workflow.completed_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

    if (-not $workflowRunAbs) {
        $fallbackRel = "$workflowRunsRootRel/$workflowRunId.blocked.json"
        $script:workflowRunAbs = Get-SafeRelativePathAbs -RelativePath $fallbackRel -AllowedRootAbs $workflowRunsRootAbs -Label "workflow_run_path"
    }

    Write-JsonFile -InputObject $workflow -OutputPath $workflowRunAbs
    Write-Host "Workflow run record: $workflowRunAbs"

    if ($ExitCode -eq 0) {
        Write-Host "PASS: sandbox workflow run completed."
    } else {
        Write-Host "FAIL: sandbox workflow run blocked."
    }

    exit $ExitCode
}

try {
    foreach ($requiredScript in @($writerScript, $reviewPacketBuildScript, $reviewDecisionRecordScript)) {
        if (-not (Test-Path -LiteralPath $requiredScript -PathType Leaf)) {
            throw "required command missing: $requiredScript"
        }
    }

    $planAbs = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $PlanPath).Path)
    if (-not (Test-Path -LiteralPath $planAbs -PathType Leaf)) {
        throw "plan file not found: $PlanPath"
    }

    $requiresDecision = ($WorkflowMode -eq "WriteReviewAndDecision" -or $WorkflowMode -eq "RollbackRequestedOnly")
    if ($requiresDecision) {
        if ([string]::IsNullOrWhiteSpace($OperatorId)) {
            throw "operator_id is required for workflow mode $WorkflowMode."
        }
        if ([string]::IsNullOrWhiteSpace($DecisionReason)) {
            throw "decision_reason is required for workflow mode $WorkflowMode."
        }
    }

    if ($allowedDecisionStates -notcontains $DecisionState) {
        throw "decision_state '$DecisionState' is invalid for workflow runner."
    }

    $defaultReceiptRel = "examples/sandbox/logs/$workflowRunId.receipt.json"
    $defaultReviewPacketRel = "examples/sandbox/review-packets/$workflowRunId.review-packet.json"
    $defaultDecisionRel = "examples/sandbox/review-decisions/$workflowRunId.decision.json"
    $defaultWorkflowRel = "$workflowRunsRootRel/$workflowRunId.json"

    $receiptAbs = Resolve-WorkflowPath -RequestedPath $ReceiptPath -DefaultRelativePath $defaultReceiptRel -AllowedRootAbs $logsRootAbs -Label "receipt_path"
    $reviewPacketAbs = Resolve-WorkflowPath -RequestedPath $ReviewPacketPath -DefaultRelativePath $defaultReviewPacketRel -AllowedRootAbs $reviewPacketsRootAbs -Label "review_packet_path"
    $decisionAbs = Resolve-WorkflowPath -RequestedPath $DecisionPath -DefaultRelativePath $defaultDecisionRel -AllowedRootAbs $reviewDecisionsRootAbs -Label "decision_path"
    $workflowRunAbs = Resolve-WorkflowPath -RequestedPath $WorkflowRunPath -DefaultRelativePath $defaultWorkflowRel -AllowedRootAbs $workflowRunsRootAbs -Label "workflow_run_path"

    $receiptRel = Get-RepoRelativePath -AbsolutePath $receiptAbs
    $reviewPacketRel = Get-RepoRelativePath -AbsolutePath $reviewPacketAbs
    $decisionRel = Get-RepoRelativePath -AbsolutePath $decisionAbs

    $writerArgs = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $writerScript,
        "-PlanPath", $planAbs,
        "-ReceiptPath", $receiptRel
    )
    if (-not [string]::IsNullOrWhiteSpace($ReceiptIndexPath)) {
        $writerArgs += @("-ReceiptIndexPath", $ReceiptIndexPath)
    }

    & powershell @writerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "sandbox write step failed."
    }

    if (-not (Test-Path -LiteralPath $receiptAbs -PathType Leaf)) {
        throw "sandbox write did not produce receipt."
    }

    $receipt = Get-Content -LiteralPath $receiptAbs -Raw | ConvertFrom-Json
    $workflow.receipt_id = [string]$receipt.receipt_id
    $workflow.receipt_path = $receiptRel
    $workflow.files_written = @($receipt.files_written)

    if ($WorkflowMode -eq "WriteOnly") {
        $workflow.workflow_status = "completed"
        Finalize-Workflow -ExitCode 0
    }

    $reviewDecisionState = "pending_review"
    if ($WorkflowMode -eq "RollbackRequestedOnly") {
        $reviewDecisionState = "request_rollback"
    }

    & powershell -NoProfile -ExecutionPolicy Bypass -File $reviewPacketBuildScript -ReceiptPath $receiptRel -OutputPath $reviewPacketRel -OperatorDecisionState $reviewDecisionState
    if ($LASTEXITCODE -ne 0) {
        throw "review packet build step failed."
    }

    if (-not (Test-Path -LiteralPath $reviewPacketAbs -PathType Leaf)) {
        throw "review packet build did not produce output packet."
    }

    $reviewPacket = Get-Content -LiteralPath $reviewPacketAbs -Raw | ConvertFrom-Json
    $workflow.review_packet_id = [string]$reviewPacket.review_packet_id
    $workflow.review_packet_path = $reviewPacketRel

    if ($WorkflowMode -eq "WriteAndReview") {
        $workflow.workflow_status = "completed"
        Finalize-Workflow -ExitCode 0
    }

    $finalDecisionState = $DecisionState
    $finalRequestedAction = $RequestedNextAction
    if ($WorkflowMode -eq "RollbackRequestedOnly") {
        $finalDecisionState = "request_rollback"
        $finalRequestedAction = "rollback_requested"
    }

    $decisionArgs = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $reviewDecisionRecordScript,
        "-ReviewPacketPath", $reviewPacketRel,
        "-DecisionState", $finalDecisionState,
        "-OperatorId", $OperatorId,
        "-DecisionReason", $DecisionReason,
        "-OutputPath", $decisionRel
    )

    if (-not [string]::IsNullOrWhiteSpace($finalRequestedAction)) {
        $decisionArgs += @("-RequestedNextAction", $finalRequestedAction)
    }

    & powershell @decisionArgs
    if ($LASTEXITCODE -ne 0) {
        throw "review decision record step failed."
    }

    if (-not (Test-Path -LiteralPath $decisionAbs -PathType Leaf)) {
        throw "review decision step did not produce output decision."
    }

    $decision = Get-Content -LiteralPath $decisionAbs -Raw | ConvertFrom-Json
    $workflow.decision_id = [string]$decision.decision_id
    $workflow.decision_path = $decisionRel
    $workflow.decision_state = [string]$decision.decision_state
    $workflow.requested_next_action = $decision.requested_next_action
    $workflow.rollback_execution_admitted = [bool]$decision.rollback_execution_admitted

    $workflow.workflow_status = "completed"
    Finalize-Workflow -ExitCode 0
} catch {
    $workflow.blocked_reason = $_.Exception.Message
    $workflow.workflow_status = "blocked"

    if ($receiptAbs -and (Test-Path -LiteralPath $receiptAbs -PathType Leaf)) {
        try {
            $receiptOnFailure = Get-Content -LiteralPath $receiptAbs -Raw | ConvertFrom-Json
            $workflow.receipt_id = [string]$receiptOnFailure.receipt_id
            $workflow.receipt_path = Get-RepoRelativePath -AbsolutePath $receiptAbs
            $workflow.files_written = @($receiptOnFailure.files_written)
        } catch {
            # Keep best-effort blocked record.
        }
    }

    if ($reviewPacketAbs -and (Test-Path -LiteralPath $reviewPacketAbs -PathType Leaf)) {
        try {
            $reviewOnFailure = Get-Content -LiteralPath $reviewPacketAbs -Raw | ConvertFrom-Json
            $workflow.review_packet_id = [string]$reviewOnFailure.review_packet_id
            $workflow.review_packet_path = Get-RepoRelativePath -AbsolutePath $reviewPacketAbs
        } catch {
            # Keep best-effort blocked record.
        }
    }

    if ($decisionAbs -and (Test-Path -LiteralPath $decisionAbs -PathType Leaf)) {
        try {
            $decisionOnFailure = Get-Content -LiteralPath $decisionAbs -Raw | ConvertFrom-Json
            $workflow.decision_id = [string]$decisionOnFailure.decision_id
            $workflow.decision_path = Get-RepoRelativePath -AbsolutePath $decisionAbs
            $workflow.decision_state = [string]$decisionOnFailure.decision_state
            $workflow.requested_next_action = $decisionOnFailure.requested_next_action
            $workflow.rollback_execution_admitted = [bool]$decisionOnFailure.rollback_execution_admitted
        } catch {
            # Keep best-effort blocked record.
        }
    }

    Finalize-Workflow -ExitCode 1
}
