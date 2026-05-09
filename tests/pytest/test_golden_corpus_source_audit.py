import json
import subprocess
import sys
from pathlib import Path

from tools.o3de.audit_golden_corpus_sources import audit_golden_corpus_sources


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "o3de" / "audit_golden_corpus_sources.py"
CORPUS = REPO_ROOT / "examples" / "golden-corpus"


def _write_project(tmp_path: Path, *, gems: list[str] | None = None) -> Path:
    project = tmp_path / "MAXINE_GoldenCorpus"
    (project / "Assets" / "Characters" / "MAXINE" / "release").mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps(
            {
                "project_name": "MAXINE_GoldenCorpus",
                "gem_names": gems or ["EMotionFX", "PhysX5", "PrefabBuilder"],
            }
        ),
        encoding="utf-8",
    )
    return project


def test_source_audit_reports_missing_release_rigged_sources(tmp_path):
    project = _write_project(tmp_path)

    report = audit_golden_corpus_sources(CORPUS, project)

    assert report["status"] == "fail"
    assert report["release_rigged_source_asset_found"] is False
    assert report["actor_capable_source"]["present"] is False
    assert report["motion_capable_source"]["present"] is False
    assert report["motionset"]["status"] == "missing"
    assert report["animgraph"]["status"] == "missing"
    assert report["pxmesh"]["status"] == "missing"
    assert "MXN_RELEASE_RIGGED_SOURCE_MISSING" in report["errors"]


def test_source_audit_accepts_local_release_rigged_source_capabilities(tmp_path):
    project = _write_project(tmp_path)
    root = project / "Assets" / "Characters" / "MAXINE" / "release"
    (root / "maxine_release_source.fbx").write_bytes(b"fixture fbx")
    (root / "maxine_release_source.fbx.assetinfo").write_text('{"values":[{"$type":"ActorGroup"}]}', encoding="utf-8")
    (root / "maxine_idle.fbx").write_bytes(b"fixture fbx")
    (root / "maxine_idle.fbx.assetinfo").write_text('{"values":[{"$type":"MotionGroup"}]}', encoding="utf-8")
    (root / "maxine_collider.fbx").write_bytes(b"fixture fbx")
    (root / "maxine_collider.fbx.assetinfo").write_text(
        '{"values":[{"$type":"MeshGroup","PhysicsMaterialSlots":{"Slots":[{"Name":"Entire object"}]}}]}',
        encoding="utf-8",
    )
    (root / "maxine.motionset").write_text("<ObjectStream />", encoding="utf-8")
    (root / "maxine.animgraph").write_text("<ObjectStream />", encoding="utf-8")

    report = audit_golden_corpus_sources(CORPUS, project)

    assert report["status"] == "pass"
    assert report["release_rigged_source_asset_found"] is True
    assert report["actor_capable_source"]["present"] is True
    assert report["motion_capable_source"]["present"] is True
    assert report["motionset"]["status"] == "source-provided"
    assert report["animgraph"]["status"] == "source-provided"
    assert report["pxmesh"]["status"] == "source-settings-present"
    assert report["errors"] == []


def test_source_audit_accepts_primitive_asset_params_for_pxmesh_source(tmp_path):
    project = _write_project(tmp_path)
    root = project / "Assets" / "Characters" / "MAXINE" / "release"
    (root / "maxine_release_source.fbx").write_bytes(b"fixture fbx")
    (root / "maxine_release_source.fbx.assetinfo").write_text('{"values":[{"$type":"ActorGroup"}]}', encoding="utf-8")
    (root / "maxine_idle.fbx").write_bytes(b"fixture fbx")
    (root / "maxine_idle.fbx.assetinfo").write_text('{"values":[{"$type":"MotionGroup"}]}', encoding="utf-8")
    (root / "maxine_pxmesh_box.fbx").write_bytes(b"fixture fbx")
    (root / "maxine_pxmesh_box.fbx.assetinfo").write_text(
        '{"values":[{"$type":"MeshGroup","PrimitiveAssetParams":{"PrimitiveShapeTarget":2}}]}',
        encoding="utf-8",
    )
    (root / "maxine.motionset").write_text("<ObjectStream />", encoding="utf-8")
    (root / "maxine.animgraph").write_text("<ObjectStream />", encoding="utf-8")

    report = audit_golden_corpus_sources(CORPUS, project)

    assert report["status"] == "pass"
    assert report["pxmesh"]["status"] == "source-settings-present"
    assert report["pxmesh"]["path"] == "Assets/Characters/MAXINE/release/maxine_pxmesh_box.fbx.assetinfo"


def test_source_audit_cli_json_valid(tmp_path):
    project = _write_project(tmp_path)

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--corpus",
            str(CORPUS),
            "--project",
            str(project),
            "--json",
        ],
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["report_type"] == "maxine_golden_corpus_source_audit"
    assert payload["live_editor_execution"] is False
    assert payload["live_publication"] is False
