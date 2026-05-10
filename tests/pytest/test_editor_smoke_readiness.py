import json
import os
import subprocess
import sys
from pathlib import Path

from tools.o3de.editor_smoke import build_editor_smoke_readiness_report


REPO_ROOT = Path(__file__).resolve().parents[2]
DIAGNOSTIC_SCRIPT = REPO_ROOT / "tools" / "o3de" / "diagnose_editor_smoke_readiness.py"
EDITOR_SMOKE_SCRIPT = REPO_ROOT / "tools" / "o3de" / "editor_smoke.py"


def _project(root: Path, *, gems: list[str] | None = None) -> Path:
    project = root / "MAXINE_GoldenCorpus"
    project.mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps(
            {
                "project_name": "MAXINE_GoldenCorpus",
                "gem_names": gems if gems is not None else ["EditorPythonBindings"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return project


def _engine(root: Path, *, editor: bool = True, bindings: bool = True) -> Path:
    engine = root / "o3de"
    bin_dir = engine / "build" / "windows" / "bin" / "profile"
    bin_dir.mkdir(parents=True)
    (engine / "engine.json").write_text('{"engine_name":"o3de"}\n', encoding="utf-8")
    if editor:
        (bin_dir / "Editor.exe").write_text("editor placeholder", encoding="utf-8")
    if bindings:
        (bin_dir / "EditorPythonBindings.Editor.dll").write_text("bindings placeholder", encoding="utf-8")
    return engine


def _env(engine: Path, project: Path, *, editor: Path | None = None) -> dict:
    env = os.environ.copy()
    env["O3DE_ENGINE_ROOT"] = str(engine)
    env["O3DE_PROJECT_PATH"] = str(project)
    env["MAXINE_ENABLE_O3DE_INTEGRATION"] = "1"
    env["MAXINE_ENABLE_O3DE_EDITOR_SMOKE"] = "1"
    env["MAXINE_ALLOW_LIVE_O3DE_COMMANDS"] = "1"
    env["MAXINE_ALLOW_LIVE_EDITOR_COMMANDS"] = "1"
    env["MAXINE_ALLOW_LIVE_PUBLICATION"] = "0"
    env["MAXINE_ENABLE_RELEASE_PACKAGING"] = "0"
    if editor is not None:
        env["O3DE_EDITOR_EXECUTABLE"] = str(editor)
    else:
        env.pop("O3DE_EDITOR_EXECUTABLE", None)
    return env


def test_editor_readiness_rejects_missing_editor_executable(tmp_path):
    engine = _engine(tmp_path, editor=False)
    project = _project(tmp_path)
    report = build_editor_smoke_readiness_report(env=_env(engine, project), strict=True)

    assert report["status"] == "fail"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in report["errors"]
    assert report["editor_executable"]["available"] is False
    assert report["live_editor_execution_allowed"] is False
    assert report["live_publication_allowed"] is False
    assert report["release_packaging_allowed"] is False


def test_editor_readiness_requires_editor_python_bindings_enabled(tmp_path):
    engine = _engine(tmp_path)
    project = _project(tmp_path, gems=[])
    editor = engine / "build" / "windows" / "bin" / "profile" / "Editor.exe"

    report = build_editor_smoke_readiness_report(env=_env(engine, project, editor=editor), strict=True)

    assert report["status"] == "fail"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in report["errors"]
    assert report["editor_python_bindings_enabled"] is False


def test_editor_readiness_passes_with_paired_editor_bindings_and_closed_publication_gates(tmp_path):
    engine = _engine(tmp_path)
    project = _project(tmp_path)
    editor = engine / "build" / "windows" / "bin" / "profile" / "Editor.exe"

    report = build_editor_smoke_readiness_report(env=_env(engine, project, editor=editor), strict=True)

    assert report["status"] == "pass"
    assert report["editor_executable"]["available"] is True
    assert report["editor_executable"]["provenance"] == "engine_profile_bin"
    assert report["editor_python_bindings_enabled"] is True
    assert report["editor_python_bindings_available"] is True
    assert report["temp_level_policy"]["valid"] is True
    assert report["live_editor_execution_allowed"] is True
    assert report["live_publication_allowed"] is False
    assert report["release_packaging_allowed"] is False


def test_editor_readiness_cli_json_reports_unavailable_without_strict(tmp_path):
    engine = _engine(tmp_path, editor=False)
    project = _project(tmp_path)
    env = _env(engine, project)

    result = subprocess.run(
        [
            sys.executable,
            str(DIAGNOSTIC_SCRIPT),
            "--engine-root",
            str(engine),
            "--project",
            str(project),
            "--json",
        ],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["report_type"] == "maxine_editor_smoke_readiness"
    assert payload["status"] == "unavailable"
    assert payload["live_editor_execution_allowed"] is False


def test_editor_smoke_check_local_readiness_strict_fails_without_editor(tmp_path):
    engine = _engine(tmp_path, editor=False)
    project = _project(tmp_path)
    env = _env(engine, project)

    result = subprocess.run(
        [
            sys.executable,
            str(EDITOR_SMOKE_SCRIPT),
            "--manifest",
            "examples/manifests/release_rigged.pass.example.json",
            "--check-local-readiness",
            "--strict",
        ],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode != 0
    assert "Editor smoke readiness: fail" in result.stdout
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result.stdout
