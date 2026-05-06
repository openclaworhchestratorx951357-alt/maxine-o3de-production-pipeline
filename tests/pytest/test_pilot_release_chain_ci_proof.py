import json
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _proof_script() -> Path:
    return _repo_root() / "tools" / "release-lane" / "prove_pilot_release_chain.py"


@pytest.fixture()
def repo_tmp_dir() -> Path:
    base = _repo_root() / "examples" / "manifests" / "_pytest_pilot_chain_proof"
    run_dir = base / uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_pilot_chain_proof_command_passes_expected_pass_baseline(repo_tmp_dir: Path):
    cmd = [
        sys.executable,
        str(_proof_script()),
        "--output-root",
        str(repo_tmp_dir / "proof-output"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    start = result.stdout.find("{")
    assert start >= 0, f"proof output did not include JSON payload:\n{result.stdout}"
    payload = json.loads(result.stdout[start:])
    assert payload["status"] == "pass"
    assert payload["check_id"] == "pilot_release_chain_ci_proof_v1"
    assert payload["details"]["normal_run"]["pilot_chain_status"] == "pass"
    assert payload["details"]["strict_run"]["pilot_chain_status"] == "pass"
    assert payload["details"]["normal_run"]["runner_return_code"] == 0
    assert payload["details"]["strict_run"]["runner_return_code"] == 0
    normal_steps = {step["step"]: step for step in payload["details"]["normal_run"]["validator_steps"]}
    strict_steps = {step["step"]: step for step in payload["details"]["strict_run"]["validator_steps"]}
    assert "controlled_real_evidence_inventory" in normal_steps
    assert "source_product_resolver_extract" in normal_steps
    assert "controlled_real_evidence_inventory" in strict_steps
    assert "source_product_resolver_extract" in strict_steps
    assert Path(normal_steps["controlled_real_evidence_inventory"]["payload_path"]).exists()
    assert Path(normal_steps["source_product_resolver_extract"]["payload_path"]).exists()
    evidence_status = payload["details"]["evidence_admission_report"]
    assert evidence_status["status"] == "pass"
    assert evidence_status["report_type"] == "RELEASE_LANE_EVIDENCE_ADMISSION_STATUS_v1_REPORT"
    assert evidence_status["overall_release_lane_state"] == "controlled_evidence_ready_execution_blocked"
    assert "max_biped_v1_skeleton_contract" in evidence_status["evidence_classification"]["controlled_real_check_ids"]
    assert "material_uv_qc_v1" in evidence_status["evidence_classification"]["controlled_real_check_ids"]
    assert "animation_smoke_v1" in evidence_status["evidence_classification"]["controlled_real_check_ids"]
    assert "screenshot_evidence_v1" in evidence_status["evidence_classification"]["controlled_real_check_ids"]
    assert "aaa_performance_budget_v1" in evidence_status["evidence_classification"]["controlled_real_check_ids"]
    assert "manual_hero_review_v1" in evidence_status["evidence_classification"]["manual_check_ids"]
    assert "real_pilot_release_candidate_package_v1" in evidence_status["evidence_classification"]["manual_check_ids"]
    assert evidence_status["reporter_return_code"] == 0
    assert Path(evidence_status["output_path"]).exists()
    readiness_status = payload["details"]["production_readiness_report"]
    assert readiness_status["status"] == "pass"
    assert readiness_status["report_type"] == "PRODUCTION_READINESS_REPORT_v1_REPORT"
    assert readiness_status["production_readiness_level"] == "review_ready"
    assert readiness_status["readiness_decision"] == "blocked_for_execution"
    assert readiness_status["admitted_noop_receipt_candidate_ids"] == ["release_candidate_package_receipt_noop_v1"]
    assert readiness_status["receipt_backed_candidate_ids"] == ["release_candidate_package_receipt_noop_v1"]
    assert readiness_status["admitted_real_execution_candidate_ids"] == []
    assert readiness_status["admitted_publication_candidate_ids"] == []
    assert readiness_status["execution_admission_status"] == "blocked"
    assert readiness_status["real_execution_admission_status"] == "blocked"
    assert readiness_status["publication_admission_status"] == "blocked"
    assert readiness_status["reporter_return_code"] == 0
    assert Path(readiness_status["output_path"]).exists()
    receipt_status = payload["details"]["release_candidate_package_receipt_noop_report"]
    assert receipt_status["status"] == "pass"
    assert receipt_status["report_type"] == "RELEASE_CANDIDATE_PACKAGE_RECEIPT_NOOP_v1_REPORT"
    assert receipt_status["candidate_id"] == "release_candidate_package_receipt_noop_v1"
    assert receipt_status["command_mode"] == "noop"
    assert receipt_status["external_execution_performed"] is False
    assert receipt_status["publication_performed"] is False
    assert receipt_status["reporter_return_code"] == 0
    receipt_output_path = Path(receipt_status["output_path"])
    assert receipt_output_path.exists()
    receipt_output_path.unlink(missing_ok=True)
    controlled_inventory_status = payload["details"]["controlled_real_evidence_inventory_report"]
    assert controlled_inventory_status["status"] == "pass"
    assert controlled_inventory_status["report_type"] == "CONTROLLED_REAL_EVIDENCE_INVENTORY_v1_REPORT"
    assert controlled_inventory_status["inventory_mode"] == "approved_local_inputs_and_evidence_sources_only"
    assert controlled_inventory_status["execution_admitted"] is False
    assert controlled_inventory_status["reporter_return_code"] == 0
    assert Path(controlled_inventory_status["output_path"]).exists()
