import json
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script() -> Path:
    return _repo_root() / "tools" / "screenshot-evidence" / "extract_screenshot_evidence_index.py"


def _source_index_fixture() -> Path:
    return _repo_root() / "examples" / "screenshot-evidence" / "max_biped_v1_screenshot_source_index.json"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(_script()), *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))


def _payload(stdout: str) -> dict:
    start = stdout.find("{")
    assert start >= 0, f"extractor output did not contain JSON payload:\n{stdout}"
    return json.loads(stdout[start:])


@pytest.fixture()
def repo_tmp_dir() -> Path:
    base = _repo_root() / "examples" / "screenshot-evidence" / "_pytest_extractor"
    run_dir = base / uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


@pytest.fixture()
def sandbox_tmp_shots_dir() -> Path:
    base = _repo_root() / "examples" / "sandbox" / "evidence-sources" / "screenshots" / "_pytest_extractor"
    run_dir = base / uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_pass_fixture_returns_pass():
    result = _run(["--source-index", str(_source_index_fixture())])
    payload = _payload(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "pass"
    assert payload["manifest_attachment"]["target_path"] == "qc.gates[]"
    assert payload["manifest_attachment"]["future_target_path"] == "qc.checks[]"
    assert payload["manifest_attachment"]["qc_check"]["check_id"] == "screenshot_evidence_v1"


def test_warn_requires_allow_warn(repo_tmp_dir: Path, sandbox_tmp_shots_dir: Path):
    odd_ext = sandbox_tmp_shots_dir / "odd-extension.txt"
    odd_ext.write_text("fixture", encoding="utf-8")

    warn_index = {
        "schema_version": "1.0.0",
        "evidence_source_type": "imported_capture",
        "minimum_required": 1,
        "screenshots": [
            {
                "path": str(odd_ext.relative_to(_repo_root())).replace("\\", "/"),
                "label": "odd_extension",
            },
        ],
    }
    path = repo_tmp_dir / "warn-index.json"
    path.write_text(json.dumps(warn_index, indent=2), encoding="utf-8")

    no_allow = _run(["--source-index", str(path)])
    no_allow_payload = _payload(no_allow.stdout)
    assert no_allow_payload["status"] == "warn"
    assert no_allow.returncode != 0

    allow = _run(["--source-index", str(path), "--allow-warn"])
    allow_payload = _payload(allow.stdout)
    assert allow_payload["status"] == "warn"
    assert allow.returncode == 0


def test_missing_file_fails(repo_tmp_dir: Path):
    fail_index = {
        "schema_version": "1.0.0",
        "evidence_source_type": "fixture",
        "minimum_required": 1,
        "screenshots": [
            {
                "path": "examples/sandbox/evidence-sources/screenshots/does-not-exist.png",
                "label": "missing",
            }
        ],
    }
    path = repo_tmp_dir / "fail-index.json"
    path.write_text(json.dumps(fail_index, indent=2), encoding="utf-8")

    result = _run(["--source-index", str(path)])
    payload = _payload(result.stdout)
    assert payload["status"] == "fail"
    assert result.returncode != 0
    assert any(item.get("id") == "screenshot_missing" for item in payload["findings"])


def test_path_traversal_fails(repo_tmp_dir: Path):
    bad_index = {
        "schema_version": "1.0.0",
        "evidence_source_type": "fixture",
        "minimum_required": 1,
        "screenshots": [{"path": "../outside.png", "label": "bad"}],
    }
    path = repo_tmp_dir / "bad-index.json"
    path.write_text(json.dumps(bad_index, indent=2), encoding="utf-8")

    result = _run(["--source-index", str(path)])
    payload = _payload(result.stdout)
    assert payload["status"] == "fail"
    assert result.returncode != 0
    assert any(item.get("id") == "screenshot_path_invalid" for item in payload["findings"])
