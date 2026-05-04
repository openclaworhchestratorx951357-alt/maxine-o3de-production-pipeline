import subprocess
import sys
from pathlib import Path


def test_sandbox_write_final_preflight_design_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "roadmap" / "SANDBOX-WRITE-FINAL-PREFLIGHT-CONTRACT-DESIGN.md"
    assert path.exists()


def test_sandbox_write_final_preflight_contract_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "contracts" / "SANDBOX-WRITE-FINAL-PREFLIGHT-CONTRACT.md"
    assert path.exists()


def test_sandbox_write_final_preflight_schema_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "schemas" / "maxine_sandbox_write_final_preflight_report.schema.json"
    assert path.exists()


def test_sandbox_write_final_preflight_report_example_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "examples" / "manifests" / "example-sandbox-write-final-preflight-report.json"
    assert path.exists()


def test_sandbox_write_final_preflight_job_example_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "examples" / "jobs" / "example-sandbox-write-final-preflight-job.json"
    assert path.exists()


def test_sandbox_write_final_preflight_report_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_write_final_preflight_report.py"
    assert path.exists()


def test_sandbox_write_final_preflight_contract_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_write_final_preflight_contract.py"
    assert path.exists()


def test_sandbox_write_final_preflight_report_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxWriteFinalPreflightReport.ps1"
    assert path.exists()


def test_sandbox_write_final_preflight_contract_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxWriteFinalPreflightContract.ps1"
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


def test_sandbox_write_final_preflight_report_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_sandbox_write_final_preflight_report.py"
    report = repo_root / "examples" / "manifests" / "example-sandbox-write-final-preflight-report.json"
    result = subprocess.run(
        [sys.executable, str(script), "--report", str(report)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox write final preflight report verifier failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_sandbox_write_final_preflight_contract_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_sandbox_write_final_preflight_contract.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox write final preflight contract verifier failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_sandbox_write_final_preflight_contract():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Write Final Preflight Contract" in readme


def test_handoff_contains_sandbox_write_final_preflight_contract_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Write Final Preflight Contract Complete Criteria" in handoff
