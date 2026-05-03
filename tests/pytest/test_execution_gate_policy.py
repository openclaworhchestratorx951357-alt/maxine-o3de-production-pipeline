import json
import subprocess
import sys
from pathlib import Path


def test_execution_gate_policy_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "validate_execution_gate_policy.py"
    assert script_path.exists()


def test_execution_gate_policy_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Validate-MaxineExecutionGatePolicy.ps1"
    assert wrapper_path.exists()


def test_execution_gate_policy_schema_exists():
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "schemas" / "maxine_execution_gate_policy.schema.json"
    assert schema_path.exists()


def _write_pre_write_report(path: Path, status: str):
    report = {
        "schema_version": "1.0.0",
        "report_id": "pre-write-report-test-001",
        "status": status,
        "proposal_id": "authoritative-write-proposal-test-001",
        "approval_validation_id": "approval-validation-test-001",
        "approved_write_fields": [
            "manifest.o3de.products.resolved"
        ],
        "blocked_reasons": [],
        "final_checks": [
            {
                "id": "proposal_approval_required",
                "passed": status == "pre_write_ready",
                "message": "example check"
            }
        ],
        "safety": {
            "read_only": True,
            "executes_writes": False,
            "marks_products_resolved": False,
            "claims_asset_ids": False,
            "runs_o3de_editor": False,
            "runs_asset_processor": False,
            "spawns_entities": False,
            "publishes_prefabs": False
        }
    }
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _run_validator(repo_root: Path, pre_write_report: Path, output_path: Path):
    script_path = repo_root / "tools" / "asset-resolver" / "validate_execution_gate_policy.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--pre-write-report",
        str(pre_write_report),
        "--output",
        str(output_path),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))


def test_pre_write_ready_produces_policy_only_and_write_disabled(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    pre_write_path = tmp_path / "pre-write-ready.json"
    output_path = tmp_path / "policy-ready.json"
    _write_pre_write_report(pre_write_path, "pre_write_ready")

    result = _run_validator(repo_root, pre_write_path, output_path)
    assert result.returncode == 0, f"Validator failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    report = json.loads(output_path.read_text(encoding="utf-8-sig"))
    assert report.get("status") == "policy_only"
    assert report.get("implementation_available") is False
    assert report.get("write_allowed") is False


def test_pre_write_blocked_produces_not_executable(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    pre_write_path = tmp_path / "pre-write-blocked.json"
    output_path = tmp_path / "policy-blocked.json"
    _write_pre_write_report(pre_write_path, "pre_write_blocked")

    result = _run_validator(repo_root, pre_write_path, output_path)
    assert result.returncode == 0

    report = json.loads(output_path.read_text(encoding="utf-8-sig"))
    assert report.get("status") == "not_executable"


def test_execution_gate_policy_safety_non_executing(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    pre_write_path = tmp_path / "pre-write-safety.json"
    output_path = tmp_path / "policy-safety.json"
    _write_pre_write_report(pre_write_path, "pre_write_ready")

    result = _run_validator(repo_root, pre_write_path, output_path)
    assert result.returncode == 0

    report = json.loads(output_path.read_text(encoding="utf-8-sig"))
    safety = report.get("safety", {})
    assert safety.get("read_only") is True
    assert safety.get("executes_writes") is False
    assert safety.get("marks_products_resolved") is False
    assert safety.get("claims_asset_ids") is False
    assert safety.get("runs_o3de_editor") is False
    assert safety.get("runs_asset_processor") is False
    assert safety.get("spawns_entities") is False
    assert safety.get("publishes_prefabs") is False


def test_manual_command_template_present(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    pre_write_path = tmp_path / "pre-write-command.json"
    output_path = tmp_path / "policy-command.json"
    _write_pre_write_report(pre_write_path, "pre_write_ready")

    result = _run_validator(repo_root, pre_write_path, output_path)
    assert result.returncode == 0

    report = json.loads(output_path.read_text(encoding="utf-8-sig"))
    command = report.get("manual_command_template", "")
    assert "Invoke-MaxineAuthoritativeResolverWrite.ps1" in command
    assert "-ConfirmWrite" in command


def test_rollback_requirements_present(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    pre_write_path = tmp_path / "pre-write-rollback.json"
    output_path = tmp_path / "policy-rollback.json"
    _write_pre_write_report(pre_write_path, "pre_write_ready")

    result = _run_validator(repo_root, pre_write_path, output_path)
    assert result.returncode == 0

    report = json.loads(output_path.read_text(encoding="utf-8-sig"))
    rollback = report.get("rollback_requirements", {})
    assert rollback.get("pre_write_snapshot") is True
    assert rollback.get("previous_manifest_copy") is True
    assert rollback.get("fields_to_revert") is True
    assert rollback.get("timestamp") is True
    assert rollback.get("operator_identity") is True
    assert rollback.get("rollback_command_proposal") is True


def test_no_products_resolved_field_written(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    pre_write_path = tmp_path / "pre-write-products.json"
    output_path = tmp_path / "policy-products.json"
    _write_pre_write_report(pre_write_path, "pre_write_ready")

    result = _run_validator(repo_root, pre_write_path, output_path)
    assert result.returncode == 0

    report = json.loads(output_path.read_text(encoding="utf-8-sig"))
    assert "o3de" not in report
    assert "products" not in report
