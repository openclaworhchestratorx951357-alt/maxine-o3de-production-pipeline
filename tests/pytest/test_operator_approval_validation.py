import datetime as dt
import json
import subprocess
import sys
from pathlib import Path


def test_operator_approval_validation_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "validate_operator_approval.py"
    assert script_path.exists()


def test_operator_approval_validation_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Validate-MaxineOperatorApproval.ps1"
    assert wrapper_path.exists()


def test_operator_approval_schema_exists():
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "schemas" / "maxine_operator_approval.schema.json"
    assert schema_path.exists()


def _utc_iso(offset_days: int = 0) -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=offset_days)).isoformat().replace("+00:00", "Z")


def _write_proposal(path: Path, status: str = "approval_required"):
    proposal = {
        "schema_version": "1.0.0",
        "proposal_id": "authoritative-write-proposal-test-001",
        "status": status,
        "source_plan_id": "authoritative-plan-test-001",
        "proposed_write_fields": {
            "manifest.o3de.products.resolved": {"write_now": False},
            "manifest.o3de.products.resolution_mode": {"write_now": False},
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


def _write_approval(path: Path, *, proposal_id: str = "authoritative-write-proposal-test-001", expired: bool = False):
    approval = {
        "schema_version": "1.0.0",
        "approval_id": "approval-test-001",
        "proposal_id": proposal_id,
        "approved_by": "operator-1",
        "approved_at_utc": _utc_iso(offset_days=-1),
        "approval_reason": "Validated proposal for next gated stage.",
        "approved_plan_id": "authoritative-plan-test-001",
        "approval_scope": "pre-write-report-only",
        "approved_write_fields": [
            "manifest.o3de.products.resolved",
            "manifest.o3de.products.operator_approval"
        ],
        "expires_at_utc": _utc_iso(offset_days=-1 if expired else 7),
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
    path.write_text(json.dumps(approval, indent=2), encoding="utf-8")


def _run_validator(repo_root: Path, proposal_path: Path, approval_path: Path, output_path: Path):
    script_path = repo_root / "tools" / "asset-resolver" / "validate_operator_approval.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--proposal",
        str(proposal_path),
        "--approval",
        str(approval_path),
        "--output",
        str(output_path),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))


def test_valid_approval_produces_approval_valid(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    proposal_path = tmp_path / "proposal-valid.json"
    approval_path = tmp_path / "approval-valid.json"
    report_path = tmp_path / "report-valid.json"

    _write_proposal(proposal_path, status="approval_required")
    _write_approval(approval_path, expired=False)

    result = _run_validator(repo_root, proposal_path, approval_path, report_path)
    assert result.returncode == 0, f"Validator failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    assert report.get("status") == "approval_valid"


def test_expired_approval_produces_approval_expired(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    proposal_path = tmp_path / "proposal-expired.json"
    approval_path = tmp_path / "approval-expired.json"
    report_path = tmp_path / "report-expired.json"

    _write_proposal(proposal_path, status="approval_required")
    _write_approval(approval_path, expired=True)

    result = _run_validator(repo_root, proposal_path, approval_path, report_path)
    assert result.returncode == 0

    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    assert report.get("status") == "approval_expired"


def test_blocked_proposal_produces_proposal_not_approvable(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    proposal_path = tmp_path / "proposal-blocked.json"
    approval_path = tmp_path / "approval-blocked.json"
    report_path = tmp_path / "report-blocked.json"

    _write_proposal(proposal_path, status="blocked")
    _write_approval(approval_path, expired=False)

    result = _run_validator(repo_root, proposal_path, approval_path, report_path)
    assert result.returncode == 0

    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    assert report.get("status") == "proposal_not_approvable"


def test_mismatched_proposal_id_produces_approval_invalid(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    proposal_path = tmp_path / "proposal-mismatch.json"
    approval_path = tmp_path / "approval-mismatch.json"
    report_path = tmp_path / "report-mismatch.json"

    _write_proposal(proposal_path, status="approval_required")
    _write_approval(approval_path, proposal_id="wrong-proposal-id", expired=False)

    result = _run_validator(repo_root, proposal_path, approval_path, report_path)
    assert result.returncode == 0

    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    assert report.get("status") == "approval_invalid"


def test_validation_report_safety_is_non_executing(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    proposal_path = tmp_path / "proposal-safety.json"
    approval_path = tmp_path / "approval-safety.json"
    report_path = tmp_path / "report-safety.json"

    _write_proposal(proposal_path, status="approval_required")
    _write_approval(approval_path, expired=False)

    result = _run_validator(repo_root, proposal_path, approval_path, report_path)
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
