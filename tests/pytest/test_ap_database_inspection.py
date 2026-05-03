import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_inspection_script_exists():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "inspect_ap_database_schema.py"
    assert script_path.exists()


def test_inspection_wrapper_exists():
    repo_root = Path(__file__).resolve().parents[2]
    wrapper_path = repo_root / "scripts" / "powershell" / "Inspect-MaxineApDatabase.ps1"
    assert wrapper_path.exists()


def test_ap_database_schema_inspection(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tools" / "asset-resolver" / "inspect_ap_database_schema.py"
    manifest_src = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"

    db_path = tmp_path / "ap_schema_test.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE Sources (SourceID INTEGER PRIMARY KEY, SourceName TEXT)")
    conn.execute("CREATE TABLE Products (ProductID INTEGER PRIMARY KEY, SourceID INTEGER, ProductName TEXT)")
    conn.execute("CREATE TABLE Jobs (JobID INTEGER PRIMARY KEY, SourceID INTEGER, Status TEXT)")
    conn.execute("CREATE TABLE SourceDependency (SourceID INTEGER, DependsOnSource INTEGER)")
    conn.execute("CREATE INDEX idx_products_sourceid ON Products(SourceID)")
    conn.execute("INSERT INTO Sources (SourceName) VALUES ('Source_A'), ('Source_B')")
    conn.execute("INSERT INTO Products (SourceID, ProductName) VALUES (1, 'Product_A'), (2, 'Product_B')")
    conn.execute("INSERT INTO Jobs (SourceID, Status) VALUES (1, 'queued'), (2, 'pass')")
    conn.execute("INSERT INTO SourceDependency (SourceID, DependsOnSource) VALUES (2, 1)")
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
        "--output",
        str(manifest_out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    assert result.returncode == 0, f"Inspection failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    data = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    inspection = data.get("o3de", {}).get("ap_database_inspection")
    assert isinstance(inspection, dict), "o3de.ap_database_inspection missing"

    summary = inspection.get("summary", {})
    assert summary.get("opened_database_count") == 1
    assert summary.get("total_table_count", 0) >= 4
    assert summary.get("heuristic_source_table_count", 0) >= 1
    assert summary.get("heuristic_product_table_count", 0) >= 1
    assert summary.get("heuristic_job_table_count", 0) >= 1
    assert summary.get("heuristic_dependency_table_count", 0) >= 1

    safety = inspection.get("safety", {})
    assert safety.get("read_only") is True
    assert safety.get("modified_database") is False
    assert safety.get("authoritative_resolution") is False
    assert safety.get("claimed_asset_ids") is False
    assert safety.get("claimed_products_resolved") is False

    assert db_path.exists()
    reopen_conn = sqlite3.connect(str(db_path))
    count = reopen_conn.execute("SELECT COUNT(*) FROM Sources").fetchone()[0]
    reopen_conn.close()
    assert count >= 1
