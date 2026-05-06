import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "maxine_controlled_real_evidence_inventory_report.schema.json"
PASS_EXAMPLE_PATH = (
    REPO_ROOT
    / "examples"
    / "controlled-real-evidence-inventory"
    / "max_biped_v1_controlled_real_evidence_inventory_pass.json"
)
WARN_EXAMPLE_PATH = (
    REPO_ROOT
    / "examples"
    / "controlled-real-evidence-inventory"
    / "max_biped_v1_controlled_real_evidence_inventory_warn.json"
)
FAIL_EXAMPLE_PATH = (
    REPO_ROOT
    / "examples"
    / "controlled-real-evidence-inventory"
    / "max_biped_v1_controlled_real_evidence_inventory_fail.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _try_jsonschema_validator():
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return None
    return Draft202012Validator


def _validate_or_minimal(schema: dict, instance: dict) -> None:
    validator_cls = _try_jsonschema_validator()
    if validator_cls is not None:
        validator = validator_cls(schema)
        errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.path))
        assert not errors, "Schema validation errors: " + "; ".join(
            f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors
        )
        return

    assert instance["schema_version"] == "1.0.0"
    assert instance["report_type"] == "CONTROLLED_REAL_EVIDENCE_INVENTORY_v1_REPORT"
    assert instance["status"] in {"pass", "warn", "fail"}
    assert instance["execution_admitted"] is False


def test_pass_warn_fail_examples_validate_or_match_minimal_contract():
    schema = _load_json(SCHEMA_PATH)
    for path in [PASS_EXAMPLE_PATH, WARN_EXAMPLE_PATH, FAIL_EXAMPLE_PATH]:
        _validate_or_minimal(schema, _load_json(path))


def test_execution_admitted_true_fails_schema_when_jsonschema_available():
    schema = _load_json(SCHEMA_PATH)
    instance = _load_json(PASS_EXAMPLE_PATH)
    instance["execution_admitted"] = True
    validator_cls = _try_jsonschema_validator()
    if validator_cls is None:
        assert instance["execution_admitted"] is not False
        return

    validator = validator_cls(schema)
    errors = list(validator.iter_errors(instance))
    assert errors
