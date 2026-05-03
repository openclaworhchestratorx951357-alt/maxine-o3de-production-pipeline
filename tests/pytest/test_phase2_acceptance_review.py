import subprocess
import sys
from pathlib import Path


def test_phase2_acceptance_review_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "reviews" / "PHASE-2-ACCEPTANCE-REVIEW.md"
    assert path.exists()


def test_phase2_acceptance_review_package_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "reviews" / "phase2_acceptance_review_package.json"
    assert path.exists()


def test_phase2_acceptance_review_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_phase2_acceptance_review.py"
    assert path.exists()


def test_phase2_acceptance_review_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxinePhase2AcceptanceReview.ps1"
    assert path.exists()


def test_sandbox_write_command_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxResolverWrite.ps1"
    assert not path.exists()


def test_rollback_command_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxRollback.ps1"
    assert not path.exists()


def test_authoritative_write_command_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
    assert not path.exists()


def test_phase2_acceptance_review_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_phase2_acceptance_review.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Phase 2 acceptance review verifier failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_phase2_acceptance_review():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Phase 2 Acceptance Review" in readme


def test_handoff_contains_phase2_acceptance_review_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Phase 2 Acceptance Review Complete Criteria" in handoff
