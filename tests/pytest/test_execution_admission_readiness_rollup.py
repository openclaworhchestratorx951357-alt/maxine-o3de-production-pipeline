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
    / "maxine_execution_admission_readiness_rollup.schema.json"
)
ROLLUP_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "execution_admission_readiness_rollup_v1.json"
)
MATRIX_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "execution_admission_candidate_matrix_v1.json"
)
PREFLIGHT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "execution_admission_preflight_contracts_v1.json"
)
PREFLIGHT_PROOF_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "execution_admission_preflight_proof_packages_v1.json"
)
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_execution_admission_readiness_rollup.py"
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


def _finding_ids(payload: dict) -> set[str]:
    return {
        str(item.get("id", "")).strip()
        for item in payload.get("findings", [])
        if isinstance(item, dict)
    }


def _find_rollup_candidate(payload: dict, candidate_id: str) -> dict:
    for item in payload.get("candidate_rollups", []):
        if (
            isinstance(item, dict)
            and str(item.get("candidate_id", "")).strip() == candidate_id
        ):
            return item
    raise AssertionError(f"rollup candidate not found: {candidate_id}")


def _clone_base_payload() -> dict:
    return copy.deepcopy(_load(ROLLUP_EXAMPLE))


def test_readiness_rollup_example_validates_and_reports_blocked_posture():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    payload = _load(ROLLUP_EXAMPLE)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, [f"{'.'.join(str(p) for p in err.path)}: {err.message}" for err in errors]

    code, report = _run_validator(ROLLUP_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["execution_admission_readiness_rollup_present"] is True
    assert report["overall_readiness_rollup_status"] == "static_rollup_valid_blocked"
    assert report["admitted_noop_receipt_candidate_ids"] == [
        "release_candidate_package_receipt_noop_v1"
    ]
    assert report["admitted_real_execution_candidate_ids"] == []
    assert report["admitted_publication_candidate_ids"] == []
    assert report["real_execution_preflight_passed_candidate_ids"] == []
    assert report["publication_preflight_passed_candidate_ids"] == []
    assert report["real_execution_admission_status"] == "blocked"
    assert report["publication_admission_status"] == "blocked"
    assert report["production_ready_claimed"] is False
    assert report["unsafe_claims_detected"] is False


def test_validator_cross_checks_matrix_contracts_and_preflight_proof_validators():
    code, report = _run_validator(ROLLUP_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    source_status = report["source_artifact_validation_status"]
    assert source_status["candidate_matrix_status"] == "pass"
    assert source_status["preflight_contracts_status"] == "pass"
    assert source_status["preflight_proof_packages_status"] == "pass"


def test_every_matrix_contract_and_preflight_proof_candidate_has_rollup_entry():
    rollup = _load(ROLLUP_EXAMPLE)
    matrix = _load(MATRIX_EXAMPLE)
    preflight = _load(PREFLIGHT_EXAMPLE)
    preflight_proof = _load(PREFLIGHT_PROOF_EXAMPLE)

    rollup_map = {
        str(item.get("candidate_id", "")).strip(): str(item.get("candidate_type", "")).strip()
        for item in rollup.get("candidate_rollups", [])
        if isinstance(item, dict)
    }
    matrix_map = {
        str(item.get("candidate_id", "")).strip(): str(item.get("candidate_type", "")).strip()
        for item in matrix.get("candidates", [])
        if isinstance(item, dict)
    }
    preflight_map = {
        str(item.get("candidate_id", "")).strip(): str(item.get("candidate_type", "")).strip()
        for item in preflight.get("contracts", [])
        if isinstance(item, dict)
    }
    proof_map = {
        str(item.get("candidate_id", "")).strip(): str(item.get("candidate_type", "")).strip()
        for item in preflight_proof.get("proof_packages", [])
        if isinstance(item, dict)
    }

    assert set(rollup_map) == set(matrix_map)
    assert set(rollup_map) == set(preflight_map)
    assert set(rollup_map) == set(proof_map)
    for candidate_id, candidate_type in rollup_map.items():
        assert matrix_map[candidate_id] == candidate_type
        assert preflight_map[candidate_id] == candidate_type
        assert proof_map[candidate_id] == candidate_type


def test_validator_accepts_noop_only_admitted_noop_satisfied_rollup():
    payload = _clone_base_payload()
    noop = _find_rollup_candidate(payload, "release_candidate_package_receipt_noop_v1")
    assert noop["candidate_type"] == "no_op_receipt"
    assert noop["admission_status"] == "admitted_no_op_only"
    assert noop["proof_package_status"] in {
        "satisfied_no_op_only",
        "satisfied_non_execution_only",
    }
    code, report = _run_validator(ROLLUP_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"


def test_validator_rejects_noop_candidate_misclassified_as_real_execution(tmp_path: Path):
    payload = _clone_base_payload()
    _find_rollup_candidate(payload, "release_candidate_package_receipt_noop_v1")[
        "candidate_type"
    ] = "real_execution"
    path = tmp_path / "invalid-noop-real.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "noop_candidate_misclassified_as_real_execution" in _finding_ids(report)


def test_validator_rejects_noop_candidate_misclassified_as_publication(tmp_path: Path):
    payload = _clone_base_payload()
    _find_rollup_candidate(payload, "release_candidate_package_receipt_noop_v1")[
        "candidate_type"
    ] = "publication"
    path = tmp_path / "invalid-noop-publication.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "noop_candidate_misclassified_as_publication" in _finding_ids(report)


def test_validator_rejects_noop_candidate_marked_admitted_real_execution(tmp_path: Path):
    payload = _clone_base_payload()
    _find_rollup_candidate(payload, "release_candidate_package_receipt_noop_v1")[
        "admission_status"
    ] = "admitted_real_execution"
    path = tmp_path / "invalid-noop-admitted-real.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "noop_candidate_marked_admitted_real_execution" in _finding_ids(report)


def test_validator_rejects_noop_candidate_marked_admitted_publication(tmp_path: Path):
    payload = _clone_base_payload()
    _find_rollup_candidate(payload, "release_candidate_package_receipt_noop_v1")[
        "admission_status"
    ] = "admitted_publication"
    path = tmp_path / "invalid-noop-admitted-publication.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "noop_candidate_marked_admitted_publication" in _finding_ids(report)


def test_validator_rejects_future_real_execution_candidate_listed_as_admitted(tmp_path: Path):
    payload = _clone_base_payload()
    _find_rollup_candidate(payload, "dcc_conform_execution_v1")[
        "admission_status"
    ] = "admitted_real_execution"
    path = tmp_path / "invalid-future-real-admitted.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "future_real_execution_candidate_admitted_not_allowed" in _finding_ids(report)


def test_validator_rejects_future_publication_candidate_listed_as_admitted(tmp_path: Path):
    payload = _clone_base_payload()
    _find_rollup_candidate(payload, "release_candidate_package_publication_v1")[
        "admission_status"
    ] = "admitted_publication"
    path = tmp_path / "invalid-future-publication-admitted.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "future_publication_candidate_admitted_not_allowed" in _finding_ids(report)


def test_validator_rejects_future_real_execution_preflight_passed(tmp_path: Path):
    payload = _clone_base_payload()
    _find_rollup_candidate(payload, "dcc_conform_execution_v1")["preflight_passed"] = True
    path = tmp_path / "invalid-future-real-preflight-passed.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "future_real_execution_candidate_preflight_passed_not_allowed" in _finding_ids(report)


def test_validator_rejects_future_publication_preflight_passed(tmp_path: Path):
    payload = _clone_base_payload()
    _find_rollup_candidate(payload, "release_candidate_package_publication_v1")[
        "preflight_passed"
    ] = True
    path = tmp_path / "invalid-future-publication-preflight-passed.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "future_publication_candidate_preflight_passed_not_allowed" in _finding_ids(report)


def test_validator_rejects_non_empty_admitted_real_execution_candidate_ids(tmp_path: Path):
    payload = _clone_base_payload()
    payload["admitted_real_execution_candidate_ids"] = ["dcc_conform_execution_v1"]
    path = tmp_path / "invalid-admitted-real-ids.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "admitted_real_execution_candidate_ids_not_empty" in _finding_ids(report)


def test_validator_rejects_non_empty_admitted_publication_candidate_ids(tmp_path: Path):
    payload = _clone_base_payload()
    payload["admitted_publication_candidate_ids"] = ["release_candidate_package_publication_v1"]
    path = tmp_path / "invalid-admitted-publication-ids.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "admitted_publication_candidate_ids_not_empty" in _finding_ids(report)


def test_validator_rejects_non_empty_real_execution_preflight_passed_candidate_ids(tmp_path: Path):
    payload = _clone_base_payload()
    payload["real_execution_preflight_passed_candidate_ids"] = ["dcc_conform_execution_v1"]
    path = tmp_path / "invalid-real-preflight-passed-ids.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "real_execution_preflight_passed_candidate_ids_not_empty" in _finding_ids(report)


def test_validator_rejects_non_empty_publication_preflight_passed_candidate_ids(tmp_path: Path):
    payload = _clone_base_payload()
    payload["publication_preflight_passed_candidate_ids"] = [
        "release_candidate_package_publication_v1"
    ]
    path = tmp_path / "invalid-publication-preflight-passed-ids.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "publication_preflight_passed_candidate_ids_not_empty" in _finding_ids(report)


def test_validator_rejects_production_ready_claim(tmp_path: Path):
    payload = _clone_base_payload()
    payload["production_ready_claimed"] = True
    path = tmp_path / "invalid-production-ready-claimed.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "production_ready_claim_not_allowed" in _finding_ids(report)


def test_validator_rejects_real_execution_admission_status_admitted(tmp_path: Path):
    payload = _clone_base_payload()
    payload["real_execution_admission_status"] = "admitted"
    path = tmp_path / "invalid-real-execution-status-admitted.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "real_execution_admission_status_not_blocked" in _finding_ids(report)


def test_validator_rejects_publication_admission_status_admitted(tmp_path: Path):
    payload = _clone_base_payload()
    payload["publication_admission_status"] = "admitted"
    path = tmp_path / "invalid-publication-status-admitted.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "publication_admission_status_not_blocked" in _finding_ids(report)


def test_validator_rejects_dry_run_candidate_treated_as_publication_admission(tmp_path: Path):
    payload = _clone_base_payload()
    _find_rollup_candidate(payload, "release_candidate_package_publish_dry_run_v1")[
        "admission_status"
    ] = "admitted_publication"
    path = tmp_path / "invalid-dry-run-publication-admission.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "dry_run_candidate_treated_as_real_or_publication_admission" in _finding_ids(report)


def test_validator_rejects_safest_next_slice_if_it_admits_execution_or_publication(tmp_path: Path):
    payload = _clone_base_payload()
    payload["safest_next_preparation_slice"]["admits_execution"] = True
    payload["safest_next_preparation_slice"]["admits_publication"] = True
    path = tmp_path / "invalid-safest-next-slice-admits.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "safest_next_slice_admits_execution" in finding_ids
    assert "safest_next_slice_admits_publication" in finding_ids


def test_validator_rejects_safest_next_slice_without_required_future_pr_or_explicit_approval(
    tmp_path: Path,
):
    payload = _clone_base_payload()
    payload["safest_next_preparation_slice"]["requires_future_pr"] = False
    payload["safest_next_preparation_slice"][
        "requires_explicit_approval_before_admission"
    ] = False
    path = tmp_path / "invalid-safest-next-slice-requirements.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "safest_next_slice_requires_future_pr_false" in finding_ids
    assert "safest_next_slice_requires_explicit_approval_false" in finding_ids


def test_validator_rejects_rollup_claims_that_allow_production_engine_or_cache_writes(tmp_path: Path):
    payload = _clone_base_payload()
    payload["safety"]["production_write_status"] = "allowed"
    payload["safety"]["engine_write_status"] = "allowed"
    payload["safety"]["cache_live_db_access_status"] = "allowed"
    path = tmp_path / "invalid-unsafe-safety-surface-claims.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "production_path_write_allowed_claim" in finding_ids
    assert "engine_path_write_allowed_claim" in finding_ids
    assert "cache_live_db_access_allowed_claim" in finding_ids
