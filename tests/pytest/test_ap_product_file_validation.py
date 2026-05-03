import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_product_file_validation_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "validate_ap_product_files.py"
    assert script_path.exists()


def test_product_file_validation_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Validate-MaxineApProductFiles.ps1"
    assert wrapper_path.exists()


def _inject_product_candidate_match(manifest_path: Path, product_path: str):
    data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    o3de = data.setdefault("o3de", {})
    o3de["ap_product_candidate_match"] = {
        "matching_version": "ap-product-candidate-match-test",
        "status": "candidate_products",
        "expected_contract": {
            "required_products": ["azmodel"],
            "optional_products": [],
            "planned_products": [],
        },
        "candidate_products": [
            {
                "candidate_product_types": ["azmodel"],
                "expected_product_match": ["azmodel"],
                "required_product_match": ["azmodel"],
                "link_reason_codes": ["source_identifier_match:SourceID:SourceID"],
                "row_values": {
                    "ProductPath": product_path,
                    "ProductName": "test.azmodel",
                },
            }
        ],
    }
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_product_file_validation_found(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "validate_ap_product_files.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "input.manifest.json"
    manifest_out = tmp_path / "output.manifest.json"
    shutil.copy2(manifest_src, manifest_in)
    _inject_product_candidate_match(manifest_in, "pc/test.azmodel")

    cache_root = tmp_path / "cache"
    product_file = cache_root / "pc" / "test.azmodel"
    product_file.parent.mkdir(parents=True, exist_ok=True)
    product_file.write_text("dummy", encoding="utf-8")

    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(manifest_in),
        "--cache-root",
        str(cache_root),
        "--output",
        str(manifest_out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    assert result.returncode == 0, f"Validation failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    data = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    val = data.get("o3de", {}).get("ap_product_file_validation")
    assert isinstance(val, dict)
    assert val.get("status") == "file_candidates_found"
    summary = val.get("summary", {})
    assert summary.get("candidates_with_existing_file", 0) >= 1
    assert summary.get("required_product_existing_file_count", 0) >= 1

    safety = val.get("safety", {})
    assert safety.get("read_only") is True
    assert safety.get("opened_database") is False
    assert safety.get("modified_database") is False
    assert safety.get("authoritative_resolution") is False
    assert safety.get("claimed_asset_ids") is False
    assert safety.get("claimed_products_resolved") is False
    assert safety.get("file_existence_is_resolution") is False
    assert safety.get("published_or_spawned") is False

    products = data.get("o3de", {}).get("products")
    if isinstance(products, dict):
        assert products.get("resolved") is not True


def test_product_file_validation_no_existing_files(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "validate_ap_product_files.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "input-no-file.manifest.json"
    manifest_out = tmp_path / "output-no-file.manifest.json"
    shutil.copy2(manifest_src, manifest_in)
    _inject_product_candidate_match(manifest_in, "pc/missing.azmodel")

    cache_root = tmp_path / "cache"
    cache_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(manifest_in),
        "--cache-root",
        str(cache_root),
        "--output",
        str(manifest_out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    assert result.returncode == 0, f"No-file path should pass:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    data = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    val = data.get("o3de", {}).get("ap_product_file_validation")
    assert isinstance(val, dict)
    assert val.get("status") == "no_existing_files"


def test_product_file_validation_rejects_unsafe_paths(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "validate_ap_product_files.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "input-unsafe.manifest.json"
    manifest_out = tmp_path / "output-unsafe.manifest.json"
    shutil.copy2(manifest_src, manifest_in)
    _inject_product_candidate_match(manifest_in, "../outside.azmodel")

    cache_root = tmp_path / "cache"
    cache_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(manifest_in),
        "--cache-root",
        str(cache_root),
        "--output",
        str(manifest_out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    assert result.returncode == 0, f"Unsafe-path path should still pass with rejection recorded:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    data = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    val = data.get("o3de", {}).get("ap_product_file_validation")
    assert isinstance(val, dict)
    summary = val.get("summary", {})
    assert summary.get("rejected_path_count", 0) >= 1
