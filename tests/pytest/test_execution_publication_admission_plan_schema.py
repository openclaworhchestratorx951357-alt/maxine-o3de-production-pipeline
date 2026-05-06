import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "maxine_execution_publication_admission_plan.schema.json"
REVIEW_ONLY_PATH = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "release_candidate_package_receipt_noop_review_only.json"
)
BLOCKED_PATH = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "release_candidate_package_receipt_noop_blocked.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load_json(SCHEMA_PATH)
    return jsonschema.Draft202012Validator(schema)


def test_review_only_and_blocked_examples_validate():
    validator = _validator()
    for path in (REVIEW_ONLY_PATH, BLOCKED_PATH):
        payload = _load_json(path)
        errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
        assert not errors, f"{path} schema errors: {[err.message for err in errors]}"


def test_admitted_execution_claim_fails():
    validator = _validator()
    payload = _load_json(REVIEW_ONLY_PATH)
    payload["current_readiness"]["execution_admission_admitted"] = True
    payload["approval"]["approval_received"] = True

    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert errors, "expected schema failure when execution is claimed admitted in review-only slice"


def test_missing_blocked_surface_fails():
    validator = _validator()
    payload = _load_json(REVIEW_ONLY_PATH)
    payload["blocked_inputs"] = [
        value for value in payload["blocked_inputs"] if value != "o3de_execution"
    ]

    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert errors, "expected schema failure when blocked_inputs omits required execution surface"


def test_missing_blocked_write_surface_fails():
    validator = _validator()
    payload = _load_json(REVIEW_ONLY_PATH)
    payload["blocked_outputs"] = [
        value for value in payload["blocked_outputs"] if value != "production_path_write"
    ]

    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert errors, "expected schema failure when blocked_outputs omits production path write block"


def test_authoritative_id_claim_fails():
    validator = _validator()
    payload = _load_json(REVIEW_ONLY_PATH)
    payload["claim_status"]["source_uuid_status"] = "authoritative"

    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert errors, "expected schema failure when authoritative source UUID status is claimed"

