Describe "Maxine Manifest Repository Baseline" {
    It "has schema file" {
        Test-Path -LiteralPath "schemas/maxine_job_manifest.schema.json" | Should -BeTrue
    }

    It "has example manifest file" {
        Test-Path -LiteralPath "examples/manifests/example-draft-mesh.manifest.json" | Should -BeTrue
    }

    It "has manifest validator script" {
        Test-Path -LiteralPath "tools/manifest-validator/validate_manifest.py" | Should -BeTrue
    }
}
