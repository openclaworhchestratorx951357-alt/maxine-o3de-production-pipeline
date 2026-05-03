import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_source_identity_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "match_ap_source_identity.py"
    assert script_path.exists()


def test_source_identity_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Match-MaxineApSourceIdentity.ps1"
    assert wrapper_path.exists()


def _inject_row_mapping(manifest_path: Path) -> None:
    data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    o3de = data.setdefault("o3de", {})
    o3de["ap_row_mapping"] = {
        "mapping_version": "ap-row-mapping-test",
        "status": "mapped_candidate_rows",
        "databases": [
            {
                "path": "C:/fake/ap.sqlite",
                "opened_read_only": True,
                "candidate_tables": {
                    "source_tables": ["Sources"],
                    "product_tables": ["Products"],
                    "job_tables": ["Jobs"],
                    "dependency_tables": ["SourceDependency"],
                },
                "tables": [
                    {
                        "name": "Sources",
                        "role": "source",
                        "columns": [
                            {"name": "SourceUUID"},
                            {"name": "SourceName"},
                            {"name": "SourcePath"},
                        ],
                        "sampled_rows": [
                            {
                                "SourceUUID": "uuid-1",
                                "SourceName": "test.obj",
                                "SourcePath": "Assets/Characters/Test/source/test.obj",
                            }
                        ],
                    },
                    {
                        "name": "Products",
                        "role": "product",
                        "columns": [
                            {"name": "ProductPath"},
                        ],
                        "sampled_rows": [
                            {
                                "ProductPath": "Cache/pc/test.azmodel",
                            }
                        ],
                    },
                ],
            }
        ],
    }
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_source_identity_candidate_match(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "match_ap_source_identity.py"
    src_manifest = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    in_manifest = tmp_path / "input.manifest.json"
    out_manifest = tmp_path / "output.manifest.json"
    shutil.copy2(src_manifest, in_manifest)
    _inject_row_mapping(in_manifest)

    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(in_manifest),
        "--source-asset",
        "Assets/Characters/Test/source/test.obj",
        "--output",
        str(out_manifest),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    assert result.returncode == 0, f"Matcher failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    data = json.loads(out_manifest.read_text(encoding="utf-8-sig"))
    match = data.get("o3de", {}).get("ap_source_identity_match")
    assert isinstance(match, dict), "o3de.ap_source_identity_match missing"
    assert match.get("status") == "candidate_match"

    summary = match.get("summary", {})
    assert summary.get("candidate_match_count", 0) >= 1
    assert summary.get("best_confidence", 0) >= 0.70

    best = match.get("best_match")
    assert isinstance(best, dict)
    reason_codes = best.get("reason_codes", [])
    assert "exact_normalized_path_match" in reason_codes or "path_suffix_match" in reason_codes

    safety = match.get("safety", {})
    assert safety.get("read_only") is True
    assert safety.get("opened_database") is False
    assert safety.get("modified_database") is False
    assert safety.get("authoritative_resolution") is False
    assert safety.get("claimed_source_uuid") is False
    assert safety.get("claimed_asset_ids") is False
    assert safety.get("claimed_products_resolved") is False
    assert safety.get("source_identity_is_product_resolution") is False

    products = data.get("o3de", {}).get("products")
    if isinstance(products, dict):
        assert products.get("resolved") is not True


def test_source_identity_no_match_returns_zero(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "match_ap_source_identity.py"
    src_manifest = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    in_manifest = tmp_path / "input-no-match.manifest.json"
    out_manifest = tmp_path / "output-no-match.manifest.json"
    shutil.copy2(src_manifest, in_manifest)
    _inject_row_mapping(in_manifest)

    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(in_manifest),
        "--source-asset",
        "Assets/Characters/Other/source/nope.obj",
        "--output",
        str(out_manifest),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    assert result.returncode == 0, f"Matcher no-match path failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    data = json.loads(out_manifest.read_text(encoding="utf-8-sig"))
    match = data.get("o3de", {}).get("ap_source_identity_match")
    assert isinstance(match, dict), "o3de.ap_source_identity_match missing on no-match path"
    assert match.get("status") == "no_match"
