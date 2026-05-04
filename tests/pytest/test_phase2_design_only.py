import subprocess
import sys
from pathlib import Path


def test_phase2_design_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "roadmap" / "PHASE-2-SANDBOX-WRITE-PROTOTYPE-DESIGN.md"
    assert path.exists()


def test_phase2_contract_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "contracts" / "SANDBOX-WRITE-PROTOTYPE-CONTRACT.md"
    assert path.exists()


def test_phase2_inventory_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "audits" / "phase2_sandbox_write_design_inventory.json"
    assert path.exists()


def test_phase2_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_phase2_design_only.py"
    assert path.exists()


def test_phase2_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxinePhase2DesignOnly.ps1"
    assert path.exists()


def test_sandbox_write_command_admitted_under_safety_contract():
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


def test_authoritative_write_command_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
    assert not path.exists()


def test_phase2_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "audit" / "verify_phase2_design_only.py"
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Phase 2 verifier failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_phase2_section():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Phase 2 Sandbox-Only Write Prototype Design" in readme


def test_handoff_contains_phase2_complete_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Phase 2 Design-Only Complete Criteria" in handoff
