import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_ap_job_state_proof_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "extract_ap_job_state_proof.py"
    assert script_path.exists()


def test_ap_job_state_proof_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Extract-MaxineApJobStateProof.ps1"
    assert wrapper_path.exists()


def _inject_job_state_evidence_manifest(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    o3de = data.setdefault("o3de", {})

    o3de["ap_row_mapping"] = {
        "mapping_version": "ap-row-mapping-test",
        "databases": [
            {
                "path": "C:/fake/ap.sqlite",
                "opened_read_only": True,
                "tables": [
                    {
                        "name": "Sources",
                        "role": "source",
                        "sampled_rows": [
                            {
                                "SourceID": 1,
                                "SourceUUID": "uuid-1",
                                "SourcePath": "Assets/Characters/Test/source/test.obj"
                            }
                        ]
                    },
                    {
                        "name": "Products",
                        "role": "product",
                        "sampled_rows": [
                            {
                                "ProductID": 101,
                                "SourceID": 1,
                                "ProductPath": "Cache/pc/test.azmodel",
                                "ProductName": "test.azmodel"
                            }
                        ]
                    },
                    {
                        "name": "Jobs",
                        "role": "job",
                        "sampled_rows": [
                            {
                                "JobID": 5001,
                                "SourceID": 1,
                                "ProductID": 101,
                                "Status": "Completed",
                                "Result": "Success"
                            }
                        ]
                    }
                ]
            }
        ]
    }

    o3de["ap_source_identity_match"] = {
        "status": "candidate_match",
        "best_match": {
            "confidence": 1.0,
            "table_name": "Sources",
            "row_index": 0,
            "row_values": {
                "SourceID": 1,
                "SourceUUID": "uuid-1",
                "SourcePath": "Assets/Characters/Test/source/test.obj"
            }
        }
    }

    o3de["ap_product_candidate_match"] = {
        "status": "candidate_products",
        "candidate_products": [
            {
                "database_path": "C:/fake/ap.sqlite",
                "table_name": "Products",
                "row_index": 0,
                "candidate_product_types": [
                    "azmodel"
                ],
                "row_values": {
                    "ProductID": 101,
                    "SourceID": 1,
                    "ProductPath": "Cache/pc/test.azmodel",
                    "ProductName": "test.azmodel"
                }
            }
        ]
    }

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_ap_job_state_proof_extraction_happy_path(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "extract_ap_job_state_proof.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "ap-job-state-input.manifest.json"
    manifest_out = tmp_path / "ap-job-state-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_job_state_evidence_manifest(manifest_in)

    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(manifest_in),
        "--output",
        str(manifest_out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    assert result.returncode == 0, f"Extractor failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    output = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    proof = output.get("o3de", {}).get("ap_job_state_proof")
    assert isinstance(proof, dict)
    assert proof.get("status") == "candidate_job_state_found"

    summary = proof.get("summary", {})
    assert summary.get("success_like_job_count", 0) >= 1

    safety = proof.get("safety", {})
    assert safety.get("read_only") is True
    assert safety.get("opened_database") is False
    assert safety.get("modified_database") is False
    assert safety.get("ran_o3de_editor") is False
    assert safety.get("ran_asset_processor") is False
    assert safety.get("authoritative_resolution") is False
    assert safety.get("claimed_asset_ids") is False
    assert safety.get("claimed_products_resolved") is False
    assert safety.get("job_state_is_resolution") is False

    products = output.get("o3de", {}).get("products")
    if isinstance(products, dict):
        assert products.get("resolved") is not True
