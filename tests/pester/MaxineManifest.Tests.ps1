Describe "Maxine Manifest Repository Baseline" {
    It "has schema file" {
        Test-Path -LiteralPath "schemas/maxine_job_manifest.schema.json" | Should Be $true
    }

    It "has example manifest file" {
        Test-Path -LiteralPath "examples/manifests/example-draft-mesh.manifest.json" | Should Be $true
    }

    It "has manifest validator script" {
        Test-Path -LiteralPath "tools/manifest-validator/validate_manifest.py" | Should Be $true
    }

    It "has New-MaxineManifest adapter script" {
        Test-Path -LiteralPath "scripts/powershell/New-MaxineManifest.ps1" | Should Be $true
    }

    It "has Write-MaxineEvidence adapter script" {
        Test-Path -LiteralPath "scripts/powershell/Write-MaxineEvidence.ps1" | Should Be $true
    }

    It "has Invoke-MaxineJob adapter script" {
        Test-Path -LiteralPath "scripts/powershell/Invoke-MaxineJob.ps1" | Should Be $true
    }
}
