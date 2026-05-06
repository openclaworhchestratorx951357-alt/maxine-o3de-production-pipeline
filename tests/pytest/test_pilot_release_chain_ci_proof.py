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
    candidate_matrix_status = payload["details"]["execution_admission_candidate_matrix_report"]
    assert candidate_matrix_status["status"] == "pass"
    assert (
        candidate_matrix_status["report_type"]
        == "EXECUTION_ADMISSION_CANDIDATE_MATRIX_VALIDATION_v1_REPORT"
    )
    assert candidate_matrix_status["candidate_matrix_present"] is True
    assert candidate_matrix_status["admitted_noop_receipt_candidate_ids"] == [
        "release_candidate_package_receipt_noop_v1"
    ]
    assert candidate_matrix_status["admitted_real_execution_candidate_ids"] == []
    assert candidate_matrix_status["admitted_publication_candidate_ids"] == []
    assert candidate_matrix_status["real_execution_admission_status"] == "blocked"
    assert candidate_matrix_status["publication_admission_status"] == "blocked"
    assert "dcc_conform_execution_v1" in candidate_matrix_status["proposed_or_blocked_real_execution_candidate_ids"]
    assert "release_candidate_package_publication_v1" in candidate_matrix_status[
        "proposed_or_blocked_publication_candidate_ids"
    ]
    assert "release_candidate_package_publish_dry_run_v1" in candidate_matrix_status[
        "proposed_or_blocked_dry_run_candidate_ids"
    ]
    assert candidate_matrix_status["reporter_return_code"] == 0
    preflight_status = payload["details"]["execution_admission_preflight_contracts_report"]
    assert preflight_status["status"] == "pass"
    assert (
        preflight_status["report_type"]
        == "EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_VALIDATION_v1_REPORT"
    )
    assert preflight_status["preflight_contracts_present"] is True
    assert preflight_status["admitted_noop_receipt_candidate_ids"] == [
        "release_candidate_package_receipt_noop_v1"
    ]
    assert preflight_status["admitted_real_execution_candidate_ids"] == []
    assert preflight_status["admitted_publication_candidate_ids"] == []
    assert preflight_status["real_execution_preflight_passed_candidate_ids"] == []
    assert preflight_status["publication_preflight_passed_candidate_ids"] == []
    assert preflight_status["real_execution_admission_status"] == "blocked"
    assert preflight_status["publication_admission_status"] == "blocked"
    assert preflight_status["production_ready_claimed"] is False
    assert "dcc_conform_execution_v1" in preflight_status["preflight_contract_candidate_ids"]
    assert "release_candidate_package_publication_v1" in preflight_status[
        "preflight_contract_candidate_ids"
    ]
    assert preflight_status["reporter_return_code"] == 0
    preflight_proof_status = payload["details"]["execution_admission_preflight_proof_packages_report"]
    assert preflight_proof_status["status"] == "pass"
    assert (
        preflight_proof_status["report_type"]
        == "EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_VALIDATION_v1_REPORT"
    )
    assert preflight_proof_status["preflight_proof_packages_present"] is True
    assert preflight_proof_status["admitted_noop_receipt_candidate_ids"] == [
        "release_candidate_package_receipt_noop_v1"
    ]
    assert preflight_proof_status["admitted_real_execution_candidate_ids"] == []
    assert preflight_proof_status["admitted_publication_candidate_ids"] == []
    assert preflight_proof_status["real_execution_preflight_passed_candidate_ids"] == []
    assert preflight_proof_status["publication_preflight_passed_candidate_ids"] == []
    assert preflight_proof_status["real_execution_admission_status"] == "blocked"
    assert preflight_proof_status["publication_admission_status"] == "blocked"
    assert preflight_proof_status["production_ready_claimed"] is False
    assert "dcc_conform_execution_v1" in preflight_proof_status[
        "blocked_real_execution_preflight_candidate_ids"
    ]
    assert "release_candidate_package_publication_v1" in preflight_proof_status[
        "blocked_publication_preflight_candidate_ids"
    ]
    assert "release_candidate_package_publish_dry_run_v1" in preflight_proof_status[
        "blocked_dry_run_preflight_candidate_ids"
    ]
    assert preflight_proof_status["reporter_return_code"] == 0
    readiness_rollup_status = payload["details"]["execution_admission_readiness_rollup_report"]
    assert readiness_rollup_status["status"] == "pass"
    assert (
        readiness_rollup_status["report_type"]
        == "EXECUTION_ADMISSION_READINESS_ROLLUP_VALIDATION_v1_REPORT"
    )
    assert readiness_rollup_status["execution_admission_readiness_rollup_present"] is True
    assert readiness_rollup_status["overall_readiness_rollup_status"] == "static_rollup_valid_blocked"
    assert readiness_rollup_status["admitted_noop_receipt_candidate_ids"] == [
        "release_candidate_package_receipt_noop_v1"
    ]
    assert readiness_rollup_status["admitted_real_execution_candidate_ids"] == []
    assert readiness_rollup_status["admitted_publication_candidate_ids"] == []
    assert readiness_rollup_status["real_execution_preflight_passed_candidate_ids"] == []
    assert readiness_rollup_status["publication_preflight_passed_candidate_ids"] == []
    assert "dcc_conform_execution_v1" in readiness_rollup_status[
        "blocked_real_execution_candidate_ids"
    ]
    assert "release_candidate_package_publication_v1" in readiness_rollup_status[
        "blocked_publication_candidate_ids"
    ]
    assert "release_candidate_package_publish_dry_run_v1" in readiness_rollup_status[
        "blocked_dry_run_candidate_ids"
    ]
    assert readiness_rollup_status["real_execution_admission_status"] == "blocked"
    assert readiness_rollup_status["publication_admission_status"] == "blocked"
    assert readiness_rollup_status["production_ready_claimed"] is False
    assert readiness_rollup_status["unsafe_claims_detected"] is False
    next_slice = readiness_rollup_status["safest_next_preparation_slice"]
    assert next_slice["slice_id"] == "candidate_specific_dry_run_planning_v1"
    assert next_slice["candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert next_slice["admits_execution"] is False
    assert next_slice["admits_publication"] is False
    assert next_slice["requires_future_pr"] is True
    assert next_slice["requires_explicit_approval_before_admission"] is True
    assert readiness_rollup_status["reporter_return_code"] == 0
    dry_run_plan_status = payload["details"]["release_candidate_publication_dry_run_plan_report"]
    assert dry_run_plan_status["status"] == "pass"
    assert (
        dry_run_plan_status["report_type"]
        == "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_VALIDATION_v1_REPORT"
    )
    assert dry_run_plan_status["release_candidate_publication_dry_run_plan_present"] is True
    assert dry_run_plan_status["planned_candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert dry_run_plan_status["candidate_type"] == "dry_run"
    assert dry_run_plan_status["plan_status"] == "static_plan_valid_blocked"
    assert dry_run_plan_status["dry_run_admitted"] is False
    assert dry_run_plan_status["publication_admitted"] is False
    assert dry_run_plan_status["real_execution_admitted"] is False
    assert dry_run_plan_status["production_ready_claimed"] is False
    assert dry_run_plan_status["publication_surfaces_blocked"] is True
    assert dry_run_plan_status["execution_surfaces_blocked"] is True
    assert dry_run_plan_status["missing_evidence_items_count"] > 0
    assert len(dry_run_plan_status["blocked_reason_codes"]) > 0
    assert (
        dry_run_plan_status["approval_phrase_required"]
        == "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
    )
    dry_run_alignment = dry_run_plan_status["readiness_rollup_alignment"]
    assert dry_run_alignment["safest_next_preparation_slice_id"] == "candidate_specific_dry_run_planning_v1"
    assert dry_run_alignment["safest_next_preparation_candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert dry_run_alignment["alignment_status"] == "aligned"
    source_status = dry_run_plan_status["computed_source_artifact_validation_status"]
    assert source_status["candidate_matrix_status"] == "pass"
    assert source_status["preflight_contracts_status"] == "pass"
    assert source_status["preflight_proof_packages_status"] == "pass"
    assert source_status["readiness_rollup_status"] == "pass"
    assert source_status["production_readiness_status"] == "pass"
    assert source_status["noop_receipt_status"] == "pass"
    assert dry_run_plan_status["reporter_return_code"] == 0
    dry_run_receipt_contract_status = payload["details"]["release_candidate_publication_dry_run_receipt_contract_report"]
    assert dry_run_receipt_contract_status["status"] == "pass"
    assert (
        dry_run_receipt_contract_status["report_type"]
        == "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_CONTRACT_VALIDATION_v1_REPORT"
    )
    assert (
        dry_run_receipt_contract_status["release_candidate_publication_dry_run_receipt_contract_present"]
        is True
    )
    assert dry_run_receipt_contract_status["planned_candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert dry_run_receipt_contract_status["candidate_type"] == "dry_run"
    assert (
        dry_run_receipt_contract_status["receipt_type"]
        == "release_candidate_package_publish_dry_run_receipt_v1"
    )
    assert dry_run_receipt_contract_status["receipt_contract_status"] == "static_contract_valid_blocked"
    assert dry_run_receipt_contract_status["receipt_issued"] is False
    assert dry_run_receipt_contract_status["dry_run_admitted"] is False
    assert dry_run_receipt_contract_status["publication_admitted"] is False
    assert dry_run_receipt_contract_status["real_execution_admitted"] is False
    assert dry_run_receipt_contract_status["production_ready_claimed"] is False
    assert dry_run_receipt_contract_status["publication_surfaces_blocked"] is True
    assert dry_run_receipt_contract_status["execution_surfaces_blocked"] is True
    assert dry_run_receipt_contract_status["cache_live_db_access_blocked"] is True
    assert dry_run_receipt_contract_status["authoritative_id_claims_blocked"] is True
    assert dry_run_receipt_contract_status["missing_evidence_items_count"] > 0
    assert len(dry_run_receipt_contract_status["blocked_reason_codes"]) > 0
    assert (
        dry_run_receipt_contract_status["approval_phrase_required"]
        == "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
    )
    receipt_source_status = dry_run_receipt_contract_status["computed_source_artifact_validation_status"]
    assert receipt_source_status["candidate_matrix_status"] == "pass"
    assert receipt_source_status["preflight_contracts_status"] == "pass"
    assert receipt_source_status["preflight_proof_packages_status"] == "pass"
    assert receipt_source_status["readiness_rollup_status"] == "pass"
    assert receipt_source_status["dry_run_plan_status"] == "pass"
    assert receipt_source_status["production_readiness_status"] == "pass"
    assert receipt_source_status["noop_receipt_status"] == "pass"
    receipt_rollup_alignment = dry_run_receipt_contract_status["readiness_rollup_alignment"]
    assert receipt_rollup_alignment["safest_next_preparation_slice_id"] == "candidate_specific_dry_run_planning_v1"
    assert receipt_rollup_alignment["safest_next_preparation_candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert receipt_rollup_alignment["alignment_status"] == "aligned"
    receipt_plan_alignment = dry_run_receipt_contract_status["dry_run_plan_alignment"]
    assert receipt_plan_alignment["planned_candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert receipt_plan_alignment["alignment_status"] == "aligned"
    assert dry_run_receipt_contract_status["reporter_return_code"] == 0
    dry_run_admission_blockers_status = payload["details"][
        "release_candidate_publication_dry_run_admission_blockers_report"
    ]
    assert dry_run_admission_blockers_status["status"] == "pass"
    assert (
        dry_run_admission_blockers_status["report_type"]
        == "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_ADMISSION_BLOCKERS_VALIDATION_v1_REPORT"
    )
    assert (
        dry_run_admission_blockers_status[
            "release_candidate_publication_dry_run_admission_blockers_present"
        ]
        is True
    )
    assert (
        dry_run_admission_blockers_status["planned_candidate_id"]
        == "release_candidate_package_publish_dry_run_v1"
    )
    assert dry_run_admission_blockers_status["candidate_type"] == "dry_run"
    assert dry_run_admission_blockers_status["checklist_status"] == "static_checklist_valid_blocked"
    assert dry_run_admission_blockers_status["admission_status"] == "unadmitted"
    assert dry_run_admission_blockers_status["approval_review_ready"] is False
    assert dry_run_admission_blockers_status["ready_to_request_approval"] is False
    assert dry_run_admission_blockers_status["dry_run_admitted"] is False
    assert dry_run_admission_blockers_status["receipt_issued"] is False
    assert dry_run_admission_blockers_status["publication_admitted"] is False
    assert dry_run_admission_blockers_status["real_execution_admitted"] is False
    assert dry_run_admission_blockers_status["production_ready_claimed"] is False
    assert (
        dry_run_admission_blockers_status["approval_phrase_required"]
        == "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
    )
    assert len(dry_run_admission_blockers_status["admission_blockers"]) > 0
    assert len(dry_run_admission_blockers_status["approval_blockers"]) > 0
    assert len(dry_run_admission_blockers_status["evidence_blockers"]) > 0
    assert len(dry_run_admission_blockers_status["receipt_blockers"]) > 0
    assert len(dry_run_admission_blockers_status["rollback_or_cleanup_blockers"]) > 0
    assert len(dry_run_admission_blockers_status["publication_blockers"]) > 0
    assert len(dry_run_admission_blockers_status["execution_blockers"]) > 0
    blockers_source_status = dry_run_admission_blockers_status[
        "computed_source_artifact_validation_status"
    ]
    assert blockers_source_status["candidate_matrix_status"] == "pass"
    assert blockers_source_status["preflight_contracts_status"] == "pass"
    assert blockers_source_status["preflight_proof_packages_status"] == "pass"
    assert blockers_source_status["readiness_rollup_status"] == "pass"
    assert blockers_source_status["dry_run_plan_status"] == "pass"
    assert blockers_source_status["dry_run_receipt_contract_status"] == "pass"
    assert blockers_source_status["blocked_unissued_receipt_status"] == "pass"
    assert blockers_source_status["production_readiness_status"] == "pass"
    assert blockers_source_status["noop_receipt_status"] == "pass"
    assert dry_run_admission_blockers_status["reporter_return_code"] == 0
    dry_run_operator_packet_status = payload["details"][
        "release_candidate_publication_dry_run_operator_approval_packet_report"
    ]
    assert dry_run_operator_packet_status["status"] == "pass"
    assert (
        dry_run_operator_packet_status["report_type"]
        == "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_OPERATOR_APPROVAL_PACKET_VALIDATION_v1_REPORT"
    )
    assert (
        dry_run_operator_packet_status[
            "release_candidate_publication_dry_run_operator_approval_packet_present"
        ]
        is True
    )
    assert (
        dry_run_operator_packet_status["planned_candidate_id"]
        == "release_candidate_package_publish_dry_run_v1"
    )
    assert dry_run_operator_packet_status["candidate_type"] == "dry_run"
    assert (
        dry_run_operator_packet_status["approval_packet_status"]
        == "static_template_valid_blocked"
    )
    assert dry_run_operator_packet_status["admission_status"] == "unadmitted"
    assert dry_run_operator_packet_status["approval_request_ready"] is False
    assert dry_run_operator_packet_status["operator_approval_granted"] is False
    assert dry_run_operator_packet_status["approval_phrase_present"] is False
    assert dry_run_operator_packet_status["dry_run_admitted"] is False
    assert dry_run_operator_packet_status["receipt_issued"] is False
    assert dry_run_operator_packet_status["publication_admitted"] is False
    assert dry_run_operator_packet_status["real_execution_admitted"] is False
    assert dry_run_operator_packet_status["production_ready_claimed"] is False
    assert (
        dry_run_operator_packet_status["approval_phrase_required"]
        == "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
    )
    assert len(dry_run_operator_packet_status["approval_blocker_summary"]) > 0
    assert len(dry_run_operator_packet_status["required_operator_review_items"]) > 0
    assert len(dry_run_operator_packet_status["required_validation_commands"]) > 0
    assert len(dry_run_operator_packet_status["blocked_surface_attestations"]) > 0
    assert len(dry_run_operator_packet_status["forbidden_actions"]) > 0
    assert len(dry_run_operator_packet_status["forbidden_outputs"]) > 0
    assert len(dry_run_operator_packet_status["forbidden_paths"]) > 0
    operator_source_status = dry_run_operator_packet_status[
        "computed_source_artifact_validation_status"
    ]
    assert operator_source_status["candidate_matrix_status"] == "pass"
    assert operator_source_status["preflight_contracts_status"] == "pass"
    assert operator_source_status["preflight_proof_packages_status"] == "pass"
    assert operator_source_status["readiness_rollup_status"] == "pass"
    assert operator_source_status["dry_run_plan_status"] == "pass"
    assert operator_source_status["dry_run_receipt_contract_status"] == "pass"
    assert operator_source_status["blocked_unissued_receipt_status"] == "pass"
    assert operator_source_status["admission_blocker_checklist_status"] == "pass"
    assert operator_source_status["production_readiness_status"] == "pass"
    assert operator_source_status["noop_receipt_status"] == "pass"
    assert dry_run_operator_packet_status["reporter_return_code"] == 0
