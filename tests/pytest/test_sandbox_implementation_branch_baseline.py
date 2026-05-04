import subprocess
import sys
from pathlib import Path


def test_sandbox_implementation_branch_baseline_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "audits" / "SANDBOX-IMPLEMENTATION-BRANCH-BASELINE.md"
    assert path.exists()


def test_sandbox_implementation_branch_baseline_json_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "audits" / "sandbox_implementation_branch_baseline.json"
    assert path.exists()


def test_sandbox_implementation_branch_baseline_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_implementation_branch_baseline.py"
    assert path.exists()


def test_sandbox_implementation_branch_baseline_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxImplementationBranchBaseline.ps1"
    assert path.exists()


def test_invoke_sandbox_write_absent_for_baseline_phase():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxResolverWrite.ps1"
    assert not path.exists()


def test_invoke_sandbox_rollback_absent_for_baseline_phase():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxRollback.ps1"
    assert not path.exists()


def test_invoke_authoritative_write_absent_for_baseline_phase():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
    assert not path.exists()


def test_sandbox_implementation_branch_baseline_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_sandbox_implementation_branch_baseline.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox implementation branch baseline verifier failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_sandbox_implementation_branch_baseline():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Implementation Branch Baseline" in readme


def test_handoff_contains_sandbox_implementation_branch_baseline_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Implementation Branch Baseline Complete Criteria" in handoff
