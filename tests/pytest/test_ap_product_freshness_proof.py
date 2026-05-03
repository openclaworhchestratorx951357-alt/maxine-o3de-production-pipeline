import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_ap_product_freshness_proof_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "extract_ap_product_freshness_proof.py"
    assert script_path.exists()


def test_ap_product_freshness_proof_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Extract-MaxineApProductFreshnessProof.ps1"
    assert wrapper_path.exists()


def _inject_timestamp_evidence(path: Path, source_ts: str | None, product_ts: str | None, job_ts: str | None):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    o3de = data.setdefault("o3de", {})

    if source_ts is not None:
        o3de["asset_probe"] = {"modified_utc": source_ts}
    else:
        o3de["asset_probe"] = {}

    o3de["ap_product_file_validation"] = {
        "status": "file_candidates_found",
        "validated_candidates": [
            {
                "candidate_index": 0,
                "path_checks": [
                    {
                        "column": "ProductPath",
                        "normalized_path": "Cache/pc/test.azmodel",
                        "resolved_path": "C:/tmp/cache/pc/test.azmodel",
                        "modified_utc": product_ts if product_ts is not None else "",
                        "exists": True
                    }
                ]
            }
        ]
    }

    o3de["ap_product_candidate_match"] = {
        "status": "candidate_products",
        "candidate_products": [
            {
                "row_values": {
                    "ProductPath": "Cache/pc/test.azmodel"
                }
            }
        ]
    }

    if job_ts is not None:
        o3de["ap_job_state_proof"] = {
            "status": "candidate_job_state_found",
            "candidate_job_rows": [
                {
                    "timestamp_fields": {
                        "CompletedUtc": job_ts
                    },
                    "row_values": {
                        "Status": "Completed"
                    }
                }
            ]
        }
    else:
        o3de["ap_job_state_proof"] = {"candidate_job_rows": []}

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _run_extractor(repo_root: Path, manifest_in: Path, manifest_out: Path):
    script_path = repo_root / "tools" / "asset-resolver" / "extract_ap_product_freshness_proof.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(manifest_in),
        "--output",
        str(manifest_out),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))


def test_ap_product_freshness_supported(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "freshness-input.manifest.json"
    manifest_out = tmp_path / "freshness-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_timestamp_evidence(
        manifest_in,
        source_ts="2026-05-03T10:00:00Z",
        product_ts="2026-05-03T10:05:00Z",
        job_ts="2026-05-03T10:06:00Z",
    )

    result = _run_extractor(repo_root, manifest_in, manifest_out)
    assert result.returncode == 0, f"Extractor failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    output = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    proof = output.get("o3de", {}).get("ap_product_freshness_proof")
    assert isinstance(proof, dict)
    assert proof.get("status") == "candidate_freshness_supported"

    summary = proof.get("summary", {})
    assert summary.get("product_newer_or_equal_source_count", 0) >= 1

    safety = proof.get("safety", {})
    assert safety.get("read_only") is True
    assert safety.get("opened_database") is False
    assert safety.get("modified_database") is False
    assert safety.get("ran_o3de_editor") is False
    assert safety.get("ran_asset_processor") is False
    assert safety.get("authoritative_resolution") is False
    assert safety.get("claimed_asset_ids") is False
    assert safety.get("claimed_products_resolved") is False
    assert safety.get("freshness_proof_is_resolution") is False

    products = output.get("o3de", {}).get("products")
    if isinstance(products, dict):
        assert products.get("resolved") is not True


def test_ap_product_freshness_stale_product(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "freshness-stale-input.manifest.json"
    manifest_out = tmp_path / "freshness-stale-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_timestamp_evidence(
        manifest_in,
        source_ts="2026-05-03T10:05:00Z",
        product_ts="2026-05-03T10:00:00Z",
        job_ts="2026-05-03T10:06:00Z",
    )

    result = _run_extractor(repo_root, manifest_in, manifest_out)
    assert result.returncode == 0

    output = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    proof = output.get("o3de", {}).get("ap_product_freshness_proof")
    assert isinstance(proof, dict)
    assert proof.get("status") == "product_older_than_source"


def test_ap_product_freshness_insufficient_evidence(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    manifest_in = tmp_path / "freshness-insufficient-input.manifest.json"
    manifest_out = tmp_path / "freshness-insufficient-output.manifest.json"

    shutil.copy2(manifest_src, manifest_in)
    _inject_timestamp_evidence(
        manifest_in,
        source_ts=None,
        product_ts=None,
        job_ts=None,
    )

    result = _run_extractor(repo_root, manifest_in, manifest_out)
    assert result.returncode == 0

    output = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    proof = output.get("o3de", {}).get("ap_product_freshness_proof")
    assert isinstance(proof, dict)
    assert proof.get("status") in {
        "insufficient_timestamp_evidence",
        "no_source_timestamp",
        "no_product_file_timestamp",
    }
