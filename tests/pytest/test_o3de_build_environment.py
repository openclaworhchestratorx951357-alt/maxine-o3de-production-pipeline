import json
import subprocess
import sys
from pathlib import Path

from tools.o3de.diagnose_o3de_build_environment import build_environment_report


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "o3de" / "diagnose_o3de_build_environment.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _engine(root: Path) -> Path:
    root.mkdir(parents=True)
    _write_json(root / "engine.json", {"engine_name": "o3de"})
    (root / "scripts").mkdir()
    (root / "scripts" / "o3de.bat").write_text("@echo off\n", encoding="utf-8")
    (root / "Gems").mkdir()
    (root / "Code").mkdir()
    (root / "cmake").mkdir()
    return root


def _project(root: Path, name: str = "MAXINE_GoldenCorpus") -> Path:
    root.mkdir(parents=True)
    _write_json(root / "project.json", {"project_name": name, "engine": "o3de"})
    return root


def _cache(build_dir: Path, third_party: Path, cl: Path, link: Path) -> Path:
    build_dir.mkdir(parents=True)
    cl.parent.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    cl.write_text("fake cl", encoding="utf-8")
    link.write_text("fake link", encoding="utf-8")
    third_party.mkdir(parents=True)
    cache = build_dir / "CMakeCache.txt"
    cache.write_text(
        "\n".join(
            [
                "CMAKE_GENERATOR:INTERNAL=Visual Studio 17 2022",
                "CMAKE_GENERATOR_INSTANCE:INTERNAL=C:/VS/BuildTools",
                "CMAKE_CONFIGURATION_TYPES:STRING=debug;profile;release",
                f"CMAKE_CXX_COMPILER:FILEPATH={cl.as_posix()}",
                f"CMAKE_LINKER:FILEPATH={link.as_posix()}",
                f"LY_3RDPARTY_PATH:PATH={third_party.as_posix()}",
                "LY_UNITY_BUILD:BOOL=ON",
                "O3DE_SOURCE_DIR:STATIC=C:/src/o3de",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (build_dir / "Code" / "Tools" / "AssetProcessor").mkdir(parents=True)
    (build_dir / "Code" / "Tools" / "AssetProcessor" / "AssetProcessorBatch.vcxproj").write_text(
        "<Project />\n",
        encoding="utf-8",
    )
    return cache


def test_build_environment_report_classifies_missing_apb_output(tmp_path):
    engine = _engine(tmp_path / "o3de")
    project = _project(tmp_path / "Projects" / "MAXINE_GoldenCorpus")
    build_dir = tmp_path / "o3de" / "build" / "windows"
    third_party = tmp_path / "3rdParty"
    _cache(build_dir, third_party, tmp_path / "VC" / "cl.exe", tmp_path / "VC" / "link.exe")

    report = build_environment_report(engine_root=engine, project_path=project, build_dir=build_dir)

    assert report["status"] == "warn"
    assert report["engine"]["valid"] is True
    assert report["project"]["valid"] is True
    assert report["cmake"]["cache_present"] is True
    assert report["visual_studio"]["msvc_tools_present"] is True
    assert report["ly_3rdparty_path"]["exists"] is True
    assert report["asset_processor_batch_output"]["exists"] is False
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in report["warnings"]
    assert report["live_asset_processor_batch_execution"] is False
    assert report["live_editor_execution"] is False


def test_build_environment_report_passes_when_apb_output_exists(tmp_path):
    engine = _engine(tmp_path / "o3de")
    project = _project(tmp_path / "Projects" / "MAXINE_GoldenCorpus")
    build_dir = tmp_path / "o3de" / "build" / "windows"
    _cache(build_dir, tmp_path / "3rdParty", tmp_path / "VC" / "cl.exe", tmp_path / "VC" / "link.exe")
    apb = build_dir / "bin" / "profile" / "AssetProcessorBatch.exe"
    apb.parent.mkdir(parents=True)
    apb.write_text("fake apb", encoding="utf-8")

    report = build_environment_report(engine_root=engine, project_path=project, build_dir=build_dir)

    assert report["status"] == "pass"
    assert report["asset_processor_batch_output"]["path"] == str(apb)
    assert report["asset_processor_batch_output"]["exists"] is True
    assert report["errors"] == []


def test_build_environment_cli_json(tmp_path):
    engine = _engine(tmp_path / "o3de")
    project = _project(tmp_path / "Projects" / "MAXINE_GoldenCorpus")
    build_dir = tmp_path / "o3de" / "build" / "windows"
    _cache(build_dir, tmp_path / "3rdParty", tmp_path / "VC" / "cl.exe", tmp_path / "VC" / "link.exe")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--engine-root",
            str(engine),
            "--project",
            str(project),
            "--build-dir",
            str(build_dir),
            "--json",
        ],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["report_type"] == "maxine_o3de_apb_build_environment"
    assert payload["status"] == "warn"
