import json
import shutil
import subprocess
import sys
from pathlib import Path


SUPPORTED_LANES = {
    "draft_mesh",
    "text_mesh",
    "photo_rig_prep",
    "text_full_rig",
    "external_rig_import",
    "release_character",
}


def test_product_contracts_have_supported_lanes():
    repo_root = Path(__file__).resolve().parents[2]
    contracts_path = repo_root / "tools" / "asset-resolver" / "product_contracts.json"
    data = json.loads(contracts_path.read_text(encoding="utf-8"))
    for lane in SUPPORTED_LANES:
        assert lane in data, f"Missing lane in product contracts: {lane}"


def test_product_contract_shape():
    repo_root = Path(__file__).resolve().parents[2]
    contracts_path = repo_root / "tools" / "asset-resolver" / "product_contracts.json"
    data = json.loads(contracts_path.read_text(encoding="utf-8"))
    for lane in SUPPORTED_LANES:
        lane_data = data[lane]
        assert "required_products" in lane_data
        assert "optional_products" in lane_data
        assert "planned_products" in lane_data
        assert "notes" in lane_data


def test_resolver_updates_manifest_contract(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    resolver = repo_root / "tools" / "asset-resolver" / "resolve_asset_contract.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "input.manifest.json"
    manifest_out = tmp_path / "output.manifest.json"
    shutil.copy2(manifest_src, manifest_in)

    cmd = [
        sys.executable,
        str(resolver),
        "--manifest",
        str(manifest_in),
        "--source-asset",
        "Assets/Characters/Test/source/test.obj",
        "--lane",
        "draft_mesh",
        "--output",
        str(manifest_out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    assert result.returncode == 0, f"Resolver failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    data = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    ar = data.get("o3de", {}).get("asset_resolution")
    assert isinstance(ar, dict), "o3de.asset_resolution missing"
    assert ar.get("cache_guessing_used") is False
    assert ar.get("real_o3de_query_used") is False
    assert "azmodel" in ar.get("required_products", [])
    assert ar.get("status") in {"planned", "unresolved"}
