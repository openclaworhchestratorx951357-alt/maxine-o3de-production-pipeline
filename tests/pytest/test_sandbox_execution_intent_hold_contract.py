import subprocess
import sys
from pathlib import Path


def test_sandbox_execution_intent_design_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "roadmap" / "SANDBOX-EXECUTION-INTENT-HOLD-DESIGN.md"
    assert path.exists()


def test_sandbox_execution_intent_contract_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "contracts" / "SANDBOX-EXECUTION-INTENT-HOLD-CONTRACT.md"
    assert path.exists()


def test_sandbox_execution_intent_schema_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "schemas" / "maxine_sandbox_execution_intent.schema.json"
    assert path.exists()


def test_sandbox_execution_hold_schema_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "schemas" / "maxine_sandbox_execution_hold.schema.json"
    assert path.exists()


def test_sandbox_execution_intent_example_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "examples" / "manifests" / "example-sandbox-execution-intent.json"
    assert path.exists()


def test_sandbox_execution_hold_example_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "examples" / "manifests" / "example-sandbox-execution-hold.json"
    assert path.exists()


def test_sandbox_execution_intent_hold_job_example_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "examples" / "jobs" / "example-sandbox-execution-intent-hold-job.json"
    assert path.exists()


def test_sandbox_execution_intent_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_execution_intent.py"
    assert path.exists()


def test_sandbox_execution_hold_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_execution_hold.py"
    assert path.exists()


def test_sandbox_execution_intent_hold_contract_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_execution_intent_hold_contract.py"
    assert path.exists()


def test_sandbox_execution_intent_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxExecutionIntent.ps1"
    assert path.exists()


def test_sandbox_execution_hold_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxExecutionHold.ps1"
    assert path.exists()


def test_sandbox_execution_intent_hold_contract_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxExecutionIntentHoldContract.ps1"
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


def test_sandbox_execution_intent_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_sandbox_execution_intent.py"
    intent = repo_root / "examples" / "manifests" / "example-sandbox-execution-intent.json"
    report = repo_root / "examples" / "manifests" / "example-sandbox-write-final-preflight-report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--intent",
            str(intent),
            "--final-preflight-report",
            str(report),
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox execution intent verifier failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_sandbox_execution_hold_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_sandbox_execution_hold.py"
    hold = repo_root / "examples" / "manifests" / "example-sandbox-execution-hold.json"
    result = subprocess.run(
        [sys.executable, str(script), "--hold", str(hold)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox execution hold verifier failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_sandbox_execution_intent_hold_contract_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_sandbox_execution_intent_hold_contract.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox execution intent/hold contract verifier failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_sandbox_execution_intent_hold_contract():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Execution Intent and Hold Contract" in readme


def test_handoff_contains_sandbox_execution_intent_hold_contract_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Execution Intent and Hold Contract Complete Criteria" in handoff
