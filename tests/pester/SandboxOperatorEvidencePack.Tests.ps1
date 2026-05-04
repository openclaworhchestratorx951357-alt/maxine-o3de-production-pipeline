Describe "Sandbox Operator Evidence Pack" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $workflowRun = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineSandboxWorkflowRun.ps1"
        $workflowInspect = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineSandboxWorkflowInspect.ps1"
        $bundleExport = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineSandboxEvidenceBundleExport.ps1"
        $operatorSummary = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineSandboxOperatorSummary.ps1"
        $authoritative = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineAuthoritativeResolverWrite.ps1"
    }

    It "exports sandbox-local evidence bundle from workflow run without mutating source run" {
        $suffix = [Guid]::NewGuid().ToString('N')
        $targetRel = "examples/sandbox/staging/pester-evidence-pack-$suffix.json"
        $targetAbs = Join-Path $repoRoot $targetRel
        $receiptRel = "examples/sandbox/logs/pester-evidence-pack-receipt-$suffix.json"
        $receiptAbs = Join-Path $repoRoot $receiptRel
        $indexRel = "examples/sandbox/receipts/pester-evidence-pack-index-$suffix.json"
        $indexAbs = Join-Path $repoRoot $indexRel
        $packetRel = "examples/sandbox/review-packets/pester-evidence-pack-packet-$suffix.json"
        $packetAbs = Join-Path $repoRoot $packetRel
        $decisionRel = "examples/sandbox/review-decisions/pester-evidence-pack-decision-$suffix.json"
        $decisionAbs = Join-Path $repoRoot $decisionRel
        $runRel = "examples/sandbox/workflow-runs/pester-evidence-pack-run-$suffix.json"
        $runAbs = Join-Path $repoRoot $runRel
        $bundleRel = "examples/sandbox/evidence-bundles/pester-evidence-pack-$suffix/bundle.manifest.json"
        $bundleAbs = Join-Path $repoRoot $bundleRel
        $bundleDir = Split-Path -Parent $bundleAbs

        $plan = @{
            schema_version = "1.0.0"
            plan_id = "pester-plan-$suffix"
            command_name = "Invoke-MaxineSandboxResolverWrite.ps1"
            sandbox_scope = "sandbox_only"
            sandbox_root = "examples/sandbox"
            receipt_index_path = $indexRel
            target_path = $targetRel
            approved_target_under_sandbox = $true
            explicit_sandbox_approval = $true
            plan_signature = @{
                signed_by = "pester-operator"
                signature = "pester-signed"
            }
        } | ConvertTo-Json -Depth 20

        $planPath = Join-Path $TestDrive "evidence-plan.json"
        [System.IO.File]::WriteAllText($planPath, $plan, [System.Text.UTF8Encoding]::new($false))

        foreach ($p in @($targetAbs, $receiptAbs, $indexAbs, $packetAbs, $decisionAbs, $runAbs)) {
            if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force }
        }
        if (Test-Path -LiteralPath $bundleDir) { Remove-Item -LiteralPath $bundleDir -Recurse -Force }

        & powershell -NoProfile -ExecutionPolicy Bypass -File $workflowRun -PlanPath $planPath -WorkflowMode WriteReviewAndDecision -ReceiptPath $receiptRel -ReviewPacketPath $packetRel -DecisionPath $decisionRel -WorkflowRunPath $runRel -DecisionState accepted_for_sandbox_only -OperatorId pester-operator -DecisionReason "evidence check"
        $LASTEXITCODE | Should Be 0

        $runHashBefore = (Get-FileHash -LiteralPath $runAbs -Algorithm SHA256).Hash

        & powershell -NoProfile -ExecutionPolicy Bypass -File $bundleExport -WorkflowRunPath $runRel -BundlePath $bundleRel | Out-Null
        $LASTEXITCODE | Should Be 0

        (Test-Path -LiteralPath $bundleAbs) | Should Be $true
        $bundle = Get-Content -LiteralPath $bundleAbs -Raw | ConvertFrom-Json
        $bundle.bundle_path.StartsWith("examples/sandbox/evidence-bundles/") | Should Be $true
        $bundle.source_workflow_run_id | Should Not BeNullOrEmpty
        $bundle.copied_artifact_paths.Count | Should BeGreaterThan 0

        foreach ($rel in $bundle.copied_artifact_paths) {
            $rel.StartsWith("examples/sandbox/evidence-bundles/") | Should Be $true
            $rel.EndsWith(".json") | Should Be $true
            (Test-Path -LiteralPath (Join-Path $repoRoot $rel)) | Should Be $true
        }

        $runHashAfter = (Get-FileHash -LiteralPath $runAbs -Algorithm SHA256).Hash
        $runHashAfter | Should Be $runHashBefore

        foreach ($p in @($targetAbs, $receiptAbs, $indexAbs, $packetAbs, $decisionAbs, $runAbs)) {
            if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force }
        }
        if (Test-Path -LiteralPath $bundleDir) { Remove-Item -LiteralPath $bundleDir -Recurse -Force }
    }

    It "operator summary is read-only by default and writes only sandbox-local report when requested" {
        $summaryNoWrite = & powershell -NoProfile -ExecutionPolicy Bypass -File $operatorSummary
        $LASTEXITCODE | Should Be 0
        $summaryJson = $summaryNoWrite | ConvertFrom-Json
        $summaryJson.total_workflow_runs | Should BeGreaterThan -1
        $summaryJson.workflow_status_counts | Should Not BeNullOrEmpty

        $reportRel = "examples/sandbox/operator-reports/pester-operator-summary-$([Guid]::NewGuid().ToString('N')).json"
        $reportAbs = Join-Path $repoRoot $reportRel
        if (Test-Path -LiteralPath $reportAbs) { Remove-Item -LiteralPath $reportAbs -Force }

        $summaryWrite = & powershell -NoProfile -ExecutionPolicy Bypass -File $operatorSummary -WriteReport -ReportPath $reportRel
        $LASTEXITCODE | Should Be 0
        (Test-Path -LiteralPath $reportAbs) | Should Be $true
        $summaryWriteJson = $summaryWrite | ConvertFrom-Json
        $summaryWriteJson.report_path | Should Be $reportRel

        & powershell -NoProfile -ExecutionPolicy Bypass -File $operatorSummary -WriteReport -ReportPath "../outside/operator-summary.json" | Out-Null
        $LASTEXITCODE | Should Not Be 0

        if (Test-Path -LiteralPath $reportAbs) { Remove-Item -LiteralPath $reportAbs -Force }
    }

    It "capability matrix preserves blocked and forbidden boundaries" {
        $matrixPath = Join-Path $repoRoot "examples/capabilities/maxine-capability-matrix.json"
        (Test-Path -LiteralPath $matrixPath) | Should Be $true

        $matrix = Get-Content -LiteralPath $matrixPath -Raw | ConvertFrom-Json
        $caps = $matrix.capabilities

        $caps.sandbox_evidence_bundle_export | Should Be "sandbox_only"
        $caps.sandbox_operator_summary | Should Be "read_only"

        $caps.authoritative_resolver_write | Should Be "forbidden"
        $caps.o3de_editor_execution | Should Be "blocked"
        $caps.asset_processor_execution | Should Be "blocked"
        $caps.product_resolution | Should Be "blocked"
        $caps.asset_id_claims | Should Be "blocked"
        $caps.spawning | Should Be "blocked"
        $caps.publishing | Should Be "blocked"
        $caps.production_path_write | Should Be "forbidden"
        $caps.cache_path_write | Should Be "forbidden"
        $caps.engine_path_write | Should Be "forbidden"
    }

    It "keeps authoritative writer absent and blocks O3DE/AP/Editor execution hooks" {
        (Test-Path -LiteralPath $authoritative) | Should Be $false

        $workflowRunText = (Get-Content -LiteralPath $workflowRun -Raw).ToLowerInvariant()
        $workflowInspectText = (Get-Content -LiteralPath $workflowInspect -Raw).ToLowerInvariant()
        $bundleExportText = (Get-Content -LiteralPath $bundleExport -Raw).ToLowerInvariant()
        $operatorSummaryText = (Get-Content -LiteralPath $operatorSummary -Raw).ToLowerInvariant()
        $combined = $workflowRunText + "`n" + $workflowInspectText + "`n" + $bundleExportText + "`n" + $operatorSummaryText

        $combined.Contains("o3de editor") | Should Be $false
        $combined.Contains("asset processor") | Should Be $false
        $combined.Contains("o3de.exe") | Should Be $false
        $combined.Contains("editor.exe") | Should Be $false
        $combined.Contains("invoke-maxineauthoritativeresolverwrite.ps1") | Should Be $false
    }
}
