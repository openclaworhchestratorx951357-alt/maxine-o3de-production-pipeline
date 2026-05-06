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


def _pass_fixture() -> Path:
    return _repo_root() / "examples" / "screenshot-evidence" / "max_biped_v1_visual_evidence_pass.json"


def _warn_fixture() -> Path:
    return _repo_root() / "examples" / "screenshot-evidence" / "max_biped_v1_visual_evidence_warn.json"


def _fail_fixture() -> Path:
    return _repo_root() / "examples" / "screenshot-evidence" / "max_biped_v1_visual_evidence_fail.json"


def _controlled_real_runner_fixture() -> Path:
    return (
        _repo_root()
        / "examples"
        / "sandbox"
        / "visual-evidence"
        / "pilot-candidates"
        / "max_biped_v1_visual_evidence_controlled_real.fixture.json"
    )


def _legacy_source_index_fixture() -> Path:
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


def test_pass_fixture_returns_pass():
    result = _run(["--source-index", str(_pass_fixture())])
    payload = _payload(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "pass"
    assert payload["evidence_class"] == "controlled_real"
    assert payload["claim_status"] == "evidence_only"
    assert payload["manifest_attachment"]["target_path"] == "qc.gates[]"
    assert payload["manifest_attachment"]["future_target_path"] == "qc.checks[]"
    assert payload["manifest_attachment"]["qc_check"]["check_id"] == "screenshot_evidence_v1"
    details = payload["manifest_attachment"]["qc_check"]["details"]
    assert details["evidence_class"] == "controlled_real"
    assert details["safety"]["runtime_execution_status"] == "blocked"
    assert details["computed_required_views_present"]["detail"] is True
    assert details["missing_required_views"] == []


def test_warn_requires_allow_warn():
    no_allow = _run(["--source-index", str(_warn_fixture())])
    no_allow_payload = _payload(no_allow.stdout)
    assert no_allow_payload["status"] == "warn"
    assert no_allow.returncode != 0

    allow = _run(["--source-index", str(_warn_fixture()), "--allow-warn"])
    allow_payload = _payload(allow.stdout)
    assert allow_payload["status"] == "warn"
    assert allow.returncode == 0


def test_fail_fixture_fails():
    result = _run(["--source-index", str(_fail_fixture())])
    payload = _payload(result.stdout)
    assert payload["status"] == "fail"
    assert result.returncode != 0
    assert any(item.get("id") == "screenshot_ref_missing_file" for item in payload["findings"])
    assert any(item.get("id") == "missing_required_views" for item in payload["findings"])


def test_path_traversal_fails(repo_tmp_dir: Path):
    bad_report = json.loads(_pass_fixture().read_text(encoding="utf-8-sig"))
    bad_report["screenshot_refs"][0]["path"] = "../outside.txt"
    bad_report["status"] = "fail"
    bad_report["manifest_attachment"]["qc_check"]["result"] = "fail"
    bad_report["manifest_attachment"]["qc_check"]["severity"] = "error"
    path = repo_tmp_dir / "bad-index.json"
    path.write_text(json.dumps(bad_report, indent=2), encoding="utf-8")

    result = _run(["--source-index", str(path)])
    payload = _payload(result.stdout)
    assert payload["status"] == "fail"
    assert result.returncode != 0
    assert any(item.get("id") == "screenshot_ref_path_unsafe" for item in payload["findings"])


def test_runner_fixture_contract_returns_controlled_real_pass():
    result = _run(["--source-index", str(_controlled_real_runner_fixture())])
    payload = _payload(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "pass"
    assert payload["evidence_class"] == "controlled_real"


def test_legacy_source_index_is_still_supported():
    result = _run(["--source-index", str(_legacy_source_index_fixture())])
    payload = _payload(result.stdout)
    assert payload["check_id"] == "screenshot_evidence_v1"
    assert payload["manifest_attachment"]["target_path"] == "qc.gates[]"
    assert payload["manifest_attachment"]["future_target_path"] == "qc.checks[]"
    assert payload["evidence_class"] == "fixture"
    assert result.returncode in (0, 2)
