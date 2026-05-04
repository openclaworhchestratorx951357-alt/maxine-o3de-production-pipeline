Describe "Sandbox Writer Skeleton" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $writer = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineSandboxResolverWrite.ps1"
        $rollback = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineSandboxRollback.ps1"
        $authoritative = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineAuthoritativeResolverWrite.ps1"
    }

    It "writes and rolls back only within sandbox staging" {
        $targetName = "pester-write-$([Guid]::NewGuid().ToString('N')).json"
        $targetRel = "examples/sandbox/staging/$targetName"
        $targetAbs = Join-Path $repoRoot $targetRel
        $receiptName = "pester-receipt-$([Guid]::NewGuid().ToString('N')).json"
        $receiptRel = "examples/sandbox/logs/$receiptName"
        $receiptAbs = Join-Path $repoRoot $receiptRel
        $rollbackReportAbs = Join-Path $repoRoot ("examples/sandbox/manifests/reports/{0}.rollback.json" -f [System.IO.Path]::GetFileNameWithoutExtension($receiptName))

        $plan = @{
            schema_version = "1.0.0"
            plan_id = "pester-plan-$([Guid]::NewGuid().ToString('N'))"
            command_name = "Invoke-MaxineSandboxResolverWrite.ps1"
            sandbox_scope = "sandbox_only"
            sandbox_root = "examples/sandbox"
            target_path = $targetRel
            approved_target_under_sandbox = $true
            explicit_sandbox_approval = $true
            plan_signature = @{
                signed_by = "pester-operator"
                signature = "pester-signed"
            }
            write_payload = @{
                source = "pester"
            }
        } | ConvertTo-Json -Depth 20

        $planPath = Join-Path $TestDrive "plan.json"
        [System.IO.File]::WriteAllText($planPath, $plan, [System.Text.UTF8Encoding]::new($false))

        if (Test-Path -LiteralPath $targetAbs) {
            Remove-Item -LiteralPath $targetAbs -Force
        }
        if (Test-Path -LiteralPath $receiptAbs) {
            Remove-Item -LiteralPath $receiptAbs -Force
        }

        & powershell -NoProfile -ExecutionPolicy Bypass -File $writer -PlanPath $planPath -ReceiptPath $receiptRel
        $LASTEXITCODE | Should Be 0
        (Test-Path -LiteralPath $targetAbs) | Should Be $true
        (Test-Path -LiteralPath $receiptAbs) | Should Be $true

        & powershell -NoProfile -ExecutionPolicy Bypass -File $rollback -ReceiptPath $receiptRel -ConfirmRollback
        $LASTEXITCODE | Should Be 0
        (Test-Path -LiteralPath $targetAbs) | Should Be $false

        if (Test-Path -LiteralPath $receiptAbs) {
            Remove-Item -LiteralPath $receiptAbs -Force
        }
        if (Test-Path -LiteralPath $rollbackReportAbs) {
            Remove-Item -LiteralPath $rollbackReportAbs -Force
        }
    }

    It "blocks production path writes" {
        $receiptName = "pester-blocked-$([Guid]::NewGuid().ToString('N')).json"
        $receiptRel = "examples/sandbox/logs/$receiptName"
        $receiptAbs = Join-Path $repoRoot $receiptRel

        $plan = @{
            schema_version = "1.0.0"
            plan_id = "pester-plan-$([Guid]::NewGuid().ToString('N'))"
            command_name = "Invoke-MaxineSandboxResolverWrite.ps1"
            sandbox_scope = "sandbox_only"
            sandbox_root = "examples/sandbox"
            target_path = "Projects/MaxineShow/forbidden.json"
            approved_target_under_sandbox = $true
            explicit_sandbox_approval = $true
            plan_signature = @{
                signed_by = "pester-operator"
                signature = "pester-signed"
            }
        } | ConvertTo-Json -Depth 20

        $planPath = Join-Path $TestDrive "blocked-plan.json"
        [System.IO.File]::WriteAllText($planPath, $plan, [System.Text.UTF8Encoding]::new($false))

        & powershell -NoProfile -ExecutionPolicy Bypass -File $writer -PlanPath $planPath -ReceiptPath $receiptRel
        $LASTEXITCODE | Should Not Be 0

        if (Test-Path -LiteralPath $receiptAbs) {
            Remove-Item -LiteralPath $receiptAbs -Force
        }
    }

    It "keeps authoritative resolver write absent" {
        Test-Path -LiteralPath $authoritative | Should Be $false
    }

    It "does not contain O3DE or Asset Processor execution hooks" {
        $writerText = (Get-Content -LiteralPath $writer -Raw).ToLowerInvariant()
        $rollbackText = (Get-Content -LiteralPath $rollback -Raw).ToLowerInvariant()
        $combined = $writerText + "`n" + $rollbackText

        $combined.Contains("o3de editor") | Should Be $false
        $combined.Contains("asset processor") | Should Be $false
        $combined.Contains("o3de.exe") | Should Be $false
        $combined.Contains("editor.exe") | Should Be $false
        $combined.Contains("invoke-maxineauthoritativeresolverwrite.ps1") | Should Be $false
    }
}
