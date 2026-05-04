import subprocess
import sys
from pathlib import Path


def test_sandbox_implementation_decision_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "reviews" / "SANDBOX-PROTOTYPE-IMPLEMENTATION-DECISION.md"
    assert path.exists()


def test_sandbox_implementation_decision_json_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "reviews" / "sandbox_implementation_decision.json"
    assert path.exists()


def test_sandbox_implementation_decision_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_implementation_decision.py"
    assert path.exists()


def test_sandbox_implementation_decision_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxImplementationDecision.ps1"
    assert path.exists()


def test_invoke_sandbox_write_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxResolverWrite.ps1"
    assert not path.exists()


def test_invoke_sandbox_rollback_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineSandboxRollback.ps1"
    assert not path.exists()


def test_invoke_authoritative_write_absent():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
    assert not path.exists()


def test_sandbox_implementation_decision_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_sandbox_implementation_decision.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox implementation decision verifier failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_sandbox_implementation_decision_record():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Prototype Implementation Decision Record" in readme


def test_handoff_contains_sandbox_implementation_decision_record_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Prototype Implementation Decision Record Complete Criteria" in handoff
