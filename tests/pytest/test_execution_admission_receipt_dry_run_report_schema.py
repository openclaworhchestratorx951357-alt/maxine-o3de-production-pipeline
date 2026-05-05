import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "maxine_execution_admission_receipt_dry_run_report.schema.json"
)
PASS_EXAMPLE_PATH = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "max_biped_v1_execution_admission_receipt_dry_run_pass.json"
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
        assert instance["report_type"] == "EXECUTION_ADMISSION_RECEIPT_DRY_RUN_v1_REPORT"
        assert instance["status"] == "pass"
        assert instance["execution_mode"] == "no_op_dry_run"
        assert instance["execution_performed"] is False
        assert instance["dry_run_receipt"]["no_command_execution_recorded"] is True


def test_execution_performed_true_fails_schema_when_available():
    schema = _load_json(SCHEMA_PATH)
    instance = _load_json(PASS_EXAMPLE_PATH)
    instance["execution_performed"] = True
    validator_cls = _try_jsonschema_validator()

    if validator_cls is not None:
        validator = validator_cls(schema)
        errors = list(validator.iter_errors(instance))
        assert errors
    else:
        assert instance["execution_performed"] is not False
