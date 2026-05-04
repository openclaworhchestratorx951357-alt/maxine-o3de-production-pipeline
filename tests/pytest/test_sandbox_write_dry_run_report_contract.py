import subprocess
import sys
from pathlib import Path


def test_sandbox_write_dry_run_design_doc_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "roadmap" / "SANDBOX-WRITE-DRY-RUN-REPORT-DESIGN.md"
    assert path.exists()


def test_sandbox_write_dry_run_contract_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "contracts" / "SANDBOX-WRITE-DRY-RUN-REPORT-CONTRACT.md"
    assert path.exists()


def test_sandbox_write_dry_run_schema_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "schemas" / "maxine_sandbox_write_dry_run_report.schema.json"
    assert path.exists()


def test_sandbox_write_dry_run_report_example_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "examples" / "manifests" / "example-sandbox-write-dry-run-report.json"
    assert path.exists()


def test_sandbox_write_dry_run_job_example_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "examples" / "jobs" / "example-sandbox-write-dry-run-report-job.json"
    assert path.exists()


def test_sandbox_write_dry_run_report_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_write_dry_run_report.py"
    assert path.exists()


def test_sandbox_write_dry_run_contract_verifier_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "tools" / "audit" / "verify_sandbox_write_dry_run_contract.py"
    assert path.exists()


def test_sandbox_write_dry_run_report_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxWriteDryRunReport.ps1"
    assert path.exists()


def test_sandbox_write_dry_run_contract_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "powershell" / "Test-MaxineSandboxWriteDryRunContract.ps1"
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


def test_sandbox_write_dry_run_report_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_sandbox_write_dry_run_report.py"
    report = repo_root / "examples" / "manifests" / "example-sandbox-write-dry-run-report.json"
    result = subprocess.run(
        [sys.executable, str(script), "--report", str(report)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox write dry-run report verifier failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_sandbox_write_dry_run_contract_verifier_runs_successfully():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "audit" / "verify_sandbox_write_dry_run_contract.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "Sandbox write dry-run contract verifier failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_readme_contains_sandbox_write_dry_run_report_contract():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Write Dry-Run Report Contract" in readme


def test_handoff_contains_sandbox_write_dry_run_report_contract_criteria():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Sandbox Write Dry-Run Report Contract Complete Criteria" in handoff
