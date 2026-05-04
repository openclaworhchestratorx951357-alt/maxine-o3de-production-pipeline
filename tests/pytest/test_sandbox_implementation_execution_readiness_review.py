import subprocess
import sys
from pathlib import Path


def test_execution_readiness_review_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "reviews" / "SANDBOX-IMPLEMENTATION-EXECUTION-READINESS-REVIEW.md"
    assert path.exists()


def test_execution_readiness_review_package_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "reviews" / "sandbox_implementation_execution_readiness_review_package.json"
    assert path.exists()


def test_execution_readiness_decision_template_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "reviews" / "sandbox_implementation_execution_readiness_decision_template.json"
    assert path.exists()


def test_execution_readiness_review_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_implementation_execution_readiness_review.py"
    assert path.exists()


def test_execution_readiness_review_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxImplementationExecutionReadinessReview.ps1"
    assert path.exists()


def test_invoke_sandbox_write_admitted_under_safety_contract_for_execution_readiness_review_phase():
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


def test_invoke_sandbox_rollback_admitted_under_safety_contract_for_execution_readiness_review_phase():
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


def test_invoke_authoritative_write_absent_for_execution_readiness_review_phase():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
    assert not path.exists()


def test_execution_readiness_review_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_sandbox_implementation_execution_readiness_review.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox implementation execution-readiness review verifier failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_execution_readiness_review_section():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Implementation-Branch Execution-Readiness Review" in readme


def test_handoff_contains_execution_readiness_review_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Implementation-Branch Execution-Readiness Review Complete Criteria" in handoff
