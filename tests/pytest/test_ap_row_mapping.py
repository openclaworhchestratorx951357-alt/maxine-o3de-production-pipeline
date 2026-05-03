import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_row_mapping_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "map_ap_source_product_rows.py"
    assert script_path.exists()


def test_row_mapping_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Map-MaxineApRows.ps1"
    assert wrapper_path.exists()


def test_row_mapping_reads_candidate_rows(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "map_ap_source_product_rows.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"

    db_path = tmp_path / "ap_row_mapping_test.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE Sources (SourceID INTEGER PRIMARY KEY, SourceUUID TEXT, SourceName TEXT, SourcePath TEXT)"
    )
    conn.execute(
        "CREATE TABLE Products (ProductID INTEGER PRIMARY KEY, SourceID INTEGER, ProductSubID INTEGER, ProductName TEXT, ProductPath TEXT)"
    )
    conn.execute("CREATE TABLE Jobs (JobID INTEGER PRIMARY KEY, SourceID INTEGER, Status TEXT)")
    conn.execute("CREATE TABLE SourceDependency (SourceID INTEGER, DependsOnSource INTEGER)")
    conn.execute(
        "INSERT INTO Sources (SourceUUID, SourceName, SourcePath) VALUES ('uuid-1', 'TestSource', 'Assets/Characters/Test/source/test.obj')"
    )
    conn.execute(
        "INSERT INTO Products (SourceID, ProductSubID, ProductName, ProductPath) VALUES (1, 101, 'TestProduct', 'Cache/pc/test.azmodel')"
    )
    conn.execute("INSERT INTO Jobs (SourceID, Status) VALUES (1, 'queued')")
    conn.execute("INSERT INTO SourceDependency (SourceID, DependsOnSource) VALUES (1, 1)")
    conn.commit()
    conn.close()

    manifest_in = tmp_path / "input.manifest.json"
    manifest_out = tmp_path / "output.manifest.json"
    shutil.copy2(manifest_src, manifest_in)

    cmd = [
        sys.executable,
        str(script_path),
        "--manifest",
        str(manifest_in),
        "--database",
        str(db_path),
        "--source-asset",
        "Assets/Characters/Test/source/test.obj",
        "--output",
        str(manifest_out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    assert result.returncode == 0, f"Row mapping failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    data = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    mapping = data.get("o3de", {}).get("ap_row_mapping")
    assert isinstance(mapping, dict), "o3de.ap_row_mapping missing"

    summary = mapping.get("summary", {})
    assert summary.get("opened_database_count") == 1
    assert summary.get("source_table_count", 0) >= 1
    assert summary.get("product_table_count", 0) >= 1
    assert summary.get("job_table_count", 0) >= 1
    assert summary.get("dependency_table_count", 0) >= 1
    assert summary.get("sampled_row_count", 0) >= 4
    assert summary.get("candidate_source_match_count", 0) >= 1

    safety = mapping.get("safety", {})
    assert safety.get("read_only") is True
    assert safety.get("modified_database") is False
    assert safety.get("authoritative_resolution") is False
    assert safety.get("claimed_asset_ids") is False
    assert safety.get("claimed_products_resolved") is False
    assert safety.get("row_presence_is_resolution") is False

    products = data.get("o3de", {}).get("products")
    if isinstance(products, dict):
        assert products.get("resolved") is not True
