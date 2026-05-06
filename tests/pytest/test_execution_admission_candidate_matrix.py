import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = REPO_ROOT / "schemas" / "maxine_execution_admission_candidate_matrix.schema.json"
MATRIX_EXAMPLE = REPO_ROOT / "examples" / "execution-admission" / "execution_admission_candidate_matrix_v1.json"
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_execution_admission_candidate_matrix.py"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _find_candidate(payload: dict, candidate_id: str) -> dict:
    for item in payload.get("candidates", []):
        if isinstance(item, dict) and str(item.get("candidate_id", "")).strip() == candidate_id:
            return item
    raise AssertionError(f"candidate not found: {candidate_id}")


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


def test_matrix_example_validates_and_reports_blocked_real_and_publication():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    matrix = _load(MATRIX_EXAMPLE)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(matrix), key=lambda err: list(err.path))
    assert not errors, [f"{'.'.join(str(p) for p in err.path)}: {err.message}" for err in errors]

    code, payload = _run_validator(MATRIX_EXAMPLE)
    assert code == 0
    assert payload["status"] == "pass"
    assert payload["candidate_matrix_present"] is True
    assert payload["admitted_noop_receipt_candidate_ids"] == ["release_candidate_package_receipt_noop_v1"]
    assert payload["receipt_backed_candidate_ids"] == ["release_candidate_package_receipt_noop_v1"]
    assert payload["admitted_real_execution_candidate_ids"] == []
    assert payload["admitted_publication_candidate_ids"] == []
    assert payload["real_execution_admission_status"] == "blocked"
    assert payload["publication_admission_status"] == "blocked"


def test_validator_rejects_noop_candidate_when_misclassified_as_real_execution(tmp_path: Path):
    payload = _load(MATRIX_EXAMPLE)
    noop = _find_candidate(payload, "release_candidate_package_receipt_noop_v1")
    noop["candidate_type"] = "real_execution"
    path = tmp_path / "invalid-noop-real.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert report["status"] == "fail"
    assert "noop_candidate_misclassified_as_real_execution" in _finding_ids(report)


def test_validator_rejects_noop_candidate_when_misclassified_as_publication(tmp_path: Path):
    payload = _load(MATRIX_EXAMPLE)
    noop = _find_candidate(payload, "release_candidate_package_receipt_noop_v1")
    noop["candidate_type"] = "publication"
    path = tmp_path / "invalid-noop-publication.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert report["status"] == "fail"
    assert "noop_candidate_misclassified_as_publication" in _finding_ids(report)


def test_validator_rejects_admitted_real_execution_without_decision_reference(tmp_path: Path):
    payload = _load(MATRIX_EXAMPLE)
    candidate = _find_candidate(payload, "dcc_conform_execution_v1")
    candidate["current_status"] = "admitted"
    candidate.pop("explicit_admission_decision_ref", None)
    payload["real_execution_admission_status"] = "admitted"
    payload["admitted_real_execution_candidate_ids"] = ["dcc_conform_execution_v1"]
    path = tmp_path / "invalid-real-no-ref.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "real_execution_admitted_missing_decision_reference" in _finding_ids(report)


def test_validator_rejects_admitted_publication_without_decision_reference(tmp_path: Path):
    payload = _load(MATRIX_EXAMPLE)
    candidate = _find_candidate(payload, "release_candidate_package_publication_v1")
    candidate["current_status"] = "admitted"
    candidate.pop("explicit_admission_decision_ref", None)
    payload["publication_admission_status"] = "admitted"
    payload["admitted_publication_candidate_ids"] = ["release_candidate_package_publication_v1"]
    path = tmp_path / "invalid-pub-no-ref.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "publication_admitted_missing_decision_reference" in _finding_ids(report)


def test_validator_rejects_real_execution_without_explicit_approval_requirement(tmp_path: Path):
    payload = _load(MATRIX_EXAMPLE)
    candidate = _find_candidate(payload, "dcc_conform_execution_v1")
    candidate["requires_explicit_approval"] = False
    path = tmp_path / "invalid-real-requires-approval.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "real_execution_requires_explicit_approval_false" in _finding_ids(report)


def test_validator_rejects_publication_without_explicit_approval_requirement(tmp_path: Path):
    payload = _load(MATRIX_EXAMPLE)
    candidate = _find_candidate(payload, "release_candidate_package_publication_v1")
    candidate["requires_explicit_approval"] = False
    path = tmp_path / "invalid-publication-requires-approval.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "publication_requires_explicit_approval_false" in _finding_ids(report)


def test_validator_rejects_real_or_publication_candidate_without_receipt_required(tmp_path: Path):
    payload = _load(MATRIX_EXAMPLE)
    real_candidate = _find_candidate(payload, "dcc_conform_execution_v1")
    publication_candidate = _find_candidate(payload, "release_candidate_package_publication_v1")
    real_candidate["receipt_required"] = False
    publication_candidate["receipt_required"] = False
    path = tmp_path / "invalid-receipt-required.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_receipt_required_false" in finding_ids
    assert "publication_receipt_required_false" in finding_ids


def test_validator_rejects_real_or_publication_candidate_without_rollback_plan_required(tmp_path: Path):
    payload = _load(MATRIX_EXAMPLE)
    real_candidate = _find_candidate(payload, "dcc_conform_execution_v1")
    publication_candidate = _find_candidate(payload, "release_candidate_package_publication_v1")
    real_candidate["rollback_plan_required"] = False
    publication_candidate["rollback_plan_required"] = False
    path = tmp_path / "invalid-rollback-required.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_rollback_plan_required_false" in finding_ids
    assert "publication_rollback_plan_required_false" in finding_ids


def test_validator_rejects_real_or_publication_candidate_without_validator_or_tests_required(tmp_path: Path):
    payload = _load(MATRIX_EXAMPLE)
    real_candidate = _find_candidate(payload, "dcc_conform_execution_v1")
    publication_candidate = _find_candidate(payload, "release_candidate_package_publication_v1")
    real_candidate["validator_required"] = False
    real_candidate["tests_required"] = False
    publication_candidate["validator_required"] = False
    publication_candidate["tests_required"] = False
    path = tmp_path / "invalid-validator-tests-required.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_validator_required_false" in finding_ids
    assert "real_execution_tests_required_false" in finding_ids
    assert "publication_validator_required_false" in finding_ids
    assert "publication_tests_required_false" in finding_ids


def test_validator_rejects_real_execution_admission_status_admitted_without_references(tmp_path: Path):
    payload = _load(MATRIX_EXAMPLE)
    payload["real_execution_admission_status"] = "admitted"
    payload["admitted_real_execution_candidate_ids"] = []
    path = tmp_path / "invalid-real-status-no-candidates.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "real_execution_status_admitted_without_candidates" in _finding_ids(report)


def test_validator_rejects_publication_admission_status_admitted_without_references(tmp_path: Path):
    payload = _load(MATRIX_EXAMPLE)
    payload["publication_admission_status"] = "admitted"
    payload["admitted_publication_candidate_ids"] = []
    path = tmp_path / "invalid-publication-status-no-candidates.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "publication_status_admitted_without_candidates" in _finding_ids(report)


def test_validator_rejects_production_ready_claim_while_blocked(tmp_path: Path):
    payload = _load(MATRIX_EXAMPLE)
    payload["production_ready_claimed"] = True
    path = tmp_path / "invalid-production-ready-claim.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "production_ready_claim_not_allowed" in _finding_ids(report)
