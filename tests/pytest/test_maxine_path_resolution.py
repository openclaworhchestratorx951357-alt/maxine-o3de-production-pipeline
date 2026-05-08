from pathlib import Path

from tools.validation.maxine_paths import (
    MXN_INPUT_MISSING,
    MXN_PATH_UNSAFE,
    normalize_path_text,
    project_relative_path,
    validate_publication_path,
)


def test_relative_project_path_accepted(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    result = project_relative_path("Assets/Characters/maxine.fbx", project_root)

    assert result.ok
    assert result.relative_path == "Assets/Characters/maxine.fbx"


def test_absolute_path_inside_project_converted(tmp_path: Path):
    project_root = tmp_path / "project"
    source = project_root / "Assets" / "Characters" / "maxine.fbx"
    source.parent.mkdir(parents=True)
    source.write_text("fixture", encoding="utf-8")

    result = project_relative_path(str(source), project_root)

    assert result.ok
    assert result.relative_path == "Assets/Characters/maxine.fbx"


def test_outside_path_rejected_for_publication(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside = tmp_path / "outside" / "maxine.fbx"
    outside.parent.mkdir()
    outside.write_text("fixture", encoding="utf-8")

    result = validate_publication_path(str(outside), [project_root])

    assert not result.ok
    assert result.error_code == MXN_PATH_UNSAFE


def test_windows_style_path_normalized():
    assert normalize_path_text("Assets\\Characters\\MAXINE.fbx") == "Assets/Characters/MAXINE.fbx"


def test_missing_path_returns_clear_error_code(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    result = validate_publication_path("Assets/Characters/missing.fbx", [project_root], must_exist=True)

    assert not result.ok
    assert result.error_code == MXN_INPUT_MISSING
