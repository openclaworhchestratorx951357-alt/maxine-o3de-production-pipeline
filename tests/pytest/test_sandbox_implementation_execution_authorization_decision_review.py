import subprocess
import sys
from pathlib import Path


def test_execution_authorization_decision_review_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = (
        repo_root
        / "docs"
        / "reviews"
        / "SANDBOX-IMPLEMENTATION-EXECUTION-AUTHORIZATION-DECISION-REVIEW.md"
    )
    assert path.exists()


def test_execution_authorization_decision_review_package_json_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = (
        repo_root
        / "docs"
        / "reviews"
        / "sandbox_implementation_execution_authorization_decision_review_package.json"
    )
    assert path.exists()


def test_execution_authorization_decision_template_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = (
        repo_root
        / "docs"
        / "reviews"
        / "sandbox_implementation_execution_authorization_decision_template.json"
    )
    assert path.exists()


def test_execution_authorization_decision_review_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = (
        repo_root
        / "tools"
        / "audit"
        / "verify_sandbox_implementation_execution_authorization_decision_review.py"
    )
    assert path.exists()


def test_execution_authorization_decision_review_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = (
        repo_root
        / "scripts"
        / "powershell"
        / "Test-MaxineSandboxImplementationExecutionAuthorizationDecisionReview.ps1"
    )
    assert path.exists()


def test_invoke_sandbox_write_absent_for_execution_authorization_decision_review_phase():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxResolverWrite.ps1"
    assert not path.exists()


def test_invoke_sandbox_rollback_absent_for_execution_authorization_decision_review_phase():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxRollback.ps1"
    assert not path.exists()


def test_invoke_authoritative_write_absent_for_execution_authorization_decision_review_phase():
    repo_root = Path(__file__).resolve().parents[2]
    path = (
        repo_root
        / "scripts"
        / "powershell"
        / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
    )
    assert not path.exists()


def test_execution_authorization_decision_review_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root
        / "tools"
        / "audit"
        / "verify_sandbox_implementation_execution_authorization_decision_review.py"
    )
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox implementation execution-authorization decision review verifier failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_execution_authorization_decision_review_section():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert (
        "Sandbox Implementation-Branch Execution-Authorization Decision Review Package"
        in readme
    )


def test_handoff_contains_execution_authorization_decision_review_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert (
        "Sandbox Implementation-Branch Execution-Authorization Decision Review Package Complete Criteria"
        in handoff
    )
