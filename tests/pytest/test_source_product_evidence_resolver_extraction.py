import json
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "release-lane" / "extract_source_product_evidence_resolver_report.py"
PROJECT_FIXTURE = (
    REPO_ROOT / "examples" / "sandbox" / "project-inventory" / "max_biped_v1_project_inventory.fixture.json"
)
ASSET_FIXTURE = (
    REPO_ROOT / "examples" / "sandbox" / "asset-candidates" / "max_biped_v1_asset_candidate_inventory.fixture.json"
)
CONTROLLED_FIXTURE = (
    REPO_ROOT
    / "examples"
    / "controlled-real-evidence-inventory"
    / "max_biped_v1_controlled_real_evidence_inventory_pass.json"
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
    base = REPO_ROOT / "examples" / "manifests" / "_pytest_source_product_extract"
    run_dir = base / uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_extractor_default_fixtures_pass(repo_tmp_dir: Path):
    output_path = repo_tmp_dir / "source-product-report.json"
    result = _run(
        "--project-inventory",
        str(PROJECT_FIXTURE),
        "--asset-candidate-inventory",
        str(ASSET_FIXTURE),
        "--controlled-inventory-report",
        str(CONTROLLED_FIXTURE),
        "--output",
        str(output_path),
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    payload = _payload(result.stdout)
    assert payload["status"] == "pass"
    assert payload["report_type"] == "SOURCE_PRODUCT_EVIDENCE_RESOLVER_v1_REPORT"
    assert payload["evidence_source_type"] == "fixture"
    assert payload["source_uuid_claim_status"] == "not_claimed"
    assert payload["asset_id_claim_status"] == "not_claimed"
    assert payload["product_id_claim_status"] == "not_claimed"
    assert payload["cache_access_status"] == "blocked"
    assert payload["live_db_access_status"] == "blocked"
    assert output_path.exists()


def test_extractor_uses_imported_ap_evidence_when_present(repo_tmp_dir: Path):
    ap_import_path = (
        REPO_ROOT
        / "examples"
        / "sandbox"
        / "ap-evidence-imports"
        / f"pytest-source-product-ap-import-{uuid4().hex}.json"
    )
    output_path = repo_tmp_dir / "source-product-report-ap-import.json"

    try:
        ap_import_payload = {
            "schema_version": "1.0.0",
            "ap_evidence_import_id": f"pytest-ap-import-{uuid4().hex}",
            "read_only": True,
            "asset_processor_execution_admitted": False,
            "o3de_execution_admitted": False,
            "cache_access_admitted": False,
            "live_database_access_admitted": False,
            "product_ids_claimed": False,
            "asset_ids_claimed": False,
            "source_uuids_claimed": False,
            "product_resolution_claimed": False,
            "spawn_admitted": False,
            "publish_admitted": False,
            "evidence_quality": "partial",
            "observed_product_like_mentions": [
                "evidence-hint://ap-import/objects/max_biped_v1.actor",
                "evidence-hint://ap-import/objects/max_biped_v1.motion",
                "evidence-hint://ap-import/prefabs/max_biped_v1.procprefab",
                "evidence-hint://ap-import/objects/max_biped_v1.azmodel",
            ],
        }
        ap_import_path.write_text(json.dumps(ap_import_payload, indent=2) + "\n", encoding="utf-8")

        result = _run(
            "--project-inventory",
            str(PROJECT_FIXTURE),
            "--asset-candidate-inventory",
            str(ASSET_FIXTURE),
            "--controlled-inventory-report",
            str(CONTROLLED_FIXTURE),
            "--ap-evidence-import",
            str(ap_import_path),
            "--output",
            str(output_path),
        )
        assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
        payload = _payload(result.stdout)
        assert payload["status"] == "pass"
        assert payload["evidence_source_type"] == "imported_ap_evidence"
        actor = next(
            item for item in payload["observed_products"] if item.get("product_type") == "actor"
        )
        assert actor["evidence_source"] == "imported_ap_evidence"
    finally:
        if ap_import_path.exists():
            ap_import_path.unlink()


def test_extractor_fails_when_candidate_is_outside_approved_roots(repo_tmp_dir: Path):
    project_path = repo_tmp_dir / "project.json"
    asset_path = repo_tmp_dir / "asset.json"
    output_path = repo_tmp_dir / "source-product-report-fail.json"

    project_payload = json.loads(PROJECT_FIXTURE.read_text(encoding="utf-8-sig"))
    asset_payload = json.loads(ASSET_FIXTURE.read_text(encoding="utf-8-sig"))
    asset_payload["source_asset_candidates"][0]["relative_path"] = "examples/unsafe/max_biped_v1_source_character.fbx"

    project_path.write_text(json.dumps(project_payload, indent=2) + "\n", encoding="utf-8")
    asset_path.write_text(json.dumps(asset_payload, indent=2) + "\n", encoding="utf-8")

    result = _run(
        "--project-inventory",
        str(project_path),
        "--asset-candidate-inventory",
        str(asset_path),
        "--controlled-inventory-report",
        str(CONTROLLED_FIXTURE),
        "--output",
        str(output_path),
    )
    assert result.returncode == 1
    payload = _payload(result.stdout)
    assert payload["status"] == "fail"
    finding_ids = {item.get("id") for item in payload.get("findings", [])}
    assert "source_asset_path_outside_approved_roots" in finding_ids
