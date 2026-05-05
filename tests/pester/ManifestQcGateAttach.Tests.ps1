Describe "Manifest QC Gate Attach" {
    BeforeAll {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
        $attachScript = Join-Path $repoRoot "tools/manifest-validator/attach_qc_gate.py"
        $exampleManifest = Join-Path $repoRoot "examples/manifests/example-draft-mesh.manifest.json"

        function Write-JsonUtf8NoBom {
            param(
                [Parameter(Mandatory = $true)][string]$Path,
                [Parameter(Mandatory = $true)][object]$Object,
                [int]$Depth = 50
            )
            $dir = Split-Path -Parent $Path
            if (-not [string]::IsNullOrWhiteSpace($dir) -and -not (Test-Path -LiteralPath $dir)) {
                New-Item -Path $dir -ItemType Directory -Force | Out-Null
            }
            [System.IO.File]::WriteAllText(
                $Path,
                ($Object | ConvertTo-Json -Depth $Depth),
                [System.Text.UTF8Encoding]::new($false)
            )
        }
    }

    It "attaches qc_check payload into qc.gates and updates qc.overall" {
        $suffix = [Guid]::NewGuid().ToString("N")
        $manifestRel = "examples/manifests/pester-manifest-qc-attach-$suffix.json"
        $payloadRel = "examples/manifests/pester-payload-qc-attach-$suffix.json"
        $manifestAbs = Join-Path $repoRoot $manifestRel
        $payloadAbs = Join-Path $repoRoot $payloadRel

        try {
            $manifestObj = Get-Content -LiteralPath $exampleManifest -Raw | ConvertFrom-Json
            $manifestObj.qc.overall = "pass"
            $manifestObj.qc.gates = @()
            Write-JsonUtf8NoBom -Path $manifestAbs -Object $manifestObj

            $payloadObj = [ordered]@{
                status = "warn"
                check_id = "dcc_conform_v1"
                contract_id = "DCC_CONFORM_v1"
                findings = @()
                manifest_attachment = [ordered]@{
                    target_path = "qc.gates[]"
                    future_target_path = "qc.checks[]"
                    qc_check = [ordered]@{
                        check_id = "dcc_conform_v1"
                        result = "warn"
                        severity = "warning"
                        details = [ordered]@{ source = "pester" }
                    }
                }
            }
            Write-JsonUtf8NoBom -Path $payloadAbs -Object $payloadObj

            & python $attachScript $manifestAbs $payloadAbs --write-back | Out-Null
            $LASTEXITCODE | Should Be 0

            $updated = Get-Content -LiteralPath $manifestAbs -Raw | ConvertFrom-Json
            $updated.qc.overall | Should Be "warn"
            @($updated.qc.gates).Count | Should Be 1
            $updated.qc.gates[0].check_id | Should Be "dcc_conform_v1"
            $updated.qc.gates[0].result | Should Be "warn"
        }
        finally {
            if (Test-Path -LiteralPath $manifestAbs) { Remove-Item -LiteralPath $manifestAbs -Force }
            if (Test-Path -LiteralPath $payloadAbs) { Remove-Item -LiteralPath $payloadAbs -Force }
        }
    }

    It "rejects unsupported target_path to prevent writing outside qc.gates[]" {
        $suffix = [Guid]::NewGuid().ToString("N")
        $manifestRel = "examples/manifests/pester-manifest-qc-target-$suffix.json"
        $payloadRel = "examples/manifests/pester-payload-qc-target-$suffix.json"
        $manifestAbs = Join-Path $repoRoot $manifestRel
        $payloadAbs = Join-Path $repoRoot $payloadRel

        try {
            Copy-Item -LiteralPath $exampleManifest -Destination $manifestAbs -Force
            $payloadObj = [ordered]@{
                status = "pass"
                check_id = "material_uv_qc_v1"
                contract_id = "MATERIAL_UV_QC_v1"
                findings = @()
                manifest_attachment = [ordered]@{
                    target_path = "qc.checks[]"
                    future_target_path = "qc.checks[]"
                    qc_check = [ordered]@{
                        check_id = "material_uv_qc_v1"
                        result = "pass"
                        severity = "info"
                        details = [ordered]@{ source = "pester" }
                    }
                }
            }
            Write-JsonUtf8NoBom -Path $payloadAbs -Object $payloadObj

            & python $attachScript $manifestAbs $payloadAbs --write-back | Out-Null
            $LASTEXITCODE | Should Not Be 0
        }
        finally {
            if (Test-Path -LiteralPath $manifestAbs) { Remove-Item -LiteralPath $manifestAbs -Force }
            if (Test-Path -LiteralPath $payloadAbs) { Remove-Item -LiteralPath $payloadAbs -Force }
        }
    }

    It "preserves unknown manifest fields for forward compatibility" {
        $suffix = [Guid]::NewGuid().ToString("N")
        $manifestRel = "examples/manifests/pester-manifest-qc-preserve-$suffix.json"
        $payloadRel = "examples/manifests/pester-payload-qc-preserve-$suffix.json"
        $manifestAbs = Join-Path $repoRoot $manifestRel
        $payloadAbs = Join-Path $repoRoot $payloadRel

        try {
            $manifestObj = Get-Content -LiteralPath $exampleManifest -Raw | ConvertFrom-Json
            $manifestObj | Add-Member -NotePropertyName "custom_future_field" -NotePropertyValue ([ordered]@{
                unchanged = $true
                version = 2
            })
            Write-JsonUtf8NoBom -Path $manifestAbs -Object $manifestObj

            $payloadObj = [ordered]@{
                status = "pass"
                check_id = "animation_smoke_v1"
                contract_id = "ANIMATION_SMOKE_v1"
                findings = @()
                manifest_attachment = [ordered]@{
                    target_path = "qc.gates[]"
                    future_target_path = "qc.checks[]"
                    qc_check = [ordered]@{
                        check_id = "animation_smoke_v1"
                        result = "pass"
                        severity = "info"
                        details = [ordered]@{ source = "pester" }
                    }
                }
            }
            Write-JsonUtf8NoBom -Path $payloadAbs -Object $payloadObj

            & python $attachScript $manifestAbs $payloadAbs --write-back | Out-Null
            $LASTEXITCODE | Should Be 0

            $updated = Get-Content -LiteralPath $manifestAbs -Raw | ConvertFrom-Json
            $updated.custom_future_field.unchanged | Should Be $true
            $updated.custom_future_field.version | Should Be 2
        }
        finally {
            if (Test-Path -LiteralPath $manifestAbs) { Remove-Item -LiteralPath $manifestAbs -Force }
            if (Test-Path -LiteralPath $payloadAbs) { Remove-Item -LiteralPath $payloadAbs -Force }
        }
    }
}
