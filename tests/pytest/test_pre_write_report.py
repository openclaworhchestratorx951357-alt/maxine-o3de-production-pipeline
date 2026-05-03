import json
import subprocess
import sys
from pathlib import Path


def test_pre_write_report_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "build_pre_write_report.py"
    assert script_path.exists()


def test_pre_write_report_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Build-MaxinePreWriteReport.ps1"
    assert wrapper_path.exists()


def test_pre_write_report_schema_exists():
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "schemas" / "maxine_pre_write_report.schema.json"
    assert schema_path.exists()


def _write_proposal(path: Path, status: str = "approval_required"):
    proposal = {
        "schema_version": "1.0.0",
        "proposal_id": "authoritative-write-proposal-test-001",
        "status": status,
        "source_plan_id": "authoritative-plan-test-001",
        "proposed_write_fields": {
            "manifest.o3de.products.resolved": {"write_now": False},
            "manifest.o3de.products.operator_approval": {"write_now": False}
        },
        "required_approval": {
            "required_fields": [
                "approval_id",
                "approved_by",
                "approved_at_utc",
                "approval_reason",
                "approved_plan_id",
                "approval_scope"
            ]
        },
        "forbidden_until_approved": [
            "resolved true",
            "Asset IDs"
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
    path.write_text(json.dumps(proposal, indent=2), encoding="utf-8")


def _write_approval_validation(path: Path, status: str = "approval_valid"):
    validation = {
        "schema_version": "1.0.0",
        "validation_id": "approval-validation-test-001",
        "status": status,
        "proposal_id": "authoritative-write-proposal-test-001",
        "approval_id": "approval-test-001",
        "checks": [
            {
                "id": "approved_write_fields_subset",
                "passed": status == "approval_valid",
                "message": "approved_write_fields must reference proposal fields.",
                "details": {
                    "approved_write_fields": [
                        "manifest.o3de.products.resolved",
                        "manifest.o3de.products.operator_approval"
                    ]
                }
            }
        ],
        "blockers": [],
        "safety": {
            "read_only": True,
            "executes_writes": False,
            "marks_products_resolved": False,
            "claims_asset_ids": False,
            "runs_o3de_editor": False,
            "runs_asset_processor": False,
            "spawns_entities": False,
            "publishes_prefabs": False
        },
        "updated_utc": "2026-05-03T00:00:00Z"
    }
    path.write_text(json.dumps(validation, indent=2), encoding="utf-8")


def _run_builder(repo_root: Path, proposal_path: Path, validation_path: Path, output_path: Path):
    script_path = repo_root / "tools" / "asset-resolver" / "build_pre_write_report.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--proposal",
        str(proposal_path),
        "--approval-validation",
        str(validation_path),
        "--output",
        str(output_path),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))


def test_ready_inputs_produce_pre_write_ready(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    proposal_path = tmp_path / "proposal-ready.json"
    validation_path = tmp_path / "approval-validation-ready.json"
    report_path = tmp_path / "pre-write-ready.json"

    _write_proposal(proposal_path, status="approval_required")
    _write_approval_validation(validation_path, status="approval_valid")

    result = _run_builder(repo_root, proposal_path, validation_path, report_path)
    assert result.returncode == 0, f"Builder failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    assert report.get("status") == "pre_write_ready"


def test_blocked_proposal_produces_pre_write_blocked(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    proposal_path = tmp_path / "proposal-blocked.json"
    validation_path = tmp_path / "approval-validation-blocked.json"
    report_path = tmp_path / "pre-write-blocked.json"

    _write_proposal(proposal_path, status="blocked")
    _write_approval_validation(validation_path, status="approval_valid")

    result = _run_builder(repo_root, proposal_path, validation_path, report_path)
    assert result.returncode == 0

    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    assert report.get("status") == "pre_write_blocked"


def test_approval_invalid_never_produces_ready(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    proposal_path = tmp_path / "proposal-incomplete.json"
    validation_path = tmp_path / "approval-validation-invalid.json"
    report_path = tmp_path / "pre-write-incomplete.json"

    _write_proposal(proposal_path, status="approval_required")
    _write_approval_validation(validation_path, status="approval_invalid")

    result = _run_builder(repo_root, proposal_path, validation_path, report_path)
    assert result.returncode == 0

    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    assert report.get("status") in {"pre_write_incomplete", "pre_write_blocked"}
    assert report.get("status") != "pre_write_ready"


def test_pre_write_report_safety_non_executing(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    proposal_path = tmp_path / "proposal-safety.json"
    validation_path = tmp_path / "approval-validation-safety.json"
    report_path = tmp_path / "pre-write-safety.json"

    _write_proposal(proposal_path, status="approval_required")
    _write_approval_validation(validation_path, status="approval_valid")

    result = _run_builder(repo_root, proposal_path, validation_path, report_path)
    assert result.returncode == 0

    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    safety = report.get("safety", {})
    assert safety.get("read_only") is True
    assert safety.get("executes_writes") is False
    assert safety.get("marks_products_resolved") is False
    assert safety.get("claims_asset_ids") is False
    assert safety.get("runs_o3de_editor") is False
    assert safety.get("runs_asset_processor") is False
    assert safety.get("spawns_entities") is False
    assert safety.get("publishes_prefabs") is False


def test_no_products_resolved_field_written(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    proposal_path = tmp_path / "proposal-no-products.json"
    validation_path = tmp_path / "approval-validation-no-products.json"
    report_path = tmp_path / "pre-write-no-products.json"

    _write_proposal(proposal_path, status="approval_required")
    _write_approval_validation(validation_path, status="approval_valid")

    result = _run_builder(repo_root, proposal_path, validation_path, report_path)
    assert result.returncode == 0

    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    assert "o3de" not in report
    assert "products" not in report
