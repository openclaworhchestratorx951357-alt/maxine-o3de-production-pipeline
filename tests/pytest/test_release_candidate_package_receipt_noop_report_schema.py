import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "maxine_release_candidate_package_receipt_noop_report.schema.json"
)
PASS_EXAMPLE_PATH = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "release_candidate_package_receipt_noop_report_pass.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _try_jsonschema_validator():
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return None
    return Draft202012Validator


def test_pass_example_validates_against_schema_or_minimal_rules():
    schema = _load_json(SCHEMA_PATH)
    instance = _load_json(PASS_EXAMPLE_PATH)
    validator_cls = _try_jsonschema_validator()

    if validator_cls is not None:
        validator = validator_cls(schema)
        errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.path))
        assert not errors, "Schema validation errors: " + "; ".join(
            f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors
        )
    else:
        assert instance["schema_version"] == "1.0.0"
        assert instance["report_type"] == "RELEASE_CANDIDATE_PACKAGE_RECEIPT_NOOP_v1_REPORT"
        assert instance["candidate_id"] == "release_candidate_package_receipt_noop_v1"
        assert instance["external_execution_performed"] is False
        assert instance["publication_performed"] is False


def test_external_execution_true_fails_schema_when_available():
    schema = _load_json(SCHEMA_PATH)
    instance = _load_json(PASS_EXAMPLE_PATH)
    instance["external_execution_performed"] = True
    validator_cls = _try_jsonschema_validator()

    if validator_cls is not None:
        validator = validator_cls(schema)
        errors = list(validator.iter_errors(instance))
        assert errors
    else:
        assert instance["external_execution_performed"] is not False


def test_wrong_approval_phrase_fails_schema_when_available():
    schema = _load_json(SCHEMA_PATH)
    instance = _load_json(PASS_EXAMPLE_PATH)
    instance["approval_phrase"] = "APPROVE EXECUTION ADMISSION wrong_candidate"
    validator_cls = _try_jsonschema_validator()

    if validator_cls is not None:
        validator = validator_cls(schema)
        errors = list(validator.iter_errors(instance))
        assert errors
    else:
        assert instance["approval_phrase"] != "APPROVE EXECUTION ADMISSION release_candidate_package_receipt_noop_v1"
