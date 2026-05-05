import json
from pathlib import Path


def test_adapter_scripts_exist():
    repo_root = Path(__file__).resolve().parents[2]
    required = [
        repo_root / "scripts" / "powershell" / "New-MaxineManifest.ps1",
        repo_root / "scripts" / "powershell" / "Write-MaxineEvidence.ps1",
        repo_root / "scripts" / "powershell" / "Invoke-MaxineJob.ps1",
        repo_root / "tools" / "manifest-validator" / "attach_qc_gate.py",
    ]
    for path in required:
        assert path.exists(), f"Missing adapter script: {path}"


def test_placeholder_readmes_exist():
    repo_root = Path(__file__).resolve().parents[2]
    required = [
        repo_root / "tools" / "asset-resolver" / "README.md",
        repo_root / "tools" / "qc-runner" / "README.md",
    ]
    for path in required:
        assert path.exists(), f"Missing placeholder README: {path}"


def test_example_jobs_exist():
    repo_root = Path(__file__).resolve().parents[2]
    required = [
        repo_root / "examples" / "jobs" / "example-photo-mesh-job.json",
        repo_root / "examples" / "jobs" / "example-release-character-job.json",
        repo_root / "examples" / "jobs" / "example-text-mesh-job.json",
    ]
    for path in required:
        assert path.exists(), f"Missing example job file: {path}"


def test_schema_baseline_structure():
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "schemas" / "maxine_job_manifest.schema.json"
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    required = data.get("required", [])
    for key in ("schema_version", "job", "identity", "inputs", "qc"):
        assert key in required, f"Schema required missing key: {key}"
