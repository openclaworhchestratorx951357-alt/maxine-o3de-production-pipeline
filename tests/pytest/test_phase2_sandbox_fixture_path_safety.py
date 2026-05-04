import subprocess
import sys
from pathlib import Path


def test_path_safety_design_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "roadmap" / "PHASE-2-SANDBOX-FIXTURE-PATH-SAFETY-DESIGN.md"
    assert path.exists()


def test_path_safety_contract_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "contracts" / "SANDBOX-FIXTURE-PATH-SAFETY-CONTRACT.md"
    assert path.exists()


def test_sandbox_readme_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "examples" / "sandbox" / "README.md"
    assert path.exists()


def test_path_safety_policy_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "audits" / "phase2_sandbox_path_safety_policy.json"
    assert path.exists()


def test_path_safety_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_path_safety.py"
    assert path.exists()


def test_phase_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_phase2_sandbox_fixture_design.py"
    assert path.exists()


def test_path_safety_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxPathSafety.ps1"
    assert path.exists()


def test_phase_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxinePhase2SandboxFixtureDesign.ps1"
    assert path.exists()


def test_invoke_sandbox_write_admitted_under_safety_contract():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxResolverWrite.ps1"
    assert path.exists()
    safety = repo_root / "tools" / "audit" / "verify_sandbox_writer_safety.py"
    result = subprocess.run(
        [sys.executable, str(safety)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox writer safety verification failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_invoke_sandbox_rollback_admitted_under_safety_contract():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxRollback.ps1"
    assert path.exists()
    safety = repo_root / "tools" / "audit" / "verify_sandbox_writer_safety.py"
    result = subprocess.run(
        [sys.executable, str(safety)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox writer safety verification failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_invoke_authoritative_write_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
    assert not path.exists()


def test_path_safety_policy_only_passes():
    repo_root = Path(__file__).resolve().parents[2]
    verifier = repo_root / "tools" / "audit" / "verify_sandbox_path_safety.py"
    result = subprocess.run(
        [sys.executable, str(verifier)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Path-safety policy-only validation failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_path_safety_accepts_sandbox_path():
    repo_root = Path(__file__).resolve().parents[2]
    verifier = repo_root / "tools" / "audit" / "verify_sandbox_path_safety.py"
    result = subprocess.run(
        [
            sys.executable,
            str(verifier),
            "--path",
            "examples/sandbox/manifests/working/example-working.manifest.json",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Accepted sandbox path check failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_path_safety_rejects_parent_traversal():
    repo_root = Path(__file__).resolve().parents[2]
    verifier = repo_root / "tools" / "audit" / "verify_sandbox_path_safety.py"
    result = subprocess.run(
        [sys.executable, str(verifier), "--path", "../outside.json"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_path_safety_rejects_production_token_path():
    repo_root = Path(__file__).resolve().parents[2]
    verifier = repo_root / "tools" / "audit" / "verify_sandbox_path_safety.py"
    result = subprocess.run(
        [
            sys.executable,
            str(verifier),
            "--path",
            "C:/Users/topgu/OneDrive/Documents/O3de_GEMS_Research/Projects/MaxineShow/Project.json",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_phase_verifier_passes():
    repo_root = Path(__file__).resolve().parents[2]
    verifier = repo_root / "tools" / "audit" / "verify_phase2_sandbox_fixture_design.py"
    result = subprocess.run(
        [sys.executable, str(verifier)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Phase verifier failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_phase2_sandbox_fixture_path_safety_design():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Phase 2 Sandbox Fixture Path-Safety Design" in readme


def test_handoff_contains_phase2_sandbox_fixture_path_safety_complete_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Phase 2 Sandbox Fixture Path-Safety Complete Criteria" in handoff
