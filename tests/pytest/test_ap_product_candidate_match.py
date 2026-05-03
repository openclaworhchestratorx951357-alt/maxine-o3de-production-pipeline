import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_product_candidate_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "match_ap_product_candidates.py"
    assert script_path.exists()


def test_product_candidate_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Match-MaxineApProductCandidates.ps1"
    assert wrapper_path.exists()


def _inject_manifest_for_candidate_product_test(manifest_path: Path, required_products):
    data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    o3de = data.setdefault("o3de", {})
    o3de["asset_resolution"] = {
        "required_products": list(required_products),
        "optional_products": ["procprefab", "azmaterial"],
        "planned_products": [],
    }
    o3de["ap_row_mapping"] = {
        "mapping_version": "ap-row-mapping-test",
        "databases": [
            {
                "path": "C:/fake/ap.sqlite",
                "opened_read_only": True,
                "candidate_tables": {
                    "source_tables": ["Sources"],
                    "product_tables": ["Products"],
                },
                "tables": [
                    {
                        "name": "Sources",
                        "role": "source",
                        "sampled_rows": [
                            {
                                "SourceID": 1,
                                "SourceUUID": "uuid-1",
                                "SourcePath": "Assets/Characters/Test/source/test.obj",
                            }
                        ],
                    },
                    {
                        "name": "Products",
                        "role": "product",
                        "sampled_rows": [
                            {
                                "ProductID": 101,
                                "SourceID": 1,
                                "ProductName": "test.azmodel",
                                "ProductPath": "Cache/pc/test.azmodel",
                            }
                        ],
                    },
                ],
            }
        ],
    }
    o3de["ap_source_identity_match"] = {
        "matching_version": "ap-source-identity-match-test",
        "status": "candidate_match",
        "source_asset_name": "test.obj",
        "source_asset_stem": "test",
        "best_match": {
            "confidence": 1.0,
            "table_name": "Sources",
            "row_index": 0,
            "row_values": {
                "SourceID": 1,
                "SourceUUID": "uuid-1",
                "SourcePath": "Assets/Characters/Test/source/test.obj",
            },
        },
    }
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_product_candidate_match_happy_path(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "match_ap_product_candidates.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "candidate-input.manifest.json"
    manifest_out = tmp_path / "candidate-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_manifest_for_candidate_product_test(manifest_in, required_products=["azmodel"])

    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(manifest_in),
        "--output",
        str(manifest_out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    assert result.returncode == 0, f"Candidate matching failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    data = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    match = data.get("o3de", {}).get("ap_product_candidate_match")
    assert isinstance(match, dict), "o3de.ap_product_candidate_match missing"
    assert match.get("status") == "candidate_products"

    summary = match.get("summary", {})
    assert summary.get("candidate_product_count", 0) >= 1
    assert summary.get("required_product_candidate_count", 0) >= 1
    assert summary.get("missing_required_product_types", []) == []
    assert summary.get("best_product_confidence", 0) >= 0.70

    candidates = match.get("candidate_products", [])
    assert isinstance(candidates, list) and len(candidates) >= 1
    first_types = candidates[0].get("candidate_product_types", [])
    assert "azmodel" in first_types

    safety = match.get("safety", {})
    assert safety.get("read_only") is True
    assert safety.get("opened_database") is False
    assert safety.get("modified_database") is False
    assert safety.get("authoritative_resolution") is False
    assert safety.get("claimed_asset_ids") is False
    assert safety.get("claimed_products_resolved") is False
    assert safety.get("product_candidate_is_resolution") is False
    assert safety.get("published_or_spawned") is False

    products = data.get("o3de", {}).get("products")
    if isinstance(products, dict):
        assert products.get("resolved") is not True


def test_product_candidate_no_source_match_exit_zero(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "match_ap_product_candidates.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "candidate-nosource-input.manifest.json"
    manifest_out = tmp_path / "candidate-nosource-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_manifest_for_candidate_product_test(manifest_in, required_products=["azmodel"])
    data = json.loads(manifest_in.read_text(encoding="utf-8-sig"))
    data["o3de"]["ap_source_identity_match"]["best_match"]["confidence"] = 0.20
    manifest_in.write_text(json.dumps(data, indent=2), encoding="utf-8")

    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(manifest_in),
        "--output",
        str(manifest_out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    assert result.returncode == 0, f"No-source path should succeed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    out_data = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    match = out_data.get("o3de", {}).get("ap_product_candidate_match")
    assert isinstance(match, dict)
    assert match.get("status") == "no_source_match"


def test_product_candidate_missing_required_type(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "match_ap_product_candidates.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "candidate-missingreq-input.manifest.json"
    manifest_out = tmp_path / "candidate-missingreq-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_manifest_for_candidate_product_test(manifest_in, required_products=["actor"])

    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(manifest_in),
        "--output",
        str(manifest_out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    assert result.returncode == 0, f"Missing-required path failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    data = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    match = data.get("o3de", {}).get("ap_product_candidate_match")
    assert isinstance(match, dict)
    assert match.get("status") == "candidate_products"
    missing = match.get("summary", {}).get("missing_required_product_types", [])
    assert "actor" in missing
