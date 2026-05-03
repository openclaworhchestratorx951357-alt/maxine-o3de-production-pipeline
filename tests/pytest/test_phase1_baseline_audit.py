import subprocess
import sys
from pathlib import Path


def test_phase1_audit_report_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "audits" / "PHASE-1-OPERATIONAL-BASELINE.md"
    assert path.exists()


def test_phase1_inventory_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "audits" / "phase1_operational_baseline_inventory.json"
    assert path.exists()


def test_phase1_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_phase1_baseline.py"
    assert path.exists()


def test_phase1_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxinePhase1Baseline.ps1"
    assert path.exists()


def test_authoritative_write_command_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
    assert not path.exists()


def test_phase1_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "audit" / "verify_phase1_baseline.py"
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Verifier failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_phase1_baseline_section():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Phase 1 Operational Baseline" in readme


def test_handoff_contains_phase1_complete_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Phase 1 Operational Baseline Complete Criteria" in handoff
