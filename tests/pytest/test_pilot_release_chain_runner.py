import json
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _runner_script() -> Path:
    return _repo_root() / "tools" / "release-lane" / "run_pilot_release_chain_validation.py"


def _base_manifest() -> Path:
    return _repo_root() / "examples" / "manifests" / "example-release-character-pilot-chain-base.manifest.json"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(_runner_script()), *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))


def _extract_payload(stdout: str) -> dict:
    start = stdout.find("{")
    assert start >= 0, f"runner output did not include JSON payload:\n{stdout}"
    return json.loads(stdout[start:])


@pytest.fixture()
def repo_tmp_dir() -> Path:
    base = _repo_root() / "examples" / "manifests" / "_pytest_pilot_chain_runner"
    run_dir = base / uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_runner_builds_generated_manifest_and_attaches_expected_checks(repo_tmp_dir: Path):
    output_manifest = repo_tmp_dir / "generated.manifest.json"
    output_dir = repo_tmp_dir / "reports"
    result = _run(
        [
            "--base-manifest",
            str(_base_manifest()),
            "--output-manifest",
            str(output_manifest),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "completed"
    assert payload["pilot_chain_status"] == "pass"

    manifest = json.loads(output_manifest.read_text(encoding="utf-8-sig"))
    gate_ids = {
        str(item.get("check_id", "")).strip()
        for item in manifest.get("qc", {}).get("gates", [])
        if isinstance(item, dict)
    }
    assert "max_biped_v1_skeleton_contract" in gate_ids
    assert "dcc_conform_v1" in gate_ids
    assert "source_product_evidence_resolver_v1" in gate_ids
    assert "material_uv_qc_v1" in gate_ids
    assert "animation_smoke_v1" in gate_ids
    assert "screenshot_evidence_v1" in gate_ids
    assert "manual_hero_review_v1" in gate_ids
    assert "ci_artifact_retention_v1" in gate_ids
    assert "release_package_bundle_v1" in gate_ids
    assert "release_promotion_decision_v1" in gate_ids
    assert "release_publication_preflight_v1" in gate_ids
    assert "release_publication_request_approval_v1" in gate_ids
    assert "release_publication_execution_admission_gate_v1" in gate_ids
    assert "release_publication_execution_request_ledger_v1" in gate_ids
    assert "release_publication_execution_receipt_v1" in gate_ids
    assert "release_publication_evidence_integrity_index_v1" in gate_ids
    assert "release_publication_chain_audit_bundle_v1" in gate_ids
    assert "release_publication_rollback_drill_v1" in gate_ids
    assert "release_publication_ready_for_execution_request_v1" in gate_ids
    assert "release_publication_execution_handoff_v1" in gate_ids
    assert "release_publication_execution_admission_request_packet_v1" in gate_ids
    assert "release_publication_gate_set_v1" in gate_ids
    assert "pilot_release_chain_v1" in gate_ids


def test_runner_strict_chain_passes_for_pass_chain(repo_tmp_dir: Path):
    output_manifest = repo_tmp_dir / "generated-strict.manifest.json"
    output_dir = repo_tmp_dir / "reports-strict"
    result = _run(
        [
            "--base-manifest",
            str(_base_manifest()),
            "--output-manifest",
            str(output_manifest),
            "--output-dir",
            str(output_dir),
            "--strict-chain",
        ]
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    payload = _extract_payload(result.stdout)
    assert payload["pilot_chain_status"] == "pass"
