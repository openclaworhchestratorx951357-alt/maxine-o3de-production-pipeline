$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$newScript = Join-Path $repoRoot "scripts/powershell/New-MaxineManifest.ps1"
$writeScript = Join-Path $repoRoot "scripts/powershell/Write-MaxineEvidence.ps1"
$readScript = Join-Path $repoRoot "scripts/powershell/Read-MaxineManifest.ps1"
$validator = Join-Path $repoRoot "tools/manifest-validator/validate_manifest.py"

Describe "Manifest V1 Foundation" {
    It "validates golden success and failure manifests" {
        $samples = @(
            (Join-Path $repoRoot "examples/manifests/example-manifest-v1-success.json"),
            (Join-Path $repoRoot "examples/manifests/example-manifest-v1-failure.json")
        )
        foreach ($sample in $samples) {
            & python $validator $sample | Out-Null
            $LASTEXITCODE | Should Be 0
        }
    }

    It "creates deterministic artifact layout and manifest fields for created jobs" {
        $jobId = "pester-manifest-v1-created"
        $artifactRoot = Join-Path $repoRoot ("scripts/generated/" + $jobId)
        if (Test-Path -LiteralPath $artifactRoot) {
            Remove-Item -LiteralPath $artifactRoot -Recurse -Force
        }
        $manifestPath = Join-Path $artifactRoot "manifest.json"

        & $newScript `
            -JobId $jobId `
            -Lane "draft_mesh" `
            -CharacterName "Pester Created Character" `
            -Operator "ci" `
            -ArtifactRoot $artifactRoot `
            -OutputPath $manifestPath | Out-Null
        $LASTEXITCODE | Should Be 0

        Test-Path -LiteralPath $manifestPath | Should Be $true
        Test-Path -LiteralPath (Join-Path $artifactRoot "logs") | Should Be $true
        Test-Path -LiteralPath (Join-Path $artifactRoot "screenshots") | Should Be $true
        Test-Path -LiteralPath (Join-Path $artifactRoot "o3de") | Should Be $true
        Test-Path -LiteralPath (Join-Path $artifactRoot "qc") | Should Be $true
        Test-Path -LiteralPath (Join-Path $artifactRoot "temp") | Should Be $true
        Test-Path -LiteralPath (Join-Path $artifactRoot "undo") | Should Be $true
        Test-Path -LiteralPath (Join-Path $artifactRoot "cleanup") | Should Be $true

        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        $manifest.job.status | Should Be "created"
        $manifest.qc.overall | Should Be "not_run"
        $manifest.evidence.artifact_root | Should Be $artifactRoot

        if (Test-Path -LiteralPath $artifactRoot) {
            Remove-Item -LiteralPath $artifactRoot -Recurse -Force
        }
    }

    It "records structured errors and pending manual review in manifest updates" {
        $jobId = "pester-manifest-v1-updates"
        $artifactRoot = Join-Path $repoRoot ("scripts/generated/" + $jobId)
        if (Test-Path -LiteralPath $artifactRoot) {
            Remove-Item -LiteralPath $artifactRoot -Recurse -Force
        }
        $manifestPath = Join-Path $artifactRoot "manifest.json"

        & $newScript `
            -JobId $jobId `
            -Lane "release_character" `
            -CharacterName "Pester Update Character" `
            -Operator "human" `
            -ArtifactRoot $artifactRoot `
            -OutputPath $manifestPath | Out-Null
        $LASTEXITCODE | Should Be 0

        & $writeScript `
            -JobId $jobId `
            -ManifestPath $manifestPath `
            -EvidenceRoot $artifactRoot `
            -Status "fail" `
            -Message "Synthetic pester failure." `
            -ErrorCode "SYNTHETIC_FAIL" `
            -ErrorStage "unit_test" `
            -ExitCode 9 | Out-Null
        $LASTEXITCODE | Should Be 0

        & $writeScript `
            -JobId $jobId `
            -ManifestPath $manifestPath `
            -EvidenceRoot $artifactRoot `
            -Status "pending_manual" `
            -Message "Awaiting manual review." `
            -ManualReviewReason "Human verification pending." `
            -ExitCode 0 | Out-Null
        $LASTEXITCODE | Should Be 0

        $manifest = & $readScript -ManifestPath $manifestPath
        $manifest.job.status | Should Be "pending_manual"
        $manifest.manual_review.required | Should Be $true
        $manifest.manual_review.review_state | Should Be "pending"
        $manifest.manual_review.reason | Should Be "Human verification pending."
        $manifest.errors.Count | Should BeGreaterThan 0
        $manifest.errors[-1].code | Should Be "SYNTHETIC_FAIL"
        $manifest.errors[-1].stage | Should Be "unit_test"

        if (Test-Path -LiteralPath $artifactRoot) {
            Remove-Item -LiteralPath $artifactRoot -Recurse -Force
        }
    }
}
