import json
import subprocess
import sys
from pathlib import Path


def test_authoritative_write_protocol_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "propose_authoritative_write_protocol.py"
    assert script_path.exists()


def test_authoritative_write_protocol_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Propose-MaxineAuthoritativeWriteProtocol.ps1"
    assert wrapper_path.exists()


def test_authoritative_write_protocol_schema_exists():
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "schemas" / "maxine_authoritative_write_protocol.schema.json"
    assert schema_path.exists()


def _write_plan(path: Path, status: str):
    plan = {
        "schema_version": "1.0.0",
        "plan_id": "authoritative-plan-test-001",
        "status": status,
        "source_manifest": "examples/manifests/example-draft-mesh.manifest.json",
        "required_proofs": [],
        "available_evidence": {},
        "missing_proofs": [],
        "proposed_actions": [],
        "forbidden_actions": [],
        "safety": {
            "read_only": True,
            "writes_resolved_products": False,
            "runs_o3de_editor": False,
            "runs_asset_processor": False,
            "opens_database": False,
            "modifies_database": False,
            "spawns_entities": False,
            "publishes_prefabs": False,
            "claims_asset_ids": False
        }
    }
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def _run_proposal(repo_root: Path, plan_path: Path, output_path: Path):
    script_path = repo_root / "tools" / "asset-resolver" / "propose_authoritative_write_protocol.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--plan",
        str(plan_path),
        "--output",
        str(output_path),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))


def test_ready_plan_produces_approval_required(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    plan_path = tmp_path / "ready-plan.json"
    proposal_path = tmp_path / "ready-proposal.json"
    _write_plan(plan_path, "dry_run_ready")

    result = _run_proposal(repo_root, plan_path, proposal_path)
    assert result.returncode == 0, f"Proposal failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    proposal = json.loads(proposal_path.read_text(encoding="utf-8-sig"))
    assert proposal.get("status") == "approval_required"


def test_incomplete_plan_produces_blocked(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    plan_path = tmp_path / "incomplete-plan.json"
    proposal_path = tmp_path / "incomplete-proposal.json"
    _write_plan(plan_path, "dry_run_incomplete")

    result = _run_proposal(repo_root, plan_path, proposal_path)
    assert result.returncode == 0

    proposal = json.loads(proposal_path.read_text(encoding="utf-8-sig"))
    assert proposal.get("status") == "blocked"


def test_proposal_safety_forbids_writes_resolution_and_runtime(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    plan_path = tmp_path / "safety-plan.json"
    proposal_path = tmp_path / "safety-proposal.json"
    _write_plan(plan_path, "dry_run_ready")

    result = _run_proposal(repo_root, plan_path, proposal_path)
    assert result.returncode == 0

    proposal = json.loads(proposal_path.read_text(encoding="utf-8-sig"))
    safety = proposal.get("safety", {})
    assert safety.get("read_only") is True
    assert safety.get("executes_writes") is False
    assert safety.get("marks_products_resolved") is False
    assert safety.get("claims_asset_ids") is False
    assert safety.get("runs_o3de_editor") is False
    assert safety.get("runs_asset_processor") is False
    assert safety.get("spawns_entities") is False
    assert safety.get("publishes_prefabs") is False
