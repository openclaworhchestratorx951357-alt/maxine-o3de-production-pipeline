import subprocess
import sys
from pathlib import Path


def test_phase2_rollback_design_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "roadmap" / "PHASE-2-ROLLBACK-ARTIFACT-DESIGN.md"
    assert path.exists()


def test_sandbox_rollback_contract_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "contracts" / "SANDBOX-ROLLBACK-ARTIFACT-CONTRACT.md"
    assert path.exists()


def test_sandbox_rollback_schema_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "schemas" / "maxine_sandbox_rollback_artifact.schema.json"
    assert path.exists()


def test_sandbox_rollback_example_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "examples" / "manifests" / "example-sandbox-rollback-artifact.json"
    assert path.exists()


def test_sandbox_rollback_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_rollback_artifact.py"
    assert path.exists()


def test_phase2_rollback_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_phase2_rollback_design.py"
    assert path.exists()


def test_sandbox_rollback_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxRollbackArtifact.ps1"
    assert path.exists()


def test_phase2_rollback_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxinePhase2RollbackDesign.ps1"
    assert path.exists()


def test_invoke_sandbox_rollback_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxRollback.ps1"
    assert not path.exists()


def test_invoke_sandbox_write_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxResolverWrite.ps1"
    assert not path.exists()


def test_invoke_authoritative_write_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
    assert not path.exists()


def test_rollback_artifact_verifier_passes():
    repo_root = Path(__file__).resolve().parents[2]
    verifier = repo_root / "tools" / "audit" / "verify_sandbox_rollback_artifact.py"
    artifact = repo_root / "examples" / "manifests" / "example-sandbox-rollback-artifact.json"
    result = subprocess.run(
        [sys.executable, str(verifier), "--artifact", str(artifact)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Rollback artifact verifier failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_phase2_rollback_design_verifier_passes():
    repo_root = Path(__file__).resolve().parents[2]
    verifier = repo_root / "tools" / "audit" / "verify_phase2_rollback_design.py"
    result = subprocess.run(
        [sys.executable, str(verifier)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Phase 2 rollback design verifier failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_phase2_rollback_design():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Phase 2 Rollback Artifact Design" in readme


def test_handoff_contains_phase2_rollback_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Phase 2 Rollback Design Complete Criteria" in handoff
