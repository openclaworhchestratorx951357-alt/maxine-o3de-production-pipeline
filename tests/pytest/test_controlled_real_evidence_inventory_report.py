import json
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "release-lane" / "report_controlled_real_evidence_inventory.py"
PROJECT_FIXTURE = (
    REPO_ROOT / "examples" / "sandbox" / "project-inventory" / "max_biped_v1_project_inventory.fixture.json"
)
ASSET_FIXTURE = (
    REPO_ROOT / "examples" / "sandbox" / "asset-candidates" / "max_biped_v1_asset_candidate_inventory.fixture.json"
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def _payload(stdout: str) -> dict:
    start = stdout.find("{")
    assert start >= 0, f"stdout did not include JSON payload:\n{stdout}"
    return json.loads(stdout[start:])


@pytest.fixture()
def repo_tmp_dir() -> Path:
    base = REPO_ROOT / "examples" / "manifests" / "_pytest_controlled_real_inventory"
    run_dir = base / uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_default_fixture_inventory_report_passes_and_writes_output(repo_tmp_dir: Path):
    output_path = repo_tmp_dir / "controlled-real-evidence-inventory.json"
    result = _run("--output", str(output_path))
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    payload = _payload(result.stdout)
    assert payload["status"] == "pass"
    assert payload["report_type"] == "CONTROLLED_REAL_EVIDENCE_INVENTORY_v1_REPORT"
    assert payload["inventory_mode"] == "approved_local_inputs_and_evidence_sources_only"
    assert payload["execution_admitted"] is False
    assert payload["controlled_real_inventory_ready"] is True
    assert payload["discovered_asset_candidate_count"] >= 1
    assert output_path.exists()


def test_warn_when_candidates_and_evidence_are_missing(repo_tmp_dir: Path):
    project_path = repo_tmp_dir / "project.json"
    asset_path = repo_tmp_dir / "asset.json"
    output_path = repo_tmp_dir / "warn-output.json"
    project_payload = json.loads(PROJECT_FIXTURE.read_text(encoding="utf-8-sig"))
    asset_payload = json.loads(ASSET_FIXTURE.read_text(encoding="utf-8-sig"))

    asset_payload["source_asset_candidates"] = []
    asset_payload["linked_sandbox_evidence"] = {
        "receipt_ids": [],
        "review_packet_ids": [],
        "decision_ids": [],
        "workflow_run_ids": [],
        "evidence_bundle_ids": [],
    }

    project_path.write_text(json.dumps(project_payload, indent=2) + "\n", encoding="utf-8")
    asset_path.write_text(json.dumps(asset_payload, indent=2) + "\n", encoding="utf-8")

    warn_result = _run(
        "--project-inventory",
        str(project_path),
        "--asset-candidate-inventory",
        str(asset_path),
        "--output",
        str(output_path),
    )
    assert warn_result.returncode == 2
    warn_payload = _payload(warn_result.stdout)
    assert warn_payload["status"] == "warn"

    allow_result = _run(
        "--project-inventory",
        str(project_path),
        "--asset-candidate-inventory",
        str(asset_path),
        "--output",
        str(output_path),
        "--allow-warn",
    )
    assert allow_result.returncode == 0, f"{allow_result.stdout}\n{allow_result.stderr}"
    allow_payload = _payload(allow_result.stdout)
    assert allow_payload["status"] == "warn"


def test_fail_when_candidate_path_has_parent_traversal(repo_tmp_dir: Path):
    project_path = repo_tmp_dir / "project.json"
    asset_path = repo_tmp_dir / "asset.json"
    output_path = repo_tmp_dir / "fail-output.json"
    project_payload = json.loads(PROJECT_FIXTURE.read_text(encoding="utf-8-sig"))
    asset_payload = json.loads(ASSET_FIXTURE.read_text(encoding="utf-8-sig"))

    asset_payload["source_asset_candidates"][0]["relative_path"] = "../outside/max_biped_v1_source_character.fbx"

    project_path.write_text(json.dumps(project_payload, indent=2) + "\n", encoding="utf-8")
    asset_path.write_text(json.dumps(asset_payload, indent=2) + "\n", encoding="utf-8")

    result = _run(
        "--project-inventory",
        str(project_path),
        "--asset-candidate-inventory",
        str(asset_path),
        "--output",
        str(output_path),
        "--allow-warn",
    )
    assert result.returncode == 1
    payload = _payload(result.stdout)
    assert payload["status"] == "fail"
    finding_ids = {item.get("id") for item in payload["findings"]}
    assert "candidate_invalid_relative_path" in finding_ids
