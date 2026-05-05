Describe "Release Publication Execution Window State" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $validator = Join-Path $repoRoot "tools/release-publication-execution-window-state/validate_release_publication_execution_window_state_report.py"
        $passReport = Join-Path $repoRoot "examples/release-publication-execution-window-state/max_biped_v1_release_publication_execution_window_state_pass.json"
        $warnReport = Join-Path $repoRoot "examples/release-publication-execution-window-state/max_biped_v1_release_publication_execution_window_state_warn.json"
        $failReport = Join-Path $repoRoot "examples/release-publication-execution-window-state/max_biped_v1_release_publication_execution_window_state_fail.json"
        $authoritative = Join-Path $repoRoot "scripts/powershell/Invoke-MaxineAuthoritativeResolverWrite.ps1"

        function Convert-ValidatorOutputToJson {
            param([Parameter(Mandatory = $true)][string]$OutputText)
            $start = $OutputText.IndexOf("{")
            if ($start -lt 0) {
                throw "validator output did not include JSON payload: $OutputText"
            }
            return $OutputText.Substring($start) | ConvertFrom-Json
        }
    }

    It "validates pass and warn fixtures with allow-warn" {
        $passOutput = & python $validator $passReport 2>&1 | Out-String
        $LASTEXITCODE | Should Be 0
        $passObj = Convert-ValidatorOutputToJson -OutputText $passOutput
        $passObj.status | Should Be "pass"
        $passObj.check_id | Should Be "release_publication_execution_window_state_v1"
        $passObj.manifest_attachment.target_path | Should Be "qc.gates[]"
        $passObj.manifest_attachment.future_target_path | Should Be "qc.checks[]"

        $warnOutput = & python $validator $warnReport --allow-warn 2>&1 | Out-String
        $LASTEXITCODE | Should Be 0
        $warnObj = Convert-ValidatorOutputToJson -OutputText $warnOutput
        $warnObj.status | Should Be "warn"
    }

    It "returns nonzero for fail fixture and preserves evidence-only boundaries" {
        $failOutput = & python $validator $failReport 2>&1 | Out-String
        $LASTEXITCODE | Should Not Be 0
        $failObj = Convert-ValidatorOutputToJson -OutputText $failOutput
        $failObj.status | Should Be "fail"
        (($failObj.findings | ForEach-Object { $_.id }) -contains "window_state_window_bounds_invalid") | Should Be $true

        $scriptText = (Get-Content -LiteralPath $validator -Raw).ToLowerInvariant()
        $scriptText.Contains("start-process") | Should Be $false
        $scriptText.Contains("invoke-expression") | Should Be $false
        $scriptText.Contains("o3de.exe") | Should Be $false
        $scriptText.Contains("editor.exe") | Should Be $false
    }

    It "keeps capability matrix and authoritative-writer boundary intact" {
        (Test-Path -LiteralPath $authoritative) | Should Be $false

        $matrixPath = Join-Path $repoRoot "examples/capabilities/maxine-capability-matrix.json"
        $matrix = Get-Content -LiteralPath $matrixPath -Raw | ConvertFrom-Json
        $caps = $matrix.capabilities

        $caps.release_publication_execution_window_ticket_report_validation | Should Be "proof_only"
        $caps.release_publication_execution_window_state_report_validation | Should Be "proof_only"
        $caps.asset_processor_execution | Should Be "blocked"
        $caps.real_asset_processor_execution | Should Be "blocked"
        $caps.o3de_editor_execution | Should Be "blocked"
        $caps.o3de_cli_execution | Should Be "blocked"
        $caps.spawning | Should Be "blocked"
        $caps.publishing | Should Be "blocked"
    }
}
