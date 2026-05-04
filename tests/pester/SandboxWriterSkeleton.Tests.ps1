Describe "Sandbox Writer Skeleton" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $writer = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineSandboxResolverWrite.ps1"
        $rollback = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineSandboxRollback.ps1"
        $inspect = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineSandboxReceiptInspect.ps1"
        $authoritative = Join-Path $repoRoot "scripts\powershell\Invoke-MaxineAuthoritativeResolverWrite.ps1"
    }

    It "writes, indexes, and rolls back only within sandbox staging while preserving receipt history" {
        $targetName = "pester-write-$([Guid]::NewGuid().ToString('N')).json"
        $targetRel = "examples/sandbox/staging/$targetName"
        $targetAbs = Join-Path $repoRoot $targetRel
        $receiptName = "pester-receipt-$([Guid]::NewGuid().ToString('N')).json"
        $receiptRel = "examples/sandbox/logs/$receiptName"
        $receiptAbs = Join-Path $repoRoot $receiptRel
        $indexName = "pester-index-$([Guid]::NewGuid().ToString('N')).json"
        $indexRel = "examples/sandbox/receipts/$indexName"
        $indexAbs = Join-Path $repoRoot $indexRel
        $rollbackReportAbs = Join-Path $repoRoot ("examples/sandbox/manifests/reports/{0}.rollback.json" -f [System.IO.Path]::GetFileNameWithoutExtension($receiptName))

        $plan = @{
            schema_version = "1.0.0"
            plan_id = "pester-plan-$([Guid]::NewGuid().ToString('N'))"
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
            write_payload = @{
                source = "pester"
            }
        } | ConvertTo-Json -Depth 20

        $planPath = Join-Path $TestDrive "plan.json"
        [System.IO.File]::WriteAllText($planPath, $plan, [System.Text.UTF8Encoding]::new($false))

        foreach ($p in @($targetAbs, $receiptAbs, $indexAbs, $rollbackReportAbs)) {
            if (Test-Path -LiteralPath $p) {
                Remove-Item -LiteralPath $p -Force
            }
        }

        & powershell -NoProfile -ExecutionPolicy Bypass -File $writer -PlanPath $planPath -ReceiptPath $receiptRel
        $LASTEXITCODE | Should Be 0
        (Test-Path -LiteralPath $targetAbs) | Should Be $true
        (Test-Path -LiteralPath $receiptAbs) | Should Be $true
        (Test-Path -LiteralPath $indexAbs) | Should Be $true

        $receipt = Get-Content -LiteralPath $receiptAbs -Raw | ConvertFrom-Json
        $receipt.status | Should Be "written"

        $index = Get-Content -LiteralPath $indexAbs -Raw | ConvertFrom-Json
        $entry = $index.receipts | Where-Object { $_.receipt_id -eq $receipt.receipt_id } | Select-Object -First 1
        $entry | Should Not BeNullOrEmpty
        $entry.status | Should Be "written"

        & powershell -NoProfile -ExecutionPolicy Bypass -File $rollback -ReceiptPath $receiptRel -ConfirmRollback
        $LASTEXITCODE | Should Be 0
        (Test-Path -LiteralPath $targetAbs) | Should Be $false
        (Test-Path -LiteralPath $receiptAbs) | Should Be $true

        $receiptAfter = Get-Content -LiteralPath $receiptAbs -Raw | ConvertFrom-Json
        $receiptAfter.status | Should Be "rolled_back"
        $receiptAfter.rollback_status | Should Be "rolled_back"

        $indexAfter = Get-Content -LiteralPath $indexAbs -Raw | ConvertFrom-Json
        $entryAfter = $indexAfter.receipts | Where-Object { $_.receipt_id -eq $receipt.receipt_id } | Select-Object -First 1
        $entryAfter | Should Not BeNullOrEmpty
        $entryAfter.status | Should Be "rolled_back"

        foreach ($p in @($receiptAbs, $indexAbs, $rollbackReportAbs)) {
            if (Test-Path -LiteralPath $p) {
                Remove-Item -LiteralPath $p -Force
            }
        }
    }

    It "inspect command is read-only and can inspect by receipt_id" {
        $targetName = "pester-inspect-write-$([Guid]::NewGuid().ToString('N')).json"
        $targetRel = "examples/sandbox/staging/$targetName"
        $targetAbs = Join-Path $repoRoot $targetRel
        $receiptName = "pester-inspect-receipt-$([Guid]::NewGuid().ToString('N')).json"
        $receiptRel = "examples/sandbox/logs/$receiptName"
        $receiptAbs = Join-Path $repoRoot $receiptRel
        $indexName = "pester-inspect-index-$([Guid]::NewGuid().ToString('N')).json"
        $indexRel = "examples/sandbox/receipts/$indexName"
        $indexAbs = Join-Path $repoRoot $indexRel

        $plan = @{
            schema_version = "1.0.0"
            plan_id = "pester-plan-$([Guid]::NewGuid().ToString('N'))"
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

        $planPath = Join-Path $TestDrive "inspect-plan.json"
        [System.IO.File]::WriteAllText($planPath, $plan, [System.Text.UTF8Encoding]::new($false))

        foreach ($p in @($targetAbs, $receiptAbs, $indexAbs)) {
            if (Test-Path -LiteralPath $p) {
                Remove-Item -LiteralPath $p -Force
            }
        }

        & powershell -NoProfile -ExecutionPolicy Bypass -File $writer -PlanPath $planPath -ReceiptPath $receiptRel
        $LASTEXITCODE | Should Be 0

        $receipt = Get-Content -LiteralPath $receiptAbs -Raw | ConvertFrom-Json
        $beforeHash = (Get-FileHash -LiteralPath $indexAbs -Algorithm SHA256).Hash

        $listOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $inspect -List -IndexPath $indexRel
        $LASTEXITCODE | Should Be 0
        $listJson = $listOutput | ConvertFrom-Json
        $listJson.receipt_count | Should BeGreaterThan 0

        $entryOutput = & powershell -NoProfile -ExecutionPolicy Bypass -File $inspect -ReceiptId $receipt.receipt_id -IndexPath $indexRel
        $LASTEXITCODE | Should Be 0
        $entryJson = $entryOutput | ConvertFrom-Json
        $entryJson.receipt_id | Should Be $receipt.receipt_id
        $entryJson.files_written.Count | Should Be 1

        $afterHash = (Get-FileHash -LiteralPath $indexAbs -Algorithm SHA256).Hash
        $afterHash | Should Be $beforeHash

        foreach ($p in @($targetAbs, $receiptAbs, $indexAbs)) {
            if (Test-Path -LiteralPath $p) {
                Remove-Item -LiteralPath $p -Force
            }
        }
    }

    It "blocks production path writes" {
        $receiptName = "pester-blocked-$([Guid]::NewGuid().ToString('N')).json"
        $receiptRel = "examples/sandbox/logs/$receiptName"
        $receiptAbs = Join-Path $repoRoot $receiptRel
        $indexName = "pester-blocked-index-$([Guid]::NewGuid().ToString('N')).json"
        $indexRel = "examples/sandbox/receipts/$indexName"
        $indexAbs = Join-Path $repoRoot $indexRel

        $plan = @{
            schema_version = "1.0.0"
            plan_id = "pester-plan-$([Guid]::NewGuid().ToString('N'))"
            command_name = "Invoke-MaxineSandboxResolverWrite.ps1"
            sandbox_scope = "sandbox_only"
            sandbox_root = "examples/sandbox"
            receipt_index_path = $indexRel
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

        foreach ($p in @($receiptAbs, $indexAbs)) {
            if (Test-Path -LiteralPath $p) {
                Remove-Item -LiteralPath $p -Force
            }
        }

        & powershell -NoProfile -ExecutionPolicy Bypass -File $writer -PlanPath $planPath -ReceiptPath $receiptRel
        $LASTEXITCODE | Should Not Be 0

        (Test-Path -LiteralPath $receiptAbs) | Should Be $true
        (Test-Path -LiteralPath $indexAbs) | Should Be $true

        $receipt = Get-Content -LiteralPath $receiptAbs -Raw | ConvertFrom-Json
        $receipt.status | Should Be "blocked"

        $index = Get-Content -LiteralPath $indexAbs -Raw | ConvertFrom-Json
        $entry = $index.receipts | Where-Object { $_.receipt_id -eq $receipt.receipt_id } | Select-Object -First 1
        $entry | Should Not BeNullOrEmpty
        $entry.status | Should Be "blocked"

        foreach ($p in @($receiptAbs, $indexAbs)) {
            if (Test-Path -LiteralPath $p) {
                Remove-Item -LiteralPath $p -Force
            }
        }
    }

    It "keeps authoritative resolver write absent" {
        Test-Path -LiteralPath $authoritative | Should Be $false
    }

    It "does not contain O3DE or Asset Processor execution hooks" {
        $writerText = (Get-Content -LiteralPath $writer -Raw).ToLowerInvariant()
        $rollbackText = (Get-Content -LiteralPath $rollback -Raw).ToLowerInvariant()
        $inspectText = (Get-Content -LiteralPath $inspect -Raw).ToLowerInvariant()
        $combined = $writerText + "`n" + $rollbackText + "`n" + $inspectText

        $combined.Contains("o3de editor") | Should Be $false
        $combined.Contains("asset processor") | Should Be $false
        $combined.Contains("o3de.exe") | Should Be $false
        $combined.Contains("editor.exe") | Should Be $false
        $combined.Contains("invoke-maxineauthoritativeresolverwrite.ps1") | Should Be $false
    }
}
