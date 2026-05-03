import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_ap_product_identity_proof_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "extract_ap_product_identity_proof.py"
    assert script_path.exists()


def test_ap_product_identity_proof_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Extract-MaxineApProductIdentityProof.ps1"
    assert wrapper_path.exists()


def _inject_identity_evidence(path: Path, include_freshness: bool = True, safety_violation: bool = False) -> None:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    o3de = data.setdefault("o3de", {})

    o3de["asset_resolution"] = {
        "required_products": ["azmodel"],
        "optional_products": ["procprefab"],
        "planned_products": []
    }

    o3de["ap_source_identity_match"] = {
        "status": "candidate_match",
        "source_asset_input": "Assets/Characters/Test/source/test.obj",
        "source_asset_name": "test.obj",
        "source_asset_stem": "test",
        "best_match": {
            "confidence": 1.0,
            "table_name": "Sources",
            "row_index": 0,
            "row_values": {
                "SourceID": 1,
                "SourceUUID": "uuid-1",
                "SourcePath": "Assets/Characters/Test/source/test.obj"
            }
        },
        "summary": {
            "candidate_match_count": 1,
            "best_confidence": 1.0
        },
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
            "source_identity_is_product_resolution": False
        }
    }

    o3de["ap_product_candidate_match"] = {
        "status": "candidate_products",
        "source_match_summary": {
            "has_source_match": True,
            "source_confidence": 1.0,
            "source_match_table": "Sources",
            "source_match_row_index": 0
        },
        "candidate_products": [
            {
                "database_path": "C:/fake/ap.sqlite",
                "table_name": "Products",
                "row_index": 0,
                "confidence": 0.85,
                "candidate_product_types": ["azmodel"],
                "expected_product_match": ["azmodel"],
                "required_product_match": ["azmodel"],
                "optional_product_match": [],
                "planned_product_match": [],
                "link_reason_codes": ["source_identifier_match:SourceID:SourceID"],
                "type_reason_codes": ["type_token_match:azmodel", "extension_match:azmodel"],
                "row_values": {
                    "ProductID": 101,
                    "SourceID": 1,
                    "ProductName": "test.azmodel",
                    "ProductPath": "Cache/pc/test.azmodel"
                }
            }
        ],
        "summary": {
            "product_rows_considered": 1,
            "linked_product_row_count": 1,
            "candidate_product_count": 1,
            "required_product_candidate_count": 1,
            "optional_product_candidate_count": 0,
            "planned_product_candidate_count": 0,
            "missing_required_product_types": [],
            "best_product_confidence": 0.85
        },
        "safety": {
            "read_only": True,
            "opened_database": False,
            "modified_database": False,
            "ran_o3de_editor": False,
            "ran_asset_processor": False,
            "authoritative_resolution": False,
            "claimed_asset_ids": False,
            "claimed_products_resolved": safety_violation,
            "product_candidate_is_resolution": False,
            "published_or_spawned": False
        }
    }

    o3de["ap_product_file_validation"] = {
        "status": "file_candidates_found",
        "summary": {
            "candidate_product_count": 1,
            "candidates_with_existing_file": 1,
            "candidates_without_existing_file": 0,
            "required_product_candidate_count": 1,
            "required_product_existing_file_count": 1,
            "missing_required_product_types": [],
            "required_product_types_without_existing_file": []
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
            "published_or_spawned": False
        }
    }

    o3de["ap_job_state_proof"] = {
        "status": "candidate_job_state_found",
        "summary": {
            "candidate_job_count": 1,
            "success_like_job_count": 1,
            "failure_like_job_count": 0,
            "unknown_job_count": 0
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
            "job_state_is_resolution": False
        }
    }

    o3de["ap_platform_proof"] = {
        "status": "candidate_platform_found",
        "target_platform": "pc",
        "summary": {
            "platform_hint_count": 1,
            "matching_hint_count": 1,
            "mismatching_hint_count": 0
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
            "platform_proof_is_resolution": False
        }
    }

    if include_freshness:
        o3de["ap_product_freshness_proof"] = {
            "status": "candidate_freshness_supported",
            "summary": {
                "source_timestamp_count": 1,
                "product_timestamp_count": 1,
                "job_timestamp_count": 1,
                "product_newer_or_equal_source_count": 1,
                "product_older_than_source_count": 0
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
                "freshness_proof_is_resolution": False
            }
        }
    else:
        o3de.pop("ap_product_freshness_proof", None)

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _run_extractor(repo_root: Path, manifest_in: Path, manifest_out: Path):
    script_path = repo_root / "tools" / "asset-resolver" / "extract_ap_product_identity_proof.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(manifest_in),
        "--output",
        str(manifest_out),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))


def test_ap_product_identity_supported(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "identity-input.manifest.json"
    manifest_out = tmp_path / "identity-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_identity_evidence(manifest_in, include_freshness=True, safety_violation=False)

    result = _run_extractor(repo_root, manifest_in, manifest_out)
    assert result.returncode == 0, f"Extractor failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    output = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    proof = output.get("o3de", {}).get("ap_product_identity_proof")
    assert isinstance(proof, dict)
    assert proof.get("status") == "candidate_product_identity_supported"

    dimensions = proof.get("dimensions", {})
    assert dimensions.get("source_identity_supported", {}).get("passes") is True
    assert dimensions.get("expected_product_type_supported", {}).get("passes") is True
    assert dimensions.get("product_candidate_supported", {}).get("passes") is True
    assert dimensions.get("product_file_supported", {}).get("passes") is True
    assert dimensions.get("job_state_supported", {}).get("passes") is True
    assert dimensions.get("platform_supported", {}).get("passes") is True
    assert dimensions.get("freshness_supported", {}).get("passes") is True

    safety = proof.get("safety", {})
    assert safety.get("read_only") is True
    assert safety.get("opened_database") is False
    assert safety.get("modified_database") is False
    assert safety.get("ran_o3de_editor") is False
    assert safety.get("ran_asset_processor") is False
    assert safety.get("authoritative_resolution") is False
    assert safety.get("claimed_asset_ids") is False
    assert safety.get("claimed_products_resolved") is False
    assert safety.get("product_identity_is_resolution") is False

    products = output.get("o3de", {}).get("products")
    if isinstance(products, dict):
        assert products.get("resolved") is not True


def test_ap_product_identity_incomplete_when_freshness_missing(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "identity-incomplete-input.manifest.json"
    manifest_out = tmp_path / "identity-incomplete-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_identity_evidence(manifest_in, include_freshness=False, safety_violation=False)

    result = _run_extractor(repo_root, manifest_in, manifest_out)
    assert result.returncode == 0

    output = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    proof = output.get("o3de", {}).get("ap_product_identity_proof")
    assert isinstance(proof, dict)
    assert proof.get("status") == "incomplete_product_identity"


def test_ap_product_identity_blocked_safety_violation(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "identity-safety-input.manifest.json"
    manifest_out = tmp_path / "identity-safety-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_identity_evidence(manifest_in, include_freshness=True, safety_violation=True)

    result = _run_extractor(repo_root, manifest_in, manifest_out)
    assert result.returncode == 0

    output = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    proof = output.get("o3de", {}).get("ap_product_identity_proof")
    assert isinstance(proof, dict)
    assert proof.get("status") == "blocked_safety_violation"
