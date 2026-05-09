import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from tools.o3de.audit_apb_product_evidence import audit_apb_product_evidence


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "o3de" / "audit_apb_product_evidence.py"


def _write_project(tmp_path: Path) -> Path:
    project = tmp_path / "MAXINE_GoldenCorpus"
    (project / "Cache").mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps(
            {
                "project_name": "MAXINE_GoldenCorpus",
                "gem_names": ["PhysX5", "PhysXCommon", "PrefabBuilder", "EMotionFX"],
            }
        ),
        encoding="utf-8",
    )
    return project


def _write_asset_db(project: Path, products: list[tuple[str, str, str, str, int]]) -> None:
    db_path = project / "Cache" / "assetdb.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            create table Sources (
                SourceID integer primary key,
                SourceName text not null,
                SourceGuid text not null
            );
            create table Jobs (
                JobID integer primary key,
                SourcePK integer not null,
                JobKey text not null,
                Platform text not null,
                Status integer not null,
                ErrorCount integer default 0,
                WarningCount integer default 0
            );
            create table Products (
                ProductID integer primary key,
                JobPK integer not null,
                ProductName text not null,
                SubID integer default 0
            );
            """
        )
        source_map: dict[str, int] = {}
        for index, (source_name, product_name, platform, job_key, status) in enumerate(products, start=1):
            if source_name not in source_map:
                source_pk = len(source_map) + 1
                source_map[source_name] = source_pk
                conn.execute(
                    "insert into Sources(SourceID, SourceName, SourceGuid) values (?, ?, ?)",
                    (source_pk, source_name, f"source-guid-{source_pk}"),
                )
            source_pk = source_map[source_name]
            conn.execute(
                "insert into Jobs(JobID, SourcePK, JobKey, Platform, Status) values (?, ?, ?, ?, ?)",
                (index, source_pk, job_key, platform, status),
            )
            conn.execute(
                "insert into Products(ProductID, JobPK, ProductName, SubID) values (?, ?, ?, ?)",
                (index, index, product_name, 1000 + index),
            )


def _write_engine_bin(tmp_path: Path, *, include_physx_registry: bool) -> Path:
    bin_dir = tmp_path / "engine" / "build" / "windows" / "bin" / "profile"
    registry = bin_dir / "Registry"
    registry.mkdir(parents=True)
    (bin_dir / "AssetProcessorBatch.exe").write_bytes(b"apb")
    (bin_dir / "PhysX5.Editor.Gem.dll").write_bytes(b"physx")
    module_text = "SceneProcessing.Editor.dll\n"
    if include_physx_registry:
        module_text += "PhysX5.Editor.Gem.dll\n"
    (registry / "cmake_dependencies.assetbuilder.setreg").write_text(module_text, encoding="utf-8")
    (registry / "cmake_dependencies.assetprocessorbatch.setreg").write_text(module_text, encoding="utf-8")
    return bin_dir / "AssetProcessorBatch.exe"


def test_audit_reports_exact_pxmesh_from_asset_db(tmp_path):
    project = _write_project(tmp_path)
    apb = _write_engine_bin(tmp_path, include_physx_registry=True)
    _write_asset_db(
        project,
        [
            (
                "assets/characters/maxine/release/maxine_physx_final_spherebot.fbx",
                "pc/assets/characters/maxine/release/maxine_physx_final_spherebot.pxmesh",
                "pc",
                "Scene compilation",
                4,
            )
        ],
    )

    report = audit_apb_product_evidence(project=project, apb_executable=apb)

    assert report["status"] == "pass"
    assert report["pxmesh_found_in_ap_db"] is True
    assert report["pxmesh_found_in_apb_report"] is False
    assert report["product_matrix_status"] == "pass"
    assert report["cache_heuristic_used"] is False
    assert report["errors"] == []


def test_audit_reports_missing_pxmesh_without_reclassifying_lookalikes(tmp_path):
    project = _write_project(tmp_path)
    apb = _write_engine_bin(tmp_path, include_physx_registry=False)
    _write_asset_db(
        project,
        [
            (
                "assets/characters/maxine/release/maxine_physx_final_spherebot.fbx",
                "pc/assets/characters/maxine/release/maxine_physx_final_spherebot.azmodel",
                "pc",
                "Scene compilation",
                4,
            ),
            (
                "assets/characters/maxine/release/maxine_physx_final_spherebot.fbx",
                "pc/assets/characters/maxine/release/maxine_physx_final_spherebot_physx_collision.azbuffer",
                "pc",
                "Scene compilation",
                4,
            ),
        ],
    )

    report = audit_apb_product_evidence(project=project, apb_executable=apb)

    assert report["status"] == "fail"
    assert report["pxmesh_found_in_ap_db"] is False
    assert report["pxmesh_like_product_found_under_different_classification"] is True
    assert report["product_matrix_status"] == "fail"
    assert "MXN_ASSET_PRODUCT_MISSING" in report["errors"]
    assert report["physx_builder_audit"]["physx_editor_module_available"] is True
    assert report["physx_builder_audit"]["physx_editor_module_listed_in_dependency_registry"] is False


def test_audit_can_use_apb_report_product_evidence(tmp_path):
    project = _write_project(tmp_path)
    apb = _write_engine_bin(tmp_path, include_physx_registry=True)
    _write_asset_db(project, [])
    apb_report = tmp_path / "asset_processor_batch_live_report.json"
    apb_report.write_text(
        json.dumps(
            {
                "produced_products": [
                    {
                        "product_type": "pxmesh",
                        "product_path": "pc/assets/characters/maxine/release/collider.pxmesh",
                    }
                ],
                "missing_products": [],
                "cache_heuristic_used": False,
            }
        ),
        encoding="utf-8",
    )

    report = audit_apb_product_evidence(project=project, apb_executable=apb, apb_report=apb_report)

    assert report["status"] == "pass"
    assert report["pxmesh_found_in_apb_report"] is True
    assert report["pxmesh_found_in_ap_db"] is False


def test_audit_cli_json_valid(tmp_path):
    project = _write_project(tmp_path)
    apb = _write_engine_bin(tmp_path, include_physx_registry=False)
    _write_asset_db(project, [])

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project",
            str(project),
            "--apb-executable",
            str(apb),
            "--json",
        ],
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["report_type"] == "maxine_apb_product_evidence_audit"
    assert payload["live_editor_execution"] is False
    assert payload["live_publication"] is False
