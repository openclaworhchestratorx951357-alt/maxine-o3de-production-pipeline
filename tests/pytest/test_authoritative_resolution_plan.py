import json
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_PROOF_IDS = {
    "source_identity_proof",
    "expected_product_type_proof",
    "product_file_existence_proof",
    "asset_processor_job_success_proof",
    "platform_proof",
    "product_freshness_proof",
    "product_identity_proof",
    "safety_compliance_proof",
}


def test_authoritative_planner_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "plan_authoritative_resolution.py"
    assert script_path.exists()


def test_authoritative_planner_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Plan-MaxineAuthoritativeResolution.ps1"
    assert wrapper_path.exists()


def test_authoritative_plan_schema_exists():
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "schemas" / "maxine_authoritative_resolver_plan.schema.json"
    assert schema_path.exists()


def _inject_readiness_for_dry_run(manifest_path: Path, readiness_status: str = "ready_for_authoritative_resolution_attempt"):
    data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    o3de = data.setdefault("o3de", {})
    o3de["asset_resolution"] = {
        "required_products": ["azmodel"],
        "optional_products": [],
        "planned_products": [],
    }
    o3de["ap_source_identity_match"] = {"status": "candidate_match"}
    o3de["ap_product_candidate_match"] = {"status": "candidate_products"}
    o3de["ap_product_file_validation"] = {"status": "file_candidates_found"}
    o3de["ap_resolver_readiness"] = {
        "status": readiness_status,
        "dimensions": {
            "source_identity_evidence": {"passes": True, "status": "candidate_match"},
            "product_candidate_evidence": {"passes": True, "status": "candidate_products"},
            "file_existence_evidence": {"passes": True, "status": "file_candidates_found"},
            "required_contract_coverage": {"passes": True, "missing_required_product_types": []},
            "safety_compliance": {"passes": True, "violations": []},
        },
    }
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _run_planner(repo_root: Path, manifest_path: Path, output_path: Path):
    script_path = repo_root / "tools" / "asset-resolver" / "plan_authoritative_resolution.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(manifest_path),
        "--output",
        str(output_path),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))


def test_authoritative_plan_ready_evidence_is_still_incomplete(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "authoritative-plan-input.manifest.json"
    plan_out = tmp_path / "authoritative-plan-output.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_readiness_for_dry_run(manifest_in)

    result = _run_planner(repo_root, manifest_in, plan_out)
    assert result.returncode == 0, f"Planner failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    plan = json.loads(plan_out.read_text(encoding="utf-8-sig"))
    assert plan.get("status") == "dry_run_incomplete"

    proofs = plan.get("required_proofs", [])
    assert isinstance(proofs, list)
    proof_ids = {str(p.get("id")) for p in proofs if isinstance(p, dict)}
    assert REQUIRED_PROOF_IDS.issubset(proof_ids)

    missing = set(plan.get("missing_proofs", []))
    assert "asset_processor_job_success_proof" in missing
    assert "platform_proof" in missing
    assert "product_freshness_proof" in missing
    assert "product_identity_proof" in missing

    safety = plan.get("safety", {})
    assert safety.get("read_only") is True
    assert safety.get("writes_resolved_products") is False
    assert safety.get("runs_o3de_editor") is False
    assert safety.get("runs_asset_processor") is False
    assert safety.get("opens_database") is False
    assert safety.get("modifies_database") is False
    assert safety.get("spawns_entities") is False
    assert safety.get("publishes_prefabs") is False
    assert safety.get("claims_asset_ids") is False


def test_authoritative_plan_blocked_when_safety_blocked(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "authoritative-plan-blocked-input.manifest.json"
    plan_out = tmp_path / "authoritative-plan-blocked-output.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_readiness_for_dry_run(manifest_in, readiness_status="blocked_safety_violation")

    result = _run_planner(repo_root, manifest_in, plan_out)
    assert result.returncode == 0

    plan = json.loads(plan_out.read_text(encoding="utf-8-sig"))
    assert plan.get("status") == "dry_run_blocked"


def test_authoritative_example_plan_has_required_fields():
    repo_root = Path(__file__).resolve().parents[2]
    example_path = repo_root / "examples" / "manifests" / "example-authoritative-resolution-plan.json"
    data = json.loads(example_path.read_text(encoding="utf-8-sig"))

    required_top = [
        "schema_version",
        "plan_id",
        "status",
        "source_manifest",
        "required_proofs",
        "available_evidence",
        "missing_proofs",
        "proposed_actions",
        "forbidden_actions",
        "safety",
    ]
    for field in required_top:
        assert field in data
