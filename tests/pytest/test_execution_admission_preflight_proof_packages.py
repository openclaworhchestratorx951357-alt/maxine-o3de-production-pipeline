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
    / "maxine_execution_admission_preflight_proof_packages.schema.json"
)
PROOF_PACKAGES_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "execution_admission_preflight_proof_packages_v1.json"
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
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_execution_admission_preflight_proof_packages.py"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_validator(
    path: Path,
    matrix_path: Path | None = None,
    preflight_path: Path | None = None,
) -> tuple[int, dict]:
    cmd = [sys.executable, str(VALIDATOR), str(path)]
    if matrix_path is not None:
        cmd.extend(["--matrix-path", str(matrix_path)])
    if preflight_path is not None:
        cmd.extend(["--preflight-path", str(preflight_path)])
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


def _find_package(payload: dict, candidate_id: str) -> dict:
    for package in payload.get("proof_packages", []):
        if (
            isinstance(package, dict)
            and str(package.get("candidate_id", "")).strip() == candidate_id
        ):
            return package
    raise AssertionError(f"proof package not found: {candidate_id}")


def _clone_base_payload() -> dict:
    return copy.deepcopy(_load(PROOF_PACKAGES_EXAMPLE))


def test_proof_packages_example_validates_and_reports_blocked_posture():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    payload = _load(PROOF_PACKAGES_EXAMPLE)

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, [f"{'.'.join(str(p) for p in err.path)}: {err.message}" for err in errors]

    code, report = _run_validator(PROOF_PACKAGES_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["preflight_proof_packages_present"] is True
    assert report["admitted_noop_receipt_candidate_ids"] == ["release_candidate_package_receipt_noop_v1"]
    assert report["admitted_real_execution_candidate_ids"] == []
    assert report["admitted_publication_candidate_ids"] == []
    assert report["real_execution_preflight_passed_candidate_ids"] == []
    assert report["publication_preflight_passed_candidate_ids"] == []
    assert report["real_execution_admission_status"] == "blocked"
    assert report["publication_admission_status"] == "blocked"
    assert report["production_ready_claimed"] is False
    assert report["publication_admitted_claimed"] is False


def test_every_matrix_and_preflight_candidate_has_proof_package_and_types_match():
    packages = _load(PROOF_PACKAGES_EXAMPLE)
    matrix = _load(MATRIX_EXAMPLE)
    preflight = _load(PREFLIGHT_EXAMPLE)

    package_map = {
        str(item.get("candidate_id", "")).strip(): str(item.get("candidate_type", "")).strip()
        for item in packages.get("proof_packages", [])
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

    assert set(package_map) == set(matrix_map)
    assert set(package_map) == set(preflight_map)
    for candidate_id, candidate_type in package_map.items():
        assert matrix_map[candidate_id] == candidate_type
        assert preflight_map[candidate_id] == candidate_type

    code, report = _run_validator(PROOF_PACKAGES_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"


def test_validator_accepts_noop_only_satisfied_package():
    payload = _clone_base_payload()
    noop = _find_package(payload, "release_candidate_package_receipt_noop_v1")
    assert noop["candidate_type"] == "no_op_receipt"
    assert noop["admission_status"] == "admitted_no_op_only"
    assert noop["proof_package_status"] in {
        "satisfied_no_op_only",
        "satisfied_non_execution_only",
    }
    code, report = _run_validator(PROOF_PACKAGES_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"


def test_validator_rejects_noop_when_misclassified_as_real_execution(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "release_candidate_package_receipt_noop_v1")["candidate_type"] = "real_execution"
    path = tmp_path / "invalid-noop-real.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "noop_candidate_misclassified_as_real_execution" in _finding_ids(report)


def test_validator_rejects_noop_when_misclassified_as_publication(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "release_candidate_package_receipt_noop_v1")["candidate_type"] = "publication"
    path = tmp_path / "invalid-noop-publication.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "noop_candidate_misclassified_as_publication" in _finding_ids(report)


def test_validator_rejects_noop_marked_admitted_real_execution(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "release_candidate_package_receipt_noop_v1")[
        "admission_status"
    ] = "admitted_real_execution"
    path = tmp_path / "invalid-noop-admitted-real.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "noop_candidate_marked_admitted_real_execution" in _finding_ids(report)


def test_validator_rejects_noop_marked_admitted_publication(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "release_candidate_package_receipt_noop_v1")[
        "admission_status"
    ] = "admitted_publication"
    path = tmp_path / "invalid-noop-admitted-publication.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "noop_candidate_marked_admitted_publication" in _finding_ids(report)


def test_validator_rejects_future_real_execution_candidate_marked_admitted(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "dcc_conform_execution_v1")["admission_status"] = "admitted_real_execution"
    path = tmp_path / "invalid-real-admitted.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "real_execution_candidate_admitted_not_allowed" in _finding_ids(report)


def test_validator_rejects_future_publication_candidate_marked_admitted(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "release_candidate_package_publication_v1")[
        "admission_status"
    ] = "admitted_publication"
    path = tmp_path / "invalid-publication-admitted.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "publication_candidate_admitted_not_allowed" in _finding_ids(report)


def test_validator_rejects_future_real_execution_preflight_passed(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "dcc_conform_execution_v1")["preflight_passed"] = True
    path = tmp_path / "invalid-real-preflight-passed.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "real_execution_candidate_preflight_passed_not_allowed" in _finding_ids(report)


def test_validator_rejects_future_publication_preflight_passed(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "release_candidate_package_publication_v1")["preflight_passed"] = True
    path = tmp_path / "invalid-publication-preflight-passed.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "publication_candidate_preflight_passed_not_allowed" in _finding_ids(report)


def test_validator_rejects_future_real_or_publication_full_satisfaction_status(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "dcc_conform_execution_v1")["proof_package_status"] = "satisfied_non_execution_only"
    _find_package(payload, "release_candidate_package_publication_v1")[
        "proof_package_status"
    ] = "satisfied_no_op_only"
    path = tmp_path / "invalid-full-satisfaction-status.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_candidate_full_satisfaction_not_allowed" in finding_ids
    assert "publication_candidate_full_satisfaction_not_allowed" in finding_ids


def test_validator_rejects_empty_missing_evidence_items_for_real_and_publication(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "dcc_conform_execution_v1")["missing_evidence_items"] = []
    _find_package(payload, "release_candidate_package_publication_v1")[
        "missing_evidence_items"
    ] = []
    path = tmp_path / "invalid-empty-missing-evidence-items.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_missing_evidence_items_empty" in finding_ids
    assert "publication_missing_evidence_items_empty" in finding_ids


def test_validator_rejects_missing_blocked_reason_codes_for_real_and_publication(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "dcc_conform_execution_v1")["blocked_reason_codes"] = []
    _find_package(payload, "release_candidate_package_publication_v1")["blocked_reason_codes"] = []
    path = tmp_path / "invalid-missing-blocked-reason-codes.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_missing_blocked_reason_codes" in finding_ids
    assert "publication_missing_blocked_reason_codes" in finding_ids


def test_validator_rejects_missing_required_validator_for_real_and_publication(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "dcc_conform_execution_v1")["required_validator"] = ""
    _find_package(payload, "release_candidate_package_publication_v1")["required_validator"] = ""
    path = tmp_path / "invalid-missing-required-validator.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_missing_required_validator" in finding_ids
    assert "publication_missing_required_validator" in finding_ids


def test_validator_rejects_missing_required_receipt_schema_for_real_and_publication(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "dcc_conform_execution_v1")["required_receipt_schema"] = ""
    _find_package(payload, "release_candidate_package_publication_v1")[
        "required_receipt_schema"
    ] = ""
    path = tmp_path / "invalid-missing-required-receipt-schema.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_missing_required_receipt_schema" in finding_ids
    assert "publication_missing_required_receipt_schema" in finding_ids


def test_validator_rejects_missing_approval_phrase_required_for_real_and_publication(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "dcc_conform_execution_v1")["approval_phrase_required"] = ""
    _find_package(payload, "release_candidate_package_publication_v1")[
        "approval_phrase_required"
    ] = ""
    path = tmp_path / "invalid-missing-approval-phrase-required.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "real_execution_missing_approval_phrase_required" in finding_ids
    assert "publication_missing_approval_phrase_required" in finding_ids


def test_validator_rejects_production_ready_claim(tmp_path: Path):
    payload = _clone_base_payload()
    payload["production_ready_claimed"] = True
    path = tmp_path / "invalid-production-ready-claim.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "production_ready_claim_not_allowed" in _finding_ids(report)


def test_validator_rejects_publication_admitted_claim(tmp_path: Path):
    payload = _clone_base_payload()
    payload["publication_admitted_claimed"] = True
    path = tmp_path / "invalid-publication-admitted-claim.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "publication_admitted_claim_not_allowed" in _finding_ids(report)


def test_validator_rejects_real_execution_admission_status_admitted_without_candidate_ids(tmp_path: Path):
    payload = _clone_base_payload()
    payload["real_execution_admission_status"] = "admitted"
    payload["admitted_real_execution_candidate_ids"] = []
    path = tmp_path / "invalid-real-execution-admitted-without-ids.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "real_execution_status_admitted_without_candidates" in _finding_ids(report)


def test_validator_rejects_publication_admission_status_admitted_without_candidate_ids(tmp_path: Path):
    payload = _clone_base_payload()
    payload["publication_admission_status"] = "admitted"
    payload["admitted_publication_candidate_ids"] = []
    path = tmp_path / "invalid-publication-admitted-without-ids.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    assert "publication_status_admitted_without_candidates" in _finding_ids(report)


def test_validator_rejects_unsafe_forbidden_paths_status_claims(tmp_path: Path):
    payload = _clone_base_payload()
    _find_package(payload, "dcc_conform_execution_v1")["forbidden_paths_status"] = "unsafe"
    path = tmp_path / "invalid-unsafe-forbidden-paths-status.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "production_path_write_allowed_claim" in finding_ids
    assert "engine_path_write_allowed_claim" in finding_ids
    assert "cache_live_db_access_allowed_claim" in finding_ids


def test_validator_rejects_missing_matrix_or_preflight_coverage(tmp_path: Path):
    payload = _clone_base_payload()
    payload["proof_packages"] = [
        item
        for item in payload["proof_packages"]
        if str(item.get("candidate_id", "")).strip() != "animation_smoke_execution_v1"
    ]
    path = tmp_path / "invalid-missing-proof-package-candidate.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "matrix_candidate_missing_preflight_proof_package" in finding_ids
    assert "preflight_contract_candidate_missing_preflight_proof_package" in finding_ids


def test_validator_rejects_unknown_candidate_not_in_matrix_or_preflight(tmp_path: Path):
    payload = _clone_base_payload()
    extra = copy.deepcopy(_find_package(payload, "dcc_conform_execution_v1"))
    extra["candidate_id"] = "unknown_candidate_execution_v1"
    extra["approval_phrase_required"] = "APPROVE EXECUTION ADMISSION unknown_candidate_execution_v1"
    payload["proof_packages"].append(extra)
    path = tmp_path / "invalid-extra-unknown-candidate.json"
    _write(path, payload)

    code, report = _run_validator(path)
    assert code != 0
    finding_ids = _finding_ids(report)
    assert "preflight_proof_package_candidate_missing_from_matrix" in finding_ids
    assert "preflight_proof_package_candidate_missing_from_preflight_contracts" in finding_ids
