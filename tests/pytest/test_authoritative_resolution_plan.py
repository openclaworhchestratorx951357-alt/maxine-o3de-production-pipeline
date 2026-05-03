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


def _clean_safety_block(extra: dict | None = None) -> dict:
    block = {
        "read_only": True,
        "opened_database": False,
        "modified_database": False,
        "ran_o3de_editor": False,
        "ran_asset_processor": False,
        "authoritative_resolution": False,
        "claimed_asset_ids": False,
        "claimed_products_resolved": False,
        "published_or_spawned": False,
    }
    if extra:
        block.update(extra)
    return block


def _inject_full_proof_stack(manifest_path: Path, include_platform: bool = True, safety_violation: bool = False):
    data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    o3de = data.setdefault("o3de", {})

    o3de["asset_resolution"] = {
        "required_products": ["azmodel"],
        "optional_products": ["procprefab"],
        "planned_products": [],
    }

    o3de["ap_source_identity_match"] = {
        "status": "candidate_match",
        "best_match": {"confidence": 1.0},
        "summary": {"best_confidence": 1.0},
        "safety": _clean_safety_block({"source_identity_is_product_resolution": False}),
    }

    o3de["ap_product_candidate_match"] = {
        "status": "candidate_products",
        "candidate_products": [
            {
                "confidence": 0.95,
                "candidate_product_types": ["azmodel"],
                "expected_product_match": ["azmodel"],
                "required_product_match": ["azmodel"],
                "row_values": {
                    "ProductName": "test.azmodel",
                    "ProductPath": "Cache/pc/test.azmodel",
                },
            }
        ],
        "summary": {
            "candidate_product_count": 1,
            "best_product_confidence": 0.95,
            "missing_required_product_types": [],
        },
        "safety": _clean_safety_block(
            {
                "product_candidate_is_resolution": False,
                "claimed_products_resolved": safety_violation,
            }
        ),
    }

    o3de["ap_product_file_validation"] = {
        "status": "file_candidates_found",
        "summary": {
            "candidates_with_existing_file": 1,
            "required_product_existing_file_count": 1,
            "required_product_types_without_existing_file": [],
        },
        "safety": _clean_safety_block({"file_existence_is_resolution": False}),
    }

    o3de["ap_job_state_proof"] = {
        "status": "candidate_job_state_found",
        "summary": {
            "candidate_job_count": 1,
            "success_like_job_count": 1,
            "failure_like_job_count": 0,
            "unknown_job_count": 0,
        },
        "safety": _clean_safety_block({"job_state_is_resolution": False}),
    }

    if include_platform:
        o3de["ap_platform_proof"] = {
            "status": "candidate_platform_found",
            "target_platform": "pc",
            "summary": {
                "platform_hint_count": 1,
                "matching_hint_count": 1,
                "mismatching_hint_count": 0,
            },
            "safety": _clean_safety_block({"platform_proof_is_resolution": False}),
        }
    else:
        o3de.pop("ap_platform_proof", None)

    o3de["ap_product_freshness_proof"] = {
        "status": "candidate_freshness_supported",
        "summary": {
            "source_timestamp_count": 1,
            "product_timestamp_count": 1,
            "job_timestamp_count": 1,
            "product_newer_or_equal_source_count": 1,
            "product_older_than_source_count": 0,
        },
        "safety": _clean_safety_block({"freshness_proof_is_resolution": False}),
    }

    o3de["ap_product_identity_proof"] = {
        "status": "candidate_product_identity_supported",
        "dimensions": {
            "source_identity_supported": {"passes": True},
            "expected_product_type_supported": {"passes": True},
            "product_candidate_supported": {"passes": True},
            "product_file_supported": {"passes": True},
            "job_state_supported": {"passes": True},
            "platform_supported": {"passes": True},
            "freshness_supported": {"passes": True},
        },
        "identity_candidates": [{"confidence": 0.95}],
        "summary": {
            "dimension_count": 7,
            "passing_dimension_count": 7,
            "all_dimensions_pass": True,
            "identity_candidate_count": 1,
        },
        "safety": _clean_safety_block(
            {
                "product_identity_is_resolution": False,
                "claimed_products_resolved": safety_violation,
            }
        ),
    }

    o3de["ap_resolver_readiness"] = {
        "status": "ready_for_authoritative_resolution_attempt",
        "dimensions": {
            "source_identity_evidence": {"passes": True, "status": "candidate_match"},
            "product_candidate_evidence": {"passes": True, "status": "candidate_products"},
            "file_existence_evidence": {"passes": True, "status": "file_candidates_found"},
            "required_contract_coverage": {"passes": True, "missing_required_product_types": []},
            "safety_compliance": {"passes": True, "violations": []},
        },
        "safety": {
            "read_only": True,
            "opened_database": False,
            "modified_database": False,
            "ran_o3de_editor": False,
            "ran_asset_processor": False,
            "authoritative_resolution": False,
            "claimed_asset_ids": False,
            "claimed_products_resolved": False,
            "readiness_is_resolution": False,
            "published_or_spawned": False,
        },
    }

    data.setdefault("o3de", {}).setdefault("products", {})["resolved"] = False
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


def test_authoritative_plan_full_proof_stack_ready(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "authoritative-plan-ready-input.manifest.json"
    plan_out = tmp_path / "authoritative-plan-ready-output.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_full_proof_stack(manifest_in, include_platform=True, safety_violation=False)

    result = _run_planner(repo_root, manifest_in, plan_out)
    assert result.returncode == 0, f"Planner failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    plan = json.loads(plan_out.read_text(encoding="utf-8-sig"))
    assert plan.get("status") == "dry_run_ready"

    proofs = plan.get("required_proofs", [])
    assert isinstance(proofs, list)
    proof_ids = {str(p.get("id")) for p in proofs if isinstance(p, dict)}
    assert REQUIRED_PROOF_IDS.issubset(proof_ids)

    assert plan.get("missing_proofs") == []

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


def test_authoritative_plan_missing_platform_proof_is_incomplete(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "authoritative-plan-platform-missing-input.manifest.json"
    plan_out = tmp_path / "authoritative-plan-platform-missing-output.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_full_proof_stack(manifest_in, include_platform=False, safety_violation=False)

    result = _run_planner(repo_root, manifest_in, plan_out)
    assert result.returncode == 0

    plan = json.loads(plan_out.read_text(encoding="utf-8-sig"))
    assert plan.get("status") == "dry_run_incomplete"
    assert "platform_proof" in set(plan.get("missing_proofs", []))


def test_authoritative_plan_safety_violation_is_blocked(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "authoritative-plan-safety-input.manifest.json"
    plan_out = tmp_path / "authoritative-plan-safety-output.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_full_proof_stack(manifest_in, include_platform=True, safety_violation=True)

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
