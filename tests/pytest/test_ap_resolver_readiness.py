import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_resolver_readiness_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "evaluate_ap_resolver_readiness.py"
    assert script_path.exists()


def test_resolver_readiness_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Evaluate-MaxineApResolverReadiness.ps1"
    assert wrapper_path.exists()


def _inject_readiness_blocks(manifest_path: Path):
    data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    o3de = data.setdefault("o3de", {})
    o3de["asset_resolution"] = {
        "required_products": ["azmodel"],
        "optional_products": [],
        "planned_products": [],
    }
    o3de["ap_source_identity_match"] = {
        "status": "candidate_match",
        "best_match": {"confidence": 1.0},
        "safety": {
            "read_only": True,
            "opened_database": False,
            "modified_database": False,
            "ran_o3de_editor": False,
            "ran_asset_processor": False,
            "authoritative_resolution": False,
            "claimed_source_uuid": False,
            "claimed_asset_ids": False,
            "claimed_products_resolved": False,
            "source_identity_is_product_resolution": False,
        },
    }
    o3de["ap_product_candidate_match"] = {
        "status": "candidate_products",
        "summary": {
            "candidate_product_count": 1,
            "best_product_confidence": 0.70,
            "missing_required_product_types": [],
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
            "product_candidate_is_resolution": False,
            "published_or_spawned": False,
        },
    }
    o3de["ap_product_file_validation"] = {
        "status": "file_candidates_found",
        "summary": {
            "candidates_with_existing_file": 1,
            "required_product_existing_file_count": 1,
            "required_product_types_without_existing_file": [],
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
            "file_existence_is_resolution": False,
            "published_or_spawned": False,
        },
    }
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _run_readiness(script_path: Path, repo_root: Path, manifest_in: Path, manifest_out: Path):
    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(manifest_in),
        "--output",
        str(manifest_out),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))


def test_resolver_readiness_ready_path(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "evaluate_ap_resolver_readiness.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "readiness-input.manifest.json"
    manifest_out = tmp_path / "readiness-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_readiness_blocks(manifest_in)
    result = _run_readiness(script_path, repo_root, manifest_in, manifest_out)
    assert result.returncode == 0, f"Readiness failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    data = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    readiness = data.get("o3de", {}).get("ap_resolver_readiness")
    assert isinstance(readiness, dict)
    assert readiness.get("status") == "ready_for_authoritative_resolution_attempt"

    dimensions = readiness.get("dimensions", {})
    assert dimensions.get("source_identity_evidence", {}).get("passes") is True
    assert dimensions.get("product_candidate_evidence", {}).get("passes") is True
    assert dimensions.get("file_existence_evidence", {}).get("passes") is True
    assert dimensions.get("required_contract_coverage", {}).get("passes") is True
    assert dimensions.get("safety_compliance", {}).get("passes") is True

    safety = readiness.get("safety", {})
    assert safety.get("readiness_is_resolution") is False
    assert safety.get("claimed_products_resolved") is False
    assert safety.get("published_or_spawned") is False

    products = data.get("o3de", {}).get("products")
    if isinstance(products, dict):
        assert products.get("resolved") is not True


def test_resolver_readiness_blocked_missing_source_identity(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "evaluate_ap_resolver_readiness.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "source-missing-input.manifest.json"
    manifest_out = tmp_path / "source-missing-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_readiness_blocks(manifest_in)
    data = json.loads(manifest_in.read_text(encoding="utf-8-sig"))
    data["o3de"]["ap_source_identity_match"]["status"] = "no_match"
    data["o3de"]["ap_source_identity_match"]["best_match"]["confidence"] = 0.20
    manifest_in.write_text(json.dumps(data, indent=2), encoding="utf-8")

    result = _run_readiness(script_path, repo_root, manifest_in, manifest_out)
    assert result.returncode == 0
    output = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    readiness = output.get("o3de", {}).get("ap_resolver_readiness", {})
    assert readiness.get("status") == "blocked_missing_source_identity"


def test_resolver_readiness_blocked_missing_product_candidates(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "evaluate_ap_resolver_readiness.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "product-missing-input.manifest.json"
    manifest_out = tmp_path / "product-missing-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_readiness_blocks(manifest_in)
    data = json.loads(manifest_in.read_text(encoding="utf-8-sig"))
    data["o3de"]["ap_product_candidate_match"]["status"] = "no_source_match"
    data["o3de"]["ap_product_candidate_match"]["summary"]["candidate_product_count"] = 0
    manifest_in.write_text(json.dumps(data, indent=2), encoding="utf-8")

    result = _run_readiness(script_path, repo_root, manifest_in, manifest_out)
    assert result.returncode == 0
    output = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    readiness = output.get("o3de", {}).get("ap_resolver_readiness", {})
    assert readiness.get("status") == "blocked_missing_product_candidates"


def test_resolver_readiness_blocked_missing_required_product_files(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "evaluate_ap_resolver_readiness.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "required-file-missing-input.manifest.json"
    manifest_out = tmp_path / "required-file-missing-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_readiness_blocks(manifest_in)
    data = json.loads(manifest_in.read_text(encoding="utf-8-sig"))
    data["o3de"]["ap_product_file_validation"]["summary"]["required_product_types_without_existing_file"] = ["azmodel"]
    manifest_in.write_text(json.dumps(data, indent=2), encoding="utf-8")

    result = _run_readiness(script_path, repo_root, manifest_in, manifest_out)
    assert result.returncode == 0
    output = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    readiness = output.get("o3de", {}).get("ap_resolver_readiness", {})
    assert readiness.get("status") == "blocked_missing_required_product_files"


def test_resolver_readiness_blocked_safety_violation(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "evaluate_ap_resolver_readiness.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "safety-blocked-input.manifest.json"
    manifest_out = tmp_path / "safety-blocked-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_readiness_blocks(manifest_in)
    data = json.loads(manifest_in.read_text(encoding="utf-8-sig"))
    data["o3de"]["ap_product_candidate_match"]["safety"]["claimed_products_resolved"] = True
    manifest_in.write_text(json.dumps(data, indent=2), encoding="utf-8")

    result = _run_readiness(script_path, repo_root, manifest_in, manifest_out)
    assert result.returncode == 0
    output = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    readiness = output.get("o3de", {}).get("ap_resolver_readiness", {})
    assert readiness.get("status") == "blocked_safety_violation"
