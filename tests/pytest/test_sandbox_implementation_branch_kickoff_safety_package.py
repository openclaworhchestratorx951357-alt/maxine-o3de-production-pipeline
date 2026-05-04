import subprocess
import sys
from pathlib import Path


def test_kickoff_safety_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = (
        repo_root
        / "docs"
        / "audits"
        / "SANDBOX-IMPLEMENTATION-BRANCH-KICKOFF-SAFETY-PACKAGE.md"
    )
    assert path.exists()


def test_kickoff_safety_json_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "audits" / "sandbox_implementation_branch_kickoff_safety_package.json"
    assert path.exists()


def test_kickoff_safety_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = (
        repo_root
        / "tools"
        / "audit"
        / "verify_sandbox_implementation_branch_kickoff_safety_package.py"
    )
    assert path.exists()


def test_kickoff_safety_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = (
        repo_root
        / "scripts"
        / "powershell"
        / "Test-MaxineSandboxImplementationBranchKickoffSafetyPackage.ps1"
    )
    assert path.exists()


def test_invoke_sandbox_write_absent_for_kickoff_safety_phase():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxResolverWrite.ps1"
    assert not path.exists()


def test_invoke_sandbox_rollback_absent_for_kickoff_safety_phase():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxRollback.ps1"
    assert not path.exists()


def test_invoke_authoritative_write_absent_for_kickoff_safety_phase():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
    assert not path.exists()


def test_kickoff_safety_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "tools"
        / "audit"
        / "verify_sandbox_implementation_branch_kickoff_safety_package.py"
    )
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox implementation kickoff safety package verifier failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_kickoff_safety_package():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Implementation-Branch Kickoff Safety Package" in readme


def test_handoff_contains_kickoff_safety_package_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Implementation-Branch Kickoff Safety Package Complete Criteria" in handoff
