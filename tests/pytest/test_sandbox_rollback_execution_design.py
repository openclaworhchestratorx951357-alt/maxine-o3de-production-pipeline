import subprocess
import sys
from pathlib import Path


def test_rollback_execution_design_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "roadmap" / "SANDBOX-PROTOTYPE-ROLLBACK-EXECUTION-DESIGN.md"
    assert path.exists()


def test_rollback_execution_contract_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "contracts" / "SANDBOX-ROLLBACK-EXECUTION-CONTRACT.md"
    assert path.exists()


def test_rollback_execution_design_plan_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "audits" / "sandbox_rollback_execution_design_plan.json"
    assert path.exists()


def test_rollback_execution_design_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_rollback_execution_design.py"
    assert path.exists()


def test_rollback_execution_design_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxRollbackExecutionDesign.ps1"
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


def test_rollback_execution_design_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_sandbox_rollback_execution_design.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Sandbox rollback execution design verifier failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_sandbox_rollback_execution_design():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Prototype Rollback Execution Design" in readme


def test_handoff_contains_sandbox_rollback_execution_design_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Prototype Rollback Execution Design Complete Criteria" in handoff
