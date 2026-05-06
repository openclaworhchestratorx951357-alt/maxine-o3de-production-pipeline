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
    / "maxine_execution_admission_preflight_contracts.schema.json"
)
PREFLIGHT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "execution_admission_preflight_contracts_v1.json"
)
MATRIX_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "execution_admission_candidate_matrix_v1.json"
)
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_execution_admission_preflight_contracts.py"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_validator(path: Path, matrix_path: Path | None = None) -> tuple[int, dict]:
    cmd = [sys.executable, str(VALIDATOR), str(path)]
    if matrix_path is not None:
        cmd.extend(["--matrix-path", str(matrix_path)])
    result = subprocess.run(
        cmd,
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


def _find_contract(payload: dict, candidate_id: str) -> dict:
    for contract in payload.get("contracts", []):
        if isinstance(contract, dict) and str(contract.get("candidate_id", "")).strip() == candidate_id:
            return contract
    raise AssertionError(f"contract not found: {candidate_id}")


def _clone_base_payload() -> dict:
    return copy.deepcopy(_load(PREFLIGHT_EXAMPLE))


def test_preflight_example_validates_and_reports_blocked_posture():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    payload = _load(PREFLIGHT_EXAMPLE)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, [f"{'.'.join(str(p) for p in err.path)}: {err.message}" for err in errors]

    code, report = _run_validator(PREFLIGHT_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["preflight_contracts_present"] is True
    assert report["admitted_noop_receipt_candidate_ids"] == ["release_candidate_package_receipt_noop_v1"]
    assert report["admitted_real_execution_candidate_ids"] == []
    assert report["admitted_publication_candidate_ids"] == []
    assert report["real_execution_preflight_passed_candidate_ids"] == []
    assert report["publication_preflight_passed_candidate_ids"] == []
    assert report["real_execution_admission_status"] == "blocked"
    assert report["publication_admission_status"] == "blocked"
    assert report["production_ready_claimed"] is False


def test_every_matrix_candidate_has_preflight_contract_and_every_contract_has_matrix_candidate():
    payload = _load(PREFLIGHT_EXAMPLE)
    matrix = _load(MATRIX_EXAMPLE)

    matrix_ids = {
        str(item.get("candidate_id", "")).strip()
        for item in matrix.get("candidates", [])
        if isinstance(item, dict)
    }
    contract_ids = {
        str(item.get("candidate_id", "")).strip()
        for item in payload.get("contracts", [])
        if isinstance(item, dict)
    }
    assert matrix_ids == contract_ids

    code, report = _run_validator(PREFLIGHT_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"


def test_validator_rejects_noop_contract_when_misclassified_as_real_execution(tmp_path: Path):
    payload = _clone_base_payload()
    noop = _find_contract(payload, "release_candidate_package_receipt_noop_v1")
    noop["candidate_type"] = "real_execution"
    path = tmp_path / "invalid-noop-real.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "noop_candidate_misclassified_as_real_execution" in _finding_ids(report)


def test_validator_rejects_noop_contract_when_misclassified_as_publication(tmp_path: Path):
    payload = _clone_base_payload()
    noop = _find_contract(payload, "release_candidate_package_receipt_noop_v1")
    noop["candidate_type"] = "publication"
    path = tmp_path / "invalid-noop-publication.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "noop_candidate_misclassified_as_publication" in _finding_ids(report)


def test_validator_rejects_noop_contract_when_marked_admitted_real_execution(tmp_path: Path):
    payload = _clone_base_payload()
    noop = _find_contract(payload, "release_candidate_package_receipt_noop_v1")
    noop["admission_status"] = "admitted_real_execution"
    path = tmp_path / "invalid-noop-admitted-real.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "noop_candidate_marked_admitted_real_execution" in _finding_ids(report)


def test_validator_rejects_noop_contract_when_marked_admitted_publication(tmp_path: Path):
    payload = _clone_base_payload()
    noop = _find_contract(payload, "release_candidate_package_receipt_noop_v1")
    noop["admission_status"] = "admitted_publication"
    path = tmp_path / "invalid-noop-admitted-publication.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "noop_candidate_marked_admitted_publication" in _finding_ids(report)


def test_validator_rejects_future_real_execution_candidate_marked_admitted(tmp_path: Path):
    payload = _clone_base_payload()
    contract = _find_contract(payload, "dcc_conform_execution_v1")
    contract["admission_status"] = "admitted_real_execution"
    path = tmp_path / "invalid-real-admitted.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "real_execution_candidate_admitted_not_allowed" in _finding_ids(report)


def test_validator_rejects_future_publication_candidate_marked_admitted(tmp_path: Path):
    payload = _clone_base_payload()
    contract = _find_contract(payload, "release_candidate_package_publication_v1")
    contract["admission_status"] = "admitted_publication"
    path = tmp_path / "invalid-publication-admitted.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "publication_candidate_admitted_not_allowed" in _finding_ids(report)


def test_validator_rejects_real_execution_preflight_passed(tmp_path: Path):
    payload = _clone_base_payload()
    contract = _find_contract(payload, "dcc_conform_execution_v1")
    contract["preflight_status"] = "passed"
    path = tmp_path / "invalid-real-preflight-passed.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "real_execution_candidate_preflight_passed_not_allowed" in _finding_ids(report)


def test_validator_rejects_publication_preflight_passed(tmp_path: Path):
    payload = _clone_base_payload()
    contract = _find_contract(payload, "release_candidate_package_publication_v1")
    contract["preflight_status"] = "passed"
    path = tmp_path / "invalid-publication-preflight-passed.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "publication_candidate_preflight_passed_not_allowed" in _finding_ids(report)


def test_validator_rejects_missing_receipt_required_for_real_and_publication_candidates(tmp_path: Path):
    payload = _clone_base_payload()
    _find_contract(payload, "dcc_conform_execution_v1")["receipt_required"] = False
    _find_contract(payload, "release_candidate_package_publication_v1")["receipt_required"] = False
    path = tmp_path / "invalid-receipt-required.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_receipt_required_false" in finding_ids
    assert "publication_receipt_required_false" in finding_ids


def test_validator_rejects_requires_explicit_approval_false_for_real_and_publication_candidates(tmp_path: Path):
    payload = _clone_base_payload()
    _find_contract(payload, "dcc_conform_execution_v1")["requires_explicit_approval"] = False
    _find_contract(payload, "release_candidate_package_publication_v1")[
        "requires_explicit_approval"
    ] = False
    path = tmp_path / "invalid-requires-explicit-approval.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_requires_explicit_approval_false" in finding_ids
    assert "publication_requires_explicit_approval_false" in finding_ids


def test_validator_rejects_missing_rollback_required_for_real_and_publication_candidates(tmp_path: Path):
    payload = _clone_base_payload()
    _find_contract(payload, "dcc_conform_execution_v1")["rollback_plan_required"] = False
    _find_contract(payload, "release_candidate_package_publication_v1")["rollback_plan_required"] = False
    path = tmp_path / "invalid-rollback-required.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_rollback_plan_required_false" in finding_ids
    assert "publication_rollback_plan_required_false" in finding_ids


def test_validator_rejects_missing_operator_approval_required_for_real_and_publication_candidates(tmp_path: Path):
    payload = _clone_base_payload()
    _find_contract(payload, "dcc_conform_execution_v1")["operator_approval_required"] = False
    _find_contract(payload, "release_candidate_package_publication_v1")["operator_approval_required"] = False
    path = tmp_path / "invalid-operator-approval-required.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_operator_approval_required_false" in finding_ids
    assert "publication_operator_approval_required_false" in finding_ids


def test_validator_rejects_missing_approval_decision_reference_required_for_real_and_publication_candidates(tmp_path: Path):
    payload = _clone_base_payload()
    _find_contract(payload, "dcc_conform_execution_v1")[
        "approval_decision_reference_required"
    ] = False
    _find_contract(payload, "release_candidate_package_publication_v1")[
        "approval_decision_reference_required"
    ] = False
    path = tmp_path / "invalid-approval-decision-reference-required.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_approval_decision_reference_required_false" in finding_ids
    assert "publication_approval_decision_reference_required_false" in finding_ids


def test_validator_rejects_missing_blocked_surfaces_for_real_and_publication_candidates(tmp_path: Path):
    payload = _clone_base_payload()
    _find_contract(payload, "dcc_conform_execution_v1")["blocked_surfaces"] = []
    _find_contract(payload, "release_candidate_package_publication_v1")["blocked_surfaces"] = []
    path = tmp_path / "invalid-missing-blocked-surfaces.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_missing_blocked_surfaces" in finding_ids
    assert "publication_missing_blocked_surfaces" in finding_ids


def test_validator_rejects_missing_forbidden_paths_for_real_and_publication_candidates(tmp_path: Path):
    payload = _clone_base_payload()
    _find_contract(payload, "dcc_conform_execution_v1")["forbidden_paths"] = []
    _find_contract(payload, "release_candidate_package_publication_v1")["forbidden_paths"] = []
    path = tmp_path / "invalid-missing-forbidden-paths.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_missing_forbidden_paths" in finding_ids
    assert "publication_missing_forbidden_paths" in finding_ids


def test_validator_rejects_missing_allowed_sandbox_paths_for_real_and_publication_candidates(tmp_path: Path):
    payload = _clone_base_payload()
    _find_contract(payload, "dcc_conform_execution_v1")["allowed_sandbox_paths"] = ["docs/maxine"]
    _find_contract(payload, "release_candidate_package_publication_v1")["allowed_sandbox_paths"] = [
        "docs/maxine"
    ]
    path = tmp_path / "invalid-missing-allowed-sandbox-paths.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_missing_allowed_sandbox_paths" in finding_ids
    assert "publication_missing_allowed_sandbox_paths" in finding_ids


def test_validator_rejects_production_ready_or_publication_admitted_claims(tmp_path: Path):
    payload = _clone_base_payload()
    payload["production_ready_claimed"] = True
    payload["publication_admitted_claimed"] = True
    path = tmp_path / "invalid-ready-or-publication-claims.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "production_ready_claim_not_allowed" in finding_ids
    assert "publication_admitted_claim_not_allowed" in finding_ids


def test_validator_rejects_when_matrix_candidate_is_missing_a_preflight_contract(tmp_path: Path):
    payload = _clone_base_payload()
    payload["contracts"] = [
        c
        for c in payload["contracts"]
        if str(c.get("candidate_id", "")).strip() != "animation_smoke_execution_v1"
    ]
    path = tmp_path / "invalid-missing-contract.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "matrix_candidate_missing_preflight_contract" in _finding_ids(report)


def test_validator_rejects_preflight_candidate_missing_from_matrix(tmp_path: Path):
    payload = _clone_base_payload()
    extra = copy.deepcopy(_find_contract(payload, "dcc_conform_execution_v1"))
    extra["candidate_id"] = "unknown_execution_candidate_v1"
    extra["approval_phrase"] = "APPROVE EXECUTION ADMISSION unknown_execution_candidate_v1"
    payload["contracts"].append(extra)
    path = tmp_path / "invalid-extra-contract.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "preflight_candidate_missing_from_matrix" in _finding_ids(report)


def test_validator_rejects_candidate_type_mismatch_with_matrix(tmp_path: Path):
    payload = _clone_base_payload()
    _find_contract(payload, "dcc_conform_execution_v1")["candidate_type"] = "dry_run"
    path = tmp_path / "invalid-type-mismatch.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "candidate_type_mismatch_with_matrix" in _finding_ids(report)
