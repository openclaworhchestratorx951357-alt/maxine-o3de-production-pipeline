import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_ap_platform_proof_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "extract_ap_platform_proof.py"
    assert script_path.exists()


def test_ap_platform_proof_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Extract-MaxineApPlatformProof.ps1"
    assert wrapper_path.exists()


def _inject_platform_evidence(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    o3de = data.setdefault("o3de", {})

    o3de["ap_product_candidate_match"] = {
        "status": "candidate_products",
        "candidate_products": [
            {
                "database_path": "C:/fake/ap.sqlite",
                "table_name": "Products",
                "row_index": 0,
                "candidate_product_types": ["azmodel"],
                "row_values": {
                    "ProductID": 101,
                    "SourceID": 1,
                    "ProductPath": "Cache/pc/test.azmodel",
                    "ProductName": "test.azmodel"
                }
            }
        ]
    }

    o3de["ap_product_file_validation"] = {
        "status": "file_candidates_found",
        "validated_candidates": [
            {
                "candidate_index": 0,
                "path_checks": [
                    {
                        "column": "ProductPath",
                        "input_path": "Cache/pc/test.azmodel",
                        "normalized_path": "Cache/pc/test.azmodel",
                        "resolved_path": "C:/tmp/cache/pc/test.azmodel",
                        "exists": True
                    }
                ]
            }
        ]
    }

    o3de["ap_job_state_proof"] = {
        "status": "candidate_job_state_found",
        "candidate_job_rows": [
            {
                "database_path": "C:/fake/ap.sqlite",
                "table_name": "Jobs",
                "row_index": 0,
                "platform_fields": {
                    "Platform": "pc"
                },
                "row_values": {
                    "Status": "Completed",
                    "Platform": "pc"
                }
            }
        ]
    }

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _run_extractor(repo_root: Path, manifest_in: Path, manifest_out: Path, target_platform: str):
    script_path = repo_root / "tools" / "asset-resolver" / "extract_ap_platform_proof.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(manifest_in),
        "--output",
        str(manifest_out),
        "--target-platform",
        target_platform,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))


def test_ap_platform_proof_matching_pc(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "platform-input.manifest.json"
    manifest_out = tmp_path / "platform-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_platform_evidence(manifest_in)

    result = _run_extractor(repo_root, manifest_in, manifest_out, "pc")
    assert result.returncode == 0, f"Extractor failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    output = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    proof = output.get("o3de", {}).get("ap_platform_proof")
    assert isinstance(proof, dict)
    assert proof.get("status") == "candidate_platform_found"

    summary = proof.get("summary", {})
    assert summary.get("matching_hint_count", 0) >= 1

    safety = proof.get("safety", {})
    assert safety.get("read_only") is True
    assert safety.get("opened_database") is False
    assert safety.get("modified_database") is False
    assert safety.get("ran_o3de_editor") is False
    assert safety.get("ran_asset_processor") is False
    assert safety.get("authoritative_resolution") is False
    assert safety.get("claimed_asset_ids") is False
    assert safety.get("claimed_products_resolved") is False
    assert safety.get("platform_proof_is_resolution") is False

    products = output.get("o3de", {}).get("products")
    if isinstance(products, dict):
        assert products.get("resolved") is not True


def test_ap_platform_proof_mismatch_android(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "platform-mismatch-input.manifest.json"
    manifest_out = tmp_path / "platform-mismatch-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_platform_evidence(manifest_in)

    result = _run_extractor(repo_root, manifest_in, manifest_out, "android")
    assert result.returncode == 0, f"Extractor failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    output = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    proof = output.get("o3de", {}).get("ap_platform_proof")
    assert isinstance(proof, dict)
    assert proof.get("status") in {"platform_mismatch", "candidate_platform_found"}

    summary = proof.get("summary", {})
    assert summary.get("mismatching_hint_count", 0) >= 1
