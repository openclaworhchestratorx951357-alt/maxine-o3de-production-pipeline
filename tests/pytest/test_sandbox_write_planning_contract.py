import subprocess
import sys
from pathlib import Path


def test_sandbox_write_planning_design_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "roadmap" / "SANDBOX-WRITE-PLANNING-CONTRACT-DESIGN.md"
    assert path.exists()


def test_sandbox_write_planning_contract_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "contracts" / "SANDBOX-WRITE-PLANNING-CONTRACT.md"
    assert path.exists()


def test_sandbox_write_planning_plan_json_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "audits" / "sandbox_write_planning_contract_plan.json"
    assert path.exists()


def test_sandbox_write_plan_example_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "examples" / "manifests" / "example-sandbox-write-plan.json"
    assert path.exists()


def test_sandbox_write_plan_job_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "examples" / "jobs" / "example-sandbox-write-plan-job.json"
    assert path.exists()


def test_sandbox_write_plan_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_write_plan.py"
    assert path.exists()


def test_sandbox_write_planning_contract_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_write_planning_contract.py"
    assert path.exists()


def test_sandbox_write_plan_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxWritePlan.ps1"
    assert path.exists()


def test_sandbox_write_planning_contract_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxWritePlanningContract.ps1"
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


def test_sandbox_write_plan_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_sandbox_write_plan.py"
    plan = repo_root / "examples" / "manifests" / "example-sandbox-write-plan.json"
    result = subprocess.run(
        [sys.executable, str(script), "--plan", str(plan)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Sandbox write plan verifier failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_sandbox_write_planning_contract_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_sandbox_write_planning_contract.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox write planning contract verifier failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_sandbox_write_planning_contract():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Write Planning Contract" in readme


def test_handoff_contains_sandbox_write_planning_contract_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Write Planning Contract Complete Criteria" in handoff
