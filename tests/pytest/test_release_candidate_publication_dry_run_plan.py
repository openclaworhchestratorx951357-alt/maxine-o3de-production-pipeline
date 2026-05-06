import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "maxine_release_candidate_publication_dry_run_plan.schema.json"
)
PLAN_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "release_candidate_package_publish_dry_run_plan_v1.json"
)
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_release_candidate_publication_dry_run_plan.py"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_validator(path: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    start = result.stdout.find("{")
    assert start >= 0, f"expected JSON output:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    return result.returncode, json.loads(result.stdout[start:])


def _clone_base_payload() -> dict:
    return copy.deepcopy(_load(PLAN_EXAMPLE))


def _finding_ids(payload: dict) -> set[str]:
    return {
        str(item.get("id", "")).strip()
        for item in payload.get("findings", [])
        if isinstance(item, dict)
    }


def _remove_token(items: list[str], token: str) -> list[str]:
    token_lower = token.lower()
    return [item for item in items if token_lower not in str(item).lower()]


def test_dry_run_plan_example_validates_and_reports_blocked_posture():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    payload = _load(PLAN_EXAMPLE)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, [f"{'.'.join(str(p) for p in err.path)}: {err.message}" for err in errors]

    code, report = _run_validator(PLAN_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["release_candidate_publication_dry_run_plan_present"] is True
    assert report["planned_candidate_id"] == "release_candidate_package_publish_dry_run_v1"
    assert report["candidate_type"] == "dry_run"
    assert report["plan_status"] == "static_plan_valid_blocked"
    assert report["dry_run_admitted"] is False
    assert report["publication_admitted"] is False
    assert report["real_execution_admitted"] is False
    assert report["production_ready_claimed"] is False
    assert report["publication_surfaces_blocked"] is True
    assert report["execution_surfaces_blocked"] is True
    assert report["missing_evidence_items_count"] > 0
    assert len(report["blocked_reason_codes"]) > 0
    assert (
        report["approval_phrase_required"]
        == "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
    )


def test_validator_cross_checks_matrix_preflight_proof_and_rollup():
    code, report = _run_validator(PLAN_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    source_status = report["computed_source_artifact_validation_status"]
    assert source_status["candidate_matrix_status"] == "pass"
    assert source_status["preflight_contracts_status"] == "pass"
    assert source_status["preflight_proof_packages_status"] == "pass"
    assert source_status["readiness_rollup_status"] == "pass"
    assert source_status["production_readiness_status"] == "pass"
    assert source_status["noop_receipt_status"] == "pass"


def test_validator_rejects_candidate_id_not_target(tmp_path: Path):
    payload = _clone_base_payload()
    payload["candidate_id"] = "wrong_candidate_v1"
    path = tmp_path / "invalid-candidate-id.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "candidate_id_mismatch" in _finding_ids(report)


def test_validator_rejects_candidate_type_not_dry_run(tmp_path: Path):
    payload = _clone_base_payload()
    payload["candidate_type"] = "publication"
    path = tmp_path / "invalid-candidate-type.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "candidate_type_mismatch" in _finding_ids(report)


def test_validator_rejects_admitted_flags_and_production_ready_claim(tmp_path: Path):
    payload = _clone_base_payload()
    payload["dry_run_admitted"] = True
    payload["publication_admitted"] = True
    payload["real_execution_admitted"] = True
    payload["production_ready_claimed"] = True
    path = tmp_path / "invalid-admitted-flags.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "dry_run_admitted_not_allowed" in finding_ids
    assert "publication_admitted_not_allowed" in finding_ids
    assert "real_execution_admitted_not_allowed" in finding_ids
    assert "production_ready_claim_not_allowed" in finding_ids


def test_validator_rejects_approval_phrase_mismatch_and_admission_reference(tmp_path: Path):
    payload = _clone_base_payload()
    payload["approval_phrase_required"] = "APPROVE EXECUTION ADMISSION wrong_id"
    payload["approval_decision_reference"] = "admitted::decision"
    path = tmp_path / "invalid-approval-fields.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "approval_phrase_required_mismatch" in finding_ids
    assert "approval_decision_reference_not_allowed" in finding_ids


def test_validator_rejects_plan_status_missing_evidence_and_blocked_reason_codes(tmp_path: Path):
    payload = _clone_base_payload()
    payload["plan_status"] = "static_plan_invalid"
    payload["missing_evidence_items"] = []
    payload["blocked_reason_codes"] = []
    path = tmp_path / "invalid-plan-status-and-missing-items.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "plan_status_not_static_plan_valid_blocked" in finding_ids
    assert "missing_evidence_items_empty" in finding_ids
    assert "blocked_reason_codes_empty" in finding_ids


def test_validator_rejects_publication_and_execution_surfaces_unblocked(tmp_path: Path):
    payload = _clone_base_payload()
    payload["publication_surfaces_blocked"] = False
    payload["execution_surfaces_blocked"] = False
    path = tmp_path / "invalid-surface-blocking-flags.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "publication_surfaces_blocked_false" in finding_ids
    assert "execution_surfaces_blocked_false" in finding_ids


def test_validator_rejects_future_allowed_outputs_in_production_engine_or_outside_sandbox(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    payload["future_allowed_sandbox_outputs"] = [
        "production/releases/output.json",
        "engine/build/output.json",
        "outside-sandbox/output.json",
    ]
    path = tmp_path / "invalid-future-allowed-outputs.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "future_allowed_sandbox_outputs_contains_production_path" in finding_ids
    assert "future_allowed_sandbox_outputs_contains_engine_path" in finding_ids
    assert "future_allowed_sandbox_outputs_outside_sandbox" in finding_ids


def test_validator_rejects_forbidden_paths_missing_required_categories(tmp_path: Path):
    payload = _clone_base_payload()
    payload["forbidden_paths"] = []
    path = tmp_path / "invalid-forbidden-paths.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "forbidden_paths_missing_production_category" in finding_ids
    assert "forbidden_paths_missing_engine_category" in finding_ids
    assert "forbidden_paths_missing_cache_live_db_category" in finding_ids
    assert "forbidden_paths_missing_destructive_cleanup_category" in finding_ids


def test_validator_rejects_plan_that_allows_publish_or_spawn(tmp_path: Path):
    payload = _clone_base_payload()
    payload["out_of_scope_surfaces"] = _remove_token(
        _remove_token(payload["out_of_scope_surfaces"], "publication_execution"),
        "spawn_execution",
    )
    payload["forbidden_outputs"] = _remove_token(
        _remove_token(payload["forbidden_outputs"], "publish"),
        "spawn",
    )
    path = tmp_path / "invalid-plan-allows-publish-spawn.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "plan_allows_publish" in finding_ids
    assert "plan_allows_spawn" in finding_ids


def test_validator_rejects_plan_that_allows_production_engine_or_cache_live_db_access(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    payload["out_of_scope_surfaces"] = _remove_token(
        _remove_token(
            _remove_token(payload["out_of_scope_surfaces"], "production_path_write"),
            "engine_path_write",
        ),
        "cache_live_db_access",
    )
    path = tmp_path / "invalid-plan-allows-prod-engine-cache.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "plan_allows_production_path_writes" in finding_ids
    assert "plan_allows_engine_path_writes" in finding_ids
    assert "plan_allows_cache_live_db_access" in finding_ids


def test_validator_rejects_authoritative_claim_status(tmp_path: Path):
    payload = _clone_base_payload()
    payload["claim_status"]["source_uuid_status"] = "authoritative"
    payload["claim_status"]["asset_id_status"] = "authoritative"
    payload["claim_status"]["product_id_status"] = "authoritative"
    path = tmp_path / "invalid-authoritative-claim-status.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "authoritative_source_uuid_claim_allowed" in finding_ids
    assert "authoritative_asset_id_claim_allowed" in finding_ids
    assert "authoritative_product_id_claim_allowed" in finding_ids


def test_validator_rejects_readiness_rollup_alignment_mismatch(tmp_path: Path):
    payload = _clone_base_payload()
    payload["readiness_rollup_alignment"]["safest_next_preparation_candidate_id"] = (
        "release_candidate_package_publication_v1"
    )
    path = tmp_path / "invalid-readiness-rollup-alignment.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "readiness_rollup_alignment_candidate_mismatch" in _finding_ids(report)


def test_validator_rejects_readiness_rollup_mismatch_target_candidate(tmp_path: Path):
    payload = _clone_base_payload()
    rollup = _load(
        REPO_ROOT
        / "examples"
        / "execution-admission"
        / "execution_admission_readiness_rollup_v1.json"
    )
    rollup["safest_next_preparation_slice"]["candidate_id"] = "release_candidate_package_publication_v1"
    rollup_path = tmp_path / "invalid-rollup-mismatch-target.json"
    _write(rollup_path, rollup)
    payload["source_artifacts"]["readiness_rollup_ref"] = str(rollup_path)
    path = tmp_path / "invalid-plan-rollup-target-mismatch.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "readiness_rollup_validation_failed" in finding_ids
    assert "readiness_rollup_safest_next_candidate_mismatch" in finding_ids


def test_validator_rejects_next_slice_when_it_admits_execution_or_publication(tmp_path: Path):
    payload = _clone_base_payload()
    rollup = _load(
        REPO_ROOT
        / "examples"
        / "execution-admission"
        / "execution_admission_readiness_rollup_v1.json"
    )
    rollup["safest_next_preparation_slice"]["admits_execution"] = True
    rollup["safest_next_preparation_slice"]["admits_publication"] = True
    rollup_path = tmp_path / "invalid-rollup-admits-exec-pub.json"
    _write(rollup_path, rollup)
    payload["source_artifacts"]["readiness_rollup_ref"] = str(rollup_path)
    path = tmp_path / "invalid-plan-rollup-admits-exec-pub.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "readiness_rollup_validation_failed" in finding_ids
    assert "real_execution_admitted_not_allowed" in finding_ids
    assert "plan_allows_publish" in finding_ids
