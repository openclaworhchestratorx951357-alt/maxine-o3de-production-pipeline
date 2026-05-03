import subprocess
import sys
from pathlib import Path


def test_phase2_acceptance_decision_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "reviews" / "PHASE-2-ACCEPTANCE-DECISION.md"
    assert path.exists()


def test_phase2_acceptance_decision_json_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "reviews" / "phase2_acceptance_decision.json"
    assert path.exists()


def test_phase2_acceptance_decision_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_phase2_acceptance_decision.py"
    assert path.exists()


def test_phase2_acceptance_decision_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxinePhase2AcceptanceDecision.ps1"
    assert path.exists()


def test_sandbox_write_command_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxResolverWrite.ps1"
    assert not path.exists()


def test_sandbox_rollback_command_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxRollback.ps1"
    assert not path.exists()


def test_authoritative_write_command_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
    assert not path.exists()


def test_phase2_acceptance_decision_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_phase2_acceptance_decision.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Phase 2 acceptance decision verifier failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_phase2_acceptance_decision():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Phase 2 Acceptance Decision" in readme


def test_handoff_contains_phase2_acceptance_decision_complete_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Phase 2 Acceptance Decision Complete Criteria" in handoff
